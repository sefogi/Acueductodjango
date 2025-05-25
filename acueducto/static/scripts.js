// Funciones de utilidad para UI
function showLoading(element) {
    element.classList.add('loading');
    element.disabled = true;
}

function hideLoading(element) {
    element.classList.remove('loading');
    element.disabled = false;
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger';
    errorDiv.textContent = message;
    document.body.insertBefore(errorDiv, document.body.firstChild);
    setTimeout(() => errorDiv.remove(), 5000);
}

// Funciones específicas para la búsqueda de usuarios
function actualizarSelectUsuario(selectUsuario, contrato) {
    const options = selectUsuario?.options;
    if (!options) return;

    for (let i = 0; i < options.length; i++) {
        if (options[i].value === contrato) {
            selectUsuario.selectedIndex = i;
            break;
        }
    }
}

function mostrarInfoUsuario(nombreUsuarioSpan, usuarioInfo, nombre) {
    if (!nombreUsuarioSpan || !usuarioInfo) return;
    nombreUsuarioSpan.textContent = nombre;
    usuarioInfo.style.display = 'block';
}

function ocultarInfoUsuario(usuarioInfo) {
    if (usuarioInfo) {
        usuarioInfo.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Elementos del DOM
    const busquedaInput = document.getElementById('busqueda_contrato');
    const selectUsuario = document.getElementById('contrato');
    const buscarBtn = document.getElementById('buscarContrato');
    const usuarioInfo = document.getElementById('usuarioInfo');
    const nombreUsuarioSpan = document.getElementById('nombreUsuario');

    async function buscarUsuarioPorContrato() {
        if (!buscarBtn) return;

        const numeroContrato = busquedaInput?.value?.trim();
        
        if (!numeroContrato) {
            showError('Por favor ingrese un número de contrato');
            return;
        }

        showLoading(buscarBtn);

        try {
            const response = await fetch(`/buscar-usuario/?contrato=${numeroContrato}`);
            if (!response.ok) throw new Error('Error en la respuesta del servidor');
            
            const data = await response.json();
            
            if (data.found) {
                actualizarSelectUsuario(selectUsuario, data.contrato);
                mostrarInfoUsuario(nombreUsuarioSpan, usuarioInfo, data.nombre);
            } else {
                showError('No se encontró ningún usuario con ese número de contrato');
                ocultarInfoUsuario(usuarioInfo);
            }
        } catch (error) {
            console.error('Error:', error);
            showError('Ocurrió un error al buscar el usuario');
        } finally {
            hideLoading(buscarBtn);
        }
    }

    // Event listeners para búsqueda
    buscarBtn?.addEventListener('click', buscarUsuarioPorContrato);
    
    busquedaInput?.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            buscarUsuarioPorContrato();
        }
    });

    // Manejo de selección de usuario con validación mejorada
    selectUsuario?.addEventListener('change', function() {
        const nombreUsuario = this.options[this.selectedIndex]?.text?.split(' - ')[1];
        const valor = this.options[this.selectedIndex]?.value;

        if (!valor || !nombreUsuario) {
            ocultarInfoUsuario(usuarioInfo);
            return;
        }

        if (busquedaInput) {
            busquedaInput.value = valor;
        }
        
        mostrarInfoUsuario(nombreUsuarioSpan, usuarioInfo, nombreUsuario);
    });

    // Configuración de drag and drop para rutas
    const rutaForm = document.getElementById('rutaForm');
    const usuariosLista = document.getElementById('usuariosLista');

    if (!usuariosLista) return;

    function actualizarOrdenRuta() {
        return Array.from(usuariosLista.children).map(item => item.dataset.id);
    }

    function configurarDragAndDrop(item) {
        let draggedItem = null;
        
        item.setAttribute('draggable', 'true');
        
        item.addEventListener('dragstart', (e) => {
            draggedItem = item;
            item.classList.add('dragging');
            setTimeout(() => item.style.opacity = '0.5', 0);
        });

        item.addEventListener('dragend', () => {
            item.classList.remove('dragging');
            item.style.opacity = '1';
            actualizarOrdenRuta();
        });

        item.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (item === draggedItem) return;

            const rect = item.getBoundingClientRect();
            const y = e.clientY - rect.top;
            
            if (y < rect.height / 2) {
                item.parentNode.insertBefore(draggedItem, item);
            } else {
                item.parentNode.insertBefore(draggedItem, item.nextSibling);
            }
        });
    }

    // Configurar drag and drop para cada elemento
    document.querySelectorAll('.usuario-item').forEach(configurarDragAndDrop);

    // Validación del formulario de ruta
    rutaForm?.addEventListener('submit', function(e) {
        const usuariosOrdenados = actualizarOrdenRuta();
        const nombreRuta = document.getElementById('nombre_ruta')?.value?.trim();
        
        if (!nombreRuta) {
            e.preventDefault();
            showError('Por favor, ingrese un nombre para la ruta');
            return;
        }

        if (usuariosOrdenados.length < 2) {
            e.preventDefault();
            showError('Una ruta debe contener al menos dos usuarios');
            
        }
    });
});