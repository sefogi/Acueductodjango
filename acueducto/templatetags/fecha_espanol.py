from django import template
from ..utils import formatear_fecha_espanol

register = template.Library()

@register.filter(name='fecha_espanol')
def fecha_espanol(value):
    """Convierte una fecha al formato español."""
    return formatear_fecha_espanol(value)
