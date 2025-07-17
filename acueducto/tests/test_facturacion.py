from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.contrib.messages import get_messages
from acueducto.models import UserAcueducto, HistoricoLectura, Factura
from acueducto.utils import formatear_fecha_espanol

class FacturacionTests(TestCase):
    def setUp(self):
        """
        Configuración inicial para las pruebas
        """
        # Crear usuario de prueba
        self.usuario = UserAcueducto.objects.create(
            contrato="TEST001",
            numero_de_medidor="MED001",
            name="Usuario",
            lastname="De Prueba",
            email="test@example.com",
            phone="1234567890",
            address="Dirección de prueba",
            categoria="residencial",
            zona="Zona Test",
            lectura=100.0
        )

        # Crear lecturas históricas
        fecha_base = timezone.now().date()
        self.lecturas = []
        for i in range(3):
            lectura = HistoricoLectura.objects.create(
                usuario=self.usuario,
                fecha_lectura=fecha_base - timedelta(days=30 * i),
                lectura=100.0 - (20.0 * i)
            )
            self.lecturas.append(lectura)

        # Cliente para pruebas de vistas
        self.client = Client()

    def test_crear_factura(self):
        """
        Prueba la creación de una factura
        """
        factura = Factura.objects.create(
            usuario=self.usuario,
            consecutivo=Factura.get_next_consecutivo(),
            fecha_emision=date.today(),
            periodo_inicio=date.today() - timedelta(days=30),
            periodo_fin=date.today(),
            consumo=20.0,
            valor_total=Decimal('20000.00')
        )

        self.assertEqual(factura.consecutivo, 1)
        self.assertEqual(factura.usuario, self.usuario)
        self.assertEqual(factura.consumo, 20.0)
        self.assertEqual(factura.valor_total, Decimal('20000.00'))
        self.assertFalse(factura.pdf_generado)
        self.assertFalse(factura.email_enviado)

    def test_consecutivo_automatico(self):
        """
        Prueba que el consecutivo se genera automáticamente y de forma única
        """
        # Crear varias facturas
        facturas = []
        for i in range(3):
            factura = Factura.objects.create(
                usuario=self.usuario,
                consecutivo=Factura.get_next_consecutivo(),
                fecha_emision=date.today(),
                periodo_inicio=date.today() - timedelta(days=30),
                periodo_fin=date.today(),
                consumo=20.0,
                valor_total=Decimal('20000.00')
            )
            facturas.append(factura)

        # Verificar que los consecutivos son únicos y secuenciales
        self.assertEqual(facturas[0].consecutivo, 1)
        self.assertEqual(facturas[1].consecutivo, 2)
        self.assertEqual(facturas[2].consecutivo, 3)

    def test_historico_lecturas(self):
        """
        Prueba el registro y consulta de lecturas históricas
        """
        # Verificar que las lecturas se guardaron correctamente
        lecturas = HistoricoLectura.objects.filter(usuario=self.usuario).order_by('-fecha_lectura')
        self.assertEqual(lecturas.count(), 3)
        
        # Verificar que el orden es correcto (más reciente primero)
        self.assertEqual(lecturas[0].lectura, 100.0)
        self.assertEqual(lecturas[1].lectura, 80.0)
        self.assertEqual(lecturas[2].lectura, 60.0)

    def test_calculo_consumo(self):
        """
        Prueba el cálculo del consumo entre dos lecturas
        """
        ultima_lectura = self.lecturas[0].lectura
        penultima_lectura = self.lecturas[1].lectura
        consumo = ultima_lectura - penultima_lectura
        
        self.assertEqual(consumo, 20.0)

    def test_formateo_fecha_espanol(self):
        """
        Prueba el formateo de fechas en español
        """
        fecha_prueba = date(2025, 7, 17)
        fecha_formateada = formatear_fecha_espanol(fecha_prueba)
        self.assertEqual(fecha_formateada, "17 de julio de 2025")

    def test_generar_factura_view(self):
        """
        Prueba la vista de generación de facturas
        """
        url = reverse('generar_factura')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'generar_factura.html')

    def test_validacion_periodo_factura(self):
        """
        Prueba la validación de períodos de facturación
        """
        # Intentar generar factura con período inválido
        url = reverse('generar_factura')
        data = {
            'contrato': self.usuario.contrato,
            'fecha_emision': date.today().strftime('%Y-%m-%d'),
            'periodo_inicio': date.today().strftime('%Y-%m-%d'),
            'periodo_fin': (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)  # Debería redirigir en caso de error

    def test_generar_factura_post(self):
        """
        Prueba la generación de una factura vía POST
        """
        # Crear una lectura histórica para que haya datos para generar la factura
        HistoricoLectura.objects.create(
            usuario=self.usuario,
            fecha_lectura=date.today() - timedelta(days=30),
            lectura=80.0
        )
        
        url = reverse('generar_factura')
        data = {
            'contrato': self.usuario.contrato,
            'fecha_emision': date.today().strftime('%Y-%m-%d'),
            'periodo_inicio': (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'periodo_fin': date.today().strftime('%Y-%m-%d')
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        # La respuesta puede ser PDF o redirección en caso de error
        self.assertIn(response['Content-Type'], ['application/pdf', 'text/html; charset=utf-8'])

    def test_generar_todas_facturas(self):
        """
        Prueba la generación masiva de facturas
        """
        url = reverse('generar_factura')
        data = {
            'generar_todas': True,
            'periodo_inicio_todas': (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'periodo_fin_todas': date.today().strftime('%Y-%m-%d')
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')

    def test_consecutivos_masivos(self):
        """
        Prueba que los consecutivos se generen correctamente en la generación masiva de facturas
        """
        # Crear usuarios adicionales para la prueba
        usuario2 = UserAcueducto.objects.create(
            contrato="TEST003",
            numero_de_medidor="MED003",
            name="Usuario2",
            lastname="Prueba2",
            email="test2@example.com",
            categoria="residencial"
        )
        usuario3 = UserAcueducto.objects.create(
            contrato="TEST004",
            numero_de_medidor="MED004",
            name="Usuario3",
            lastname="Prueba3",
            email="test3@example.com",
            categoria="residencial"
        )
        
        # Crear lecturas para todos los usuarios
        fecha_base = timezone.now().date()
        usuarios = [self.usuario, usuario2, usuario3]
        for usuario in usuarios:
            HistoricoLectura.objects.create(
                usuario=usuario,
                fecha_lectura=fecha_base - timedelta(days=30),
                lectura=80.0
            )
            HistoricoLectura.objects.create(
                usuario=usuario,
                fecha_lectura=fecha_base,
                lectura=100.0
            )
        
        # Generar facturas masivas
        url = reverse('generar_factura')
        data = {
            'generar_todas': True,
            'periodo_inicio_todas': (fecha_base - timedelta(days=30)).strftime('%Y-%m-%d'),
            'periodo_fin_todas': fecha_base.strftime('%Y-%m-%d'),
            'consecutivo_desde': 1,
            'consecutivo_hasta': 3
        }
        response = self.client.post(url, data)
        
        # Verificar que se crearon las facturas
        facturas = Factura.objects.all().order_by('consecutivo')
        self.assertEqual(facturas.count(), 3)
        
        # Verificar que los consecutivos son secuenciales
        consecutivos = list(facturas.values_list('consecutivo', flat=True))
        self.assertEqual(consecutivos, [1, 2, 3])
        
        # Verificar que los consecutivos son únicos
        self.assertEqual(len(consecutivos), len(set(consecutivos)))

    def test_generacion_masiva_con_consecutivos_personalizados(self):
        """
        Prueba la generación masiva de facturas con rango de consecutivos personalizado
        """
        # Crear usuarios adicionales
        usuarios_adicionales = [
            {
                "contrato": f"TEST{i}",
                "numero_de_medidor": f"MED{i}",
                "name": f"Usuario{i}",
                "lastname": f"Prueba{i}",
                "email": f"test{i}@example.com",
                "categoria": "residencial"
            }
            for i in range(3, 6)  # Crear 3 usuarios más
        ]
        
        for data in usuarios_adicionales:
            UserAcueducto.objects.create(**data)
        
        # Crear lecturas para todos los usuarios
        fecha_base = timezone.now().date()
        usuarios = UserAcueducto.objects.all()
        for usuario in usuarios:
            # Primera lectura
            HistoricoLectura.objects.create(
                usuario=usuario,
                fecha_lectura=fecha_base - timedelta(days=30),
                lectura=100.0
            )
            # Segunda lectura
            HistoricoLectura.objects.create(
                usuario=usuario,
                fecha_lectura=fecha_base,
                lectura=150.0
            )
        
        # Generar facturas masivas con rango específico
        url = reverse('generar_factura')
        data = {
            'generar_todas': True,
            'periodo_inicio_todas': (fecha_base - timedelta(days=30)).strftime('%Y-%m-%d'),
            'periodo_fin_todas': fecha_base.strftime('%Y-%m-%d'),
            'consecutivo_desde': 1001,
            'consecutivo_hasta': 1005
        }
        response = self.client.post(url, data)
        
        # Verificar respuesta
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        
        # Verificar facturas generadas
        facturas = Factura.objects.all().order_by('consecutivo')
        self.assertEqual(facturas.count(), 4)  # 1 usuario de setUp + 3 adicionales
        
        # Verificar consecutivos
        consecutivos = list(facturas.values_list('consecutivo', flat=True))
        self.assertEqual(consecutivos, [1001, 1002, 1003, 1004])
        
        # Verificar que los consecutivos son únicos
        self.assertEqual(len(consecutivos), len(set(consecutivos)))

    def test_validacion_rango_consecutivos(self):
        """
        Prueba las validaciones del rango de consecutivos
        """
        fecha_base = timezone.now().date()
        url = reverse('generar_factura')
        
        # Caso 1: Consecutivo final menor que inicial
        data = {
            'generar_todas': True,
            'periodo_inicio_todas': (fecha_base - timedelta(days=30)).strftime('%Y-%m-%d'),
            'periodo_fin_todas': fecha_base.strftime('%Y-%m-%d'),
            'consecutivo_desde': 1002,
            'consecutivo_hasta': 1001
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)  # Redirección por error
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("consecutivo final debe ser mayor" in str(m) for m in messages))
        
        # Caso 2: Rango insuficiente para todos los usuarios
        # Crear usuarios adicionales
        for i in range(3, 6):
            UserAcueducto.objects.create(
                contrato=f"TEST{i}",
                numero_de_medidor=f"MED{i}",
                name=f"Usuario{i}",
                lastname=f"Prueba{i}",
                email=f"test{i}@example.com",
                categoria="residencial"
            )
        
        data = {
            'generar_todas': True,
            'periodo_inicio_todas': (fecha_base - timedelta(days=30)).strftime('%Y-%m-%d'),
            'periodo_fin_todas': fecha_base.strftime('%Y-%m-%d'),
            'consecutivo_desde': 1001,
            'consecutivo_hasta': 1002  # Solo 2 consecutivos para 4 usuarios
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)  # Redirección por error
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("rango de consecutivos" in str(m) for m in messages))

    def test_calculo_credito(self):
        """
        Prueba el cálculo de créditos y sus cuotas
        """
        # Configurar un crédito de prueba
        self.usuario.credito = Decimal('1000.00')
        self.usuario.credito_total_cuotas = 3
        self.usuario.credito_descripcion = "Crédito de prueba"
        self.usuario.credito_interes = Decimal('12.00')  # 12% anual
        self.usuario.save()

        # Verificar que el crédito se calculó correctamente
        self.assertEqual(self.usuario.credito_cuotas_restantes, 3)
        self.assertEqual(self.usuario.credito_valor_restante, Decimal('1000.00'))

        # Verificar que la cuota mensual se calculó correctamente (con interés)
        cuota_esperada = Decimal('340.02')  # Calculado manualmente
        self.assertAlmostEqual(self.usuario.credito_valor_cuota, cuota_esperada, delta=Decimal('0.01'))

    def test_calculo_otros_gastos(self):
        """
        Prueba el cálculo de otros gastos y sus cuotas
        """
        # Configurar otros gastos de prueba
        self.usuario.otros_gastos_valor = Decimal('600.00')
        self.usuario.otros_gastos_total_cuotas = 2
        self.usuario.otros_gastos_descripcion = "Otros gastos de prueba"
        self.usuario.otros_gastos_interes = Decimal('0.00')  # Sin interés
        self.usuario.save()

        # Verificar que otros gastos se calculó correctamente
        self.assertEqual(self.usuario.otros_gastos_cuotas_restantes, 2)
        self.assertEqual(self.usuario.otros_gastos_valor_restante, Decimal('600.00'))

        # Verificar que la cuota mensual se calculó correctamente (sin interés)
        cuota_esperada = Decimal('300.00')
        self.assertEqual(self.usuario.otros_gastos_valor_cuota, cuota_esperada)

    def test_factura_con_creditos_y_otros_gastos(self):
        """
        Prueba la generación de una factura que incluye créditos y otros gastos
        """
        # Configurar créditos y otros gastos
        self.usuario.credito = Decimal('1000.00')
        self.usuario.credito_total_cuotas = 3
        self.usuario.credito_interes = Decimal('12.00')
        self.usuario.otros_gastos_valor = Decimal('600.00')
        self.usuario.otros_gastos_total_cuotas = 2
        self.usuario.otros_gastos_interes = Decimal('0.00')
        self.usuario.save()

        # Crear una factura
        fecha_actual = timezone.now().date()
        factura = Factura.objects.create(
            usuario=self.usuario,
            consecutivo=1,
            fecha_emision=fecha_actual,
            periodo_inicio=fecha_actual - timedelta(days=30),
            periodo_fin=fecha_actual,
            consumo=20.0,
            valor_total=Decimal('20000.00')  # 20 m³ * 1000
        )

        # Actualizar los valores después de la factura
        cuota_credito = self.usuario.actualizar_credito_factura()
        cuota_otros_gastos = self.usuario.actualizar_otros_gastos_factura()

        # Verificar que las cuotas se descontaron correctamente
        self.assertEqual(self.usuario.credito_cuotas_restantes, 2)
        self.assertEqual(self.usuario.otros_gastos_cuotas_restantes, 1)

        # Verificar los valores de las cuotas
        self.assertAlmostEqual(cuota_credito, Decimal('340.02'), delta=Decimal('0.01'))
        self.assertEqual(cuota_otros_gastos, Decimal('300.00'))

        # Verificar que los valores restantes se actualizaron
        self.assertLess(self.usuario.credito_valor_restante, Decimal('1000.00'))
        self.assertLess(self.usuario.otros_gastos_valor_restante, Decimal('600.00'))

    def test_factura_con_creditos_y_otros_gastos(self):
        """
        Prueba que la factura incluya correctamente la información de créditos y otros gastos
        """
        # Configurar un usuario con crédito y otros gastos
        self.usuario.credito = Decimal('1000000.00')
        self.usuario.credito_descripcion = "Crédito para mejoras"
        self.usuario.credito_total_cuotas = 12
        self.usuario.credito_interes = Decimal('12.00')  # 12% anual
        
        self.usuario.otros_gastos_valor = Decimal('500000.00')
        self.usuario.otros_gastos_descripcion = "Instalación de medidor"
        self.usuario.otros_gastos_total_cuotas = 6
        self.usuario.otros_gastos_interes = Decimal('10.00')  # 10% anual
        
        self.usuario.save()  # Esto activará el cálculo de cuotas
        
        # Crear una lectura reciente
        HistoricoLectura.objects.create(
            usuario=self.usuario,
            fecha_lectura=date.today(),
            lectura=120.0
        )
        
        # Generar una factura
        url = reverse('generar_factura')
        data = {
            'contrato': self.usuario.contrato,
            'fecha_emision': date.today().strftime('%Y-%m-%d'),
            'periodo_inicio': (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'periodo_fin': date.today().strftime('%Y-%m-%d')
        }
        response = self.client.post(url, data)
        
        # Verificar que se generó la factura
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # Obtener la factura generada
        factura = Factura.objects.latest('fecha_creacion')
        
        # Verificar que los valores se calcularon correctamente
        self.assertGreater(factura.valor_total, self.usuario.credito_valor_cuota + self.usuario.otros_gastos_valor_cuota)
        
        # Verificar que se actualizaron las cuotas restantes
        usuario_actualizado = UserAcueducto.objects.get(pk=self.usuario.pk)
        self.assertEqual(usuario_actualizado.credito_cuotas_restantes, self.usuario.credito_total_cuotas - 1)
        self.assertEqual(usuario_actualizado.otros_gastos_cuotas_restantes, self.usuario.otros_gastos_total_cuotas - 1)

class UserAcueductoTests(TestCase):
    def setUp(self):
        self.usuario_data = {
            'contrato': 'TEST002',
            'numero_de_medidor': 'MED002',
            'name': 'Juan',
            'lastname': 'Pérez',
            'email': 'juan@example.com',
            'phone': '1234567890',
            'address': 'Calle Principal',
            'categoria': 'residencial',
            'zona': 'Norte'
        }

    def test_crear_usuario(self):
        """
        Prueba la creación de un usuario
        """
        usuario = UserAcueducto.objects.create(**self.usuario_data)
        self.assertEqual(usuario.contrato, 'TEST002')
        self.assertEqual(usuario.name, 'Juan')
        self.assertEqual(usuario.categoria, 'residencial')

    def test_validacion_categoria(self):
        """
        Prueba la validación de categorías
        """
        # Intentar crear usuario con categoría inválida
        self.usuario_data['categoria'] = 'invalida'
        usuario = UserAcueducto(**self.usuario_data)
        with self.assertRaises(ValidationError):
            usuario.full_clean()

    def test_credito_default(self):
        """
        Prueba los valores por defecto de crédito
        """
        usuario = UserAcueducto.objects.create(**self.usuario_data)
        self.assertEqual(usuario.credito, Decimal('0'))
        self.assertEqual(usuario.otros_gastos_valor, Decimal('0'))

    def test_str_representation(self):
        """
        Prueba la representación en string del usuario
        """
        usuario = UserAcueducto.objects.create(**self.usuario_data)
        expected_str = f"{usuario.name} {usuario.lastname} - {usuario.contrato}"
        self.assertEqual(str(usuario), expected_str)

    def test_email_unique(self):
        """
        Prueba que el email sea único
        """
        UserAcueducto.objects.create(**self.usuario_data)
        
        # Intentar crear otro usuario con el mismo email
        usuario_data_2 = self.usuario_data.copy()
        usuario_data_2['contrato'] = 'TEST003'
        usuario_data_2['numero_de_medidor'] = 'MED003'
        
        with self.assertRaises(IntegrityError):
            UserAcueducto.objects.create(**usuario_data_2)

    def test_contrato_unique(self):
        """
        Prueba que el número de contrato sea único
        """
        UserAcueducto.objects.create(**self.usuario_data)
        
        # Intentar crear otro usuario con el mismo contrato
        usuario_data_2 = self.usuario_data.copy()
        usuario_data_2['email'] = 'otro@example.com'
        usuario_data_2['numero_de_medidor'] = 'MED003'
        
        with self.assertRaises(IntegrityError):
            UserAcueducto.objects.create(**usuario_data_2)
