# VetPaw — Backend API

Backend de la plataforma VetPaw: comunidad de mascotas, turnos veterinarios,
historial clínico, mensajería, adopciones, mascotas perdidas, perfiles
profesionales, negocios y moderación.

- Producción: `https://www.vetpaw.com.ar`
- API de estado: `/api/health/`
- Documentación Swagger: `/api/docs/`

## Tecnología

- Python 3.13 / Django 5.2 / Django REST Framework
- PostgreSQL en Railway
- JWT con SimpleJWT
- Cloudinary para imágenes y archivos
- Resend para correos
- Web Push con VAPID
- Gunicorn y Whitenoise

## Instalación local

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Nunca subas `.env`, backups ni credenciales a GitHub.

## Validación

```powershell
python manage.py check --settings=vetpaw.test_settings
python manage.py makemigrations --check --dry-run --settings=vetpaw.test_settings
python manage.py test users partners community commerce adoptions lost_pets pets clinics appointments messaging contact operations --settings=vetpaw.test_settings
```

## Auditoría de producción

Desde un entorno que tenga cargadas las variables reales:

```powershell
python manage.py audit_production
```

La auditoría revisa configuración segura, conexión a PostgreSQL, migraciones,
correo, Cloudinary y notificaciones push sin mostrar valores secretos.

## Backup lógico

```powershell
python manage.py backup_vetpaw --output-dir backups
python manage.py verify_vetpaw_backup backups\vetpaw-backup-FECHA.json.gz
```

El comando genera el `.json.gz` y un archivo `.sha256`. Guardá ambos fuera del
servidor. Las imágenes viven en Cloudinary y deben conservarse también allí.

## Operación

- Railway ejecuta las migraciones antes de iniciar el servidor.
- GitHub Actions ejecuta `send_reminders` una vez por hora.
- Los avisos de mensajes sin leer se marcan para no enviarse repetidamente.
- Los errores de API incluyen `X-Request-ID` para encontrarlos en los logs.

La guía completa está en `docs/PRODUCCION_Y_RECUPERACION.md`.
