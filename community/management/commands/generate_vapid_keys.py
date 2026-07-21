import base64

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from django.core.management.base import BaseCommand


def _b64url(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


class Command(BaseCommand):
    help = 'Genera un par de claves VAPID para notificaciones Web Push.'

    def handle(self, *args, **options):
        private_key = ec.generate_private_key(ec.SECP256R1())
        private_value = private_key.private_numbers().private_value.to_bytes(32, 'big')
        public_value = private_key.public_key().public_bytes(
            Encoding.X962,
            PublicFormat.UncompressedPoint,
        )

        self.stdout.write(self.style.SUCCESS('Claves VAPID generadas.'))
        self.stdout.write('Guardá estas tres variables en Railway:')
        self.stdout.write('')
        self.stdout.write(f'VAPID_PRIVATE_KEY={_b64url(private_value)}')
        self.stdout.write(f'VAPID_PUBLIC_KEY={_b64url(public_value)}')
        self.stdout.write('VAPID_SUBJECT=mailto:vetpaw.app@gmail.com')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            'No subas VAPID_PRIVATE_KEY a GitHub ni la compartas públicamente.'
        ))
