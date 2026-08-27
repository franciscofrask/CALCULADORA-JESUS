/**
 * EL «···» DE LA CABECERA DE NUTRICIÓN (punto 119 del artifact del 25-08).
 *
 * «Hoy en el ordenador hay cinco (PDF · Copiar · Favoritas · Preferencias · engranaje) y en
 * el móvil sólo tres, y desaparecen justo PDF y Copiar, que son los que se usan. Queda PDF
 * fuera y el resto dentro del ···. Igual en los dos sitios.»
 *
 * Lo de «igual en los dos sitios» es la mitad importante: la cabecera tenía una botonera
 * distinta por tamaño de ventana -- PDF y Copiar con `hidden sm:inline-flex`, la tuerca con
 * `lg:hidden` -- y encima PDF y Copiar reaparecían en el móvil ABAJO DEL TODO, después de
 * las comidas, donde nadie baja a buscarlos. Tres sitios para cinco botones. Ahora hay uno.
 *
 * No es un menú genérico: sabe lo justo para esta cabecera. Se cierra al elegir, al pulsar
 * fuera y con Escape, que es lo mínimo para que no se quede abierto tapando la pantalla.
 *
 * ── POR QUÉ EL DESPLEGABLE SE PINTA FUERA DE SU SITIO ────────────────────────────────
 *
 * «En la comida hay un botón de 3 puntos, al tocarlo no pasa nada» (Francisco, 27-08).
 *
 * Sí pasaba: el menú se abría y **la tarjeta de la comida se lo comía**. La tarjeta lleva
 * `overflow-hidden` -- lo necesita para que sus esquinas redondeadas recorten lo de dentro --
 * y el menú colgaba de ella en `absolute`, justo al final, así que se salía por abajo y lo
 * cortaba. Medido en la app: **de los 106 px que mide el menú se veían 11**. Una franja de
 * nada al pie de la tarjeta, que no parece un menú ni parece nada.
 *
 * Por eso ahora va en un `portal` colgado del `body` y colocado a mano debajo del botón: así
 * no hay antepasado que pueda recortarlo, ni aquí ni en ninguno de los otros sitios donde se
 * use. Y si no cabe debajo, se abre hacia arriba.
 */
import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { MoreHorizontal } from 'lucide-react';

//: Lo que separa el menú del botón, y el aire que se le deja al borde de la pantalla.
const HUECO = 8;
const MARGEN = 12;

const MenuDeLaPantalla = ({ opciones = [], etiqueta = 'Más opciones' }) => {
    const [abierto, setAbierto] = useState(false);
    const [sitio, setSitio] = useState(null);     // { top, left, width } en coordenadas de pantalla
    const boton = useRef(null);
    const menu = useRef(null);

    // Dónde se pinta: debajo del botón y alineado a su derecha. Si no cabe debajo -- que es lo
    // que pasa con el «···» del final de una comida --, encima.
    const colocar = useCallback(() => {
        const b = boton.current?.getBoundingClientRect();
        if (!b) return;
        const ancho = Math.min(240, window.innerWidth - MARGEN * 2);
        const alto = menu.current?.getBoundingClientRect().height || 0;
        const cabeDebajo = b.bottom + HUECO + alto <= window.innerHeight - MARGEN;
        setSitio({
            top: cabeDebajo ? b.bottom + HUECO : Math.max(MARGEN, b.top - HUECO - alto),
            // Alineado a la derecha del botón, sin salirse de la pantalla por ningún lado.
            left: Math.max(MARGEN, Math.min(b.right - ancho, window.innerWidth - ancho - MARGEN)),
            width: ancho,
        });
    }, []);

    // Se coloca ANTES de pintar (`useLayoutEffect`) para que no se vea saltar de sitio.
    useLayoutEffect(() => { if (abierto) colocar(); }, [abierto, colocar]);

    useEffect(() => {
        if (!abierto) return undefined;
        const fuera = (e) => {
            // El menú ya NO está dentro del botón: va en un portal. Sin mirarlo también, este
            // `mousedown` lo cerraría antes de que llegara el `click` de la opción, y elegir
            // no haría nada -- que es el mismo fallo por el otro lado.
            if (boton.current?.contains(e.target) || menu.current?.contains(e.target)) return;
            setAbierto(false);
        };
        const escape = (e) => { if (e.key === 'Escape') setAbierto(false); };
        // Al rodar la pantalla el menú se recoloca, que si no se queda flotando donde estaba.
        const recolocar = () => colocar();
        document.addEventListener('mousedown', fuera);
        document.addEventListener('keydown', escape);
        window.addEventListener('scroll', recolocar, true);
        window.addEventListener('resize', recolocar);
        return () => {
            document.removeEventListener('mousedown', fuera);
            document.removeEventListener('keydown', escape);
            window.removeEventListener('scroll', recolocar, true);
            window.removeEventListener('resize', recolocar);
        };
    }, [abierto, colocar]);

    const visibles = opciones.filter(Boolean);
    if (!visibles.length) return null;

    const desplegable = (
        <div role="menu" data-testid="menu-pantalla-abierto" ref={menu}
            style={{ position: 'fixed', top: sitio?.top ?? -9999, left: sitio?.left ?? -9999, width: sitio?.width }}
            className="z-[70] surface p-1.5 shadow-xl">
            {visibles.map((o) => (
                <button key={o.id} type="button" role="menuitem"
                    data-testid={`menu-pantalla-${o.id}`}
                    disabled={o.deshabilitada}
                    onClick={() => { setAbierto(false); o.al(); }}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left text-sm transition-colors disabled:opacity-50 ${
                        o.peligro ? 'text-pasado hover:bg-pasado/10' : 'text-foreground hover:bg-muted'}`}>
                    {/* Lo que se lleva algo por delante va en rojo (punto 126: «Vaciar
                        la comida, esta en rojo»). Es la unica marca que distingue una
                        opcion destructiva de las demas dentro de un menu. */}
                    {o.icono && <o.icono className={`w-4 h-4 flex-shrink-0 ${o.peligro ? '' : 'text-muted-foreground'}`} />}
                    <span className="min-w-0">
                        <span className="block font-semibold">{o.texto}</span>
                        {/* El detalle es para el resumen de la configuración del día
                            (punto 113): «es corto, es cierto y además es un botón». */}
                        {o.detalle && <span className="block text-xs text-muted-foreground">{o.detalle}</span>}
                    </span>
                </button>
            ))}
        </div>
    );

    return (
        <div className="relative">
            <button type="button" ref={boton} onClick={() => setAbierto((v) => !v)}
                aria-haspopup="menu" aria-expanded={abierto} aria-label={etiqueta} title={etiqueta}
                data-testid="menu-pantalla"
                className={`inline-flex items-center justify-center w-10 h-10 text-sm font-semibold transition-colors ${
                    abierto ? 'rounded-2xl bg-brand text-white' : 'surface text-muted-foreground hover:text-brand'}`}>
                <MoreHorizontal size={18} />
            </button>

            {abierto && typeof document !== 'undefined' && createPortal(desplegable, document.body)}
        </div>
    );
};

export default MenuDeLaPantalla;
