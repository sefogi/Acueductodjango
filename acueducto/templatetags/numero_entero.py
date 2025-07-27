from django import template

register = template.Library()

@register.filter(name='numero_entero')
def numero_entero(value):
    """
    Convierte un número a entero para mostrar en la factura.
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return value
