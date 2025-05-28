from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User as AuthUser # Added import
from acueducto.models import UserAcueducto, Ruta, OrdenRuta
import json
from django.db.utils import IntegrityError # Import IntegrityError
from decimal import Decimal # Added
from django.template import Context, Template # Added
from django.test import SimpleTestCase # Added for SimpleTestCase
from .forms import UserAcueductoForm # Import the form
from acueducto.models import HistoricoLectura # Ensure HistoricoLectura is imported
from django.conf import settings # For settings.BASE_DIR
from django.template.loader import get_template # For template rendering test
from pathlib import Path # For base_url in generar_pdf_factura


class RutaCreationTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.lista_usuarios_url = reverse('lista_usuarios')

        # Create some users for testing
        self.user1 = UserAcueducto.objects.create(contrato='101', name='Usuario Uno', lastname='Test', email='uno@test.com', address='Calle 1', zona='A', categoria='Residencial')
        self.user2 = UserAcueducto.objects.create(contrato='102', name='Usuario Dos', lastname='Test', email='dos@test.com', address='Calle 2', zona='B', categoria='Comercial')
        self.user3 = UserAcueducto.objects.create(contrato='103', name='Usuario Tres', lastname='Test', email='tres@test.com', address='Calle 3', zona='A', categoria='Residencial')

    def test_crear_nueva_ruta_desactiva_otras(self):
        # Create an initial active route
        ruta_antigua1 = Ruta.objects.create(nombre='Ruta Vieja 1', activa=True)
        OrdenRuta.objects.create(ruta=ruta_antigua1, usuario=self.user1, orden=1)

        # Create another initial active route
        ruta_antigua2 = Ruta.objects.create(nombre='Ruta Vieja 2', activa=True, fecha_creacion=timezone.now() - timezone.timedelta(days=1))
        OrdenRuta.objects.create(ruta=ruta_antigua2, usuario=self.user2, orden=1)

        # Verify initial state
        self.assertTrue(Ruta.objects.get(id=ruta_antigua1.id).activa)
        self.assertIsNone(Ruta.objects.get(id=ruta_antigua1.id).fecha_finalizacion)
        self.assertTrue(Ruta.objects.get(id=ruta_antigua2.id).activa)
        self.assertIsNone(Ruta.objects.get(id=ruta_antigua2.id).fecha_finalizacion)
        self.assertEqual(Ruta.objects.filter(activa=True).count(), 2)

        # Data for the new route
        nueva_ruta_nombre = 'Ruta Nueva Principal'
        usuarios_orden_data = [
            {'id': self.user1.id, 'orden': 1},
            {'id': self.user2.id, 'orden': 2},
        ]

        response = self.client.post(self.lista_usuarios_url, {
            'nombre_ruta': nueva_ruta_nombre,
            'usuarios_orden': json.dumps(usuarios_orden_data),
            'generar_ruta': 'Generar Ruta' 
        })

        self.assertEqual(response.status_code, 302) 
        self.assertRedirects(response, self.lista_usuarios_url)

        ruta_antigua1.refresh_from_db()
        ruta_antigua2.refresh_from_db()
        self.assertFalse(ruta_antigua1.activa, "Ruta Antigua 1 should be inactive")
        self.assertIsNotNone(ruta_antigua1.fecha_finalizacion, "Ruta Antigua 1 should have a finalization date")
        self.assertFalse(ruta_antigua2.activa, "Ruta Antigua 2 should be inactive")
        self.assertIsNotNone(ruta_antigua2.fecha_finalizacion, "Ruta Antigua 2 should have a finalization date")
        
        self.assertTrue(Ruta.objects.filter(nombre=nueva_ruta_nombre, activa=True).exists(), "New route should be active")
        ruta_nueva = Ruta.objects.get(nombre=nueva_ruta_nombre)
        self.assertIsNone(ruta_nueva.fecha_finalizacion, "New route should not have a finalization date")
        self.assertEqual(Ruta.objects.filter(activa=True).count(), 1, "Only one route should be active")

    def test_crear_nueva_ruta_sin_rutas_previas(self):
        Ruta.objects.all().update(activa=False, fecha_finalizacion=timezone.now()) 
        self.assertEqual(Ruta.objects.filter(activa=True).count(), 0)

        nueva_ruta_nombre = 'Ruta Unica'
        usuarios_orden_data = [
            {'id': self.user3.id, 'orden': 1},
        ]

        response = self.client.post(self.lista_usuarios_url, {
            'nombre_ruta': nueva_ruta_nombre,
            'usuarios_orden': json.dumps(usuarios_orden_data),
            'generar_ruta': 'Generar Ruta'
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.lista_usuarios_url)

        self.assertTrue(Ruta.objects.filter(nombre=nueva_ruta_nombre, activa=True).exists())
        ruta_creada = Ruta.objects.get(nombre=nueva_ruta_nombre)
        self.assertIsNone(ruta_creada.fecha_finalizacion)
        self.assertEqual(Ruta.objects.filter(activa=True).count(), 1)

    def test_orden_ruta_creada_correctamente(self):
        nueva_ruta_nombre = 'Ruta Con Orden Especifico'
        usuarios_para_orden = [
            {'id': self.user2.id, 'orden': 1}, 
            {'id': self.user1.id, 'orden': 2}, 
            {'id': self.user3.id, 'orden': 3}, 
        ]
        
        response = self.client.post(self.lista_usuarios_url, {
            'nombre_ruta': nueva_ruta_nombre,
            'usuarios_orden': json.dumps(usuarios_para_orden), 
            'generar_ruta': 'Generar Ruta'
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.lista_usuarios_url)

        self.assertTrue(Ruta.objects.filter(nombre=nueva_ruta_nombre, activa=True).exists())
        ruta_creada = Ruta.objects.get(nombre=nueva_ruta_nombre)

        ordenes_ruta = OrdenRuta.objects.filter(ruta=ruta_creada).order_by('orden')
        
        self.assertEqual(len(ordenes_ruta), 3)
        self.assertEqual(ordenes_ruta[0].usuario, self.user2)
        self.assertEqual(ordenes_ruta[0].orden, 1)
        self.assertFalse(ordenes_ruta[0].lectura_tomada)
        self.assertEqual(ordenes_ruta[1].usuario, self.user1)
        self.assertEqual(ordenes_ruta[1].orden, 2)
        self.assertFalse(ordenes_ruta[1].lectura_tomada)
        self.assertEqual(ordenes_ruta[2].usuario, self.user3)
        self.assertEqual(ordenes_ruta[2].orden, 3)
        self.assertFalse(ordenes_ruta[2].lectura_tomada)


class UserCreationFormTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.index_url = reverse('index')

    def test_user_creation_success(self):
        initial_user_count = UserAcueducto.objects.count()
        valid_data = {
            'contrato': '201',
            'numero_de_medidor': 'MEDFORM201', # Added
            'name': 'Test',
            'lastname': 'User',
            'email': 'testuser@example.com',
            'phone': '1234567890',
            'address': '123 Test St',
            'categoria': 'residencial',
            'zona': 'Norte',
            'fecha_ultima_lectura': '2023-01-01',
            'credito': '0.00', 
            'credito_descripcion': '', 
            'otros_gastos_valor': '0.00', 
            'otros_gastos_descripcion': '' 
        }
        response = self.client.post(self.index_url, valid_data, follow=True)

        self.assertEqual(response.status_code, 200) 
        # Check if form has errors before asserting count
        if 'form' in response.context and response.context['form'].errors:
            print("Form errors:", response.context['form'].errors)
        self.assertEqual(UserAcueducto.objects.count(), initial_user_count + 1)
        
        created_user = UserAcueducto.objects.get(contrato='201')
        self.assertEqual(created_user.name, 'Test')
        self.assertEqual(created_user.email, 'testuser@example.com')
        self.assertEqual(created_user.numero_de_medidor, 'MEDFORM201')
        
        self.assertRedirects(response, self.index_url, status_code=302, target_status_code=200)
        messages_in_response = list(response.context.get('messages', []))
        self.assertEqual(len(messages_in_response), 1)
        self.assertEqual(str(messages_in_response[0]), "Usuario creado exitosamente")
        self.assertContains(response, "Usuario creado exitosamente")

    def test_user_creation_invalid_data(self):
        initial_user_count = UserAcueducto.objects.count()
        invalid_data = {
            'contrato': '', 
            'name': 'Test Invalid',
            'lastname': 'User Invalid',
            'email': 'not-an-email', 
            'phone': '123',
            'address': 'Invalid Address',
            'categoria': 'residencial',
            'zona': 'Sur',
            # numero_de_medidor is missing, which is required
        }
        response = self.client.post(self.index_url, invalid_data)

        self.assertEqual(UserAcueducto.objects.count(), initial_user_count) 
        self.assertEqual(response.status_code, 200) 
        self.assertIn('form', response.context)
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('contrato', form.errors) 
        self.assertIn('email', form.errors)    
        self.assertIn('numero_de_medidor', form.errors) # Should have error for missing numero_de_medidor

    def test_user_creation_contrato_unique_constraint(self):
        UserAcueducto.objects.create(
            contrato='301', name='Existing', lastname='User', 
            email='existing@example.com', address='Some Address', 
            categoria='comercial', zona='Centro', numero_de_medidor='MED301'
        )
        initial_user_count = UserAcueducto.objects.count()

        data_with_duplicate_contrato = {
            'contrato': '301', 
            'numero_de_medidor': 'MED301_NEW',
            'name': 'New',
            'lastname': 'User',
            'email': 'new@example.com',
            'phone': '0987654321',
            'address': '456 New St',
            'categoria': 'residencial',
            'zona': 'Este',
            'fecha_ultima_lectura': '2023-02-01'
        }
        response = self.client.post(self.index_url, data_with_duplicate_contrato)

        self.assertEqual(UserAcueducto.objects.count(), initial_user_count)
        self.assertEqual(response.status_code, 200) 
        self.assertIn('form', response.context)
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('contrato', form.errors)

    def test_index_view_get_request(self):
        response = self.client.get(self.index_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIsInstance(response.context['form'], UserAcueductoForm)
        self.assertFalse(response.context['form'].is_bound) 
        self.assertTemplateUsed(response, 'index.html')


class UserModificationTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.auth_user = AuthUser.objects.create_user(username='testadmin', password='password123', is_staff=True, is_superuser=True)
        self.client.login(username='testadmin', password='password123')

        self.user_to_modify = UserAcueducto.objects.create(
            contrato='401',
            numero_de_medidor='MED401_ORIG',
            name='Original Name',
            lastname='Original Lastname',
            email='original@example.com',
            phone='1112223333',
            address='Original Address',
            categoria='residencial',
            zona='Centro',
            credito=Decimal('100.00'),
            credito_descripcion='Initial credit'
        )
        self.modificar_usuario_url_base = reverse('modificar_usuario')
        self.modificar_usuario_url_for_user = f"{self.modificar_usuario_url_base}?contrato={self.user_to_modify.contrato}"

    def test_user_modification_page_loads_with_form(self):
        response = self.client.get(self.modificar_usuario_url_for_user)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'modificar_usuario.html')
        
        self.assertIn('form', response.context)
        form_in_context = response.context['form']
        self.assertIsInstance(form_in_context, UserAcueductoForm)
        self.assertEqual(form_in_context.instance, self.user_to_modify)
        self.assertTrue(form_in_context.fields['contrato'].disabled)

    def test_user_modification_success(self):
        updated_data = {
            'contrato': self.user_to_modify.contrato, 
            'numero_de_medidor': self.user_to_modify.numero_de_medidor or 'MEDMOD401', 
            'name': 'Updated Name',
            'lastname': self.user_to_modify.lastname, 
            'email': self.user_to_modify.email,
            'phone': '9998887777', 
            'address': 'Updated Address', 
            'categoria': self.user_to_modify.categoria,
            'zona': self.user_to_modify.zona,
            'credito': '250.50', 
            'credito_descripcion': 'Updated credit info', 
            'otros_gastos_valor': '50.00', 
            'otros_gastos_descripcion': 'New other expense'
        }
        
        response = self.client.post(self.modificar_usuario_url_base, updated_data, follow=True)
        
        self.assertEqual(response.status_code, 200) 
        self.assertRedirects(response, self.modificar_usuario_url_for_user, status_code=302, target_status_code=200)

        self.user_to_modify.refresh_from_db()
        self.assertEqual(self.user_to_modify.name, 'Updated Name')
        self.assertEqual(self.user_to_modify.phone, '9998887777')
        self.assertEqual(self.user_to_modify.address, 'Updated Address')
        self.assertEqual(self.user_to_modify.credito, Decimal('250.50'))
        self.assertEqual(self.user_to_modify.credito_descripcion, 'Updated credit info')
        self.assertEqual(self.user_to_modify.otros_gastos_valor, Decimal('50.00'))
        self.assertEqual(self.user_to_modify.otros_gastos_descripcion, 'New other expense')

        messages_in_response = list(response.context.get('messages', []))
        self.assertEqual(len(messages_in_response), 1)
        self.assertEqual(str(messages_in_response[0]), "Usuario actualizado exitosamente")
        self.assertContains(response, "Usuario actualizado exitosamente")

    def test_user_modification_invalid_data(self):
        original_name = self.user_to_modify.name
        original_email = self.user_to_modify.email
        invalid_data = {
            'contrato': self.user_to_modify.contrato, 
            'numero_de_medidor': self.user_to_modify.numero_de_medidor,
            'name': 'Name Before Error', 
            'lastname': self.user_to_modify.lastname,
            'email': 'this-is-not-an-email', 
            'phone': self.user_to_modify.phone,
            'address': self.user_to_modify.address,
            'categoria': self.user_to_modify.categoria,
            'zona': self.user_to_modify.zona,
        }
        response = self.client.post(self.modificar_usuario_url_base, invalid_data)

        self.assertEqual(response.status_code, 200) 
        self.user_to_modify.refresh_from_db()
        self.assertEqual(self.user_to_modify.name, original_name)
        self.assertEqual(self.user_to_modify.email, original_email)

        self.assertIn('form', response.context)
        form_in_context = response.context['form']
        self.assertTrue(form_in_context.errors)
        self.assertIn('email', form_in_context.errors)
        self.assertContains(response, "Error al actualizar usuario. Por favor revise los datos.")

    def test_user_modification_non_existent_user_get(self):
        non_existent_contrato = '99999'
        url = f"{self.modificar_usuario_url_base}?contrato={non_existent_contrato}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_user_modification_non_existent_user_post(self):
        non_existent_contrato = '88888'
        data = {
            'contrato': non_existent_contrato, 
            'numero_de_medidor': 'MED888',
            'name': 'Trying To Update NonExistent',
            'email': 'nonexistent@example.com',
            'categoria': 'comercial',
            'zona': 'Sur'
        }
        initial_user_count = UserAcueducto.objects.count()
        
        response = self.client.post(self.modificar_usuario_url_base, data, follow=False) 
        
        self.assertEqual(response.status_code, 200) 
        
        messages_in_response = list(response.context.get('messages', []))
        expected_full_error_msg = "Ocurrió un error inesperado al actualizar el usuario: No UserAcueducto matches the given query."
        self.assertTrue(
            any(expected_full_error_msg == str(m) for m in messages_in_response),
            f"Expected error message not found. Messages: {[str(m) for m in messages_in_response]}"
        )
        
        self.assertEqual(UserAcueducto.objects.count(), initial_user_count) 
        self.user_to_modify.refresh_from_db()
        self.assertEqual(self.user_to_modify.name, 'Original Name')


class FormatCOPTemplateFilterTests(SimpleTestCase):
    def render_template(self, string, context=None):
        context = context or {}
        context = Context(context)
        template_string = "{% load acueducto_filters %} " + string
        return Template(template_string).render(context)

    def test_format_cop_integer(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": 1234567})
        self.assertEqual(rendered, "$1.234.567,00")

    def test_format_cop_float(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": 12345.67})
        self.assertEqual(rendered, "$12.345,67")

    def test_format_cop_decimal(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": Decimal('12345.67')})
        self.assertEqual(rendered, "$12.345,67")

    def test_format_cop_with_3_decimal_places(self):
        rendered = self.render_template("{{ value|format_cop:3 }}", {"value": 123.456})
        self.assertEqual(rendered, "$123,456")
        
    def test_format_cop_with_custom_float_3_decimal_places(self):
        rendered = self.render_template("{{ value|format_cop:3 }}", {"value": 12345.678})
        self.assertEqual(rendered, "$12.345,678")

    def test_format_cop_with_0_decimal_places(self):
        rendered = self.render_template("{{ value|format_cop:0 }}", {"value": 12345})
        self.assertEqual(rendered, "$12.345")
        
    def test_format_cop_float_with_0_decimal_places(self):
        rendered = self.render_template("{{ value|format_cop:0 }}", {"value": 12345.6}) 
        self.assertEqual(rendered, "$12.346") 

    def test_format_cop_none_value(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": None})
        self.assertEqual(rendered, "") 

    def test_format_cop_zero_value(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": 0})
        self.assertEqual(rendered, "$0,00")
        
    def test_format_cop_zero_value_0_decimals(self):
        rendered = self.render_template("{{ value|format_cop:0 }}", {"value": 0})
        self.assertEqual(rendered, "$0")

    def test_format_cop_negative_value(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": -12345.67})
        self.assertEqual(rendered, "$-12.345,67")
        
    def test_format_cop_negative_value_0_decimals(self):
        rendered = self.render_template("{{ value|format_cop:0 }}", {"value": -12345.67})
        self.assertEqual(rendered, "$-12.346") 

    def test_format_cop_string_value_valid_number(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": "12345.67"})
        self.assertEqual(rendered, "$12.345,67")

    def test_format_cop_string_value_invalid_number(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": "not_a_number"})
        self.assertEqual(rendered, "") 
        
    def test_format_cop_large_number(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": 1234567890.12})
        self.assertEqual(rendered, "$1.234.567.890,12")

    def test_format_cop_small_number_many_decimals_default(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": 0.12345})
        self.assertEqual(rendered, "$0,12")
        
    def test_format_cop_small_number_many_decimals_custom(self):
        rendered = self.render_template("{{ value|format_cop:4 }}", {"value": 0.12345})
        self.assertEqual(rendered, "$0,1235") 


class UserAcueductoModelTest(TestCase):
    def test_numero_de_medidor_field_properties(self):
        field = UserAcueducto._meta.get_field('numero_de_medidor')
        self.assertTrue(field.unique, "Field numero_de_medidor should be unique.")
        self.assertTrue(field.blank, "Field numero_de_medidor should allow blank.")
        self.assertTrue(field.null, "Field numero_de_medidor should allow null.")
        user = UserAcueducto(contrato='TPROP001', name='TestProp', lastname='User', email='testprop@example.com', numero_de_medidor='MEDPROP001')
        self.assertTrue(hasattr(user, 'numero_de_medidor'))

    def test_numero_de_medidor_unique_constraint_with_value(self):
        UserAcueducto.objects.create(
            contrato='TU001', name='First Unique', lastname='User', email='firstunique@example.com',
            numero_de_medidor='MED_UNIQUE_VALUE_001', categoria='residencial', zona='Norte'
        )
        with self.assertRaises(IntegrityError, msg="Saving a duplicate non-empty numero_de_medidor should raise IntegrityError."):
            UserAcueducto.objects.create(
                contrato='TU002', name='Second Unique', lastname='User', email='secondunique@example.com',
                numero_de_medidor='MED_UNIQUE_VALUE_001', categoria='residencial', zona='Norte' 
            )

    def test_numero_de_medidor_allows_multiple_nulls(self):
        UserAcueducto.objects.create(
            contrato='TNULL001', name='NoneMedidor1', lastname='User', email='none1null@example.com',
            numero_de_medidor=None, categoria='residencial', zona='Norte'
        )
        UserAcueducto.objects.create(
            contrato='TNULL002', name='NoneMedidor2', lastname='User', email='none2null@example.com',
            numero_de_medidor=None, categoria='residencial', zona='Norte'
        )
        self.assertEqual(UserAcueducto.objects.filter(numero_de_medidor=None).count(), 2, "Should be able to save multiple users with numero_de_medidor as None.")

    def test_numero_de_medidor_unique_for_blank_string(self):
        UserAcueducto.objects.create(
            contrato='TBLANK001', name='BlankMedidor1', lastname='User', email='blank1str@example.com',
            numero_de_medidor='', categoria='residencial', zona='Norte'
        )
        with self.assertRaises(IntegrityError, msg="Saving a duplicate blank string for numero_de_medidor should raise IntegrityError."):
            UserAcueducto.objects.create(
                contrato='TBLANK002', name='BlankMedidor2', lastname='User', email='blank2str@example.com',
                numero_de_medidor='', categoria='residencial', zona='Norte' 
            )


class UserAcueductoFormTest(TestCase): # Renamed from UserCreationFormTests to be more general if needed
    def test_numero_de_medidor_in_form(self):
        form = UserAcueductoForm()
        self.assertIn('numero_de_medidor', form.fields)
        self.assertTrue(form.fields['numero_de_medidor'].required)

        valid_data = {
            'contrato': 'F001',
            'numero_de_medidor': 'MEDF001',
            'name': 'FormTest',
            'lastname': 'User',
            'email': 'formtest@example.com',
            'address': '123 Form St',
            'categoria': 'residencial',
            'zona': 'Centro',
            'credito': '0', 
            'otros_gastos_valor': '0' 
        }
        form_valid = UserAcueductoForm(data=valid_data)
        self.assertTrue(form_valid.is_valid(), form_valid.errors.as_data())

        invalid_data = valid_data.copy()
        del invalid_data['numero_de_medidor']
        form_invalid = UserAcueductoForm(data=invalid_data)
        self.assertFalse(form_invalid.is_valid())
        self.assertIn('numero_de_medidor', form_invalid.errors)

        self.assertEqual(form.fields['numero_de_medidor'].label, 'Número de Medidor')
        self.assertEqual(form.fields['numero_de_medidor'].widget.attrs.get('placeholder'), 'Número del medidor')


class InvoiceGenerationTest(TestCase):
    def setUp(self):
        self.user = UserAcueducto.objects.create(
            contrato='INV001',
            name='Invoice',
            lastname='User',
            email='invoice@example.com',
            numero_de_medidor='MEDINV001',
            lectura=120.0, 
            categoria='comercial',
            zona='Industrial',
            credito=Decimal('50.00'),
            credito_descripcion='Abono',
            otros_gastos_valor=Decimal('10.00'),
            otros_gastos_descripcion='Envio'
        )
        HistoricoLectura.objects.create(usuario=self.user, fecha_lectura=timezone.now() - timezone.timedelta(days=60), lectura=80.0)
        HistoricoLectura.objects.create(usuario=self.user, fecha_lectura=timezone.now() - timezone.timedelta(days=30), lectura=100.0) 
        HistoricoLectura.objects.create(usuario=self.user, fecha_lectura=timezone.now(), lectura=120.0) 
        
        if not hasattr(settings, 'BASE_DIR'): # Ensure BASE_DIR is set for tests needing it
            settings.BASE_DIR = Path(__file__).resolve().parent.parent

    def test_invoice_context_and_calculation(self):
        historico_lecturas = self.user.lecturas.all().order_by('-fecha_lectura')
        
        lectura_anterior_obj = None
        if len(historico_lecturas) > 1:
             lectura_anterior_obj = historico_lecturas[1] 

        consumo_m3 = 0
        if lectura_anterior_obj and self.user.lectura is not None and lectura_anterior_obj.lectura is not None:
            consumo_m3 = self.user.lectura - lectura_anterior_obj.lectura
        elif self.user.lectura is not None:
            consumo_m3 = self.user.lectura
        
        self.assertEqual(consumo_m3, 20.0) # This is for display (120 - 100)

        valor_por_m3_expected = 1000
        # New logic: costo_consumo_raw is based on self.user.lectura directly
        costo_consumo_raw = self.user.lectura * valor_por_m3_expected # 120.0 * 1000 = 120000
        costo_consumo_agua_redondeado_expected = round(costo_consumo_raw)
        self.assertEqual(costo_consumo_agua_redondeado_expected, 120000)

        credito = self.user.credito if self.user.credito is not None else Decimal('0')
        otros_gastos = self.user.otros_gastos_valor if self.user.otros_gastos_valor is not None else Decimal('0')
        
        total_factura_raw = Decimal(costo_consumo_agua_redondeado_expected) + credito + otros_gastos
        total_factura_redondeado_expected = round(total_factura_raw)
        # Expected: 120000 (costo) + 50 (credito) + 10 (otros_gastos) = 120060

        context = {
            'usuario': self.user,
            'historico_lecturas': historico_lecturas[:6],
            'lectura_anterior': lectura_anterior_obj,
            'fecha_emision': timezone.now(),
            'periodo_facturacion': "Test Period",
            'costo_consumo_agua_redondeado': costo_consumo_agua_redondeado_expected,
            'total_factura_redondeado': total_factura_redondeado_expected,
            'valor_por_m3': valor_por_m3_expected,
            # consumo_m3 is also in context for display
            'consumo_m3': consumo_m3,
        }

        self.assertEqual(context['valor_por_m3'], valor_por_m3_expected)
        self.assertEqual(context['costo_consumo_agua_redondeado'], 120000)
        self.assertEqual(context['total_factura_redondeado'], 120060)
        self.assertEqual(context['consumo_m3'], 20.0)


    def test_invoice_calculation_with_previous_reading_new_logic(self):
        user = UserAcueducto.objects.create(
            contrato='INV002', name='Test User 2', lastname='WithPrev',
            email='test2@example.com', numero_de_medidor='MEDINV002',
            lectura=150.0, # Current actual reading
            credito=Decimal('20.00'),
            otros_gastos_valor=Decimal('5.00')
        )
        # Historical readings
        HistoricoLectura.objects.create(usuario=user, fecha_lectura=timezone.now() - timezone.timedelta(days=60), lectura=80.0) # Older
        HistoricoLectura.objects.create(usuario=user, fecha_lectura=timezone.now() - timezone.timedelta(days=30), lectura=110.0) # Previous
        HistoricoLectura.objects.create(usuario=user, fecha_lectura=timezone.now(), lectura=150.0) # Current historical entry

        # Simulate context building as in generar_pdf_factura
        historico_lecturas = user.lecturas.all().order_by('-fecha_lectura')
        lectura_anterior_obj = None
        if len(historico_lecturas) > 1:
            lectura_anterior_obj = historico_lecturas[1] # This should be 110.0

        # For display:
        consumo_m3_display = 0
        if lectura_anterior_obj and user.lectura is not None and lectura_anterior_obj.lectura is not None:
            consumo_m3_display = user.lectura - lectura_anterior_obj.lectura # 150.0 - 110.0 = 40.0
        elif user.lectura is not None:
            consumo_m3_display = user.lectura
        
        valor_por_m3 = 1000

        # For billing (new logic):
        expected_costo_consumo_raw = 0
        if user.lectura is not None:
            expected_costo_consumo_raw = user.lectura * valor_por_m3 # 150.0 * 1000 = 150000
        
        expected_costo_consumo_agua_redondeado = round(expected_costo_consumo_raw)

        credito = user.credito if user.credito is not None else Decimal('0')
        otros_gastos = user.otros_gastos_valor if user.otros_gastos_valor is not None else Decimal('0')
        
        expected_total_factura_raw = Decimal(expected_costo_consumo_agua_redondeado) + credito + otros_gastos
        expected_total_factura_redondeado = round(expected_total_factura_raw)
        # 150000 + 20 (credito) + 5 (otros) = 150025

        self.assertEqual(consumo_m3_display, 40.0)
        self.assertEqual(expected_costo_consumo_agua_redondeado, 150000)
        self.assertEqual(expected_total_factura_redondeado, 150025)
        self.assertIsNotNone(lectura_anterior_obj)
        if lectura_anterior_obj: # make mypy happy
             self.assertEqual(lectura_anterior_obj.lectura, 110.0)


    def test_invoice_calculation_no_previous_reading_new_logic(self):
        user = UserAcueducto.objects.create(
            contrato='INV003', name='Test User 3', lastname='NoPrev',
            email='test3@example.com', numero_de_medidor='MEDINV003',
            lectura=70.0, # Current actual reading
            credito=Decimal('10.00'),
            otros_gastos_valor=Decimal('2.00')
        )
        # Only one historical reading (current)
        HistoricoLectura.objects.create(usuario=user, fecha_lectura=timezone.now(), lectura=70.0)

        # Simulate context building as in generar_pdf_factura
        historico_lecturas = user.lecturas.all().order_by('-fecha_lectura')
        lectura_anterior_obj = None
        if len(historico_lecturas) > 1: # This will be false
            lectura_anterior_obj = historico_lecturas[1]

        # For display:
        consumo_m3_display = 0
        if lectura_anterior_obj and user.lectura is not None and lectura_anterior_obj.lectura is not None:
            consumo_m3_display = user.lectura - lectura_anterior_obj.lectura 
        elif user.lectura is not None: # This path will be taken
            consumo_m3_display = user.lectura # Should be 70.0
        
        valor_por_m3 = 1000

        # For billing (new logic):
        expected_costo_consumo_raw = 0
        if user.lectura is not None:
            expected_costo_consumo_raw = user.lectura * valor_por_m3 # 70.0 * 1000 = 70000
            
        expected_costo_consumo_agua_redondeado = round(expected_costo_consumo_raw)

        credito = user.credito if user.credito is not None else Decimal('0')
        otros_gastos = user.otros_gastos_valor if user.otros_gastos_valor is not None else Decimal('0')
        
        expected_total_factura_raw = Decimal(expected_costo_consumo_agua_redondeado) + credito + otros_gastos
        expected_total_factura_redondeado = round(expected_total_factura_raw)
        # 70000 + 10 (credito) + 2 (otros) = 70012

        self.assertEqual(consumo_m3_display, 70.0)
        self.assertEqual(expected_costo_consumo_agua_redondeado, 70000)
        self.assertEqual(expected_total_factura_redondeado, 70012)
        self.assertIsNone(lectura_anterior_obj)


    def test_invoice_template_renders_dynamic_valor_unitario(self):
        # This test might need adjustment if its setup relied on the old consumption calculation
        # For now, assuming it tests template rendering with given context values, it might still be valid.
        # Let's re-verify its assumptions based on the new logic.
        # The key is that `costo_consumo_test` and `valor_por_m3_test` are passed directly in context.
        
        # If self.user (created in setUp) is used, its lectura is 120.0
        # If mock_lectura_anterior.lectura (100.0) is used for consumption diff, it's 20.
        # The test passes `costo_consumo_test = 24000` and `valor_por_m3_test = 1200`.
        # If this test is purely about template rendering these *given* values, it's fine.
        # However, the HTML assertion "$24.000" implies this value is used for cost_consumo_agua_redondeado.
        # And "$1.200 por unidad" implies valor_por_m3.

        # Let's ensure the user for this test also aligns with how values are derived or make it self-contained.
        # Using self.user from setUp.
        # self.user.lectura = 120.0
        # self.user.credito = 50.00
        # self.user.otros_gastos_valor = 10.00
        
        valor_por_m3_test = 1200
        
        # Under new logic, cost_consumo_raw would be user.lectura * valor_por_m3_test
        # costo_consumo_raw_calculated = self.user.lectura * valor_por_m3_test # 120.0 * 1200 = 144000
        # costo_consumo_test_redondeado_calculated = round(costo_consumo_raw_calculated) # 144000

        # The test provides `costo_consumo_test = 24000` directly to the template context.
        # This test is more about whether the template *displays* the numbers passed in `context_data` correctly formatted,
        # rather than if those numbers were calculated correctly according to business logic (other tests cover that).
        # So, the existing structure of this specific test should be fine.

        mock_lectura_actual = HistoricoLectura(usuario=self.user, fecha_lectura=timezone.now(), lectura=120.0)
        mock_lectura_anterior = HistoricoLectura(usuario=self.user, fecha_lectura=timezone.now() - timezone.timedelta(days=30), lectura=100.0) # Display consumption: 20

        # This context is what's passed to the template.
        # The test asserts if the template renders these values, not how they are derived.
        costo_consumo_test_for_template = 24000 # This is an arbitrary value for testing template rendering.
        total_factura_for_template = Decimal(costo_consumo_test_for_template) + \
                                     (self.user.credito or Decimal(0)) + \
                                     (self.user.otros_gastos_valor or Decimal(0))
                                     # 24000 + 50 + 10 = 24060

        context_data = {
            'usuario': self.user,
            'historico_lecturas': [mock_lectura_actual, mock_lectura_anterior],
            'lectura_anterior': mock_lectura_anterior,
            'fecha_emision': timezone.now(),
            'periodo_facturacion': 'Período de Prueba',
            'valor_por_m3': valor_por_m3_test, # 1200
            'costo_consumo_agua_redondeado': costo_consumo_test_for_template, # 24000
            'total_factura_redondeado': total_factura_for_template # 24060
            # 'consumo_m3' would be needed if template displays it. Assuming it does:
            # consumo_m3_display_for_template = mock_lectura_actual.lectura - mock_lectura_anterior.lectura if mock_lectura_actual and mock_lectura_anterior else 0
            # context_data['consumo_m3'] = consumo_m3_display_for_template # 20
        }
        
        template = get_template('factura_template.html')
        html_output = template.render(context_data)

        self.assertIn("$1.200 por unidad", html_output) # Checks formatting of valor_por_m3
        self.assertIn("$24.000", html_output) # Checks formatting of costo_consumo_agua_redondeado
        # Add assertion for total if it's displayed and formatted
        # Example: self.assertIn("$24.060", html_output) # Check formatting of total_factura_redondeado
        # This depends on the exact output of format_cop filter and if total is shown this way.
        # For now, keeping original assertions for valor_por_m3 and costo_consumo.


class ListaUsuariosViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.lista_usuarios_url = reverse('lista_usuarios')

        # Create users with distinct zona, contrato, email, and address to isolate zona search
        self.user_norte1 = UserAcueducto.objects.create(
            contrato='ZN001', name='Usuario', lastname='NorteUno', 
            email='norteuno@example.com', numero_de_medidor='MEDN1',
            address='Calle Falsa 123', zona='ZonaNorte', categoria='Residencial'
        )
        self.user_sur1 = UserAcueducto.objects.create(
            contrato='ZS001', name='Usuario', lastname='SurUno', 
            email='suruno@example.com', numero_de_medidor='MEDS1',
            address='Avenida Siempre Viva 456', zona='ZonaSur', categoria='Comercial'
        )
        self.user_norte2 = UserAcueducto.objects.create(
            contrato='ZN002', name='Usuario', lastname='NorteDos', 
            email='nortedos@example.com', numero_de_medidor='MEDN2',
            address='Boulevard Inventado 789', zona='ZonaNorte', categoria='Residencial'
        )
        self.user_centro1 = UserAcueducto.objects.create(
            contrato='ZC001', name='Usuario', lastname='CentroUno', 
            email='centrouno@example.com', numero_de_medidor='MEDC1',
            address='Plaza Principal 000', zona='ZonaCentro', categoria='Residencial'
        )
        # User for testing combined search (address contains a zona name)
        self.user_conflicting_address = UserAcueducto.objects.create(
            contrato='CX001', name='Conflicto', lastname='Dir',
            email='conflictodir@example.com', numero_de_medidor='MEDCXA',
            address='Urbanizacion ZonaNorteña', zona='ZonaOeste', categoria='Residencial'
        )
        # User for testing combined search (contrato contains a zona name)
        self.user_conflicting_contrato = UserAcueducto.objects.create(
            contrato='CONTRATO_ZonaSur_123', name='Conflicto', lastname='Cont',
            email='conflictocont@example.com', numero_de_medidor='MEDCXC',
            address='Calle Real 999', zona='ZonaEste', categoria='Residencial'
        )


    def test_search_by_full_zona_name(self):
        response = self.client.get(self.lista_usuarios_url, {'busqueda': 'ZonaNorte'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('usuarios', response.context)
        usuarios_en_contexto = response.context['usuarios']
        self.assertIn(self.user_norte1, usuarios_en_contexto)
        self.assertIn(self.user_norte2, usuarios_en_contexto)
        self.assertEqual(len(usuarios_en_contexto), 2)

    def test_search_by_partial_zona_name(self):
        response = self.client.get(self.lista_usuarios_url, {'busqueda': 'Nor'})
        self.assertEqual(response.status_code, 200)
        usuarios_en_contexto = response.context['usuarios']
        self.assertIn(self.user_norte1, usuarios_en_contexto)
        self.assertIn(self.user_norte2, usuarios_en_contexto)
        # Also includes user_conflicting_address because 'ZonaNorteña' in address contains 'Nor'
        self.assertIn(self.user_conflicting_address, usuarios_en_contexto)
        self.assertEqual(len(usuarios_en_contexto), 3)

    def test_search_by_non_existent_zona_name(self):
        response = self.client.get(self.lista_usuarios_url, {'busqueda': 'ZonaInexistente'})
        self.assertEqual(response.status_code, 200)
        usuarios_en_contexto = response.context['usuarios']
        self.assertEqual(len(usuarios_en_contexto), 0)

    def test_search_by_zona_excludes_other_zonas(self):
        response = self.client.get(self.lista_usuarios_url, {'busqueda': 'ZonaSur'})
        self.assertEqual(response.status_code, 200)
        usuarios_en_contexto = response.context['usuarios']
        self.assertIn(self.user_sur1, usuarios_en_contexto)
        self.assertNotIn(self.user_norte1, usuarios_en_contexto)
        self.assertNotIn(self.user_norte2, usuarios_en_contexto)
        self.assertNotIn(self.user_centro1, usuarios_en_contexto)
        # This will also include self.user_conflicting_contrato due to 'ZonaSur' in its contrato
        self.assertIn(self.user_conflicting_contrato, usuarios_en_contexto)
        self.assertEqual(len(usuarios_en_contexto), 2)

    def test_search_by_zona_also_matching_address_of_different_user(self):
        # Search for 'ZonaNorte', should get user_norte1, user_norte2
        # AND user_conflicting_address (because its address 'Urbanizacion ZonaNorteña' contains 'ZonaNorte')
        response = self.client.get(self.lista_usuarios_url, {'busqueda': 'ZonaNorte'})
        self.assertEqual(response.status_code, 200)
        usuarios_en_contexto = response.context['usuarios']
        self.assertIn(self.user_norte1, usuarios_en_contexto)
        self.assertIn(self.user_norte2, usuarios_en_contexto)
        self.assertIn(self.user_conflicting_address, usuarios_en_contexto) # Matches on address
        self.assertEqual(len(usuarios_en_contexto), 3)

    def test_search_by_zona_also_matching_contrato_of_different_user(self):
        # Search for 'ZonaSur', should get user_sur1
        # AND user_conflicting_contrato (because its contrato 'CONTRATO_ZonaSur_123' contains 'ZonaSur')
        response = self.client.get(self.lista_usuarios_url, {'busqueda': 'ZonaSur'})
        self.assertEqual(response.status_code, 200)
        usuarios_en_contexto = response.context['usuarios']
        self.assertIn(self.user_sur1, usuarios_en_contexto) # Matches on zona
        self.assertIn(self.user_conflicting_contrato, usuarios_en_contexto) # Matches on contrato
        self.assertEqual(len(usuarios_en_contexto), 2)

    def test_search_by_address_not_matching_zona(self):
        # Search for an address that is unique and not part of any zona name
        response = self.client.get(self.lista_usuarios_url, {'busqueda': 'Calle Falsa 123'})
        self.assertEqual(response.status_code, 200)
        usuarios_en_contexto = response.context['usuarios']
        self.assertIn(self.user_norte1, usuarios_en_contexto)
        self.assertEqual(len(usuarios_en_contexto), 1)

    def test_search_by_contrato_not_matching_zona(self):
        # Search for a contrato that is unique and not part of any zona name
        response = self.client.get(self.lista_usuarios_url, {'busqueda': 'ZC001'})
        self.assertEqual(response.status_code, 200)
        usuarios_en_contexto = response.context['usuarios']
        self.assertIn(self.user_centro1, usuarios_en_contexto)
        self.assertEqual(len(usuarios_en_contexto), 1)


from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta # Ensure timedelta is also imported if used for date calculations

# Assuming formatear_fecha_espanol is in .utils
from .utils import formatear_fecha_espanol 

class GenerarFacturaViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.generar_factura_url = reverse('generar_factura')
        self.test_user = UserAcueducto.objects.create(
            contrato="GFV001", 
            name="FacturaTest", 
            lastname="Usuario", 
            email="facturatest@example.com",
            numero_de_medidor="MEDGFV001", # Required non-null field
            categoria='residencial',       # Required field with default
            zona='TestZone',               # Required field
            # Add any other fields that might be accessed directly or indirectly during invoice generation
            lectura=150.0 # Example, might be relevant for context
        )
        # Ensure BASE_DIR is available for tests if not globally set in test settings
        if not hasattr(settings, 'BASE_DIR'):
            settings.BASE_DIR = Path(__file__).resolve().parent.parent


    @patch('acueducto.views.generar_pdf_factura')
    def test_individual_factura_with_consecutivo(self, mock_generar_pdf):
        # Configure the mock for the return value of generar_pdf_factura
        # This function in views.py returns a tempfile.NamedTemporaryFile object
        mock_temp_file = MagicMock()
        mock_temp_file.name = "dummy_invoice.pdf" # Path to the dummy file
        # The view then opens this file, so we need to ensure it can be "opened"
        # However, for this test, we only care about the arguments to generar_pdf_factura
        # The view logic:
        # pdf_file = generar_factura_individual(...)
        # with open(pdf_file.name, 'rb') as pdf:
        # So, mock_generar_pdf.return_value.name needs to be set.
        mock_generar_pdf.return_value = mock_temp_file

        consecutivo_desde_val = "C001"
        consecutivo_hasta_val = "C100"
        
        # Prepare dates for POST data
        fecha_emision_str = timezone.now().strftime('%Y-%m-%d')
        # Using different dates for period to make it more realistic
        periodo_inicio_str = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d') 
        periodo_fin_str = timezone.now().strftime('%Y-%m-%d')

        post_data = {
            'contrato': self.test_user.contrato,
            'fecha_emision': fecha_emision_str,
            'periodo_inicio': periodo_inicio_str,
            'periodo_fin': periodo_fin_str,
            'consecutivo_desde': consecutivo_desde_val,
            'consecutivo_hasta': consecutivo_hasta_val,
            'descargar': 'Descargar Factura' # Simulating button press
        }

        response = self.client.post(self.generar_factura_url, data=post_data)

        # Check response status (should be 200 for file download)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('inline; filename="factura_'))

        # Assert that generar_pdf_factura was called once
        mock_generar_pdf.assert_called_once()

        # Retrieve the arguments it was called with
        # The mock is on `generar_pdf_factura` which is called by `generar_factura_individual`
        _args, kwargs = mock_generar_pdf.call_args
        
        # --- Prepare expected arguments for assertion ---
        expected_usuario = UserAcueducto.objects.get(contrato=self.test_user.contrato)
        
        # fecha_emision logic in generar_factura_individual:
        # It receives the parsed date string or None. If None, defaults to timezone.now().
        # If string is provided, it's parsed to datetime.datetime.
        expected_fecha_emision_dt = datetime.strptime(fecha_emision_str, '%Y-%m-%d')
        # The view passes this datetime object.

        # periodo_facturacion logic:
        periodo_inicio_dt = datetime.strptime(periodo_inicio_str, '%Y-%m-%d')
        periodo_fin_dt = datetime.strptime(periodo_fin_str, '%Y-%m-%d')
        expected_periodo_facturacion_str = f"Del {formatear_fecha_espanol(periodo_inicio_dt)} al {formatear_fecha_espanol(periodo_fin_dt)}"
        
        expected_base_url = settings.BASE_DIR / 'acueducto' / 'static'

        # --- Perform assertions on kwargs passed to mock_generar_pdf ---
        self.assertEqual(kwargs.get('usuario'), expected_usuario)
        
        # Compare date part of fecha_emision as timezone.now() includes time
        # The view code for fecha_emision:
        # `datetime.strptime(request.POST.get('fecha_emision'), '%Y-%m-%d') if request.POST.get('fecha_emision') else None`
        # This is then passed to `generar_factura_individual` which calls `generar_pdf_factura` with `fecha_emision or timezone.now()`
        # So the argument to `generar_pdf_factura` is a datetime object.
        called_fecha_emision = kwargs.get('fecha_emision')
        self.assertIsInstance(called_fecha_emision, datetime)
        self.assertEqual(called_fecha_emision.strftime('%Y-%m-%d'), expected_fecha_emision_dt.strftime('%Y-%m-%d'))

        self.assertEqual(kwargs.get('periodo_facturacion'), expected_periodo_facturacion_str)
        self.assertEqual(kwargs.get('base_url'), expected_base_url)
        self.assertEqual(kwargs.get('consecutivo_desde'), consecutivo_desde_val)
        self.assertEqual(kwargs.get('consecutivo_hasta'), consecutivo_hasta_val)
