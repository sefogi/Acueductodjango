from django.contrib import admin
from django import forms
from .models import UserAcueducto, HistoricoLectura

# This local form might be redundant if the main UserAcueductoForm from forms.py is sufficient.
# For now, let's update it as per the field rename.
class UserAcueductoAdminForm(forms.ModelForm): # Renamed for clarity, or could be removed
    fecha_ultima_lectura = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False
    )
    
    class Meta:
        model = UserAcueducto
        fields = '__all__'

@admin.register(UserAcueducto)
class UsersAcueductoAdmin(admin.ModelAdmin):
    form = UserAcueductoAdminForm # Use the updated form name if changed
    list_display = [
        'contrato',
        'numero_de_medidor',
        'fecha_ultima_lectura', # Renamed from date
        'name',
        'lastname',
        'email',
        'phone',
        'address',
        'lectura'
    ]
    search_fields = [
        'contrato',
        'numero_de_medidor',
        'name',
        'lastname',
        'email',
        'phone',
        'address',
        'lectura'
    ]
    list_filter = [
        'contrato',
        'fecha_ultima_lectura', # Renamed from date
        'name',
        'lastname',
        'email',
        'phone',
        'address',
        'lectura'
    ]

@admin.register(HistoricoLectura)
class HistoricoLecturaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'fecha_lectura', 'lectura')
    list_filter = ('fecha_lectura',)
    search_fields = ('usuario__contrato', 'usuario__name')



