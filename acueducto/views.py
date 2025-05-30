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
from datetime import datetime, timedelta
from django.utils import timezone # Import timezone
from django.db import IntegrityError, DatabaseError # Import IntegrityError and DatabaseError
import tempfile
import os
import logging # Import logging
from io import BytesIO
import zipfile
import json
from .models import UserAcueducto, HistoricoLectura, Ruta, OrdenRuta
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
    
    pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    HTML(string=html, base_url=str(base_url)).write_pdf(pdf_file.name)
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
    """Genera un archivo ZIP con todas las facturas"""
    if not periodo_inicio or not periodo_fin:
        raise ValueError('Por favor, especifique el período de facturación')
    
    periodo_inicio_fecha = datetime.strptime(periodo_inicio, '%Y-%m-%d')
    periodo_fin_fecha = datetime.strptime(periodo_fin, '%Y-%m-%d')
    periodo_facturacion = f"Del {formatear_fecha_espanol(periodo_inicio_fecha)} al {formatear_fecha_espanol(periodo_fin_fecha)}"
    
    zip_buffer = BytesIO()
    base_url = settings.BASE_DIR / 'acueducto' / 'static'
    errores_facturacion = []
    
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        for usuario in UserAcueducto.objects.all():
            try:
                pdf_file = generar_pdf_factura(
                    usuario=usuario,
                    fecha_emision=timezone.now(),
                    periodo_facturacion=periodo_facturacion,
                    base_url=base_url
                )
                
                with open(pdf_file.name, 'rb') as pdf:
                    zip_file.writestr(f'factura_{usuario.contrato}.pdf', pdf.read())
                
                os.unlink(pdf_file.name)
            except Exception as e:
                error_msg = f'Error al generar factura para {usuario.contrato}: {str(e)}'
                logger.error(error_msg)
                errores_facturacion.append(f"Error para {usuario.contrato}: {str(e)}")
                continue # Continue to the next user
    
    # This message might not be directly visible to the user with a file download response,
    # but it's good practice. Logging is the more reliable way to track these errors.
    if errores_facturacion:
        # Note: messages added here won't be seen if the view returns a direct HttpResponse (like a file download)
        # This message would typically be displayed on the next rendered page if a redirect occurred.
        # For a direct file download, this message might not show up easily.
        # We will add it for completeness, assuming the calling view might handle it or for logging.
        # A better UX would be to show a summary page after the download attempt.
        # For now, we'll store it in a way the calling view `generar_factura` can potentially access it.
        # This function returns zip_buffer, so it can't add messages to request directly.
        # Instead, it can return errors along with the buffer.
        return zip_buffer, errores_facturacion # Return errors along with the buffer
        
    return zip_buffer, None # No errors

def generar_factura_individual(contrato, fecha_emision, periodo_inicio, periodo_fin, consecutivo_desde=None, consecutivo_hasta=None):
    """Genera una factura individual"""
    if not all([periodo_inicio, periodo_fin]):
        raise ValueError('Por favor, especifique el período de facturación')
    
    periodo_inicio_fecha = datetime.strptime(periodo_inicio, '%Y-%m-%d')
    periodo_fin_fecha = datetime.strptime(periodo_fin, '%Y-%m-%d')
    periodo_facturacion = f"Del {formatear_fecha_espanol(periodo_inicio_fecha)} al {formatear_fecha_espanol(periodo_fin_fecha)}"
    
    usuario = get_object_or_404(UserAcueducto, contrato=contrato)
    base_url = settings.BASE_DIR / 'acueducto' / 'static'
    
    return generar_pdf_factura(
        usuario=usuario,
        fecha_emision=fecha_emision or timezone.now(),
        periodo_facturacion=periodo_facturacion,
        base_url=base_url,
        consecutivo_desde=consecutivo_desde,
        consecutivo_hasta=consecutivo_hasta
    )

