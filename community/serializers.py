from django.utils import timezone
from rest_framework import serializers

from clinics.models import Clinic
from pets.models import Pet
from partners.models import BusinessProfile, ShelterProfile
from vetpaw.image_validation import validate_uploaded_image
from users.permissions import is_community_moderator

from .models import BlockedUser, Comment, CommunityNotification, PetFollow, PetSocialProfile, Post, PushSubscription, Reaction, Report, SavedPost


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


class CommentSerializer(serializers.ModelSerializer):
    author = CommunityUserSerializer(read_only=True)
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'post', 'author', 'text', 'created_at', 'updated_at', 'can_delete']
        read_only_fields = ['id', 'post', 'author', 'created_at', 'updated_at', 'can_delete']

    def get_can_delete(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.author_id == request.user.id or is_community_moderator(request.user)

    def validate_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Escribí un comentario.')
        return value


class PostSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    reactions_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    comments_preview = serializers.SerializerMethodField()
    reacted_by_me = serializers.SerializerMethodField()
    saved_by_me = serializers.SerializerMethodField()
    following_actor = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    lost_pet = serializers.SerializerMethodField()
    birthday = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'post_type', 'text', 'image', 'image_url', 'province', 'locality',
            'actor', 'reactions_count', 'comments_count', 'comments_preview',
            'reacted_by_me', 'saved_by_me', 'following_actor', 'can_delete',
            'lost_pet', 'birthday', 'created_at', 'updated_at',
        ]
        extra_kwargs = {'image': {'write_only': True, 'required': False, 'allow_null': True}}
        read_only_fields = [
            'id', 'post_type', 'actor', 'image_url', 'reactions_count', 'comments_count',
            'comments_preview', 'reacted_by_me', 'saved_by_me', 'following_actor',
            'can_delete', 'lost_pet', 'birthday', 'province', 'locality', 'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError('Necesitás iniciar sesión para publicar.')
        text = (attrs.get('text') or '').strip()
        image = attrs.get('image')
        if not text and not image:
            raise serializers.ValidationError('Agregá un texto o una foto.')
        if image:
            validate_uploaded_image(image, max_mb=5, label='La foto')
        attrs['text'] = text
        return attrs

    def create(self, validated_data):
        request = self.context['request']
        user = request.user
        pet_id = request.data.get('pet')
        if user.role == 'owner':
            if not pet_id:
                raise serializers.ValidationError({'pet': 'Elegí la mascota que va a publicar.'})
            try:
                pet = Pet.objects.get(pk=pet_id, owner=user)
            except Pet.DoesNotExist:
                raise serializers.ValidationError({'pet': 'La mascota seleccionada no te pertenece.'})
            profile, _ = PetSocialProfile.objects.get_or_create(pet=pet)
            if not profile.is_public:
                raise serializers.ValidationError({'pet': 'Activá el perfil público de esta mascota para publicar.'})
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
            return Post.objects.create(
                created_by=user,
                clinic=clinic,
                post_type=Post.TYPE_CLINIC,
                province=clinic.province,
                locality=clinic.locality,
                **validated_data,
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

    def get_actor(self, obj):
        request = self.context.get('request')
        if obj.pet_id:
            pet = obj.pet
            profile = getattr(pet, 'social_profile', None)
            return {
                'type': 'pet',
                'id': pet.id,
                'name': pet.name,
                'subtitle': ' · '.join(filter(None, [pet.get_species_display(), pet.breed])),
                'photo': absolute_file_url(request, pet.photo),
                'cover': absolute_file_url(request, profile.cover if profile else None),
                'profile_url': f'/mascotas/{pet.id}',
                'verified': False,
                'owner_user_id': pet.owner_id,
            }
        if obj.clinic_id:
            clinic = obj.clinic
            return {
                'type': 'clinic',
                'id': clinic.id,
                'name': clinic.name,
                'subtitle': ' · '.join(filter(None, [clinic.locality, clinic.province])),
                'photo': absolute_file_url(request, clinic.logo),
                'profile_url': f'/clinicas/{clinic.slug}',
                'verified': True,
                'owner_user_id': clinic.owner_id,
            }
        if obj.business_id:
            business = obj.business
            return {
                'type': 'business',
                'id': business.id,
                'name': business.name,
                'subtitle': ' · '.join(filter(None, [business.get_business_type_display(), business.locality])),
                'photo': absolute_file_url(request, business.logo),
                'profile_url': f'/negocios/{business.slug}',
                'verified': business.is_verified,
                'owner_user_id': business.owner_id,
            }
        if obj.shelter_id:
            shelter = obj.shelter
            return {
                'type': 'shelter',
                'id': shelter.id,
                'name': shelter.name,
                'subtitle': ' · '.join(filter(None, [shelter.get_shelter_type_display(), shelter.locality])),
                'photo': absolute_file_url(request, shelter.logo),
                'profile_url': f'/refugios/{shelter.slug}',
                'verified': shelter.is_verified,
                'owner_user_id': shelter.owner_id,
            }
        if obj.related_lost_pet_id:
            lost = obj.related_lost_pet
            return {
                'type': 'lost',
                'id': lost.id,
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
        if obj.pet_id and obj.post_type == Post.TYPE_BIRTHDAY:
            return absolute_file_url(request, obj.pet.photo)
        return None

    def get_reactions_count(self, obj):
        return getattr(obj, 'reactions_total', None) if hasattr(obj, 'reactions_total') else obj.reactions.count()

    def get_comments_count(self, obj):
        return getattr(obj, 'comments_total', None) if hasattr(obj, 'comments_total') else obj.comments.filter(moderation_status=Comment.STATUS_PUBLISHED).count()

    def get_comments_preview(self, obj):
        queryset = obj.comments.filter(moderation_status=Comment.STATUS_PUBLISHED).select_related('author')
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
        return bool(user and obj.pet_id and PetFollow.objects.filter(follower=user, pet=obj.pet).exists())

    def get_can_delete(self, obj):
        user = self._viewer()
        return bool(user and (obj.created_by_id == user.id or is_community_moderator(user)))

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
    temperament = serializers.CharField(source='pet.temperament', read_only=True)
    temperament_display = serializers.CharField(source='pet.get_temperament_display', read_only=True)
    photo = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()
    locality = serializers.CharField(source='pet.owner.locality', read_only=True)
    province = serializers.CharField(source='pet.owner.province', read_only=True)
    owner_display_name = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    posts_count = serializers.SerializerMethodField()
    following = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    recent_posts = serializers.SerializerMethodField()

    class Meta:
        model = PetSocialProfile
        fields = [
            'id', 'name', 'species', 'species_display', 'breed', 'birth_date',
            'temperament', 'temperament_display', 'photo', 'cover', 'cover_url',
            'bio', 'is_public', 'locality', 'province', 'owner_display_name',
            'followers_count', 'posts_count', 'following', 'is_owner', 'recent_posts',
        ]
        extra_kwargs = {'cover': {'write_only': True, 'required': False, 'allow_null': True}}
        read_only_fields = [
            'id', 'name', 'species', 'species_display', 'breed', 'birth_date',
            'temperament', 'temperament_display', 'photo', 'cover_url', 'locality',
            'province', 'owner_display_name', 'followers_count', 'posts_count',
            'following', 'is_owner', 'recent_posts',
        ]

    def get_photo(self, obj):
        return absolute_file_url(self.context.get('request'), obj.pet.photo)

    def get_cover_url(self, obj):
        return absolute_file_url(self.context.get('request'), obj.cover)

    def get_owner_display_name(self, obj):
        owner = obj.pet.owner
        return owner.first_name or owner.username

    def get_followers_count(self, obj):
        return obj.pet.social_followers.count()

    def get_posts_count(self, obj):
        return obj.pet.community_posts.filter(moderation_status=Post.STATUS_PUBLISHED, is_public=True).count()

    def get_following(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and PetFollow.objects.filter(follower=request.user, pet=obj.pet).exists())

    def get_is_owner(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and obj.pet.owner_id == request.user.id)

    def get_recent_posts(self, obj):
        posts = obj.pet.community_posts.filter(moderation_status=Post.STATUS_PUBLISHED, is_public=True).select_related(
            'pet__owner', 'pet__social_profile', 'clinic', 'business', 'shelter', 'related_lost_pet', 'related_birthday'
        )[:20]
        return PostSerializer(posts, many=True, context=self.context).data

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
    comment_id = serializers.IntegerField(source='comment.id', read_only=True)

    class Meta:
        model = CommunityNotification
        fields = [
            'id', 'notification_type', 'actor', 'message', 'extra_text',
            'is_read', 'read_at', 'created_at', 'target_url', 'target_type',
            'post_id', 'pet_id', 'comment_id',
        ]
        read_only_fields = [
            'id', 'notification_type', 'actor', 'message', 'extra_text',
            'is_read', 'read_at', 'created_at', 'target_url', 'target_type',
            'post_id', 'pet_id', 'comment_id',
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
        actor_name = self._actor_name(obj)
        if obj.notification_type == CommunityNotification.TYPE_REACTION:
            return f'{actor_name} dejó una patita en {self._post_subject(obj)}.'
        if obj.notification_type == CommunityNotification.TYPE_COMMENT:
            return f'{actor_name} comentó {self._post_subject(obj)}.'
        if obj.notification_type == CommunityNotification.TYPE_FOLLOW:
            pet_name = obj.pet.name if obj.pet_id else 'tu mascota'
            return f'{actor_name} comenzó a seguir a {pet_name}.'
        return 'Tenés nueva actividad en VetPaw.'

    def get_target_url(self, obj):
        if obj.notification_type == CommunityNotification.TYPE_FOLLOW and obj.pet_id:
            return f'/mascotas/{obj.pet_id}'
        if (
            obj.notification_type == CommunityNotification.TYPE_COMMENT
            and obj.post_id
            and obj.comment_id
        ):
            return f'/comunidad?publicacion={obj.post_id}&comentario={obj.comment_id}'
        if obj.post_id:
            return f'/comunidad?publicacion={obj.post_id}'
        return '/comunidad'

    def get_target_type(self, obj):
        if obj.notification_type == CommunityNotification.TYPE_FOLLOW:
            return 'pet'
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
