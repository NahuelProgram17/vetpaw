from django.db import DatabaseError, connection
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


def _health_payload(request, *, service_status, database_status):
    return {
        'status': service_status,
        'service': 'vetpaw-api',
        'database': database_status,
        'timestamp': timezone.now().isoformat(),
        'request_id': getattr(request, 'request_id', None),
    }


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def health_check(request):
    """Comprueba que la API y su base de datos estén disponibles."""

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except DatabaseError:
        response = Response(
            _health_payload(
                request,
                service_status='degraded',
                database_status='unavailable',
            ),
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        response['Retry-After'] = '30'
    else:
        response = Response(
            _health_payload(
                request,
                service_status='ok',
                database_status='ok',
            ),
            status=status.HTTP_200_OK,
        )

    response['Cache-Control'] = 'no-store'
    return response
