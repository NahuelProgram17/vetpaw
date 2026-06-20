from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pets', '0007_alter_clinicalphoto_caption_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Treatment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('treatment_type', models.CharField(choices=[('deworming', 'Desparasitación'), ('flea', 'Pastilla antipulgas'), ('pipette', 'Pipeta')], max_length=20)),
                ('date_applied', models.DateField()),
                ('product', models.CharField(blank=True, max_length=120)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('pet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='treatments', to='pets.pet')),
            ],
            options={
                'ordering': ['-date_applied'],
            },
        ),
    ]
