from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count, Case, When, FloatField, Value
from django.template.loader import get_template
from django.core.mail import EmailMessage
from django.conf import settings
from weasyprint import HTML
from datetime import datetime, timedelta
import tempfile
import os
from io import BytesIO
# import zipfile # No longer used directly in views.py
import json
from .models import UserAcueducto, HistoricoLectura, Ruta, OrdenRuta
from . import utils # Updated import
from .forms import UserAcueductoForm # Import the form
from . import services # Import services

# Create your views here.
def index(request):
    if request.method == 'POST':
        form = UserAcueductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario creado exitosamente')
            return redirect('index') # Or 'lista_usuarios'
        else:
            messages.error(request, 'Error al crear usuario. Por favor, revise los datos.')
    else:
        form = UserAcueductoForm()
    return render(request, 'index.html', {'form': form})

def lista_usuarios(request):
    busqueda = request.GET.get('busqueda', '')
    usuarios = UserAcueducto.objects.all()
    
    # Obtener solo las rutas activas
    rutas_activas = Ruta.objects.filter(activa=True).annotate(
        total_ordenes=Count('ordenruta'),
        lecturas_completadas_count=Count('ordenruta', filter=Q(ordenruta__lectura_tomada=True))
    ).prefetch_related('ordenruta_set__usuario')

    if request.method == 'POST' and 'generar_ruta' in request.POST:
        try:
            nombre_ruta = request.POST.get('nombre_ruta')
            usuarios_orden = json.loads(request.POST.get('usuarios_orden', '[]'))
            
            # Call the service to create the new route
            services.crear_nueva_ruta_service(nombre_ruta, usuarios_orden)
            messages.success(request, 'Ruta creada exitosamente')
            return redirect('lista_usuarios')
        except ValueError as ve: # Catch specific error from service for better feedback
            messages.error(request, str(ve))
        except Exception as e: # Catch any other unexpected errors
            messages.error(request, f'Error al crear la ruta: {str(e)}')
    
    if busqueda:
        usuarios = usuarios.filter(
            Q(contrato__icontains=busqueda) |
            Q(address__icontains=busqueda)
        )
    
    return render(request, 'lista_usuarios.html', {
        'usuarios': usuarios,
        'busqueda': busqueda,
        'rutas_activas': rutas_activas
    })

# generar_pdf_factura and enviar_factura_email moved to utils.py
# generar_todas_facturas moved to services.py

def generar_factura_individual(contrato, fecha_emision, periodo_inicio, periodo_fin):
    """Genera una factura individual"""
    if not all([periodo_inicio, periodo_fin]):
        raise ValueError('Por favor, especifique el período de facturación')
    
    periodo_inicio_fecha = datetime.strptime(periodo_inicio, '%Y-%m-%d')
    periodo_fin_fecha = datetime.strptime(periodo_fin, '%Y-%m-%d')
    periodo_facturacion = f"Del {utils.formatear_fecha_espanol(periodo_inicio_fecha)} al {utils.formatear_fecha_espanol(periodo_fin_fecha)}"
    
    usuario = get_object_or_404(UserAcueducto, contrato=contrato)
    base_url = settings.BASE_DIR / 'acueducto' / 'static'
    
    return utils.generar_pdf_factura( # Updated call
        usuario=usuario,
        fecha_emision=fecha_emision or datetime.now(),
        periodo_facturacion=periodo_facturacion,
        base_url=base_url
    )

# Helper function to generate ZIP of all invoices
def _generar_todas_facturas_zip(periodo_inicio, periodo_fin):
    # Call the service function to get the zip_buffer
    zip_buffer = services.generar_zip_todas_facturas_service(periodo_inicio, periodo_fin)
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="todas_las_facturas.zip"'
    return response

