/**
 * ATAJOS ARRIBA Y, DEBAJO, LO MISMO AGRUPADO POR CICLO (doc de Jesús del 2-09, fase 3).
 *
 * Es la forma que comparten los tres selectores de Evolución: el de fotos («mi primera
 * foto · inicio de este ciclo · fin del ciclo anterior · hoy» y las tomas por ciclo), el de
 * medidas (el mismo) y el del comparador de puntos («mi pico de forma · mi peso más alto ·
 * mi peso más bajo · inicio de este ciclo · hoy» y los puntos por ciclo). Jesús: «se busca
 * por dónde estaba, no por qué día era», y «así puede comparar el bloque 3 de un ciclo con
 * el bloque 3 de otro».
 *
 * Dos reglas que vienen del doc y aquí solo se pintan (quien decide es quien monta la lista):
 *   - Un atajo sin dato no se esconde: se enseña apagado con su nota («no tienes foto de
 *     ese momento»). Nunca un hueco.
 *   - Cuando el atajo no es exacto lleva su nota («la más próxima al inicio del ciclo:
 *     12 de junio»). Nunca mentir con la fecha.
 *
 * Los ciclos anteriores al cuaderno no existen como tales: llegan como tramos de cuatro
 * semanas desde el alta y se dicen aproximados (decisión del 4-09), con `aproximado: true`.
 */
import React from 'react';

const Atajo = ({ atajo, elegido, onElegir }) => {
    const apagado = atajo.id == null;
    return (
        <button type="button" disabled={apagado}
            data-testid={`atajo-${atajo.clave}`}
            onClick={() => !apagado && onElegir(atajo.id)}
            className={`w-full text-left rounded-xl border px-4 py-3 transition-colors ${
                apagado ? 'border-border/50 text-muted-foreground/60 cursor-not-allowed'
                    : elegido ? 'border-brand bg-brand/10 text-foreground'
                        : 'border-border text-foreground hover:border-brand'}`}>
            <span className="block text-base">{atajo.texto}</span>
            {atajo.nota && <span className="block text-xs text-muted-foreground mt-0.5">{atajo.nota}</span>}
        </button>
    );
};

const ListaPorCiclo = ({ atajos = [], grupos = [], seleccionado = null, onElegir, tituloAtajos = null, tituloGrupos = 'O por ciclo' }) => (
    <div className="space-y-4" data-testid="lista-por-ciclo">
        {atajos.length > 0 && (
            <div className="space-y-2">
                {tituloAtajos && <p className="caption">{tituloAtajos}</p>}
                {atajos.map(a => (
                    <Atajo key={a.clave} atajo={a} elegido={a.id != null && a.id === seleccionado} onElegir={onElegir} />
                ))}
            </div>
        )}
        {grupos.length > 0 && (
            <div className="space-y-3">
                <p className="caption">{tituloGrupos}</p>
                {grupos.map(g => (
                    <div key={g.id || g.etiqueta} className="space-y-1.5" data-testid="grupo-ciclo">
                        <p className="text-[11px] font-bold uppercase tracking-wider text-brand">
                            {g.etiqueta}
                            {g.aproximado && <span className="ml-2 font-normal normal-case tracking-normal text-muted-foreground">aproximado</span>}
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                            {g.items.map(it => (
                                <button key={it.id} type="button" onClick={() => onElegir(it.id)}
                                    data-testid={`toma-${it.id}`}
                                    className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                                        it.id === seleccionado ? 'border-brand bg-brand/10 text-foreground'
                                            : 'border-border text-foreground/80 hover:border-brand'}`}>
                                    {it.texto}
                                    {it.marca && <span className="text-muted-foreground"> · {it.marca}</span>}
                                </button>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        )}
        {atajos.length === 0 && grupos.length === 0 && (
            <p className="text-sm text-muted-foreground">Todavía no hay nada que elegir.</p>
        )}
    </div>
);

export default ListaPorCiclo;
