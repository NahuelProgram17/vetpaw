from django.http import JsonResponse
from django.views import defaults


def _is_api_request(request):
    return request.path.startswith('/api/')


def api_not_found(request, exception):
    if not _is_api_request(request):
        return defaults.page_not_found(request, exception)

    response = JsonResponse(
        {
            'error': 'No encontramos el recurso solicitado.',
            'code': 'not_found',
            'request_id': getattr(request, 'request_id', None),
        },
        status=404,
    )
    response['Cache-Control'] = 'no-store'
    return response


def api_server_error(request):
    if not _is_api_request(request):
        return defaults.server_error(request)

    response = JsonResponse(
        {
            'error': 'VetPaw tuvo un problema temporal. Intentá nuevamente en unos minutos.',
            'code': 'server_error',
            'request_id': getattr(request, 'request_id', None),
        },
        status=500,
    )
    response['Cache-Control'] = 'no-store'
    return response
