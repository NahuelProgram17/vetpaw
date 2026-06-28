from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pets', '0008_treatment'),
    ]

    operations = [
        migrations.AddField(
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
                ],
                default='',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='treatment',
            name='next_dose',
            field=models.DateField(blank=True, null=True),
        ),
    ]
