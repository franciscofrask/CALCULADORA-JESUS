import { useEffect, useState } from 'react';

/**
 * ¿Estamos en un teléfono?
 *
 * El rediseño del 10-08 es SOLO del móvil: en escritorio la app se queda como estaba
 * hasta que le toque su pasada. Casi todo se resuelve con las clases `lg:` de Tailwind
 * -- enseñar una cosa u otra según el ancho --, pero hay dos casos que no son de pintar
 * sino de decidir:
 *
 *   - en Nutrición, si al entrar se abre la primera comida (escritorio) o ninguna (móvil);
 *   - en Inicio, si los avisos pendientes se apilan (escritorio) o sale uno solo (móvil).
 *
 * Eso no lo puede hacer una clase de CSS, así que hace falta mirar el ancho de verdad.
 * El corte son 1024 px, EL MISMO que usa Tailwind para `lg`: si los dos números se
 * separan, habría anchos en los que el CSS cree que es móvil y el JavaScript que no.
 *
 * Escucha los cambios de tamaño porque una tableta girando cruza el corte, y con el valor
 * congelado del primer render se quedaría con el reparto que no toca.
 */
export const CORTE_LG = 1024;

const mirar = () => (typeof window === 'undefined' ? false : window.innerWidth < CORTE_LG);

export function useEsTelefono() {
    const [esTelefono, setEsTelefono] = useState(mirar);
    useEffect(() => {
        const mq = window.matchMedia(`(max-width: ${CORTE_LG - 1}px)`);
        const alCambiar = (e) => setEsTelefono(e.matches);
        setEsTelefono(mq.matches);
        mq.addEventListener('change', alCambiar);
        return () => mq.removeEventListener('change', alCambiar);
    }, []);
    return esTelefono;
}

export default useEsTelefono;
