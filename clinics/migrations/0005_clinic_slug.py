from django.db import migrations
from django.utils.text import slugify


def add_slug_and_populate(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        # Limpiar restos de intentos anteriores
        cursor.execute("DROP INDEX IF EXISTS clinics_clinic_slug_1cc9c220_like;")
        cursor.execute("DROP INDEX IF EXISTS clinics_clinic_slug_key;")
        cursor.execute("ALTER TABLE clinics_clinic DROP COLUMN IF EXISTS slug;")

        # Agregar columna
        cursor.execute("ALTER TABLE clinics_clinic ADD COLUMN slug VARCHAR(255) NOT NULL DEFAULT '';")

        # Obtener todas las clínicas
        cursor.execute("SELECT id, name FROM clinics_clinic;")
        clinics = cursor.fetchall()

        # Generar y guardar slugs con SQL puro
        for clinic_id, name in clinics:
            base_slug = slugify(name)
            slug = base_slug
            counter = 1
            while True:
                cursor.execute("SELECT COUNT(*) FROM clinics_clinic WHERE slug = %s AND id != %s;", [slug, clinic_id])
                if cursor.fetchone()[0] == 0:
                    break
                slug = f"{base_slug}-{counter}"
                counter += 1
            cursor.execute("UPDATE clinics_clinic SET slug = %s WHERE id = %s;", [slug, clinic_id])

        # Crear índice único
        cursor.execute("CREATE UNIQUE INDEX clinics_clinic_slug_key ON clinics_clinic (slug);")


def reverse_slug(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS clinics_clinic_slug_key;")
        cursor.execute("ALTER TABLE clinics_clinic DROP COLUMN IF EXISTS slug;")


class Migration(migrations.Migration):

    dependencies = [
        ('clinics', '0004_clinic_latitude_clinic_longitude'),
    ]

    operations = [
        migrations.RunPython(add_slug_and_populate, reverse_slug),
    ]