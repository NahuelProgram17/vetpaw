from django.db import migrations, models


def normalize_existing_data(apps, schema_editor):
    Clinic = apps.get_model('clinics', 'Clinic')
    ClinicCampaign = apps.get_model('clinics', 'ClinicCampaign')

    # Las clínicas que ya usaban VetPaw antes de incorporar planes conservan
    # sus herramientas activas. Se consideran cuentas preexistentes, no nuevas
    # candidatas al beneficio inicial de 30 días.
    Clinic.objects.filter(plan_status='active').update(
        trial_used=True,
        plan_notes='Plan activo previo a la gestión de suscripciones',
    )
    ClinicCampaign.objects.filter(allow_booking=True).update(allow_booking=False)
    ClinicCampaign.objects.filter(campaign_type='guard').update(campaign_type='other')


class Migration(migrations.Migration):
    dependencies = [
        ('clinics', '0016_cliniccampaign'),
    ]

    operations = [
        migrations.AddField(
            model_name='clinic',
            name='plan_status',
            field=models.CharField(
                choices=[
                    ('inactive', 'Sin plan'),
                    ('trial', 'Mes de prueba gratis'),
                    ('active', 'Plan activo'),
                    ('grace', 'Período de gracia'),
                    ('expired', 'Plan vencido'),
                    ('suspended', 'Plan suspendido'),
                ],
                default='active',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='clinic',
            name='plan_started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='clinic',
            name='plan_ends_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='clinic',
            name='grace_ends_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='clinic',
            name='trial_used',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='clinic',
            name='plan_notes',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AlterField(
            model_name='cliniccampaign',
            name='allow_booking',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(normalize_existing_data, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='cliniccampaign',
            name='campaign_type',
            field=models.CharField(
                choices=[
                    ('vaccination', 'Campaña de vacunación'),
                    ('castration', 'Campaña de castración'),
                    ('checkup', 'Jornada de controles'),
                    ('event', 'Evento veterinario'),
                    ('other', 'Otra actividad'),
                ],
                default='other',
                max_length=24,
            ),
        ),
    ]
