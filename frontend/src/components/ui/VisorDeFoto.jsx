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
 * Las cuatro cosas que tiene que hacer un visor en un móvil, y que son las que se olvidan:
 *
 *  · CERRARSE DE VARIAS MANERAS. La X, tocar el fondo, y Escape en el ordenador. La zona de
 *    la X es de 44 px, que es el mínimo para un dedo.
 *  · NO DEJAR QUE EL FONDO SE MUEVA. Sin bloquear el scroll del `body`, arrastrar sobre la
 *    foto desplaza la página de detrás y al cerrar has perdido el sitio donde estabas.
 *  · VOLVER CON EL BOTÓN ATRÁS. En un teléfono, lo primero que se hace para cerrar algo que
 *    ocupa la pantalla es el gesto de atrás. Sin esto, ese gesto se lleva al cliente fuera de
 *    Seguimiento y hay que volver a entrar. Se mete una entrada en el historial al abrir y
 *    se consume al cerrar.
 *  · NO ROBAR EL FOCO PARA SIEMPRE: al cerrar, el foco vuelve solo porque el botón que la
 *    abrió sigue montado detrás.
 *
 * No hace zoom ni gestos de pellizco a propósito: el navegador ya los hace sobre una imagen
 * a pantalla completa, y montar los nuestros encima suele estropear los suyos.
 */
import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

const VisorDeFoto = ({ url, alt = '', pie = null, alCerrar }) => {
    /* `alCerrar` llega como una función nueva en CADA render del padre. Si el efecto de
       abajo dependiera de ella, se limpiaría y se volvería a montar en cada repintado -- y
       su limpieza hace `history.back()`, que dispara `popstate`, que llama a `alCerrar`.
       Resultado: el visor se abría y se cerraba solo, sin dar tiempo a verlo y sin ningún
       error en consola. Se guarda en una ref y el efecto se queda atado solo a la foto. */
    const cerrar = useRef(alCerrar);
    cerrar.current = alCerrar;
    // Si esta foto ya metió su entrada en el historial. Con una ref y no con estado: no
    // tiene que repintar nada, y tiene que sobrevivir al monta-desmonta-monta que React
    // hace en desarrollo.
    const enElHistorial = useRef(false);

    useEffect(() => {
        if (!url) return undefined;

        // El fondo se queda quieto mientras la foto está delante.
        const overflowPrevio = document.body.style.overflow;
        document.body.style.overflow = 'hidden';

        const conTecla = (e) => { if (e.key === 'Escape') pedirCierre(); };
        // El gesto de atrás ya ha consumido la entrada: aquí solo queda cerrar.
        const conAtras = () => { enElHistorial.current = false; cerrar.current(); };
        if (!enElHistorial.current) {
            window.history.pushState({ visorDeFoto: true }, '');
            enElHistorial.current = true;
        }
        window.addEventListener('keydown', conTecla);
        window.addEventListener('popstate', conAtras);

        // LA LIMPIEZA NO TOCA EL HISTORIAL, Y ESO ES LO IMPORTANTE. Antes hacía aquí el
        // `history.back()` que consume la entrada, y eso cerraba el visor nada más abrirlo:
        // `back()` dispara `popstate` en el siguiente ciclo, no al momento, así que para
        // cuando llegaba, React ya había vuelto a montar el efecto y a registrar el
        // listener -- y ese listener nuevo recibía el «atrás» del desmontaje anterior. La
        // foto se abría y se cerraba sola, sin un solo error en consola. Quien consume la
        // entrada es quien cierra a propósito (`pedirCierre`), no el desmontaje.
        return () => {
            document.body.style.overflow = overflowPrevio;
            window.removeEventListener('keydown', conTecla);
            window.removeEventListener('popstate', conAtras);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [url]);

    /* Cerrar con la X o tocando el fondo pasa por el historial, para que la entrada que se
       metió al abrir no se quede ahí convertida en un «atrás» que no hace nada. El
       `popstate` que provoca es el que llama a `alCerrar`. */
    const pedirCierre = () => {
        if (enElHistorial.current) window.history.back();
        else cerrar.current();
    };

    if (!url) return null;

    return createPortal(
        // Negro opaco y no translúcido: con un 5 % de transparencia se leían la gráfica de
        // peso y los títulos de detrás, y una foto que se mira para compararse con la del
        // mes pasado no puede tener texto por encima.
        <div className="fixed inset-0 z-[100] bg-black flex flex-col animate-in fade-in-0"
            onClick={pedirCierre} role="dialog" aria-modal="true" aria-label={alt || 'Foto ampliada'}
            data-testid="visor-foto">
            <div className="flex justify-end p-2 flex-shrink-0">
                <button onClick={pedirCierre} aria-label="Cerrar la foto" data-testid="visor-foto-cerrar"
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
