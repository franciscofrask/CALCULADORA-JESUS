/**
 * SelectorGrasa - el carrusel de % de grasa.
 *
 * Vivia dentro del cuestionario. Se saca aqui porque el acceso gratis tambien lo necesita.
 *
 * PARTIDO POR SEXO desde el 18-08 (bloque 2 del doc del cuestionario): 22 valores en
 * hombre y 6 en mujer. Antes habia una sola escala, la de hombre, y a una mujer se le
 * enseñaban veintidos cuerpos de hombre para que se identificara con uno; de ese numero
 * sale medio calculo y el indice de muscularidad entero.
 *
 * Las FOTOS de mujer siguen sin existir -- son de Jesus, de la pestaña Mujer de su hoja --
 * asi que a ellas se les enseña la escala sin foto. En cuanto lleguen, se ponen en
 * `/bodyfat/mujer/` y se enciende `conFotos`.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, ImagePlus } from 'lucide-react';

// Referencias de % de grasa (de mayor a menor), réplica del carrusel de la web.
const BF_PERCENTAGES = [50, 48, 46, 44, 42, 40, 38, 36, 34, 32, 30, 28, 26, 24, 22, 20, 18, 16, 14, 12, 10, 8];
const BF_DEFAULT = 20;

// LA ESCALA DE MUJER, la del doc del 18-08: seis valores, no veintidós. Hasta ahora había
// una sola escala -- la de hombre -- y a una mujer se le enseñaban veintidós cuerpos de
// hombre para que se identificara con uno. De ese número sale medio cálculo.
//
// Y SIN FOTO, a propósito: las de mujer no existen todavía (son de Jesús). Entre enseñarle
// cuerpos de hombre y enseñarle solo el número, el número. En cuanto lleguen las fotos se
// añaden aquí y la pantalla queda igual que la de ellos.
const BF_MUJER = [45, 40, 35, 30, 25, 20];
const BF_DEFAULT_MUJER = 30;

const esMujer = (sexo) => String(sexo || '').toLowerCase().startsWith('muj');
export const escalaDeGrasa = (sexo) => (esMujer(sexo) ? BF_MUJER : BF_PERCENTAGES);
export const grasaPorDefecto = (sexo) => (esMujer(sexo) ? BF_DEFAULT_MUJER : BF_DEFAULT);

// Slider de % de grasa: carrusel horizontal de imágenes de referencia con la
// foto del cliente fija en el centro. Se desliza hasta situar la foto entre dos
// porcentajes; el valor es el de la referencia que queda centrada.
const BodyFatSlider = ({ value, onChange, sexo, photo: fotoDeFuera, onPhoto }) => {
    // La escala y el valor de partida son los de su sexo (doc del 18-08).
    const ESCALA = escalaDeGrasa(sexo);
    const POR_DEFECTO = grasaPorDefecto(sexo);
    const conFotos = !esMujer(sexo);   // las de mujer no existen todavía
    const scrollRef = useRef(null);
    // LA FOTO PUEDE VIVIR FUERA (doc del 23-08, punto 1): el cuestionario la guarda con
    // las respuestas para poder subirla al terminar; hasta entonces se perdía en este
    // estado local. Sin `onPhoto` (otros usos del carrusel) se comporta como siempre.
    const [fotoLocal, setFotoLocal] = useState(null);
    const photo = onPhoto ? fotoDeFuera : fotoLocal;
    const setPhoto = onPhoto || setFotoLocal;
    const [arrastrando, setArrastrando] = useState(false);

    const handleScroll = useCallback(() => {
        const el = scrollRef.current;
        if (!el) return;
        const col = el.clientWidth / 3; // 3 columnas visibles
        // SIN ANCHO NO SE DECIDE NADA (punto 16 del 17-08). Mientras el navegador no ha
        // resuelto el layout, `clientWidth` es 0: `scrollLeft / 0` da NaN, el índice sale
        // NaN, `BF_PERCENTAGES[NaN]` es undefined y esto llamaba a `onChange(undefined)`,
        // o sea BORRABA la respuesta del cliente en la pregunta de la que salen sus macros.
        if (!col) return;
        const i = Math.max(0, Math.min(ESCALA.length - 1, Math.round(el.scrollLeft / col)));
        const pct = ESCALA[i];
        if (pct !== value) onChange(pct);
    }, [value, onChange]);

    // ── Arrastrar agarrando las propias fotos ────────────────────────────────
    // Antes solo se podia mover desde la barra de abajo, que es un objetivo fino y en el movil
    // ni se ve. Ahora se agarra el carrusel donde sea. `movido` distingue un arrastre de un clic:
    // sin eso, soltar encima del hueco de la foto abriria el selector de archivos.
    const arrastre = useRef({ activo: false, xInicial: 0, scrollInicial: 0, movido: 0 });

    const empezarArrastre = (e) => {
        const el = scrollRef.current;
        if (!el) return;
        // Sin esto el navegador se queda con el gesto y arrastra la imagen como si fueras a
        // soltarla en otra pestaña, en vez de mover el carrusel.
        e.preventDefault();
        // El puntero se "engancha" al carrusel: aunque el cursor salga de el mientras arrastras,
        // los eventos siguen llegando aqui y el gesto no se corta a medias.
        try { e.currentTarget.setPointerCapture(e.pointerId); } catch (err) { /* navegador antiguo */ }
        arrastre.current = { activo: true, xInicial: e.clientX, scrollInicial: el.scrollLeft, movido: 0 };
        setArrastrando(true);
        el.style.scrollBehavior = 'auto';   // durante el arrastre debe seguir al dedo, sin suavizado
    };

    const moverArrastre = (e) => {
        const el = scrollRef.current;
        if (!el || !arrastre.current.activo) return;
        e.preventDefault();
        const dx = e.clientX - arrastre.current.xInicial;
        arrastre.current.movido = Math.max(arrastre.current.movido, Math.abs(dx));
        el.scrollLeft = arrastre.current.scrollInicial - dx;
    };

    const soltarArrastre = (e) => {
        const el = scrollRef.current;
        if (!arrastre.current.activo) return;
        arrastre.current.activo = false;
        setArrastrando(false);
        try { e?.currentTarget?.releasePointerCapture?.(e.pointerId); } catch (err) { /* ya soltado */ }
        if (el) {
            el.style.scrollBehavior = '';
            // Al soltar, encaja en la referencia mas cercana en vez de quedarse a medias.
            const col = el.clientWidth / 3;
            if (col) el.scrollTo({ left: Math.round(el.scrollLeft / col) * col, behavior: 'smooth' });
        }
    };

    // Botones de una en una, para ajustar fino sin pelearse con el arrastre.
    const mover = (pasos) => {
        const el = scrollRef.current;
        if (!el) return;
        const col = el.clientWidth / 3;
        if (!col) return;   // sin ancho la cuenta da NaN y el carrusel se va al extremo
        el.scrollTo({ left: (Math.round(el.scrollLeft / col) + pasos) * col, behavior: 'smooth' });
    };

    const iBase = ESCALA.indexOf(value ?? POR_DEFECTO);
    // El array va de mayor a menor (50 -> 8): "menos grasa" es avanzar en el carrusel.
    const puedeMenos = iBase < ESCALA.length - 1;
    const puedeMas = iBase > 0;

    // Posicionar el carrusel en el valor inicial al montar.
    //
    // SE ESPERA A TENER ANCHO (punto 16 del 17-08). Esto medía `el.clientWidth` en el efecto
    // de montaje, y ahí el navegador todavía no ha resuelto el layout de un contenedor que se
    // dimensiona por `aspect-ratio`: `clientWidth` valía 0, así que `scrollLeft` se ponía a 0
    // -- la primera columna del array, el 50 % -- y el cliente se encontraba el carrusel
    // abierto en el extremo, con el hueco espaciador a la vista. Que es exactamente lo que
    // se veía: «arranca en 50 %, las fotos salen a trozos y hay huecos en blanco».
    //
    // Con `ResizeObserver` se coloca en cuanto hay ancho de verdad, y una sola vez: `hecho`
    // corta el observador para que un cambio de tamaño posterior no le mueva la respuesta
    // al cliente mientras la está eligiendo.
    const colocado = useRef(false);
    useEffect(() => {
        const el = scrollRef.current;
        if (!el) return;
        const start = value ?? POR_DEFECTO;
        if (value == null) onChange(start);

        const colocar = () => {
            const col = el.clientWidth / 3;
            if (!col || colocado.current) return;
            const i = ESCALA.indexOf(start);
            el.scrollLeft = (i < 0 ? ESCALA.indexOf(POR_DEFECTO) : i) * col;
            colocado.current = true;
        };

        colocar();                       // si ya hay layout, aquí se acaba
        if (colocado.current) return;
        const obs = new ResizeObserver(() => { colocar(); if (colocado.current) obs.disconnect(); });
        obs.observe(el);
        return () => obs.disconnect();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const pickPhoto = () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = (ev) => {
            const file = ev.target.files?.[0];
            if (!file) return;
            // El mismo tope que las demás fotos de la app: al terminar el alta esta se
            // guarda, y un original de cámara sin tope es un cuerpo de 20 MB en el envío.
            if (file.size > 8 * 1024 * 1024) return;
            const reader = new FileReader();
            reader.onload = (e) => setPhoto(e.target.result);
            reader.readAsDataURL(file);
        };
        input.click();
    };

    return (
        <div>
            <style>{`
                .bf-scroll::-webkit-scrollbar{height:6px}
                .bf-scroll::-webkit-scrollbar-track{background:transparent}
                .bf-scroll::-webkit-scrollbar-thumb{background:#FF671F;border-radius:9999px}
                /* El navegador arrastra las imagenes por su cuenta (como para soltarlas en otra
                   pestana) y se come el gesto de mover el carrusel. */
                .bf-scroll img{-webkit-user-drag:none;user-select:none;-webkit-touch-callout:none}
                .bf-scroll{-webkit-user-drag:none}
            `}</style>

            <div className="text-center mb-4">
                <span className="font-heading font-extrabold text-5xl text-brand">{value ?? POR_DEFECTO}%</span>
            </div>

            <div className="relative rounded-xl overflow-hidden border-2 border-[#222222] select-none" style={{ aspectRatio: '1800 / 933' }}>
                {/* Foto del cliente, fija en el centro. Un clic la cambia; si se ha arrastrado
                    encima de ella, no: era un gesto para mover el carrusel. */}
                <button type="button"
                    onClick={() => { if (arrastre.current.movido < 6) pickPhoto(); }}
                    className={`absolute top-0 bottom-0 left-1/3 w-1/3 z-30 flex flex-col items-center justify-center bg-[#e9eae5] overflow-hidden ${arrastrando ? 'cursor-grabbing' : 'cursor-pointer'}`}
                    style={photo ? { backgroundImage: `url(${photo})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}}>
                    {!photo && (
                        <>
                            <ImagePlus className="w-7 h-7 text-black/40" />
                            <span className="text-black/50 text-xs font-bold mt-2 px-2 text-center leading-tight">Sube tu foto</span>
                        </>
                    )}
                </button>

                {/* Carrusel de referencias. Se agarra en cualquier punto para moverlo. */}
                <div ref={scrollRef} onScroll={handleScroll}
                    onPointerDown={empezarArrastre}
                    onPointerMove={moverArrastre}
                    onPointerUp={soltarArrastre}
                    onPointerCancel={soltarArrastre}
                    onDragStart={(e) => e.preventDefault()}
                    draggable={false}
                    className={`bf-scroll h-full flex overflow-x-scroll overflow-y-hidden scroll-smooth touch-pan-x ${arrastrando ? 'cursor-grabbing' : 'cursor-grab'}`}>
                    <div className="flex-shrink-0 w-1/3 h-full" aria-hidden="true" />
                    {ESCALA.map((n) => (
                        <div key={n} className="relative flex-shrink-0 w-1/3 h-full border-r-4 border-white/80 last:border-r-0">
                            {/* Son 22 fotos de 600x933. Sin `lazy` el navegador las decodifica
                                todas a la vez -- unos 49 MB de mapa de bits -- y la pestaña se
                                queda sin responder mientras tanto: medido en producción el
                                17-08, treinta segundos con la pantalla congelada en el paso
                                del que salen los macros. */}
                            {conFotos ? (
                                <img src={`/bodyfat/frente/${n}.webp`} alt={`${n}%`} draggable="false"
                                    loading="lazy" decoding="async"
                                    className="w-full h-full object-cover pointer-events-none" />
                            ) : (
                                <div className="w-full h-full bg-[#1a1a1a]" aria-hidden="true" />
                            )}
                            <span className="absolute inset-x-0 bottom-[8%] flex items-end justify-center font-extrabold text-3xl text-white"
                                style={{ textShadow: '1px 1px 6px rgba(0,0,0,.9)' }}>{n}%</span>
                        </div>
                    ))}
                    <div className="flex-shrink-0 w-1/3 h-full" aria-hidden="true" />
                </div>

                {/* Flechas: para ajustar de uno en uno sin pelearse con el arrastre. */}
                <button type="button" onClick={() => mover(-1)} disabled={!puedeMas} aria-label="Más grasa"
                    className="absolute left-2 top-1/2 -translate-y-1/2 z-40 w-10 h-10 rounded-full bg-black/60 hover:bg-black/80 disabled:opacity-25 disabled:hover:bg-black/60 text-white flex items-center justify-center backdrop-blur-sm transition-colors">
                    <ArrowLeft className="w-5 h-5" />
                </button>
                <button type="button" onClick={() => mover(1)} disabled={!puedeMenos} aria-label="Menos grasa"
                    className="absolute right-2 top-1/2 -translate-y-1/2 z-40 w-10 h-10 rounded-full bg-black/60 hover:bg-black/80 disabled:opacity-25 disabled:hover:bg-black/60 text-white flex items-center justify-center backdrop-blur-sm transition-colors">
                    <ArrowRight className="w-5 h-5" />
                </button>
            </div>

            <p className="text-foreground/50 text-xs mt-3 text-center">
                {conFotos
                    ? 'Sube tu foto y arrastra las imágenes (o usa las flechas) hasta situarla entre dos porcentajes.'
                    : 'Sube tu foto y elige el porcentaje que más se acerque. Las fotos de referencia de mujer están en camino.'}
            </p>
        </div>
    );
};

export default BodyFatSlider;
export { BF_PERCENTAGES, BF_DEFAULT };
