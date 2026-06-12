from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ('pets', '0005_clinicalphoto'),
]

    operations = [
        migrations.AddField(
            model_name='vaccine',
            name='reminder_sent',
            field=models.BooleanField(default=False),
        ),
    ]
