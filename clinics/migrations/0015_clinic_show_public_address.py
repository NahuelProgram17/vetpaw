from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('clinics', '0014_clinic_cover')]

    operations = [
        migrations.AddField(
            model_name='clinic',
            name='show_public_address',
            field=models.BooleanField(default=True),
        ),
    ]
