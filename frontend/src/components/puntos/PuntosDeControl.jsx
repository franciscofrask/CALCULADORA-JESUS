/**
 * TUS PUNTOS DE CONTROL, dentro de Evolución (doc de Jesús del 2-09, «Los puntos de
 * control»; fase 3, 4-09).
 *
 * «Un punto es un reporte. Ni quincenales ni pesajes sueltos: los reportes son los únicos
 * que traen fotos y medidas, que es lo que hace que dos puntos se puedan comparar.» La
 * lista va uno por reporte, DEL MÁS ANTIGUO AL DE HOY, igual que la gráfica y la tabla de
 * medidas: «en toda la pantalla el tiempo va en la misma dirección».
 *
 * Cada punto se llama por el bloque que CIERRA («Final bloque 2 · Ciclo 3»: el reporte se
 * manda al terminar, no al empezar) y debajo, en gris, su otro papel («y el inicio del
 * bloque 3»). Con su objetivo, su peso y encima las etiquetas: pico de forma (la pone el
 * entrenador), peso máximo y peso mínimo (salen solas). Todo eso lo decide el servidor en
 * `GET /reports/puntos`; aquí solo se pinta.
 *
 * Los puntos anteriores al cuaderno de ciclos no existen como tales: llegan como tramos de
 * cuatro semanas desde el alta, con `aproximado: true`, y se enseñan igual diciendo
 * «aproximado» (decisión del 4-09). Nunca un hueco.
 *
 * Al tocar uno se abre su detalle EN EL MISMO SITIO de la lista (como el informe del mes en
 * el historial): su foto de ese día, los macros que llevaba entonces, sus medidas y su
 * grasa. Desde ahí, «Comparar este punto con otro ›» lleva al comparador con ese punto ya
 * elegido (`?abrir=comparar&punto=ID`).
 */
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { kg } from '../../lib/pesoValido';
import DetalleDelPunto from './DetalleDelPunto';
import { Pastillas, fechaCorta, puntosEnOrden, useDatosDePuntos } from './comun';

const TITULO = 'Tus puntos de control';

const Tarjeta = ({ children }) => (
    <div className="bg-card border border-border rounded-2xl p-4 space-y-3" data-testid="puntos-de-control">
        <p className="caption">{TITULO}</p>
        {children}
    </div>
);

/** Una fila de la lista: el nombre con su fecha, las pastillas, el objetivo a la izquierda
 *  y el peso a la derecha, y en gris cursiva su otro papel. */
const Punto = ({ punto, onAbrir }) => (
    <button type="button" onClick={() => onAbrir(punto)} data-testid={`punto-${punto.id}`}
        className="w-full text-left rounded-xl border border-border px-3 py-2.5 space-y-1.5 hover:border-brand transition-colors">
        <div className="flex items-start justify-between gap-2">
            <span className="text-sm font-bold text-foreground leading-tight">
                {punto.nombre}
                <span className="font-normal text-muted-foreground"> · {fechaCorta(punto.fecha)}</span>
            </span>
            <span className="flex items-center gap-1 shrink-0">
                {punto.aproximado && <span className="text-[11px] text-muted-foreground">aproximado</span>}
                <ChevronRight className="w-4 h-4 text-foreground/20" />
            </span>
        </div>
        <Pastillas etiquetas={punto.etiquetas} />
        <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="text-foreground/80">{punto.objetivo_nombre || 'Sin objetivo apuntado'}</span>
            {punto.peso != null && (
                <span className="font-bold text-foreground tabular-nums whitespace-nowrap">{kg(punto.peso)} kg</span>
            )}
        </div>
        {punto.nombre_secundario && (
            <p className="text-xs italic text-muted-foreground">{punto.nombre_secundario}</p>
        )}
    </button>
);

const PuntosDeControl = ({ api, alComparar = null }) => {
    const navigate = useNavigate();
    const { datos, error } = useDatosDePuntos(api);
    const [abierto, setAbierto] = useState(null);
    const arriba = useRef(null);

    // Al abrir un punto, la tarjeta se convierte en su detalle: se lleva la vista a su
    // cabecera, que en el móvil puede haber quedado por encima del sitio donde se tocó.
    useEffect(() => {
        if (abierto && arriba.current) arriba.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, [abierto]);

    const comparar = alComparar || ((punto) => navigate(`/dashboard/reports?abrir=comparar&punto=${encodeURIComponent(punto.id)}`));

    if (error) {
        return <Tarjeta><p className="text-sm text-muted-foreground" data-testid="puntos-error">{error}</p></Tarjeta>;
    }
    if (!datos) {
        return <div className="animate-pulse h-28 bg-card border border-border rounded-2xl" data-testid="puntos-cargando" />;
    }

    const puntos = puntosEnOrden(datos);

    if (abierto) {
        return (
            <div ref={arriba} className="scroll-mt-4">
                <DetalleDelPunto api={api} punto={abierto}
                    alVolver={() => setAbierto(null)}
                    alComparar={() => comparar(abierto)} />
            </div>
        );
    }

    return (
        <Tarjeta>
            <p className="text-xs text-muted-foreground -mt-1">
                Uno por reporte, del más antiguo al de hoy. Tócalos para ver tus macros, tus medidas y tus fotos de ese día.
            </p>
            {puntos.length ? (
                <div className="space-y-2" data-testid="lista-de-puntos">
                    {puntos.map(p => <Punto key={p.id} punto={p} onAbrir={setAbierto} />)}
                </div>
            ) : (
                <p className="text-sm text-muted-foreground" data-testid="puntos-vacio">
                    Tus puntos de control van saliendo con cada reporte. Todavía no tienes ninguno.
                </p>
            )}
        </Tarjeta>
    );
};

export default PuntosDeControl;
