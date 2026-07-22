from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('community', '0007_privacy_and_control_stage5')]
    operations = [
        migrations.AlterField(
            model_name='communitynotification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('reaction', 'Patita en publicación'),
                    ('comment', 'Comentario en publicación'),
                    ('follow', 'Nuevo seguidor'),
                    ('comment_reaction', 'Patita en comentario'),
                    ('reply', 'Respuesta a comentario'),
                    ('mention', 'Mención'),
                    ('follow_request', 'Solicitud de seguimiento'),
                    ('business_inquiry', 'Consulta comercial'),
                    ('business_reservation', 'Nueva reserva comercial'),
                    ('business_reservation_update', 'Actualización de reserva comercial'),
                ],
                max_length=32,
            ),
        ),
    ]
