/**
 * ChatDayOverview - "¿Qué comidas tengo cargadas?"
 *
 * Antes esto era una lista de texto larguísima: por cada una de las seis comidas, su
 * nombre, su estado, sus alimentos con los tres macros escritos con letra ("proteína
 * 16.0 g · hidratos 0.0 g · grasa 12.0 g") y una línea de "Falta / Te pasas". Seis
 * bloques iguales seguidos, imposible de ojear.
 *
 * Ahora cada comida es una fila: estado a la izquierda, lo que lleva en pequeño y una
 * barra por macro. Las vacías se pliegan a una sola línea, que es lo que son.
 */
import React from 'react';
import { Check } from 'lucide-react';
import { getFoodEmoji } from './constants';

const MACRO = { P: '#FF671F', H: '#2196F3', G: '#FFA500' };
const CLAVES = ['P', 'H', 'G'];

const fmt = (x) => {
    const n = Math.round((x || 0) * 10) / 10;
    return Number.isInteger(n) ? String(n) : n.toFixed(1).replace('.', ',');
};

/** Barras finas de los tres macros, en horizontal, para ver la comida de un vistazo. */
const MiniBarras = ({ actual, objetivo }) => (
    <div className="flex items-center gap-2">
        {CLAVES.map(k => {
            const obj = objetivo?.[k] || 0;
            const act = actual?.[k] || 0;
            if (obj <= 0 && act <= 0) return null;
            const pct = obj > 0 ? Math.min((act / obj) * 100, 100) : 0;
            const pasado = obj > 0 && act > obj + 0.05;
            return (
                <div key={k} className="flex min-w-0 flex-1 items-center gap-1">
                    <span className="font-data text-[10px] text-muted-foreground">{k}</span>
                    <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
                        <div className="h-full rounded-full"
                            style={{ width: `${pct}%`, backgroundColor: pasado ? '#EF4444' : MACRO[k] }} />
                    </div>
                    <span className="shrink-0 font-data text-[10px]"
                        style={{ color: pasado ? '#EF4444' : 'inherit' }}>
                        {fmt(act)}<span className="text-muted-foreground">/{fmt(obj)}</span>
                    </span>
                </div>
            );
        })}
    </div>
);

const Comida = ({ m }) => {
    const alimentos = m.alimentos || [];
    const vacia = !alimentos.length;
    return (
        <div className={`rounded-lg border p-2 ${m.es_actual ? 'border-brand/50 bg-brand/5' : 'border-border'}`}>
            <div className="mb-1.5 flex items-center gap-2">
                <span className="truncate text-xs font-bold text-foreground">{m.nombre}</span>
                {m.es_actual && (
                    <span className="shrink-0 rounded-full bg-brand px-1.5 py-px text-[9px] font-bold uppercase text-white">
                        Actual
                    </span>
                )}
                <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">
                    {m.cuadrado && !vacia
                        ? <span className="inline-flex items-center gap-0.5 font-semibold text-green-600 dark:text-green-500">
                            <Check className="h-3 w-3" />cuadrada</span>
                        : vacia ? 'vacía' : (m.guardada ? 'guardada, sin cuadrar' : 'incompleta')}
                </span>
            </div>

            {!vacia && (
                <div className="mb-1.5 flex flex-wrap gap-x-3 gap-y-0.5">
                    {alimentos.map((a, i) => (
                        <span key={i} className="inline-flex items-baseline gap-1 text-[11px] text-muted-foreground">
                            <span>{getFoodEmoji(a.categorias)}</span>
                            <span className="text-foreground">{a.nombre}</span>
                            <span className="font-data">{a.cantidad_display}</span>
                        </span>
                    ))}
                </div>
            )}

            <MiniBarras actual={m.actual} objetivo={m.objetivo} />
        </div>
    );
};

export const ChatDayOverview = ({ data }) => {
    const meals = data?.day_overview?.meals;
    if (!meals?.length) return null;
    const ov = data.day_overview;
    const hechas = meals.filter(m => (m.alimentos || []).length > 0).length;

    return (
        <div className="mt-2 space-y-2 rounded-xl border border-border bg-muted/30 p-3">
            <div className="flex items-baseline justify-between gap-2">
                <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Tu día</p>
                <span className="font-data text-[10px] text-muted-foreground">
                    {hechas} de {meals.length} con alimentos
                </span>
            </div>

            <div className="space-y-1.5">
                {meals.map((m, i) => <Comida key={i} m={m} />)}
            </div>

            {ov?.objetivo && (
                <div className="border-t border-border pt-2">
                    <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                        Total del día
                    </p>
                    <MiniBarras actual={ov.consumido} objetivo={ov.objetivo} />
                </div>
            )}

            <p className="border-t border-border pt-2 text-[11px] text-muted-foreground">
                Puedes decirme "edita la comida 2", "borra la comida 3" o "vacía el post-entreno".
            </p>
        </div>
    );
};

export default ChatDayOverview;
