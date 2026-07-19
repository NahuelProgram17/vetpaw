from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from lost_pets.models import LostPet
from pets.models import BirthdayCelebration, Pet

from .models import PetSocialProfile, Post


@receiver(post_save, sender=Pet)
def ensure_pet_social_profile(sender, instance, **kwargs):
    PetSocialProfile.objects.get_or_create(pet=instance)


@receiver(post_save, sender=LostPet)
def sync_lost_pet_community_post(sender, instance, created, **kwargs):
    if not instance.owner_id:
        return
    label = 'Se perdió' if instance.report_type == 'lost' else 'Encontramos'
    pet_name = instance.pet_name or 'una mascota'
    text = f'🚨 {label} {pet_name}. {instance.description}'.strip()
    defaults = {
        'created_by': instance.owner,
        'post_type': Post.TYPE_LOST,
        'text': text[:3000],
        'province': instance.province,
        'locality': instance.locality,
        'is_public': True,
        'moderation_status': Post.STATUS_PUBLISHED if instance.expires_at > timezone.now() else Post.STATUS_HIDDEN,
    }
    Post.objects.update_or_create(related_lost_pet=instance, defaults=defaults)


@receiver(post_save, sender=BirthdayCelebration)
def create_birthday_community_post(sender, instance, created, **kwargs):
    if not created:
        return
    profile, _ = PetSocialProfile.objects.get_or_create(pet=instance.pet)
    if not profile.is_public:
        return
    age_label = f'{instance.age} año' if instance.age == 1 else f'{instance.age} años'
    Post.objects.get_or_create(
        related_birthday=instance,
        defaults={
            'created_by': instance.pet.owner,
            'pet': instance.pet,
            'post_type': Post.TYPE_BIRTHDAY,
            'text': f'🎂 Hoy {instance.pet.name} cumple {age_label}. ¡La comunidad VetPaw le desea un día lleno de mimos y aventuras!',
            'province': instance.pet.owner.province,
            'locality': instance.pet.owner.locality,
            'is_public': True,
        },
    )
