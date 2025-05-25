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
        
        self.assertEqual(consumo_m3, 20.0) 

        valor_por_m3_expected = 1000 
        costo_consumo_raw = consumo_m3 * valor_por_m3_expected
        costo_consumo_agua_redondeado_expected = round(costo_consumo_raw)
        self.assertEqual(costo_consumo_agua_redondeado_expected, 20000)

        credito = self.user.credito if self.user.credito is not None else Decimal('0')
        otros_gastos = self.user.otros_gastos_valor if self.user.otros_gastos_valor is not None else Decimal('0')
        # Ensure all parts are Decimal for arithmetic if they come from model
        total_factura_raw = Decimal(costo_consumo_agua_redondeado_expected) + credito + otros_gastos
        total_factura_redondeado_expected = round(total_factura_raw)

        context = {
            'usuario': self.user,
            'historico_lecturas': historico_lecturas[:6], 
            'lectura_anterior': lectura_anterior_obj,
            'fecha_emision': timezone.now(),
            'periodo_facturacion': "Test Period",
            'costo_consumo_agua_redondeado': costo_consumo_agua_redondeado_expected,
            'total_factura_redondeado': total_factura_redondeado_expected,
            'valor_por_m3': valor_por_m3_expected,
        }

        self.assertEqual(context['valor_por_m3'], valor_por_m3_expected)
        self.assertEqual(context['costo_consumo_agua_redondeado'], 20000)
        self.assertEqual(context['total_factura_redondeado'], 20060) 


    def test_invoice_template_renders_dynamic_valor_unitario(self):
        valor_por_m3_test = 1200 
        costo_consumo_test = 24000 
        
        mock_lectura_actual = HistoricoLectura(usuario=self.user, fecha_lectura=timezone.now(), lectura=120.0)
        mock_lectura_anterior = HistoricoLectura(usuario=self.user, fecha_lectura=timezone.now() - timezone.timedelta(days=30), lectura=100.0)

        context_data = {
            'usuario': self.user, 
            'historico_lecturas': [mock_lectura_actual, mock_lectura_anterior], 
            'lectura_anterior': mock_lectura_anterior,
            'fecha_emision': timezone.now(),
            'periodo_facturacion': 'Período de Prueba',
            'valor_por_m3': valor_por_m3_test,
            'costo_consumo_agua_redondeado': costo_consumo_test,
            'total_factura_redondeado': Decimal(costo_consumo_test) + (self.user.credito or Decimal(0)) + (self.user.otros_gastos_valor or Decimal(0))
        }
        
        template = get_template('factura_template.html')
        html_output = template.render(context_data)

        self.assertIn("$1.200 por unidad", html_output)
        self.assertIn("$24.000", html_output)
