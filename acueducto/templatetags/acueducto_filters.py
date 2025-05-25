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

@register.filter(name='format_cop')
def format_cop(value, decimal_places=2):
    if value is None:
        return ""  # Return empty string for None input
    try:
        # Ensure value is treated as a number, attempt conversion if it's string etc.
        val = float(value)
    except (ValueError, TypeError):
        return ""  # Return empty string if conversion to float fails

    try:
        # Format the number to a string with 'decimal_places' decimal points.
        # Using 'f' for fixed-point notation.
        # We'll use a dot as a temporary decimal separator for splitting.
        s_value = "{:.{dp}f}".format(val, dp=decimal_places)

        parts = s_value.split('.')
        integer_part = parts[0]
        
        # Handle potential absence of decimal part if decimal_places is 0 or number is whole
        decimal_part_str = parts[1] if len(parts) > 1 and decimal_places > 0 else ""

        # Add thousands separators for the integer part
        # Handle negative sign if present
        sign = ""
        if integer_part.startswith('-'):
            sign = "-"
            integer_part = integer_part[1:]

        integer_part_formatted = ""
        for i, digit in enumerate(reversed(integer_part)):
            if i > 0 and i % 3 == 0:
                integer_part_formatted = "." + integer_part_formatted  # Colombian thousands separator
            integer_part_formatted = digit + integer_part_formatted
        
        integer_part_formatted = sign + integer_part_formatted

        if decimal_places > 0 and decimal_part_str:
            return f"${integer_part_formatted},{decimal_part_str}"  # Colombian decimal separator
        else:
            return f"${integer_part_formatted}"
            
    except (ValueError, TypeError):
        # Fallback for any unexpected error during formatting
        return ""
