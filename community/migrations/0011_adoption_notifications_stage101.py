from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('adoptions', '0001_initial'),
        ('community', '0010_clinic_content_stage81'),
    ]

    operations = [
        migrations.AddField(
            model_name='communitynotification',
            name='adoption_animal',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='community_notifications',
                to='adoptions.adoptionanimal',
            ),
        ),
        migrations.AddField(
            model_name='communitynotification',
            name='adoption_application',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='community_notifications',
                to='adoptions.adoptionapplication',
            ),
        ),
        migrations.AddField(
            model_name='communitynotification',
            name='help_offer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='community_notifications',
                to='adoptions.helpoffer',
            ),
        ),
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
                    ('clinic_appointment', 'Nueva solicitud de turno veterinario'),
                    ('clinic_appointment_update', 'Actualización de turno veterinario'),
                    ('adoption_application', 'Nueva solicitud de adopción'),
                    ('adoption_help_offer', 'Nuevo ofrecimiento de ayuda'),
                    ('adoption_application_update', 'Actualización de solicitud de adopción'),
                ],
                max_length=32,
            ),
        ),
        migrations.AddConstraint(
            model_name='communitynotification',
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ('adoption_application__isnull', False),
                    ('notification_type', 'adoption_application'),
                ),
                fields=('recipient', 'actor', 'adoption_application', 'notification_type'),
                name='unique_adoption_application_notification',
            ),
        ),
        migrations.AddConstraint(
            model_name='communitynotification',
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ('help_offer__isnull', False),
                    ('notification_type', 'adoption_help_offer'),
                ),
                fields=('recipient', 'actor', 'help_offer', 'notification_type'),
                name='unique_adoption_help_offer_notification',
            ),
        ),
    ]
