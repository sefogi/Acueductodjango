from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.index, name='index'),
    path('lista/', views.lista_usuarios, name='lista_usuarios'),
    path('factura/', views.generar_factura, name='generar_factura'),
    path('toma-lectura/', views.toma_lectura, name='toma_lectura'),
    path('guardar-lectura/', views.guardar_lectura, name='guardar_lectura'),
    path('historico-lecturas/<str:contrato>/', views.historico_lecturas, name='historico_lecturas'),
    path('buscar-usuario/', views.buscar_usuario_por_contrato, name='buscar_usuario'),
    path('modificar-usuario/', views.modificar_usuario, name='modificar_usuario'),
    path('finalizar-ruta/', views.finalizar_ruta, name='finalizar_ruta'),
]
