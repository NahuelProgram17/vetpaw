import secrets


class RequestIDMiddleware:
    """Agrega un identificador seguro a cada solicitud para soporte y diagnóstico."""

    header_name = 'X-Request-ID'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = secrets.token_hex(16)
        response = self.get_response(request)
        response[self.header_name] = request.request_id
        return response
