from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import UserAcueducto, HistoricoLectura
from django.contrib import messages
from django.db.models import Q
from django.template.loader import render_to_string
from django.http import HttpResponse, JsonResponse
from django.core.mail import EmailMessage
from django.conf import settings
from weasyprint import HTML
from django.template.loader import get_template
from datetime import datetime
import tempfile
import os
from io import BytesIO
import zipfile


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
                lectura=request.POST['lectura'] or None
            )
            messages.success(request, 'Usuario creado exitosamente')
        except Exception as e:
            messages.error(request, f'Error al crear usuario: {str(e)}')

    return render(request, 'index.html', {'usuario_creado': usuario_creado})


def lista_usuarios(request):
    busqueda = request.GET.get('busqueda', '')
    usuarios = UserAcueducto.objects.all()

    if busqueda:
        usuarios = usuarios.filter(
            Q(contrato__icontains=busqueda) |
            Q(address__icontains=busqueda)
        )

    return render(request, 'lista_usuarios.html', {
        'usuarios': usuarios,
        'busqueda': busqueda
    })


def generar_factura(request):
    contrato_preseleccionado = request.GET.get('contrato', '')
    busqueda_contrato = request.GET.get('busqueda_contrato', '')
    fecha_actual = datetime.now()
    
    if request.method == 'POST':
        if 'generar_todas' in request.POST:
            # Generar ZIP con todas las facturas
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                for usuario in UserAcueducto.objects.all():
                    try:
                        # Generar PDF para cada usuario
                        template = get_template('factura_template.html')
                        context = {'usuario': usuario}
                        html = template.render(context)
                        
                        pdf_buffer = BytesIO()
                        HTML(string=html).write_pdf(pdf_buffer)
                        
                        # Añadir PDF al ZIP
                        zip_file.writestr(
                            f'factura_{usuario.contrato}.pdf',
                            pdf_buffer.getvalue()
                        )
                    except Exception as e:
                        messages.error(request, f'Error al generar factura para {usuario.contrato}: {str(e)}')
            
            # Devolver el archivo ZIP
            response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="todas_las_facturas.zip"'
            return response
        
        else:
            # Código para generar factura individual
            contrato = request.POST.get('contrato')
            fecha_emision = request.POST.get('fecha_emision', datetime.now().strftime('%Y-%m-%d'))
            usuario = get_object_or_404(UserAcueducto, contrato=contrato)
            
            # Obtener el histórico de lecturas ordenado por fecha
            historico_lecturas = usuario.lecturas.all().order_by('-fecha_lectura')[:6]
            
            # Obtener la lectura anterior si existe
            lectura_anterior = None
            if len(historico_lecturas) > 1:
                lectura_anterior = historico_lecturas[1]
            
            template = get_template('factura_template.html')
            context = {
                'usuario': usuario,
                'historico_lecturas': historico_lecturas,
                'lectura_anterior': lectura_anterior,
                'fecha_emision': fecha_emision,
            }
            html = template.render(context)
            
            pdf_file = None
            try:
                pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                base_url = settings.BASE_DIR / 'acueducto' / 'static'
                HTML(string=html, base_url=str(base_url)).write_pdf(pdf_file.name)
                
                if 'enviar_email' in request.POST:
                    try:
                        email = EmailMessage(
                            'Factura del Acueducto',
                            'Adjunto encontrará su factura.',
                            settings.DEFAULT_FROM_EMAIL,
                            [usuario.email]
                        )
                        email.attach_file(pdf_file.name)
                        email.send()
                        messages.success(request, 'Factura enviada por correo exitosamente')
                        return redirect('generar_factura')
                    except Exception as e:
                        messages.error(request, f'Error al enviar el correo: {str(e)}')
                        return redirect('generar_factura')
                
                with open(pdf_file.name, 'rb') as pdf:
                    response = HttpResponse(pdf.read(), content_type='application/pdf')
                    response['Content-Disposition'] = f'inline; filename="factura_{usuario.contrato}.pdf"'
                    return response
                    
            except Exception as e:
                messages.error(request, f'Error al generar la factura: {str(e)}')
                return redirect('generar_factura')
            finally:
                if pdf_file and os.path.exists(pdf_file.name):
                    os.unlink(pdf_file.name)
                    
    usuarios = UserAcueducto.objects.all().order_by('contrato')
    
    # Si hay una búsqueda de contrato, filtramos los usuarios
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
            
            mensaje = "Lectura registrada exitosamente"
            historico = usuario.lecturas.all()[:6]  # Obtener las últimas 6 lecturas
            
        except UserAcueducto.DoesNotExist:
            mensaje = "Usuario no encontrado"
    
    elif request.method == 'GET':
        contrato = request.GET.get('contrato')
        if contrato:
            try:
                usuario = UserAcueducto.objects.get(contrato=contrato)
                historico = usuario.lecturas.all()[:6]  # Obtener las últimas 6 lecturas
            except UserAcueducto.DoesNotExist:
                mensaje = "Usuario no encontrado"
    
    return render(request, 'toma_lectura.html', {
        'mensaje': mensaje,
        'usuario': usuario,
        'historico': historico
    })

def historico_lecturas(request, contrato):
    usuario = get_object_or_404(UserAcueducto, contrato=contrato)
    historico = list(usuario.lecturas.all().order_by('-fecha_lectura'))
    
    return render(request, 'historico_lecturas.html', {
        'usuario': usuario,
        'historico': historico
    })


