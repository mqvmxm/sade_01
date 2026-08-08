# IMPORTANTE: --workers 1 es intencional, NO un descuido de configuración
# -- no lo "corrijas" a más workers. El motor de monitoreo asíncrono
# (APScheduler, ver app/__init__.py:_iniciar_scheduler) corre embebido
# dentro del mismo proceso de la app, sin coordinación entre procesos. Con
# más de un worker de gunicorn, cada uno arrancaría su propia copia del
# scheduler y el chequeo periódico de viajes (cada 60s) se duplicaría (o
# triplicaría, etc.) por worker: alertas repetidas y notificaciones de
# WhatsApp/SMS duplicadas a conductores y administrador. Si en el futuro
# hace falta más capacidad, hay que sacar el scheduler a un proceso/worker
# separado (o a un servicio como Render Cron Jobs) antes de subir
# --workers por encima de 1.
web: gunicorn wsgi:app --workers 1
