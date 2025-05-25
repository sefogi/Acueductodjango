from django import forms
from .models import UserAcueducto

class UserAcueductoForm(forms.ModelForm):
    class Meta:
        model = UserAcueducto
        fields = [
            'contrato',
            'numero_de_medidor',
            'name', 
            'lastname', 
            'email', 
            'phone', 
            'address', 
            'categoria', 
            'zona', 
            'fecha_ultima_lectura', # Renamed from 'date'
            'credito', 
            'credito_descripcion', 
            'otros_gastos_valor', 
            'otros_gastos_descripcion',
            'lectura', # Added lectura field
        ]
        labels = {
            'contrato': 'Número de Contrato',
            'numero_de_medidor': 'Número de Medidor',
            'name': 'Nombres',
            'lastname': 'Apellidos',
            'email': 'Correo Electrónico',
            'phone': 'Teléfono',
            'address': 'Dirección',
            'categoria': 'Categoría',
            'zona': 'Zona',
            'fecha_ultima_lectura': 'Fecha de Última Lectura',
            'credito': 'Crédito Asignado',
            'credito_descripcion': 'Descripción del Crédito',
            'otros_gastos_valor': 'Valor de Otros Gastos',
            'otros_gastos_descripcion': 'Descripción de Otros Gastos',
            'lectura': 'Lectura Actual', # Added lectura label
        }
        widgets = {
            'fecha_ultima_lectura': forms.DateInput(attrs={'type': 'date'}), # Renamed from 'date'
            'credito_descripcion': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Descripción del crédito'}),
            'otros_gastos_descripcion': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Descripción de otros gastos'}),
            'lectura': forms.NumberInput(attrs={'placeholder': 'Valor numérico del medidor'}), # Added lectura widget
            'numero_de_medidor': forms.TextInput(attrs={'placeholder': 'Número del medidor'}),
        }

    def __init__(self, *args, **kwargs):
        super(UserAcueductoForm, self).__init__(*args, **kwargs)
        
        # Fields that should be optional
        self.fields['fecha_ultima_lectura'].required = False # Renamed from 'date'
        self.fields['credito_descripcion'].required = False
        self.fields['otros_gastos_descripcion'].required = False
        self.fields['phone'].required = False # Assuming phone can be optional
        self.fields['email'].required = False # Assuming email can be optional
        self.fields['lectura'].required = False # Made lectura optional
        self.fields['numero_de_medidor'].required = True

        # If instance is provided, it's an update, so disable 'contrato'
        if self.instance and self.instance.pk:
            self.fields['contrato'].disabled = True
            # self.fields['fecha_ultima_lectura'].disabled = True # Example if date should not be changed on update

        # Add placeholders
        self.fields['contrato'].widget.attrs.update({'placeholder': 'Número de Contrato'})
        self.fields['numero_de_medidor'].widget.attrs.update({'placeholder': 'Número del medidor'})
        self.fields['name'].widget.attrs.update({'placeholder': 'Nombres'})
        self.fields['lastname'].widget.attrs.update({'placeholder': 'Apellidos'})
        self.fields['email'].widget.attrs.update({'placeholder': 'correo@ejemplo.com'})
        self.fields['phone'].widget.attrs.update({'placeholder': 'Número de Teléfono'})
        self.fields['address'].widget.attrs.update({'placeholder': 'Dirección Completa'})
        self.fields['zona'].widget.attrs.update({'placeholder': 'Zona'})
        self.fields['credito'].widget.attrs.update({'placeholder': 'Valor del crédito (ej: 100.00)'})
        self.fields['otros_gastos_valor'].widget.attrs.update({'placeholder': 'Valor (ej: 50.00)'})

        # Add CSS classes for styling if needed (example)
        for field_name in self.fields:
            if not isinstance(self.fields[field_name].widget, forms.CheckboxInput):
                 self.fields[field_name].widget.attrs.update({'class': 'form-control-field'})
        
        self.fields['categoria'].widget.attrs.update({'class': 'form-control-select'})
        self.fields['zona'].widget.attrs.update({'class': 'form-control-field'}) # Assuming zona is text input based on original template
