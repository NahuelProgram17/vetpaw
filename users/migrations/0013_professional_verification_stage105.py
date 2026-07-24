from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def initialize_professional_verifications(apps, schema_editor):
    User = apps.get_model('users', 'User')
    BusinessProfile = apps.get_model('partners', 'BusinessProfile')
    ShelterProfile = apps.get_model('partners', 'ShelterProfile')
    now = django.utils.timezone.now()

    User.objects.filter(role__in=('clinic', 'business', 'shelter')).update(
        professional_verification_status='pending',
        verification_updated_at=now,
    )

    verified_user_ids = list(
        BusinessProfile.objects.filter(is_verified=True).values_list('owner_id', flat=True)
    )
    verified_user_ids.extend(
        ShelterProfile.objects.filter(is_verified=True).values_list('owner_id', flat=True)
    )
    if verified_user_ids:
        User.objects.filter(id__in=verified_user_ids).update(
            professional_verification_status='verified',
            verification_updated_at=now,
            verified_at=now,
        )


def reverse_professional_verifications(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.update(
        professional_verification_status='not_applicable',
        verification_public_note='',
        verification_updated_at=None,
        verified_at=None,
        verified_by=None,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0012_abuse_protection_stage104'),
        ('partners', '0002_businessprofile_accepts_reservations'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='professional_verification_status',
            field=models.CharField(
                choices=[
                    ('not_applicable', 'No corresponde'),
                    ('pending', 'Pendiente'),
                    ('in_review', 'En revisión'),
                    ('corrections', 'Requiere correcciones'),
                    ('verified', 'Verificada'),
                    ('rejected', 'Rechazada'),
                    ('withdrawn', 'Verificación retirada'),
                ],
                default='not_applicable',
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='verification_public_note',
            field=models.TextField(blank=True, max_length=1200),
        ),
        migrations.AddField(
            model_name='user',
            name='verification_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='verified_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='professional_verifications_granted',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name='ProfessionalVerificationDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_status', models.CharField(
                    choices=[
                        ('not_applicable', 'No corresponde'),
                        ('pending', 'Pendiente'),
                        ('in_review', 'En revisión'),
                        ('corrections', 'Requiere correcciones'),
                        ('verified', 'Verificada'),
                        ('rejected', 'Rechazada'),
                        ('withdrawn', 'Verificación retirada'),
                    ],
                    max_length=24,
                )),
                ('to_status', models.CharField(
                    choices=[
                        ('not_applicable', 'No corresponde'),
                        ('pending', 'Pendiente'),
                        ('in_review', 'En revisión'),
                        ('corrections', 'Requiere correcciones'),
                        ('verified', 'Verificada'),
                        ('rejected', 'Rechazada'),
                        ('withdrawn', 'Verificación retirada'),
                    ],
                    max_length=24,
                )),
                ('public_note', models.TextField(blank=True, max_length=1200)),
                ('internal_note', models.TextField(blank=True, max_length=2000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('decided_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='professional_verification_decisions_made',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='professional_verification_decisions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', '-created_at'], name='users_profver_user_created_idx'),
                    models.Index(fields=['to_status', '-created_at'], name='users_pver_status_created'),
                ],
            },
        ),
        migrations.RunPython(
            initialize_professional_verifications,
            reverse_professional_verifications,
        ),
    ]
