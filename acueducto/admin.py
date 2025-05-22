from django.contrib import admin
from django import forms
from .models import UserAcueducto

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



