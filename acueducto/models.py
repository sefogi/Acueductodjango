from django.db import models
from decimal import Decimal

# Create your models here.

class UserAcueducto(models.Model):
    CATEGORIA_CHOICES = [
        ('residencial', 'Residencial'),
        ('comercial', 'Comercial'),
    ]
    
    contrato = models.CharField(max_length=100, unique=True)
    numero_de_medidor = models.CharField(max_length=50, unique=True, blank=True, null=True)
    fecha_ultima_lectura = models.DateField(blank=True, null=True) # Renamed from 'date', removed max_length
    name = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, unique=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.CharField(max_length=255, blank=True)
    lectura = models.FloatField(blank=True, null=True)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='residencial')
    zona = models.CharField(max_length=100, blank=True)
    # Campos para crédito
    credito = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credito_descripcion = models.TextField(blank=True)
    credito_total_cuotas = models.IntegerField(default=1)
    credito_cuotas_restantes = models.IntegerField(default=0)
    credito_valor_cuota = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credito_interes = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Porcentaje de interés
    credito_valor_restante = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Campos para otros gastos
    otros_gastos_valor = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    otros_gastos_descripcion = models.TextField(blank=True)
    otros_gastos_total_cuotas = models.IntegerField(default=1)
    otros_gastos_cuotas_restantes = models.IntegerField(default=0)
    otros_gastos_valor_cuota = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    otros_gastos_interes = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Porcentaje de interés
    otros_gastos_valor_restante = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.name} {self.lastname} - {self.contrato}"

    def get_ultima_lectura(self):
        """
        Obtiene la última lectura del usuario incluyendo la fecha.
        Returns:
            tuple: (fecha_lectura, lectura) o (None, None) si no hay lecturas
        """
        ultima_lectura = self.lecturas.order_by('-fecha_lectura').first()
        if ultima_lectura:
            return ultima_lectura.fecha_lectura, ultima_lectura.lectura
        return None, None

    def calcular_credito(self):
        """
        Calcula los valores del crédito basado en el monto total, número de cuotas e interés.
        Utiliza la fórmula de amortización con interés compuesto:
        PMT = P * (r * (1 + r)^n) / ((1 + r)^n - 1)
        Donde:
        PMT = Pago mensual
        P = Principal (monto del crédito)
        r = Tasa de interés mensual
        n = Número de cuotas
        """
        if self.credito > 0 and self.credito_total_cuotas > 0:
            # Convertir valores a Decimal para mayor precisión
            principal = Decimal(str(self.credito))
            n_cuotas = Decimal(str(self.credito_total_cuotas))
            tasa_anual = Decimal(str(self.credito_interes))
            
            # Calculamos la tasa mensual (dividir por 100 para convertir porcentaje)
            tasa_mensual = tasa_anual / Decimal('100') / Decimal('12')
            
            if tasa_mensual > 0:
                # Fórmula de cuota con interés compuesto
                factor = (1 + tasa_mensual) ** n_cuotas
                cuota = principal * (tasa_mensual * factor) / (factor - 1)
            else:
                # Sin interés, división simple
                cuota = principal / n_cuotas
                
            self.credito_valor_cuota = round(cuota, 2)
            self.credito_cuotas_restantes = int(n_cuotas)
            self.credito_valor_restante = principal
            
            # Guardar los cambios
            self.save(update_fields=['credito_valor_cuota', 'credito_cuotas_restantes', 'credito_valor_restante'])

    def calcular_otros_gastos(self):
        """
        Calcula los valores de otros gastos basado en el monto total, número de cuotas e interés.
        Utiliza la misma fórmula de amortización que el crédito.
        """
        if self.otros_gastos_valor > 0 and self.otros_gastos_total_cuotas > 0:
            # Convertir valores a Decimal para mayor precisión
            principal = Decimal(str(self.otros_gastos_valor))
            n_cuotas = Decimal(str(self.otros_gastos_total_cuotas))
            tasa_anual = Decimal(str(self.otros_gastos_interes))
            
            # Calculamos la tasa mensual (dividir por 100 para convertir porcentaje)
            tasa_mensual = tasa_anual / Decimal('100') / Decimal('12')
            
            if tasa_mensual > 0:
                # Fórmula de cuota con interés compuesto
                factor = (1 + tasa_mensual) ** n_cuotas
                cuota = principal * (tasa_mensual * factor) / (factor - 1)
            else:
                # Sin interés, división simple
                cuota = principal / n_cuotas
            
            self.otros_gastos_valor_cuota = round(cuota, 2)
            self.otros_gastos_cuotas_restantes = int(n_cuotas)
            self.otros_gastos_valor_restante = principal
            
            # Guardar los cambios
            self.save(update_fields=['otros_gastos_valor_cuota', 'otros_gastos_cuotas_restantes', 'otros_gastos_valor_restante'])
            
    def actualizar_credito_factura(self):
        """
        Actualiza el estado del crédito después de generar una factura y retorna el valor de la cuota.
        """
        if self.credito_cuotas_restantes > 0:
            cuota = self.credito_valor_cuota
            self.credito_cuotas_restantes -= 1
            self.credito_valor_restante -= cuota
            if self.credito_cuotas_restantes == 0:
                self.credito = Decimal('0')
            self.save(update_fields=['credito_cuotas_restantes', 'credito_valor_restante', 'credito'])
            return cuota
        return Decimal('0')
        
    def actualizar_otros_gastos_factura(self):
        """
        Actualiza el estado de otros gastos después de generar una factura y retorna el valor de la cuota.
        """
        if self.otros_gastos_cuotas_restantes > 0:
            cuota = self.otros_gastos_valor_cuota
            self.otros_gastos_cuotas_restantes -= 1
            self.otros_gastos_valor_restante -= cuota
            if self.otros_gastos_cuotas_restantes == 0:
                self.otros_gastos_valor = Decimal('0')
            self.save(update_fields=['otros_gastos_cuotas_restantes', 'otros_gastos_valor_restante', 'otros_gastos_valor'])
            return cuota
        return Decimal('0')
            


    def actualizar_credito_factura(self):
        """
        Actualiza los valores del crédito después de generar una factura.
        Retorna el valor de la cuota actual.
        """
        if self.credito_cuotas_restantes > 0:
            cuota_actual = self.credito_valor_cuota
            self.credito_cuotas_restantes -= 1
            self.credito_valor_restante = max(0, self.credito_valor_restante - self.credito_valor_cuota)
            self.save()
            return cuota_actual
        return 0

    def actualizar_otros_gastos_factura(self):
        """
        Actualiza los valores de otros gastos después de generar una factura.
        Retorna el valor de la cuota actual.
        """
        if self.otros_gastos_cuotas_restantes > 0:
            cuota_actual = self.otros_gastos_valor_cuota
            self.otros_gastos_cuotas_restantes -= 1
            self.otros_gastos_valor_restante = max(0, self.otros_gastos_valor_restante - self.otros_gastos_valor_cuota)
            self.save()
            return cuota_actual
        return 0

    def save(self, *args, **kwargs):
        is_new = not self.pk or self._state.adding
        
        # Detectar cambios en los valores relevantes
        if is_new:
            old_credito = Decimal('0')
            old_otros_gastos = Decimal('0')
        else:
            old_instance = UserAcueducto.objects.get(pk=self.pk)
            old_credito = old_instance.credito
            old_otros_gastos = old_instance.otros_gastos_valor
            
        # Guardar primero para tener el ID si es nuevo
        super().save(*args, **kwargs)
        
        # Recalcular si es nuevo o si los valores cambiaron
        if is_new or self.credito != old_credito:
            self.calcular_credito()
        if is_new or self.otros_gastos_valor != old_otros_gastos:
            self.calcular_otros_gastos()
            
        if self.credito_valor_cuota or self.otros_gastos_valor_cuota:
            super().save(update_fields=[
                'credito_valor_cuota', 'credito_cuotas_restantes', 'credito_valor_restante',
                'otros_gastos_valor_cuota', 'otros_gastos_cuotas_restantes', 'otros_gastos_valor_restante'
            ])

