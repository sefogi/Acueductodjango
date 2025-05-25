from django import template
from django.template.defaultfilters import floatformat

register = template.Library()

@register.filter
def sub(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def calcular_consumo(lecturas, posicion):
    try:
        posicion = int(posicion)
        lectura_actual = lecturas[posicion].lectura
        if posicion + 1 < len(lecturas):
            lectura_anterior = lecturas[posicion + 1].lectura
            consumo = lectura_actual - lectura_anterior
            return floatformat(consumo, 3)
    except (IndexError, ValueError, AttributeError):
        pass
    return 'N/A'
