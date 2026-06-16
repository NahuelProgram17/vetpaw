# 🐾 VetPaw — Backend API

**Plataforma web que conecta veterinarias con dueños de mascotas.**
Gestión de turnos, fichas médicas, historial clínico, mascotas perdidas y comunicación directa entre profesionales y clientes.

🌐 **App en producción:** [www.vetpaw.com.ar](https://www.vetpaw.com.ar)
📂 **Frontend repo:** [vetpaw-frontend](https://github.com/NahuelProgram17/vetpaw-frontend)

---

## Stack

- **Python 3.12** + **Django 5.2** + **Django REST Framework**
- **PostgreSQL** (Railway)
- **JWT** (SimpleJWT) para autenticación
- **Cloudinary** para almacenamiento de imágenes
- **APScheduler** para recordatorios automáticos por email (turnos y vacunas)
- **Whitenoise** para archivos estáticos
- **Gunicorn** como servidor WSGI
- **Railway** para deploy

## Funcionalidades

- Registro y login con roles diferenciados (dueño / veterinario / clínica)
- CRUD completo de mascotas con foto (upload a Cloudinary)
- Sistema de turnos: solicitud, confirmación, cancelación
- Ficha médica y historial de visitas por mascota
- Recordatorios automáticos por email de turnos y vacunas próximas
- Reportes de mascotas perdidas
- Mensajería interna entre dueños y veterinarios
- Panel de administración Django
- Formulario de contacto y solicitud para sumar veterinarias

## Estructura del proyecto

```
vetpaw/
├── vetpaw/          # Configuración principal (settings, urls, wsgi)
├── users/           # Registro, login, perfiles, roles
├── pets/            # Mascotas, fichas médicas, historial
├── clinics/         # Clínicas y veterinarios
├── appointments/    # Turnos y agenda
├── messages_app/    # Mensajería interna
├── lost_pets/       # Reportes de mascotas perdidas
├── contact/         # Formulario de contacto
├── manage.py
├── requirements.txt
└── Procfile
```

## Instalación local

```bash
# Clonar el repositorio
git clone https://github.com/NahuelProgram17/vetpaw.git
cd vetpaw

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno (.env)
# DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT
# CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
# SECRET_KEY, DEBUG=True

# Migraciones y servidor
python manage.py migrate
python manage.py runserver
```

## API Endpoints principales

| Recurso | Método | Endpoint |
|---------|--------|----------|
| Registro | POST | `/api/users/register/` |
| Login (JWT) | POST | `/api/users/token/` |
| Mascotas | GET/POST | `/api/pets/` |
| Turnos | GET/POST | `/api/appointments/` |
| Clínicas | GET | `/api/clinics/` |
| Mensajes | GET/POST | `/api/messages/` |
| Mascotas perdidas | GET/POST | `/api/lost-pets/` |

## Deploy

El backend corre en **Railway** con PostgreSQL y se conecta al frontend en Vercel.
Variables de entorno configuradas en el dashboard de Railway.

## Autor

**Nahuel Pedreyra**
📧 vetpaw.app@gmail.com
🔗 [LinkedIn](https://www.linkedin.com/in/nahuelprogram17/)
💻 [GitHub](https://github.com/NahuelProgram17)
