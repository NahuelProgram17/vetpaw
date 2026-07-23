from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0010_appointment_seen_by_clinic'),
        ('clinics', '0016_cliniccampaign'),
        ('community', '0009_clinic_community_stage8'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='source_campaign',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appointments', to='clinics.cliniccampaign'),
        ),
        migrations.AddField(
            model_name='appointment',
            name='source_post',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generated_appointments', to='community.post'),
        ),
    ]
