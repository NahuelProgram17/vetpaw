from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0009_create_vetpaw_permission_groups')]
    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('owner', 'Dueño de mascota'),
                    ('clinic', 'Veterinario/a'),
                    ('business', 'Negocio de mascotas'),
                    ('shelter', 'Refugio o rescatista'),
                ],
                default='owner',
                max_length=10,
            ),
        ),
    ]
