# Sistema de Facturación de Acueducto

Este es un sistema de gestión y facturación para un acueducto, desarrollado con Django. Permite gestionar usuarios, registrar lecturas de consumo, generar facturas y realizar seguimiento histórico del consumo de agua.

## Características Principales

### 1. Gestión de Usuarios

- Registro de nuevos usuarios con información completa
- Número de contrato único por usuario
- Datos personales: nombre, apellido, dirección, email y teléfono
- Listado y búsqueda de usuarios

### 2. Registro de Lecturas

- Sistema de login para lectores de medidores
- Registro de lecturas con fecha automática
- Validación de datos ingresados
- Histórico de lecturas por usuario
- Visualización de las últimas 6 lecturas

### 3. Generación de Facturas

- Generación individual o masiva de facturas
- Formato PDF profesional
- Inclusión de:
  - Información del cliente
  - Lecturas actual y anterior
  - Cálculo de consumo
  - Gráfico de consumo histórico
  - Fecha de emisión personalizable
- Opción de envío por email automático

### 4. Visualización de Datos

- Gráficos de consumo histórico
- Estadísticas de lectura
- Interfaz intuitiva y responsive

## Tecnologías Utilizadas

- **Backend:** Django
- **Frontend:** HTML, CSS, JavaScript
- **Base de Datos:** SQLite
- **Gráficos:** Chart.js
- **Generación de PDFs:** WeasyPrint
- **Estilos:** CSS personalizado

## Estructura del Proyecto

```
acueducto/
├── static/          # Archivos estáticos (CSS, JS, imágenes)
├── templates/       # Plantillas HTML
├── templatetags/    # Filtros personalizados
├── migrations/      # Migraciones de base de datos
├── models.py        # Modelos de datos
├── views.py         # Lógica de la aplicación
└── urls.py         # Configuración de rutas
```

## Modelos Principales

### UserAcueducto

- Contrato (único)
- Nombre y apellido
- Dirección
- Email
- Teléfono
- Lectura actual
- Fecha de última lectura

### HistoricoLectura

- Usuario (ForeignKey)
- Lectura
- Fecha de lectura

## Funcionalidades por Rol

### Administrador

- Gestión completa de usuarios
- Generación de facturas individuales o masivas
- Acceso a todos los registros históricos

### Lector de Medidores

- Registro de nuevas lecturas
- Consulta de histórico de lecturas
- Búsqueda de usuarios por contrato

## Proceso de Facturación

1. **Ingreso de Lectura**

   - Registro de nueva lectura por el lector
   - Almacenamiento en histórico
2. **Generación de Factura**

   - Selección de usuario por número de contrato
   - Selección de fecha de emisión
   - Cálculo automático de consumo
   - Generación de PDF
3. **Distribución**

   - Descarga directa del PDF
   - Envío por correo electrónico
   - Generación masiva en ZIP

## Contacto y Soporte

Para cualquier consulta sobre el sistema, comuníquese al teléfono: +34 617786268

## Requisitos de Sistema

- Python 3.8+
- Django 3.2+
- WeasyPrint
- Navegador web moderno

## Licencia y Propiedad

Este software es propietario y está protegido por derechos de autor © 2025 Sebastian Forero Giraldo.
Desarrollado por Sebastian Forero Giraldo - Fullstack Developer.
Todos los derechos están reservados.

El uso de este software está sujeto a las siguientes restricciones:

- No se permite la copia o distribución sin autorización
- No se permite la modificación del código fuente
- No se permite la ingeniería inversa
- No se permite la transferencia de la licencia

Para obtener una licencia de uso o información comercial, contacte al propietario del software.

Vea el archivo [LICENSE](LICENSE) para los términos y condiciones completos.

---

Sistema desarrollado por:
Sebastian Forero Giraldo
Fullstack Developer
Email: sebast18@gmail.com
Teléfono: +34 617786268

© 2025 Todos los derechos reservados