class HistoricoLectura(models.Model):
    usuario = models.ForeignKey(UserAcueducto, on_delete=models.CASCADE, related_name='lecturas')
    fecha_lectura = models.DateField()
    lectura = models.FloatField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha_lectura']
        
    def __str__(self):
        return f"Lectura {self.usuario.contrato} - {self.fecha_lectura}"

class Ruta(models.Model):
    nombre = models.CharField(max_length=100)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)
    usuarios = models.ManyToManyField(UserAcueducto, through='OrdenRuta')
    activa = models.BooleanField(default=True)

    def __str__(self):
        estado = "Activa" if self.activa else "Finalizada"
        return f"Ruta {self.nombre} - {estado} ({self.fecha_creacion.strftime('%d/%m/%Y')})"

    def porcentaje_completado(self):
        total_lecturas = self.ordenruta_set.count()
        if total_lecturas == 0:
            return 0
        lecturas_completadas = self.ordenruta_set.filter(lectura_tomada=True).count()
        return int((lecturas_completadas / total_lecturas) * 100)

class OrdenRuta(models.Model):
    ruta = models.ForeignKey(Ruta, on_delete=models.CASCADE)
    usuario = models.ForeignKey(UserAcueducto, on_delete=models.CASCADE)
    orden = models.IntegerField()
    lectura_tomada = models.BooleanField(default=False)

    class Meta:
        ordering = ['orden']
        unique_together = [['ruta', 'orden']]

    def __str__(self):
        return f"{self.ruta} - {self.usuario.contrato} (Orden: {self.orden})"

