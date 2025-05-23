from django.db import models

# Create your models here.

class UserAcueducto(models.Model):
    contrato = models.CharField(max_length=100, unique=True)
    date = models.DateField(max_length=10, blank=True, null=True)
    name = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, unique=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.CharField(max_length=255, blank=True)
    lectura = models.FloatField(blank=True, null=True)
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






