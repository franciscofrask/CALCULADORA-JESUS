/**
 * VistaComidas - Como se ven las comidas del dia.
 *
 * La pestaña de Nutrición cargaba mucho: la lista lateral con las seis comidas y sus
 * barras, el detalle al lado, y en móvil el acordeón entero. No todo el mundo trabaja
 * igual, así que en vez de imponer una disposición se ofrecen tres y el cliente elige
 * la suya; se le recuerda de un día para otro.
 *
 *   actual    la de siempre: lista de comidas a la izquierda, detalle a la derecha
 *   pestanas  las comidas arriba como pestañas y la abierta a todo el ancho
 *   continua  el día entero seguido, como la dieta de Calma
 */
import React from 'react';
import { PanelLeft, LayoutPanelTop, AlignJustify } from 'lucide-react';

export const VISTAS = [
    { id: 'actual', nombre: 'Lista y detalle', Icono: PanelLeft },
    { id: 'pestanas', nombre: 'Pestañas', Icono: LayoutPanelTop },
    { id: 'continua', nombre: 'Todo seguido', Icono: AlignJustify },
];

const CLAVE = 'nutricion-vista-comidas';

export const leerVista = () => {
    try {
        const v = localStorage.getItem(CLAVE);
        return VISTAS.some(x => x.id === v) ? v : 'actual';
    } catch (e) {
        return 'actual';
    }
};

export const guardarVista = (v) => {
    try { localStorage.setItem(CLAVE, v); } catch (e) {}
};

export const VistaComidasSelector = ({ vista, onCambiar }) => (
    <div className="inline-flex items-center gap-1.5">
        <span className="hidden sm:inline text-[10px] uppercase tracking-wider text-muted-foreground">Vista</span>
        <div className="inline-flex rounded-lg bg-muted p-0.5 border border-border" role="group" aria-label="Cómo ver las comidas">
            {VISTAS.map(({ id, nombre, Icono }) => (
                <button
                    key={id}
                    type="button"
                    onClick={() => onCambiar(id)}
                    aria-pressed={vista === id}
                    title={nombre}
                    data-testid={`vista-${id}`}
                    className={`h-7 w-8 rounded-md flex items-center justify-center transition-colors ${
                        vista === id ? 'bg-card text-brand shadow-sm' : 'text-muted-foreground hover:text-foreground'
                    }`}
                >
                    <Icono className="w-4 h-4" />
                    <span className="sr-only">{nombre}</span>
                </button>
            ))}
        </div>
    </div>
);

export default VistaComidasSelector;
