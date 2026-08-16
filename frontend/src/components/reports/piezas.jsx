/**
 * Las piezas del reporte: los bloques numerados, las opciones, las estrellas y el dato.
 *
 * Salen de T7 y T8 del doc del 16-08. El reporte dejó de ser un formulario con campos
 * sueltos y pasó a ser una lista de bloques numerados donde CADA BLOQUE EMPIEZA POR LO
 * QUE YA SABEMOS y solo pregunta lo que no se puede saber (reglas 3 y 5 del doc). Eso es
 * lo que hay aquí: el sitio donde se pinta el dato, y el sitio donde se pregunta.
 *
 * Los textos no viven en estas piezas: los pone quien las usa, porque son los del doc y
 * tienen que poder leerse tal cual en el formulario, no repartidos por tres ficheros.
 */
import React from 'react';
import { Star } from 'lucide-react';

const ORANGE = '#FF671F';

/** Un bloque del reporte: "04 Tu dieta". El número lo pone el formulario, porque cambia
 *  de un plan a otro (el que no lleva lesiones ni cardio tiene 11 bloques, no 13). */
export const Bloque = ({ numero, titulo, sub, children, testid }) => (
    <div className="bg-card border border-border rounded-2xl p-4 space-y-3" data-testid={testid}>
        <div>
            <p className="text-sm font-bold text-foreground">
                {numero && <span className="text-muted-foreground tabular-nums mr-1.5">{numero}</span>}
                {titulo}
            </p>
            {sub && <p className="text-[13px] text-muted-foreground mt-0.5">{sub}</p>}
        </div>
        {children}
    </div>
);

/**
 * EL DATO, ANTES DE LA PREGUNTA.
 *
 * "ESTE MES HAS REGISTRADO · 25 de 28 días · 89 %". Va arriba del bloque y en grande
 * porque es el motivo de que las preguntas de siempre hayan desaparecido: no se le
 * pregunta si ha seguido la dieta, se le enseña.
 */
export const Dato = ({ encabezado, cifra, pct, nota, testid }) => (
    <div className="rounded-xl bg-muted px-3.5 py-3" data-testid={testid}>
        {encabezado && (
            <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">{encabezado}</p>
        )}
        <p className="flex items-baseline gap-2 mt-0.5">
            <span className="text-xl font-bold text-foreground" style={{ fontFamily: 'Barlow Condensed' }}>{cifra}</span>
            {pct != null && <span className="text-sm font-bold" style={{ color: ORANGE }}>{pct} %</span>}
        </p>
        {nota && <p className="text-[13px] text-muted-foreground mt-1">{nota}</p>}
    </div>
);

/** Una pregunta con sus opciones cerradas. `columnas` para las listas cortas. */
export const Opciones = ({ pregunta, ayuda, opciones, valor, onChange, columnas = 1, testid }) => (
    <div data-testid={testid}>
        {pregunta && <p className="text-sm text-foreground mb-2">{pregunta}</p>}
        {ayuda && <p className="text-[13px] text-muted-foreground -mt-1 mb-2">{ayuda}</p>}
        <div className={`grid gap-2 ${columnas === 1 ? 'grid-cols-1' : columnas === 2 ? 'grid-cols-2' : 'grid-cols-2 sm:grid-cols-4'}`}>
            {opciones.map(o => {
                const activo = valor === o.value;
                return (
                    <button key={o.value} type="button" data-testid={`${testid}-${o.value}`}
                        onClick={() => onChange(activo ? '' : o.value)}
                        className={`py-2.5 px-3 rounded-xl border text-sm font-semibold text-left transition-all ${
                            activo ? 'border-[#FF671F] bg-[#FF671F]/10 text-[#FF671F]'
                                   : 'border-border bg-muted text-foreground/70 hover:border-foreground/30'}`}>
                        {o.label}
                    </button>
                );
            })}
        </div>
    </div>
);

