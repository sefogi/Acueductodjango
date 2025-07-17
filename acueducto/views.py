from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.template.loader import get_template
from django.core.mail import EmailMessage
from django.conf import settings
from weasyprint import HTML
from datetime import datetime, timedelta, date
from django.utils import timezone # Import timezone
from django.db import IntegrityError, DatabaseError # Import IntegrityError and DatabaseError
import tempfile
import os
import logging # Import logging
from io import BytesIO
import zipfile
import json
from .models import UserAcueducto, HistoricoLectura, Ruta, OrdenRuta, Factura
from .utils import formatear_fecha_espanol
from .forms import UserAcueductoForm # Import the new form

logger = logging.getLogger(__name__) # Initialize logger

# Create your views here.
def index(request):
    if request.method == 'POST':
        form = UserAcueductoForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Usuario creado exitosamente')
                return redirect('index') # Redirect to avoid form resubmission
            except IntegrityError as e:
                logger.error(f"Error de integridad al crear usuario: {e}")
                # Determine which field caused the error if possible, e.g. by parsing 'e'
                if 'contrato' in str(e).lower():
                    form.add_error('contrato', 'Este número de contrato ya existe.')
                elif 'email' in str(e).lower(): # Assuming email is unique
                    form.add_error('email', 'Este correo electrónico ya está en uso.')
                else:
                    messages.error(request, f'Error de integridad de datos: {e}. Por favor, revise los campos únicos.')
            except Exception as e: # Catch other potential errors during save
                logger.error(f"Error inesperado al guardar formulario de creación de usuario: {e}")
                messages.error(request, f'Ocurrió un error inesperado al crear el usuario: {e}')
        # If form is not valid (either from initial validation or after adding error from IntegrityError), 
        # it will be passed to the template with errors
    else:
        form = UserAcueductoForm() # Unbound form for GET request
    return render(request, 'index.html', {'form': form})

def lista_usuarios(request):
    busqueda = request.GET.get('busqueda', '')
    usuarios = UserAcueducto.objects.all()
    
    # Obtener solo las rutas activas
    rutas_activas = Ruta.objects.filter(activa=True).prefetch_related('ordenruta_set__usuario')

    if request.method == 'POST' and 'generar_ruta' in request.POST:
        try:
            nombre_ruta = request.POST.get('nombre_ruta')
            usuarios_orden = json.loads(request.POST.get('usuarios_orden', '[]'))
            
            if not nombre_ruta or not usuarios_orden:
                raise ValueError("Nombre de ruta y usuarios son requeridos")

            now = timezone.now()

            # Deactivate all currently active routes
            active_routes = Ruta.objects.filter(activa=True)
            for r in active_routes:
                r.activa = False
                r.fecha_finalizacion = now
                r.save()
            
            # Crear la nueva ruta
            ruta = Ruta.objects.create(nombre=nombre_ruta, activa=True)
            
            for usuario_data in usuarios_orden:
                OrdenRuta.objects.create(
                    ruta=ruta,
                    usuario_id=usuario_data['id'],
                    orden=usuario_data['orden']
                )
            
            messages.success(request, 'Ruta creada exitosamente')
            return redirect('lista_usuarios')
        except Exception as e:
            messages.error(request, f'Error al crear la ruta: {str(e)}')
    
    if busqueda:
        usuarios = usuarios.filter(
            Q(contrato__icontains=busqueda) |
            Q(address__icontains=busqueda) |
            Q(zona__icontains=busqueda)
        )
    
    return render(request, 'lista_usuarios.html', {
        'usuarios': usuarios,
        'busqueda': busqueda,
        'rutas_activas': rutas_activas
    })

