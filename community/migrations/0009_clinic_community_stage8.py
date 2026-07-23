from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0010_appointment_seen_by_clinic'),
        ('clinics', '0016_cliniccampaign'),
        ('community', '0008_business_notifications_stage7'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='clinic_content_type',
            field=models.CharField(blank=True, choices=[('health_tip', 'Consejo veterinario'), ('campaign', 'Campaña o evento'), ('availability', 'Turnos disponibles'), ('guard', 'Guardia y horarios'), ('service', 'Servicio veterinario'), ('notice', 'Aviso importante')], default='', max_length=24),
        ),
        migrations.AddField(
            model_name='post',
            name='related_clinic_campaign',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='community_post', to='clinics.cliniccampaign'),
        ),
        migrations.AddField(
            model_name='communitynotification',
            name='appointment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='community_notifications', to='appointments.appointment'),
        ),
        migrations.AlterField(
            model_name='communitynotification',
            name='notification_type',
            field=models.CharField(choices=[('reaction', 'Patita en publicación'), ('comment', 'Comentario en publicación'), ('follow', 'Nuevo seguidor'), ('comment_reaction', 'Patita en comentario'), ('reply', 'Respuesta a comentario'), ('mention', 'Mención'), ('follow_request', 'Solicitud de seguimiento'), ('business_inquiry', 'Consulta comercial'), ('business_reservation', 'Nueva reserva comercial'), ('business_reservation_update', 'Actualización de reserva comercial'), ('clinic_appointment', 'Nueva solicitud de turno veterinario'), ('clinic_appointment_update', 'Actualización de turno veterinario')], max_length=32),
        ),
    ]
