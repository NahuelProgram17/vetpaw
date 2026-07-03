# Generated manually for VetPaw clinical files.
from django.db import migrations, models
import pets.storage


class Migration(migrations.Migration):

    dependencies = [
        ('pets', '0011_clinicalphoto_file_pdf'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clinicalphoto',
            name='image',
            field=models.FileField(storage=pets.storage.ClinicalFileCloudinaryStorage(), upload_to='clinical_files/'),
        ),
    ]
