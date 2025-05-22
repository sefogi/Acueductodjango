from django.shortcuts import render, redirect, get_object_or_404
from .models import UserAcueducto
from django.contrib import messages
from django.db.models import Q
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.core.mail import EmailMessage
from django.conf import settings
from weasyprint import HTML
from django.template.loader import get_template
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
            # Código existente para generar factura individual
            contrato = request.POST.get('contrato')
            usuario = get_object_or_404(UserAcueducto, contrato=contrato)
            
            template = get_template('factura_template.html')
            context = {'usuario': usuario}
            html = template.render(context)
            
            pdf_file = None
            try:
                pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                HTML(string=html).write_pdf(pdf_file.name)
                
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
                    
    usuarios = UserAcueducto.objects.all()
    return render(request, 'generar_factura.html', {
        'usuarios': usuarios,
        'contrato_preseleccionado': contrato_preseleccionado
    })


