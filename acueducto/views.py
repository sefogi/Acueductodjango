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
import tempfile
import os
from io import BytesIO
import zipfile
import json
from .models import UserAcueducto, HistoricoLectura, Ruta, OrdenRuta
from .utils import formatear_fecha_espanol

# Create your views here.
def index(request):
    usuario_creado = None
    if request.method == 'POST':
        try:
            usuario_creado = UserAcueducto.objects.create(
                contrato=request.POST['contrato'],
                date=request.POST['date'] or None,
                name=request.POST['name'],
                lastname=request.POST['lastname'],
                email=request.POST['email'],
                phone=request.POST['phone'],
                address=request.POST['address'],
                lectura=request.POST['lectura'] or None,
                categoria=request.POST['categoria'],
                zona=request.POST['zona']
            )
            messages.success(request, 'Usuario creado exitosamente')
        except Exception as e:
            messages.error(request, f'Error al crear usuario: {str(e)}')
    return render(request, 'index.html', {'usuario_creado': usuario_creado})

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
            
            # Eliminar todas las rutas existentes antes de crear una nueva
            Ruta.objects.all().delete()
            
            # Crear la nueva ruta
            ruta = Ruta.objects.create(nombre=nombre_ruta)
            
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
            Q(address__icontains=busqueda)
        )
    
    return render(request, 'lista_usuarios.html', {
        'usuarios': usuarios,
        'busqueda': busqueda,
        'rutas_activas': rutas_activas
    })

def generar_pdf_factura(usuario, fecha_emision, periodo_facturacion, base_url):
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
    
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        for usuario in UserAcueducto.objects.all():
            try:
                pdf_file = generar_pdf_factura(
                    usuario=usuario,
                    fecha_emision=datetime.now(),
                    periodo_facturacion=periodo_facturacion,
                    base_url=base_url
                )
                
                with open(pdf_file.name, 'rb') as pdf:
                    zip_file.writestr(f'factura_{usuario.contrato}.pdf', pdf.read())
                
                os.unlink(pdf_file.name)
            except Exception as e:
                raise Exception(f'Error al generar factura para {usuario.contrato}: {str(e)}')
    
    return zip_buffer

def generar_factura_individual(contrato, fecha_emision, periodo_inicio, periodo_fin):
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
        fecha_emision=fecha_emision or datetime.now(),
        periodo_facturacion=periodo_facturacion,
        base_url=base_url
    )

def generar_factura(request):
    """Vista principal para la generación de facturas"""
    contrato_preseleccionado = request.GET.get('contrato', '')
    fecha_actual = datetime.now()
    
    if request.method == 'POST':
        try:
            if 'generar_todas' in request.POST:
                zip_buffer = generar_todas_facturas(
                    request.POST.get('periodo_inicio_todas'),
                    request.POST.get('periodo_fin_todas')
                )
                
                response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
                response['Content-Disposition'] = 'attachment; filename="todas_las_facturas.zip"'
                return response
            else:
                pdf_file = generar_factura_individual(
                    contrato=request.POST.get('contrato'),
                    fecha_emision=datetime.strptime(request.POST.get('fecha_emision'), '%Y-%m-%d') if request.POST.get('fecha_emision') else None,
                    periodo_inicio=request.POST.get('periodo_inicio'),
                    periodo_fin=request.POST.get('periodo_fin')
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

@login_required(login_url='login')
def toma_lectura(request):
    mensaje = None
    usuario = None
    historico = None
    
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
                from django.utils import timezone
                fecha_actual = timezone.now().date()
                
                # Crear el histórico de lectura
                HistoricoLectura.objects.create(
                    usuario=usuario,
                    lectura=nueva_lectura,
                    fecha_lectura=fecha_actual
                )
                
                # Actualizar la lectura actual del usuario
                usuario.lectura = nueva_lectura
                usuario.date = fecha_actual
                usuario.save()
                
                # Actualizar el estado de la lectura en la ruta si existe
                if ruta:
                    orden_ruta = ruta.ordenruta_set.filter(usuario=usuario).first()
                    if orden_ruta:
                        orden_ruta.lectura_tomada = True
                        orden_ruta.save()
                
                mensaje = "Lectura registrada exitosamente"
                historico = usuario.lecturas.all()[:6]
                
            except UserAcueducto.DoesNotExist:
                mensaje = "Usuario no encontrado"
        
        elif request.method == 'GET':
            contrato = request.GET.get('contrato')
            if contrato:
                try:
                    usuario = UserAcueducto.objects.get(contrato=contrato)
                    historico = usuario.lecturas.all()[:6]
                except UserAcueducto.DoesNotExist:
                    mensaje = "Usuario no encontrado"

        context = {
            'mensaje': mensaje,
            'usuario': usuario,
            'historico': historico,
            'ruta_activa': ruta,
            'total_lecturas': total_lecturas,
            'lecturas_completadas': lecturas_completadas,
            'porcentaje_completado': porcentaje_completado
        }
        
        return render(request, 'toma_lectura.html', context)
        
    except Exception as e:
        messages.error(request, f'Error al cargar la ruta: {str(e)}')
        return render(request, 'toma_lectura.html')

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
        usuario.date = fecha_actual
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
            
            ruta = get_object_or_404(Ruta, id=ruta_id)
            
            # Verificar que todas las lecturas estén tomadas
            lecturas_pendientes = ruta.ordenruta_set.filter(lectura_tomada=False).exists()
            if lecturas_pendientes:
                return JsonResponse({
                    'error': 'No se puede finalizar la ruta. Hay lecturas pendientes.'
                }, status=400)
            
            # Marcar la ruta como finalizada
            from django.utils import timezone
            ruta.activa = False
            ruta.fecha_finalizacion = timezone.now()
            ruta.save()
            
            return JsonResponse({
                'message': 'Ruta finalizada exitosamente',
                'redirect': '/toma-lectura/'
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error al finalizar la ruta: {str(e)}'
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

@login_required(login_url='login')
def modificar_usuario(request):
    contrato_busqueda = request.GET.get('contrato')
    usuario = None
    if contrato_busqueda:
        usuario = get_object_or_404(UserAcueducto, contrato=contrato_busqueda)
    
    if request.method == 'POST':
        contrato = request.POST.get('contrato')
        usuario = get_object_or_404(UserAcueducto, contrato=contrato)
        
        try:
            # Actualizar los campos básicos
            usuario.name = request.POST.get('name')
            usuario.lastname = request.POST.get('lastname')
            usuario.email = request.POST.get('email')
            usuario.phone = request.POST.get('phone')
            usuario.address = request.POST.get('address')
            usuario.categoria = request.POST.get('categoria')
            usuario.zona = request.POST.get('zona')
            
            # Actualizar crédito y otros gastos
            usuario.credito = request.POST.get('credito', 0)
            usuario.credito_descripcion = request.POST.get('credito_descripcion', '')
            usuario.otros_gastos_valor = request.POST.get('otros_gastos_valor', 0)
            usuario.otros_gastos_descripcion = request.POST.get('otros_gastos_descripcion', '')
            
            usuario.save()
            messages.success(request, 'Usuario actualizado exitosamente')
            
        except Exception as e:
            messages.error(request, f'Error al actualizar usuario: {str(e)}')
    
    return render(request, 'modificar_usuario.html', {
        'usuario': usuario,
        'contrato_busqueda': contrato_busqueda
    })


