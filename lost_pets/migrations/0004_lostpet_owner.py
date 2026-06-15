from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('lost_pets', '0003_lostpet_locality_lostpet_province'),
    ]

    operations = [
        migrations.AddField(
            model_name='lostpet',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='lost_pets',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
