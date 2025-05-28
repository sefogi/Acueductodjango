from django.db import transaction
from .models import ConfiguracionGlobal

def obtener_siguiente_numero_factura():
    with transaction.atomic():
        config, created = ConfiguracionGlobal.objects.select_for_update().get_or_create(clave='main')
        # Optional: Initialize to a specific starting number if 'created' is True and you want a higher start
        # if created and config.ultimo_numero_factura == 0:
        #     config.ultimo_numero_factura = 1000 # Example starting number
        config.ultimo_numero_factura += 1
        config.save()
        return config.ultimo_numero_factura
