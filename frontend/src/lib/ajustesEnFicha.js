/**
 * LOS AJUSTES DE LA APP, EN LA FICHA (doc 19-08, bloque 07).
 *
 * El de MACROS · Método/Reales y el de VISTA se guardaban solo en
 * localStorage: al entrar desde otro móvil salía todo por defecto otra vez. Ahora cada
 * cambio se escribe también en la ficha (`ajustes_app`), y al entrar la ficha rellena el
 * localStorage antes de que las pantallas lean.
 * (El tema claro/oscuro también vivía aquí; se retiró con el claro, doc 21-08.)
 *
 * A PROPÓSITO SIN `X-Actuar-Como`: cuando el entrenador trabaja «como» un cliente y
 * cambia el tema, ese tema es SUYO, del entrenador; con la cabecera puesta se escribiría
 * en la ficha del cliente sin que nadie lo pidiera (la trampa de siempre, ver
 * lib/cabeceras.js pero al revés).
 */

const API = process.env.REACT_APP_BACKEND_URL || '';

// clave de la ficha -> clave del localStorage que leen las pantallas
export const CLAVES_LOCALES = {
    modo_macros: 'nutricion-modo-macros',
    vista: 'nutricion-vista-comidas',
};

/** Un ajuste a la ficha, sin bloquear a nadie: si falla, el localStorage ya lo tiene. */
export function guardarAjusteEnFicha(clave, valor) {
    try {
        const token = localStorage.getItem('token');
        if (!token) return;
        fetch(`${API}/api/user/ajustes-app`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ [clave]: valor }),
        }).catch(() => {});
    } catch (e) { /* sin red o sin storage: el ajuste local sigue mandando */ }
}

/**
 * Lo guardado en la ficha, al localStorage. Se llama al cargar el perfil (AuthContext):
 * así «entrar desde otro móvil» arranca con lo suyo.
 */
export function aplicarAjustesDeFicha(ajustes) {
    if (!ajustes || typeof ajustes !== 'object') return;
    for (const [clave, claveLocal] of Object.entries(CLAVES_LOCALES)) {
        const v = ajustes[clave];
        if (typeof v === 'string' && v) {
            try { localStorage.setItem(claveLocal, v); } catch (e) { /* storage capado */ }
        }
    }
}
