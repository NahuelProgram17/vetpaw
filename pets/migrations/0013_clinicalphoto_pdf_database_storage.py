# Generated manually for VetPaw clinical PDF storage.
from django.db import migrations, models
import pets.storage


class Migration(migrations.Migration):

    dependencies = [
        ('pets', '0012_clinicalphoto_cloudinary_raw_pdf'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clinicalphoto',
            name='image',
            field=models.FileField(blank=True, null=True, storage=pets.storage.ClinicalFileCloudinaryStorage(), upload_to='clinical_files/'),
        ),
        migrations.AddField(
            model_name='clinicalphoto',
            name='pdf_file',
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='clinicalphoto',
            name='pdf_filename',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='clinicalphoto',
            name='pdf_content_type',
            field=models.CharField(blank=True, default='application/pdf', max_length=100),
        ),
    ]
