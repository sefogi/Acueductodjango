from django.db import models

# Create your models here.

class UserAcueducto(models.Model):
    CATEGORIA_CHOICES = [
        ('residencial', 'Residencial'),
        ('comercial', 'Comercial'),
    ]
    
    contrato = models.CharField(max_length=100, unique=True)
    fecha_ultima_lectura = models.DateField(verbose_name="Fecha Última Lectura", blank=True, null=True)
    name = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, unique=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.CharField(max_length=255, blank=True)
    lectura = models.FloatField(blank=True, null=True)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='residencial')
    zona = models.CharField(max_length=100, blank=True)
    credito = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credito_descripcion = models.TextField(blank=True)
    otros_gastos_valor = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    otros_gastos_descripcion = models.TextField(blank=True)
    numero_de_medidor = models.CharField(max_length=50, blank=True, null=True, unique=True)

    def __str__(self):
        return f"{self.name} {self.lastname} - {self.contrato}"

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
        if hasattr(self, 'total_ordenes') and hasattr(self, 'lecturas_completadas_count'):
            # Using annotated fields
            if self.total_ordenes == 0:
                return 0
            # Ensure counts are not None, though Count should return 0
            total_ordenes = self.total_ordenes if self.total_ordenes is not None else 0
            lecturas_completadas_count = self.lecturas_completadas_count if self.lecturas_completadas_count is not None else 0
            if total_ordenes == 0: # Double check after potential None conversion
                return 0
            return int((lecturas_completadas_count / total_ordenes) * 100)
        else: # Fallback for cases where annotation is not used
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






