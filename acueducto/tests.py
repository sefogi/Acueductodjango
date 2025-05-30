from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.utils import timezone
from datetime import date, timedelta

from .models import UserAcueducto, Ruta, OrdenRuta, HistoricoLectura
from .views import _get_active_route_details, _handle_lectura_submission, _get_user_data_for_display, toma_lectura
# Import logger to potentially silence it during specific tests if needed, or check its output
import logging

# Reduce logging noise during tests
# Comment out the line below if you want to see all logs during tests.
logging.disable(logging.CRITICAL)


class BaseAcueductoTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a test user for login-required views
        cls.test_user = User.objects.create_user(username='testuser', password='password123')

        # Create UserAcueducto instances
        cls.user_ac1 = UserAcueducto.objects.create(
            contrato='1001', name='Juan', lastname='Perez', address='Calle Falsa 123',
            email='juan@example.com', phone='1234567890', zona='A', lectura=100,
            fecha_ultima_lectura=timezone.now().date() - timedelta(days=30)
        )
        cls.user_ac2 = UserAcueducto.objects.create(
            contrato='1002', name='Ana', lastname='Gomez', address='Avenida Siempre Viva 742',
            email='ana@example.com', phone='0987654321', zona='B', lectura=150,
            fecha_ultima_lectura=timezone.now().date() - timedelta(days=30)
        )
        cls.user_ac3_no_orden = UserAcueducto.objects.create(
            contrato='1003', name='Luis', lastname='Martinez', address='Calle Luna Calle Sol',
            email='luis@example.com', phone='1122334455', zona='A', lectura=200,
            fecha_ultima_lectura=timezone.now().date() - timedelta(days=30)
        )

        # Create Ruta instances
        cls.active_route = Ruta.objects.create(nombre='Ruta Activa Test', activa=True)
        cls.inactive_route = Ruta.objects.create(nombre='Ruta Inactiva Test', activa=False)
        
        cls.empty_active_route = Ruta.objects.create(nombre='Ruta Activa Vacía Test', activa=True)

        # Create OrdenRuta instances for the active route
        cls.orden1 = OrdenRuta.objects.create(ruta=cls.active_route, usuario=cls.user_ac1, orden=1)
        # Mark one reading as already taken for calculations
        cls.orden2 = OrdenRuta.objects.create(ruta=cls.active_route, usuario=cls.user_ac2, orden=2, lectura_tomada=True) 

        # Create HistoricoLectura instances
        # For user_ac1
        for i in range(5): # 5 older readings
            HistoricoLectura.objects.create(
                usuario=cls.user_ac1,
                lectura=90 + i*2, # 90, 92, 94, 96, 98
                fecha_lectura=timezone.now().date() - timedelta(days=60 - i*7)
            )
        HistoricoLectura.objects.create( # This matches user_ac1.lectura and fecha_ultima_lectura
                usuario=cls.user_ac1,
                lectura=cls.user_ac1.lectura, # 100
                fecha_lectura=cls.user_ac1.fecha_ultima_lectura
            )
        
        # For user_ac2
        for i in range(5): # 5 older readings
            HistoricoLectura.objects.create(
                usuario=cls.user_ac2,
                lectura=140 + i*2, # 140, 142, 144, 146, 148
                fecha_lectura=timezone.now().date() - timedelta(days=60 - i*7)
            )
        HistoricoLectura.objects.create( # This matches user_ac2.lectura and fecha_ultima_lectura
                usuario=cls.user_ac2,
                lectura=cls.user_ac2.lectura, # 150
                fecha_lectura=cls.user_ac2.fecha_ultima_lectura
            )
    
    def setUp(self):
        # Request factory for helper function tests
        self.factory = RequestFactory()
        # Refresh active_route's state before each test method if modified by other tests
        # self.active_route.activa = True
        # self.active_route.save()
        # Ruta.objects.filter(id=self.active_route.id).update(activa=True)
        # Ruta.objects.filter(id=self.empty_active_route.id).update(activa=True)
        # OrdenRuta.objects.filter(id=self.orden1.id).update(lectura_tomada=False)
        # OrdenRuta.objects.filter(id=self.orden2.id).update(lectura_tomada=True)
        pass


