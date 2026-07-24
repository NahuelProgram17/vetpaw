import gzip
import hashlib
import json
from secrets import token_urlsafe
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from users.models import User


class BackupCommandsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='backup-user',
            email='backup@example.com',
            password=token_urlsafe(24),
            role='owner',
            is_approved=True,
        )

    def test_backup_creates_compressed_data_and_checksum(self):
        with TemporaryDirectory() as temp_dir:
            call_command(
                'backup_vetpaw',
                output_dir=temp_dir,
                filename='test-backup.json.gz',
                verbosity=0,
            )
            backup_path = Path(temp_dir) / 'test-backup.json.gz'
            checksum_path = Path(temp_dir) / 'test-backup.json.gz.sha256'

            self.assertTrue(backup_path.is_file())
            self.assertTrue(checksum_path.is_file())

            with gzip.open(backup_path, 'rt', encoding='utf-8') as stream:
                payload = json.load(stream)
            self.assertTrue(any(item['model'] == 'users.user' for item in payload))

    def test_verify_accepts_a_valid_backup(self):
        with TemporaryDirectory() as temp_dir:
            call_command(
                'backup_vetpaw',
                output_dir=temp_dir,
                filename='valid.json.gz',
                verbosity=0,
            )
            call_command(
                'verify_vetpaw_backup',
                str(Path(temp_dir) / 'valid.json.gz'),
                verbosity=0,
            )

    def test_verify_rejects_a_modified_backup(self):
        with TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / 'modified.json.gz'
            with gzip.open(backup_path, 'wt', encoding='utf-8') as stream:
                json.dump([], stream)

            original_hash = hashlib.sha256(backup_path.read_bytes()).hexdigest()
            checksum_path = Path(str(backup_path) + '.sha256')
            checksum_path.write_text(
                f'{original_hash}  {backup_path.name}\n',
                encoding='utf-8',
            )
            backup_path.write_bytes(backup_path.read_bytes() + b'corruption')

            with self.assertRaises(CommandError):
                call_command('verify_vetpaw_backup', str(backup_path), verbosity=0)
