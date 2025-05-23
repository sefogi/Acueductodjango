document.addEventListener('DOMContentLoaded', function() {
    const busquedaInput = document.getElementById('busqueda_contrato');
    const selectUsuario = document.getElementById('contrato');
    const buscarBtn = document.getElementById('buscarContrato');
    const usuarioInfo = document.getElementById('usuarioInfo');
    const nombreUsuarioSpan = document.getElementById('nombreUsuario');

    function buscarUsuarioPorContrato() {
        const numeroContrato = busquedaInput.value.trim();
        
        if (!numeroContrato) {
            alert('Por favor ingrese un número de contrato');
            return;
        }

        fetch(`/buscar-usuario/?contrato=${numeroContrato}`)
            .then(response => response.json())
            .then(data => {
                if (data.found) {
                    // Seleccionar el usuario en el dropdown
                    const options = selectUsuario.options;
                    for (let i = 0; i < options.length; i++) {
                        if (options[i].value === data.contrato) {
                            selectUsuario.selectedIndex = i;
                            break;
                        }
                    }
                    
                    // Mostrar información del usuario
                    nombreUsuarioSpan.textContent = data.nombre;
                    usuarioInfo.style.display = 'block';
                } else {
                    alert('No se encontró ningún usuario con ese número de contrato');
                    usuarioInfo.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Ocurrió un error al buscar el usuario');
            });
    }

    // Event listeners
    if (buscarBtn) {
        buscarBtn.addEventListener('click', buscarUsuarioPorContrato);
    }

    if (busquedaInput) {
        busquedaInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                buscarUsuarioPorContrato();
            }
        });
    }

    // Actualizar información cuando se cambia la selección del dropdown
    if (selectUsuario) {
        selectUsuario.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            if (selectedOption.value) {
                busquedaInput.value = selectedOption.value;
                nombreUsuarioSpan.textContent = selectedOption.text.split(' - ')[1];
                usuarioInfo.style.display = 'block';
            } else {
                usuarioInfo.style.display = 'none';
            }
        });
    }
});

console.log("hola capullos")