class GetActiveRouteDetailsTests(BaseAcueductoTestCase):
    def test_active_route_exists_with_readings(self):
        # Ensure self.active_route is the one being tested
        Ruta.objects.filter(activa=True).exclude(id=self.active_route.id).update(activa=False)
        self.active_route.activa = True
        self.active_route.save()
        
        # Ensure one reading is taken, one is not for self.active_route
        OrdenRuta.objects.filter(ruta=self.active_route, usuario=self.user_ac1).update(lectura_tomada=False)
        OrdenRuta.objects.filter(ruta=self.active_route, usuario=self.user_ac2).update(lectura_tomada=True)

        ruta, total, completadas, porcentaje = _get_active_route_details()
        
        self.assertEqual(ruta, self.active_route)
        self.assertEqual(total, 2) 
        self.assertEqual(completadas, 1)
        self.assertAlmostEqual(porcentaje, 50.0)

    def test_no_active_route(self):
        Ruta.objects.filter(activa=True).update(activa=False)
        ruta, total, completadas, porcentaje = _get_active_route_details()
        self.assertIsNone(ruta)
        self.assertEqual(total, 0)
        self.assertEqual(completadas, 0)
        self.assertEqual(porcentaje, 0)

    def test_active_route_no_orders(self):
        Ruta.objects.filter(activa=True).exclude(id=self.empty_active_route.id).update(activa=False)
        self.empty_active_route.activa = True
        self.empty_active_route.save()
                
        ruta, total, completadas, porcentaje = _get_active_route_details()
        self.assertEqual(ruta, self.empty_active_route)
        self.assertEqual(total, 0)
        self.assertEqual(completadas, 0)
        self.assertEqual(porcentaje, 0)

class GetUserDataForDisplayTests(BaseAcueductoTestCase):
    def _prepare_request_with_messages(self):
        request = self.factory.get('/')
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        return request

    def test_user_found(self):
        request = self._prepare_request_with_messages()
        usuario, historico = _get_user_data_for_display(request, self.user_ac1.contrato)
        self.assertEqual(usuario, self.user_ac1)
        self.assertIsNotNone(historico)
        # Expecting 6: 5 older + 1 current that matches user_ac1.lectura
        self.assertEqual(len(historico), 6) 
        self.assertEqual(historico[0].lectura, self.user_ac1.lectura) 

    def test_user_not_found(self):
        request = self._prepare_request_with_messages()
        usuario, historico = _get_user_data_for_display(request, '0000')
        self.assertIsNone(usuario)
        self.assertIsNone(historico)
        messages_list = [m.message for m in list(request._messages)]
        self.assertIn("Usuario no encontrado", messages_list)

    def test_empty_contrato_str(self):
        request = self._prepare_request_with_messages()
        usuario, historico = _get_user_data_for_display(request, '')
        self.assertIsNone(usuario)
        self.assertIsNone(historico)


class HandleLecturaSubmissionTests(BaseAcueductoTestCase):
    def _prepare_post_request_with_messages(self, data):
        request = self.factory.post('/', data)
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        return request

    def test_successful_submission(self):
        # Ensure the specific OrdenRuta for user_ac1 in active_route is not taken
        OrdenRuta.objects.filter(ruta=self.active_route, usuario=self.user_ac1).update(lectura_tomada=False)
        self.active_route.activa = True # Ensure active_route is active
        self.active_route.save()
        Ruta.objects.filter(activa=True).exclude(id=self.active_route.id).update(activa=False)


        nueva_lectura_valor_str = "125"
        request = self._prepare_post_request_with_messages({
            'contrato': self.user_ac1.contrato,
            'lectura': nueva_lectura_valor_str
        })
        
        initial_historico_count = HistoricoLectura.objects.filter(usuario=self.user_ac1).count()

        usuario, historico_returned = _handle_lectura_submission(request, self.active_route, self.user_ac1.contrato, nueva_lectura_valor_str)

        self.assertEqual(usuario, self.user_ac1)
        self.assertIsNotNone(historico_returned)
        # Returned historico should be most recent 6, including the new one
        self.assertEqual(len(historico_returned), 6) 
        self.assertEqual(historico_returned[0].lectura, int(nueva_lectura_valor_str))

        self.user_ac1.refresh_from_db()
        self.assertEqual(self.user_ac1.lectura, int(nueva_lectura_valor_str))
        self.assertEqual(self.user_ac1.fecha_ultima_lectura, timezone.now().date())
        
        self.assertTrue(HistoricoLectura.objects.filter(usuario=self.user_ac1, lectura=int(nueva_lectura_valor_str), fecha_lectura=timezone.now().date()).exists())
        self.assertEqual(HistoricoLectura.objects.filter(usuario=self.user_ac1).count(), initial_historico_count + 1)
        
        orden_despues = OrdenRuta.objects.get(ruta=self.active_route, usuario=self.user_ac1)
        self.assertTrue(orden_despues.lectura_tomada)
        
        messages_list = [m.message for m in list(request._messages)]
        self.assertIn("Lectura registrada exitosamente", messages_list)

    def test_user_not_found_submission(self):
        request = self._prepare_post_request_with_messages({'contrato': '0000', 'lectura': '150'})
        usuario, historico = _handle_lectura_submission(request, self.active_route, '0000', '150')
        self.assertIsNone(usuario)
        self.assertIsNone(historico)
        messages_list = [m.message for m in list(request._messages)]
        self.assertIn("Usuario no encontrado", messages_list)

