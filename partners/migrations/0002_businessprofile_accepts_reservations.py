from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('partners', '0001_initial')]
    operations = [
        migrations.AddField(
            model_name='businessprofile',
            name='accepts_reservations',
            field=models.BooleanField(default=False),
        ),
    ]
