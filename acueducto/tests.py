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