class TomaLecturaViewTests(BaseAcueductoTestCase):
    def setUp(self):
        super().setUp() # Call BaseAcueductoTestCase.setUp if it has per-test setup
        self.client.login(username='testuser', password='password123')
        # Reset states that might be modified by tests if not using setUpTestData exclusively
        self.active_route.activa = True
        self.active_route.save()
        OrdenRuta.objects.filter(ruta=self.active_route, usuario=self.user_ac1).update(lectura_tomada=False)
        OrdenRuta.objects.filter(ruta=self.active_route, usuario=self.user_ac2).update(lectura_tomada=True)


    def test_login_required(self):
        self.client.logout() # Ensure client is logged out
        response = self.client.get(reverse('toma_lectura'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))

    def test_get_toma_lectura_no_contrato_no_active_route(self):
        Ruta.objects.filter(activa=True).update(activa=False)
        response = self.client.get(reverse('toma_lectura'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['usuario'])
        self.assertIsNone(response.context['ruta_activa'])
        self.assertContains(response, "No hay ruta activa disponible en este momento.")

    def test_get_toma_lectura_with_active_route_no_contrato(self):
        # Ensure self.active_route is the only active one
        Ruta.objects.filter(activa=True).exclude(id=self.active_route.id).update(activa=False)
        self.active_route.activa = True; self.active_route.save()
        OrdenRuta.objects.filter(ruta=self.active_route, usuario=self.user_ac1).update(lectura_tomada=False)
        OrdenRuta.objects.filter(ruta=self.active_route, usuario=self.user_ac2).update(lectura_tomada=True)

        response = self.client.get(reverse('toma_lectura'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['usuario'])
        self.assertEqual(response.context['ruta_activa'], self.active_route)
        self.assertEqual(response.context['total_lecturas'], 2)
        self.assertEqual(response.context['lecturas_completadas'], 1)
        self.assertAlmostEqual(response.context['porcentaje_completado'], 50.0)

    def test_get_toma_lectura_with_contrato_valid(self):
        response = self.client.get(reverse('toma_lectura'), {'contrato': self.user_ac1.contrato})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['usuario'], self.user_ac1)
        self.assertEqual(len(response.context['historico']), 6)

    def test_get_toma_lectura_with_contrato_invalid(self):
        response = self.client.get(reverse('toma_lectura'), {'contrato': '0000'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['usuario'])
        self.assertContains(response, "Usuario no encontrado")

    def test_post_toma_lectura_successful(self):
        # Ensure user_ac1's order in active_route is not yet taken
        OrdenRuta.objects.filter(ruta=self.active_route, usuario=self.user_ac1).update(lectura_tomada=False)
        # Ensure user_ac2's order in active_route is already taken (to test percentage update)
        OrdenRuta.objects.filter(ruta=self.active_route, usuario=self.user_ac2).update(lectura_tomada=True)
        # Ensure self.active_route is the only active one for predictability
        Ruta.objects.filter(activa=True).exclude(id=self.active_route.id).update(activa=False)
        self.active_route.activa = True; self.active_route.save()

        contrato_test = self.user_ac1.contrato
        nueva_lectura_valor_str = "135"
        
        response = self.client.post(reverse('toma_lectura'), {
            'contrato': contrato_test,
            'lectura': nueva_lectura_valor_str
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lectura registrada exitosamente")

        self.user_ac1.refresh_from_db()
        self.assertEqual(self.user_ac1.lectura, int(nueva_lectura_valor_str))
        
        orden_ruta_after = OrdenRuta.objects.get(ruta=self.active_route, usuario__contrato=contrato_test)
        self.assertTrue(orden_ruta_after.lectura_tomada)

        self.assertEqual(response.context['ruta_activa'], self.active_route)
        self.assertEqual(response.context['lecturas_completadas'], 2) # Both user_ac1 and user_ac2 now completed
        self.assertAlmostEqual(response.context['porcentaje_completado'], 100.0)

    def test_post_toma_lectura_user_not_found(self):
        response = self.client.post(reverse('toma_lectura'), {
            'contrato': '0000', 
            'lectura': '200'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Usuario no encontrado")

# To re-enable logging if disabled elsewhere:
# logging.disable(logging.NOTSET)

from .services import crear_nueva_ruta_service, finalizar_ruta_service # Moved import to top
from django.http import Http404 # For testing Http404 expectation

class RouteServiceTests(BaseAcueductoTestCase):
    def test_crear_nueva_ruta_service_success(self):
        # Setup: Create an old route to ensure it's deleted
        old_ruta_nombre = "Ruta Vieja"
        old_ruta = Ruta.objects.create(nombre=old_ruta_nombre)
        OrdenRuta.objects.create(ruta=old_ruta, usuario=self.user_ac1, orden=1)
        self.assertTrue(Ruta.objects.filter(nombre=old_ruta_nombre).exists())

        nombre_ruta_nueva = "Ruta Test Service"
        # Use users created in BaseAcueductoTestCase.setUpTestData
        usuarios_orden_data = [
            {'id': self.user_ac1.id, 'orden': 1},
            {'id': self.user_ac2.id, 'orden': 2}
        ]

        # Execution
        ruta_creada = crear_nueva_ruta_service(nombre_ruta_nueva, usuarios_orden_data)

        # Assertions
        self.assertIsNotNone(ruta_creada)
        self.assertIsInstance(ruta_creada, Ruta)
        self.assertEqual(ruta_creada.nombre, nombre_ruta_nueva)

        # Assert that the old Ruta object no longer exists
        self.assertFalse(Ruta.objects.filter(nombre=old_ruta_nombre).exists())
        # Assert that only one Ruta object exists (the newly created one)
        self.assertEqual(Ruta.objects.count(), 1) # This assumes no other routes are active from base setup

        # Assert new OrdenRuta objects
        self.assertEqual(ruta_creada.ordenruta_set.count(), len(usuarios_orden_data))

        orden1_creada = OrdenRuta.objects.get(ruta=ruta_creada, usuario=self.user_ac1)
        self.assertEqual(orden1_creada.orden, 1)

        orden2_creada = OrdenRuta.objects.get(ruta=ruta_creada, usuario=self.user_ac2)
        self.assertEqual(orden2_creada.orden, 2)

    def test_crear_nueva_ruta_service_empty_users(self):
        nombre_ruta = "Ruta Vacia Service"
        usuarios_orden_data = [] # Empty list of users

        # Ensure any old routes are gone to not interfere with count assertions
        Ruta.objects.all().delete()

        # Execution
        ruta_creada = crear_nueva_ruta_service(nombre_ruta, usuarios_orden_data)

        # Assertions
        self.assertIsNotNone(ruta_creada)
        self.assertEqual(ruta_creada.nombre, nombre_ruta)
        self.assertEqual(ruta_creada.ordenruta_set.count(), 0)
        self.assertEqual(Ruta.objects.count(), 1) # Only this new empty route should exist

    def test_crear_nueva_ruta_service_value_error_no_name(self):
        # Test for ValueError if nombre_ruta is empty
        with self.assertRaisesMessage(ValueError, "Nombre de ruta y usuarios son requeridos para crear la ruta."):
             # The service function itself raises ValueError for empty nombre_ruta
            crear_nueva_ruta_service("", [{'id': self.user_ac1.id, 'orden': 1}])

    def test_crear_nueva_ruta_service_value_error_no_users_if_required_by_service(self):
        # The service's current check is `if not nombre_ruta or not usuarios_orden_data:`.
        # So, an empty list for usuarios_orden_data with a valid name should also raise ValueError.
        nombre_ruta = "Test Ruta Con Nombre Sin Usuarios"
        with self.assertRaisesMessage(ValueError, "Nombre de ruta y usuarios son requeridos para crear la ruta."):
            crear_nueva_ruta_service(nombre_ruta, [])

    def test_finalizar_ruta_service_success(self):
        # Setup: Create a new Ruta for this test to avoid interference
        ruta_a_finalizar = Ruta.objects.create(nombre="Ruta para Finalizar Test", activa=True)
        OrdenRuta.objects.create(ruta=ruta_a_finalizar, usuario=self.user_ac1, orden=1, lectura_tomada=True)
        OrdenRuta.objects.create(ruta=ruta_a_finalizar, usuario=self.user_ac2, orden=2, lectura_tomada=True)

        # Execution
        success, message, ruta_obj = finalizar_ruta_service(ruta_a_finalizar.id)

        # Assertions
        self.assertTrue(success)
        self.assertIsNotNone(ruta_obj)
        self.assertFalse(ruta_obj.activa) # Check if the object returned is updated
        self.assertIsNotNone(ruta_obj.fecha_finalizacion)
        self.assertEqual(message, 'Ruta finalizada exitosamente')

        # Verify in DB as well
        ruta_reloaded = Ruta.objects.get(id=ruta_a_finalizar.id)
        self.assertFalse(ruta_reloaded.activa)
        self.assertIsNotNone(ruta_reloaded.fecha_finalizacion)

    def test_finalizar_ruta_service_pending_lecturas(self):
        # Setup
        ruta_con_pendientes = Ruta.objects.create(nombre="Ruta con Pendientes Test", activa=True)
        OrdenRuta.objects.create(ruta=ruta_con_pendientes, usuario=self.user_ac1, orden=1, lectura_tomada=True)
        OrdenRuta.objects.create(ruta=ruta_con_pendientes, usuario=self.user_ac2, orden=2, lectura_tomada=False) # Pending

        # Execution
        success, message, ruta_obj = finalizar_ruta_service(ruta_con_pendientes.id)

        # Assertions
        self.assertFalse(success)
        self.assertIsNotNone(ruta_obj) # Service returns the route object even on failure
        self.assertTrue(ruta_obj.activa) # Should still be active
        self.assertIsNone(ruta_obj.fecha_finalizacion) # Should not be set
        self.assertEqual(message, 'No se puede finalizar la ruta. Hay lecturas pendientes.')

        # Verify in DB
        ruta_reloaded = Ruta.objects.get(id=ruta_con_pendientes.id)
        self.assertTrue(ruta_reloaded.activa)
        self.assertIsNone(ruta_reloaded.fecha_finalizacion)

    def test_finalizar_ruta_service_non_existent_ruta(self):
        non_existent_ruta_id = 99999
        # Ensure this ID does not exist
        Ruta.objects.filter(id=non_existent_ruta_id).delete()

        with self.assertRaises(Http404):
            finalizar_ruta_service(non_existent_ruta_id)


from .services import generar_zip_todas_facturas_service # Specific import for this class
from unittest import mock # Already at top level, but good to note it's used here
from io import BytesIO # Already at top level
import zipfile # Already at top level
from datetime import datetime # Already at top level (date also present)

class InvoiceServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create minimal UserAcueducto instances needed for these tests
        # Ensure 'categoria' is provided as it's a required field with choices
        cls.user1 = UserAcueducto.objects.create(
            contrato="C001", name="Test", lastname="User1",
            email="test1_invoice@example.com", categoria="residencial",
            fecha_ultima_lectura=date(2023,1,15), lectura=100.0
        )
        cls.user2 = UserAcueducto.objects.create(
            contrato="C002", name="Test", lastname="User2",
            email="test2_invoice@example.com", categoria="comercial",
            fecha_ultima_lectura=date(2023,1,16), lectura=200.0
        )

    @mock.patch('acueducto.services.os.unlink') # Path to os.unlink used within services.py
    @mock.patch('acueducto.services.utils.generar_pdf_factura') # Path to utils.generar_pdf_factura used by the service
    def test_generar_zip_todas_facturas_service_success(self, mock_generar_pdf, mock_os_unlink):
        periodo_inicio_str = "2023-01-01"
        periodo_fin_str = "2023-01-31"

        # Configure the mock for generar_pdf_factura
        # It needs to return an object that has a 'name' attribute (like a file object)
        mock_pdf_file_object = mock.MagicMock()
        mock_pdf_file_object.name = "dummy_temp_factura.pdf" # Simulate temp file name
        mock_generar_pdf.return_value = mock_pdf_file_object

        zip_buffer = generar_zip_todas_facturas_service(periodo_inicio_str, periodo_fin_str)

        self.assertEqual(mock_generar_pdf.call_count, 2) # Called for user1 and user2

        # Example assertion for one of the calls to generar_pdf_factura
        # We need to be careful about asserting datetime.now()
        # Instead, we check the type and other more stable arguments.
        args_list = mock_generar_pdf.call_args_list
        # Find call for self.user1 (order might not be guaranteed by .all())
        call_for_user1 = next((call for call in args_list if call[1]['usuario'] == self.user1), None)
        self.assertIsNotNone(call_for_user1, "Call for user1 not found in mock_generar_pdf calls")

        self.assertEqual(call_for_user1[1]['usuario'], self.user1)
        self.assertIsInstance(call_for_user1[1]['fecha_emision'], datetime)
        self.assertEqual(call_for_user1[1]['periodo_facturacion'], "Del 1 de enero de 2023 al 31 de enero de 2023")
        # Ensure base_url is passed correctly
        self.assertTrue(call_for_user1[1]['base_url'].endswith('acueducto/static'))


        self.assertEqual(mock_os_unlink.call_count, 2) # Called twice to delete temp PDFs
        mock_os_unlink.assert_any_call("dummy_temp_factura.pdf") # Check it was called with the dummy name

        self.assertIsNotNone(zip_buffer)
        self.assertIsInstance(zip_buffer, BytesIO)
        zip_buffer.seek(0) # Important before reading the zip
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            self.assertEqual(len(zf.namelist()), 2)
            self.assertIn(f'factura_{self.user1.contrato}.pdf', zf.namelist())
            self.assertIn(f'factura_{self.user2.contrato}.pdf', zf.namelist())

    @mock.patch('acueducto.services.os.unlink')
    @mock.patch('acueducto.services.utils.generar_pdf_factura')
    def test_generar_zip_todas_facturas_service_no_users(self, mock_generar_pdf, mock_os_unlink):
        # Ensure users are deleted for this specific test case
        UserAcueducto.objects.all().delete()

        periodo_inicio_str = "2023-01-01"
        periodo_fin_str = "2023-01-31"

        zip_buffer = generar_zip_todas_facturas_service(periodo_inicio_str, periodo_fin_str)

        mock_generar_pdf.assert_not_called()
        mock_os_unlink.assert_not_called()
        self.assertIsNotNone(zip_buffer)
        zip_buffer.seek(0)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            self.assertEqual(len(zf.namelist()), 0)

        # No need to recreate users manually; Django TestCase handles transaction rollback.

    def test_generar_zip_todas_facturas_service_empty_date_strings(self):
        with self.assertRaisesRegex(ValueError, 'Por favor, especifique el período de facturación'):
            generar_zip_todas_facturas_service("", "2023-01-31")
        with self.assertRaisesRegex(ValueError, 'Por favor, especifique el período de facturación'):
            generar_zip_todas_facturas_service("2023-01-01", "")

    def test_generar_zip_todas_facturas_service_invalid_date_format(self):
        with self.assertRaises(ValueError): # strptime raises ValueError for invalid format
            generar_zip_todas_facturas_service("invalid-date-format", "2023-01-31")
        with self.assertRaises(ValueError):
            generar_zip_todas_facturas_service("2023-01-01", "31/01/2023-invalid")


from .utils import generar_pdf_factura, formatear_fecha_espanol
import tempfile # For the return value of generar_pdf_factura
import os # For cleaning up temp file

class UtilsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserAcueducto.objects.create(
            contrato="U001", name="UtilTest", lastname="User",
            email="util_test@example.com", categoria="residencial", # Ensure unique email
            fecha_ultima_lectura=date(2023,2,10), lectura=150.0
        )
        # Create some historical readings for the user
        HistoricoLectura.objects.create(usuario=cls.user, fecha_lectura=date(2023,2,10), lectura=150)
        HistoricoLectura.objects.create(usuario=cls.user, fecha_lectura=date(2023,1,10), lectura=120)
        HistoricoLectura.objects.create(usuario=cls.user, fecha_lectura=date(2022,12,10), lectura=100)

    @mock.patch('acueducto.utils.HTML') # Mock WeasyPrint's HTML
    @mock.patch('acueducto.utils.get_template') # Mock Django's get_template
    def test_generar_pdf_factura_success(self, mock_get_template, mock_weasy_html):
        # Setup mock for get_template
        mock_template_obj = mock.MagicMock()
        mock_get_template.return_value = mock_template_obj

        # Setup mock for HTML().write_pdf()
        mock_html_instance = mock.MagicMock()
        mock_weasy_html.return_value = mock_html_instance # HTML(string=...) returns this instance

        fecha_emision_dt = datetime(2023, 3, 1, 10, 0, 0) # Use datetime for fecha_emision
        periodo_facturacion_str = "Del 1 de febrero de 2023 al 28 de febrero de 2023"
        base_url_dummy = "/dummy/static/path/"

        pdf_file_obj = None # Initialize to ensure it's available in finally block
        try:
            pdf_file_obj = generar_pdf_factura(
                usuario=self.user,
                fecha_emision=fecha_emision_dt,
                periodo_facturacion=periodo_facturacion_str,
                base_url=base_url_dummy
            )

            # Assertions
            mock_get_template.assert_called_once_with('factura_template.html')

            mock_template_obj.render.assert_called_once()
            render_context = mock_template_obj.render.call_args[0][0]
            self.assertEqual(render_context['usuario'], self.user)
            self.assertEqual(render_context['fecha_emision'], fecha_emision_dt)
            self.assertEqual(render_context['periodo_facturacion'], periodo_facturacion_str)
            self.assertIn('historico_lecturas', render_context)
            # Based on setUpTestData, 3 lecturas exist. The function fetches up to 6.
            self.assertEqual(len(render_context['historico_lecturas']), 3)
            self.assertIn('lectura_anterior', render_context)
            # Check if lectura_anterior is correctly identified
            # Readings are: 150 (Feb 10), 120 (Jan 10), 100 (Dec 10)
            # If current is Feb 10 (150), anterior should be Jan 10 (120)
            # The logic in generar_pdf_factura gets all() and orders by -fecha_lectura
            # historico_lecturas[0] is the latest, historico_lecturas[1] is the one before.
            if len(self.user.lecturas.all().order_by('-fecha_lectura')) > 1:
                self.assertEqual(render_context['lectura_anterior'].lectura, 120) # Second latest
            else:
                self.assertIsNone(render_context['lectura_anterior'])


            mock_weasy_html.assert_called_once_with(string=mock_template_obj.render.return_value, base_url=base_url_dummy)
            mock_html_instance.write_pdf.assert_called_once_with(pdf_file_obj.name)

            self.assertIsNotNone(pdf_file_obj)
            self.assertTrue(hasattr(pdf_file_obj, 'name'))
            self.assertTrue(pdf_file_obj.name.endswith('.pdf'))

        finally:
            # Cleanup the temporary file
            if pdf_file_obj and hasattr(pdf_file_obj, 'name') and os.path.exists(pdf_file_obj.name):
                try:
                    pdf_file_obj.close() # Close before unlinking if it's still open
                except Exception:
                    pass # Ignore errors on close if already closed or unlinked
                os.unlink(pdf_file_obj.name)

    def test_formatear_fecha_espanol(self):
        fecha1 = date(2023, 1, 15) # January 15, 2023
        self.assertEqual(formatear_fecha_espanol(fecha1), "15 de enero de 2023")

        fecha2 = date(2024, 3, 5) # March 5, 2024
        self.assertEqual(formatear_fecha_espanol(fecha2), "5 de marzo de 2024")

        fecha3 = date(2022, 12, 25) # December 25, 2022
        self.assertEqual(formatear_fecha_espanol(fecha3), "25 de diciembre de 2022")
