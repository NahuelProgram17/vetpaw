# Variables de entorno del backend

Usar `.env.example` como plantilla. Los valores reales se guardan únicamente
en Railway, GitHub Secrets o el `.env` local ignorado por Git.

## Obligatorias

| Variable | Uso |
|---|---|
| `SECRET_KEY` | Firma y seguridad interna de Django. |
| `DEBUG` | Debe ser `False` en producción. |
| `ALLOWED_HOSTS` | Hosts autorizados para la API. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL. |
| `RESEND_API_KEY` | Envío de correos. |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Imágenes y archivos. |
| `CORS_ALLOWED_ORIGINS` | Frontends que pueden llamar a la API. |
| `CSRF_TRUSTED_ORIGINS` | Orígenes HTTPS confiables. |

## Push

| Variable | Uso |
|---|---|
| `VAPID_PUBLIC_KEY` | Clave pública usada también por el frontend. |
| `VAPID_PRIVATE_KEY` | Clave privada; nunca debe ir al frontend. |
| `VAPID_SUBJECT` | Contacto del servicio push. |
| `WEB_PUSH_TTL` | Duración máxima de una notificación. |
| `WEB_PUSH_TIMEOUT` | Tiempo máximo de envío. |

## Operación y seguridad

| Variable | Valor inicial recomendado |
|---|---|
| `DB_CONN_MAX_AGE` | `60` |
| `SESSION_COOKIE_SECURE` | `True` |
| `CSRF_COOKIE_SECURE` | `True` |
| `SECURE_SSL_REDIRECT` | `False` hasta confirmar el proxy; luego puede activarse. |
| `SECURE_HSTS_SECONDS` | `0` inicialmente; activar de forma gradual. |
| `LOG_LEVEL` | `INFO` |

## GitHub Actions para recordatorios

Crear estos Secrets en el repositorio del backend:

- `SECRET_KEY`
- `DB_PASSWORD`
- `RESEND_API_KEY`

Crear estas variables del repositorio cuando cambien los valores de Railway:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DEFAULT_FROM_EMAIL`

El workflow conserva valores de respaldo para no interrumpir los recordatorios.
La contraseña siempre permanece en GitHub Secrets.
