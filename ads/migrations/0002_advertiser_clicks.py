from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ads', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='advertiser',
            name='clicks',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
