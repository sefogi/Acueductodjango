from django.contrib import admin
from .models import UserAcueducto

# Register your models here.
@admin.register(UserAcueducto)
class UsersAcueductoAdmin(admin.ModelAdmin):
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
    


