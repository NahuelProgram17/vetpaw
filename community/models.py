from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.text import slugify


class PetSocialProfile(models.Model):
    pet = models.OneToOneField(
        'pets.Pet',
        on_delete=models.CASCADE,
        related_name='social_profile',
    )
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    bio = models.CharField(max_length=500, blank=True)
    cover = models.ImageField(upload_to='community/pet-covers/', blank=True, null=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.pet.name) or f'mascota-{self.pet_id}'
            candidate = base
            index = 2
            while PetSocialProfile.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f'{base}-{index}'
                index += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Perfil social de {self.pet.name}'


class Post(models.Model):
    TYPE_NORMAL = 'normal'
    TYPE_BIRTHDAY = 'birthday'
    TYPE_LOST = 'lost'
    TYPE_CLINIC = 'clinic'
    TYPE_BUSINESS = 'business'
    TYPE_SHELTER = 'shelter'
    TYPE_ADOPTION = 'adoption'

    CLINIC_CONTENT_TIP = 'health_tip'
    CLINIC_CONTENT_CAMPAIGN = 'campaign'
    CLINIC_CONTENT_AVAILABILITY = 'availability'
    CLINIC_CONTENT_GUARD = 'guard'
    CLINIC_CONTENT_SERVICE = 'service'
    CLINIC_CONTENT_NOTICE = 'notice'
    CLINIC_CONTENT_CHOICES = [
        (CLINIC_CONTENT_TIP, 'Consejo veterinario'),
        (CLINIC_CONTENT_CAMPAIGN, 'Campaña o evento'),
        (CLINIC_CONTENT_NOTICE, 'Aviso importante'),
        (CLINIC_CONTENT_SERVICE, 'Servicio veterinario'),
    ]
    TYPE_CHOICES = [
        (TYPE_NORMAL, 'Publicación'),
        (TYPE_BIRTHDAY, 'Cumpleaños'),
        (TYPE_LOST, 'Mascota perdida/encontrada'),
        (TYPE_CLINIC, 'Veterinaria'),
        (TYPE_BUSINESS, 'Negocio de mascotas'),
        (TYPE_SHELTER, 'Refugio o rescatista'),
        (TYPE_ADOPTION, 'Adopción'),
    ]

    STATUS_PUBLISHED = 'published'
    STATUS_HIDDEN = 'hidden'
    STATUS_REMOVED = 'removed'
    STATUS_CHOICES = [
        (STATUS_PUBLISHED, 'Publicada'),
        (STATUS_HIDDEN, 'Oculta'),
        (STATUS_REMOVED, 'Eliminada por moderación'),
    ]

    COMMENTS_EVERYONE = 'everyone'
    COMMENTS_FOLLOWERS = 'followers'
    COMMENTS_NONE = 'none'
    COMMENT_PERMISSION_CHOICES = [
        (COMMENTS_EVERYONE, 'Todos pueden comentar'),
        (COMMENTS_FOLLOWERS, 'Solo seguidores'),
        (COMMENTS_NONE, 'Comentarios desactivados'),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='community_posts',
        null=True,
        blank=True,
    )
    pet = models.ForeignKey(
        'pets.Pet',
        on_delete=models.SET_NULL,
        related_name='community_posts',
        null=True,
        blank=True,
    )
    clinic = models.ForeignKey(
        'clinics.Clinic',
        on_delete=models.SET_NULL,
        related_name='community_posts',
        null=True,
        blank=True,
    )
    business = models.ForeignKey(
        'partners.BusinessProfile',
        on_delete=models.SET_NULL,
        related_name='community_posts',
        null=True,
        blank=True,
    )
    shelter = models.ForeignKey(
        'partners.ShelterProfile',
        on_delete=models.SET_NULL,
        related_name='community_posts',
        null=True,
        blank=True,
    )
    post_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_NORMAL)
    clinic_content_type = models.CharField(
        max_length=24,
        choices=CLINIC_CONTENT_CHOICES,
        blank=True,
        default='',
    )
    related_clinic_campaign = models.OneToOneField(
        'clinics.ClinicCampaign',
        on_delete=models.SET_NULL,
        related_name='community_post',
        null=True,
        blank=True,
    )
    text = models.TextField(blank=True, max_length=3000)
    image = models.ImageField(upload_to='community/posts/', blank=True, null=True)
    shares_count = models.PositiveIntegerField(default=0)
    province = models.CharField(max_length=100, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    is_public = models.BooleanField(default=True)
    comment_permission = models.CharField(
        max_length=20,
        choices=COMMENT_PERMISSION_CHOICES,
        default=COMMENTS_EVERYONE,
    )
    moderation_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PUBLISHED)
    related_lost_pet = models.OneToOneField(
        'lost_pets.LostPet',
        on_delete=models.CASCADE,
        related_name='community_post',
        null=True,
        blank=True,
    )
    related_birthday = models.OneToOneField(
        'pets.BirthdayCelebration',
        on_delete=models.CASCADE,
        related_name='community_post',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['moderation_status', '-created_at']),
            models.Index(fields=['post_type', '-created_at']),
            models.Index(fields=['locality', '-created_at']),
            models.Index(fields=['pet', '-created_at']),
            models.Index(fields=['clinic', '-created_at']),
            models.Index(fields=['business', '-created_at']),
            models.Index(fields=['shelter', '-created_at']),
        ]

    def clean(self):
        actor_count = sum(bool(value) for value in (
            self.pet_id, self.clinic_id, self.business_id, self.shelter_id,
        ))
        if actor_count > 1:
            raise ValidationError('Una publicación solo puede pertenecer a un perfil de VetPaw.')
        if actor_count == 0 and not self.related_lost_pet_id:
            raise ValidationError('La publicación debe tener una mascota, veterinaria, negocio, refugio o reporte asociado.')
        if not self.text and not self.image and not self.related_lost_pet_id and not self.related_birthday_id:
            raise ValidationError('La publicación necesita texto o imagen.')

    def __str__(self):
        if self.pet_id:
            actor = self.pet.name
        elif self.clinic_id:
            actor = self.clinic.name
        elif self.business_id:
            actor = self.business.name
        elif self.shelter_id:
            actor = self.shelter.name
        else:
            actor = 'VetPaw'
        return f'{actor}: {self.text[:50]}'


