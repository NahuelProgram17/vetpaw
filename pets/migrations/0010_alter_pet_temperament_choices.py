# Generated manually to add new pet temperament choices.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pets', '0009_pet_temperament_treatment_next_dose'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pet',
            name='temperament',
            field=models.CharField(
                blank=True,
                choices=[
                    ('friendly', 'Amigable'),
                    ('shy', 'Tímido'),
                    ('nervous', 'Nervioso'),
                    ('protective', 'Protector'),
                    ('playful', 'Juguetón'),
                    ('sleepy', 'Dormilón'),
                    ('eater', 'Comilón'),
                    ('intimidating', 'Intimidante'),
                ],
                default='',
                max_length=20,
            ),
        ),
    ]
