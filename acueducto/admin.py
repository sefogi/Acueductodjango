from django.contrib import admin
from django import forms
from .models import UserAcueducto, HistoricoLectura

class UserAcueductoForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False
    )
    
    class Meta:
        model = UserAcueducto
        fields = '__all__'

@admin.register(UserAcueducto)
class UsersAcueductoAdmin(admin.ModelAdmin):
    form = UserAcueductoForm
    list_display = [
        'contrato',
        'date',
        'name',
        'lastname',
        'email',
        'phone',
        'address',
        'lectura'
    ]
    search_fields = [
        'contrato',
        'name',
        'lastname',
        'email',
        'phone',
        'address',
        'lectura'
    ]
    list_filter = [
        'contrato',
        'date',
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



