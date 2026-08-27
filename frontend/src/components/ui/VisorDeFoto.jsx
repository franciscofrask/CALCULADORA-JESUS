/**
 * VER UNA FOTO A PANTALLA COMPLETA, TOCÁNDOLA (Francisco, 26-08).
 *
 * En el móvil las fotos del cliente se ven en un hueco de 3/4 con `object-cover`, así que
 * van RECORTADAS: en la comparativa de evolución la cabeza y los pies se quedan fuera, y
 * ampliar es justo lo que hace falta para comparar dos meses. Y en el chat la única forma de
 * ver una etiqueta o el número de una báscula era abrir la imagen EN OTRA PESTAÑA, que en un
 * teléfono te saca de la app y en la app instalada te deja fuera.
 *
 * Aquí la foto se abre encima, entera (`object-contain`, nada recortado) y sobre negro.
 *
 * Lo que tiene que hacer, y que es lo que se olvida:
 *
 *  · CERRARSE DE VARIAS MANERAS. La X, tocar el fondo, y Escape en el ordenador. La zona de
 *    la X es de 44 px, que es el mínimo para un dedo.
 *  · NO DEJAR QUE EL FONDO SE MUEVA. Sin bloquear el scroll del `body`, arrastrar sobre la
 *    foto desplaza la página de detrás y al cerrar has perdido el sitio donde estabas.
 *  · NO NAVEGAR A NINGUNA PARTE. Abrir y cerrar una foto no es cambiar de pantalla: al
 *    cerrar te quedas donde estabas, sin recargar y sin moverte. Ver abajo.
 *  · NO ROBAR EL FOCO PARA SIEMPRE: al cerrar, el foco vuelve solo porque el botón que la
 *    abrió sigue montado detrás.
 *
 * ESTE VISOR NO TOCA EL HISTORIAL, Y ES A PROPÓSITO.
 *
 * La primera versión metía una entrada con `pushState` para que el gesto de «atrás» del
 * móvil cerrara la foto en vez de salir de la pantalla. Sonaba bien y estaba mal: React
 * Router guarda su posición en `history.state` (el campo `idx`), y un `pushState` propio lo
 * machaca. Al cerrar, el `history.back()` dejaba a Router sin su índice y **la app se iba al
 * inicio**. Francisco lo vio en producción: cerrabas la foto y aparecías en otra pantalla.
 *
 * Cerrar una foto no es navegar. Se cierra con la X, tocando el fondo y con Escape, y la
 * página se queda exactamente donde estaba.
 *
 * No hace zoom ni gestos de pellizco a propósito: el navegador ya los hace sobre una imagen
 * a pantalla completa, y montar los nuestros encima suele estropear los suyos.
 */
import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

const VisorDeFoto = ({ url, alt = '', pie = null, alCerrar }) => {
    /* `alCerrar` llega como una función nueva en CADA render del padre. Si el efecto de
       abajo dependiera de ella, se limpiaría y se volvería a montar en cada repintado. Se
       guarda en una ref y el efecto se queda atado solo a la foto. */
    const cerrar = useRef(alCerrar);
    cerrar.current = alCerrar;

    useEffect(() => {
        if (!url) return undefined;

        // El fondo se queda quieto mientras la foto está delante.
        const overflowPrevio = document.body.style.overflow;
        document.body.style.overflow = 'hidden';

        const conTecla = (e) => { if (e.key === 'Escape') cerrar.current(); };
        window.addEventListener('keydown', conTecla);

        return () => {
            document.body.style.overflow = overflowPrevio;
            window.removeEventListener('keydown', conTecla);
        };
    }, [url]);

    if (!url) return null;

    return createPortal(
        // Negro opaco y no translúcido: con un 5 % de transparencia se leían la gráfica de
        // peso y los títulos de detrás, y una foto que se mira para compararse con la del
        // mes pasado no puede tener texto por encima.
        <div className="fixed inset-0 z-[100] bg-black flex flex-col animate-in fade-in-0"
            onClick={() => cerrar.current()} role="dialog" aria-modal="true"
            aria-label={alt || 'Foto ampliada'} data-testid="visor-foto">
            <div className="flex justify-end p-2 flex-shrink-0">
                <button type="button" onClick={() => cerrar.current()} aria-label="Cerrar la foto"
                    data-testid="visor-foto-cerrar"
                    className="w-11 h-11 rounded-full flex items-center justify-center text-white/90 bg-white/10 active:bg-white/20 transition-colors">
                    <X className="w-6 h-6" />
                </button>
            </div>
            {/* La imagen no cierra al tocarla: en una foto grande se toca para mirarla, y
                cerrarse ahí se siente un accidente. Se cierra por el fondo y por la X. */}
            <img src={url} alt={alt} onClick={(e) => e.stopPropagation()}
                className="flex-1 min-h-0 w-full object-contain select-none"
                data-testid="visor-foto-imagen" />
            {pie && (
                <p className="flex-shrink-0 text-center text-sm text-white/70 p-3"
                    onClick={(e) => e.stopPropagation()} data-testid="visor-foto-pie">{pie}</p>
            )}
        </div>,
        document.body,
    );
};

export default VisorDeFoto;
