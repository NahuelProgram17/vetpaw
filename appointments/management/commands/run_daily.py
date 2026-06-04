from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Corre send_reminders todos los dias'

    def handle(self, *args, **kwargs):
        from django.core.management import call_command

        # Recordatorios — todos los días
        self.stdout.write('Corriendo send_reminders...')
        call_command('send_reminders')