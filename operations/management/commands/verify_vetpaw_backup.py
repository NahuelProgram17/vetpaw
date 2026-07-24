import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Verifica integridad, checksum y estructura de un backup de VetPaw.'

    def add_arguments(self, parser):
        parser.add_argument('backup_path', help='Ruta al archivo .json.gz')

    def handle(self, *args, **options):
        backup_path = Path(options['backup_path']).expanduser().resolve()
        checksum_path = backup_path.with_suffix(backup_path.suffix + '.sha256')

        if not backup_path.is_file():
            raise CommandError(f'No existe el backup: {backup_path}')
        if not backup_path.name.endswith('.json.gz'):
            raise CommandError('El backup debe terminar en .json.gz')

        digest = hashlib.sha256()
        with backup_path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        actual_hash = digest.hexdigest()

        if checksum_path.exists():
            checksum_text = checksum_path.read_text(encoding='utf-8').strip()
            expected_hash = checksum_text.split(maxsplit=1)[0] if checksum_text else ''
            if expected_hash != actual_hash:
                raise CommandError('El checksum SHA-256 no coincide. El backup puede estar dañado.')
        else:
            self.stdout.write(
                self.style.WARNING('No se encontró el archivo .sha256; se validará solo el contenido.')
            )

        try:
            with gzip.open(backup_path, mode='rt', encoding='utf-8') as stream:
                payload = json.load(stream)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CommandError(f'No se pudo leer el backup: {exc}') from exc

        if not isinstance(payload, list):
            raise CommandError('La estructura del backup no es una lista de objetos Django.')

        model_counts = Counter()
        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                raise CommandError(f'Objeto inválido en la posición {index}.')
            # Cuando dumpdata usa claves primarias naturales, Django puede
            # omitir ``pk`` de forma válida. Para restaurar el fixture solo son
            # obligatorios el modelo y sus campos.
            if not {'model', 'fields'}.issubset(item):
                raise CommandError(f'Objeto incompleto en la posición {index}.')
            if not isinstance(item['model'], str) or not item['model'].strip():
                raise CommandError(f'Modelo inválido en la posición {index}.')
            if not isinstance(item['fields'], dict):
                raise CommandError(f'Campos inválidos en la posición {index}.')
            model_counts[item['model']] += 1

        self.stdout.write(self.style.SUCCESS('Backup válido.'))
        self.stdout.write(f'  Archivo: {backup_path}')
        self.stdout.write(f'  SHA-256: {actual_hash}')
        self.stdout.write(f'  Objetos: {len(payload)}')
        self.stdout.write(f'  Modelos: {len(model_counts)}')
