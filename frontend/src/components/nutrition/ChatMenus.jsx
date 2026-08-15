/**
 * ChatMenus - Los menús completos (borradores) que propone el asistente-agente.
 *
 * A diferencia de ChatSuggestions (alimentos sueltos para elegir UNO), aquí cada tarjeta
 * es una comida entera con sus cantidades ya cuadradas por el motor. "Elegir este menú"
 * la vuelca a la comida actual pasando por la revisión del backend (si algo choca con
 * una restricción, el backend lo bloquea y el chat lo cuenta).
 */
import React from 'react';
import { getFoodEmoji } from './constants';

const MACRO = { P: '#FF671F', H: '#2196F3', G: '#FFA500' };

const fmt = (x) => {
    const n = Math.round((x || 0) * 10) / 10;
    // Coma decimal, como el resto de la casa: la tarjeta decia "47.1 P" mientras el
    // bloque de la comida de al lado decia "47,1" (QA 15-08 ronda 3, B1).
    return Number.isInteger(n) ? String(n) : n.toFixed(1).replace('.', ',');
};

export const ChatMenus = ({ data, onAplicar, disabled }) => {
    const borradores = data?.borradores;
    if (!borradores?.length) return null;

    return (
        <div className="mt-2 space-y-2 rounded-xl border border-border bg-muted/30 p-3">
            <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                {borradores.length > 1 ? 'Elige un menú' : 'Menú propuesto'}
            </p>

            <div className="space-y-2">
                {borradores.map((b, i) => {
                    const t = b.macros_totales || {};
                    return (
                        <div key={b.id || i}
                            className="rounded-lg border border-border bg-card p-2.5">
                            <div className="flex items-baseline justify-between gap-2">
                                <span className="text-sm font-semibold text-foreground">
                                    {/* El numero viene del backend y no se reinicia entre
                                        tandas: la "opción 3" del texto del asistente es
                                        SIEMPRE la tarjeta "Opción 3". Y el numero se pinta
                                        SIEMPRE, tambien en las recetas: una tarjeta sin
                                        numero deja al cliente sin saber cual es "la 2"
                                        (QA 15-08, A1-A6). */}
                                    {`Opción ${b.numero || i + 1}`}
                                    {b.nombre ? ` · ${b.nombre}` : ''}
                                    {b.origen === 'recetario' && (
                                        <span className="ml-1.5 rounded bg-brand/10 px-1 py-0.5 text-[9px] font-bold uppercase text-brand">
                                            receta
                                        </span>
                                    )}
                                </span>
                                {/* SEPARADOS Y CON AIRE. Iban tres spans pegados de 11 px con
                                    6 px de margen: en el teléfono se leía «47.5P54H9.5G», un
                                    churro de doce caracteres. Un punto entre medias y un
                                    espacio antes de la letra y ya son tres números. */}
                                <span className="shrink-0 font-data text-[11px] whitespace-nowrap">
                                    {['P', 'H', 'G'].map((k, n) => (
                                        <span key={k} className="font-bold" style={{ color: MACRO[k] }}>
                                            {n > 0 && <span className="mx-1 font-normal text-muted-foreground">·</span>}
                                            {fmt(t[k])} {k}
                                        </span>
                                    ))}
                                </span>
                            </div>

                            <ul className="mt-1.5 space-y-0.5">
                                {(b.items || []).map((it, j) => (
                                    <li key={j} className="flex items-center gap-1.5 text-xs text-foreground">
                                        <span className="text-sm leading-4">{getFoodEmoji(it.categorias)}</span>
                                        {/* Sin `truncate`: en el teléfono, con los macros y la
                                            cantidad a la derecha, «Cecina de vacuno» ya no
                                            cabía y se cortaba. Que baje de línea. */}
                                        <span className="min-w-0 flex-1 break-words">{it.nombre}</span>
                                        {/* Macros por alimento: sin esto, el cliente preguntaba
                                            "muéstrame los macros" porque solo veía el total */}
                                        <span className="shrink-0 font-data text-[10px] text-muted-foreground whitespace-nowrap">
                                            {['P', 'H', 'G'].filter(k => (it.macros?.[k] || 0) > 0)
                                                .map(k => `${fmt(it.macros[k])} ${k}`).join(' · ')}
                                        </span>
                                        <span className="shrink-0 font-data text-muted-foreground">
                                            {it.cantidad_display || `${it.cantidad_g}g`}
                                        </span>
                                    </li>
                                ))}
                            </ul>

                            {/* Aviso del revisor: la opción se enseña igual (ocultarla
                                descuadraba la numeración con el texto del asistente),
                                pero el cliente elige sabiendo qué cojea. */}
                            {(b.avisos || []).length > 0 && (
                                <p className="mt-1.5 rounded bg-amber-500/10 px-2 py-1 text-[11px] text-amber-600 dark:text-amber-400">
                                    ⚠ {b.avisos.join('; ')}
                                </p>
                            )}
                            {/* Sin enlace a la receta (Francisco, 15-08): la tarjeta trae el
                                menu entero con sus cantidades y el enlace sacaba al cliente
                                de la app. El backend ya no manda receta_url. */}

                            {/* Un menu que el revisor tumbo se ve (nadie se queda sin
                                opciones) pero no se puede elegir: el boton desaparece. */}
                            {b.aplicado ? (
                                <p className="mt-2 w-full rounded-lg bg-muted py-1.5 text-center text-[11px] font-semibold text-muted-foreground">
                                    Ya lo tienes puesto en esta comida
                                </p>
                            ) : b.no_aplicable ? (
                                <p className="mt-2 w-full rounded-lg bg-muted py-1.5 text-center text-[11px] font-semibold text-muted-foreground">
                                    Solo de referencia: pide otra opción
                                </p>
                            ) : (
                            <button
                                type="button"
                                disabled={disabled}
                                onClick={() => onAplicar?.(b)}
                                data-testid={`chat-menu-aplicar-${i}`}
                                className="mt-2 w-full rounded-lg bg-brand py-1.5 text-xs font-bold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                            >
                                Elegir este menú
                            </button>
                            )}
                        </div>
                    );
                })}
            </div>

            <p className="text-[11px] text-muted-foreground">
                También puedes pedir cambios ("cámbiame la fruta", "sin el yogur") u otras opciones.
            </p>
        </div>
    );
};

export default ChatMenus;
