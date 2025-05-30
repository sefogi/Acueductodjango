from io import BytesIO
import zipfile
from datetime import datetime
import os
import json # Added for json.loads in one of the moved functions

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone # For finalizar_ruta_service
from django.db.models import Q # May be needed by moved logic

from .models import UserAcueducto, Ruta, OrdenRuta, HistoricoLectura
from . import utils # For PDF generation, formatear_fecha_espanol

# Placeholder for service functions to be added

def generar_zip_todas_facturas_service(periodo_inicio_str: str, periodo_fin_str: str) -> BytesIO:
    """Genera un archivo ZIP con todas las facturas para el período dado."""
    if not periodo_inicio_str or not periodo_fin_str:
        raise ValueError('Por favor, especifique el período de facturación')

    periodo_inicio_fecha = datetime.strptime(periodo_inicio_str, '%Y-%m-%d')
    periodo_fin_fecha = datetime.strptime(periodo_fin_str, '%Y-%m-%d')
    periodo_facturacion = f"Del {utils.formatear_fecha_espanol(periodo_inicio_fecha)} al {utils.formatear_fecha_espanol(periodo_fin_fecha)}"

    zip_buffer = BytesIO()
    # Ensure settings.BASE_DIR is Path object or string for correct path joining
    base_url = os.path.join(str(settings.BASE_DIR), 'acueducto', 'static') # Use os.path.join for robustness

    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        for usuario in UserAcueducto.objects.all():
            try:
                # Assuming utils.generar_pdf_factura returns a temporary file object (like NamedTemporaryFile)
                pdf_file_obj = utils.generar_pdf_factura(
                    usuario=usuario,
                    fecha_emision=datetime.now(), # Consider making this configurable or using timezone.now()
                    periodo_facturacion=periodo_facturacion,
                    base_url=base_url
                )

                with open(pdf_file_obj.name, 'rb') as pdf_content_file:
                    zip_file.writestr(f'factura_{usuario.contrato}.pdf', pdf_content_file.read())

                os.unlink(pdf_file_obj.name) # Clean up the temporary PDF file
            except Exception as e:
                # Consider logging the error or handling it more gracefully
                raise Exception(f'Error al generar factura para {usuario.contrato}: {str(e)}')

    zip_buffer.seek(0) # Reset buffer position to the beginning before reading
    return zip_buffer

def crear_nueva_ruta_service(nombre_ruta: str, usuarios_orden_data: list) -> Ruta:
    """
    Crea una nueva ruta de lectura.
    Elimina todas las rutas existentes antes de crear una nueva.
    """
    if not nombre_ruta or not usuarios_orden_data:
        raise ValueError("Nombre de ruta y usuarios son requeridos para crear la ruta.") # Or handle as a more specific exception

    # Eliminar todas las rutas existentes antes de crear una nueva
    Ruta.objects.all().delete() # Consider if this is truly desired, or if routes should be deactivated/archived.
                                # For now, matching existing logic.

    # Crear la nueva ruta
    nueva_ruta = Ruta.objects.create(nombre=nombre_ruta)

    for usuario_data in usuarios_orden_data:
        OrdenRuta.objects.create(
            ruta=nueva_ruta,
            usuario_id=usuario_data['id'], # Assuming 'id' is passed in usuario_data
            orden=usuario_data['orden']    # Assuming 'orden' is passed
        )

    return nueva_ruta

def finalizar_ruta_service(ruta_id: int) -> tuple[bool, str, Ruta | None]:
    """
    Finaliza una ruta de lectura.
    Verifica que todas las lecturas estén tomadas antes de finalizar.
    """
    ruta = get_object_or_404(Ruta, id=ruta_id)

    # Verificar que todas las lecturas estén tomadas
    lecturas_pendientes = ruta.ordenruta_set.filter(lectura_tomada=False).exists()
    if lecturas_pendientes:
        return False, 'No se puede finalizar la ruta. Hay lecturas pendientes.', ruta

    # Marcar la ruta como finalizada
    ruta.activa = False
    ruta.fecha_finalizacion = timezone.now()
    ruta.save()

    return True, 'Ruta finalizada exitosamente', ruta