# Helper function to generate PDF response for a single invoice
def _generar_factura_pdf_response(request_post_data):
    pdf_file = generar_factura_individual(
        contrato=request_post_data.get('contrato'),
        fecha_emision=datetime.strptime(request_post_data.get('fecha_emision'), '%Y-%m-%d') if request_post_data.get('fecha_emision') else None,
        periodo_inicio=request_post_data.get('periodo_inicio'),
        periodo_fin=request_post_data.get('periodo_fin')
    )
    with open(pdf_file.name, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="factura_{request_post_data.get("contrato")}.pdf"'
    os.unlink(pdf_file.name)
    return response

# Helper function to send a single invoice via email
def _enviar_factura_email_view(request, request_post_data):
    try:
        pdf_file = generar_factura_individual(
            contrato=request_post_data.get('contrato'),
            fecha_emision=datetime.strptime(request_post_data.get('fecha_emision'), '%Y-%m-%d') if request_post_data.get('fecha_emision') else None,
            periodo_inicio=request_post_data.get('periodo_inicio'),
            periodo_fin=request_post_data.get('periodo_fin')
        )
        usuario = UserAcueducto.objects.get(contrato=request_post_data.get('contrato'))
        utils.enviar_factura_email(usuario, pdf_file.name) # Updated call
        messages.success(request, 'Factura enviada por correo exitosamente')
        os.unlink(pdf_file.name)
    except Exception as e:
        messages.error(request, f'Error al enviar la factura por correo: {str(e)}')
    return redirect('generar_factura')

def generar_factura(request):
    """Vista principal para la generación de facturas"""
    contrato_preseleccionado = request.GET.get('contrato', '')
    fecha_actual = datetime.now()
    
    if request.method == 'POST':
        try:
            if 'generar_todas' in request.POST:
                return _generar_todas_facturas_zip(
                    request.POST.get('periodo_inicio_todas'),
                    request.POST.get('periodo_fin_todas')
                )
            elif 'enviar_email' in request.POST:
                return _enviar_factura_email_view(request, request.POST)
            else:
                return _generar_factura_pdf_response(request.POST)
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

def _get_ruta_context():
    """Fetches active route and calculates completion statistics."""
    try:
        ruta = Ruta.objects.filter(activa=True).annotate(
            total_ordenes=Count('ordenruta'),
            lecturas_completadas_count=Count('ordenruta', filter=Q(ordenruta__lectura_tomada=True))
        ).prefetch_related(
            'ordenruta_set__usuario',
            'ordenruta_set__usuario__lecturas'
        ).first()
        
        # Values for context will now be derived from 'ruta' object itself using its properties or updated method
        # The model's `porcentaje_completado` method will use the annotated fields.
        # We can also directly pass annotated values if needed by the template,
        # but relying on the model method is cleaner if it's correctly updated.

        if ruta:
            # These specific context variables are used in 'toma_lectura.html' currently.
            # Let's ensure they are available. The model method handles percentage.
            context_total_lecturas = ruta.total_ordenes
            context_lecturas_completadas = ruta.lecturas_completadas_count
            context_porcentaje_completado = ruta.porcentaje_completado() # Will use annotations
        else:
            context_total_lecturas = 0
            context_lecturas_completadas = 0
            context_porcentaje_completado = 0
        
        return {
            'ruta_activa': ruta, # The annotated ruta object
            'total_lecturas': context_total_lecturas,
            'lecturas_completadas': context_lecturas_completadas,
            'porcentaje_completado': context_porcentaje_completado
        }
    except Exception as e:
        # Propagate the exception to be caught by the main view
        raise Exception(f'Error al cargar la ruta: {str(e)}')

def _handle_toma_lectura_post(request, ruta_activa):
    """Handles the POST request logic for toma_lectura."""
    mensaje = None
    usuario = None
    historico = None
    contrato = request.POST.get('contrato')
    nueva_lectura = request.POST.get('lectura')
    try:
        usuario = UserAcueducto.objects.get(contrato=contrato)
        from django.utils import timezone
        fecha_actual = timezone.now().date()

        HistoricoLectura.objects.create(
            usuario=usuario,
            lectura=nueva_lectura,
            fecha_lectura=fecha_actual
        )

        usuario.lectura = nueva_lectura
        usuario.fecha_ultima_lectura = fecha_actual # Renamed field
        usuario.save()

        if ruta_activa:
            orden_ruta = ruta_activa.ordenruta_set.filter(usuario=usuario).first()
            if orden_ruta:
                orden_ruta.lectura_tomada = True
                orden_ruta.save()

        mensaje = "Lectura registrada exitosamente"
        historico = usuario.lecturas.all()[:6]

    except UserAcueducto.DoesNotExist:
        mensaje = "Usuario no encontrado"
    except Exception as e:
        # Let the main view's error handler catch this if it's a more general error
        # Or handle specific errors here if needed
        mensaje = f"Error al procesar la lectura: {str(e)}"

    return mensaje, usuario, historico

def _handle_toma_lectura_get_contrato(request):
    """Handles the GET request logic when 'contrato' is present for toma_lectura."""
    mensaje = None
    usuario = None
    historico = None
    contrato = request.GET.get('contrato')
    try:
        usuario = UserAcueducto.objects.get(contrato=contrato)
        historico = usuario.lecturas.all()[:6]
    except UserAcueducto.DoesNotExist:
        mensaje = "Usuario no encontrado"
    except Exception as e:
        mensaje = f"Error al buscar usuario: {str(e)}"

    return mensaje, usuario, historico

@login_required(login_url='login')
def toma_lectura(request):
    mensaje = None
    usuario = None
    historico = None
    context = {}

    try:
        ruta_context = _get_ruta_context()
        context.update(ruta_context) # Add ruta_activa, total_lecturas, etc.

        if request.method == 'POST':
            mensaje, usuario, historico = _handle_toma_lectura_post(request, context.get('ruta_activa'))
        
        elif request.method == 'GET':
            if 'contrato' in request.GET:
                mensaje, usuario, historico = _handle_toma_lectura_get_contrato(request)

        context.update({
            'mensaje': mensaje,
            'usuario': usuario,
            'historico': historico,
        })
        
        return render(request, 'toma_lectura.html', context)
        
    except Exception as e:
        # This will catch errors from _get_ruta_context or any other unforeseen error
        messages.error(request, str(e)) # Use str(e) directly as it's already formatted
        # Render with minimal context in case of error during route loading
        # or provide a specific error template/handling
        return render(request, 'toma_lectura.html', {'mensaje': str(e)})

@require_POST
def guardar_lectura(request):
    try:
        data = json.loads(request.body)
        usuario_id = data.get('usuario_id')
        lectura = data.get('lectura')

        usuario = get_object_or_404(UserAcueducto, id=usuario_id)
        fecha_actual = datetime.now().date()

        # Guardar la lectura en el histórico
        HistoricoLectura.objects.create(
            usuario=usuario,
            lectura=lectura,
            fecha_lectura=fecha_actual
        )

        # Actualizar la lectura actual del usuario
        usuario.lectura = lectura
        usuario.fecha_ultima_lectura = fecha_actual # Renamed field
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

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def finalizar_ruta(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ruta_id = data.get('ruta_id')

            if not ruta_id:
                return JsonResponse({'error': 'ruta_id es requerido'}, status=400)

            success, message, ruta_obj = services.finalizar_ruta_service(ruta_id)

            if success:
                return JsonResponse({
                    'message': message,
                    'redirect': '/toma-lectura/' # Or reverse('toma_lectura')
                })
            else:
                return JsonResponse({'error': message}, status=400)
            
        except Ruta.DoesNotExist: # Or Http404 if get_object_or_404 is used in service and not caught there
             return JsonResponse({'error': 'Ruta no encontrada.'}, status=404)
        except Exception as e:
            # Log the exception e for server-side review
            return JsonResponse({'error': f'Error interno del servidor: {str(e)}'}, status=500)
            
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

@login_required(login_url='login')
def modificar_usuario(request):
    contrato_busqueda = request.GET.get('contrato')
    usuario = None
    form = None

    if contrato_busqueda:
        usuario = get_object_or_404(UserAcueducto, contrato=contrato_busqueda)

    if request.method == 'POST':
        # Ensure 'usuario' is fetched if not already by GET 'contrato' (e.g., if form submitted without GET param)
        # This might happen if the form action URL doesn't include the GET parameter.
        # However, standard practice is to include it or fetch via a hidden input if necessary.
        # For this refactor, we assume 'contrato_busqueda' (from GET) or 'contrato' (from POST hidden field if any) helps identify the user.
        # If 'usuario' is None here, it means no 'contrato' was in GET to pre-fill.
        # A POST request should ideally provide the user's ID/contrato to update.
        # If 'contrato' is part of the form, then request.POST['contrato'] would be the identifier.
        # Let's assume the form is for a specific user identified by 'contrato_busqueda' from GET.
        
        if usuario: # User must be identified to update
            form = UserAcueductoForm(request.POST, instance=usuario)
            if form.is_valid():
                form.save()
                messages.success(request, 'Usuario actualizado exitosamente')
                # Redirect to the same page with GET param to show updated data
                return redirect(f"{request.path}?contrato={usuario.contrato}")
            else:
                messages.error(request, 'Error al actualizar usuario. Por favor, revise los datos.')
        else:
            # This case should ideally not happen if the page is designed to always have a user context for POST.
            messages.error(request, 'No se especificó un usuario para actualizar.')
            return redirect('lista_usuarios') # Or some other appropriate redirect

    else: # GET request
        if usuario:
            form = UserAcueductoForm(instance=usuario)
        else:
            # Optionally, provide an empty form or a message if no 'contrato' is in GET
            # For now, form remains None if no 'contrato' in GET, template should handle this.
            # Or, redirect if 'contrato' is always expected:
            # return redirect('lista_usuarios')
            # Or, show an unbound form:
            form = UserAcueductoForm() # Shows an empty form if no contrato in GET

    return render(request, 'modificar_usuario.html', {
        'form': form, # Pass form to template
        'usuario': usuario, # Still pass usuario for display purposes (e.g., name in title)
        'contrato_busqueda': contrato_busqueda
    })


