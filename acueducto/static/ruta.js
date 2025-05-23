async function finalizarRuta(rutaId) {
    if (!confirm('¿Estás seguro que deseas finalizar esta ruta? Esta acción eliminará la ruta inmediatamente.')) {
        return;
    }

    try {
        const response = await fetch('/finalizar-ruta/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ ruta_id: rutaId })
        });

        const data = await response.json();

        if (response.ok) {
            alert(data.message);
            if (data.redirect) {
                window.location.href = data.redirect;
            } else {
                location.reload();
            }
        } else {
            alert(data.error || 'Error al finalizar la ruta');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al finalizar la ruta');
    }
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

async function guardarLectura(event, usuarioId) {
    event.preventDefault();
    const form = event.target;
    const lecturaInput = form.querySelector('input[name="lectura"]');
    const lectura = lecturaInput.value;

    try {
        const response = await fetch('/guardar-lectura/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                usuario_id: usuarioId,
                lectura: lectura
            })
        });

        const data = await response.json();

        if (response.ok) {
            // Marcar el elemento como completado
            const usuarioItem = document.getElementById(`usuario-${usuarioId}`);
            usuarioItem.classList.add('completado');
            
            // Reemplazar el formulario con un mensaje de éxito
            const formContainer = form.parentElement;
            formContainer.innerHTML = '<span class="lectura-completada">Lectura registrada</span>';
            
            // Actualizar el contador de lecturas completadas
            const lecturasTotales = document.querySelectorAll('.usuario-ruta-item').length;
            const lecturasCompletadas = document.querySelectorAll('.usuario-ruta-item.completado').length;
            
            // Actualizar la barra de progreso
            const progresoBarra = document.querySelector('.progreso-barra');
            const progresoTexto = document.querySelector('.progreso-texto');
            const porcentaje = (lecturasCompletadas / lecturasTotales) * 100;
            
            if (progresoBarra && progresoTexto) {
                progresoBarra.style.width = porcentaje + '%';
                progresoTexto.textContent = `Progreso: ${lecturasCompletadas} de ${lecturasTotales} lecturas`;
            }
            
            // Si todas las lecturas están completadas, mostrar el botón de finalizar
            if (lecturasCompletadas === lecturasTotales) {
                const rutaActiva = document.querySelector('.ruta-activa');
                const rutaId = rutaActiva.dataset.rutaId;
                
                if (!document.querySelector('.finalizar-ruta')) {
                    const finalizarDiv = document.createElement('div');
                    finalizarDiv.className = 'finalizar-ruta';
                    finalizarDiv.innerHTML = `
                        <button onclick="finalizarRuta(${rutaId})" class="btn-finalizar">
                            Finalizar Ruta
                        </button>
                    `;
                    rutaActiva.appendChild(finalizarDiv);
                }
            }
        } else {
            alert(data.error || 'Error al guardar la lectura');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al guardar la lectura');
    }
}
