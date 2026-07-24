# VetPaw — Producción, backups y recuperación

Esta guía es el procedimiento oficial para mantener el backend sin depender de
la memoria de una persona.

## 1. Antes de cada deploy

En Windows, dentro del backend:

```powershell
python manage.py check --settings=vetpaw.test_settings
python manage.py makemigrations --check --dry-run --settings=vetpaw.test_settings
python manage.py test users partners community commerce adoptions lost_pets pets clinics appointments messaging contact operations --settings=vetpaw.test_settings
```

Revisar después:

```powershell
git status
git diff --check
```

No subir `.env`, bases SQLite, carpetas `backups`, `venv` ni archivos con
credenciales.

## 2. Después del deploy en Railway

Comprobar en este orden:

1. El deploy aparece activo.
2. `GET /api/health/` responde `200` con `status: ok` y `database: ok`.
3. Abrir login desde el frontend.
4. Crear o leer una publicación de prueba.
5. Revisar los logs de Railway por errores nuevos.
6. Ante un error de usuario, buscar su valor `X-Request-ID`.

Ejecutar en el entorno de producción:

```powershell
python manage.py audit_production
```

La auditoría no imprime secretos. Si informa HSTS desactivado, eso es una
advertencia controlada hasta que HTTPS haya sido probado durante varios días.

## 3. Backups de la base de datos

Crear un backup lógico:

```powershell
python manage.py backup_vetpaw --output-dir backups
```

Se generan dos archivos:

```text
vetpaw-backup-FECHA.json.gz
vetpaw-backup-FECHA.json.gz.sha256
```

Verificarlo inmediatamente:

```powershell
python manage.py verify_vetpaw_backup backups\vetpaw-backup-FECHA.json.gz
```

### Reglas

- Guardar ambos archivos fuera de Railway.
- Conservar al menos una copia en dos ubicaciones diferentes.
- No enviar backups por WhatsApp ni subirlos a repositorios.
- El backup contiene usuarios, correos, mensajes e información privada.
- Probar periódicamente la restauración en una base separada.

### Imágenes y documentos

El backup lógico conserva las referencias guardadas en PostgreSQL, pero no
copia los archivos binarios alojados en Cloudinary. La cuenta de Cloudinary y
sus credenciales deben mantenerse activas y protegidas.

## 4. Restauración segura

Nunca probar una restauración directamente sobre la base de producción.

Procedimiento:

1. Crear una base PostgreSQL temporal o de prueba.
2. Configurar un `.env` que apunte únicamente a esa base.
3. Ejecutar:

```powershell
python manage.py migrate
python manage.py loaddata backups\vetpaw-backup-FECHA.json.gz
python manage.py check
python manage.py audit_production
```

4. Iniciar la API y verificar usuarios, mascotas, publicaciones, turnos y
   mensajes.
5. Recién después decidir una recuperación de producción.

Las migraciones recrean los grupos administrativos oficiales antes de cargar
los usuarios. El backup también conserva los grupos adicionales existentes.

## 5. Recordatorios automáticos

La fuente oficial de ejecución es:

```text
.github/workflows/send_reminders.yml
```

Corre una vez por hora y tiene control de concurrencia para evitar dos
instancias simultáneas. Las credenciales de PostgreSQL se leen desde GitHub
Secrets.

Los mensajes sin leer poseen `unread_reminder_sent`; después de un correo
exitoso quedan marcados y no se vuelven a enviar cada hora.

## 6. Incidentes

### Railway no responde

1. Revisar `/api/health/`.
2. Revisar el deploy y los logs.
3. Buscar errores de conexión a PostgreSQL.
4. No cambiar varias variables al mismo tiempo.
5. Volver al último commit estable si el fallo comenzó tras un deploy.

### Base de datos no disponible

1. No ejecutar `flush` ni borrar migraciones.
2. Confirmar host, puerto y estado de PostgreSQL.
3. Verificar el backup más reciente.
4. Recuperar primero en una base temporal.

### Imágenes no cargan

1. Revisar las tres variables de Cloudinary.
2. No volver a subir archivos masivamente.
3. Confirmar que las URLs almacenadas sigan accesibles.

### Correos no salen

1. Revisar `RESEND_API_KEY` y `DEFAULT_FROM_EMAIL`.
2. Ejecutar manualmente `python manage.py send_reminders` una sola vez.
3. Revisar el historial de GitHub Actions.

## 7. Frecuencia operativa recomendada

- Antes de cada deploy: tests completos.
- Semanalmente: revisar `/api/health/` y errores de Railway.
- Semanalmente durante el crecimiento inicial: backup verificado.
- Antes de cambios grandes: backup adicional.
- Mensualmente: prueba de restauración en una base separada.
- Cuando se cambie una credencial: actualizar Railway y GitHub Secrets.