def generar_pdf_factura(usuario, fecha_emision, periodo_facturacion, base_url, consecutivo_desde=None, consecutivo_hasta=None):
    """Genera el PDF de una factura individual"""
    historico_lecturas = usuario.lecturas.all().order_by('-fecha_lectura')[:6]
    lectura_anterior = None
    if len(historico_lecturas) > 1:
        lectura_anterior = historico_lecturas[1]
    
    # Determine consumo_m3
    consumo_m3 = 0
    if lectura_anterior and usuario.lectura is not None and lectura_anterior.lectura is not None:
        consumo_m3 = usuario.lectura - lectura_anterior.lectura
    elif usuario.lectura is not None:
        consumo_m3 = usuario.lectura
    else:
        consumo_m3 = 0

    valor_por_m3 = 1000
    
    # Calculate costo_consumo_raw based on usuario.lectura
    if usuario.lectura is not None:
        costo_consumo_raw = usuario.lectura * valor_por_m3
    else:
        costo_consumo_raw = 0
        
    costo_consumo_agua_redondeado = round(costo_consumo_raw)

    credito = usuario.credito if usuario.credito is not None else 0
    otros_gastos = usuario.otros_gastos_valor if usuario.otros_gastos_valor is not None else 0

    total_factura_raw = costo_consumo_agua_redondeado + float(credito) + float(otros_gastos)
    total_factura_redondeado = round(total_factura_raw)

    template = get_template('factura_template.html')
    context = {
        'usuario': usuario,
        'historico_lecturas': historico_lecturas,
        'lectura_anterior': lectura_anterior,
        'fecha_emision': fecha_emision,
        'periodo_facturacion': periodo_facturacion,
        'costo_consumo_agua_redondeado': costo_consumo_agua_redondeado,
        'total_factura_redondeado': total_factura_redondeado,
        'valor_por_m3': valor_por_m3,
        'consecutivo_desde': consecutivo_desde,
        'consecutivo_hasta': consecutivo_hasta,
    }
    html = template.render(context)
    
    pdf_buffer = BytesIO()
    HTML(string=html).write_pdf(pdf_buffer)
    
    # Crear archivo temporal y escribir el contenido
    pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    with open(pdf_file.name, 'wb') as f:
        f.write(pdf_buffer.getvalue())
    
    return pdf_file

def enviar_factura_email(usuario, pdf_file):
    """Envía la factura por email al usuario"""
    email = EmailMessage(
        'Factura del Acueducto',
        'Adjunto encontrará su factura.',
        settings.DEFAULT_FROM_EMAIL,
        [usuario.email]
    )
    email.attach_file(pdf_file.name)
    email.send()

def generar_todas_facturas(periodo_inicio, periodo_fin):
    """
    Genera un archivo ZIP con todas las facturas.
    Args:
        periodo_inicio: Fecha de inicio del período a facturar
        periodo_fin: Fecha de fin del período a facturar
    Returns:
        BytesIO: Buffer conteniendo el archivo ZIP con todas las facturas
    Raises:
        ValueError: Si hay error en las fechas o en la generación
    """
    if not periodo_inicio or not periodo_fin:
        raise ValueError('Por favor, especifique el período de facturación')
    
    # Función auxiliar para convertir a date
    def to_date(value):
        if isinstance(value, str):
            return datetime.strptime(value, '%Y-%m-%d').date()
        elif isinstance(value, datetime):
            return value.date()
        elif isinstance(value, date):
            return value
        else:
            raise ValueError(f"Tipo de fecha no válido: {type(value)}")
    
    try:
        # Convertir fechas
        periodo_inicio = to_date(periodo_inicio)
        periodo_fin = to_date(periodo_fin)
        fecha_emision = datetime.now().date()

        if periodo_fin <= periodo_inicio:
            raise ValueError("La fecha final debe ser posterior a la fecha inicial")

    except Exception as e:
        logger.error(f"Error procesando fechas: {str(e)}")
        raise ValueError(f"Error en el formato de las fechas: {str(e)}")
    
    # Crear buffer para el ZIP
    zip_buffer = BytesIO()
    errores = []
    
    # Crear archivo ZIP
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for usuario in UserAcueducto.objects.all():
            try:
                # Generar PDF
                pdf_buffer = BytesIO()
                factura_pdf = generar_factura_individual(
                    contrato=usuario.contrato,
                    fecha_emision=fecha_emision,
                    periodo_inicio=periodo_inicio,
                    periodo_fin=periodo_fin
                )
                pdf_buffer.write(factura_pdf.getvalue())
                pdf_buffer.seek(0)
                
                # Agregar al ZIP
                nombre_archivo = f"factura_{usuario.contrato}_{fecha_emision.strftime('%Y%m%d')}.pdf"
                zip_file.writestr(nombre_archivo, pdf_buffer.getvalue())
                
            except Exception as e:
                error_msg = f"Error generando factura para usuario {usuario.contrato}: {str(e)}"
                logger.error(error_msg)
                errores.append(error_msg)
    
    if errores:
        logger.warning(f"Se encontraron {len(errores)} errores durante la generación masiva de facturas")
    
    # Asegurar que el buffer está al inicio
    zip_buffer.seek(0)
    return zip_buffer

def generar_factura_individual(contrato, fecha_emision, periodo_inicio, periodo_fin):
    """
    Genera una factura individual para un usuario.
    """
    try:
        # Validar que las fechas son objetos date
        from datetime import date
        
        # Convertir fechas si son strings
        def ensure_date(d):
            if isinstance(d, str):
                return datetime.strptime(d, '%Y-%m-%d').date()
            elif isinstance(d, date):
                return d
            elif isinstance(d, datetime):
                return d.date()
            else:
                raise ValueError(f"Tipo de fecha no válido: {type(d)}")
        
        # Convertir todas las fechas
        fecha_emision = ensure_date(fecha_emision)
        periodo_inicio = ensure_date(periodo_inicio)
        periodo_fin = ensure_date(periodo_fin)
        
        # Validar el período
        if periodo_fin <= periodo_inicio:
            raise ValueError("La fecha final debe ser posterior a la fecha inicial")

        usuario = UserAcueducto.objects.get(contrato=contrato)

        # Obtener las lecturas del período
        lecturas = HistoricoLectura.objects.filter(
            usuario=usuario,
            fecha_lectura__range=[periodo_inicio, periodo_fin]
        ).order_by('fecha_lectura')
        
        if not lecturas.exists():
            raise ValueError("No hay lecturas para el período especificado")

        # Calcular consumo
        ultima_lectura = lecturas.last().lectura
        primera_lectura = lecturas.first().lectura
        consumo = ultima_lectura - primera_lectura

        # Calcular valor total (implementa tu lógica de cálculo aquí)
        valor_por_m3 = 1000  # Ajusta según tu lógica de negocio
        valor_total = consumo * valor_por_m3

        # Verificar si ya existe una factura para este período
        factura_existente = Factura.objects.filter(
            usuario=usuario,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin
        ).first()

        if factura_existente:
            raise ValueError("Ya existe una factura para este período")

        # Crear la factura en la base de datos
        factura = Factura.objects.create(
            usuario=usuario,
            consecutivo=Factura.get_next_consecutivo(),
            fecha_emision=fecha_emision,
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            consumo=consumo,
            valor_total=valor_total,
            pdf_generado=True
        )

        # Obtener el histórico de lecturas para mostrar en la factura
        historico_lecturas = HistoricoLectura.objects.filter(
            usuario=usuario
        ).order_by('-fecha_lectura')[:6]
        
        # Obtener la lectura anterior si existe
        lectura_anterior = None
        if len(historico_lecturas) > 1:
            lectura_anterior = historico_lecturas[1]

        # Formatear el período de facturación
        periodo_facturacion = f"Del {periodo_inicio.strftime('%d/%m/%Y')} al {periodo_fin.strftime('%d/%m/%Y')}"

        # Generar el PDF
        template = get_template('factura_template.html')
        context = {
            'factura': factura,
            'usuario': usuario,
            'lecturas': lecturas,
            'historico_lecturas': historico_lecturas,
            'lectura_anterior': lectura_anterior,
            'consumo': consumo,
            'valor_total': valor_total,
            'fecha_emision': fecha_emision,
            'periodo_facturacion': f"Del {periodo_inicio.strftime('%d/%m/%Y')} al {periodo_fin.strftime('%d/%m/%Y')}",
            'valor_por_m3': valor_por_m3,
            'costo_consumo_agua_redondeado': round(valor_total),
            'total_factura_redondeado': round(valor_total + float(usuario.credito) + float(usuario.otros_gastos_valor))
        }
        
        html_string = template.render(context)
        pdf_buffer = BytesIO()
        
        # Generar el PDF directamente desde el string
        html = HTML(string=html_string, base_url=str(settings.BASE_DIR))
        
        # Usar un archivo temporal para el PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as pdf_file:
            html.write_pdf(pdf_file.name)
            pdf_file.close()
            
            # Leer el PDF generado
            with open(pdf_file.name, 'rb') as f:
                pdf_buffer.write(f.read())
            
            # Eliminar el archivo temporal
            os.unlink(pdf_file.name)
        
        pdf_buffer.seek(0)
        
        # Marcar la factura como generada
        factura.pdf_generado = True
        factura.save()
        
        return pdf_buffer

    except UserAcueducto.DoesNotExist:
        raise ValueError(f"No se encontró usuario con contrato {contrato}")
    except Exception as e:
        logger.error(f"Error generando factura para contrato {contrato}: {str(e)}")
        raise