class Comment(models.Model):
    STATUS_PUBLISHED = 'published'
    STATUS_HIDDEN = 'hidden'
    STATUS_REMOVED = 'removed'
    STATUS_CHOICES = Post.STATUS_CHOICES

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_comments')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='replies',
        null=True,
        blank=True,
    )
    text = models.CharField(max_length=1000)
    moderation_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PUBLISHED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post', 'moderation_status', 'created_at']),
            models.Index(fields=['parent', 'moderation_status', 'created_at'], name='comm_comment_parent_idx'),
        ]

    def clean(self):
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError('Un comentario no puede responderse a sí mismo.')
            if self.parent.post_id != self.post_id:
                raise ValidationError('La respuesta debe pertenecer a la misma publicación.')
            if self.parent.parent_id:
                raise ValidationError('Las respuestas solo pueden tener un nivel de profundidad.')

    def __str__(self):
        return f'{self.author.username}: {self.text[:40]}'


class Reaction(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_reactions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['post', 'user'], name='unique_community_post_reaction')
        ]
        indexes = [models.Index(fields=['post', 'created_at'])]


class CommentReaction(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='community_comment_reactions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['comment', 'user'],
                name='unique_community_comment_reaction',
            )
        ]
        indexes = [models.Index(fields=['comment', 'created_at'], name='comm_creact_comment_idx')]