def generar_factura(request):
    """Vista principal para la generación de facturas"""
    contrato_preseleccionado = request.GET.get('contrato', '')
    fecha_actual = timezone.now()
    
    if request.method == 'POST':
        try:
            if 'generar_todas' in request.POST:
                zip_buffer, errores = generar_todas_facturas(
                    request.POST.get('periodo_inicio_todas'),
                    request.POST.get('periodo_fin_todas')
                )
                
                if errores:
                    messages.warning(request, f"Se generaron las facturas, pero con errores: {'; '.join(errores)}")

                response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
                response['Content-Disposition'] = 'attachment; filename="todas_las_facturas.zip"'
                return response
            else:
                pdf_file = generar_factura_individual(
                    contrato=request.POST.get('contrato'),
                    fecha_emision=datetime.strptime(request.POST.get('fecha_emision'), '%Y-%m-%d') if request.POST.get('fecha_emision') else None,
                    periodo_inicio=request.POST.get('periodo_inicio'),
                    periodo_fin=request.POST.get('periodo_fin'),
                    consecutivo_desde=request.POST.get('consecutivo_desde'),
                    consecutivo_hasta=request.POST.get('consecutivo_hasta')
                )
                
                if 'enviar_email' in request.POST:
                    usuario = UserAcueducto.objects.get(contrato=request.POST.get('contrato'))
                    enviar_factura_email(usuario, pdf_file)
                    messages.success(request, 'Factura enviada por correo exitosamente')
                    os.unlink(pdf_file.name)
                    return redirect('generar_factura')
                
                with open(pdf_file.name, 'rb') as pdf:
                    response = HttpResponse(pdf.read(), content_type='application/pdf')
                    response['Content-Disposition'] = f'inline; filename="factura_{request.POST.get("contrato")}.pdf"'
                    os.unlink(pdf_file.name)
                    return response
                    
        except Exception as e:
            messages.error(request, f'Error al generar la factura: {str(e)}')
            return redirect('generar_factura')
    
    usuarios = UserAcueducto.objects.all().order_by('contrato')
    busqueda_contrato = request.GET.get('busqueda_contrato', '')
    
    if busqueda_contrato:
        usuarios = usuarios.filter(contrato__icontains=busqueda_contrato)
    
    return render(request, 'generar_factura.html', {
        'usuarios': usuarios,
        'contrato_preseleccionado': contrato_preseleccionado,
        'busqueda_contrato': busqueda_contrato,
        'fecha_actual': fecha_actual,
    })

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

def _get_active_route_details():
    """
    Queries for an active route and calculates its details.
    Returns:
        tuple: (Ruta|None, total_lecturas, lecturas_completadas, porcentaje_completado)
    """
    try:
        ruta = Ruta.objects.filter(activa=True).prefetch_related(
            'ordenruta_set__usuario',
            'ordenruta_set__usuario__lecturas'  # Assuming 'lecturas' is the related_name for HistoricoLectura on UserAcueducto
        ).first()

        if ruta:
            total_lecturas = ruta.ordenruta_set.count()
            lecturas_completadas = ruta.ordenruta_set.filter(lectura_tomada=True).count()
            if total_lecturas > 0:
                porcentaje_completado = (lecturas_completadas / total_lecturas) * 100
            else:
                porcentaje_completado = 0
            return ruta, total_lecturas, lecturas_completadas, porcentaje_completado
        else:
            return None, 0, 0, 0
    except Exception as e: # Broad exception to catch any issue during query/calculation
        logger.error(f"Error in _get_active_route_details: {e}")
        return None, 0, 0, 0

