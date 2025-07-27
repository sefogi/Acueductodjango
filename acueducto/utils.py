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

def formatear_fecha_espanol(fecha) -> str:
    """
    Formatea una fecha en español.

    Args:
        fecha: Objeto date, datetime o str en formato YYYY-MM-DD.

    Returns:
        str: Fecha formateada en español (ejemplo: "15 de julio de 2025")

    Raises:
        ValueError: Si el objeto fecha no es válido o no se puede convertir
    """
    from datetime import datetime, date
    
    try:
        # Si es string, convertir a date
        if isinstance(fecha, str):
            fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
        # Si es datetime, convertir a date
        elif isinstance(fecha, datetime):
            fecha = fecha.date()
        # Si no es date, intentar convertir
        elif not isinstance(fecha, date):
            raise ValueError(f"Tipo de fecha no soportado: {type(fecha)}")

        dia = fecha.day
        mes = obtener_mes_espanol(fecha.month)
        anio = fecha.year
        return f"{dia} de {mes} de {anio}"
    except Exception as e:
        raise ValueError(f"Error al formatear fecha: {str(e)}. Valor recibido: {fecha}, Tipo: {type(fecha)}")
