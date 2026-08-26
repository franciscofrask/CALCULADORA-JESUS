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
 */
import React, { useEffect, useRef, useState } from 'react';
import { MoreHorizontal } from 'lucide-react';

const MenuDeLaPantalla = ({ opciones = [], etiqueta = 'Más opciones' }) => {
    const [abierto, setAbierto] = useState(false);
    const caja = useRef(null);

    useEffect(() => {
        if (!abierto) return undefined;
        const fuera = (e) => { if (caja.current && !caja.current.contains(e.target)) setAbierto(false); };
        const escape = (e) => { if (e.key === 'Escape') setAbierto(false); };
        document.addEventListener('mousedown', fuera);
        document.addEventListener('keydown', escape);
        return () => {
            document.removeEventListener('mousedown', fuera);
            document.removeEventListener('keydown', escape);
        };
    }, [abierto]);

    const visibles = opciones.filter(Boolean);
    if (!visibles.length) return null;

    return (
        <div className="relative" ref={caja}>
            <button type="button" onClick={() => setAbierto((v) => !v)}
                aria-haspopup="menu" aria-expanded={abierto} aria-label={etiqueta} title={etiqueta}
                data-testid="menu-pantalla"
                className={`inline-flex items-center justify-center w-10 h-10 text-sm font-semibold transition-colors ${
                    abierto ? 'rounded-2xl bg-brand text-white' : 'surface text-muted-foreground hover:text-brand'}`}>
                <MoreHorizontal size={18} />
            </button>

            {abierto && (
                <div role="menu" data-testid="menu-pantalla-abierto"
                    className="absolute right-0 top-full mt-2 z-50 min-w-[15rem] max-w-[min(20rem,calc(100vw-2rem))] surface p-1.5 shadow-xl">
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
            )}
        </div>
    );
};

export default MenuDeLaPantalla;