/** Un campo libre. En el reporte casi todos son opcionales y se dice cuando no lo son. */
export const TextoLibre = ({ etiqueta, ayuda, valor, onChange, placeholder, filas = 3, testid }) => (
    <div>
        {etiqueta && <p className="text-sm text-foreground mb-1.5">{etiqueta}</p>}
        {ayuda && <p className="text-[13px] text-muted-foreground -mt-1 mb-1.5">{ayuda}</p>}
        <textarea
            value={valor || ''} rows={filas} placeholder={placeholder}
            onChange={(e) => onChange(e.target.value)} data-testid={testid}
            className="w-full bg-muted border border-input rounded-xl px-3 py-2.5 text-foreground text-sm placeholder-foreground/20 focus:outline-none focus:border-[#FF671F] transition-colors resize-none"
        />
    </div>
);

/**
 * LAS SENSACIONES, CON ESTRELLAS ("y las sensaciones con estrellas, como pediste").
 *
 * Se puede desmarcar volviendo a pulsar la misma: una estrella puesta sin querer, en un
 * campo que no es obligatorio, no se puede quitar de ninguna otra forma.
 */
export const Estrellas = ({ valor, onChange, testid, soloLectura = false }) => (
    <div className="flex items-center gap-1" data-testid={testid}>
        {[1, 2, 3, 4, 5].map(n => {
            const puesta = (valor || 0) >= n;
            return (
                <button key={n} type="button" disabled={soloLectura}
                    onClick={() => onChange(valor === n ? null : n)}
                    data-testid={`${testid}-${n}`} aria-label={`${n} de 5`}
                    className={`p-1 transition-transform ${soloLectura ? '' : 'hover:scale-110'}`}>
                    <Star className="w-7 h-7" style={{ color: puesta ? ORANGE : 'currentColor' }}
                        fill={puesta ? ORANGE : 'none'}
                        strokeWidth={puesta ? 0 : 1.5} />
                </button>
            );
        })}
    </div>
);

/** "★★★★☆" para leer, no para tocar: la media de lo que fue marcando cada día. */
export const EstrellasMedia = ({ valor }) => {
    const n = Math.round(Number(valor) || 0);
    return (
        <span className="tracking-widest" style={{ color: ORANGE }} aria-label={`${valor} de 5`}>
            {'★'.repeat(n)}{'☆'.repeat(Math.max(0, 5 - n))}
        </span>
    );
};

/** Los dos botones de una pregunta de sí o no, uno al lado del otro. */
export const DosBotones = ({ opciones, valor, onChange, testid }) => (
    <div className="grid grid-cols-2 gap-2">
        {opciones.map(o => {
            const activo = valor === o.value;
            return (
                <button key={o.value} type="button" data-testid={`${testid}-${o.value}`}
                    onClick={() => onChange(activo ? '' : o.value)}
                    className={`py-2.5 px-3 rounded-xl border text-sm font-semibold transition-all ${
                        activo ? 'border-[#FF671F] bg-[#FF671F]/10 text-[#FF671F]'
                               : 'border-border bg-muted text-foreground/70 hover:border-foreground/30'}`}>
                    {o.label}
                </button>
            );
        })}
    </div>
);

/** "el 8 y el 14 de agosto": una lista de cosas dicha como se dice hablando. */
export const enumerar = (lista) => {
    const xs = (lista || []).filter(Boolean);
    if (!xs.length) return '';
    if (xs.length === 1) return xs[0];
    return `${xs.slice(0, -1).join(', ')} y ${xs[xs.length - 1]}`;
};

/**
 * Lo mismo con fechas, sin repetir el mes: "el 8 y el 14 de agosto", no "el 8 de agosto
 * y el 14 de agosto". Si caen en meses distintos se dice el de cada una, que ahí sí hace
 * falta.
 */
export const enumerarFechas = (fechas) => {
    const xs = (fechas || []).filter(Boolean);
    if (xs.length < 2) return enumerar(xs);
    const mes = (f) => (String(f).match(/ de (\w+)$/) || [])[1];
    const meses = new Set(xs.map(mes));
    if (meses.size !== 1 || !mes(xs[0])) return enumerar(xs);
    const sinMes = xs.slice(0, -1).map(f => String(f).replace(/ de \w+$/, ''));
    return enumerar([...sinMes, xs[xs.length - 1]]);
};

/** El peso, con coma decimal: "77,1 kg". */
export const kg = (v) => (v == null ? null : `${String(v).replace('.', ',')} kg`);