class PetFollow(models.Model):
    """Seguimiento social unificado.

    Se conserva el nombre histórico del modelo para no perder los seguimientos de
    mascotas existentes, pero ahora también puede apuntar a veterinarias,
    negocios y refugios. Exactamente uno de los cuatro destinos debe estar
    informado.
    """

    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='followed_pets',
    )
    pet = models.ForeignKey(
        'pets.Pet',
        on_delete=models.CASCADE,
        related_name='social_followers',
        null=True,
        blank=True,
    )
    clinic = models.ForeignKey(
        'clinics.Clinic',
        on_delete=models.CASCADE,
        related_name='social_followers',
        null=True,
        blank=True,
    )
    business = models.ForeignKey(
        'partners.BusinessProfile',
        on_delete=models.CASCADE,
        related_name='social_followers',
        null=True,
        blank=True,
    )
    shelter = models.ForeignKey(
        'partners.ShelterProfile',
        on_delete=models.CASCADE,
        related_name='social_followers',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(pet__isnull=False, clinic__isnull=True, business__isnull=True, shelter__isnull=True)
                    | Q(pet__isnull=True, clinic__isnull=False, business__isnull=True, shelter__isnull=True)
                    | Q(pet__isnull=True, clinic__isnull=True, business__isnull=False, shelter__isnull=True)
                    | Q(pet__isnull=True, clinic__isnull=True, business__isnull=True, shelter__isnull=False)
                ),
                name='community_follow_exactly_one_target',
            ),
            models.UniqueConstraint(
                fields=['follower', 'pet'],
                condition=Q(pet__isnull=False),
                name='unique_pet_follow',
            ),
            models.UniqueConstraint(
                fields=['follower', 'clinic'],
                condition=Q(clinic__isnull=False),
                name='unique_clinic_follow',
            ),
            models.UniqueConstraint(
                fields=['follower', 'business'],
                condition=Q(business__isnull=False),
                name='unique_business_follow',
            ),
            models.UniqueConstraint(
                fields=['follower', 'shelter'],
                condition=Q(shelter__isnull=False),
                name='unique_shelter_follow',
            ),
        ]
        indexes = [
            models.Index(fields=['follower', '-created_at'], name='comm_follow_follower_idx'),
            models.Index(fields=['pet', '-created_at'], name='comm_follow_pet_idx'),
            models.Index(fields=['clinic', '-created_at'], name='comm_follow_clinic_idx'),
            models.Index(fields=['business', '-created_at'], name='comm_follow_business_idx'),
            models.Index(fields=['shelter', '-created_at'], name='comm_follow_shelter_idx'),
        ]
        ordering = ['-created_at']

    @property
    def target_type(self):
        if self.pet_id:
            return 'pet'
        if self.clinic_id:
            return 'clinic'
        if self.business_id:
            return 'business'
        if self.shelter_id:
            return 'shelter'
        return ''

    @property
    def target(self):
        return self.pet or self.clinic or self.business or self.shelter

    @property
    def target_owner_id(self):
        target = self.target
        return getattr(target, 'owner_id', None)

    def clean(self):
        targets = [self.pet_id, self.clinic_id, self.business_id, self.shelter_id]
        if sum(value is not None for value in targets) != 1:
            raise ValidationError('El seguimiento debe apuntar a un único perfil de VetPaw.')
        if self.follower_id and self.target_owner_id == self.follower_id:
            raise ValidationError('No necesitás seguir tu propio perfil.')


class SavedPost(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_community_posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='saved_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'post'], name='unique_saved_community_post')
        ]
        ordering = ['-created_at']


class PetFollowRequest(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='community_follow_requests_sent',
    )
    pet = models.ForeignKey(
        'pets.Pet',
        on_delete=models.CASCADE,
        related_name='community_follow_requests',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['follower', 'pet'],
                name='unique_private_pet_follow_request',
            ),
        ]
        indexes = [
            models.Index(fields=['pet', '-created_at'], name='comm_freq_pet_date_idx'),
            models.Index(fields=['follower', '-created_at'], name='comm_freq_user_date_idx'),
        ]
        ordering = ['-created_at']


class MutedUser(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='community_mutes_made',
    )
    muted = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='community_mutes_received',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'muted'], name='unique_community_user_mute'),
            models.CheckConstraint(condition=~Q(user=models.F('muted')), name='cannot_mute_self_community'),
        ]
        ordering = ['-created_at']


class HiddenPost(models.Model):
    REASON_HIDDEN = 'hidden'
    REASON_NOT_INTERESTED = 'not_interested'
    REASON_CHOICES = [
        (REASON_HIDDEN, 'Ocultada'),
        (REASON_NOT_INTERESTED, 'No me interesa'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hidden_community_posts',
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='hidden_by_users',
    )
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default=REASON_HIDDEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'post'], name='unique_hidden_community_post')
        ]
        ordering = ['-created_at']


