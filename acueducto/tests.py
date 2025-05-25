from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from acueducto.models import UserAcueducto, Ruta, OrdenRuta
import json

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
        # Ensure fecha_creacion is distinct for ordering if needed, though not directly used in logic here
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

        # Simulate POST request to create a new route
        response = self.client.post(self.lista_usuarios_url, {
            'nombre_ruta': nueva_ruta_nombre,
            'usuarios_orden': json.dumps(usuarios_orden_data),
            'generar_ruta': 'Generar Ruta' # Name of the submit button
        })

        # Check response
        self.assertEqual(response.status_code, 302) # Should redirect after successful creation
        self.assertRedirects(response, self.lista_usuarios_url)

        # Assert old routes are deactivated
        ruta_antigua1.refresh_from_db()
        ruta_antigua2.refresh_from_db()
        self.assertFalse(ruta_antigua1.activa, "Ruta Antigua 1 should be inactive")
        self.assertIsNotNone(ruta_antigua1.fecha_finalizacion, "Ruta Antigua 1 should have a finalization date")
        self.assertFalse(ruta_antigua2.activa, "Ruta Antigua 2 should be inactive")
        self.assertIsNotNone(ruta_antigua2.fecha_finalizacion, "Ruta Antigua 2 should have a finalization date")
        
        # Assert new route is active
        self.assertTrue(Ruta.objects.filter(nombre=nueva_ruta_nombre, activa=True).exists(), "New route should be active")
        ruta_nueva = Ruta.objects.get(nombre=nueva_ruta_nombre)
        self.assertIsNone(ruta_nueva.fecha_finalizacion, "New route should not have a finalization date")
        self.assertEqual(Ruta.objects.filter(activa=True).count(), 1, "Only one route should be active")

    def test_crear_nueva_ruta_sin_rutas_previas(self):
        # Ensure no active routes exist initially
        Ruta.objects.all().update(activa=False, fecha_finalizacion=timezone.now()) # Deactivate any existing from other tests if run in parallel or if DB is not clean
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
        # Define the order of users for the new route
        usuarios_para_orden = [
            {'id': self.user2.id, 'orden': 1}, # User2 first
            {'id': self.user1.id, 'orden': 2}, # User1 second
            {'id': self.user3.id, 'orden': 3}, # User3 third
        ]
        
        response = self.client.post(self.lista_usuarios_url, {
            'nombre_ruta': nueva_ruta_nombre,
            'usuarios_orden': json.dumps(usuarios_para_orden), # Ensure this is a JSON string
            'generar_ruta': 'Generar Ruta'
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.lista_usuarios_url)

        self.assertTrue(Ruta.objects.filter(nombre=nueva_ruta_nombre, activa=True).exists())
        ruta_creada = Ruta.objects.get(nombre=nueva_ruta_nombre)

        # Retrieve OrdenRuta objects associated with the created route, ordered by 'orden'
        ordenes_ruta = OrdenRuta.objects.filter(ruta=ruta_creada).order_by('orden')
        
        self.assertEqual(len(ordenes_ruta), 3)

        # Assert correct order and default values
        self.assertEqual(ordenes_ruta[0].usuario, self.user2)
        self.assertEqual(ordenes_ruta[0].orden, 1)
        self.assertFalse(ordenes_ruta[0].lectura_tomada, "Lectura tomada should be False by default for user2")

        self.assertEqual(ordenes_ruta[1].usuario, self.user1)
        self.assertEqual(ordenes_ruta[1].orden, 2)
        self.assertFalse(ordenes_ruta[1].lectura_tomada, "Lectura tomada should be False by default for user1")
        
        self.assertEqual(ordenes_ruta[2].usuario, self.user3)
        self.assertEqual(ordenes_ruta[2].orden, 3)
        self.assertFalse(ordenes_ruta[2].lectura_tomada, "Lectura tomada should be False by default for user3")


from .forms import UserAcueductoForm # Import the form

class UserCreationFormTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.index_url = reverse('index')

    def test_user_creation_success(self):
        initial_user_count = UserAcueducto.objects.count()
        valid_data = {
            'contrato': '201',
            'name': 'Test',
            'lastname': 'User',
            'email': 'testuser@example.com',
            'phone': '1234567890',
            'address': '123 Test St',
            'categoria': 'residencial',
            'zona': 'Norte',
            'fecha_ultima_lectura': '2023-01-01', # Renamed from date
            'credito': '0.00', # Provide default for DecimalField
            'credito_descripcion': '', 
            'otros_gastos_valor': '0.00', # Provide default for DecimalField
            'otros_gastos_descripcion': '' 
        }
        # Use follow=True to automatically follow the redirect
        response = self.client.post(self.index_url, valid_data, follow=True)

        self.assertEqual(UserAcueducto.objects.count(), initial_user_count + 1, f"User count did not increase. Form errors: {response.context['form'].errors if 'form' in response.context else 'No form in context'}")
        created_user = UserAcueducto.objects.get(contrato='201')
        self.assertEqual(created_user.name, 'Test')
        self.assertEqual(created_user.email, 'testuser@example.com')
        
        # After follow=True, the response is the final one (after redirect)
        self.assertEqual(response.status_code, 200) 
        self.assertRedirects(response, self.index_url, status_code=302, target_status_code=200)

        # Check for messages on the final response
        messages_in_response = list(response.context.get('messages', []))
        self.assertEqual(len(messages_in_response), 1, f"Expected 1 message, got {len(messages_in_response)}. Messages: {[str(m) for m in messages_in_response]}")
        self.assertEqual(str(messages_in_response[0]), "Usuario creado exitosamente")
        
        # assertContains checks the content of the final response
        self.assertContains(response, "Usuario creado exitosamente")


    def test_user_creation_invalid_data(self):
        initial_user_count = UserAcueducto.objects.count()
        invalid_data = {
            'contrato': '', # Missing contrato
            'name': 'Test Invalid',
            'lastname': 'User Invalid',
            'email': 'not-an-email', # Invalid email
            'phone': '123',
            'address': 'Invalid Address',
            'categoria': 'residencial',
            'zona': 'Sur'
            # date is optional
        }
        response = self.client.post(self.index_url, invalid_data)

        self.assertEqual(UserAcueducto.objects.count(), initial_user_count) # No user should be created
        self.assertEqual(response.status_code, 200) # Re-renders the form
        self.assertIn('form', response.context)
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('contrato', form.errors) # Check for error in contrato field
        self.assertIn('email', form.errors)    # Check for error in email field

    def test_user_creation_contrato_unique_constraint(self):
        # Create an initial user
        UserAcueducto.objects.create(
            contrato='301', name='Existing', lastname='User', 
            email='existing@example.com', address='Some Address', 
            categoria='comercial', zona='Centro'
        )
        initial_user_count = UserAcueducto.objects.count()

        data_with_duplicate_contrato = {
            'contrato': '301', # Duplicate contrato
            'name': 'New',
            'lastname': 'User',
            'email': 'new@example.com',
            'phone': '0987654321',
            'address': '456 New St',
            'categoria': 'residencial',
            'zona': 'Este',
            'fecha_ultima_lectura': '2023-02-01' # Renamed from date
        }
        response = self.client.post(self.index_url, data_with_duplicate_contrato)

        self.assertEqual(UserAcueducto.objects.count(), initial_user_count) # No new user should be created
        self.assertEqual(response.status_code, 200) # Re-renders the form
        self.assertIn('form', response.context)
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('contrato', form.errors)
        # Check for the specific unique constraint error message if known, or just that 'contrato' has an error.
        # Example: self.assertIn("User acueducto con este Contrato ya existe.", form.errors['contrato'])


    def test_index_view_get_request(self):
        response = self.client.get(self.index_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIsInstance(response.context['form'], UserAcueductoForm)
        self.assertFalse(response.context['form'].is_bound) # Check form is unbound
        self.assertTemplateUsed(response, 'index.html')


from django.contrib.auth.models import User as AuthUser # For creating a user to log in

class UserModificationTests(TestCase):

    def setUp(self):
        self.client = Client()
        # Create a superuser for login, as some views might be admin-protected
        # or just need any logged-in user.
        self.auth_user = AuthUser.objects.create_user(username='testadmin', password='password123', is_staff=True, is_superuser=True)
        self.client.login(username='testadmin', password='password123')

        self.user_contrato = '401'
        # This is the UserAcueducto instance we are testing modification for
        self.user_to_modify = UserAcueducto.objects.create(
            contrato=self.user_contrato,
            name='Original Name',
            lastname='Original Lastname',
            email='original@example.com',
            phone='1112223333',
            address='Original Address',
            categoria='residencial',
            zona='Centro',
            credito=100.00,
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
        self.assertTrue(form_in_context.fields['contrato'].disabled, "Contrato field should be disabled")

    def test_user_modification_success(self):
        updated_data = {
            'contrato': self.user_to_modify.contrato, # Crucial hidden field for POST
            'name': 'Updated Name',
            'lastname': self.user_to_modify.lastname, # Keep some fields same
            'email': self.user_to_modify.email,
            'phone': '9998887777', # Changed
            'address': 'Updated Address', # Changed
            'categoria': self.user_to_modify.categoria,
            'zona': self.user_to_modify.zona,
            'credito': 250.50, # Changed
            'credito_descripcion': 'Updated credit info', # Changed
            'otros_gastos_valor': 50.00, # New
            'otros_gastos_descripcion': 'New other expense' # New
        }
        
        response = self.client.post(self.modificar_usuario_url_base, updated_data, follow=True) # Post to base, GET param is for initial load
        
        self.assertEqual(response.status_code, 200) # After redirect
        self.assertRedirects(response, self.modificar_usuario_url_for_user, status_code=302, target_status_code=200)

        self.user_to_modify.refresh_from_db()
        self.assertEqual(self.user_to_modify.name, 'Updated Name')
        self.assertEqual(self.user_to_modify.phone, '9998887777')
        self.assertEqual(self.user_to_modify.address, 'Updated Address')
        self.assertEqual(self.user_to_modify.credito, 250.50)
        self.assertEqual(self.user_to_modify.credito_descripcion, 'Updated credit info')
        self.assertEqual(self.user_to_modify.otros_gastos_valor, 50.00)
        self.assertEqual(self.user_to_modify.otros_gastos_descripcion, 'New other expense')

        messages_in_response = list(response.context.get('messages', []))
        self.assertEqual(len(messages_in_response), 1)
        self.assertEqual(str(messages_in_response[0]), "Usuario actualizado exitosamente")
        self.assertContains(response, "Usuario actualizado exitosamente")

    def test_user_modification_invalid_data(self):
        original_name = self.user_to_modify.name
        original_email = self.user_to_modify.email
        invalid_data = {
            'contrato': self.user_to_modify.contrato, # Hidden field
            'name': 'Name Before Error', # This should also not persist if form is invalid
            'lastname': self.user_to_modify.lastname,
            'email': 'this-is-not-an-email', # Invalid email
            'phone': self.user_to_modify.phone,
            'address': self.user_to_modify.address,
            'categoria': self.user_to_modify.categoria,
            'zona': self.user_to_modify.zona,
        }
        response = self.client.post(self.modificar_usuario_url_base, invalid_data)

        self.assertEqual(response.status_code, 200) # Form re-rendered
        self.user_to_modify.refresh_from_db()
        self.assertEqual(self.user_to_modify.name, original_name, "Name should not have changed on invalid form submission")
        self.assertEqual(self.user_to_modify.email, original_email, "Email should not have changed to invalid one")


        self.assertIn('form', response.context)
        form_in_context = response.context['form']
        self.assertTrue(form_in_context.errors)
        self.assertIn('email', form_in_context.errors)
        self.assertContains(response, "Error al actualizar usuario. Por favor revise los datos.")


    def test_user_modification_non_existent_user_get(self):
        non_existent_contrato = '99999'
        url = f"{self.modificar_usuario_url_base}?contrato={non_existent_contrato}"
        response = self.client.get(url)
        
        # Default behavior of get_object_or_404 is to raise Http404, so expect 404
        self.assertEqual(response.status_code, 404)

    def test_user_modification_non_existent_user_post(self):
        non_existent_contrato = '88888'
        data = {
            'contrato': non_existent_contrato, # This is the key for lookup
            'name': 'Trying To Update NonExistent',
            'email': 'nonexistent@example.com',
            'categoria': 'comercial',
            'zona': 'Sur'
        }
        initial_user_count = UserAcueducto.objects.count()
        
        # POST to the base URL as the form would
        # The Http404 is caught by a generic `except Exception` in the view, leading to a 200 response
        response = self.client.post(self.modificar_usuario_url_base, data, follow=False) # No redirect expected
        
        self.assertEqual(response.status_code, 200) # View catches Http404 and returns 200
        
        messages_in_response = list(response.context.get('messages', []))
        # This message comes from the broad "except Exception as e" block in the view, 
        # which catches the Http404 from get_object_or_404.
        expected_full_error_msg = "Ocurrió un error inesperado al actualizar el usuario: No UserAcueducto matches the given query."
        self.assertTrue(
            any(expected_full_error_msg == str(m) for m in messages_in_response),
            f"Expected error message not found. Messages: {[str(m) for m in messages_in_response]}"
        )
        
        self.assertEqual(UserAcueducto.objects.count(), initial_user_count) # No user created/modified
        # Check that our original user is unchanged
        self.user_to_modify.refresh_from_db()
        self.assertEqual(self.user_to_modify.name, 'Original Name')


from django.test import SimpleTestCase # Added for SimpleTestCase
from django.template import Context, Template # Added
from decimal import Decimal # Added

class FormatCOPTemplateFilterTests(SimpleTestCase):
    def render_template(self, string, context=None):
        context = context or {}
        context = Context(context)
        # Ensure the filter is loaded in the template string
        template_string = "{% load acueducto_filters %} " + string
        return Template(template_string).render(context)

    def test_format_cop_integer(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": 1234567})
        self.assertEqual(rendered, "$ 1.234.567,00")

    def test_format_cop_float(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": 12345.67})
        self.assertEqual(rendered, "$ 12.345,67")

    def test_format_cop_decimal(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": Decimal('12345.67')})
        self.assertEqual(rendered, "$ 12.345,67")

    def test_format_cop_with_3_decimal_places(self):
        rendered = self.render_template("{{ value|format_cop:3 }}", {"value": 123.456})
        self.assertEqual(rendered, "$ 123,456")
        
    def test_format_cop_with_custom_float_3_decimal_places(self):
        rendered = self.render_template("{{ value|format_cop:3 }}", {"value": 12345.678})
        self.assertEqual(rendered, "$ 12.345,678")

    def test_format_cop_with_0_decimal_places(self):
        rendered = self.render_template("{{ value|format_cop:0 }}", {"value": 12345})
        self.assertEqual(rendered, "$ 12.345")
        
    def test_format_cop_float_with_0_decimal_places(self):
        # Test rounding behavior (default float formatting usually rounds)
        rendered = self.render_template("{{ value|format_cop:0 }}", {"value": 12345.6}) 
        self.assertEqual(rendered, "$ 12.346") # 12345.6 rounds to 12346 with 0 decimal places

    def test_format_cop_none_value(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": None})
        self.assertEqual(rendered, "")

    def test_format_cop_zero_value(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": 0})
        self.assertEqual(rendered, "$ 0,00")
        
    def test_format_cop_zero_value_0_decimals(self):
        rendered = self.render_template("{{ value|format_cop:0 }}", {"value": 0})
        self.assertEqual(rendered, "$ 0")

    def test_format_cop_negative_value(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": -12345.67})
        self.assertEqual(rendered, "$ -12.345,67")
        
    def test_format_cop_negative_value_0_decimals(self):
        rendered = self.render_template("{{ value|format_cop:0 }}", {"value": -12345.67})
        self.assertEqual(rendered, "$ -12.346") # Test rounding for negative

    def test_format_cop_string_value_valid_number(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": "12345.67"})
        self.assertEqual(rendered, "$ 12.345,67")

    def test_format_cop_string_value_invalid_number(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": "not_a_number"})
        self.assertEqual(rendered, "")
        
    def test_format_cop_large_number(self):
        rendered = self.render_template("{{ value|format_cop }}", {"value": 1234567890.12})
        self.assertEqual(rendered, "$ 1.234.567.890,12")

    def test_format_cop_small_number_many_decimals_default(self):
        # Default is 2 decimal places, should round
        rendered = self.render_template("{{ value|format_cop }}", {"value": 0.12345})
        self.assertEqual(rendered, "$ 0,12")
        
    def test_format_cop_small_number_many_decimals_custom(self):
        rendered = self.render_template("{{ value|format_cop:4 }}", {"value": 0.12345})
        self.assertEqual(rendered, "$ 0,1235") # Test rounding with more decimal places
