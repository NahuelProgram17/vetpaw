import re
from collections import Counter
from datetime import timedelta
from math import ceil

from django.db.models import Case, Count, F, IntegerField, Q, TextField, Value, When
from django.db.models.functions import Cast
from django.utils import timezone
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response

from clinics.models import Clinic
from lost_pets.models import LostPet
from pets.models import Pet
from partners.models import BusinessProfile, ShelterProfile

from .models import BlockedUser, Comment, PetFollow, Post
from .privacy import privacy_for, visible_posts_for
from .serializers import PostSerializer, absolute_file_url
from .throttles import CommunityExploreThrottle

HASHTAG_RE = re.compile(r"#([\w-]{2,50})", flags=re.UNICODE)
ALLOWED_SECTIONS = {'all', 'pets', 'posts', 'clinics', 'businesses', 'shelters', 'hashtags', 'lost'}
ALLOWED_SORTS = {'recent', 'popular'}

SEARCH_STOPWORDS = {'en', 'de', 'del', 'la', 'las', 'el', 'los', 'y', 'con'}

SPECIES_ALIASES = {
    'perro': 'dog', 'perros': 'dog', 'dog': 'dog',
    'gato': 'cat', 'gatos': 'cat', 'cat': 'cat',
    'caballo': 'horse', 'caballos': 'horse', 'horse': 'horse',
    'conejo': 'rabbit', 'conejos': 'rabbit', 'rabbit': 'rabbit',
    'ave': 'bird', 'aves': 'bird', 'pajaro': 'bird', 'pájaro': 'bird', 'bird': 'bird',
    'vaca': 'cow', 'toro': 'cow', 'cow': 'cow',
    'hamster': 'hamster', 'hámster': 'hamster',
    'reptil': 'reptile', 'reptiles': 'reptile', 'reptile': 'reptile',
    'pez': 'fish', 'peces': 'fish', 'fish': 'fish',
    'otro': 'other', 'otros': 'other', 'other': 'other',
}


def _clean(value, max_length):
    return str(value or '').strip()[:max_length]


def _truthy(value):
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'si', 'sí'}


def _positive_int(value, default, maximum):
    try:
        return min(max(int(value), 1), maximum)
    except (TypeError, ValueError):
        return default


def _blocked_user_ids(user):
    if not user.is_authenticated:
        return []
    blocked = BlockedUser.objects.filter(blocker=user).values_list('blocked_id', flat=True)
    blockers = BlockedUser.objects.filter(blocked=user).values_list('blocker_id', flat=True)
    return list(set(blocked).union(blockers))


def _search_terms(query):
    words = re.findall(r"[\wáéíóúüñ-]+", query.lower().lstrip('#'), flags=re.UNICODE)
    return [word for word in words if len(word) >= 2 and word not in SEARCH_STOPWORDS][:8]


def _species_from_query(query):
    return {SPECIES_ALIASES[word] for word in _search_terms(query) if word in SPECIES_ALIASES}


def _paginate(queryset, page, page_size):
    total = queryset.count()
    start = (page - 1) * page_size
    rows = list(queryset[start:start + page_size])
    return rows, {
        'page': page,
        'page_size': page_size,
        'total': total,
        'pages': ceil(total / page_size) if total else 0,
        'has_more': start + page_size < total,
    }


def _pet_payload(request, pet):
    settings = privacy_for(pet.owner)
    show_location = not settings or settings.show_location
    return {
        'id': pet.id,
        'kind': 'pet',
        'name': pet.name,
        'species': pet.species,
        'species_display': pet.get_species_display(),
        'breed': pet.breed,
        'photo': absolute_file_url(request, pet.photo),
        'locality': pet.owner.locality if show_location else '',
        'province': pet.owner.province if show_location else '',
        'followers_count': getattr(pet, 'followers_total', pet.social_followers.count()),
        'posts_count': getattr(pet, 'posts_total', pet.community_posts.filter(
            moderation_status=Post.STATUS_PUBLISHED,
            is_public=True,
        ).count()),
        'following': bool(
            request.user.is_authenticated
            and PetFollow.objects.filter(follower=request.user, pet=pet).exists()
        ),
        'profile_url': f"/mascotas/{getattr(pet.social_profile, 'slug', '') or pet.id}",
        'owner_user_id': pet.owner_id,
    }