class CommunityPrivacySettings(models.Model):
    BIRTHDAY_COMMUNITY = 'community'
    BIRTHDAY_ACCOUNT = 'account'
    BIRTHDAY_OFF = 'off'
    BIRTHDAY_CHOICES = [
        (BIRTHDAY_COMMUNITY, 'Publicar en la comunidad'),
        (BIRTHDAY_ACCOUNT, 'Mostrar solo en mi cuenta'),
        (BIRTHDAY_OFF, 'No mostrar cumpleaños'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='community_privacy',
    )
    default_comment_permission = models.CharField(
        max_length=20,
        choices=Post.COMMENT_PERMISSION_CHOICES,
        default=Post.COMMENTS_EVERYONE,
    )
    show_location = models.BooleanField(default=True)
    show_birth_date = models.BooleanField(default=True)
    show_age = models.BooleanField(default=True)
    show_followers = models.BooleanField(default=True)
    show_following = models.BooleanField(default=True)
    show_paws = models.BooleanField(default=True)
    show_activity = models.BooleanField(default=True)
    birthday_visibility = models.CharField(
        max_length=20,
        choices=BIRTHDAY_CHOICES,
        default=BIRTHDAY_COMMUNITY,
    )
    show_phone = models.BooleanField(default=True)
    show_whatsapp = models.BooleanField(default=True)
    show_responsible_name = models.BooleanField(default=True)
    show_donation_info = models.BooleanField(default=True)
    allow_internal_messages = models.BooleanField(default=True)
    allow_appointment_requests = models.BooleanField(default=True)
    social_notifications_enabled = models.BooleanField(default=True)
    push_notifications_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Privacidad de {self.user}'


class BlockedUser(models.Model):
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_blocks_made')
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_blocks_received')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['blocker', 'blocked'], name='unique_community_user_block'),
            models.CheckConstraint(condition=~Q(blocker=models.F('blocked')), name='cannot_block_self_community'),
        ]
        ordering = ['-created_at']


class CommunityNotification(models.Model):
    TYPE_REACTION = 'reaction'
    TYPE_COMMENT = 'comment'
    TYPE_FOLLOW = 'follow'
    TYPE_COMMENT_REACTION = 'comment_reaction'
    TYPE_REPLY = 'reply'
    TYPE_MENTION = 'mention'
    TYPE_FOLLOW_REQUEST = 'follow_request'
    TYPE_BUSINESS_INQUIRY = 'business_inquiry'
    TYPE_BUSINESS_RESERVATION = 'business_reservation'
    TYPE_BUSINESS_RESERVATION_UPDATE = 'business_reservation_update'
    TYPE_CLINIC_APPOINTMENT = 'clinic_appointment'
    TYPE_CLINIC_APPOINTMENT_UPDATE = 'clinic_appointment_update'
    TYPE_CHOICES = [
        (TYPE_REACTION, 'Patita en publicación'),
        (TYPE_COMMENT, 'Comentario en publicación'),
        (TYPE_FOLLOW, 'Nuevo seguidor'),
        (TYPE_COMMENT_REACTION, 'Patita en comentario'),
        (TYPE_REPLY, 'Respuesta a comentario'),
        (TYPE_MENTION, 'Mención'),
        (TYPE_FOLLOW_REQUEST, 'Solicitud de seguimiento'),
        (TYPE_BUSINESS_INQUIRY, 'Consulta comercial'),
        (TYPE_BUSINESS_RESERVATION, 'Nueva reserva comercial'),
        (TYPE_BUSINESS_RESERVATION_UPDATE, 'Actualización de reserva comercial'),
        (TYPE_CLINIC_APPOINTMENT, 'Nueva solicitud de turno veterinario'),
        (TYPE_CLINIC_APPOINTMENT_UPDATE, 'Actualización de turno veterinario'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='community_notifications',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='community_notifications_sent',
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
    )
    pet = models.ForeignKey(
        'pets.Pet',
        on_delete=models.CASCADE,
        related_name='community_notifications',
        null=True,
        blank=True,
    )
    clinic = models.ForeignKey(
        'clinics.Clinic',
        on_delete=models.CASCADE,
        related_name='community_notifications',
        null=True,
        blank=True,
    )
    business = models.ForeignKey(
        'partners.BusinessProfile',
        on_delete=models.CASCADE,
        related_name='community_notifications',
        null=True,
        blank=True,
    )
    shelter = models.ForeignKey(
        'partners.ShelterProfile',
        on_delete=models.CASCADE,
        related_name='community_notifications',
        null=True,
        blank=True,
    )
    appointment = models.ForeignKey(
        'appointments.Appointment',
        on_delete=models.CASCADE,
        related_name='community_notifications',
        null=True,
        blank=True,
    )
    notification_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    extra_text = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at'], name='comm_notif_rec_read_idx'),
            models.Index(fields=['notification_type', '-created_at'], name='comm_notif_type_date_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'post', 'notification_type'],
                condition=Q(notification_type='reaction'),
                name='unique_reaction_notification',
            ),
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'pet', 'notification_type'],
                condition=Q(notification_type='follow', pet__isnull=False),
                name='unique_follow_notification',
            ),
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'clinic', 'notification_type'],
                condition=Q(notification_type='follow', clinic__isnull=False),
                name='unique_clinic_follow_notification',
            ),
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'business', 'notification_type'],
                condition=Q(notification_type='follow', business__isnull=False),
                name='unique_business_follow_notification',
            ),
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'shelter', 'notification_type'],
                condition=Q(notification_type='follow', shelter__isnull=False),
                name='unique_shelter_follow_notification',
            ),
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'pet', 'notification_type'],
                condition=Q(notification_type='follow_request', pet__isnull=False),
                name='unique_follow_request_notification',
            ),
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'comment', 'notification_type'],
                condition=Q(notification_type='comment_reaction', comment__isnull=False),
                name='unique_comment_reaction_notification',
            ),
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'comment', 'notification_type'],
                condition=Q(notification_type='reply', comment__isnull=False),
                name='unique_reply_notification',
            ),
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'post', 'notification_type'],
                condition=Q(notification_type='mention', comment__isnull=True, post__isnull=False),
                name='unique_post_mention_notification',
            ),
            models.UniqueConstraint(
                fields=['recipient', 'actor', 'comment', 'notification_type'],
                condition=Q(notification_type='mention', comment__isnull=False),
                name='unique_comment_mention_notification',
            ),
        ]

    def __str__(self):
        return f'{self.get_notification_type_display()} para {self.recipient}'


