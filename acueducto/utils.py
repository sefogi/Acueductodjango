from django.conf import settings
from django.template.loader import get_template
from weasyprint import HTML # type: ignore
import tempfile
import os
from django.core.mail import EmailMessage
from .models import UserAcueducto # Assuming UserAcueducto might be needed for type hinting or direct use in future utils.

def obtener_mes_espanol(numero_mes):
    meses = {
        1: 'enero',
        2: 'febrero',
        3: 'marzo',
        4: 'abril',
        5: 'mayo',
        6: 'junio',
        7: 'julio',
        8: 'agosto',
        9: 'septiembre',
        10: 'octubre',
        11: 'noviembre',
        12: 'diciembre'
    }
    return meses[numero_mes]

def formatear_fecha_espanol(fecha):
    """
    Formatea una fecha en español
    fecha: objeto datetime
    retorna: string con formato "dd de mes de yyyy"
    """
    mes = obtener_mes_espanol(fecha.month)
    return f"{fecha.day} de {mes} de {fecha.year}"

def generar_pdf_factura(usuario: UserAcueducto, fecha_emision, periodo_facturacion, base_url):
    """Genera el PDF de una factura individual"""
    historico_lecturas = usuario.lecturas.all().order_by('-fecha_lectura')[:6]
    lectura_anterior = None
    if len(historico_lecturas) > 1:
        lectura_anterior = historico_lecturas[1]

    template = get_template('factura_template.html')
    context = {
        'usuario': usuario,
        'historico_lecturas': historico_lecturas,
        'lectura_anterior': lectura_anterior,
        'fecha_emision': fecha_emision,
        'periodo_facturacion': periodo_facturacion,
    }
    html = template.render(context)

    # Use settings.BASE_DIR directly if base_url is meant to be static path
    # For now, assuming base_url is passed correctly as Path object or string
    pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    HTML(string=html, base_url=str(base_url)).write_pdf(pdf_file.name)
    return pdf_file

def enviar_factura_email(usuario: UserAcueducto, pdf_file_path: str):
    """Envía la factura por email al usuario"""
    email = EmailMessage(
        'Factura del Acueducto',
        'Adjunto encontrará su factura.',
        settings.DEFAULT_FROM_EMAIL,
        [usuario.email]
    )
    email.attach_file(pdf_file_path)
    email.send()
