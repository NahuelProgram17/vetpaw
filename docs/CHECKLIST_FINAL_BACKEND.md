# Checklist final del backend

## Código

- [ ] `check` sin problemas.
- [ ] No hay migraciones sin crear.
- [ ] Todos los tests pasan.
- [ ] `git diff --check` no informa errores.
- [ ] `.env` no aparece en `git status`.

## Railway

- [ ] Deploy activo.
- [ ] Migraciones ejecutadas.
- [ ] `/api/health/` responde `200`.
- [ ] Logs sin errores repetidos.
- [ ] `audit_production` aprobado o con advertencias conocidas.

## Servicios

- [ ] PostgreSQL accesible.
- [ ] Cloudinary carga imágenes.
- [ ] Resend envía correos.
- [ ] VAPID envía notificaciones push.
- [ ] GitHub Actions ejecuta recordatorios una sola vez por hora.

## Recuperación

- [ ] Backup `.json.gz` creado.
- [ ] Archivo `.sha256` guardado.
- [ ] `verify_vetpaw_backup` aprobado.
- [ ] Copia almacenada fuera de Railway.
- [ ] Restauración probada en una base separada.