def _clinic_payload(request, clinic):
    services = clinic.services if isinstance(clinic.services, list) else []
    return {
        'id': clinic.id,
        'kind': 'clinic',
        'name': clinic.name,
        'slug': clinic.slug,
        'description': clinic.description[:220],
        'logo': absolute_file_url(request, clinic.logo),
        'locality': clinic.locality,
        'province': clinic.province,
        'is_24h': clinic.is_24h,
        'services': services[:5],
        'followers_count': getattr(clinic, 'followers_total', clinic.social_followers.count()),
        'following': bool(
            request.user.is_authenticated
            and PetFollow.objects.filter(follower=request.user, clinic=clinic).exists()
        ),
        'owner_user_id': clinic.owner_id,
        'posts_count': getattr(clinic, 'posts_total', 0),
        'profile_url': f'/clinicas/{clinic.slug}',
    }


def _business_payload(request, item):
    return {
        'id': item.id,
        'kind': 'business',
        'name': item.name,
        'slug': item.slug,
        'type': item.business_type,
        'type_display': item.get_business_type_display(),
        'description': item.description[:220],
        'logo': absolute_file_url(request, item.logo),
        'locality': item.locality,
        'province': item.province,
        'is_24h': item.is_24h,
        'home_service': item.home_service,
        'delivery': item.delivery,
        'accepts_reservations': item.accepts_reservations,
        'catalog_count': getattr(item, 'catalog_total', item.catalog_items.filter(is_active=True).count()),
        'promotions_count': getattr(item, 'promotions_total', 0),
        'services': (item.services if isinstance(item.services, list) else [])[:5],
        'is_verified': item.is_verified,
        'followers_count': getattr(item, 'followers_total', item.social_followers.count()),
        'following': bool(
            request.user.is_authenticated
            and PetFollow.objects.filter(follower=request.user, business=item).exists()
        ),
        'owner_user_id': item.owner_id,
        'posts_count': getattr(item, 'posts_total', 0),
        'profile_url': f'/negocios/{item.slug}',
    }


def _shelter_payload(request, item):
    return {
        'id': item.id,
        'kind': 'shelter',
        'name': item.name,
        'slug': item.slug,
        'type': item.shelter_type,
        'type_display': item.get_shelter_type_display(),
        'description': item.description[:220],
        'logo': absolute_file_url(request, item.logo),
        'locality': item.locality,
        'province': item.province,
        'capacity_status': item.capacity_status,
        'capacity_status_display': item.get_capacity_status_display(),
        'accepting_animals': item.accepting_animals,
        'needs_foster_homes': item.needs_foster_homes,
        'needs_volunteers': item.needs_volunteers,
        'is_verified': item.is_verified,
        'followers_count': getattr(item, 'followers_total', item.social_followers.count()),
        'following': bool(
            request.user.is_authenticated
            and PetFollow.objects.filter(follower=request.user, shelter=item).exists()
        ),
        'owner_user_id': item.owner_id,
        'posts_count': getattr(item, 'posts_total', 0),
        'profile_url': f'/refugios/{item.slug}',
    }


def _lost_payload(request, item):
    return {
        'id': item.id,
        'kind': 'lost',
        'pet_name': item.pet_name or 'Mascota',
        'report_type': item.report_type,
        'report_type_display': item.get_report_type_display(),
        'species': item.species,
        'species_display': item.get_species_display() if item.species else '',
        'breed': item.breed,
        'description': item.description[:240],
        'photo': absolute_file_url(request, item.photo),
        'locality': item.locality,
        'province': item.province,
        'incident_date': item.incident_date,
        'created_at': item.created_at,
        'target_url': f'/mascotas-perdidas?aviso={item.id}',
    }


def _hashtag_rows(posts_queryset, query='', limit=500):
    counter = Counter()
    for text in posts_queryset.values_list('text', flat=True)[:limit]:
        for tag in HASHTAG_RE.findall(text or ''):
            counter[tag.lower()] += 1
    needle = query.lower().lstrip('#').strip()
    rows = [
        {
            'kind': 'hashtag',
            'name': name,
            'label': f'#{name}',
            'count': count,
            'target_url': f'/comunidad?hashtag={name}',
        }
        for name, count in counter.most_common()
        if not needle or needle in name
    ]
    return rows


