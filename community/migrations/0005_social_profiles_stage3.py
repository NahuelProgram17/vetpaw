from django.db import migrations, models
from django.utils.text import slugify
import django.db.models.deletion


def populate_pet_profile_slugs(apps, schema_editor):
    PetSocialProfile = apps.get_model('community', 'PetSocialProfile')
    for profile in PetSocialProfile.objects.select_related('pet').all().iterator():
        base = slugify(profile.pet.name) or f'mascota-{profile.pet_id}'
        candidate = base
        index = 2
        while PetSocialProfile.objects.filter(slug=candidate).exclude(pk=profile.pk).exists():
            candidate = f'{base}-{index}'
            index += 1
        profile.slug = candidate
        profile.save(update_fields=['slug'])


class Migration(migrations.Migration):
    dependencies = [
        ('clinics', '0014_clinic_cover'),
        ('community', '0004_post_business_post_shelter_and_types'),
        ('partners', '0001_initial'),
        ('pets', '0015_birthdaycelebration'),
    ]

    operations = [
        migrations.AddField(
            model_name='petsocialprofile',
            name='slug',
            field=models.SlugField(blank=True, max_length=180, null=True, unique=True),
        ),
        migrations.RunPython(populate_pet_profile_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='petsocialprofile',
            name='slug',
            field=models.SlugField(blank=True, max_length=180, unique=True),
        ),
        migrations.AlterField(
            model_name='petfollow',
            name='pet',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='social_followers', to='pets.pet'),
        ),
        migrations.AddField(
            model_name='petfollow',
            name='clinic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='social_followers', to='clinics.clinic'),
        ),
        migrations.AddField(
            model_name='petfollow',
            name='business',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='social_followers', to='partners.businessprofile'),
        ),
        migrations.AddField(
            model_name='petfollow',
            name='shelter',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='social_followers', to='partners.shelterprofile'),
        ),
        migrations.RemoveConstraint(
            model_name='petfollow',
            name='unique_pet_follow',
        ),
        migrations.AddConstraint(
            model_name='petfollow',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(pet__isnull=False, clinic__isnull=True, business__isnull=True, shelter__isnull=True)
                    | models.Q(pet__isnull=True, clinic__isnull=False, business__isnull=True, shelter__isnull=True)
                    | models.Q(pet__isnull=True, clinic__isnull=True, business__isnull=False, shelter__isnull=True)
                    | models.Q(pet__isnull=True, clinic__isnull=True, business__isnull=True, shelter__isnull=False)
                ),
                name='community_follow_exactly_one_target',
            ),
        ),
        migrations.AddConstraint(
            model_name='petfollow',
            constraint=models.UniqueConstraint(condition=models.Q(pet__isnull=False), fields=('follower', 'pet'), name='unique_pet_follow'),
        ),
        migrations.AddConstraint(
            model_name='petfollow',
            constraint=models.UniqueConstraint(condition=models.Q(clinic__isnull=False), fields=('follower', 'clinic'), name='unique_clinic_follow'),
        ),
        migrations.AddConstraint(
            model_name='petfollow',
            constraint=models.UniqueConstraint(condition=models.Q(business__isnull=False), fields=('follower', 'business'), name='unique_business_follow'),
        ),
        migrations.AddConstraint(
            model_name='petfollow',
            constraint=models.UniqueConstraint(condition=models.Q(shelter__isnull=False), fields=('follower', 'shelter'), name='unique_shelter_follow'),
        ),
        migrations.AddIndex(
            model_name='petfollow',
            index=models.Index(fields=['follower', '-created_at'], name='comm_follow_follower_idx'),
        ),
        migrations.AddIndex(
            model_name='petfollow',
            index=models.Index(fields=['pet', '-created_at'], name='comm_follow_pet_idx'),
        ),
        migrations.AddIndex(
            model_name='petfollow',
            index=models.Index(fields=['clinic', '-created_at'], name='comm_follow_clinic_idx'),
        ),
        migrations.AddIndex(
            model_name='petfollow',
            index=models.Index(fields=['business', '-created_at'], name='comm_follow_business_idx'),
        ),
        migrations.AddIndex(
            model_name='petfollow',
            index=models.Index(fields=['shelter', '-created_at'], name='comm_follow_shelter_idx'),
        ),
        migrations.AddField(
            model_name='communitynotification',
            name='clinic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='community_notifications', to='clinics.clinic'),
        ),
        migrations.AddField(
            model_name='communitynotification',
            name='business',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='community_notifications', to='partners.businessprofile'),
        ),
        migrations.AddField(
            model_name='communitynotification',
            name='shelter',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='community_notifications', to='partners.shelterprofile'),
        ),
        migrations.RemoveConstraint(
            model_name='communitynotification',
            name='unique_follow_notification',
        ),
        migrations.AddConstraint(
            model_name='communitynotification',
            constraint=models.UniqueConstraint(condition=models.Q(notification_type='follow', pet__isnull=False), fields=('recipient', 'actor', 'pet', 'notification_type'), name='unique_follow_notification'),
        ),
        migrations.AddConstraint(
            model_name='communitynotification',
            constraint=models.UniqueConstraint(condition=models.Q(notification_type='follow', clinic__isnull=False), fields=('recipient', 'actor', 'clinic', 'notification_type'), name='unique_clinic_follow_notification'),
        ),
        migrations.AddConstraint(
            model_name='communitynotification',
            constraint=models.UniqueConstraint(condition=models.Q(notification_type='follow', business__isnull=False), fields=('recipient', 'actor', 'business', 'notification_type'), name='unique_business_follow_notification'),
        ),
        migrations.AddConstraint(
            model_name='communitynotification',
            constraint=models.UniqueConstraint(condition=models.Q(notification_type='follow', shelter__isnull=False), fields=('recipient', 'actor', 'shelter', 'notification_type'), name='unique_shelter_follow_notification'),
        ),
    ]