def generar_factura(request):
    if request.method == 'POST':
        try:
            # Convertir fechas asegurándose de que son objetos date
            def parse_date(date_str):
                """
                Convierte una fecha en string o un objeto datetime a date.
                
                Args:
                    date_str: String en formato YYYY-MM-DD o objeto datetime/date
                
                Returns:
                    date: Objeto date de Python
                
                Raises:
                    ValueError: Si la fecha está vacía o el formato es inválido
                """
                if not date_str:
                    raise ValueError("La fecha no puede estar vacía")
                
                try:
                    # Si ya es un objeto date, retornarlo directamente
                    if isinstance(date_str, date):
                        return date_str
                    
                    # Si es datetime, convertir a date
                    if isinstance(date_str, datetime):
                        return date_str.date()
                    
                    # Si es string, intentar convertir
                    if isinstance(date_str, str):
                        try:
                            return datetime.strptime(date_str, '%Y-%m-%d').date()
                        except ValueError:
                            # Intentar otros formatos comunes si el primero falla
                            for fmt in ['%d/%m/%Y', '%d-%m-%Y']:
                                try:
                                    return datetime.strptime(date_str, fmt).date()
                                except ValueError:
                                    continue
                            raise ValueError(f"Formato de fecha no reconocido: {date_str}")
                    
                    raise ValueError(f"Tipo de fecha no válido: {type(date_str)}")
                except Exception as e:
                    logger.error(f"Error al procesar fecha. Valor: {date_str}, Tipo: {type(date_str)}, Error: {str(e)}")
                    raise ValueError(f"Error al procesar fecha: {str(e)}")

            # Generar facturas para todos los usuarios
            if 'generar_todas' in request.POST:
                try:
                    periodo_inicio = parse_date(request.POST.get('periodo_inicio_todas'))
                    periodo_fin = parse_date(request.POST.get('periodo_fin_todas'))
                    fecha_emision = datetime.now().date()
                    consecutivo_desde = int(request.POST.get('consecutivo_desde', 1))
                    consecutivo_hasta = int(request.POST.get('consecutivo_hasta', 1))

                    # Validar el período
                    if periodo_fin <= periodo_inicio:
                        messages.error(request, "La fecha final debe ser posterior a la fecha inicial")
                        return redirect('generar_factura')
                    
                    # Validar rango de consecutivos
                    if consecutivo_hasta < consecutivo_desde:
                        messages.error(request, "El consecutivo final debe ser mayor o igual al inicial")
                        return redirect('generar_factura')
                    
                    usuarios = UserAcueducto.objects.all()
                    total_usuarios = usuarios.count()
                    rango_consecutivos = consecutivo_hasta - consecutivo_desde + 1
                    
                    # Agregar logs para diagnóstico
                    print(f"DEBUG - Consecutivo desde: {consecutivo_desde}")
                    print(f"DEBUG - Consecutivo hasta: {consecutivo_hasta}")
                    print(f"DEBUG - Rango calculado: {rango_consecutivos}")
                    print(f"DEBUG - Total usuarios: {total_usuarios}")
                    
                    if total_usuarios > rango_consecutivos:
                        messages.error(request, f"El rango de consecutivos ({rango_consecutivos}) es menor que el número de usuarios ({total_usuarios})")
                        return redirect('generar_factura')
                    
                    zip_buffer = BytesIO()
                    facturas_generadas = []
                    consecutivo_actual = consecutivo_desde
                    
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for usuario in usuarios:
                            try:
                                # Verificar si ya existe una factura para este usuario y período
                                factura_existente = Factura.objects.filter(
                                    usuario=usuario,
                                    periodo_inicio=periodo_inicio,
                                    periodo_fin=periodo_fin
                                ).first()
                                
                                if factura_existente:
                                    logger.warning(f"Ya existe una factura para el usuario {usuario.contrato} en este período")
                                    continue
                                
                                # Generar nueva factura
                                lecturas = HistoricoLectura.objects.filter(
                                    usuario=usuario,
                                    fecha_lectura__range=[periodo_inicio, periodo_fin]
                                ).order_by('fecha_lectura')
                                
                                if not lecturas.exists():
                                    logger.warning(f"No hay lecturas para el usuario {usuario.contrato} en el período especificado")
                                    continue
                                
                                # Calcular consumo
                                ultima_lectura = lecturas.last().lectura
                                primera_lectura = lecturas.first().lectura
                                consumo = ultima_lectura - primera_lectura
                                valor_total = consumo * 1000  # Ajusta según tu lógica de negocio
                                
                                # Crear la factura en la base de datos usando el consecutivo actual
                                factura = Factura.objects.create(
                                    usuario=usuario,
                                    consecutivo=consecutivo_actual,
                                    fecha_emision=fecha_emision,
                                    periodo_inicio=periodo_inicio,
                                    periodo_fin=periodo_fin,
                                    consumo=consumo,
                                    valor_total=valor_total,
                                    pdf_generado=True
                                )
                                facturas_generadas.append(factura)
                                consecutivo_actual += 1
                                
                                # Generar PDF
                                template = get_template('factura_template.html')
                                # Obtener el histórico de lecturas para mostrar en la factura
                                historico_lecturas = HistoricoLectura.objects.filter(
                                    usuario=usuario
                                ).order_by('-fecha_lectura')[:6]  # Últimas 6 lecturas
                                
                                # Obtener la lectura anterior si existe
                                lectura_anterior = None
                                if len(historico_lecturas) > 1:
                                    lectura_anterior = historico_lecturas[1]
                                
                                context = {
                                    'factura': factura,
                                    'usuario': usuario,
                                    'lecturas': lecturas,
                                    'historico_lecturas': historico_lecturas,
                                    'lectura_anterior': lectura_anterior,
                                    'consumo': consumo,
                                    'valor_total': valor_total,
                                    'fecha_emision': fecha_emision,
                                    'periodo_facturacion': f"Del {periodo_inicio.strftime('%d/%m/%Y')} al {periodo_fin.strftime('%d/%m/%Y')}",
                                    'valor_por_m3': 1000,  # Ajusta este valor según tu lógica de negocio
                                    'costo_consumo_agua_redondeado': round(valor_total),
                                    'total_factura_redondeado': round(valor_total + float(usuario.credito) + float(usuario.otros_gastos_valor))
                                }
                                
                                html_string = template.render(context)
                                pdf_buffer = BytesIO()
                                HTML(string=html_string).write_pdf(pdf_buffer)
                                
                                # Agregar al ZIP
                                zip_file.writestr(
                                    f"factura_{usuario.contrato}_{factura.consecutivo}.pdf",
                                    pdf_buffer.getvalue()
                                )
                                
                                facturas_generadas.append(factura)
                                
                            except Exception as e:
                                logger.error(f"Error generando factura para usuario {usuario.contrato}: {str(e)}")
                                messages.error(request, f"Error generando factura para usuario {usuario.contrato}: {str(e)}")
                                continue

                    # Crear respuesta con el archivo ZIP
                    # Asegurarse de que el buffer está al inicio antes de leer
                    zip_buffer.seek(0)
                    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
                    response['Content-Disposition'] = f'attachment; filename=facturas_{fecha_emision.strftime("%Y%m%d")}.zip'
                    return response
                    
                except Exception as e:
                    logger.error(f"Error en la generación masiva de facturas: {str(e)}")
                    messages.error(request, f"Error en la generación de facturas: {str(e)}")
                    return redirect('generar_factura')

                # Generar factura individual
            else:
                contrato = request.POST.get('contrato')
                if not contrato:
                    raise ValueError("Debe proporcionar un número de contrato")
                
                fecha_emision = parse_date(request.POST.get('fecha_emision'))
                periodo_inicio = parse_date(request.POST.get('periodo_inicio'))
                periodo_fin = parse_date(request.POST.get('periodo_fin'))
                
                # Validar fechas
                if periodo_fin <= periodo_inicio:
                    messages.error(request, "La fecha final debe ser posterior a la fecha inicial")
                    return redirect('generar_factura')
                
                pdf_file = generar_factura_individual(
                    contrato,
                    fecha_emision,
                    periodo_inicio,
                    periodo_fin
                )

                # Si se solicitó enviar por email
                if 'enviar_email' in request.POST:
                    usuario = UserAcueducto.objects.get(contrato=contrato)
                    factura = Factura.objects.get(
                        usuario=usuario,
                        fecha_emision=fecha_emision,
                        periodo_inicio=periodo_inicio,
                        periodo_fin=periodo_fin
                    )
                    
                    email = EmailMessage(
                        f'Factura #{factura.consecutivo}',
                        'Adjunto encontrará su factura.',
                        settings.DEFAULT_FROM_EMAIL,
                        [usuario.email]
                    )
                    email.attach(f'factura_{contrato}.pdf', pdf_file.getvalue(), 'application/pdf')
                    email.send()
                    
                    factura.email_enviado = True
                    factura.save()
                    
                    messages.success(request, f'Factura #{factura.consecutivo} enviada por email a {usuario.email}')
                    return redirect('generar_factura')

                # Si se solicitó descargar
                response = HttpResponse(pdf_file.getvalue(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename=factura_{contrato}.pdf'
                return response

        except ValueError as e:
            messages.error(request, str(e))
            return redirect('generar_factura')
        except Exception as e:
            logger.error(f"Error en generación de factura: {str(e)}")
            messages.error(request, f"Error generando factura: {str(e)}")
            return redirect('generar_factura')

    return render(request, 'generar_factura.html')

def buscar_usuario_por_contrato(request):
    contrato = request.GET.get('contrato', '')
    if contrato:
        try:
            usuario = UserAcueducto.objects.get(contrato=contrato)
            return JsonResponse({
                'found': True,
                'nombre': f"{usuario.name} {usuario.lastname}",
                'contrato': usuario.contrato
            })
        except UserAcueducto.DoesNotExist:
            return JsonResponse({'found': False})
    return JsonResponse({'found': False})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('toma_lectura')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required(login_url='login')
def toma_lectura(request):
    
    usuario = None
    historico = None
    ruta = None # Initialize ruta
    total_lecturas = 0
    lecturas_completadas = 0
    porcentaje_completado = 0
    
    try:
        # Obtener la ruta activa
        ruta = Ruta.objects.filter(activa=True).prefetch_related(
            'ordenruta_set__usuario',
            'ordenruta_set__usuario__lecturas'
        ).first()
        
        if ruta:
            total_lecturas = ruta.ordenruta_set.count()
            lecturas_completadas = ruta.ordenruta_set.filter(lectura_tomada=True).count()
            porcentaje_completado = (lecturas_completadas / total_lecturas * 100) if total_lecturas > 0 else 0
        else:
            total_lecturas = 0
            lecturas_completadas = 0
            porcentaje_completado = 0
        
        if request.method == 'POST':
            contrato = request.POST.get('contrato')
            nueva_lectura = request.POST.get('lectura')
            try:
                usuario = UserAcueducto.objects.get(contrato=contrato)
                fecha_actual = timezone.now().date()
                
                try:
                    # Crear el histórico de lectura
                    HistoricoLectura.objects.create(
                        usuario=usuario,
                        lectura=nueva_lectura,
                        fecha_lectura=fecha_actual
                    )
                    
                    # Actualizar la lectura actual del usuario
                    usuario.lectura = nueva_lectura
                    usuario.fecha_ultima_lectura = fecha_actual # Renamed from date
                    usuario.save()
                    
                    # Actualizar el estado de la lectura en la ruta si existe
                    if ruta:
                        orden_ruta = ruta.ordenruta_set.filter(usuario=usuario).first()
                        if orden_ruta:
                            orden_ruta.lectura_tomada = True
                            orden_ruta.save()
                    
                    messages.success(request, "Lectura registrada exitosamente") # Use messages framework
                    historico = usuario.lecturas.all()[:6] # Refresh historico
                
                except IntegrityError as ie:
                    logger.error(f"Error de integridad al guardar lectura para {contrato}: {ie}")
                    messages.error(request, f"Error de integridad de datos al guardar la lectura: {ie}")
                except DatabaseError as de:
                    logger.error(f"Error de base de datos al guardar lectura para {contrato}: {de}")
                    messages.error(request, f"Error de base de datos al guardar la lectura: {de}")
                except Exception as e: # Catch any other unexpected error during save
                    logger.error(f"Error inesperado al guardar lectura para {contrato}: {e}")
                    messages.error(request, f"Error inesperado al guardar la lectura: {e}")

            except UserAcueducto.DoesNotExist:
                messages.error(request, "Usuario no encontrado") # Use messages framework
        
        elif request.method == 'GET':
            contrato = request.GET.get('contrato')
            if contrato:
                try:
                    usuario = UserAcueducto.objects.get(contrato=contrato)
                    historico = usuario.lecturas.all()[:6]
                except UserAcueducto.DoesNotExist:
                    messages.error(request, "Usuario no encontrado") # Use messages framework
            # If user is not found by GET, 'usuario' remains None, 'historico' remains None.
            # The template should handle this.

        # Prepare context once, after all operations
        context = {
            # 'mensaje': mensaje, # Replaced by Django messages
            'usuario': usuario,
            'historico': historico,
            'ruta_activa': ruta, # This is the ruta object from the outer try
            'total_lecturas': total_lecturas,
            'lecturas_completadas': lecturas_completadas,
            'porcentaje_completado': porcentaje_completado
        }
        return render(request, 'toma_lectura.html', context)
        
    except Ruta.DoesNotExist: # More specific error for initial route loading
        logger.warning("Intento de cargar toma_lectura sin ruta activa o ruta no encontrada.")
        messages.info(request, "No hay ruta activa disponible en este momento.") # User-friendly message
        # Render the page without route-specific context, or redirect
        context = {
            'usuario': None, 'historico': None, 'ruta_activa': None,
            'total_lecturas': 0, 'lecturas_completadas': 0, 'porcentaje_completado': 0
        }
        return render(request, 'toma_lectura.html', context)
    except Exception as e: # Catch-all for other unexpected errors during setup
        logger.error(f'Error inesperado al cargar la página de toma de lectura: {str(e)}')
        messages.error(request, f'Error inesperado al cargar la página: {str(e)}')
        # Consider redirecting to a safe page or rendering with minimal context
        context = {
            'usuario': None, 'historico': None, 'ruta_activa': None,
            'total_lecturas': 0, 'lecturas_completadas': 0, 'porcentaje_completado': 0
        }
        return render(request, 'toma_lectura.html', context)

@require_POST
def guardar_lectura(request):
    try:
        data = json.loads(request.body)
        usuario_id = data.get('usuario_id')
        lectura_valor = data.get('lectura') # Renamed to avoid conflict with model field name

        if not all([usuario_id, lectura_valor]):
            return JsonResponse({'success': False, 'error': 'Faltan datos: usuario_id o lectura.'}, status=400)

        usuario = get_object_or_404(UserAcueducto, id=usuario_id)
        fecha_actual = timezone.now().date()

        # Guardar la lectura en el histórico
        HistoricoLectura.objects.create(
            usuario=usuario,
            lectura=lectura_valor,
            fecha_lectura=fecha_actual
        )

        # Actualizar la lectura actual del usuario
        usuario.lectura = lectura_valor
        usuario.fecha_ultima_lectura = fecha_actual # Renamed from date
        usuario.save()

        # Actualizar el estado de la lectura en la ruta activa
        ruta_activa = Ruta.objects.filter(activa=True).first()
        if ruta_activa:
            orden_ruta = ruta_activa.ordenruta_set.filter(usuario=usuario).first()
            if orden_ruta:
                orden_ruta.lectura_tomada = True
                orden_ruta.save()

        return JsonResponse({
            'success': True,
            'message': 'Lectura guardada exitosamente'
        })
    except UserAcueducto.DoesNotExist:
        logger.warning(f"guardar_lectura: Usuario no encontrado con ID {data.get('usuario_id')}")
        return JsonResponse({'success': False, 'error': 'Usuario no encontrado.'}, status=404)
    except (IntegrityError, DatabaseError) as db_error:
        logger.error(f"guardar_lectura: Error de base de datos para usuario ID {data.get('usuario_id')}: {db_error}")
        return JsonResponse({'success': False, 'error': f'Error de base de datos: {str(db_error)}'}, status=500)
    except json.JSONDecodeError:
        logger.error("guardar_lectura: Error al decodificar JSON del request body.")
        return JsonResponse({'success': False, 'error': 'Error en el formato de los datos enviados (JSON inválido).'}, status=400)
    except Exception as e:
        logger.error(f"guardar_lectura: Error inesperado para usuario ID {data.get('usuario_id')}: {e}")
        return JsonResponse({
            'success': False,
            'error': f'Ocurrió un error inesperado: {str(e)}'
        }, status=500) # 500 for truly unexpected server errors

@login_required
def finalizar_ruta(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ruta_id = data.get('ruta_id')

            if not ruta_id:
                 return JsonResponse({'error': 'Falta ruta_id.'}, status=400)
            
            ruta = get_object_or_404(Ruta, id=ruta_id)
            
            # Verificar que todas las lecturas estén tomadas
            lecturas_pendientes = ruta.ordenruta_set.filter(lectura_tomada=False).exists()
            if lecturas_pendientes:
                logger.warning(f"Intento de finalizar ruta {ruta_id} con lecturas pendientes.")
                return JsonResponse({
                    'error': 'No se puede finalizar la ruta. Hay lecturas pendientes.'
                }, status=400) # Bad request, client side error
            
            # Marcar la ruta como finalizada
            ruta.activa = False
            ruta.fecha_finalizacion = timezone.now() # Ensure timezone is imported if not already
            ruta.save()
            
            logger.info(f"Ruta {ruta_id} finalizada exitosamente.")
            return JsonResponse({
                'message': 'Ruta finalizada exitosamente',
                'redirect': reverse('toma_lectura') # Use reverse for URL
            })
        except Ruta.DoesNotExist:
            logger.warning(f"finalizar_ruta: Ruta no encontrada con ID {data.get('ruta_id')}")
            return JsonResponse({'error': 'Ruta no encontrada.'}, status=404)
        except (IntegrityError, DatabaseError) as db_error:
            logger.error(f"finalizar_ruta: Error de base de datos para ruta ID {data.get('ruta_id')}: {db_error}")
            return JsonResponse({'error': f'Error de base de datos: {str(db_error)}'}, status=500)
        except json.JSONDecodeError:
            logger.error("finalizar_ruta: Error al decodificar JSON del request body.")
            return JsonResponse({'error': 'Error en el formato de los datos enviados (JSON inválido).'}, status=400)    
        except Exception as e:
            logger.error(f"finalizar_ruta: Error inesperado para ruta ID {data.get('ruta_id')}: {e}")
            return JsonResponse({
                'error': f'Ocurrió un error inesperado: {str(e)}'
            }, status=500)
            
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required(login_url='login')
def historico_lecturas(request, contrato):
    try:
        usuario = get_object_or_404(UserAcueducto, contrato=contrato)
        historico = list(usuario.lecturas.all().order_by('-fecha_lectura'))
        
        return render(request, 'historico_lecturas.html', {
            'usuario': usuario,
            'historico': historico
        })
    except Exception as e:
        messages.error(request, f'Error al cargar el histórico de lecturas: {str(e)}')
        return redirect('lista_usuarios')

from django.urls import reverse # Make sure reverse is imported

@login_required(login_url='login')
def modificar_usuario(request):
    contrato_busqueda = request.GET.get('contrato')
    usuario = None
    form = None

    if contrato_busqueda:
        try:
            usuario = get_object_or_404(UserAcueducto, contrato=contrato_busqueda)
            form = UserAcueductoForm(instance=usuario)
        except UserAcueducto.DoesNotExist:
            messages.error(request, f"No se encontró usuario con contrato '{contrato_busqueda}'.")
            # Keep contrato_busqueda for the template to show what was searched
    
    if request.method == 'POST':
        # This 'contrato' hidden input is crucial for identifying the user to update
        posted_contrato = request.POST.get('contrato')
        if not posted_contrato:
            messages.error(request, "No se especificó el contrato del usuario a modificar.")
            return redirect('modificar_usuario')

        try:
            usuario = get_object_or_404(UserAcueducto, contrato=posted_contrato)
            form = UserAcueductoForm(request.POST, instance=usuario)
            if form.is_valid():
                form.save()
                messages.success(request, 'Usuario actualizado exitosamente')
                # Redirect to the same page with GET parameter to show the updated user
                return redirect(f"{reverse('modificar_usuario')}?contrato={usuario.contrato}")
            else:
                # Form has errors, it will be re-rendered with errors
                messages.error(request, 'Error al actualizar usuario. Por favor revise los datos.')
        except UserAcueducto.DoesNotExist: # Raised by get_object_or_404 if user not found
            logger.warning(f"Intento de actualizar usuario no existente con contrato '{posted_contrato}'.")
            messages.error(request, f"No se encontró usuario con contrato '{posted_contrato}' para actualizar.")
            return redirect('modificar_usuario') # Redirect to clean search state
        except IntegrityError as e:
            logger.error(f"Error de integridad al actualizar usuario {posted_contrato}: {e}")
            if 'contrato' in str(e).lower():
                 form.add_error('contrato', 'Este número de contrato ya existe para otro usuario.')
            elif 'email' in str(e).lower():
                 form.add_error('email', 'Este correo electrónico ya está en uso por otro usuario.')
            else:
                messages.error(request, f"Error de integridad de datos al actualizar: {e}. Es posible que algunos datos ya existan.")
            # form will be re-rendered with these errors
        except Exception as e:
            logger.error(f"Error inesperado al actualizar usuario {posted_contrato}: {e}")
            messages.error(request, f'Ocurrió un error inesperado al actualizar el usuario: {str(e)}')
            # If an unexpected error occurs, we might want to re-render the form if 'usuario' and 'form' are defined
            # or redirect to a clean state. For now, let the form be re-rendered if possible.
            if usuario and form is None: # If form wasn't initialized due to early error (unlikely here as form is defined before this try)
                 form = UserAcueductoForm(request.POST, instance=usuario) # Attempt to show data trying to be saved

    context = {
        'form': form,
        'usuario': usuario, # This will be None if not found by GET, or the instance
        'contrato_busqueda': contrato_busqueda
    }
    return render(request, 'modificar_usuario.html', context)


