import gzip
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


BACKUP_APP_LABELS = (
    'auth.group',
    'users',
    'pets',
    'clinics',
    'appointments',
    'messaging',
    'lost_pets',
    'contact',
    'ads',
    'blog',
    'community',
    'partners',
    'adoptions',
    'commerce',
)


class Command(BaseCommand):
    help = 'Genera un backup lógico comprimido de los datos propios de VetPaw.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            default='backups',
            help='Carpeta de destino. Por defecto: backups',
        )
        parser.add_argument(
            '--filename',
            help='Nombre opcional del archivo .json.gz.',
        )
        parser.add_argument(
            '--database',
            default='default',
            help='Alias de base de datos de Django. Por defecto: default',
        )

    def handle(self, *args, **options):
        output_dir = Path(options['output_dir']).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = options.get('filename')
        if filename:
            if not filename.endswith('.json.gz'):
                raise CommandError('El nombre debe terminar en .json.gz')
        else:
            stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-utc')
            filename = f'vetpaw-backup-{stamp}.json.gz'

        backup_path = output_dir / filename
        checksum_path = backup_path.with_suffix(backup_path.suffix + '.sha256')

        if backup_path.exists() or checksum_path.exists():
            raise CommandError('El archivo de destino ya existe. Elegí otro nombre.')

        try:
            with gzip.open(backup_path, mode='wt', encoding='utf-8', newline='') as stream:
                call_command(
                    'dumpdata',
                    *BACKUP_APP_LABELS,
                    database=options['database'],
                    format='json',
                    indent=None,
                    use_natural_foreign_keys=True,
                    use_natural_primary_keys=True,
                    stdout=stream,
                    verbosity=0,
                )
        except Exception:
            backup_path.unlink(missing_ok=True)
            raise

        digest = hashlib.sha256()
        with backup_path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)

        checksum_path.write_text(
            f'{digest.hexdigest()}  {backup_path.name}\n',
            encoding='utf-8',
        )

        # Los backups incluyen información privada. En sistemas compatibles,
        # limitamos la lectura al usuario que ejecutó el comando.
        for path in (backup_path, checksum_path):
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass

        self.stdout.write(self.style.SUCCESS('Backup creado y verificado:'))
        self.stdout.write(f'  Datos: {backup_path}')
        self.stdout.write(f'  SHA-256: {checksum_path}')
        self.stdout.write(
            self.style.WARNING(
                'Guardalo fuera de Railway: el disco del servicio puede ser temporal.'
            )
        )
