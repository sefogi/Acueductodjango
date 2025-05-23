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
