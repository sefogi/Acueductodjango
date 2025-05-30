from django import forms
from .models import UserAcueducto

class UserAcueductoForm(forms.ModelForm):
    class Meta:
        model = UserAcueducto
        fields = [
            'contrato', 'fecha_ultima_lectura', 'name', 'lastname', 'email', 'phone',
            'address', 'lectura', 'categoria', 'zona', 'credito',
            'credito_descripcion', 'otros_gastos_valor', 'otros_gastos_descripcion'
        ]
        widgets = {
            'fecha_ultima_lectura': forms.DateInput(attrs={'type': 'date'}),
            'lectura': forms.NumberInput(attrs={'step': 'any'}), # Allows decimal input
            'credito': forms.NumberInput(attrs={'step': 'any'}),
            'otros_gastos_valor': forms.NumberInput(attrs={'step': 'any'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set all fields to not required by default, then enable as needed
        for field_name, field in self.fields.items():
            field.required = False

        # Fields that are genuinely optional (can be blank in DB)
        optional_fields = [
            'fecha_ultima_lectura', 'phone', 'address', 'lectura', 'zona',
            'credito', 'credito_descripcion',
            'otros_gastos_valor', 'otros_gastos_descripcion'
        ]
        # Fields that are mandatory
        required_fields = ['contrato', 'name', 'lastname', 'email', 'categoria']

        for field_name in required_fields:
            self.fields[field_name].required = True

        # For optional fields, ensure they are not marked as required
        # This loop is mostly for clarity, as default was set to False already
        for field_name in optional_fields:
            self.fields[field_name].required = False

        # Special case for 'lectura' if it has a default or can be truly null
        # If 'lectura' can be empty, it should be `null=True, blank=True` in the model
        # and `required=False` here.
        # If 'fecha_ultima_lectura' can be empty, it should be `null=True, blank=True` in the model.
        # Current model has:
        # fecha_ultima_lectura = models.DateField(null=True, blank=True)
        # lectura = models.FloatField(null=True, blank=True)
        # So, required=False is correct for them.

        # Add placeholders or other attributes if needed
        self.fields['contrato'].widget.attrs.update({'placeholder': 'Número de contrato'})
        self.fields['name'].widget.attrs.update({'placeholder': 'Nombres'})
        self.fields['lastname'].widget.attrs.update({'placeholder': 'Apellidos'})
        self.fields['email'].widget.attrs.update({'placeholder': 'correo@ejemplo.com'})
        self.fields['phone'].widget.attrs.update({'placeholder': 'Número de teléfono (opcional)'})
        self.fields['address'].widget.attrs.update({'placeholder': 'Dirección (opcional)'})
        self.fields['lectura'].widget.attrs.update({'placeholder': 'Lectura actual (opcional)'})
        self.fields['credito_descripcion'].widget.attrs.update({'placeholder': 'Descripción del crédito (si aplica)'})
        self.fields['otros_gastos_descripcion'].widget.attrs.update({'placeholder': 'Descripción de otros gastos (si aplica)'})