def _build_suggestions(pets, clinics, businesses, shelters, hashtags, posts, limit=10):
    suggestions = []
    for pet in pets[:3]:
        suggestions.append({
            'kind': 'pet', 'id': pet['id'], 'title': pet['name'],
            'subtitle': ' · '.join(filter(None, [pet['species_display'], pet['locality']])),
            'image': pet['photo'], 'target_url': pet['profile_url'],
        })
    for clinic in clinics[:2]:
        suggestions.append({
            'kind': 'clinic', 'id': clinic['id'], 'title': clinic['name'],
            'subtitle': ' · '.join(filter(None, [clinic['locality'], clinic['province']])),
            'image': clinic['logo'], 'target_url': clinic['profile_url'],
        })
    for item in businesses[:2]:
        suggestions.append({
            'kind': 'business', 'id': item['id'], 'title': item['name'],
            'subtitle': ' · '.join(filter(None, [item['type_display'], item['locality']])),
            'image': item['logo'], 'target_url': item['profile_url'],
        })
    for item in shelters[:2]:
        suggestions.append({
            'kind': 'shelter', 'id': item['id'], 'title': item['name'],
            'subtitle': ' · '.join(filter(None, [item['type_display'], item['locality']])),
            'image': item['logo'], 'target_url': item['profile_url'],
        })
    for tag in hashtags[:2]:
        suggestions.append({
            'kind': 'hashtag', 'id': tag['name'], 'title': tag['label'],
            'subtitle': f"{tag['count']} publicaciones", 'image': None,
            'target_url': tag['target_url'],
        })
    if posts:
        post = posts[0]
        suggestions.append({
            'kind': 'post', 'id': post['id'],
            'title': post.get('actor', {}).get('name') or 'Publicación',
            'subtitle': (post.get('text') or 'Publicación de VetPaw')[:90],
            'image': post.get('image_url'),
            'target_url': f"/comunidad?publicacion={post['id']}",
        })
    return suggestions[:limit]


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@throttle_classes([CommunityExploreThrottle])
def community_explore(request):
    query = _clean(request.query_params.get('q'), 80)
    section = _clean(request.query_params.get('section'), 20).lower() or 'all'
    if section not in ALLOWED_SECTIONS:
        section = 'all'
    sort = _clean(request.query_params.get('sort'), 20).lower() or 'popular'
    if sort not in ALLOWED_SORTS:
        sort = 'popular'

    species = _clean(request.query_params.get('species'), 20).lower()
    if species and species not in dict(Pet.SPECIES_CHOICES):
        species = ''
    locality = _clean(request.query_params.get('locality'), 100)
    province = _clean(request.query_params.get('province'), 100)
    clinic_content_type = _clean(request.query_params.get('clinic_content_type'), 24)
    if clinic_content_type and clinic_content_type not in dict(Post.CLINIC_CONTENT_CHOICES):
        clinic_content_type = ''
    page = _positive_int(request.query_params.get('page'), 1, 10000)
    page_size = _positive_int(request.query_params.get('page_size'), 12, 30)
    all_limit = min(page_size, 8)

    blocked_ids = _blocked_user_ids(request.user)
    query_terms = _search_terms(query)
    query_species = _species_from_query(query)
    preferred_species = []
    if request.user.is_authenticated and getattr(request.user, 'role', '') == 'owner':
        preferred_species = list(request.user.pets.values_list('species', flat=True).distinct())

    pets = Pet.objects.filter(social_profile__is_public=True).select_related('owner', 'social_profile').annotate(
        followers_total=Count('social_followers', distinct=True),
        posts_total=Count(
            'community_posts',
            filter=Q(
                community_posts__moderation_status=Post.STATUS_PUBLISHED,
                community_posts__is_public=True,
            ),
            distinct=True,
        ),
    )
    if blocked_ids:
        pets = pets.exclude(owner_id__in=blocked_ids)
    if query_terms:
        for term in query_terms:
            pet_q = (
                Q(name__icontains=term)
                | Q(breed__icontains=term)
                | Q(owner__username__icontains=term)
                | Q(owner__first_name__icontains=term)
                | Q(owner__last_name__icontains=term)
                | Q(owner__locality__icontains=term)
                | Q(owner__province__icontains=term)
            )
            term_species = _species_from_query(term)
            if term_species:
                pet_q |= Q(species__in=term_species)
            pets = pets.filter(pet_q)
    if species:
        pets = pets.filter(species=species)
    if locality:
        pets = pets.filter(owner__locality__icontains=locality)
    if province:
        pets = pets.filter(owner__province__icontains=province)
    if request.user.is_authenticated and request.user.locality:
        pets = pets.annotate(
            same_locality=Case(
                When(owner__locality__iexact=request.user.locality, then=Value(1)),
                default=Value(0), output_field=IntegerField(),
            )
        )
    else:
        pets = pets.annotate(same_locality=Value(0, output_field=IntegerField()))
    if preferred_species:
        pets = pets.annotate(
            preferred_species=Case(
                When(species__in=preferred_species, then=Value(1)),
                default=Value(0), output_field=IntegerField(),
            )
        )
    else:
        pets = pets.annotate(preferred_species=Value(0, output_field=IntegerField()))
    pet_order = ('-same_locality', '-preferred_species', '-followers_total', '-posts_total', '-created_at') if sort == 'popular' else ('-same_locality', '-preferred_species', '-created_at')
    pets = pets.order_by(*pet_order)

    clinics = Clinic.objects.filter(is_active=True).select_related('owner').annotate(
        services_search=Cast('services', TextField()),
        followers_total=Count('social_followers', distinct=True),
        posts_total=Count(
            'community_posts',
            filter=Q(
                community_posts__moderation_status=Post.STATUS_PUBLISHED,
                community_posts__is_public=True,
            ),
            distinct=True,
        )
    )
    if blocked_ids:
        clinics = clinics.exclude(owner_id__in=blocked_ids)
    if query_terms:
        for term in query_terms:
            clinics = clinics.filter(
                Q(name__icontains=term)
                | Q(description__icontains=term)
                | Q(address__icontains=term)
                | Q(locality__icontains=term)
                | Q(province__icontains=term)
                | Q(services_search__icontains=term)
            )
    if locality:
        clinics = clinics.filter(locality__icontains=locality)
    if province:
        clinics = clinics.filter(province__icontains=province)
    only_24h = _clean(request.query_params.get('is_24h'), 10).lower() in ('1', 'true', 'yes')
    if only_24h:
        clinics = clinics.filter(is_24h=True)
    if request.user.is_authenticated and request.user.locality:
        clinics = clinics.annotate(
            same_locality=Case(
                When(locality__iexact=request.user.locality, then=Value(1)),
                default=Value(0), output_field=IntegerField(),
            )
        )
    else:
        clinics = clinics.annotate(same_locality=Value(0, output_field=IntegerField()))
    clinic_order = ('-same_locality', '-posts_total', '-created_at') if sort == 'popular' else ('-same_locality', '-created_at')
    clinics = clinics.order_by(*clinic_order)

    businesses = BusinessProfile.objects.filter(is_active=True, owner__is_approved=True).select_related('owner').annotate(
        services_search=Cast('services', TextField()),
        followers_total=Count('social_followers', distinct=True),
        posts_total=Count(
            'community_posts',
            filter=Q(community_posts__moderation_status=Post.STATUS_PUBLISHED, community_posts__is_public=True),
            distinct=True,
        ),
        catalog_total=Count('catalog_items', filter=Q(catalog_items__is_active=True), distinct=True),
        promotions_total=Count(
            'commerce_promotions',
            filter=Q(
                commerce_promotions__is_active=True,
                commerce_promotions__starts_at__lte=timezone.now(),
                commerce_promotions__ends_at__gte=timezone.now(),
            ),
            distinct=True,
        )
    )
    if blocked_ids:
        businesses = businesses.exclude(owner_id__in=blocked_ids)
    if query_terms:
        for term in query_terms:
            businesses = businesses.filter(
                Q(name__icontains=term) | Q(description__icontains=term)
                | Q(locality__icontains=term) | Q(province__icontains=term)
                | Q(business_type__icontains=term) | Q(services_search__icontains=term)
            )
    if locality:
        businesses = businesses.filter(locality__icontains=locality)
    if province:
        businesses = businesses.filter(province__icontains=province)
    if only_24h:
        businesses = businesses.filter(is_24h=True)
    if _truthy(request.query_params.get('home_service')):
        businesses = businesses.filter(home_service=True)
    if _truthy(request.query_params.get('accepts_reservations')):
        businesses = businesses.filter(accepts_reservations=True)
    if _truthy(request.query_params.get('has_promotions')):
        businesses = businesses.filter(promotions_total__gt=0)
    business_type = _clean(request.query_params.get('business_type'), 30)
    if business_type in dict(BusinessProfile.BUSINESS_TYPE_CHOICES):
        businesses = businesses.filter(business_type=business_type)
    if request.user.is_authenticated and request.user.locality:
        businesses = businesses.annotate(same_locality=Case(When(locality__iexact=request.user.locality, then=Value(1)), default=Value(0), output_field=IntegerField()))
    else:
        businesses = businesses.annotate(same_locality=Value(0, output_field=IntegerField()))
    businesses = businesses.order_by('-same_locality', '-is_verified', '-posts_total', '-created_at') if sort == 'popular' else businesses.order_by('-same_locality', '-created_at')

    shelters = ShelterProfile.objects.filter(is_active=True, owner__is_approved=True).select_related('owner').annotate(
        activities_search=Cast('activities', TextField()),
        followers_total=Count('social_followers', distinct=True),
        posts_total=Count(
            'community_posts',
            filter=Q(community_posts__moderation_status=Post.STATUS_PUBLISHED, community_posts__is_public=True),
            distinct=True,
        )
    )
    if blocked_ids:
        shelters = shelters.exclude(owner_id__in=blocked_ids)
    if query_terms:
        for term in query_terms:
            shelters = shelters.filter(
                Q(name__icontains=term) | Q(description__icontains=term)
                | Q(locality__icontains=term) | Q(province__icontains=term)
                | Q(shelter_type__icontains=term) | Q(activities_search__icontains=term)
            )
    if locality:
        shelters = shelters.filter(locality__icontains=locality)
    if province:
        shelters = shelters.filter(province__icontains=province)
    shelter_type = _clean(request.query_params.get('shelter_type'), 30)
    if shelter_type in dict(ShelterProfile.SHELTER_TYPE_CHOICES):
        shelters = shelters.filter(shelter_type=shelter_type)
    accepting_only = _clean(request.query_params.get('accepting_animals'), 10).lower() in ('1', 'true', 'yes')
    if accepting_only:
        shelters = shelters.filter(accepting_animals=True)
    if request.user.is_authenticated and request.user.locality:
        shelters = shelters.annotate(same_locality=Case(When(locality__iexact=request.user.locality, then=Value(1)), default=Value(0), output_field=IntegerField()))
    else:
        shelters = shelters.annotate(same_locality=Value(0, output_field=IntegerField()))
    shelters = shelters.order_by('-same_locality', '-is_verified', '-posts_total', '-created_at') if sort == 'popular' else shelters.order_by('-same_locality', '-created_at')

    posts = Post.objects.filter(
        is_public=True,
        moderation_status=Post.STATUS_PUBLISHED,
    ).filter(
        Q(related_lost_pet__isnull=True) | Q(related_lost_pet__expires_at__gt=timezone.now())
    ).filter(
        Q(business__isnull=True) | Q(business__is_active=True, business__owner__is_approved=True)
    ).filter(
        Q(shelter__isnull=True) | Q(shelter__is_active=True, shelter__owner__is_approved=True)
    ).select_related(
        'created_by', 'pet__owner', 'pet__social_profile', 'clinic__owner',
        'business__owner', 'shelter__owner', 'related_lost_pet__owner', 'related_birthday__pet',
        'related_clinic_campaign__clinic__owner',
    ).prefetch_related('comments__author').annotate(
        reactions_total=Count('reactions', distinct=True),
        comments_total=Count(
            'comments',
            filter=Q(comments__moderation_status=Comment.STATUS_PUBLISHED),
            distinct=True,
        ),
    )
    posts = visible_posts_for(posts, request.user)
    if blocked_ids:
        posts = posts.exclude(created_by_id__in=blocked_ids)
    if query_terms:
        for term in query_terms:
            normalized_tag = re.sub(r'[^\w-]', '', term, flags=re.UNICODE)
            post_q = (
                Q(text__icontains=term)
                | Q(pet__name__icontains=term)
                | Q(pet__breed__icontains=term)
                | Q(clinic__name__icontains=term)
                | Q(business__name__icontains=term)
                | Q(shelter__name__icontains=term)
                | Q(locality__icontains=term)
                | Q(province__icontains=term)
                | Q(related_lost_pet__pet_name__icontains=term)
                | Q(related_lost_pet__breed__icontains=term)
            )
            if normalized_tag:
                post_q |= Q(text__icontains=f'#{normalized_tag}')
            term_species = _species_from_query(term)
            if term_species:
                post_q |= Q(pet__species__in=term_species) | Q(related_lost_pet__species__in=term_species)
            posts = posts.filter(post_q)
    if species:
        posts = posts.filter(Q(pet__species=species) | Q(related_lost_pet__species=species))
    if locality:
        posts = posts.filter(locality__icontains=locality)
    if province:
        posts = posts.filter(province__icontains=province)
    if clinic_content_type:
        posts = posts.filter(clinic_content_type=clinic_content_type)
    if sort == 'popular':
        recent_week = timezone.now() - timedelta(days=7)
        recent_month = timezone.now() - timedelta(days=30)
        posts = posts.annotate(
            recency_boost=Case(
                When(created_at__gte=recent_week, then=Value(6)),
                When(created_at__gte=recent_month, then=Value(3)),
                default=Value(0), output_field=IntegerField(),
            ),
            popularity=(F('reactions_total') * Value(2)) + (F('comments_total') * Value(3)) + F('recency_boost'),
        ).order_by('-popularity', '-created_at')
    else:
        posts = posts.order_by('-created_at')

    lost = LostPet.objects.filter(expires_at__gt=timezone.now()).select_related('owner')
    if blocked_ids:
        lost = lost.exclude(owner_id__in=blocked_ids)
    if query_terms:
        for term in query_terms:
            lost_q = (
                Q(pet_name__icontains=term)
                | Q(breed__icontains=term)
                | Q(description__icontains=term)
                | Q(locality__icontains=term)
                | Q(province__icontains=term)
            )
            term_species = _species_from_query(term)
            if term_species:
                lost_q |= Q(species__in=term_species)
            lost = lost.filter(lost_q)
    if species:
        lost = lost.filter(species=species)
    if locality:
        lost = lost.filter(locality__icontains=locality)
    if province:
        lost = lost.filter(province__icontains=province)
    lost = lost.order_by('-created_at')

    hashtag_source = visible_posts_for(Post.objects.filter(
        is_public=True,
        moderation_status=Post.STATUS_PUBLISHED,
        created_at__gte=timezone.now() - timedelta(days=45),
    ), request.user)
    if blocked_ids:
        hashtag_source = hashtag_source.exclude(created_by_id__in=blocked_ids)
    if locality:
        hashtag_source = hashtag_source.filter(locality__icontains=locality)
    if province:
        hashtag_source = hashtag_source.filter(province__icontains=province)
    hashtag_rows = _hashtag_rows(hashtag_source, query=query, limit=1000)

    counts = {
        'pets': pets.count(),
        'posts': posts.count(),
        'clinics': clinics.count(),
        'businesses': businesses.count(),
        'shelters': shelters.count(),
        'hashtags': len(hashtag_rows),
        'lost': lost.count(),
    }
    results = {'pets': [], 'posts': [], 'clinics': [], 'businesses': [], 'shelters': [], 'hashtags': [], 'lost_pets': []}
    pagination = None

    if section == 'all':
        pet_rows = list(pets[:all_limit])
        clinic_rows = list(clinics[:all_limit])
        business_rows = list(businesses[:all_limit])
        shelter_rows = list(shelters[:all_limit])
        post_rows = list(posts[:all_limit])
        lost_rows = list(lost[:min(all_limit, 6)])
        results['pets'] = [_pet_payload(request, item) for item in pet_rows]
        results['clinics'] = [_clinic_payload(request, item) for item in clinic_rows]
        results['businesses'] = [_business_payload(request, item) for item in business_rows]
        results['shelters'] = [_shelter_payload(request, item) for item in shelter_rows]
        results['posts'] = PostSerializer(post_rows, many=True, context={'request': request}).data
        results['hashtags'] = hashtag_rows[:all_limit]
        results['lost_pets'] = [_lost_payload(request, item) for item in lost_rows]
    elif section == 'pets':
        rows, pagination = _paginate(pets, page, page_size)
        results['pets'] = [_pet_payload(request, item) for item in rows]
    elif section == 'clinics':
        rows, pagination = _paginate(clinics, page, page_size)
        results['clinics'] = [_clinic_payload(request, item) for item in rows]
    elif section == 'businesses':
        rows, pagination = _paginate(businesses, page, page_size)
        results['businesses'] = [_business_payload(request, item) for item in rows]
    elif section == 'shelters':
        rows, pagination = _paginate(shelters, page, page_size)
        results['shelters'] = [_shelter_payload(request, item) for item in rows]
    elif section == 'posts':
        rows, pagination = _paginate(posts, page, page_size)
        results['posts'] = PostSerializer(rows, many=True, context={'request': request}).data
    elif section == 'lost':
        rows, pagination = _paginate(lost, page, page_size)
        results['lost_pets'] = [_lost_payload(request, item) for item in rows]
    elif section == 'hashtags':
        total = len(hashtag_rows)
        start = (page - 1) * page_size
        results['hashtags'] = hashtag_rows[start:start + page_size]
        pagination = {
            'page': page,
            'page_size': page_size,
            'total': total,
            'pages': ceil(total / page_size) if total else 0,
            'has_more': start + page_size < total,
        }

    suggestions = []
    if query:
        suggestion_pets = [_pet_payload(request, item) for item in list(pets[:3])]
        suggestion_clinics = [_clinic_payload(request, item) for item in list(clinics[:2])]
        suggestion_businesses = [_business_payload(request, item) for item in list(businesses[:2])]
        suggestion_shelters = [_shelter_payload(request, item) for item in list(shelters[:2])]
        suggestion_posts = PostSerializer(list(posts[:1]), many=True, context={'request': request}).data
        suggestions = _build_suggestions(
            suggestion_pets,
            suggestion_clinics,
            suggestion_businesses,
            suggestion_shelters,
            hashtag_rows[:2],
            suggestion_posts,
        )

    trending_hashtags = _hashtag_rows(hashtag_source, query='', limit=1000)[:10]
    locality_source = visible_posts_for(Post.objects.filter(
        is_public=True,
        moderation_status=Post.STATUS_PUBLISHED,
    ), request.user).exclude(locality='')
    if blocked_ids:
        locality_source = locality_source.exclude(created_by_id__in=blocked_ids)
    popular_localities = [
        {'name': row['locality'], 'count': row['total']}
        for row in locality_source.values('locality').annotate(total=Count('id')).order_by('-total', 'locality')[:8]
    ]

    return Response({
        'query': query,
        'section': section,
        'sort': sort,
        'filters': {
            'species': species,
            'locality': locality,
            'province': province,
            'is_24h': only_24h,
            'business_type': business_type,
            'shelter_type': shelter_type,
            'accepting_animals': accepting_only,
        },
        'counts': counts,
        'results': results,
        'pagination': pagination,
        'suggestions': suggestions,
        'trending_hashtags': trending_hashtags,
        'popular_localities': popular_localities,
        'business_type_options': [{'value': value, 'label': label} for value, label in BusinessProfile.BUSINESS_TYPE_CHOICES],
        'shelter_type_options': [{'value': value, 'label': label} for value, label in ShelterProfile.SHELTER_TYPE_CHOICES],
        'species_options': [
            {'value': value, 'label': label}
            for value, label in Pet.SPECIES_CHOICES
        ],
    })
