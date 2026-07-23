from django.db import migrations, models


def normalize_clinic_content(apps, schema_editor):
    Post = apps.get_model('community', 'Post')
    Post.objects.filter(clinic_content_type__in=['availability', 'guard']).update(
        clinic_content_type='notice'
    )


class Migration(migrations.Migration):
    dependencies = [
        ('community', '0009_clinic_community_stage8'),
        ('clinics', '0017_clinic_plan_stage81'),
    ]

    operations = [
        migrations.RunPython(normalize_clinic_content, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='post',
            name='clinic_content_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('health_tip', 'Consejo veterinario'),
                    ('campaign', 'Campaña o evento'),
                    ('notice', 'Aviso importante'),
                    ('service', 'Servicio veterinario'),
                ],
                default='',
                max_length=24,
            ),
        ),
    ]
