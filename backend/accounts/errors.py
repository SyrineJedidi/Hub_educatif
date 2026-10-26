from django.http import JsonResponse
from rest_framework.views import exception_handler as drf_handler


def csrf_failure(request, reason=''):
    return JsonResponse({'error': {'code': 'csrf_failed', 'message': 'Protection CSRF : rechargez la page puis réessayez.', 'fields': {}}}, status=403)


def exception_handler(exc, context):
    response = drf_handler(exc, context)
    if response is not None:
        data = response.data
        message = data.get('detail', 'Veuillez corriger les champs indiqués.') if isinstance(data, dict) else 'Requête invalide.'
        fields = {k: v for k, v in data.items() if k != 'detail'} if isinstance(data, dict) else {}
        response.data = {'error': {'code': getattr(exc, 'default_code', 'invalid'), 'message': str(message), 'fields': fields}}
    return response


def not_found(request, exception=None):
    return JsonResponse({'error': {'code': 'not_found', 'message': 'Ressource introuvable.', 'fields': {}}}, status=404)


def server_error(request):
    return JsonResponse({'error': {'code': 'server_error', 'message': 'Le serveur ne peut pas traiter la demande. Réessayez plus tard.', 'fields': {}}}, status=500)


def bad_request(request, exception=None):
    return JsonResponse({'error': {'code': 'bad_request', 'message': 'Requête invalide ou trop volumineuse.', 'fields': {}}}, status=400)
