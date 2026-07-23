from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clinics', '0015_clinic_show_public_address'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClinicCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('campaign_type', models.CharField(choices=[('vaccination', 'Campaña de vacunación'), ('castration', 'Campaña de castración'), ('checkup', 'Jornada de controles'), ('event', 'Evento veterinario'), ('guard', 'Guardia especial'), ('other', 'Otra actividad')], default='other', max_length=24)),
                ('title', models.CharField(max_length=180)),
                ('description', models.TextField(max_length=3000)),
                ('starts_at', models.DateTimeField()),
                ('ends_at', models.DateTimeField(blank=True, null=True)),
                ('location', models.CharField(blank=True, max_length=255)),
                ('capacity', models.PositiveIntegerField(blank=True, null=True)),
                ('species', models.JSONField(blank=True, default=list)),
                ('price', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('is_free', models.BooleanField(default=False)),
                ('image', models.ImageField(blank=True, null=True, upload_to='clinics/campaigns/')),
                ('allow_booking', models.BooleanField(default=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('clinic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_campaigns', to='clinics.clinic')),
            ],
            options={
                'ordering': ['starts_at'],
            },
        ),
        migrations.AddIndex(
            model_name='cliniccampaign',
            index=models.Index(fields=['clinic', 'is_active', 'starts_at'], name='clinic_campaign_active_idx'),
        ),
        migrations.AddIndex(
            model_name='cliniccampaign',
            index=models.Index(fields=['campaign_type', 'starts_at'], name='clinic_campaign_type_idx'),
        ),
    ]
