/**
 * ChatSuggestions - Las opciones que propone el asistente para completar la comida.
 *
 * Antes era una lista numerada dentro del texto: seis líneas con el nombre, la cantidad y
 * los tres macros escritos con letra, y al final "Dime cuál quieres (p.ej. 'la 1')". Había
 * que leerlas todas para comparar, y encima elegir escribiendo.
 *
 * El backend ya mandaba las opciones estructuradas en `suggestions`; solo se estaba
 * pintando el texto. Ahora cada una es una tarjeta con lo que aporta destacado y se elige
 * pulsándola (sigue funcionando escribir "la 1", que es lo que entiende el backend).
 */
import React from 'react';
import { getFoodEmoji } from './constants';

const MACRO = { P: '#FF671F', H: '#2196F3', G: '#FFA500' };
const NOMBRE = { P: 'proteína', H: 'hidratos', G: 'grasa' };
const FASE_MACRO = { proteina: 'P', hidratos: 'H', grasa: 'G' };

const fmt = (x) => {
    const n = Math.round((x || 0) * 10) / 10;
    return Number.isInteger(n) ? String(n) : n.toFixed(1);
};

export const ChatSuggestions = ({ data, onElegir, disabled }) => {
    const opciones = data?.suggestions;
    if (!opciones?.length) return null;

    // El macro que se está intentando cubrir: se resalta en cada opción.
    const clave = FASE_MACRO[data.fase] || null;

    // La cabecera lleva TODO el contexto de la lista. Antes lo decía también el texto de
    // la burbuja ("Lo que más te falta es proteína.") justo encima de un "PARA CUBRIR
    // PROTEÍNA": la misma frase dos veces seguidas.
    const cabecera = data.marca
        ? <>Lo que tengo de <span className="text-foreground">{data.marca}</span></>
        : clave
            ? (data.motivo === 'pedido'
                ? <>Opciones de <span style={{ color: MACRO[clave] }}>{NOMBRE[clave]}</span></>
                : <>Lo que más te falta es <span style={{ color: MACRO[clave] }}>{NOMBRE[clave]}</span></>)
            : 'Opciones';

    return (
        <div className="mt-2 space-y-2 rounded-xl border border-border bg-muted/30 p-3">
            <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                {cabecera}
            </p>

            <div className="space-y-1.5">
                {opciones.map((s, i) => {
                    const m = s.macros || {};
                    const otros = ['P', 'H', 'G']
                        .filter(k => k !== clave && (m[k] || 0) > 0)
                        .map(k => `${fmt(m[k])} ${k}`);
                    return (
                        <button
                            key={i}
                            type="button"
                            disabled={disabled}
                            onClick={() => onElegir?.(i + 1, s)}
                            className="flex w-full items-center gap-2 rounded-lg border border-border bg-card p-2 text-left transition-colors hover:border-brand hover:bg-brand/5 disabled:opacity-50"
                        >
                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted font-data text-[10px] font-bold text-muted-foreground">
                                {i + 1}
                            </span>
                            <span className="text-base leading-5">{getFoodEmoji(s.categorias)}</span>
                            {/* EL NOMBRE, SIN SALIRSE DE LA PANTALLA.
                                Este `truncate` no recortaba nada: colgaba de un `flex
                                flex-wrap` sin `min-w-0`, y un flex sin eso mide por su
                                contenido entero. Con «Fiambre de pechuga de pavo pimienta
                                finas lonchas (Hacendado)» la tarjeta se iba a 626 px en una
                                pantalla de 390 y empujaba fuera la cantidad y los macros --
                                lo único que hace falta para elegir --, sin scroll con el que
                                llegar a ellos. Medido en el navegador, 10-08.
                                Y ya de paso deja de recortar: en dos líneas cabe entero, que
                                es donde vive la marca. */}
                            <span className="min-w-0 flex-1">
                                <span className="block break-words text-sm font-semibold text-foreground line-clamp-2">
                                    {(s.nombre || '').trim()}
                                </span>
                                {otros.length > 0 && (
                                    <span className="block font-data text-[10px] text-muted-foreground">
                                        {otros.join(' · ')}
                                    </span>
                                )}
                            </span>
                            <span className="shrink-0 text-right">
                                <span className="block font-data text-xs text-foreground">
                                    {s.cantidad_display || `${s.cantidad_g || 0}g`}
                                </span>
                                {clave && (
                                    <span className="block font-data text-[11px] font-bold"
                                        style={{ color: MACRO[clave] }}>
                                        {fmt(m[clave])} {clave}
                                    </span>
                                )}
                            </span>
                        </button>
                    );
                })}
            </div>

            <p className="text-[11px] text-muted-foreground">
                Pulsa una, o dime cuál quieres ("la 1", "el nombre"). También puedes pedirme otras.
            </p>
        </div>
    );
};

export default ChatSuggestions;