class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField()
    auth = models.TextField()
    user_agent = models.CharField(max_length=500, blank=True)
    device_name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    failure_count = models.PositiveSmallIntegerField(default=0)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'is_active', '-updated_at'], name='community_p_user_id_152c42_idx'),
        ]

    def __str__(self):
        label = self.device_name or 'Dispositivo'
        return f'{label} de {self.user}'


class Report(models.Model):
    REASON_SPAM = 'spam'
    REASON_SCAM = 'scam'
    REASON_ABUSE = 'abuse'
    REASON_PRIVACY = 'privacy'
    REASON_ANIMAL_SALE = 'animal_sale'
    REASON_INAPPROPRIATE = 'inappropriate'
    REASON_OTHER = 'other'
    REASON_CHOICES = [
        (REASON_SPAM, 'Spam o publicidad engañosa'),
        (REASON_SCAM, 'Estafa o información falsa'),
        (REASON_ABUSE, 'Maltrato, acoso o violencia'),
        (REASON_PRIVACY, 'Datos personales o privacidad'),
        (REASON_ANIMAL_SALE, 'Venta irresponsable de animales'),
        (REASON_INAPPROPRIATE, 'Contenido inapropiado'),
        (REASON_OTHER, 'Otro motivo'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_REVIEWED = 'reviewed'
    STATUS_DISMISSED = 'dismissed'
    STATUS_ACTIONED = 'actioned'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_REVIEWED, 'Revisado'),
        (STATUS_DISMISSED, 'Descartado'),
        (STATUS_ACTIONED, 'Se tomó una medida'),
    ]

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_reports')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reports', null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='reports', null=True, blank=True)
    reported_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_reports_received', null=True, blank=True)
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    details = models.TextField(blank=True, max_length=1000)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    moderator_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='community_reports_reviewed')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['status', '-created_at']
        indexes = [models.Index(fields=['status', '-created_at'])]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(post__isnull=False, comment__isnull=True, reported_user__isnull=True)
                    | Q(post__isnull=True, comment__isnull=False, reported_user__isnull=True)
                    | Q(post__isnull=True, comment__isnull=True, reported_user__isnull=False)
                ),
                name='community_report_single_target',
            )
        ]

    def clean(self):
        targets = sum(bool(value) for value in (self.post_id, self.comment_id, self.reported_user_id))
        if targets != 1:
            raise ValidationError('El reporte debe apuntar a una sola publicación, comentario o usuario.')

    def __str__(self):
        return f'Reporte #{self.pk or "nuevo"} — {self.get_reason_display()}'
