from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from clinics.models import Clinic
from pets.models import Pet
from partners.models import BusinessProfile, ShelterProfile
from vetpaw.image_validation import validate_uploaded_image
from users.permissions import is_community_moderator

from .models import (
    BlockedUser, Comment, CommentReaction, CommunityNotification, CommunityPrivacySettings,
    HiddenPost, MutedUser, PetFollow, PetFollowRequest, PetSocialProfile, Post,
    PushSubscription, Reaction, Report, SavedPost,
)
from .privacy import can_access_pet_profile, follow_request_pending, privacy_for


def absolute_file_url(request, field):
    if not field:
        return None
    try:
        url = field.url
    except (ValueError, AttributeError):
        return None
    if request and url.startswith('/'):
        return request.build_absolute_uri(url)
    return url


class CommunityUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    display_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    locality = serializers.CharField(read_only=True)
    province = serializers.CharField(read_only=True)

    def get_display_name(self, obj):
        return obj.get_full_name().strip() or obj.username

    def get_avatar(self, obj):
        return absolute_file_url(self.context.get('request'), obj.avatar)


class CommentReplySerializer(serializers.ModelSerializer):
    author = CommunityUserSerializer(read_only=True)
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    is_edited = serializers.SerializerMethodField()
    reactions_count = serializers.SerializerMethodField()
    reacted_by_me = serializers.SerializerMethodField()
    can_hide = serializers.SerializerMethodField()
    is_professional_answer = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id', 'post', 'author', 'parent', 'text', 'created_at', 'updated_at',
            'is_edited', 'can_edit', 'can_delete', 'can_hide', 'is_professional_answer', 'reactions_count', 'reacted_by_me',
        ]
        read_only_fields = [
            'id', 'post', 'author', 'parent', 'created_at', 'updated_at', 'is_edited',
            'can_edit', 'can_delete', 'can_hide', 'is_professional_answer', 'reactions_count', 'reacted_by_me',
        ]

    def _can_manage(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.author_id == request.user.id or is_community_moderator(request.user)

    def get_can_edit(self, obj):
        return self._can_manage(obj)

    def get_can_delete(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return self._can_manage(obj) or obj.post.created_by_id == request.user.id

    def get_can_hide(self, obj):
        request = self.context.get('request')
        return bool(
            request and request.user.is_authenticated
            and (obj.post.created_by_id == request.user.id or is_community_moderator(request.user))
        )

    def get_is_professional_answer(self, obj):
        return bool(
            obj.post_id
            and obj.post.clinic_id
            and obj.post.clinic.owner_id == obj.author_id
            and obj.author.is_approved
        )

    def get_is_edited(self, obj):
        return bool(obj.updated_at and obj.created_at and obj.updated_at > obj.created_at + timedelta(seconds=1))

    def get_reactions_count(self, obj):
        return getattr(obj, 'reactions_total', None) if getattr(obj, 'reactions_total', None) is not None else obj.reactions.count()

    def get_reacted_by_me(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        reacted_ids = self.context.get('reacted_comment_ids')
        if reacted_ids is not None:
            return obj.id in reacted_ids
        return CommentReaction.objects.filter(comment=obj, user=request.user).exists()

    def validate_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Escribí un comentario.')
        return value


class CommentSerializer(CommentReplySerializer):
    replies = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()

    class Meta(CommentReplySerializer.Meta):
        fields = CommentReplySerializer.Meta.fields + ['replies_count', 'replies']
        read_only_fields = CommentReplySerializer.Meta.read_only_fields + ['replies_count', 'replies']

    def get_replies(self, obj):
        rows = getattr(obj, '_visible_replies', None)
        if rows is None:
            rows = obj.replies.filter(moderation_status=Comment.STATUS_PUBLISHED).select_related('author')
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                blocked = BlockedUser.objects.filter(blocker=request.user).values_list('blocked_id', flat=True)
                blockers = BlockedUser.objects.filter(blocked=request.user).values_list('blocker_id', flat=True)
                rows = rows.exclude(author_id__in=list(blocked) + list(blockers))
        return CommentReplySerializer(rows, many=True, context=self.context).data

    def get_replies_count(self, obj):
        rows = getattr(obj, '_visible_replies', None)
        if rows is not None:
            return len(rows)
        return obj.replies.filter(moderation_status=Comment.STATUS_PUBLISHED).count()


class PostSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    reactions_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    comments_preview = serializers.SerializerMethodField()
    reacted_by_me = serializers.SerializerMethodField()
    saved_by_me = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    is_edited = serializers.SerializerMethodField()
    following_actor = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    lost_pet = serializers.SerializerMethodField()
    birthday = serializers.SerializerMethodField()
    comments_enabled = serializers.SerializerMethodField()
    can_manage_comments = serializers.SerializerMethodField()
    commerce_link = serializers.SerializerMethodField()
    clinic_content = serializers.SerializerMethodField()
    clinic_campaign_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Post
        fields = [
            'id', 'post_type', 'clinic_content_type', 'clinic_campaign_id', 'clinic_content', 'text', 'image', 'image_url', 'shares_count', 'province', 'locality',
            'comment_permission', 'comments_enabled', 'can_manage_comments',
            'actor', 'reactions_count', 'comments_count', 'comments_preview',
            'reacted_by_me', 'saved_by_me', 'can_edit', 'is_edited', 'following_actor', 'can_delete',
            'lost_pet', 'birthday', 'commerce_link', 'created_at', 'updated_at',
        ]
        extra_kwargs = {'image': {'write_only': True, 'required': False, 'allow_null': True}}
        read_only_fields = [
            'id', 'post_type', 'actor', 'image_url', 'reactions_count', 'comments_count',
            'comments_preview', 'reacted_by_me', 'saved_by_me', 'can_edit', 'is_edited', 'following_actor',
            'can_delete', 'lost_pet', 'birthday', 'commerce_link', 'clinic_content', 'comments_enabled', 'can_manage_comments',
            'shares_count', 'province', 'locality', 'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError('Necesitás iniciar sesión para publicar.')
        text_value = attrs.get('text', self.instance.text if self.instance else '')
        text = (text_value or '').strip()
        image = attrs.get('image', self.instance.image if self.instance else None)
        if not text and not image:
            raise serializers.ValidationError('Agregá un texto o una foto.')
        uploaded_image = attrs.get('image')
        if uploaded_image:
            validate_uploaded_image(uploaded_image, max_mb=5, label='La foto')
        if 'text' in attrs or not self.instance:
            attrs['text'] = text
        return attrs

    def create(self, validated_data):
        request = self.context['request']
        clinic_campaign_id = validated_data.pop('clinic_campaign_id', None)
        user = request.user
        if not validated_data.get('comment_permission'):
            settings = privacy_for(user)
            validated_data['comment_permission'] = (
                settings.default_comment_permission if settings else Post.COMMENTS_EVERYONE
            )
        pet_id = request.data.get('pet')
        if user.role != 'clinic':
            validated_data.pop('clinic_content_type', None)

        if user.role == 'owner':
            if not pet_id:
                raise serializers.ValidationError({'pet': 'Elegí la mascota que va a publicar.'})
            try:
                pet = Pet.objects.get(pk=pet_id, owner=user)
            except Pet.DoesNotExist:
                raise serializers.ValidationError({'pet': 'La mascota seleccionada no te pertenece.'})
            PetSocialProfile.objects.get_or_create(pet=pet)
            return Post.objects.create(
                created_by=user,
                pet=pet,
                post_type=Post.TYPE_NORMAL,
                province=user.province,
                locality=user.locality,
                **validated_data,
            )
        if user.role == 'clinic':
            try:
                clinic = user.clinic_profile
            except Clinic.DoesNotExist:
                raise serializers.ValidationError('No tenés una veterinaria asociada.')
            clinic_content_type = validated_data.get('clinic_content_type') or Post.CLINIC_CONTENT_TIP
            if clinic_content_type not in dict(Post.CLINIC_CONTENT_CHOICES):
                raise serializers.ValidationError({'clinic_content_type': 'Elegí un tipo de publicación veterinaria válido.'})
            campaign = None
            if clinic_campaign_id:
                from clinics.models import ClinicCampaign
                try:
                    campaign = ClinicCampaign.objects.get(pk=clinic_campaign_id, clinic=clinic)
                except ClinicCampaign.DoesNotExist:
                    raise serializers.ValidationError({'clinic_campaign_id': 'La campaña no pertenece a tu veterinaria.'})
                clinic_content_type = Post.CLINIC_CONTENT_CAMPAIGN
                if hasattr(campaign, 'community_post'):
                    raise serializers.ValidationError({'clinic_campaign_id': 'Esta campaña ya está publicada en la comunidad.'})
            return Post.objects.create(
                created_by=user,
                clinic=clinic,
                related_clinic_campaign=campaign,
                post_type=Post.TYPE_CLINIC,
                clinic_content_type=clinic_content_type,
                province=clinic.province,
                locality=clinic.locality,
                **{key: value for key, value in validated_data.items() if key != 'clinic_content_type'},
            )
        if user.role == 'business':
            try:
                business = user.business_profile
            except BusinessProfile.DoesNotExist:
                raise serializers.ValidationError('No tenés un negocio asociado.')
            if not business.is_active:
                raise serializers.ValidationError('Tu negocio no está activo.')
            return Post.objects.create(
                created_by=user,
                business=business,
                post_type=Post.TYPE_BUSINESS,
                province=business.province,
                locality=business.locality,
                **validated_data,
            )
        if user.role == 'shelter':
            try:
                shelter = user.shelter_profile
            except ShelterProfile.DoesNotExist:
                raise serializers.ValidationError('No tenés un refugio asociado.')
            if not shelter.is_active:
                raise serializers.ValidationError('Tu refugio no está activo.')
            return Post.objects.create(
                created_by=user,
                shelter=shelter,
                post_type=Post.TYPE_SHELTER,
                province=shelter.province,
                locality=shelter.locality,
                **validated_data,
            )
        raise serializers.ValidationError('Tipo de cuenta no habilitado para publicar.')

    def get_can_edit(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.created_by_id == request.user.id or is_community_moderator(request.user)

    def get_is_edited(self, obj):
        return bool(obj.updated_at and obj.created_at and obj.updated_at > obj.created_at + timedelta(seconds=1))

    def get_actor(self, obj):
        from .social_profiles import identity_for_target
        request = self.context.get('request')
        if obj.pet_id:
            return identity_for_target('pet', obj.pet, request=request)
        if obj.clinic_id:
            return identity_for_target('clinic', obj.clinic, request=request)
        if obj.business_id:
            return identity_for_target('business', obj.business, request=request)
        if obj.shelter_id:
            return identity_for_target('shelter', obj.shelter, request=request)
        if obj.related_lost_pet_id:
            lost = obj.related_lost_pet
            return {
                'type': 'lost',
                'id': lost.id,
                'identifier': str(lost.id),
                'name': lost.pet_name or 'Mascota perdida/encontrada',
                'subtitle': ' · '.join(filter(None, [lost.locality, lost.province])),
                'photo': absolute_file_url(request, lost.photo),
                'profile_url': '/mascotas-perdidas',
                'verified': False,
                'owner_user_id': lost.owner_id,
            }
        return {'type': 'system', 'name': 'VetPaw', 'subtitle': 'Comunidad', 'verified': True}

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image:
            return absolute_file_url(request, obj.image)
        if obj.related_lost_pet_id:
            return absolute_file_url(request, obj.related_lost_pet.photo)
        if obj.related_clinic_campaign_id and obj.related_clinic_campaign.image:
            return absolute_file_url(request, obj.related_clinic_campaign.image)
        if obj.pet_id and obj.post_type == Post.TYPE_BIRTHDAY:
            return absolute_file_url(request, obj.pet.photo)
        return None

    def get_clinic_content(self, obj):
        if not obj.clinic_id:
            return None
        content_type = obj.clinic_content_type or Post.CLINIC_CONTENT_TIP
        labels = dict(Post.CLINIC_CONTENT_CHOICES)
        payload = {
            'type': content_type,
            'label': labels.get(content_type, 'Publicación veterinaria'),
            'verified': bool(obj.clinic.owner_id and obj.clinic.owner.is_professionally_verified and obj.clinic.is_active),
            'clinic_id': obj.clinic_id,
            'clinic_slug': obj.clinic.slug,
            # La Comunidad es informativa. Los turnos se solicitan únicamente
            # desde la sección veterinaria de VetPaw y requieren un plan vigente.
            'can_request_appointment': False,
            'campaign': None,
        }
        if obj.related_clinic_campaign_id:
            from clinics.serializers import ClinicCampaignSerializer
            payload['campaign'] = ClinicCampaignSerializer(
                obj.related_clinic_campaign,
                context=self.context,
            ).data
        return payload

    def get_reactions_count(self, obj):
        return getattr(obj, 'reactions_total', None) if hasattr(obj, 'reactions_total') else obj.reactions.count()

    def get_comments_count(self, obj):
        return getattr(obj, 'comments_total', None) if hasattr(obj, 'comments_total') else obj.comments.filter(moderation_status=Comment.STATUS_PUBLISHED).count()

    def get_comments_preview(self, obj):
        queryset = obj.comments.filter(moderation_status=Comment.STATUS_PUBLISHED, parent__isnull=True).select_related('author')
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            blocked_ids = BlockedUser.objects.filter(blocker=request.user).values_list('blocked_id', flat=True)
            blocker_ids = BlockedUser.objects.filter(blocked=request.user).values_list('blocker_id', flat=True)
            queryset = queryset.exclude(author_id__in=list(blocked_ids) + list(blocker_ids))
        comments = list(queryset.order_by('-created_at')[:3])
        comments.reverse()
        return CommentSerializer(comments, many=True, context=self.context).data

    def _viewer(self):
        request = self.context.get('request')
        return request.user if request and request.user.is_authenticated else None

    def get_reacted_by_me(self, obj):
        user = self._viewer()
        return bool(user and obj.reactions.filter(user=user).exists())

    def get_saved_by_me(self, obj):
        user = self._viewer()
        return bool(user and obj.saved_by.filter(user=user).exists())

    def get_following_actor(self, obj):
        user = self._viewer()
        if not user:
            return False
        filters = {'follower': user}
        if obj.pet_id:
            filters['pet'] = obj.pet
        elif obj.clinic_id:
            filters['clinic'] = obj.clinic
        elif obj.business_id:
            filters['business'] = obj.business
        elif obj.shelter_id:
            filters['shelter'] = obj.shelter
        else:
            return False
        return PetFollow.objects.filter(**filters).exists()

    def get_can_delete(self, obj):
        user = self._viewer()
        return bool(user and (obj.created_by_id == user.id or is_community_moderator(user)))

    def get_comments_enabled(self, obj):
        return obj.comment_permission != Post.COMMENTS_NONE

    def get_can_manage_comments(self, obj):
        return self.get_can_edit(obj)

    def get_commerce_link(self, obj):
        try:
            item = obj.catalog_item
        except Exception:
            item = None
        if item:
            return {
                'type': 'catalog_item',
                'id': item.id,
                'title': item.title,
                'url': f'/negocios/{item.business.slug}/catalogo/{item.id}',
                'action': 'Ver producto o servicio',
            }
        try:
            promotion = obj.commerce_promotion
        except Exception:
            promotion = None
        if promotion:
            return {
                'type': 'promotion',
                'id': promotion.id,
                'title': promotion.title,
                'url': f'/negocios/{promotion.business.slug}',
                'action': 'Ver promoción',
            }
        return None

    def get_lost_pet(self, obj):
        if not obj.related_lost_pet_id:
            return None
        lost = obj.related_lost_pet
        return {
            'id': lost.id,
            'report_type': lost.report_type,
            'report_type_display': lost.get_report_type_display(),
            'pet_name': lost.pet_name,
            'species': lost.species,
            'species_display': lost.get_species_display() if lost.species else '',
            'breed': lost.breed,
            'description': lost.description,
            'locality': lost.locality,
            'province': lost.province,
            'incident_date': lost.incident_date,
            'contact_type': lost.contact_type,
            'contact_value': lost.contact_value,
            'expires_at': lost.expires_at,
            'is_active': lost.expires_at > timezone.now(),
        }

    def get_birthday(self, obj):
        if not obj.related_birthday_id:
            return None
        birthday = obj.related_birthday
        return {
            'id': birthday.id,
            'age': birthday.age,
            'year': birthday.year,
            'birthday_date': birthday.birthday_date,
        }


class PetSocialProfileSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='pet.id', read_only=True)
    name = serializers.CharField(source='pet.name', read_only=True)
    species = serializers.CharField(source='pet.species', read_only=True)
    species_display = serializers.CharField(source='pet.get_species_display', read_only=True)
    breed = serializers.CharField(source='pet.breed', read_only=True)
    birth_date = serializers.DateField(source='pet.birth_date', read_only=True)
    age = serializers.SerializerMethodField()
    temperament = serializers.CharField(source='pet.temperament', read_only=True)
    temperament_display = serializers.CharField(source='pet.get_temperament_display', read_only=True)
    photo = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    locality = serializers.CharField(source='pet.owner.locality', read_only=True)
    province = serializers.CharField(source='pet.owner.province', read_only=True)
    owner_display_name = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    paws_count = serializers.SerializerMethodField()
    following = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    recent_posts = serializers.SerializerMethodField()
    gallery = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()
    access_granted = serializers.SerializerMethodField()
    follow_request_pending = serializers.SerializerMethodField()

    class Meta:
        model = PetSocialProfile
        fields = [
            'id', 'slug', 'profile_url', 'name', 'species', 'species_display', 'breed', 'birth_date', 'age',
            'temperament', 'temperament_display', 'photo', 'cover', 'cover_url',
            'bio', 'is_public', 'locality', 'province', 'owner_display_name',
            'followers_count', 'following_count', 'posts_count', 'paws_count',
            'following', 'is_owner', 'access_granted', 'follow_request_pending', 'recent_posts', 'gallery',
        ]
        extra_kwargs = {'cover': {'write_only': True, 'required': False, 'allow_null': True}}
        read_only_fields = [
            'id', 'slug', 'profile_url', 'name', 'species', 'species_display', 'breed', 'birth_date', 'age',
            'temperament', 'temperament_display', 'photo', 'cover_url', 'locality',
            'province', 'owner_display_name', 'followers_count', 'following_count',
            'posts_count', 'paws_count', 'following', 'is_owner', 'access_granted',
            'follow_request_pending', 'recent_posts', 'gallery',
        ]

    def _viewer(self):
        request = self.context.get('request')
        return request.user if request else None

    def _privacy(self, obj):
        return privacy_for(obj.pet.owner)

    def _has_access(self, obj):
        return can_access_pet_profile(obj, self._viewer())

    def get_access_granted(self, obj):
        return self._has_access(obj)

    def get_follow_request_pending(self, obj):
        return follow_request_pending(obj, self._viewer())

    def get_age(self, obj):
        birth_date = obj.pet.birth_date
        if not birth_date:
            return None
        today = timezone.localdate()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    def get_photo(self, obj):
        return absolute_file_url(self.context.get('request'), obj.pet.photo)

    def get_cover_url(self, obj):
        return absolute_file_url(self.context.get('request'), obj.cover)

    def get_owner_display_name(self, obj):
        owner = obj.pet.owner
        return owner.first_name or owner.username

    def get_followers_count(self, obj):
        settings = self._privacy(obj)
        viewer = self._viewer()
        if settings and not settings.show_followers and not (viewer and viewer.is_authenticated and viewer.id == obj.pet.owner_id):
            return None
        return obj.pet.social_followers.count()

    def get_following_count(self, obj):
        settings = self._privacy(obj)
        viewer = self._viewer()
        if settings and not settings.show_following and not (viewer and viewer.is_authenticated and viewer.id == obj.pet.owner_id):
            return None
        return PetFollow.objects.filter(follower=obj.pet.owner).count()

    def get_posts_count(self, obj):
        return obj.pet.community_posts.filter(moderation_status=Post.STATUS_PUBLISHED, is_public=True).count()

    def get_paws_count(self, obj):
        settings = self._privacy(obj)
        viewer = self._viewer()
        if settings and not settings.show_paws and not (viewer and viewer.is_authenticated and viewer.id == obj.pet.owner_id):
            return None
        from django.db.models import Count
        return obj.pet.community_posts.filter(
            moderation_status=Post.STATUS_PUBLISHED,
            is_public=True,
        ).aggregate(total=Count('reactions', distinct=True))['total'] or 0

    def get_profile_url(self, obj):
        return f'/mascotas/{obj.slug or obj.pet_id}'

    def get_following(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and PetFollow.objects.filter(follower=request.user, pet=obj.pet).exists())

    def get_is_owner(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and obj.pet.owner_id == request.user.id)

    def get_recent_posts(self, obj):
        settings = self._privacy(obj)
        if not self._has_access(obj) or (settings and not settings.show_activity and not self.get_is_owner(obj)):
            return []
        posts = obj.pet.community_posts.filter(moderation_status=Post.STATUS_PUBLISHED, is_public=True).select_related(
            'created_by', 'pet__owner', 'pet__social_profile', 'clinic__owner',
            'business__owner', 'shelter__owner', 'related_lost_pet', 'related_birthday'
        ).prefetch_related('comments__author')[:20]
        return PostSerializer(posts, many=True, context=self.context).data

    def get_gallery(self, obj):
        request = self.context.get('request')
        settings = self._privacy(obj)
        if not self._has_access(obj) or (settings and not settings.show_activity and not self.get_is_owner(obj)):
            return []
        posts = obj.pet.community_posts.filter(
            moderation_status=Post.STATUS_PUBLISHED,
            is_public=True,
        ).exclude(image='').exclude(image__isnull=True)[:24]
        return [
            {
                'post_id': post.id,
                'image_url': absolute_file_url(request, post.image),
                'text': post.text[:180],
                'created_at': post.created_at,
            }
            for post in posts
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        viewer = self._viewer()
        is_owner = bool(viewer and viewer.is_authenticated and viewer.id == instance.pet.owner_id)
        settings = self._privacy(instance)
        if not is_owner and settings:
            if not settings.show_location:
                data['locality'] = ''
                data['province'] = ''
            if not settings.show_birth_date:
                data['birth_date'] = None
            if not settings.show_age:
                data['age'] = None
        if not data.get('access_granted') and not is_owner:
            for key in ('breed', 'birth_date', 'age', 'temperament', 'temperament_display', 'locality', 'province', 'owner_display_name'):
                data[key] = None if key in ('birth_date', 'age') else ''
            data['recent_posts'] = []
            data['gallery'] = []
            data['posts_count'] = 0
            data['paws_count'] = None
        return data

    def validate_cover(self, value):
        return validate_uploaded_image(value, max_mb=5, label='La portada')


class ReportSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source='reporter.username', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    target_preview = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'id', 'reporter', 'reporter_name', 'post', 'comment', 'reported_user',
            'reason', 'reason_display', 'details', 'status', 'moderator_notes',
            'target_preview', 'created_at', 'reviewed_at',
        ]
        read_only_fields = ['id', 'reporter', 'reporter_name', 'status', 'moderator_notes', 'target_preview', 'created_at', 'reviewed_at']

    def validate(self, attrs):
        targets = sum(bool(attrs.get(key)) for key in ('post', 'comment', 'reported_user'))
        if targets != 1:
            raise serializers.ValidationError('Elegí una sola publicación, comentario o usuario para reportar.')
        request = self.context.get('request')
        if attrs.get('reported_user') == getattr(request, 'user', None):
            raise serializers.ValidationError('No podés reportarte a vos mismo.')
        return attrs

    def get_target_preview(self, obj):
        if obj.post_id:
            return {'type': 'post', 'id': obj.post_id, 'text': obj.post.text[:180]}
        if obj.comment_id:
            return {'type': 'comment', 'id': obj.comment_id, 'text': obj.comment.text[:180]}
        if obj.reported_user_id:
            return {'type': 'user', 'id': obj.reported_user_id, 'text': obj.reported_user.username}
        return None


class CommunityPrivacySettingsSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='user.role', read_only=True)

    class Meta:
        model = CommunityPrivacySettings
        fields = [
            'role', 'default_comment_permission', 'show_location', 'show_birth_date',
            'show_age', 'show_followers', 'show_following', 'show_paws',
            'show_activity', 'birthday_visibility', 'show_phone', 'show_whatsapp',
            'show_responsible_name', 'show_donation_info', 'allow_internal_messages',
            'allow_appointment_requests', 'social_notifications_enabled',
            'push_notifications_enabled', 'updated_at',
        ]
        read_only_fields = ['role', 'updated_at']


class PetFollowRequestSerializer(serializers.ModelSerializer):
    follower = CommunityUserSerializer(read_only=True)
    pet_id = serializers.IntegerField(source='pet.id', read_only=True)
    pet_name = serializers.CharField(source='pet.name', read_only=True)
    pet_slug = serializers.CharField(source='pet.social_profile.slug', read_only=True)
    pet_photo = serializers.SerializerMethodField()

    class Meta:
        model = PetFollowRequest
        fields = ['id', 'follower', 'pet_id', 'pet_name', 'pet_slug', 'pet_photo', 'created_at']
        read_only_fields = fields

    def get_pet_photo(self, obj):
        return absolute_file_url(self.context.get('request'), obj.pet.photo)


class MutedUserSerializer(serializers.ModelSerializer):
    muted = CommunityUserSerializer(read_only=True)

    class Meta:
        model = MutedUser
        fields = ['id', 'muted', 'created_at']
        read_only_fields = fields


class HiddenPostSerializer(serializers.ModelSerializer):
    post = PostSerializer(read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)

    class Meta:
        model = HiddenPost
        fields = ['id', 'post', 'reason', 'reason_display', 'created_at']
        read_only_fields = fields


class BlockedUserSerializer(serializers.ModelSerializer):
    blocked = CommunityUserSerializer(read_only=True)

    class Meta:
        model = BlockedUser
        fields = ['id', 'blocked', 'created_at']


class CommunityNotificationSerializer(serializers.ModelSerializer):
    actor = CommunityUserSerializer(read_only=True)
    message = serializers.SerializerMethodField()
    target_url = serializers.SerializerMethodField()
    target_type = serializers.SerializerMethodField()
    post_id = serializers.IntegerField(source='post.id', read_only=True)
    pet_id = serializers.IntegerField(source='pet.id', read_only=True)
    clinic_id = serializers.IntegerField(source='clinic.id', read_only=True)
    business_id = serializers.IntegerField(source='business.id', read_only=True)
    shelter_id = serializers.IntegerField(source='shelter.id', read_only=True)
    comment_id = serializers.IntegerField(source='comment.id', read_only=True)
    appointment_id = serializers.IntegerField(source='appointment.id', read_only=True)
    adoption_animal_id = serializers.IntegerField(source='adoption_animal.id', read_only=True)
    adoption_application_id = serializers.IntegerField(source='adoption_application.id', read_only=True)
    help_offer_id = serializers.IntegerField(source='help_offer.id', read_only=True)

    class Meta:
        model = CommunityNotification
        fields = [
            'id', 'notification_type', 'actor', 'message', 'extra_text',
            'is_read', 'read_at', 'created_at', 'target_url', 'target_type',
            'post_id', 'pet_id', 'clinic_id', 'business_id', 'shelter_id', 'comment_id', 'appointment_id',
            'adoption_animal_id', 'adoption_application_id', 'help_offer_id',
        ]
        read_only_fields = [
            'id', 'notification_type', 'actor', 'message', 'extra_text',
            'is_read', 'read_at', 'created_at', 'target_url', 'target_type',
            'post_id', 'pet_id', 'clinic_id', 'business_id', 'shelter_id', 'comment_id', 'appointment_id',
            'adoption_animal_id', 'adoption_application_id', 'help_offer_id',
        ]

    def _actor_name(self, obj):
        if obj.actor.role == 'clinic':
            clinic = getattr(obj.actor, 'clinic_profile', None)
            if clinic:
                return clinic.name
        if obj.actor.role == 'business':
            business = getattr(obj.actor, 'business_profile', None)
            if business:
                return business.name
        if obj.actor.role == 'shelter':
            shelter = getattr(obj.actor, 'shelter_profile', None)
            if shelter:
                return shelter.name
        return obj.actor.get_full_name().strip() or obj.actor.username

    def _post_subject(self, obj):
        if obj.post_id and obj.post.pet_id:
            return f'la publicación de {obj.post.pet.name}'
        if obj.post_id and obj.post.clinic_id:
            return 'tu publicación de la veterinaria'
        if obj.post_id and obj.post.business_id:
            return 'tu publicación del negocio'
        if obj.post_id and obj.post.shelter_id:
            return 'tu publicación del refugio'
        if obj.post_id and obj.post.related_lost_pet_id:
            return 'tu aviso de mascota perdida o encontrada'
        return 'tu publicación'

    def get_message(self, obj):
        from .push_utils import notification_message
        return notification_message(obj)

    def get_target_url(self, obj):
        from .push_utils import notification_target_url
        return notification_target_url(obj)

    def get_target_type(self, obj):
        if obj.notification_type == CommunityNotification.TYPE_FOLLOW_REQUEST:
            return 'follow_request'
        if obj.notification_type == CommunityNotification.TYPE_FOLLOW:
            return 'profile'
        if obj.notification_type in {
            CommunityNotification.TYPE_BUSINESS_INQUIRY,
            CommunityNotification.TYPE_BUSINESS_RESERVATION,
            CommunityNotification.TYPE_BUSINESS_RESERVATION_UPDATE,
            CommunityNotification.TYPE_CLINIC_APPOINTMENT,
            CommunityNotification.TYPE_CLINIC_APPOINTMENT_UPDATE,
        }:
            if obj.notification_type in {
                CommunityNotification.TYPE_CLINIC_APPOINTMENT,
                CommunityNotification.TYPE_CLINIC_APPOINTMENT_UPDATE,
            }:
                return 'clinic_appointment'
            return 'business'
        if obj.notification_type in {
            CommunityNotification.TYPE_ADOPTION_APPLICATION,
            CommunityNotification.TYPE_ADOPTION_HELP_OFFER,
            CommunityNotification.TYPE_ADOPTION_APPLICATION_UPDATE,
        }:
            return 'adoption'
        if obj.comment_id:
            return 'comment'
        if obj.post_id:
            return 'post'
        return 'community'


class PushSubscriptionInputSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=4000)
    keys = serializers.DictField()
    device_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    user_agent = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_keys(self, value):
        p256dh = str(value.get('p256dh') or '').strip()
        auth = str(value.get('auth') or '').strip()
        if not p256dh or not auth:
            raise serializers.ValidationError('La suscripción no incluye sus claves de seguridad.')
        if len(p256dh) > 1000 or len(auth) > 500:
            raise serializers.ValidationError('Las claves de la suscripción no son válidas.')
        return {'p256dh': p256dh, 'auth': auth}


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = [
            'id', 'device_name', 'is_active', 'last_success_at',
            'last_failure_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields
