# Generated manually for VetPaw clinical attachments
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pets', '0010_alter_pet_temperament_choices'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clinicalphoto',
            name='image',
            field=models.FileField(upload_to='clinical_files/'),
        ),
    ]
