from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('community', '0002_communitynotification'),
    ]

    operations = [
        migrations.CreateModel(
            name='PushSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.TextField(unique=True)),
                ('p256dh', models.TextField()),
                ('auth', models.TextField()),
                ('user_agent', models.CharField(blank=True, max_length=500)),
                ('device_name', models.CharField(blank=True, max_length=120)),
                ('is_active', models.BooleanField(default=True)),
                ('failure_count', models.PositiveSmallIntegerField(default=0)),
                ('last_success_at', models.DateTimeField(blank=True, null=True)),
                ('last_failure_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='push_subscriptions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddIndex(
            model_name='pushsubscription',
            index=models.Index(fields=['user', 'is_active', '-updated_at'], name='community_p_user_id_152c42_idx'),
        ),
    ]
