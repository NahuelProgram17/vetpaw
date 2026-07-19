# Generated for VetPaw Comunidad
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_social_profiles_and_system_posts(apps, schema_editor):
    Pet = apps.get_model('pets', 'Pet')
    BirthdayCelebration = apps.get_model('pets', 'BirthdayCelebration')
    LostPet = apps.get_model('lost_pets', 'LostPet')
    PetSocialProfile = apps.get_model('community', 'PetSocialProfile')
    Post = apps.get_model('community', 'Post')

    PetSocialProfile.objects.bulk_create(
        [PetSocialProfile(pet_id=pet_id) for pet_id in Pet.objects.values_list('id', flat=True)],
        ignore_conflicts=True,
    )

    for lost in LostPet.objects.exclude(owner_id=None).iterator():
        label = 'Se perdió' if lost.report_type == 'lost' else 'Encontramos'
        pet_name = lost.pet_name or 'una mascota'
        Post.objects.get_or_create(
            related_lost_pet_id=lost.id,
            defaults={
                'created_by_id': lost.owner_id,
                'post_type': 'lost',
                'text': f'🚨 {label} {pet_name}. {lost.description}'[:3000],
                'province': lost.province,
                'locality': lost.locality,
                'is_public': True,
                'moderation_status': 'published',
            },
        )

    for celebration in BirthdayCelebration.objects.select_related('pet__owner').iterator():
        age_label = f'{celebration.age} año' if celebration.age == 1 else f'{celebration.age} años'
        Post.objects.get_or_create(
            related_birthday_id=celebration.id,
            defaults={
                'created_by_id': celebration.pet.owner_id,
                'pet_id': celebration.pet_id,
                'post_type': 'birthday',
                'text': f'🎂 Hoy {celebration.pet.name} cumple {age_label}. ¡La comunidad VetPaw le desea un día lleno de mimos y aventuras!',
                'province': celebration.pet.owner.province,
                'locality': celebration.pet.owner.locality,
                'is_public': True,
                'moderation_status': 'published',
            },
        )


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('clinics', '0013_backfill_clinic_pet_access_from_appointments'),
        ('lost_pets', '0005_lostpet_breed_lostpet_incident_date_lostpet_pet_name_and_more'),
        ('pets', '0015_birthdaycelebration'),
    ]

    operations = [
        migrations.CreateModel(
            name='PetSocialProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bio', models.CharField(blank=True, max_length=500)),
                ('cover', models.ImageField(blank=True, null=True, upload_to='community/pet-covers/')),
                ('is_public', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('pet', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='social_profile', to='pets.pet')),
            ],
        ),
        migrations.CreateModel(
            name='Post',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('post_type', models.CharField(choices=[('normal', 'Publicación'), ('birthday', 'Cumpleaños'), ('lost', 'Mascota perdida/encontrada'), ('clinic', 'Veterinaria'), ('adoption', 'Adopción')], default='normal', max_length=20)),
                ('text', models.TextField(blank=True, max_length=3000)),
                ('image', models.ImageField(blank=True, null=True, upload_to='community/posts/')),
                ('province', models.CharField(blank=True, max_length=100)),
                ('locality', models.CharField(blank=True, max_length=100)),
                ('is_public', models.BooleanField(default=True)),
                ('moderation_status', models.CharField(choices=[('published', 'Publicada'), ('hidden', 'Oculta'), ('removed', 'Eliminada por moderación')], default='published', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('clinic', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='community_posts', to='clinics.clinic')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='community_posts', to=settings.AUTH_USER_MODEL)),
                ('pet', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='community_posts', to='pets.pet')),
                ('related_birthday', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='community_post', to='pets.birthdaycelebration')),
                ('related_lost_pet', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='community_post', to='lost_pets.lostpet')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=1000)),
                ('moderation_status', models.CharField(choices=[('published', 'Publicada'), ('hidden', 'Oculta'), ('removed', 'Eliminada por moderación')], default='published', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_comments', to=settings.AUTH_USER_MODEL)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='community.post')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.CreateModel(
            name='Reaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reactions', to='community.post')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_reactions', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='PetFollow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('follower', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='followed_pets', to=settings.AUTH_USER_MODEL)),
                ('pet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='social_followers', to='pets.pet')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='SavedPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saved_by', to='community.post')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saved_community_posts', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='BlockedUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('blocked', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_blocks_received', to=settings.AUTH_USER_MODEL)),
                ('blocker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_blocks_made', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(choices=[('spam', 'Spam o publicidad engañosa'), ('scam', 'Estafa o información falsa'), ('abuse', 'Maltrato, acoso o violencia'), ('privacy', 'Datos personales o privacidad'), ('animal_sale', 'Venta irresponsable de animales'), ('inappropriate', 'Contenido inapropiado'), ('other', 'Otro motivo')], max_length=30)),
                ('details', models.TextField(blank=True, max_length=1000)),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('reviewed', 'Revisado'), ('dismissed', 'Descartado'), ('actioned', 'Se tomó una medida')], default='pending', max_length=20)),
                ('moderator_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('comment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='community.comment')),
                ('post', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='community.post')),
                ('reported_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='community_reports_received', to=settings.AUTH_USER_MODEL)),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_reports', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='community_reports_reviewed', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['status', '-created_at']},
        ),
        migrations.AddIndex(model_name='post', index=models.Index(fields=['moderation_status', '-created_at'], name='community_p_moderat_5f2624_idx')),
        migrations.AddIndex(model_name='post', index=models.Index(fields=['post_type', '-created_at'], name='community_p_post_ty_d58aee_idx')),
        migrations.AddIndex(model_name='post', index=models.Index(fields=['locality', '-created_at'], name='community_p_localit_d3add2_idx')),
        migrations.AddIndex(model_name='post', index=models.Index(fields=['pet', '-created_at'], name='community_p_pet_id_40e4ab_idx')),
        migrations.AddIndex(model_name='post', index=models.Index(fields=['clinic', '-created_at'], name='community_p_clinic__427764_idx')),
        migrations.AddIndex(model_name='comment', index=models.Index(fields=['post', 'moderation_status', 'created_at'], name='community_c_post_id_ea6f03_idx')),
        migrations.AddIndex(model_name='reaction', index=models.Index(fields=['post', 'created_at'], name='community_r_post_id_215210_idx')),
        migrations.AddIndex(model_name='report', index=models.Index(fields=['status', '-created_at'], name='community_r_status_9e80af_idx')),
        migrations.AddConstraint(model_name='reaction', constraint=models.UniqueConstraint(fields=('post', 'user'), name='unique_community_post_reaction')),
        migrations.AddConstraint(model_name='petfollow', constraint=models.UniqueConstraint(fields=('follower', 'pet'), name='unique_pet_follow')),
        migrations.AddConstraint(model_name='savedpost', constraint=models.UniqueConstraint(fields=('user', 'post'), name='unique_saved_community_post')),
        migrations.AddConstraint(model_name='blockeduser', constraint=models.UniqueConstraint(fields=('blocker', 'blocked'), name='unique_community_user_block')),
        migrations.AddConstraint(model_name='blockeduser', constraint=models.CheckConstraint(condition=models.Q(('blocker', models.F('blocked')), _negated=True), name='cannot_block_self_community')),
        migrations.AddConstraint(
            model_name='report',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(('comment__isnull', True), ('post__isnull', False), ('reported_user__isnull', True))
                    | models.Q(('comment__isnull', False), ('post__isnull', True), ('reported_user__isnull', True))
                    | models.Q(('comment__isnull', True), ('post__isnull', True), ('reported_user__isnull', False))
                ),
                name='community_report_single_target',
            ),
        ),
        migrations.RunPython(backfill_social_profiles_and_system_posts, migrations.RunPython.noop),
    ]