def _handle_lectura_submission(request, ruta, usuario_contrato, nueva_lectura_str):
    """
    Handles the submission of a new lectura.
    Returns:
        tuple: (UserAcueducto|None, historico_list|None)
    """
    usuario = None
    try:
        usuario = UserAcueducto.objects.get(contrato=usuario_contrato)
    except UserAcueducto.DoesNotExist:
        messages.error(request, "Usuario no encontrado")
        return None, None

    try:
        fecha_actual = timezone.now().date()
        
        # Crear el histórico de lectura
        HistoricoLectura.objects.create(
            usuario=usuario,
            lectura=nueva_lectura_str,
            fecha_lectura=fecha_actual
        )
        
        # Actualizar la lectura actual del usuario
        usuario.lectura = nueva_lectura_str
        usuario.fecha_ultima_lectura = fecha_actual
        usuario.save()
        
        # Actualizar el estado de la lectura en la ruta si existe
        if ruta:
            orden_ruta = ruta.ordenruta_set.filter(usuario=usuario).first()
            if orden_ruta:
                orden_ruta.lectura_tomada = True
                orden_ruta.save()
        
        messages.success(request, "Lectura registrada exitosamente")
        historico = usuario.lecturas.all().order_by('-fecha_lectura')[:6]
        return usuario, list(historico)
    
    except IntegrityError as ie:
        logger.error(f"Error de integridad al guardar lectura para {usuario_contrato}: {ie}")
        messages.error(request, f"Error de integridad de datos al guardar la lectura: {ie}")
        return usuario, None
    except DatabaseError as de:
        logger.error(f"Error de base de datos al guardar lectura para {usuario_contrato}: {de}")
        messages.error(request, f"Error de base de datos al guardar la lectura: {de}")
        return usuario, None
    except Exception as e:
        logger.error(f"Error inesperado al guardar lectura para {usuario_contrato}: {e}")
        messages.error(request, f"Error inesperado al guardar la lectura: {e}")
        return usuario, None

def _get_user_data_for_display(request, contrato_str):
    """
    Fetches user and their historico for display.
    Returns:
        tuple: (UserAcueducto|None, historico_list|None)
    """
    if not contrato_str: # Handle empty contrato_str if it can occur
        # messages.error(request, "Número de contrato no proporcionado.") # Optional: if empty string is invalid
        return None, None
    try:
        usuario = UserAcueducto.objects.get(contrato=contrato_str)
        historico = usuario.lecturas.all().order_by('-fecha_lectura')[:6]
        return usuario, list(historico)
    except UserAcueducto.DoesNotExist:
        messages.error(request, "Usuario no encontrado")
        return None, None
    except Exception as e:
        logger.error(f"Error inesperado al obtener datos de usuario para {contrato_str}: {e}")
        messages.error(request, f"Error inesperado al obtener datos del usuario: {e}")
        return None, None

@login_required(login_url='login')
def toma_lectura(request):
    usuario = None
    historico = None
    
    # Attempt to get active route details first
    ruta, total_lecturas, lecturas_completadas, porcentaje_completado = _get_active_route_details()

    try:
        if request.method == 'POST':
            contrato_str = request.POST.get('contrato')
            nueva_lectura_str = request.POST.get('lectura')
            # _handle_lectura_submission will set messages for success/failure
            usuario, historico = _handle_lectura_submission(request, ruta, contrato_str, nueva_lectura_str)
            # If submission was successful and route details were updated, refresh them
            if usuario and historico and ruta: # Check if submission was successful
                 # Re-fetch route details if a reading was successfully taken, to update completion stats
                 ruta, total_lecturas, lecturas_completadas, porcentaje_completado = _get_active_route_details()

        elif request.method == 'GET':
            contrato_str = request.GET.get('contrato')
            if contrato_str:
                # _get_user_data_for_display will set messages if user not found
                usuario, historico = _get_user_data_for_display(request, contrato_str)
        
        # After POST or GET, if ruta is None (no active route or error fetching it), add info message.
        # This replaces the old Ruta.DoesNotExist block logic.
        if ruta is None:
            messages.info(request, "No hay ruta activa disponible en este momento.")
            # Ensure default values for context if ruta is None
            total_lecturas, lecturas_completadas, porcentaje_completado = 0, 0, 0

        context = {
            'usuario': usuario,
            'historico': historico,
            'ruta_activa': ruta,
            'total_lecturas': total_lecturas,
            'lecturas_completadas': lecturas_completadas,
            'porcentaje_completado': porcentaje_completado
        }
        return render(request, 'toma_lectura.html', context)

    except Exception as e: # Catch-all for any other unexpected errors
        logger.error(f'Error inesperado al cargar la página de toma de lectura: {str(e)}')
        messages.error(request, f'Error inesperado al cargar la página: {str(e)}')
        # Render with minimal context in case of a severe error
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


