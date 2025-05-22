from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('lista/', views.lista_usuarios, name='lista_usuarios'),
    path('factura/', views.generar_factura, name='generar_factura'),
]
