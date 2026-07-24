release: python manage.py migrate --noinput
web: gunicorn vetpaw.wsgi:application --access-logfile - --error-logfile - --capture-output --timeout 120 --graceful-timeout 30 --keep-alive 5
