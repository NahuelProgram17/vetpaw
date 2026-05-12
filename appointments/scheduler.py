from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django.conf import settings


def start():
    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_jobstore(DjangoJobStore(), "default")

    from appointments.tasks import send_appointment_reminders, send_vaccine_reminders

    scheduler.add_job(
        send_appointment_reminders,
        trigger='interval',
        hours=1,
        id='send_appointment_reminders',
        replace_existing=True,
    )

    scheduler.add_job(
        send_vaccine_reminders,
        trigger='interval',
        hours=24,
        id='send_vaccine_reminders',
        replace_existing=True,
    )

    scheduler.start()