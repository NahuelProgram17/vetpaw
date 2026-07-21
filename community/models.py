from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class PetSocialProfile(models.Model):
    pet = models.OneToOneField(
        'pets.Pet',
        on_delete=models.CASCADE,
        related_name='social_profile',
    )
    bio = models.CharField(max_length=500, blank=True)
    cover = models.ImageField(upload_to='community/pet-covers/', blank=True, null=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Perfil social de {self.pet.name}'


class Post(models.Model):
    TYPE_NORMAL = 'normal'
    TYPE_BIRTHDAY = 'birthday'
    TYPE_LOST = 'lost'
    TYPE_CLINIC = 'clinic'
    TYPE_ADOPTION = 'adoption'
    TYPE_CHOICES = [
        (TYPE_NORMAL, 'Publicación'),
        (TYPE_BIRTHDAY, 'Cumpleaños'),
        (TYPE_LOST, 'Mascota perdida/encontrada'),
        (TYPE_CLINIC, 'Veterinaria'),
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
    post_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_NORMAL)
    text = models.TextField(blank=True, max_length=3000)
    image = models.ImageField(upload_to='community/posts/', blank=True, null=True)
    province = models.CharField(max_length=100, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    is_public = models.BooleanField(default=True)
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
        ]

    def clean(self):
        if self.pet_id and self.clinic_id:
            raise ValidationError('Una publicación no puede pertenecer a una mascota y una veterinaria a la vez.')
        if not self.pet_id and not self.clinic_id and not self.related_lost_pet_id:
            raise ValidationError('La publicación debe tener una mascota, una veterinaria o un reporte asociado.')
        if not self.text and not self.image and not self.related_lost_pet_id and not self.related_birthday_id:
            raise ValidationError('La publicación necesita texto o imagen.')

    def __str__(self):
        actor = self.pet.name if self.pet_id else self.clinic.name if self.clinic_id else 'VetPaw'
        return f'{actor}: {self.text[:50]}'


class Comment(models.Model):
    STATUS_PUBLISHED = 'published'
    STATUS_HIDDEN = 'hidden'
    STATUS_REMOVED = 'removed'
    STATUS_CHOICES = Post.STATUS_CHOICES

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_comments')
    text = models.CharField(max_length=1000)
    moderation_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PUBLISHED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['post', 'moderation_status', 'created_at'])]

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


class PetFollow(models.Model):
    follower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followed_pets')
    pet = models.ForeignKey('pets.Pet', on_delete=models.CASCADE, related_name='social_followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['follower', 'pet'], name='unique_pet_follow')
        ]
        ordering = ['-created_at']

    def clean(self):
        if self.pet_id and self.follower_id == self.pet.owner_id:
            raise ValidationError('No necesitás seguir a tu propia mascota.')


class SavedPost(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_community_posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='saved_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'post'], name='unique_saved_community_post')
        ]
        ordering = ['-created_at']


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
    TYPE_CHOICES = [
        (TYPE_REACTION, 'Patita en publicación'),
        (TYPE_COMMENT, 'Comentario en publicación'),
        (TYPE_FOLLOW, 'Nuevo seguidor'),
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
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
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
                condition=Q(notification_type='follow'),
                name='unique_follow_notification',
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
