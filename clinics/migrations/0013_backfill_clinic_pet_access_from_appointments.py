from django.db import migrations


def backfill_clinic_pet_access(apps, schema_editor):
    Appointment = apps.get_model('appointments', 'Appointment')
    ClinicPetAccess = apps.get_model('clinics', 'ClinicPetAccess')

    appointments = (
        Appointment.objects
        .filter(pet__isnull=False, clinic__isnull=False)
        .exclude(status='cancelled')
        .order_by('clinic_id', 'pet_id', '-requested_date')
    )

    seen = set()
    to_create = []
    for appt in appointments:
        key = (appt.clinic_id, appt.pet_id)
        if key in seen:
            continue
        seen.add(key)

        exists = ClinicPetAccess.objects.filter(
            clinic_id=appt.clinic_id,
            pet_id=appt.pet_id,
        ).exists()
        if not exists:
            to_create.append(ClinicPetAccess(
                clinic_id=appt.clinic_id,
                pet_id=appt.pet_id,
                last_appointment=appt.requested_date,
            ))

    if to_create:
        ClinicPetAccess.objects.bulk_create(to_create, ignore_conflicts=True)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('clinics', '0012_clinic_slug'),
        ('appointments', '0010_appointment_seen_by_clinic'),
    ]

    operations = [
        migrations.RunPython(backfill_clinic_pet_access, reverse_noop),
    ]
