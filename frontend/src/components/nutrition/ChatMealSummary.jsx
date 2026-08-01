/**
 * ChatMealSummary - Lo que responde el asistente cuando toca una comida.
 *
 * Antes todo esto era UN SOLO texto plano dentro de la burbuja: los alimentos añadidos,
 * las tres líneas de macros (llevas / objetivo / te falta) y los avisos, uno detrás de
 * otro. Con dos o tres alimentos ya era un muro de texto donde no se veía lo importante.
 *
 * Y había algo peor: la lista era "Alimentos añadidos", o sea SOLO lo que se acababa de
 * tocar. Si tenías huevos y bacon y pedías "pon huevos", el mensaje enseñaba únicamente
 * los huevos y parecía que el bacon se hubiera borrado (seguía en la comida, y los macros
 * de abajo lo contaban). Por eso aquí se lista la comida ENTERA, marcando con un punto
 * naranja lo que acaba de entrar o cambiar.
 */
import React from 'react';
import { AlertTriangle, Check } from 'lucide-react';
import { getFoodEmoji } from './constants';

// Misma paleta que MealCard y DaySummary, para que el chat no invente colores propios.
const MACRO = { P: '#FF671F', H: '#2196F3', G: '#FFA500' };
const MACROS = [
    { key: 'P', label: 'Proteína', color: MACRO.P },
    { key: 'H', label: 'Hidratos', color: MACRO.H },
    { key: 'G', label: 'Grasa', color: MACRO.G },
];
const NOMBRE = { P: 'proteína', H: 'hidratos', G: 'grasa' };

const fmt = (x) => {
    const n = Math.round((x || 0) * 10) / 10;
    return Number.isInteger(n) ? String(n) : n.toFixed(1);
};

/** Una barra por macro: lo que llevas sobre el objetivo. Si te pasas, se marca en rojo. */
const BarraMacro = ({ label, color, actual, objetivo }) => {
    const pct = objetivo > 0 ? Math.min((actual / objetivo) * 100, 100) : 0;
    const pasado = objetivo > 0 && actual > objetivo + 0.05;
    return (
        <div className="flex items-center gap-2">
            <span className="w-[52px] shrink-0 text-[11px] text-muted-foreground">{label}</span>
            <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full transition-all"
                    style={{ width: `${pct}%`, backgroundColor: pasado ? '#EF4444' : color }} />
            </div>
            <span className="shrink-0 text-right font-data text-[11px]"
                style={{ color: pasado ? '#EF4444' : color }}>
                {fmt(actual)}<span className="text-muted-foreground">/{fmt(objetivo)}</span>
            </span>
        </div>
    );
};

const FilaAlimento = ({ nombre, cantidad, macros, categorias, esNuevo }) => {
    const m = macros || {};
    const trozos = [
        (m.P || 0) > 0 && `${fmt(m.P)} P`,
        (m.H || 0) > 0 && `${fmt(m.H)} H`,
        (m.G || 0) > 0 && `${fmt(m.G)} G`,
    ].filter(Boolean);
    return (
        <div className="flex items-start gap-2">
            <span className="text-base leading-5">{getFoodEmoji(categorias)}</span>
            <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-1.5">
                        {esNuevo && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand" title="Recién añadido" />}
                        <span className="truncate text-sm font-semibold text-foreground">{nombre}</span>
                    </span>
                    <span className="shrink-0 font-data text-xs text-foreground">{cantidad}</span>
                </div>
                {trozos.length > 0 && (
                    <div className="font-data text-[11px] text-muted-foreground">{trozos.join(' · ')}</div>
                )}
            </div>
        </div>
    );
};

export const ChatMealSummary = ({ data }) => {
    if (!data) return null;
    const ms = data.meal_status;
    const noAnadidos = data.foods_not_found || [];
    const recien = new Set((data.foods_added || []).map(f => (f.nombre || '').trim().toLowerCase()));

    // La comida entera; si no viniera meal_status, al menos lo que se acaba de añadir.
    const enLaComida = ms?.alimentos?.length
        ? ms.alimentos.map(a => ({
            nombre: (a.nombre || a.alimento?.nombre || '').trim(),
            cantidad: a.cantidad_display || `${a.cantidad_g || a.cantidad || 0}g`,
            macros: a.macros,
            categorias: a.alimento?.categorias || a.categorias,
        }))
        : (data.foods_added || []).map(f => ({
            nombre: (f.nombre || '').trim(),
            cantidad: f.cantidad_display,
            macros: f.macros,
            categorias: f.categorias,
        }));

    if (!enLaComida.length && !noAnadidos.length && !ms) return null;

    const restante = ms?.restante || {};
    const faltan = MACROS.filter(x => (restante[x.key] || 0) > 4)
        .map(x => `${fmt(restante[x.key])} g de ${NOMBRE[x.key]}`);
    const sobran = MACROS.filter(x => (restante[x.key] || 0) < -4)
        .map(x => `${fmt(Math.abs(restante[x.key]))} g de ${NOMBRE[x.key]}`);

    return (
        <div className="mt-2 space-y-2.5 rounded-xl border border-border bg-muted/30 p-3">
            {enLaComida.length > 0 && (
                <div className="space-y-2">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                        {ms?.comida_nombre || `Comida ${ms?.comida || ''}`.trim() || 'En la comida'}
                    </p>
                    {enLaComida.map((f, i) => (
                        <FilaAlimento key={i} {...f} esNuevo={recien.has(f.nombre.toLowerCase())} />
                    ))}
                </div>
            )}

            {noAnadidos.length > 0 && (
                <div className="space-y-1 border-t border-border pt-2">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">No lo tengo</p>
                    {noAnadidos.map((f, i) => (
                        <p key={i} className="text-xs text-muted-foreground">
                            <span className="font-semibold text-foreground">{f.buscado}</span>
                            {f.razon ? `: ${f.razon}` : ''}
                            {f.sugerencia ? ` ${f.sugerencia}` : ''}
                        </p>
                    ))}
                </div>
            )}

            {ms && (
                <div className="space-y-1.5 border-t border-border pt-2.5">
                    {MACROS.map(x => (
                        <BarraMacro key={x.key} label={x.label} color={x.color}
                            actual={ms.actual?.[x.key] || 0} objetivo={ms.objetivo?.[x.key] || 0} />
                    ))}
                </div>
            )}

            {ms?.cuadrado && (
                <div className="flex items-center gap-1.5 border-t border-border pt-2 text-xs font-semibold text-green-600 dark:text-green-500">
                    <Check className="h-3.5 w-3.5" />
                    Comida cuadrada. Pulsa "Guardar y siguiente".
                </div>
            )}

            {ms && !ms.cuadrado && (faltan.length > 0 || sobran.length > 0) && (
                <div className="flex items-start gap-1.5 border-t border-border pt-2 text-xs text-muted-foreground">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
                    <span>
                        {faltan.length > 0 && <>Faltan <b className="text-foreground">{faltan.join(' y ')}</b></>}
                        {faltan.length > 0 && sobran.length > 0 && ' · '}
                        {sobran.length > 0 && <>Te pasas <b className="text-foreground">{sobran.join(' y ')}</b></>}
                    </span>
                </div>
            )}
        </div>
    );
};

export default ChatMealSummary;
