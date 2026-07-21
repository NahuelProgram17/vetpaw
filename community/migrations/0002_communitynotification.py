from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('community', '0001_initial'),
        ('pets', '0015_birthdaycelebration'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommunityNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('reaction', 'Patita en publicación'), ('comment', 'Comentario en publicación'), ('follow', 'Nuevo seguidor')], max_length=20)),
                ('extra_text', models.CharField(blank=True, max_length=300)),
                ('is_read', models.BooleanField(default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_notifications_sent', to=settings.AUTH_USER_MODEL)),
                ('comment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='community.comment')),
                ('pet', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='community_notifications', to='pets.pet')),
                ('post', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='community.post')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='communitynotification',
            index=models.Index(fields=['recipient', 'is_read', '-created_at'], name='comm_notif_rec_read_idx'),
        ),
        migrations.AddIndex(
            model_name='communitynotification',
            index=models.Index(fields=['notification_type', '-created_at'], name='comm_notif_type_date_idx'),
        ),
        migrations.AddConstraint(
            model_name='communitynotification',
            constraint=models.UniqueConstraint(condition=models.Q(('notification_type', 'reaction')), fields=('recipient', 'actor', 'post', 'notification_type'), name='unique_reaction_notification'),
        ),
        migrations.AddConstraint(
            model_name='communitynotification',
            constraint=models.UniqueConstraint(condition=models.Q(('notification_type', 'follow')), fields=('recipient', 'actor', 'pet', 'notification_type'), name='unique_follow_notification'),
        ),
    ]
