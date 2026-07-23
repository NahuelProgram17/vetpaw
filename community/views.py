import re
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, F, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action, api_view, parser_classes, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from clinics.models import Clinic
from lost_pets.models import LostPet
from pets.models import BirthdayCelebration, Pet
from partners.models import BusinessProfile, ShelterProfile

from .models import (
    BlockedUser, Comment, CommentReaction, CommunityNotification, CommunityPrivacySettings,
    HiddenPost, MutedUser, PetFollow, PetFollowRequest, PetSocialProfile, Post,
    PushSubscription, Reaction, Report, SavedPost,
)
from .notification_utils import (
    create_comment_notification,
    create_comment_reaction_notification,
    create_follow_notification,
    create_follow_request_notification,
    create_reaction_notification,
    create_reply_notification,
    remove_comment_reaction_notification,
    remove_follow_notification,
    remove_follow_request_notification,
    remove_reaction_notification,
    sync_mention_notifications,
)
from .permissions import IsOwnerOrModerator, is_community_moderator
from .privacy import (
    can_access_pet_profile, can_comment_on_post, privacy_for,
    users_blocked_between, visible_posts_for,
)
from .push_utils import MAX_ACTIVE_SUBSCRIPTIONS, push_is_configured, send_test_push
from .social_profiles import (
    blocked_user_ids,
    follow_queryset_for_target,
    identity_for_follow,
    is_target_public,
    primary_identity_for_user,
    resolve_profile,
    target_kwargs,
    target_owner,
)
from .throttles import CommunityActionThrottle, CommunityCommentThrottle, CommunityExploreThrottle, CommunityPostThrottle
from .serializers import (
    BlockedUserSerializer,
    CommentSerializer,
    CommunityPrivacySettingsSerializer,
    HiddenPostSerializer,
    MutedUserSerializer,
    PetFollowRequestSerializer,
    CommunityNotificationSerializer,
    PetSocialProfileSerializer,
    PostSerializer,
    PushSubscriptionInputSerializer,
    PushSubscriptionSerializer,
    ReportSerializer,
    absolute_file_url,
)


class CommunityPostPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 30


class CommunityPostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    pagination_class = CommunityPostPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_throttles(self):
        if self.action == 'create':
            return [CommunityPostThrottle()]
        if self.action == 'comments_action' and self.request.method == 'POST':
            return [CommunityCommentThrottle()]
        if self.action == 'share':
            return [CommunityExploreThrottle()]
        if self.action in ('react', 'save_post'):
            return [CommunityActionThrottle()]
        return []

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'share'):
            return [permissions.AllowAny()]
        if self.action in ('destroy', 'partial_update', 'update'):
            return [permissions.IsAuthenticated(), IsOwnerOrModerator()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        queryset = Post.objects.filter(
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
            'business__owner', 'shelter__owner',
            'related_lost_pet__owner', 'related_birthday__pet',
            'related_clinic_campaign__clinic__owner',
        ).prefetch_related('comments__author').annotate(
            reactions_total=Count('reactions', distinct=True),
            comments_total=Count('comments', filter=Q(comments__moderation_status=Comment.STATUS_PUBLISHED), distinct=True),
        )

        request = self.request
        user = request.user
        queryset = visible_posts_for(queryset, user)

        feed = request.query_params.get('feed')
        if feed == 'following':
            if not user.is_authenticated:
                return queryset.none()
            follows = PetFollow.objects.filter(follower=user)
            pet_ids = follows.exclude(pet_id=None).values_list('pet_id', flat=True)
            clinic_ids = follows.exclude(clinic_id=None).values_list('clinic_id', flat=True)
            business_ids = follows.exclude(business_id=None).values_list('business_id', flat=True)
            shelter_ids = follows.exclude(shelter_id=None).values_list('shelter_id', flat=True)
            queryset = queryset.filter(
                Q(pet_id__in=pet_ids)
                | Q(clinic_id__in=clinic_ids)
                | Q(business_id__in=business_ids)
                | Q(shelter_id__in=shelter_ids)
                | Q(created_by=user)
            )
        elif feed == 'saved':
            if not user.is_authenticated:
                return queryset.none()
            saved_ids = SavedPost.objects.filter(user=user).values_list('post_id', flat=True)
            queryset = queryset.filter(id__in=saved_ids)

        post_type = request.query_params.get('type')
        if post_type in dict(Post.TYPE_CHOICES):
            queryset = queryset.filter(post_type=post_type)
        pet_id = request.query_params.get('pet')
        if pet_id:
            queryset = queryset.filter(pet_id=pet_id)
        clinic_id = request.query_params.get('clinic')
        if clinic_id:
            queryset = queryset.filter(clinic_id=clinic_id)
        business_id = request.query_params.get('business')
        if business_id:
            queryset = queryset.filter(business_id=business_id)
        shelter_id = request.query_params.get('shelter')
        if shelter_id:
            queryset = queryset.filter(shelter_id=shelter_id)
        locality = request.query_params.get('locality')
        if locality:
            queryset = queryset.filter(locality__icontains=locality)
        province = request.query_params.get('province')
        if province:
            queryset = queryset.filter(province__icontains=province)
        hashtag = request.query_params.get('hashtag')
        if hashtag:
            normalized_hashtag = re.sub(r'[^\w-]', '', hashtag.lstrip('#'), flags=re.UNICODE)[:50]
            if normalized_hashtag:
                queryset = queryset.filter(text__icontains=f'#{normalized_hashtag}')

        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(text__icontains=search)
                | Q(pet__name__icontains=search)
                | Q(clinic__name__icontains=search)
                | Q(business__name__icontains=search)
                | Q(shelter__name__icontains=search)
                | Q(related_lost_pet__pet_name__icontains=search)
            )
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        post = serializer.save()
        sync_mention_notifications(post.text, self.request.user, post)

    def perform_update(self, serializer):
        instance = self.get_object()
        allowed = {'text', 'image', 'comment_permission'}
        cleaned = {key: value for key, value in serializer.validated_data.items() if key in allowed}
        for key, value in cleaned.items():
            setattr(instance, key, value)
        if cleaned:
            instance.save(update_fields=[*cleaned.keys(), 'updated_at'])
        sync_mention_notifications(instance.text, self.request.user, instance)

    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        post = self.get_object()
        Post.objects.filter(pk=post.pk).update(shares_count=F('shares_count') + 1)
        post.refresh_from_db(fields=['shares_count'])
        return Response({'shares_count': post.shares_count})

    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        post = self.get_object()
        reaction, created = Reaction.objects.get_or_create(post=post, user=request.user)
        if created:
            create_reaction_notification(post, request.user)
        else:
            reaction.delete()
            remove_reaction_notification(post, request.user)
        return Response({
            'reacted': created,
            'reactions_count': post.reactions.count(),
        })

    @action(detail=True, methods=['post'])
    def save_post(self, request, pk=None):
        post = self.get_object()
        saved, created = SavedPost.objects.get_or_create(post=post, user=request.user)
        if not created:
            saved.delete()
        return Response({'saved': created})

    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments_action(self, request, pk=None):
        post = self.get_object()
        if request.method == 'GET':
            blocked_user_ids = set()
            if request.user.is_authenticated:
                blocked = BlockedUser.objects.filter(blocker=request.user).values_list('blocked_id', flat=True)
                blockers = BlockedUser.objects.filter(blocked=request.user).values_list('blocker_id', flat=True)
                blocked_user_ids = set(blocked).union(blockers)

            replies = Comment.objects.filter(
                moderation_status=Comment.STATUS_PUBLISHED,
            ).exclude(author_id__in=blocked_user_ids).select_related('author').annotate(
                reactions_total=Count('reactions', distinct=True),
            ).order_by('created_at')
            comments = post.comments.filter(
                moderation_status=Comment.STATUS_PUBLISHED,
                parent__isnull=True,
            ).exclude(author_id__in=blocked_user_ids).select_related('author').annotate(
                reactions_total=Count('reactions', distinct=True),
            ).prefetch_related(Prefetch('replies', queryset=replies, to_attr='_visible_replies'))

            all_ids = []
            rows = list(comments)
            for comment in rows:
                all_ids.append(comment.id)
                all_ids.extend(reply.id for reply in getattr(comment, '_visible_replies', []))
            reacted_ids = set()
            if request.user.is_authenticated and all_ids:
                reacted_ids = set(CommentReaction.objects.filter(
                    user=request.user,
                    comment_id__in=all_ids,
                ).values_list('comment_id', flat=True))
            context = {'request': request, 'reacted_comment_ids': reacted_ids}
            return Response(CommentSerializer(rows, many=True, context=context).data)

        allowed, reason = can_comment_on_post(post, request.user)
        if not allowed:
            return Response({'error': reason}, status=status.HTTP_403_FORBIDDEN)

        serializer = CommentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        parent = None
        parent_id = request.data.get('parent_id') or request.data.get('parent')
        if parent_id:
            parent = get_object_or_404(
                Comment.objects.filter(
                    post=post,
                    moderation_status=Comment.STATUS_PUBLISHED,
                    parent__isnull=True,
                ),
                pk=parent_id,
            )
        comment = serializer.save(post=post, author=request.user, parent=parent)
        already_notified = set()
        if not parent or parent.author_id != post.created_by_id:
            if create_comment_notification(post, request.user, comment):
                already_notified.add(post.created_by_id)
        if parent:
            if create_reply_notification(parent, comment, request.user):
                already_notified.add(parent.author_id)
        sync_mention_notifications(
            comment.text,
            request.user,
            post,
            comment=comment,
            exclude_recipient_ids=already_notified,
        )
        return Response(
            CommentSerializer(comment, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class CommentViewSet(mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrModerator]
    parser_classes = [JSONParser]

    def get_queryset(self):
        posts = visible_posts_for(
            Post.objects.filter(moderation_status=Post.STATUS_PUBLISHED),
            self.request.user,
        )
        queryset = Comment.objects.filter(post__in=posts).select_related(
            'post', 'post__created_by', 'author', 'parent__author',
        )
        if self.action in ('react', 'hide'):
            queryset = queryset.filter(moderation_status=Comment.STATUS_PUBLISHED)
        return queryset

    def get_throttles(self):
        if self.action == 'react':
            return [CommunityActionThrottle()]
        return []

    def get_permissions(self):
        if self.action in ('react', 'hide'):
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsOwnerOrModerator()]

    def check_object_permissions(self, request, obj):
        if self.action == 'destroy' and obj.post.created_by_id == request.user.id:
            return
        super().check_object_permissions(request, obj)

    def perform_update(self, serializer):
        comment = serializer.save()
        sync_mention_notifications(comment.text, self.request.user, comment.post, comment=comment)

    def perform_destroy(self, instance):
        instance.delete()

    @action(detail=True, methods=['post'])
    def hide(self, request, pk=None):
        comment = self.get_object()
        if comment.post.created_by_id != request.user.id and not is_community_moderator(request.user):
            return Response({'error': 'Solo el autor de la publicación puede ocultar este comentario.'}, status=status.HTTP_403_FORBIDDEN)
        comment.moderation_status = Comment.STATUS_HIDDEN
        comment.save(update_fields=['moderation_status', 'updated_at'])
        return Response({'hidden': True, 'comment_id': comment.id})

    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        comment = self.get_object()
        reaction, created = CommentReaction.objects.get_or_create(
            comment=comment,
            user=request.user,
        )
        if created:
            create_comment_reaction_notification(comment, request.user)
        else:
            reaction.delete()
            remove_comment_reaction_notification(comment, request.user)
        return Response({
            'reacted': created,
            'reactions_count': comment.reactions.count(),
        })


class PetSocialProfileViewSet(viewsets.GenericViewSet):
    serializer_class = PetSocialProfileSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_throttles(self):
        return [CommunityActionThrottle()] if self.action == 'follow' else []

    def get_permissions(self):
        if self.action == 'retrieve':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_object(self):
        identifier = str(self.kwargs['pk'])
        if identifier.isdigit():
            pet = get_object_or_404(Pet.objects.select_related('owner'), pk=int(identifier))
            profile, _ = PetSocialProfile.objects.get_or_create(pet=pet)
        else:
            profile = get_object_or_404(
                PetSocialProfile.objects.select_related('pet__owner'),
                slug=identifier,
            )
            pet = profile.pet
        request = self.request
        if request.user.is_authenticated and users_blocked_between(pet.owner, request.user):
            from rest_framework.exceptions import NotFound
            raise NotFound('Este perfil no está disponible.')
        return profile

    def retrieve(self, request, pk=None):
        profile = self.get_object()
        return Response(self.get_serializer(profile, context={'request': request}).data)

    def partial_update(self, request, pk=None):
        profile = self.get_object()
        if profile.pet.owner_id != request.user.id and not is_community_moderator(request.user):
            return Response({'error': 'Solo el dueño puede editar este perfil.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(profile, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def follow(self, request, pk=None):
        profile = self.get_object()
        pet = profile.pet
        if pet.owner_id == request.user.id:
            return Response({'error': 'No necesitás seguir a tu propia mascota.'}, status=status.HTTP_400_BAD_REQUEST)
        existing = PetFollow.objects.filter(follower=request.user, pet=pet).first()
        if existing:
            existing.delete()
            remove_follow_notification(pet, request.user)
            return Response({'following': False, 'requested': False, 'followers_count': pet.social_followers.count()})
        if not profile.is_public:
            pending, created = PetFollowRequest.objects.get_or_create(follower=request.user, pet=pet)
            if created:
                create_follow_request_notification(pet, request.user)
            else:
                pending.delete()
                remove_follow_request_notification(pet, request.user)
            return Response({'following': False, 'requested': created, 'followers_count': pet.social_followers.count()})
        PetFollow.objects.create(follower=request.user, pet=pet)
        create_follow_notification(pet, request.user)
        return Response({'following': True, 'requested': False, 'followers_count': pet.social_followers.count()})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def community_mention_suggestions(request):
    query = str(request.query_params.get('q') or '').strip().lstrip('@')[:80]
    if len(query) < 2:
        return Response([])
    blocked = blocked_user_ids(request.user)
    users = get_user_model().objects.filter(
        Q(username__istartswith=query)
        | Q(first_name__icontains=query)
        | Q(last_name__icontains=query),
        is_active=True,
        is_approved=True,
    ).exclude(pk=request.user.pk).exclude(pk__in=blocked).select_related(
        'clinic_profile', 'business_profile', 'shelter_profile',
    ).order_by('username')[:8]
    results = []
    for user in users:
        identity = primary_identity_for_user(user, request=request)
        results.append({
            'username': user.username,
            'display_name': identity.get('name') if identity else (user.get_full_name().strip() or user.username),
            'avatar': identity.get('photo') if identity else absolute_file_url(request, user.avatar),
            'profile_url': identity.get('profile_url') if identity else '',
            'type': identity.get('type') if identity else 'user',
        })
    return Response(results)


class CommunityNotificationPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 50


class CommunityNotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = CommunityNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CommunityNotificationPagination

    def get_queryset(self):
        queryset = CommunityNotification.objects.filter(
            recipient=self.request.user
        ).select_related(
            'actor', 'actor__clinic_profile', 'actor__business_profile', 'actor__shelter_profile',
            'pet__social_profile', 'clinic', 'business', 'shelter',
            'post__pet', 'post__clinic', 'post__business', 'post__shelter',
            'post__related_lost_pet', 'comment',
        )
        unread = self.request.query_params.get('unread')
        if unread in ('1', 'true', 'True'):
            queryset = queryset.filter(is_read=False)
        return queryset.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        unread = CommunityNotification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).count()
        return Response({'unread': unread})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        now = timezone.now()
        updated = CommunityNotification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).update(is_read=True, read_at=now, updated_at=now)
        return Response({'marked': updated})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=['is_read', 'read_at', 'updated_at'])
        return Response(self.get_serializer(notification).data)


class PushSubscriptionViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        if self.action in ('subscribe', 'unsubscribe', 'test'):
            return [CommunityActionThrottle()]
        return []

    def get_permissions(self):
        if self.action == 'config':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def config(self, request):
        return Response({
            'enabled': push_is_configured(),
            'public_key': settings.VAPID_PUBLIC_KEY if push_is_configured() else '',
        })

    @action(detail=False, methods=['get'])
    def status(self, request):
        endpoint = (request.query_params.get('endpoint') or '').strip()
        if not endpoint:
            return Response({'active': False})
        subscription = PushSubscription.objects.filter(
            user=request.user,
            endpoint=endpoint,
            is_active=True,
        ).first()
        return Response({
            'active': bool(subscription),
            'subscription': (
                PushSubscriptionSerializer(subscription).data if subscription else None
            ),
        })

    @action(detail=False, methods=['post'])
    def subscribe(self, request):
        serializer = PushSubscriptionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        keys = data['keys']

        subscription, _ = PushSubscription.objects.update_or_create(
            endpoint=data['endpoint'],
            defaults={
                'user': request.user,
                'p256dh': keys['p256dh'],
                'auth': keys['auth'],
                'device_name': data.get('device_name', ''),
                'user_agent': data.get('user_agent', '') or request.META.get('HTTP_USER_AGENT', '')[:500],
                'is_active': True,
                'failure_count': 0,
                'last_failure_at': None,
            },
        )

        stale_ids = list(
            PushSubscription.objects.filter(
                user=request.user,
                is_active=True,
            ).exclude(pk=subscription.pk).order_by('-updated_at').values_list('id', flat=True)[
                MAX_ACTIVE_SUBSCRIPTIONS - 1:
            ]
        )
        if stale_ids:
            PushSubscription.objects.filter(id__in=stale_ids).update(is_active=False)

        return Response(
            PushSubscriptionSerializer(subscription).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'])
    def unsubscribe(self, request):
        endpoint = str(request.data.get('endpoint') or '').strip()
        if not endpoint:
            return Response(
                {'error': 'Falta la suscripción del dispositivo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        updated = PushSubscription.objects.filter(
            user=request.user,
            endpoint=endpoint,
        ).update(is_active=False)
        return Response({'unsubscribed': bool(updated)})

    @action(detail=False, methods=['post'])
    def test(self, request):
        if not push_is_configured():
            return Response(
                {'error': 'Las notificaciones push todavía no están configuradas en el servidor.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        endpoint = str(request.data.get('endpoint') or '').strip()
        subscription = PushSubscription.objects.filter(
            user=request.user,
            endpoint=endpoint,
            is_active=True,
        ).first()
        if not subscription:
            return Response(
                {'error': 'Este dispositivo no está suscripto.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        result = send_test_push(subscription)
        if not result.get('sent'):
            return Response(
                {'error': 'No pudimos enviar la prueba. Volvé a activar las notificaciones.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({'sent': True})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def community_profile_follow(request, profile_type, identifier):
    try:
        target = resolve_profile(profile_type, identifier)
    except ValueError:
        return Response({'error': 'Tipo de perfil inválido.'}, status=status.HTTP_400_BAD_REQUEST)

    if getattr(target, 'owner_id', None) == request.user.id:
        return Response({'error': 'No necesitás seguir tu propio perfil.'}, status=status.HTTP_400_BAD_REQUEST)
    if users_blocked_between(target.owner, request.user):
        return Response({'error': 'Este perfil no está disponible.'}, status=status.HTTP_404_NOT_FOUND)

    filters = {'follower': request.user, **target_kwargs(profile_type, target)}
    existing = PetFollow.objects.filter(**filters).first()
    if existing:
        existing.delete()
        remove_follow_notification(target, request.user)
        return Response({
            'following': False,
            'requested': False,
            'followers_count': follow_queryset_for_target(profile_type, target).count(),
        })

    if profile_type == 'pet':
        profile, _ = PetSocialProfile.objects.get_or_create(pet=target)
        if not profile.is_public:
            pending, created = PetFollowRequest.objects.get_or_create(follower=request.user, pet=target)
            if created:
                create_follow_request_notification(target, request.user)
            else:
                pending.delete()
                remove_follow_request_notification(target, request.user)
            return Response({
                'following': False,
                'requested': created,
                'followers_count': follow_queryset_for_target(profile_type, target).count(),
            })

    PetFollow.objects.create(**filters)
    create_follow_notification(target, request.user)
    return Response({
        'following': True,
        'requested': False,
        'followers_count': follow_queryset_for_target(profile_type, target).count(),
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def community_profile_connections(request, profile_type, identifier):
    try:
        target = resolve_profile(profile_type, identifier)
    except ValueError:
        return Response({'error': 'Tipo de perfil inválido.'}, status=status.HTTP_400_BAD_REQUEST)

    if profile_type == 'pet':
        profile, _ = PetSocialProfile.objects.get_or_create(pet=target)
        if not can_access_pet_profile(profile, request.user):
            return Response({'error': 'Este perfil es privado.'}, status=status.HTTP_403_FORBIDDEN)
    elif not is_target_public(profile_type, target, request.user):
        return Response({'error': 'Este perfil no está disponible.'}, status=status.HTTP_404_NOT_FOUND)

    settings = privacy_for(target.owner)
    is_owner = bool(request.user.is_authenticated and request.user.id == target.owner_id)

    kind = str(request.query_params.get('kind') or 'followers').lower()
    if kind not in {'followers', 'following'}:
        return Response({'error': 'Elegí followers o following.'}, status=status.HTTP_400_BAD_REQUEST)
    if settings and not is_owner:
        if kind == 'followers' and not settings.show_followers:
            return Response({'error': 'La lista de seguidores es privada.'}, status=status.HTTP_403_FORBIDDEN)
        if kind == 'following' and not settings.show_following:
            return Response({'error': 'La lista de seguidos es privada.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = min(40, max(1, int(request.query_params.get('page_size', 20))))
    except (TypeError, ValueError):
        page, page_size = 1, 20

    blocked = blocked_user_ids(request.user)
    identities = []

    if kind == 'followers':
        rows = follow_queryset_for_target(profile_type, target).select_related(
            'follower', 'follower__clinic_profile', 'follower__business_profile',
            'follower__shelter_profile',
        ).exclude(follower_id__in=blocked)
        for row in rows:
            identity = primary_identity_for_user(row.follower, request=request)
            if identity:
                identities.append(identity)
    else:
        owner = target_owner(target)
        rows = PetFollow.objects.filter(follower=owner).select_related(
            'pet__owner', 'pet__social_profile', 'clinic__owner',
            'business__owner', 'shelter__owner',
        )
        for row in rows:
            if row.target_owner_id in blocked:
                continue
            identity = identity_for_follow(row, request=request)
            if identity:
                identities.append(identity)

    # Un mismo usuario sin mascota pública no debe repetirse en el listado.
    unique = []
    seen = set()
    for identity in identities:
        key = (identity.get('type'), identity.get('id'))
        if key in seen:
            continue
        seen.add(key)
        unique.append(identity)

    total = len(unique)
    start = (page - 1) * page_size
    end = start + page_size
    return Response({
        'count': total,
        'page': page,
        'page_size': page_size,
        'next': page + 1 if end < total else None,
        'previous': page - 1 if page > 1 else None,
        'results': unique[start:end],
    })


class CommunityPrivacyViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CommunityPrivacySettingsSerializer

    def list(self, request):
        settings_obj = privacy_for(request.user)
        pets = PetSocialProfile.objects.filter(pet__owner=request.user).select_related('pet')
        return Response({
            'settings': self.get_serializer(settings_obj).data,
            'pets': [
                {
                    'id': profile.pet_id,
                    'slug': profile.slug,
                    'name': profile.pet.name,
                    'photo': absolute_file_url(request, profile.pet.photo),
                    'is_public': profile.is_public,
                    'pending_requests': profile.pet.community_follow_requests.count(),
                }
                for profile in pets
            ],
        })

    @action(detail=False, methods=['patch'], url_path='settings')
    def update_settings(self, request):
        settings_obj = privacy_for(request.user)
        serializer = self.get_serializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        if 'birthday_visibility' in serializer.validated_data:
            Post.objects.filter(
                created_by=request.user,
                related_birthday__isnull=False,
            ).update(
                is_public=updated.birthday_visibility == CommunityPrivacySettings.BIRTHDAY_COMMUNITY,
            )
        return Response(serializer.data)

    @action(detail=False, methods=['patch'], url_path=r'pets/(?P<pet_id>[^/.]+)')
    def pet_settings(self, request, pet_id=None):
        profile = get_object_or_404(PetSocialProfile.objects.select_related('pet'), pet_id=pet_id, pet__owner=request.user)
        if 'is_public' not in request.data:
            return Response({'error': 'Falta indicar si el perfil será público o privado.'}, status=status.HTTP_400_BAD_REQUEST)
        profile.is_public = str(request.data.get('is_public')).lower() in {'1', 'true', 'yes', 'on'}
        profile.save(update_fields=['is_public', 'updated_at'])
        if profile.is_public:
            # Las solicitudes pendientes pasan a ser seguidores cuando el dueño hace público el perfil.
            pending = list(profile.pet.community_follow_requests.select_related('follower'))
            for row in pending:
                follow, created = PetFollow.objects.get_or_create(follower=row.follower, pet=profile.pet)
                remove_follow_request_notification(profile.pet, row.follower)
                if created:
                    create_follow_notification(profile.pet, row.follower)
            profile.pet.community_follow_requests.all().delete()
        return Response({'id': profile.pet_id, 'is_public': profile.is_public})


    @action(detail=False, methods=['get'])
    def followers(self, request):
        pet_id = request.query_params.get('pet_id')
        pet = get_object_or_404(Pet, pk=pet_id, owner=request.user)
        rows = PetFollow.objects.filter(pet=pet).select_related(
            'follower', 'follower__clinic_profile', 'follower__business_profile',
            'follower__shelter_profile',
        ).order_by('-created_at')
        return Response([
            {
                'follow_id': row.id,
                'follower_id': row.follower_id,
                'identity': primary_identity_for_user(row.follower, request=request),
                'created_at': row.created_at,
            }
            for row in rows
        ])

    @action(detail=False, methods=['post'], url_path='remove-follower')
    def remove_follower(self, request):
        pet_id = request.data.get('pet_id')
        follower_id = request.data.get('follower_id')
        pet = get_object_or_404(Pet, pk=pet_id, owner=request.user)
        deleted, _ = PetFollow.objects.filter(pet=pet, follower_id=follower_id).delete()
        remove_follow_notification(pet, get_object_or_404(get_user_model(), pk=follower_id))
        return Response({'removed': bool(deleted), 'followers_count': pet.social_followers.count()})


class PetFollowRequestViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PetFollowRequestSerializer

    def get_queryset(self):
        kind = str(self.request.query_params.get('kind') or 'received').lower()
        queryset = PetFollowRequest.objects.select_related('follower', 'pet', 'pet__owner', 'pet__social_profile')
        if kind == 'sent':
            return queryset.filter(follower=self.request.user)
        return queryset.filter(pet__owner=self.request.user)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        follow_request = get_object_or_404(self.get_queryset().filter(pet__owner=request.user), pk=pk)
        follow, created = PetFollow.objects.get_or_create(follower=follow_request.follower, pet=follow_request.pet)
        if created:
            create_follow_notification(follow_request.pet, follow_request.follower)
        remove_follow_request_notification(follow_request.pet, follow_request.follower)
        follow_request.delete()
        return Response({'accepted': True, 'followers_count': follow.pet.social_followers.count()})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        follow_request = get_object_or_404(self.get_queryset().filter(pet__owner=request.user), pk=pk)
        remove_follow_request_notification(follow_request.pet, follow_request.follower)
        follow_request.delete()
        return Response({'rejected': True})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        follow_request = get_object_or_404(PetFollowRequest, pk=pk, follower=request.user)
        remove_follow_request_notification(follow_request.pet, follow_request.follower)
        follow_request.delete()
        return Response({'cancelled': True})


class MutedUserViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MutedUserSerializer

    def get_queryset(self):
        return MutedUser.objects.filter(user=self.request.user).select_related('muted')

    @action(detail=False, methods=['post'])
    def toggle(self, request):
        user_id = request.data.get('user_id')
        if not user_id or str(user_id) == str(request.user.id):
            return Response({'error': 'Elegí otro usuario.'}, status=status.HTTP_400_BAD_REQUEST)
        User = get_user_model()
        muted_user = get_object_or_404(User, pk=user_id)
        if users_blocked_between(request.user, muted_user):
            return Response({'error': 'Ese usuario está bloqueado.'}, status=status.HTTP_400_BAD_REQUEST)
        row, created = MutedUser.objects.get_or_create(user=request.user, muted=muted_user)
        if created:
            CommunityNotification.objects.filter(recipient=request.user, actor=muted_user).delete()
        else:
            row.delete()
        return Response({'muted': created})


class HiddenPostViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = HiddenPostSerializer

    def get_queryset(self):
        return HiddenPost.objects.filter(user=self.request.user).select_related(
            'post__created_by', 'post__pet__owner', 'post__clinic__owner',
            'post__business__owner', 'post__shelter__owner',
        )

    @action(detail=False, methods=['post'])
    def hide(self, request):
        post_id = request.data.get('post_id')
        reason = request.data.get('reason', HiddenPost.REASON_HIDDEN)
        if reason not in dict(HiddenPost.REASON_CHOICES):
            return Response({'error': 'Motivo inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        post = get_object_or_404(
            visible_posts_for(Post.objects.filter(moderation_status=Post.STATUS_PUBLISHED), request.user),
            pk=post_id,
        )
        if post.created_by_id == request.user.id:
            return Response({'error': 'No necesitás ocultar tu propia publicación.'}, status=status.HTTP_400_BAD_REQUEST)
        row, _ = HiddenPost.objects.update_or_create(user=request.user, post=post, defaults={'reason': reason})
        return Response({'hidden': True, 'id': row.id, 'reason': row.reason})

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        row = get_object_or_404(self.get_queryset(), pk=pk)
        post_id = row.post_id
        row.delete()
        return Response({'restored': True, 'post_id': post_id})


class ReportViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        return [CommunityActionThrottle()] if self.action in ('create', 'moderate') else []

    def get_queryset(self):
        if is_community_moderator(self.request.user):
            queryset = Report.objects.select_related(
                'reporter', 'post', 'comment', 'reported_user', 'reviewed_by'
            )
            status_filter = self.request.query_params.get('status')
            if status_filter in dict(Report.STATUS_CHOICES):
                queryset = queryset.filter(status=status_filter)
            return queryset
        return Report.objects.filter(reporter=self.request.user)

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)

    @action(detail=True, methods=['post'])
    def moderate(self, request, pk=None):
        if not is_community_moderator(request.user):
            return Response({'error': 'Acceso denegado.'}, status=status.HTTP_403_FORBIDDEN)
        report = self.get_object()
        decision = request.data.get('decision')
        notes = request.data.get('notes', '')
        if decision not in ('dismiss', 'hide', 'remove', 'review'):
            return Response({'error': 'Decisión inválida.'}, status=status.HTTP_400_BAD_REQUEST)
        if decision in ('hide', 'remove'):
            target_status = Post.STATUS_HIDDEN if decision == 'hide' else Post.STATUS_REMOVED
            if report.post_id:
                report.post.moderation_status = target_status
                report.post.save(update_fields=['moderation_status', 'updated_at'])
            elif report.comment_id:
                report.comment.moderation_status = target_status
                report.comment.save(update_fields=['moderation_status', 'updated_at'])
        report.status = {
            'dismiss': Report.STATUS_DISMISSED,
            'review': Report.STATUS_REVIEWED,
            'hide': Report.STATUS_ACTIONED,
            'remove': Report.STATUS_ACTIONED,
        }[decision]
        report.moderator_notes = notes
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save(update_fields=['status', 'moderator_notes', 'reviewed_by', 'reviewed_at'])
        return Response(self.get_serializer(report).data)


class BlockedUserViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = BlockedUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        return [CommunityActionThrottle()] if self.action == 'toggle' else []

    def get_queryset(self):
        return BlockedUser.objects.filter(blocker=self.request.user).select_related('blocked')

    @action(detail=False, methods=['post'])
    def toggle(self, request):
        blocked_id = request.data.get('user_id')
        if not blocked_id:
            return Response({'error': 'Falta el usuario.'}, status=status.HTTP_400_BAD_REQUEST)
        if str(blocked_id) == str(request.user.id):
            return Response({'error': 'No podés bloquearte a vos mismo.'}, status=status.HTTP_400_BAD_REQUEST)
        from users.models import User
        if not User.objects.filter(pk=blocked_id).exists():
            return Response({'error': 'Usuario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        block, created = BlockedUser.objects.get_or_create(blocker=request.user, blocked_id=blocked_id)
        if created:
            CommunityNotification.objects.filter(
                Q(recipient=request.user, actor_id=blocked_id)
                | Q(recipient_id=blocked_id, actor=request.user)
            ).delete()
            MutedUser.objects.filter(Q(user=request.user, muted_id=blocked_id) | Q(user_id=blocked_id, muted=request.user)).delete()
            PetFollow.objects.filter(
                Q(follower=request.user, pet__owner_id=blocked_id)
                | Q(follower=request.user, clinic__owner_id=blocked_id)
                | Q(follower=request.user, business__owner_id=blocked_id)
                | Q(follower=request.user, shelter__owner_id=blocked_id)
                | Q(follower_id=blocked_id, pet__owner=request.user)
                | Q(follower_id=blocked_id, clinic__owner=request.user)
                | Q(follower_id=blocked_id, business__owner=request.user)
                | Q(follower_id=blocked_id, shelter__owner=request.user)
            ).delete()
            PetFollowRequest.objects.filter(
                Q(follower=request.user, pet__owner_id=blocked_id)
                | Q(follower_id=blocked_id, pet__owner=request.user)
            ).delete()
        else:
            block.delete()
        return Response({'blocked': created})


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def community_discover(request):
    user = request.user
    blocked_ids = list(blocked_user_ids(user)) if user.is_authenticated else []

    suggested_pets = Pet.objects.filter(
        social_profile__is_public=True,
    ).exclude(owner_id__in=blocked_ids).select_related('owner', 'social_profile').annotate(
        followers_total=Count('social_followers', distinct=True),
        posts_total=Count('community_posts', filter=Q(community_posts__moderation_status=Post.STATUS_PUBLISHED), distinct=True),
    ).order_by('-followers_total', '-posts_total', '-created_at')
    if user.is_authenticated:
        suggested_pets = suggested_pets.exclude(owner=user)
    suggested_pets = suggested_pets[:6]

    clinics = Clinic.objects.filter(is_active=True).select_related('owner').annotate(
        posts_total=Count('community_posts', filter=Q(community_posts__moderation_status=Post.STATUS_PUBLISHED), distinct=True)
    ).order_by('-posts_total', '-created_at')[:5]

    businesses = BusinessProfile.objects.filter(is_active=True, owner__is_approved=True).exclude(owner_id__in=blocked_ids).select_related('owner').annotate(
        posts_total=Count('community_posts', filter=Q(community_posts__moderation_status=Post.STATUS_PUBLISHED), distinct=True)
    ).order_by('-is_verified', '-posts_total', '-created_at')[:5]

    shelters = ShelterProfile.objects.filter(is_active=True, owner__is_approved=True).exclude(owner_id__in=blocked_ids).select_related('owner').annotate(
        posts_total=Count('community_posts', filter=Q(community_posts__moderation_status=Post.STATUS_PUBLISHED), distinct=True)
    ).order_by('-is_verified', '-posts_total', '-created_at')[:5]

    lost = LostPet.objects.filter(expires_at__gt=timezone.now()).order_by('-created_at')[:5]
    birthdays = BirthdayCelebration.objects.filter(
        birthday_date__gte=timezone.localdate() - timedelta(days=2),
        birthday_date__lte=timezone.localdate() + timedelta(days=1),
        pet__social_profile__is_public=True,
        pet__owner__community_privacy__birthday_visibility=CommunityPrivacySettings.BIRTHDAY_COMMUNITY,
    ).select_related('pet__owner').order_by('-birthday_date')[:5]

    return Response({
        'suggested_pets': [
            {
                'id': pet.id,
                'name': pet.name,
                'species_display': pet.get_species_display(),
                'breed': pet.breed,
                'photo': absolute_file_url(request, pet.photo),
                'locality': pet.owner.locality,
                'province': pet.owner.province,
                'followers_count': pet.followers_total,
                'following': bool(user.is_authenticated and PetFollow.objects.filter(follower=user, pet=pet).exists()),
            }
            for pet in suggested_pets
        ],
        'clinics': [
            {
                'id': clinic.id,
                'name': clinic.name,
                'slug': clinic.slug,
                'logo': absolute_file_url(request, clinic.logo),
                'locality': clinic.locality,
                'province': clinic.province,
                'is_24h': clinic.is_24h,
                'posts_count': clinic.posts_total,
            }
            for clinic in clinics
        ],
        'businesses': [
            {
                'id': item.id,
                'name': item.name,
                'slug': item.slug,
                'logo': absolute_file_url(request, item.logo),
                'locality': item.locality,
                'province': item.province,
                'type_display': item.get_business_type_display(),
                'is_verified': item.is_verified,
                'posts_count': item.posts_total,
            }
            for item in businesses
        ],
        'shelters': [
            {
                'id': item.id,
                'name': item.name,
                'slug': item.slug,
                'logo': absolute_file_url(request, item.logo),
                'locality': item.locality,
                'province': item.province,
                'type_display': item.get_shelter_type_display(),
                'capacity_status': item.capacity_status,
                'capacity_status_display': item.get_capacity_status_display(),
                'is_verified': item.is_verified,
                'posts_count': item.posts_total,
            }
            for item in shelters
        ],
        'lost_pets': [
            {
                'id': item.id,
                'pet_name': item.pet_name or 'Mascota',
                'report_type': item.report_type,
                'photo': absolute_file_url(request, item.photo),
                'locality': item.locality,
                'province': item.province,
                'created_at': item.created_at,
            }
            for item in lost
        ],
        'birthdays': [
            {
                'id': item.id,
                'pet_id': item.pet_id,
                'pet_name': item.pet.name,
                'age': item.age,
                'photo': absolute_file_url(request, item.pet.photo),
                'birthday_date': item.birthday_date,
            }
            for item in birthdays
        ],
    })
