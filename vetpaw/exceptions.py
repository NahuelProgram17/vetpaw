import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """Conserva los errores habituales de DRF y vuelve seguros los fallos inesperados."""

    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    request = context.get('request')
    request_id = getattr(request, 'request_id', None)
    logger.error(
        'Error inesperado en la API. request_id=%s',
        request_id or 'sin-id',
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    response = Response(
        {
            'error': 'VetPaw tuvo un problema temporal. Intentá nuevamente en unos minutos.',
            'code': 'server_error',
            'request_id': request_id,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    response['Cache-Control'] = 'no-store'
    return response
