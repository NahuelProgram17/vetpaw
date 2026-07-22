from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q, F


def restore_private_pet_posts(apps, schema_editor):
    Post = apps.get_model('community', 'Post')
    Post.objects.filter(pet__social_profile__is_public=False).update(is_public=True)


class Migration(migrations.Migration):
    dependencies = [
        ('community', '0006_advanced_comments_stage4'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='comment_permission',
            field=models.CharField(
                choices=[
                    ('everyone', 'Todos pueden comentar'),
                    ('followers', 'Solo seguidores'),
                    ('none', 'Comentarios desactivados'),
                ],
                default='everyone',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='CommunityPrivacySettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('default_comment_permission', models.CharField(choices=[('everyone', 'Todos pueden comentar'), ('followers', 'Solo seguidores'), ('none', 'Comentarios desactivados')], default='everyone', max_length=20)),
                ('show_location', models.BooleanField(default=True)),
                ('show_birth_date', models.BooleanField(default=True)),
                ('show_age', models.BooleanField(default=True)),
                ('show_followers', models.BooleanField(default=True)),
                ('show_following', models.BooleanField(default=True)),
                ('show_paws', models.BooleanField(default=True)),
                ('show_activity', models.BooleanField(default=True)),
                ('birthday_visibility', models.CharField(choices=[('community', 'Publicar en la comunidad'), ('account', 'Mostrar solo en mi cuenta'), ('off', 'No mostrar cumpleaños')], default='community', max_length=20)),
                ('show_phone', models.BooleanField(default=True)),
                ('show_whatsapp', models.BooleanField(default=True)),
                ('show_responsible_name', models.BooleanField(default=True)),
                ('show_donation_info', models.BooleanField(default=True)),
                ('allow_internal_messages', models.BooleanField(default=True)),
                ('allow_appointment_requests', models.BooleanField(default=True)),
                ('social_notifications_enabled', models.BooleanField(default=True)),
                ('push_notifications_enabled', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='community_privacy', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='HiddenPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(choices=[('hidden', 'Ocultada'), ('not_interested', 'No me interesa')], default='hidden', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hidden_by_users', to='community.post')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hidden_community_posts', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='MutedUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('muted', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_mutes_received', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_mutes_made', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='PetFollowRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('follower', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_follow_requests_sent', to=settings.AUTH_USER_MODEL)),
                ('pet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_follow_requests', to='pets.pet')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(model_name='hiddenpost', constraint=models.UniqueConstraint(fields=('user', 'post'), name='unique_hidden_community_post')),
        migrations.AddConstraint(model_name='muteduser', constraint=models.UniqueConstraint(fields=('user', 'muted'), name='unique_community_user_mute')),
        migrations.AddConstraint(model_name='muteduser', constraint=models.CheckConstraint(condition=~Q(user=F('muted')), name='cannot_mute_self_community')),
        migrations.AddConstraint(model_name='petfollowrequest', constraint=models.UniqueConstraint(fields=('follower', 'pet'), name='unique_private_pet_follow_request')),
        migrations.AddIndex(model_name='petfollowrequest', index=models.Index(fields=['pet', '-created_at'], name='comm_freq_pet_date_idx')),
        migrations.AddIndex(model_name='petfollowrequest', index=models.Index(fields=['follower', '-created_at'], name='comm_freq_user_date_idx')),
        migrations.AlterField(
            model_name='communitynotification',
            name='notification_type',
            field=models.CharField(choices=[('reaction', 'Patita en publicación'), ('comment', 'Comentario en publicación'), ('follow', 'Nuevo seguidor'), ('comment_reaction', 'Patita en comentario'), ('reply', 'Respuesta a comentario'), ('mention', 'Mención'), ('follow_request', 'Solicitud de seguimiento')], max_length=20),
        ),
        migrations.AddConstraint(
            model_name='communitynotification',
            constraint=models.UniqueConstraint(condition=Q(notification_type='follow_request', pet__isnull=False), fields=('recipient', 'actor', 'pet', 'notification_type'), name='unique_follow_request_notification'),
        ),
        migrations.RunPython(restore_private_pet_posts, migrations.RunPython.noop),
    ]