class Factura(models.Model):
    usuario = models.ForeignKey(UserAcueducto, on_delete=models.CASCADE, related_name='facturas')
    consecutivo = models.IntegerField(unique=True)
    fecha_emision = models.DateField()
    periodo_inicio = models.DateField()
    periodo_fin = models.DateField()
    consumo = models.DecimalField(max_digits=10, decimal_places=2)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    pdf_generado = models.BooleanField(default=False)
    email_enviado = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_emision', '-consecutivo']

    def __str__(self):
        return f"Factura #{self.consecutivo} - {self.usuario.contrato}"

    @classmethod
    def existe_factura_en_periodo(cls, usuario, periodo_inicio, periodo_fin):
        """
        Verifica si ya existe una factura para el usuario en el período especificado.
        """
        return cls.objects.filter(
            usuario=usuario,
            periodo_inicio__lte=periodo_fin,
            periodo_fin__gte=periodo_inicio
        ).exists()

    @classmethod
    def tiene_lecturas_en_periodo(cls, usuario, periodo_inicio, periodo_fin):
        """
        Verifica si el usuario tiene lecturas en el período especificado.
        """
        return HistoricoLectura.objects.filter(
            usuario=usuario,
            fecha_lectura__range=(periodo_inicio, periodo_fin)
        ).exists()

    @classmethod
    def get_next_consecutivo(cls, consecutivo_inicio=None):
        """
        Obtiene el siguiente número de consecutivo.
        Si se proporciona consecutivo_inicio, lo usa como base,
        de lo contrario genera el siguiente número automáticamente.
        """
        from django.db import transaction
        
        with transaction.atomic():
            if consecutivo_inicio is not None:
                return consecutivo_inicio
            
            # Select for update para bloquear la fila y evitar condiciones de carrera
            ultima_factura = cls.objects.select_for_update().order_by('-consecutivo').first()
            if ultima_factura:
                return ultima_factura.consecutivo + 1
            return 1






