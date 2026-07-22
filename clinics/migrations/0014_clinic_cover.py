from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('clinics', '0013_backfill_clinic_pet_access_from_appointments'),
    ]

    operations = [
        migrations.AddField(
            model_name='clinic',
            name='cover',
            field=models.ImageField(blank=True, null=True, upload_to='clinics/covers/'),
        ),
    ]
