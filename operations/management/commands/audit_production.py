from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = 'Audita configuración, base de datos y migraciones de producción sin mostrar secretos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-database',
            action='store_true',
            help='Omite conexión y revisión de migraciones.',
        )
        parser.add_argument(
            '--strict',
            action='store_true',
            help='Trata las advertencias como errores.',
        )

    def handle(self, *args, **options):
        findings = defaultdict(list)

        def error(message):
            findings['ERROR'].append(message)

        def warning(message):
            findings['WARNING'].append(message)

        def ok(message):
            findings['OK'].append(message)

        if settings.DEBUG:
            error('DEBUG debe estar en False en producción.')
        else:
            ok('DEBUG está desactivado.')

        secret_key = getattr(settings, 'SECRET_KEY', '')
        if len(secret_key) < 50 or 'insecure' in secret_key.lower():
            error('SECRET_KEY es demasiado corta o insegura.')
        else:
            ok('SECRET_KEY está configurada (valor oculto).')

        allowed_hosts = list(getattr(settings, 'ALLOWED_HOSTS', []))
        if not allowed_hosts or '*' in allowed_hosts:
            error('ALLOWED_HOSTS debe ser explícito y no usar *.')
        else:
            ok(f'ALLOWED_HOSTS tiene {len(allowed_hosts)} host(s) explícito(s).')

        cors_origins = list(getattr(settings, 'CORS_ALLOWED_ORIGINS', []))
        if not cors_origins:
            error('CORS_ALLOWED_ORIGINS está vacío.')
        elif any(not origin.startswith('https://') for origin in cors_origins):
            warning('Hay orígenes CORS que no usan HTTPS.')
        else:
            ok(f'CORS restringido a {len(cors_origins)} origen(es) HTTPS.')

        if getattr(settings, 'SESSION_COOKIE_SECURE', False):
            ok('SESSION_COOKIE_SECURE está activo.')
        else:
            error('SESSION_COOKIE_SECURE debe estar activo en producción.')

        if getattr(settings, 'CSRF_COOKIE_SECURE', False):
            ok('CSRF_COOKIE_SECURE está activo.')
        else:
            error('CSRF_COOKIE_SECURE debe estar activo en producción.')

        if getattr(settings, 'SECURE_PROXY_SSL_HEADER', None):
            ok('El proxy HTTPS está configurado.')
        else:
            warning('SECURE_PROXY_SSL_HEADER no está configurado.')

        if getattr(settings, 'SECURE_HSTS_SECONDS', 0) <= 0:
            warning('HSTS está desactivado. Activarlo gradualmente después de verificar HTTPS.')
        else:
            ok('HSTS está activo.')

        email_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        if email_password:
            ok('Resend está configurado (valor oculto).')
        else:
            error('Falta RESEND_API_KEY.')

        cloudinary = getattr(settings, 'CLOUDINARY_STORAGE', {})
        missing_cloudinary = [
            key for key in ('CLOUD_NAME', 'API_KEY', 'API_SECRET')
            if not cloudinary.get(key)
        ]
        if missing_cloudinary:
            error('Faltan variables de Cloudinary: ' + ', '.join(missing_cloudinary))
        else:
            ok('Cloudinary está configurado (valores ocultos).')

        vapid_missing = [
            name for name in ('VAPID_PUBLIC_KEY', 'VAPID_PRIVATE_KEY', 'VAPID_SUBJECT')
            if not getattr(settings, name, '')
        ]
        if vapid_missing:
            warning('Push no está completo; faltan: ' + ', '.join(vapid_missing))
        else:
            ok('Notificaciones push VAPID configuradas (valores ocultos).')

        if not options['skip_database']:
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT 1')
                    cursor.fetchone()
                ok('Conexión a la base de datos correcta.')

                executor = MigrationExecutor(connection)
                pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
                if pending:
                    error(f'Hay {len(pending)} migración(es) pendiente(s).')
                else:
                    ok('No hay migraciones pendientes.')
            except Exception as exc:
                error(f'No se pudo auditar la base de datos: {type(exc).__name__}.')
        else:
            warning('La base de datos no fue revisada (--skip-database).')

        for level in ('OK', 'WARNING', 'ERROR'):
            style = {
                'OK': self.style.SUCCESS,
                'WARNING': self.style.WARNING,
                'ERROR': self.style.ERROR,
            }[level]
            for message in findings[level]:
                self.stdout.write(style(f'[{level}] {message}'))

        errors = len(findings['ERROR'])
        warnings = len(findings['WARNING'])
        self.stdout.write(f'Resumen: {errors} error(es), {warnings} advertencia(s).')

        if errors or (options['strict'] and warnings):
            raise CommandError('La auditoría de producción requiere atención.')

        self.stdout.write(self.style.SUCCESS('Auditoría de producción aprobada.'))
