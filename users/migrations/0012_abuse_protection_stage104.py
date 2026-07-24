from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0011_account_sanctions_stage103'),
    ]

    operations = [
        migrations.CreateModel(
            name='AbuseAction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('action_type', models.CharField(choices=[('post', 'Publicación'), ('comment', 'Comentario'), ('message', 'Mensaje'), ('follow', 'Seguimiento'), ('report', 'Reporte'), ('registration', 'Registro')], max_length=24)),
                ('fingerprint', models.CharField(blank=True, max_length=64)),
                ('link_fingerprint', models.CharField(blank=True, max_length=64)),
                ('target_key', models.CharField(blank=True, max_length=120)),
                ('content_excerpt', models.CharField(blank=True, max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='abuse_actions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', 'action_type', '-created_at'], name='users_abact_user_action_idx'),
                    models.Index(fields=['ip_address', 'action_type', '-created_at'], name='users_abact_ip_action_idx'),
                    models.Index(fields=['fingerprint', '-created_at'], name='users_abact_fingerprint_idx'),
                    models.Index(fields=['link_fingerprint', '-created_at'], name='users_abact_link_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='AbuseSignal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('category', models.CharField(choices=[('rate_limit', 'Límite de acciones superado'), ('duplicate_content', 'Contenido repetido'), ('repeated_link', 'Enlace repetido'), ('mass_follow', 'Seguimientos masivos'), ('false_report', 'Reportes descartados repetidos'), ('registration_burst', 'Registros acelerados desde el mismo origen'), ('account_risk', 'Comportamiento de cuenta sospechoso')], max_length=32)),
                ('severity', models.CharField(choices=[('info', 'Informativa'), ('warning', 'En observación'), ('high', 'Riesgo alto')], default='warning', max_length=16)),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('reviewed', 'Revisada'), ('dismissed', 'Descartada'), ('actioned', 'Se tomó una medida')], default='pending', max_length=16)),
                ('action_key', models.CharField(blank=True, max_length=80)),
                ('fingerprint', models.CharField(blank=True, max_length=64)),
                ('content_excerpt', models.CharField(blank=True, max_length=300)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('occurrences', models.PositiveIntegerField(default=1)),
                ('first_seen_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_seen_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('moderator_notes', models.TextField(blank=True, max_length=2000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='abuse_signals_reviewed', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='abuse_signals', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['status', '-last_seen_at'],
                'indexes': [
                    models.Index(fields=['status', 'severity', '-last_seen_at'], name='users_absig_status_sev_idx'),
                    models.Index(fields=['user', 'status', '-last_seen_at'], name='users_absig_user_status_idx'),
                    models.Index(fields=['ip_address', 'status', '-last_seen_at'], name='users_absig_ip_status_idx'),
                    models.Index(fields=['category', '-last_seen_at'], name='users_absig_category_idx'),
                ],
            },
        ),
        migrations.AddField(
            model_name='accountsanction',
            name='source_abuse_signal',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='account_sanctions', to='users.abusesignal'),
        ),
    ]
