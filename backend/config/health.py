"""Health check for the load balancer and the container orchestrator."""
from django.db import connection
from django.http import JsonResponse


def health(request):
    try:
        connection.ensure_connection()
        connection.connection.admin.command('ping')  # a real round trip to MongoDB
        database = 'ok'
    except Exception:  # Any database failure makes the service unhealthy.
        database = 'indisponible'
    status = 200 if database == 'ok' else 503
    return JsonResponse({'status': 'ok' if status == 200 else 'degraded', 'database': database}, status=status)
