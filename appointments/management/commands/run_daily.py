from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Corre send_reminders todos los dias y weekly_monitor los lunes'

    def handle(self, *args, **kwargs):
        from django.core.management import call_command

        # Recordatorios — todos los días
        self.stdout.write('Corriendo send_reminders...')
        call_command('send_reminders')

        # Monitor semanal — solo los lunes
        if timezone.now().weekday() == 0:  # 0 = lunes
            self.stdout.write('Es lunes — corriendo weekly_monitor...')
            call_command('weekly_monitor')
        else:
            self.stdout.write('No es lunes — saltando weekly_monitor.')