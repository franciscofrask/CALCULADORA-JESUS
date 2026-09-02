import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useEsTelefono } from '../lib/esTelefono';
import { toast } from 'sonner';
import {
    Activity, CheckCircle2, Scale, Send, Zap,
    Loader2, ChevronLeft, ChevronDown,
} from 'lucide-react';
import { Estrellas } from '../components/reports/piezas';

const inputCls = "w-full bg-muted border border-input rounded-xl px-3 py-2.5 text-foreground text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors";

// Aquí había una tarjeta con la etiqueta de riesgo del cliente ("Saludable" / "Atención" /
// "En riesgo") y el motivo debajo. Se quitó el 07-08 (punto 6 del documento de Jesús): esa
// etiqueta es una nota de gestión del entrenador, para saber a quién hay que llamar, y sus
// motivos hablan de cobros y de bajas. El cliente no tiene por qué verse etiquetado en su
// propio panel. Vive solo en el lado del entrenador, y su ruta también.
//
// Y aquí vivían las cinco caritas del ánimo (`MOOD_FACES`). No las pintaba nadie desde el
// 31-07 y las sensaciones del día se preguntan ahora con estrellas (punto 01 del doc
// 24-08), así que se van con el resto del check-in viejo.

// El día del RELOJ DEL CLIENTE (bloque F, 23-08). `toISOString()` era el día UTC: desde
// América por la tarde «hoy» ya era mañana y el cierre de hoy nunca contaba como de hoy.
const todayKey = () => new Date().toLocaleDateString('en-CA');
const isSameDay = (iso) => iso && new Date(iso).toLocaleDateString('en-CA') === todayKey();

// «Jueves, 20 de agosto», la fecha de la cabecera del cierre del día.
const fechaLarga = (iso) => {
    const d = iso ? new Date(`${iso}T12:00:00`) : new Date();
    const texto = d.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
    return texto.charAt(0).toUpperCase() + texto.slice(1);
};

// La etiqueta del historial en cristiano: la base guarda el tipo en inglés
// (daily/weekly/monthly) y la píldora lo gritaba tal cual, «MONTHLY».
// El diario decía «DIARIO» (P78, doc 23-08), que es como se llama la pestaña Diario de
// Seguimiento: dos cosas distintas con el mismo nombre. La entrada se llama como la
// pantalla que la crea, «Cierre del día», y el Diario usa el mismo nombre.
// Desde el 24-08 la píldora casi no se pinta: cada bloque del historial lleva su título y
// solo sobrevive en «Reportes anteriores» cuando ahí conviven semanales y mensuales.
const TIPO_CHECKIN = { daily: 'Cierre del día', weekly: 'Semanal', monthly: 'Mensual' };

// «77,3 kg, ayer». Los decimales con coma, que es como se escriben aquí.
const kilos = (v) => `${String(v).replace('.', ',')} kg`;
const cuando = (iso) => {
    if (!iso) return '';
    const dias = Math.round((new Date(`${todayKey()}T12:00:00`) - new Date(`${iso}T12:00:00`)) / 86400000);
    if (dias <= 0) return 'hoy';
    if (dias === 1) return 'ayer';
    return new Date(`${iso}T12:00:00`).toLocaleDateString('es-ES', { day: 'numeric', month: 'long' });
};

// ── Cómo se le nombra al cliente cada respuesta ──────────────────────────────
//
// UN SOLO VOCABULARIO CON EL FORMULARIO: el historial decía «Desgaste: menos de lo
// habitual» mientras la pregunta habla de moverse y sus botones dicen «Menos» / «Como
// siempre» / «Más». Eran dos maneras de nombrar el mismo dato, y el cliente leía en su
// historial una palabra que nadie le había preguntado. Los valores guardados
// (menos/igual/mas) no cambian: esto es solo cómo se le enseña.
const MOVIMIENTO_VALOR = { menos: 'Menos', igual: 'Como siempre', mas: 'Más' };
const SUPLES_VALOR = { si: 'Sí', no_todos: 'No todos', no: 'No' };
const CARDIO_VALOR = { si: 'Sí', no: 'No', no_tocaba: 'No tocaba' };
// El entreno, con los tres estados del punto 19. Los dos valores viejos siguen aquí: hay
// cierres escritos con ellos y sin esto se leerían en blanco.
//   entrenó -> ✓ · le tocaba y no fue -> ✗ · tocaba descanso -> «Descanso», SIN SÍMBOLO,
//   «porque no es ni bueno ni malo».
const ENTRENO_VALOR = {
    si: 'Sí', no: 'No', descanso: 'No, tocaba descanso',
    si_no_lo_puse: 'Sí', no_entrene: 'No',
};
const ENTRENO_LINEA = {
    si: 'Entreno ✓', no: 'Entreno ✗', descanso: 'Descanso',
    si_no_lo_puse: 'Entreno ✓', no_entrene: 'Entreno ✗',
};

const NOMBRE_COMIDA = (k) => {
    if (!k) return 'Comida';
    if (k === 'Post') return 'Post-entreno';
    if (k === 'Intra') return 'Intra-entreno';
    return k.startsWith('C') ? `Comida ${k.slice(1)}` : k;
};

// «★★★★☆». Para leer de un vistazo una fila de días, que es para lo que Jesús las pidió.
const estrellitas = (n) => '★'.repeat(Math.max(0, Math.min(5, n || 0)))
    + '☆'.repeat(Math.max(0, 5 - Math.max(0, Math.min(5, n || 0))));

// «Lun 24». La cabecera de una línea del historial (punto 19).
const diaCorto = (iso) => {
    const d = new Date(`${iso}T12:00:00`);
    const nombre = d.toLocaleDateString('es-ES', { weekday: 'short' }).replace('.', '');
    return `${nombre.charAt(0).toUpperCase()}${nombre.slice(1)} ${d.getDate()}`;
};

// «Lun 24 · ★★★★☆ · Entreno ✓ · Dieta ✓ · 96 kg»: las cuatro cosas del punto 19, en una
// sola línea y por día. El peso, SOLO el día que lo registró.
const lineaDelDia = (c) => {
    const trozos = [];
    if (c.sensaciones != null) trozos.push(estrellitas(c.sensaciones));
    if (c.entreno_respuesta) trozos.push(ENTRENO_LINEA[c.entreno_respuesta] || 'Entreno');
    else if (c.trained != null) trozos.push(c.trained ? 'Entreno ✓' : 'Entreno ✗');
    if (c.nutrition_followed != null) trozos.push(c.nutrition_followed ? 'Dieta ✓' : 'Dieta ✗');
    if (c.weight != null) trozos.push(kilos(c.weight));
    return trozos;
};

// El detalle de un día (punto 21): las once, «con el nombre entero» y «3 de 5», no «3/5»,
// que «se lee, no se descifra».
//
// LO QUE ESE DÍA NO SE PREGUNTÓ, NO SALE. Los cierres de antes del 24-08 no tienen
// sensaciones, ni cardio, ni el entreno de tres estados: enseñarlos en blanco o con un
// guion sería once renglones para decir que no hay nada. Sale lo que contestó y ya.
const detalleDelDia = (c) => {
    const filas = [];
    const pon = (nombre, valor) => { if (valor) filas.push({ nombre, valor }); };
    pon('Sensaciones', c.sensaciones != null ? estrellitas(c.sensaciones) : null);
    if (c.entreno_respuesta || c.trained != null) {
        const respuesta = c.entreno_respuesta
            ? (ENTRENO_VALOR[c.entreno_respuesta] || c.entreno_respuesta)
            : (c.trained ? 'Sí' : 'No');
        pon('Entreno', c.entreno_estrellas != null
            ? `${respuesta} ${estrellitas(c.entreno_estrellas)}` : respuesta);
    }
    pon('Cardio', CARDIO_VALOR[c.cardio]);
    pon('Movimiento', MOVIMIENTO_VALOR[c.movimiento]);
    pon('Suplementos', SUPLES_VALOR[c.suplementos?.respuesta]);
    if (c.extras_respuesta) pon('Extras', c.extras_respuesta === 'si' ? 'Sí' : 'No');
    pon('Descanso', c.descanso != null ? `${c.descanso} de 5` : null);
    pon('Energía', c.energy != null ? `${c.energy} de 5` : null);
    pon('Hambre', c.hunger_anxiety != null ? `${c.hunger_anxiety} de 5` : null);
    pon('Ánimo', c.mood != null ? `${c.mood} de 5` : null);      // los cierres viejos
    if (c.nutrition_followed != null) pon('Dieta', c.nutrition_followed ? 'Cerrada' : 'Sin cerrar');
    if (c.cena_hecha != null && c.comida_pendiente) {
        pon(NOMBRE_COMIDA(c.comida_pendiente), c.cena_hecha ? 'La hizo' : 'Sin registrar');
    }
    // El peso ya no es siempre del día del cierre: la casilla pregunta de cuándo es el
    // pesaje (doc 24-08), así que si lo apuntó de otro día se dice, o el detalle del 24
    // estaría fechando un peso del 22.
    if (c.weight != null) {
        const otroDia = c.peso_fecha && c.peso_fecha !== c.dia ? ` · ${cuando(c.peso_fecha)}` : '';
        pon('Peso', `${kilos(c.weight)}${otroDia}`);
    }
    if (c.notas?.texto) pon('Notas', c.notas.compartida ? 'Compartidas' : 'Solo para ti');
    return filas;
};

// Los textos libres del cierre, cada uno con su título delante.
const renglonesDelCierre = (c) => {
    const renglones = [];
    if (c.entreno_nota) renglones.push({ titulo: 'Entreno', texto: c.entreno_nota });
    if (c.suplementos?.detalle) renglones.push({ titulo: 'Suplementos', texto: c.suplementos.detalle });
    if (c.exceso_nota) renglones.push({ titulo: 'Sobre el exceso', texto: c.exceso_nota });
    if (c.comido_hoy) renglones.push({ titulo: 'Comido hoy', texto: c.comido_hoy });
    if (c.notas?.texto) {
        renglones.push({
            titulo: c.notas.compartida ? 'Notas · compartidas' : 'Notas · solo para ti',
            texto: c.notas.texto,
        });
    }
    return renglones;
};

// «22 ago 2026». La fecha de una entrada del historial, SIEMPRE SIN HORA: «la hora
// confunde, un check-in de las 07:29 es el del día anterior» (punto 22 del doc 24-08).
// `dia` es el día del cliente y lo llevan los cierres desde el bloque F.
//
// EL QUE NO TIENE `dia` NO ES EL CASO RARO, ES EL HISTORIAL ENTERO: en producción son
// 1.595 de las 1.600 entradas (los 1.593 reportes mensuales importados de Calma, los 2
// semanales y hasta 2 cierres de antes del bloque F). Dejarles la hora «porque es lo
// único que traen» era dejar sin arreglar justo lo que él señala, que son esas filas. El
// día se saca de `created_at`, que va con su «+00:00»: el navegador lo pasa a la hora del
// cliente él solo, así que la fecha que sale es la que él vivió.
const fechaDeEntrada = (c) => (c.dia
    ? new Date(`${c.dia}T12:00:00`).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })
    : new Date(c.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' }));

// ── Subcomponentes a nivel de módulo (mantienen el foco al teclear) ──────────
const Card = ({ className = '', children }) => (
    <div className={`bg-card border border-border rounded-2xl ${className}`}>{children}</div>
);

// Una entrada de «Reportes anteriores» (semanal o mensual). Los cierres del día YA NO
// pasan por aquí: tienen su lista propia, una línea por día (puntos 19 a 21 del doc
// 24-08). `conTipo` pinta la píldora («Semanal», «Mensual»): dentro de un bloque con
// título no hace falta, y solo se enciende donde el título no basta.
const EntradaDelHistorial = ({ c, conTipo = false }) => (
    <li className="rounded-xl border border-border bg-muted p-3">
        <div className="flex items-center justify-between mb-2">
            {conTipo ? (
                <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full bg-card border border-border text-foreground/60">
                    {TIPO_CHECKIN[c.type] || c.type}
                </span>
            ) : <span />}
            <span className="text-[11px] text-foreground/50">{fechaDeEntrada(c)}</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-foreground/70">
            {c.weight != null && <span><Scale className="w-3 h-3 inline mr-1" />{c.weight} kg</span>}
            {c.training_compliance != null && <span>Entreno {c.training_compliance}%</span>}
            {c.nutrition_compliance != null && <span>Nutri {c.nutrition_compliance}%</span>}
            {c.sleep_quality != null && <span>Sueño {c.sleep_quality}/10</span>}
            {c.body_fat_pct != null && <span>Grasa {c.body_fat_pct}%</span>}
        </div>
        {c.trainer_feedback && (
            <div className="mt-2 p-2 bg-brand/10 border border-brand/20 rounded-lg text-sm text-foreground/80">
                <span className="text-[10px] uppercase tracking-wider text-brand font-bold mr-2">Entrenador:</span>{c.trainer_feedback}
            </div>
        )}
    </li>
);

// Aquí vivían `BoolPicker` (los dos botones de sí/no del check-in viejo) y `Collapsible`,
// la caja plegable del semanal y del mensual. Los dos formularios se cayeron con T11 del
// doc 16-08 y desde el 24-08 no queda nada que los pinte.

// ── EL HISTORIAL: UNA LÍNEA POR DÍA (puntos 19 a 21 del doc 24-08) ───────────
//
// «Lun 24 · ★★★★☆ · Entreno ✓ · Dieta ✓ · 96 kg». Se toca y se abre con las once.
//
// DESDE QUÉ DÍA SE CUENTAN LOS HUECOS (punto 20, decidido aquí porque hacía falta un
// criterio y no lo había): desde el PRIMER cierre que tiene escrito, y como mucho 30 días
// atrás. Contar desde el alta no vale -- hay clientes de 2023 y saldrían dos años de
// «Sin rellenar» --, y contar desde una fecha fija tampoco: la pantalla no lleva la misma
// vida para todos. Su primer cierre es el día en que esta pantalla empezó a existir para
// él, que es lo único que sabemos de verdad. Quien no ha cerrado ninguno no tiene huecos:
// no tiene lista todavía.
const DIAS_DE_HUECO_COMO_MUCHO = 30;

const _sumaDias = (iso, n) => {
    const d = new Date(`${iso}T12:00:00`);
    d.setDate(d.getDate() + n);
    return d.toLocaleDateString('en-CA');
};

/**
 * Los días del historial, de hoy hacia atrás: los que cerró y los huecos AGRUPADOS.
 *
 * «Los días seguidos sin rellenar se agrupan en una sola línea, no una por día. Tres
 * huecos seguidos son tres líneas que dicen lo mismo que una.»
 */
export const diasDelHistorial = (cierres, hoyIso) => {
    const porDia = new Map();
    for (const c of cierres) {
        // Los cierres de antes del bloque F no traen `dia`: su día sale del created_at,
        // que el navegador ya pasa a la hora del cliente.
        const dia = c.dia || (c.created_at ? new Date(c.created_at).toLocaleDateString('en-CA') : null);
        if (dia && !porDia.has(dia)) porDia.set(dia, c);
    }
    if (porDia.size === 0) return [];

    const primero = [...porDia.keys()].sort()[0];
    const tope = _sumaDias(hoyIso, -(DIAS_DE_HUECO_COMO_MUCHO - 1));
    const desde = primero > tope ? primero : tope;

    const filas = [];
    for (let dia = hoyIso; dia >= desde; dia = _sumaDias(dia, -1)) {
        const cierre = porDia.get(dia);
        if (cierre) { filas.push({ tipo: 'dia', dia, cierre }); continue; }
        const ultima = filas[filas.length - 1];
        if (ultima && ultima.tipo === 'hueco') ultima.dias.push(dia);
        else filas.push({ tipo: 'hueco', dias: [dia] });
    }

    // Y LOS DÍAS CERRADOS QUE QUEDAN POR DETRÁS DEL TOPE, DETRÁS. El tope son los huecos,
    // no la lista: recorriendo solo esos 30 días, al que cerró un día hace dos meses y
    // ninguno desde entonces le desaparecía su único día del historial y se quedaba con un
    // mes de «Sin rellenar» y nada más. Estos van sueltos y sin rellenarles los huecos: de
    // ahí para atrás la fila de días vacíos no cuenta nada que se pueda leer.
    for (const dia of [...porDia.keys()].filter(d => d < desde).sort().reverse()) {
        filas.push({ tipo: 'dia', dia, cierre: porDia.get(dia) });
    }
    return filas;
};

// «Mar 18 · Mié 19 · Jue 20 · Sin rellenar», o «Mié 19 · Sin rellenar» si es uno solo.
//
// UN TRAMO LARGO SE DICE POR SUS EXTREMOS. El doc enseña tres días y tres caben; el que
// lleva un mes sin cerrar tiene 30, y 30 «Lun 3 · Mar 4 · Mié 5...» son cuatro renglones
// de nombres de día que no dicen nada que no diga «del 26 de julio al 23 de agosto».
const TRAMO_QUE_TODAVIA_SE_LEE = 5;
const _delDiaAlDia = (dias) => {
    const orden = [...dias].sort();
    const dm = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('es-ES', { day: 'numeric', month: 'long' });
    return `Del ${dm(orden[0])} al ${dm(orden[orden.length - 1])}`;
};

const HuecoDelHistorial = ({ dias }) => (
    <li className="rounded-xl border border-dashed border-border px-3 py-2.5 flex items-center justify-between gap-3"
        data-testid="historial-hueco">
        <span className="text-sm text-foreground/40">
            {/* De más antiguo a más nuevo dentro del tramo: se lee como pasó. */}
            {dias.length > TRAMO_QUE_TODAVIA_SE_LEE
                ? _delDiaAlDia(dias)
                : [...dias].reverse().map(diaCorto).join(' · ')}
        </span>
        <span className="text-xs text-foreground/30 flex-shrink-0">Sin rellenar</span>
    </li>
);

const DiaDelHistorial = ({ dia, cierre, abierto, onAbrir }) => {
    const filas = detalleDelDia(cierre);
    const renglones = renglonesDelCierre(cierre);
    return (
        <li className="rounded-xl border border-border bg-muted" data-testid="historial-dia">
            <button type="button" onClick={onAbrir} data-testid={`historial-dia-${dia}`}
                className="w-full flex items-start gap-2 px-3 py-2.5 text-left">
                <span className="text-sm font-semibold text-foreground flex-shrink-0">{diaCorto(dia)}</span>
                {/* QUE ENVUELVA, NO QUE SE CORTE: en el móvil las cuatro cosas de la línea
                    no caben de una tirada, y cortando por el final se perdían justo el
                    peso y la dieta, que es lo que se viene a mirar bajando el dedo. */}
                <span className="text-sm text-foreground/60 min-w-0">
                    {lineaDelDia(cierre).map(t => ` · ${t}`).join('')}
                </span>
                <ChevronDown className={`w-4 h-4 text-foreground/40 ml-auto flex-shrink-0 transition-transform ${abierto ? 'rotate-180' : ''}`} />
            </button>
            {/* El detalle se abre DEBAJO, no encima: en el móvil, abriéndose encima se
                pierde el sitio en el que estaba. */}
            {abierto && (
                <div className="px-3 pb-3 pt-1 border-t border-border" data-testid="historial-detalle">
                    <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1">
                        {filas.map(f => (
                            <React.Fragment key={f.nombre}>
                                <dt className="text-xs text-foreground/40">{f.nombre}</dt>
                                <dd className="text-xs text-foreground/80">{f.valor}</dd>
                            </React.Fragment>
                        ))}
                    </dl>
                    {renglones.map(r => (
                        <p key={r.titulo}
                            className="text-sm text-foreground/60 mt-2 whitespace-pre-line border-l-2 border-border pl-3">
                            <span className="text-[10px] uppercase tracking-wider font-bold text-foreground/40 mr-2">{r.titulo}</span>
                            {r.texto}
                        </p>
                    ))}
                    {cierre.trainer_feedback && (
                        <div className="mt-2 p-2 bg-brand/10 border border-brand/20 rounded-lg text-sm text-foreground/80">
                            <span className="text-[10px] uppercase tracking-wider text-brand font-bold mr-2">Entrenador:</span>
                            {cierre.trainer_feedback}
                        </div>
                    )}
                </div>
            )}
        </li>
    );
};

/**
 * «Tus días»: la lista de días del punto 19, con sus huecos y su detalle.
 *
 * Se exporta a propósito. El punto 23 pide que el historial viva en UN SOLO SITIO,
 * Seguimiento -> Diario, y ese traslado toca `components/Diario.jsx` y `ReportsPage.jsx`,
 * que no son de este trabajo. Cuando se haga, se importa esto y no se vuelve a escribir.
 */
export const HistorialDeDias = ({ cierres, hoyIso }) => {
    const [abierto, setAbierto] = useState(null);
    const filas = useMemo(() => diasDelHistorial(cierres, hoyIso), [cierres, hoyIso]);
    if (filas.length === 0) return null;
    return (
        <ul className="space-y-2">
            {filas.map(f => (f.tipo === 'hueco'
                ? <HuecoDelHistorial key={`hueco-${f.dias[0]}`} dias={f.dias} />
                : <DiaDelHistorial key={f.dia} dia={f.dia} cierre={f.cierre}
                    abierto={abierto === f.dia}
                    onAbrir={() => setAbierto(a => (a === f.dia ? null : f.dia))} />
            ))}
        </ul>
    );
};

// ── El cierre del día (T4 del doc 16-08, rehecho con el doc 24-08) ───────────
//
// ONCE PREGUNTAS, una por tarjeta, y una sola encendida cada vez. El orden lo manda el
// doc del 24: sensaciones, entreno (y cómo fue), cardio, movimiento, suplementos, extras,
// descanso, energía, hambre, notas y peso.
//
// Lo condicional lo sigue decidiendo el servidor (`GET /checkins/hoy`): la pantalla pinta
// lo que le digan y no vuelve a calcular por su cuenta si le tocan suplementos o qué
// comidas se dejó sin registrar.

// Las escalas de 1 a 5, cada una con sus extremos escritos. El título va en la tarjeta,
// así que aquí es opcional: dentro de una tarjeta escribirlo dos veces sobra.
const Escala = ({ titulo, subtitulo, minLabel, maxLabel, value, onChange, testId }) => (
    <div>
        {titulo && <span className="text-sm text-foreground/70 block">{titulo}</span>}
        {subtitulo && <p className="text-[11px] text-foreground/40 mt-0.5">{subtitulo}</p>}
        <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map(v => (
                <button key={v} type="button" onClick={() => onChange(v)} data-testid={`${testId}-${v}`}
                    className={`flex-1 py-3 rounded-xl border font-bold text-sm transition-all ${value === v
                        ? 'border-brand bg-brand/10 text-brand'
                        : 'border-border bg-muted text-foreground/50 hover:border-white/30'}`}>
                    {v}
                </button>
            ))}
        </div>
        <div className="flex justify-between mt-1.5">
            <span className="text-[11px] text-foreground/40">{minLabel}</span>
            <span className="text-[11px] text-foreground/40">{maxLabel}</span>
        </div>
    </div>
);

// Los grupos de botones (entreno, suplementos, movimiento).
const Opciones = ({ opciones, value, onChange, testId, columnas = 3 }) => (
    <div className={`grid gap-2 ${columnas === 2 ? 'grid-cols-2' : 'grid-cols-3'}`}>
        {opciones.map(o => (
            <button key={o.v} type="button" onClick={() => onChange(o.v)}
                data-testid={`${testId}-${o.v}`}
                className={`py-3 px-2 rounded-xl border font-bold text-sm transition-all ${value === o.v
                    ? 'border-brand bg-brand/10 text-brand'
                    : 'border-border bg-muted text-foreground/50 hover:border-white/30'}`}>
                {o.l}
            </button>
        ))}
    </div>
);

// ── LA REGLA DEL COLOR (puntos 13, 14 y 18 del doc 24-08) ────────────────────
//
// «La tarjeta naranja significa "esto es lo que toca ahora". Sólo una encendida a la vez;
// en cuanto se contesta, se apaga y se enciende la siguiente.» Y al contestar, DOS
// señales y no una: «el tono dice por dónde vas; el tick dice lo que ya está hecho».
//
// Con eso no hace falta ni barra de progreso ni contador: el color dice por dónde va.
// Y al reabrir el cierre para corregirlo, todo sale contestado y en oscuro; tocando una
// respuesta se vuelve a encender esa tarjeta (`onAbrir`).
//
// `cola` es lo que cuelga de una respuesta y sigue haciendo falta con la tarjeta ya
// apagada: el «¿cuál y por qué?» de los suplementos y el campo de los extras. Se pinta
// abajo, encendida o no; si se escondiera al apagarse, contestar «No todos» haría
// desaparecer la caja donde tenía que escribir cuál.
const Tarjeta = ({ titulo, ayuda, ayudaCursiva = false, encendida, contestada,
                  resumen, onAbrir, cola, testId, children }) => (
    // Y SIN EL NARANJA, que era del acordeón. Marcaba «esta es la que toca» cuando sólo
    // había una abierta; con las ocho a la vista no distingue nada, y en esta app el
    // naranja quiere decir «algo que corregir» (la regla del punto 76). Ocho tarjetas
    // naranjas se leen como ocho errores. Lo que dice si está contestada es el tic, y lo
    // que dice qué falta es el pie.
    <div data-testid={testId} data-encendida={encendida ? '1' : '0'}
        className="rounded-2xl border border-border bg-card p-4 transition-colors">
        {/* TODAS ABIERTAS, SIN PLEGAR NADA («El día», 31-08). `encendida` llega siempre a
            true desde que la pantalla dejó de ser un acordeón; la rama de abajo -- la
            tarjeta cerrada con su resumen -- se queda escrita porque el mismo componente
            lo usan el semanal y el mensual, que sí pliegan. Si un día vuelve el acordeón
            del cierre, está aquí. */}
        {encendida ? (
            <div className="flex items-start gap-2">
                {contestada && (
                    <CheckCircle2 className="w-4 h-4 text-brand flex-shrink-0 mt-0.5"
                        data-testid={`${testId}-tick`} />
                )}
                <div className="min-w-0 flex-1">
                    <span className="text-sm block text-foreground font-semibold">{titulo}</span>
                    {ayuda && (
                        <p className={`text-[11px] text-foreground/40 mt-0.5 ${ayudaCursiva ? 'italic' : ''}`}>
                            {ayuda}
                        </p>
                    )}
                    <div className="mt-2">{children}</div>
                </div>
            </div>
        ) : (
            // Apagada, y entera pulsable: «al tocar una respuesta, vuelve a encenderse esa
            // tarjeta» (punto 18). Con la que aún no ha contestado vale igual, para poder
            // adelantarse sin tener que contestar por orden.
            <button type="button" onClick={onAbrir} data-testid={`${testId}-abrir`}
                className="w-full flex items-start gap-2 text-left">
                {contestada && (
                    <CheckCircle2 className="w-4 h-4 text-brand flex-shrink-0 mt-0.5"
                        data-testid={`${testId}-tick`} />
                )}
                <div className="min-w-0 flex-1">
                    <span className="text-sm block text-foreground/50">{titulo}</span>
                    {/* «Con su respuesta marcada debajo.» */}
                    {contestada && (
                        <span className="text-sm text-foreground/80 block mt-0.5"
                            data-testid={`${testId}-resumen`}>{resumen}</span>
                    )}
                </div>
            </button>
        )}
        {cola && <div className="mt-2">{cola}</div>}
    </div>
);

// Aquí vivía `diasParaPesarse`, los días entre los que se puede fechar un pesaje. Se fue
// con la casilla del peso a `components/CampoDePeso.jsx` (bloque 4 del 1-09), entera y con
// su regla: el número lo sigue diciendo el servidor -- fallo 7 del repaso del 24-08, tres
// sitios y tres números para la misma decisión --, ahora en `GET /reports/evolution`.

// Los valores viejos de `entreno_respuesta` se leen con la pregunta nueva: el que
// contestó «Sí, pero no lo puse» dijo que sí entrenó, y el que contestó «No entrené»
// dijo que no. Sin esto, al reabrir un cierre de ayer la pregunta salía en blanco.
const ENTRENO_DE_VUELTA = { si_no_lo_puse: 'si', no_entrene: 'no' };

// `inicial` es el cierre ya guardado hoy cuando se entra a EDITARLO (P75, doc 23-08): el
// formulario arranca con lo que puso, lo toca y al guardar SUSTITUYE al de antes. Sin
// `inicial` es el cierre en blanco de siempre.
//
// AQUÍ VIVÍA EL «CIERRE CORTO», el que al que ya había marcado todas sus comidas le
// escondía las preguntas condicionales, las notas y el peso. Se va con el doc 24-08: las
// once preguntas salen a todos, todos los días, y lo de las comidas no es una pregunta
// sino el aviso de arriba («la app ya sabe la respuesta»). Con eso se caen también las
// dos reglas que lo parcheaban, `verNotas` y `verPeso`: si nada se esconde, nada se
// puede perder al reeditar.
const CierreDelDia = ({ api, hoy, dia, onGuardado, inicial = null }) => {
    const navigate = useNavigate();
    const [enviando, setEnviando] = useState(false);
    const [f, setF] = useState(() => ({
        sensaciones: inicial?.sensaciones ?? null,
        entreno_respuesta: inicial?.entreno_respuesta
            ? (ENTRENO_DE_VUELTA[inicial.entreno_respuesta] || inicial.entreno_respuesta)
            : null,
        entreno_estrellas: inicial?.entreno_estrellas ?? null,
        cardio: inicial?.cardio ?? null,
        movimiento: inicial?.movimiento ?? null,
        suplementos: inicial?.suplementos?.respuesta ?? null,
        suplementos_detalle: inicial?.suplementos?.detalle || '',
        extras_respuesta: inicial?.extras_respuesta ?? null,
        descanso: inicial?.descanso ?? null,
        energy: inicial?.energy ?? null,
        hunger_anxiety: inicial?.hunger_anxiety ?? null,
        notas: inicial?.notas?.texto || '',
        compartida: inicial?.notas?.compartida ?? false,
    }));
    const set = (campo, valor) => setF(prev => ({ ...prev, [campo]: valor }));
    // Antes esto además apagaba la tarjeta y encendía la siguiente. Con todas a la vista
    // («El día», 31-08), contestar solo guarda el valor.
    const responder = (campo, valor) => set(campo, valor);

    // EL DÍA DE LA DIETA QUE SE ESTABA COMIENDO (punto 32). El cierre de las 23:50 tiene
    // que caer en el día de hoy y no en el de mañana, y el extra que se apunte desde aquí
    // tiene que ir a la lista de ESE día: los dos usan la misma fecha, la que dice el
    // servidor, y si no llegó, la del reloj del cliente.
    const fechaDelDia = hoy?.fecha || todayKey();

    // La fecha del pesaje se pregunta ahora donde se escribe el peso, en Evolución
    // (`CampoDePeso`), con la misma regla y el mismo número de días del servidor.

    // ── Los extras del día (puntos 07 y 32) ──────────────────────────────────
    // Una sola lista: la del día. Lo que escriba aquí es un `POST /diets/{fecha}/extras`,
    // el mismo que usa el campo del Inicio, para que no haya que ir a buscar los extras a
    // dos sitios.
    const [extras, setExtras] = useState(() => dia?.extras || []);
    const [textoExtra, setTextoExtra] = useState('');
    const [apuntando, setApuntando] = useState(false);

    const apuntarExtra = async () => {
        const texto = textoExtra.trim();
        if (!texto) return;
        setApuntando(true);
        try {
            const { data } = await api.post(`/diets/${fechaDelDia}/extras`,
                { texto, origen: 'checkin' });
            setExtras(prev => [...prev, data?.extra || { id: `${Date.now()}`, texto }]);
            setTextoExtra('');
        } catch (err) {
            console.error('No se pudo apuntar el extra desde el cierre del día:', err?.response?.data || err);
            toast.error('No hemos podido apuntarlo. Inténtalo en un momento.');
        } finally {
            setApuntando(false);
        }
    };

    // ── Las nueve preguntas de la cadena ─────────────────────────────────────
    //
    // Las notas y el peso NO entran aquí a propósito: son opcionales por diseño, así que
    // nunca se pueden dar por contestadas, y una tarjeta que no se puede contestar dejaría
    // el naranja clavado en ella para siempre. Van abiertas al final, como en el
    // maquetado.
    // FUERA «SENSACIONES GENERALES DEL DÍA» («El día», 31-08). Era la primera y ya no está
    // en la lista del documento. Se va de la PANTALLA, no de la base: el campo se sigue
    // guardando vacío y el historial de quien ya lo tenga contestado lo sigue pintando con
    // sus estrellitas. Borrarlo del modelo dejaría meses de días sin poder enseñarse.
    const preguntas = [
        {
            id: 'entreno', testId: 'cierre-entreno', visible: true,
            titulo: '¿Entrenaste hoy?',
            // No se da por contestada con el «Sí» a secas: «¿Cómo fue?» cuelga de él y es
            // una pregunta más de las once.
            hecha: f.entreno_respuesta != null
                && (f.entreno_respuesta !== 'si' || f.entreno_estrellas != null),
            resumen: [ENTRENO_VALOR[f.entreno_respuesta],
                      f.entreno_estrellas != null ? estrellitas(f.entreno_estrellas) : null]
                .filter(Boolean).join(' · '),
            campo: (
                <>
                    <Opciones testId="cierre-entreno-op" value={f.entreno_respuesta}
                        onChange={v => {
                            set('entreno_respuesta', v);
                            // Cambiar de idea limpia lo que colgaba del «Sí».
                            if (v !== 'si') set('entreno_estrellas', null);
                        }}
                        opciones={[{ v: 'si', l: 'Sí' }, { v: 'no', l: 'No' },
                                   { v: 'descanso', l: 'Descanso' }]} />
                    {/* SANGRADA Y COLGANDO DEL «SÍ», como lo pide el doc (punto 03). */}
                    {f.entreno_respuesta === 'si' && (
                        <div className="mt-3 pl-3 border-l-2 border-brand/40" data-testid="cierre-entreno-como-fue">
                            <span className="text-sm text-foreground/70 block">¿Cómo fue?</span>
                            <div className="mt-1">
                                <Estrellas testid="cierre-entreno-estrellas" valor={f.entreno_estrellas}
                                    onChange={v => responder('entreno_estrellas', v)} />
                            </div>
                            {/* AQUÍ NO VA UNA SEGUNDA CAJA DE NOTAS. Se probó a colgar del
                                «Sí» un «Qué entrenaste hoy» y se quitó: el punto 11 dice
                                «UNA SOLA CAJA, con la pista de qué poner», y la pista que
                                da es justamente «Cosas que quieras acordarte del entreno y
                                de la dieta». Con las dos, el que lleva rutina acababa
                                apuntando lo mismo en dos sitios, y el rótulo de la de
                                arriba no era de Jesús: era inventado. Lo que ya haya
                                escrito en `entreno_nota` no se toca, viaja tal cual. */}
                        </div>
                    )}
                </>
            ),
        },
        {
            id: 'cardio', testId: 'cierre-cardio', visible: true,
            titulo: '¿Hiciste cardio?',
            hecha: f.cardio != null,
            resumen: CARDIO_VALOR[f.cardio],
            campo: <Opciones testId="cierre-cardio-op" value={f.cardio}
                onChange={v => responder('cardio', v)}
                opciones={[{ v: 'si', l: 'Sí' }, { v: 'no', l: 'No' },
                           { v: 'no_tocaba', l: 'No tocaba' }]} />,
        },
        {
            id: 'movimiento', testId: 'cierre-movimiento-card', visible: true,
            titulo: '¿Te moviste lo suficiente?',
            // En cursiva y sin punto final, tal cual lo pide el doc.
            ayuda: 'Moverte es salud y menos grasa: a más te muevas, más gastas',
            ayudaCursiva: true,
            hecha: f.movimiento != null,
            resumen: MOVIMIENTO_VALOR[f.movimiento],
            // Etiquetas cortas: los tres botones van en fila y en el móvil tres frases no
            // caben -- se partían en tres renglones dentro del botón. Los valores
            // guardados (menos/igual/mas) son los de siempre.
            campo: <Opciones testId="cierre-movimiento" value={f.movimiento}
                onChange={v => responder('movimiento', v)}
                opciones={[{ v: 'menos', l: 'Menos' }, { v: 'igual', l: 'Como siempre' },
                           { v: 'mas', l: 'Más' }]} />,
        },
        {
            id: 'suplementos', testId: 'cierre-suplementos',
            // A TODO EL MUNDO («El día», 31-08). Hasta hoy era condicional: el servidor
            // miraba dos cosas -- que su plan incluyera suplementación y que tuviera
            // protocolo vigente ese día -- y solo entonces salía. El documento la lista
            // entre las nueve sin condición ninguna, y Francisco cerró que manda el
            // documento.
            //
            // Queda dicho lo que se lleva por delante, porque el candado no era un capricho
            // (punto 06 del 24-08): había cuatro clientes activos con protocolo de su etapa
            // anterior y un plan que ya no incluye suplementación, y el cierre les
            // preguntaba cada noche por unos suplementos que su propia pantalla no les deja
            // ni ver. Con la pregunta para todos, ese caso vuelve. `hoy.suplementos` sigue
            // llegando del servidor por si un día hay que volver a mirarlo.
            visible: true,
            titulo: '¿Tomaste la suplementación que tenías pautada?',
            hecha: f.suplementos != null,
            resumen: SUPLES_VALOR[f.suplementos],
            campo: <Opciones testId="cierre-suplementos-op" value={f.suplementos}
                onChange={v => responder('suplementos', v)}
                opciones={[{ v: 'si', l: 'Sí' }, { v: 'no_todos', l: 'No toda' },
                           { v: 'no', l: 'No' }]} />,
            cola: f.suplementos === 'no_todos' ? (
                <input value={f.suplementos_detalle} onChange={e => set('suplementos_detalle', e.target.value)}
                    data-testid="cierre-suplementos-detalle"
                    placeholder="¿Cuál y por qué?" className={inputCls} />
            ) : null,
        },
        {
            id: 'extras', testId: 'cierre-extras', visible: true,
            titulo: '¿Se te ha escapado algo más hoy?',
            // «El día», 31-08. Decía «Algo que comieras de más y no pusieras en el apartado
            // "extras"», que describe; esta pide.
            ayuda: 'Si no lo pusiste en el apartado de extras, ponlo ahora',
            hecha: f.extras_respuesta != null,
            resumen: f.extras_respuesta === 'si' ? 'Sí' : 'No',
            campo: <Opciones columnas={2} testId="cierre-extras-op" value={f.extras_respuesta}
                onChange={v => responder('extras_respuesta', v)}
                opciones={[{ v: 'no', l: 'No' }, { v: 'si', l: 'Sí → apúntalo' }]} />,
            cola: f.extras_respuesta === 'si' ? (
                <div data-testid="cierre-extras-campo">
                    {/* Lo apuntado se queda listado encima del campo, como en el Inicio. */}
                    {extras.length > 0 && (
                        <ul className="mb-2 space-y-1">
                            {extras.map(e => (
                                <li key={e.id} className="text-sm text-foreground/70">
                                    · {e.texto || e.nombre}{e.cantidad_texto ? ` · ${e.cantidad_texto}` : ''}
                                </li>
                            ))}
                        </ul>
                    )}
                    <textarea rows={2} value={textoExtra} onChange={e => setTextoExtra(e.target.value)}
                        data-testid="cierre-extras-texto"
                        placeholder="Con la cantidad aproximada a ojo si no lo pesas, pero ponlo todo."
                        className={inputCls + ' resize-none'} />
                    <button type="button" onClick={apuntarExtra} disabled={apuntando || !textoExtra.trim()}
                        data-testid="cierre-extras-apuntar"
                        className="mt-2 px-3 py-2 rounded-xl border border-border text-sm font-semibold text-foreground/70 hover:text-foreground hover:bg-muted disabled:opacity-50">
                        {apuntando ? 'Apuntando...' : 'Apuntarlo'}
                    </button>
                </div>
            ) : null,
        },
        {
            id: 'descanso', testId: 'cierre-descanso-card', visible: true,
            // El descanso se pregunta aquí, referido a la noche de ayer, y sale del
            // reporte del mes: así son 28 datos al mes en vez de uno.
            titulo: '¿Cómo descansaste la noche de ayer?',
            ayuda: 'Fundamental tener una buena rutina de sueño si no la tienes ya',
            hecha: f.descanso != null,
            resumen: f.descanso != null ? `${f.descanso} de 5` : '',
            campo: <Escala minLabel="fatal" maxLabel="genial" testId="cierre-descanso"
                value={f.descanso} onChange={v => responder('descanso', v)} />,
        },
        {
            id: 'energia', testId: 'cierre-energia-card', visible: true,
            titulo: 'Niveles de energía durante el día',
            // «Fuera de tu entrenamiento»: sin eso el que acaba de entrenar contesta por
            // cómo se encontró en el gimnasio, que no es lo que se le pregunta.
            ayuda: 'Fuera de tu entrenamiento, en tu día normal',
            hecha: f.energy != null,
            resumen: f.energy != null ? `${f.energy} de 5` : '',
            campo: <Escala minLabel="bajita" maxLabel="pletórico" testId="cierre-energia"
                value={f.energy} onChange={v => responder('energy', v)} />,
        },
        {
            id: 'hambre', testId: 'cierre-hambre-card', visible: true,
            // Hambre y ansiedad, juntas: es como lo dice él y es una sola escala. Y «con
            // la dieta», que es de lo que se pregunta y no de la ansiedad de la vida.
            titulo: 'Hambre / ansiedad con la dieta',
            hecha: f.hunger_anxiety != null,
            resumen: f.hunger_anxiety != null ? `${f.hunger_anxiety} de 5` : '',
            campo: <Escala minLabel="nada" maxLabel="mucha" testId="cierre-hambre"
                value={f.hunger_anxiety} onChange={v => responder('hunger_anxiety', v)} />,
        },
    ].filter(p => p.visible);

    // TODAS A LA VISTA («El día», 31-08). Hasta hoy iba una encendida cada vez: se
    // contestaba una, se plegaba con su resumen y se abría sola la siguiente. El documento
    // pide lo contrario -- «todas a la vista, sin plegar nada: nueve preguntas y las notas»
    // --, así que la cadena se cae y con ella el `abierta`.
    //
    // Lo que hacía esa cadena era decir por dónde iba; ahora eso lo dice el pie («Te queda
    // por contestar»), que por eso pasa a enseñarlas TODAS y no las tres primeras.
    const pendientes = preguntas.filter(p => !p.hecha);

    // ── El Guardar, apagado hasta el final (punto 15) ────────────────────────
    //
    // Cuenta lo que se le PREGUNTA a este cliente hoy, ni una cosa más: las notas y el
    // peso son opcionales por diseño, y la de los suplementos no le sale a todo el mundo.
    // Y se dice qué falta: un Guardar apagado sin decir por qué es peor que uno encendido.
    const faltan = pendientes.map(p => p.titulo);

    // Las comidas que no registró, ARRIBA DEL TODO y antes de la primera pregunta (punto
    // 16). No es una pregunta, es un aviso: la app ya sabe la respuesta y se le enseña
    // antes de empezar por si aún está a tiempo de corregirlo. Con esto se va la casilla
    // «La hice» de abajo, que preguntaba lo mismo de una sola comida.
    const sinRegistrar = hoy?.comidas_pendientes || [];
    // Aquí vivía `hayDietaMontada`, que decidía si el hueco de arriba decía «Dieta
    // registrada». Con «El día, todo bien» ya no hace falta: ver el aviso más abajo.

    const guardar = async () => {
        if (faltan.length > 0) return;

        setEnviando(true);
        try {
            await api.post('/checkins', {
                type: 'daily',
                fecha: fechaDelDia,
                sensaciones: f.sensaciones,
                entreno_respuesta: f.entreno_respuesta,
                entreno_estrellas: f.entreno_respuesta === 'si' ? f.entreno_estrellas : null,
                cardio: f.cardio,
                movimiento: f.movimiento,
                descanso: f.descanso, energy: f.energy, hunger_anxiety: f.hunger_anxiety,
                suplementos: f.suplementos
                    ? { respuesta: f.suplementos, detalle: f.suplementos_detalle.trim() || null }
                    : null,
                // La respuesta se guarda aquí; lo que escribió ya está en la lista de
                // extras del día, que es la única que hay.
                extras_respuesta: f.extras_respuesta,
                // LO QUE YA NO SE PREGUNTA, NO SE BORRA. El guardado sustituye la fila
                // entera, así que un null a pelo se llevaría por delante lo que contestó
                // antes de este rediseño (el «La hice» de la comida pendiente y la nota
                // del exceso de macros). Viaja tal cual estaba.
                //
                // ESTA LISTA YA NO ES LA QUE SOSTIENE EL ARREGLO (fallo 9 del 24-08). Ir
                // campo a campo obligaba a acordarse, y se olvidaron dos: `comido_hoy` y
                // `mood` desaparecían al reeditar. Desde el 24-08 el servidor conserva
                // TODO lo que esta pantalla no manda (routes/checkins.py, el bucle de
                // `_LO_QUE_PONE_EL_SERVIDOR`), así que un campo nuevo ya no hay que
                // añadirlo aquí. Estas cuatro líneas se quedan porque no estorban y dejan
                // a la vista lo que el formulario sabe que existe y no pregunta.
                cena_hecha: inicial?.cena_hecha ?? null,
                comida_pendiente: inicial?.comida_pendiente ?? null,
                exceso_nota: inicial?.exceso_nota || null,
                // Y la nota de entreno de los cierres de antes: la caja ya no está, pero
                // borrarla al reeditar sería tirar lo que escribió.
                entreno_nota: inicial?.entreno_nota || null,
                notas: f.notas.trim() ? { texto: f.notas.trim(), compartida: f.compartida } : null,
                // El peso ya no viaja desde aquí: se escribe en Evolución (ver arriba). El
                // que ya tuviera guardado un cierre se queda donde está, porque el servidor
                // conserva lo que esta pantalla no manda.
            });
            toast.success('Anotado. Mañana seguimos.');
            onGuardado();
        } catch (err) {
            console.error('No se pudo guardar el cierre del día:', err?.response?.data || err);
            toast.error('No hemos podido guardar tu día. Inténtalo en un momento.');
        } finally {
            setEnviando(false);
        }
    };

    return (
        <div className="space-y-3" data-testid="cierre-del-dia">
            {/* SU DIETA DE HOY, ANTES DE LA PRIMERA PREGUNTA (punto 16). */}
            {sinRegistrar.length > 0 ? (
                <div className="rounded-2xl border border-border bg-muted p-4" data-testid="cierre-dieta-aviso">
                    <p className="text-sm font-bold text-foreground">
                        {sinRegistrar.length === 1
                            ? 'Te queda 1 comida sin registrar'
                            : `Te quedan ${sinRegistrar.length} comidas sin registrar`}
                    </p>
                    <p className="text-sm text-foreground/60 mt-0.5">
                        {sinRegistrar.map(c => c.etiqueta).join(' · ')}
                    </p>
                    <button type="button" onClick={() => navigate('/dashboard/nutrition')}
                        data-testid="cierre-dieta-ir"
                        className="text-[11px] text-brand hover:underline underline-offset-4 mt-0.5">
                        Puedes cerrarlas antes de seguir
                    </button>
                </div>
            ) : (
                /* «EL DÍA, TODO BIEN» («El día», 31-08). Antes este hueco decía «Dieta
                   registrada» y sólo salía si había dieta montada; si el cliente no había
                   montado nada, se quedaba vacío y la pantalla empezaba en seco.
                   El documento pide el mismo hueco en verde, y con dos renglones. Y el
                   candado de `hayDietaMontada` se cae porque lo que se afirma ha cambiado:
                   «no te queda nada por registrar» es verdad no haya comidas pendientes,
                   haya montado dieta o no. Decir «dieta registrada» al que sólo apuntó dos
                   cañas sí habría sido mentira; esto no. */
                <div className="rounded-2xl border border-border bg-muted p-4 flex items-start gap-2"
                    data-testid="cierre-dieta-aviso">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                    <div>
                        <p className="text-sm font-bold text-foreground">El día, todo bien</p>
                        <p className="text-sm text-foreground/60 mt-0.5">No te queda nada por registrar</p>
                    </div>
                </div>
            )}

            {preguntas.map(p => (
                <Tarjeta key={p.id} testId={p.testId} titulo={p.titulo} ayuda={p.ayuda}
                    ayudaCursiva={p.ayudaCursiva} encendida
                    contestada={p.hecha} resumen={p.resumen} cola={p.cola}>
                    {p.campo}
                </Tarjeta>
            ))}

            {/* Las notas y el peso, abiertos y al final: son opcionales y no entran en la
                cadena del naranja. */}
            <div className="rounded-2xl border border-border bg-card p-4">
                <span className="text-sm text-foreground block">Notas personales</span>
                <p className="text-[11px] text-foreground/40 mt-0.5 mb-2">
                    Esto es para tu diario. Lo puedes compartir con nosotros o quedártelo para ti
                </p>
                <textarea rows={3} value={f.notas} onChange={e => set('notas', e.target.value)}
                    data-testid="cierre-notas"
                    placeholder="Cosas que quieras acordarte del entreno y de la dieta"
                    className={inputCls + ' resize-none'} />
                <label className="flex items-center gap-3 cursor-pointer mt-2">
                    <input type="checkbox" checked={f.compartida} data-testid="cierre-compartir"
                        onChange={e => set('compartida', e.target.checked)}
                        className="w-4 h-4 accent-[#FF671F]" />
                    <span className="text-sm text-foreground/80">Compartir con nosotros</span>
                </label>
            </div>

            {/* AQUÍ VIVÍA LA CASILLA DEL PESO, y se va a Evolución («Todo lo validado antes
                del 1 de septiembre», bloque 4: «El peso. Un solo registro, tres puertas» /
                «abierto todo el año» / «es el único sitio donde el peso se escribe»).

                Estaba al final de once preguntas, dentro de un formulario que solo abre
                quien cierra el día: el que no lo cierra -- la mayoría -- no tenía dónde
                apuntar un pesaje, y el que lo apuntaba lo dejaba enterrado donde no vuelve.
                Ahora el campo está siempre abierto en Evolución, que es de donde sale su
                curva, y hasta allí llevan las otras dos puertas: la fila «Hoy toca pesarte»
                de Inicio los días de pesada y el paso 1 del reporte quincenal.

                LO YA GUARDADO NO SE TOCA: los cierres viejos siguen con su peso -- se cayó
                `weight` de `_LO_QUE_PREGUNTA_EL_CIERRE` para que reeditarlos no lo borre --
                y el historial de esta misma pantalla lo sigue pintando. */}

            {faltan.length > 0 && (
                // Las tres primeras y cuántas más: la lista entera son ocho renglones al
                // empezar, y al final -- que es cuando el cliente mira el botón -- quedan
                // una o dos. Lo que hace falta es que sepa qué le falta, no leerse la
                // pantalla otra vez.
                // LAS OCHO ENTERAS, SIN «Y N MÁS» («El día», 31-08). Cortaba en tres porque
                // con el acordeón la pantalla ya decía por dónde ibas; ahora que están todas
                // abiertas, esta línea es lo único que lo dice, y decir «y 5 más» obliga a
                // releerse la pantalla para saber cuáles.
                <p className="text-[11px] text-foreground/40" data-testid="cierre-que-falta">
                    Te queda por contestar: {faltan.join(' · ')}
                </p>
            )}
            <button onClick={guardar} disabled={enviando || faltan.length > 0} data-testid="cierre-guardar"
                className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed">
                {enviando && <Loader2 className="w-4 h-4 animate-spin" />} Guardar
            </button>
        </div>
    );
};

// AQUI VIVIAN LAS FOTOS DE PROGRESO (`PhotoThumb` y `PhotosSection`), la rejilla por
// meses y la subida de la primera foto. FUERA del cierre del dia (punto 17 del doc
// 24-08): «Debajo del Guardar: Anotado. Manana seguimos, Editar lo de hoy, Ver mi
// diario. Y nada mas». Jesus lo senala ademas en el punto 53: «el check-in se ha
// llenado de cosas que no pedi: una galeria entera de fotos de progreso, con la cara».
// Las fotos se ven en Seguimiento -> Evolucion, y se suben con TresFotos, que vive en
// ReportsPage.

const CheckInsPage = () => {
    const { api, pantalla } = useAuth();
    // El cierre del día nuevo, detrás de su interruptor del panel (T4). Con él apagado se
    // queda el check-in diario de siempre, que es lo que hay hoy en producción.
    const cierreNuevo = pantalla('t4_cierre_nuevo');
    const [hoy, setHoy] = useState(null);
    // El día de la dieta de hoy: de él sale la lista de extras ya apuntados. `listo` evita
    // el parpadeo del formulario. (El aviso de arriba ya no lo mira: desde el 31-08 dice
    // «El día, todo bien» y le basta con las comidas pendientes.)
    const [diaHoy, setDiaHoy] = useState({ dia: null, listo: false });
    const navigate = useNavigate();
    // EL DÍA QUE SE ESTÁ CERRANDO. Normalmente el de hoy; con `?fecha=` el de ayer, que es
    // la ventana de la mañana (doc «El día», 31-08). Se acepta un día atrás y nada más: el
    // servidor lo vuelve a validar, pero una pantalla que se cree cualquier fecha de la URL
    // enseñaría un día que no se puede cerrar.
    const [parametros] = useSearchParams();
    const elDiaQueSeCierra = (() => {
        const pedido = parametros.get('fecha');
        if (!pedido || !/^\d{4}-\d{2}-\d{2}$/.test(pedido)) return todayKey();
        const dias = Math.round((new Date(`${todayKey()}T12:00:00`) - new Date(`${pedido}T12:00:00`)) / 86400000);
        return dias === 1 ? pedido : todayKey();
    })();
    const [checkins, setCheckins] = useState([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    // Reabrir el cierre de hoy para corregirlo (P75, doc 23-08): con esto encendido el
    // formulario vuelve, precargado con lo guardado, y el guardado sustituye al de antes.
    const [editando, setEditando] = useState(false);
    const enTelefono = useEsTelefono();

    const [daily, setDaily] = useState({ energy: null, hunger_anxiety: null });

    // Historial paginado: se muestran 12, "Cargar más" amplía y pide más al backend si hace falta
    const [histShown, setHistShown] = useState(12);
    const [histHasMore, setHistHasMore] = useState(false);
    const [histLoadingMore, setHistLoadingMore] = useState(false);

    const fetchAll = useCallback(async () => {
        try {
            const ciRes = await api.get('/checkins?limit=30');
            const list = Array.isArray(ciRes.data) ? ciRes.data : [];
            setCheckins(list);
            setHistHasMore(list.length === 30);
        } catch {
            toast.error('Error al cargar check-ins');
        } finally {
            setLoading(false);
        }
    }, [api]);

    // Lo que le falta hoy: lo decide el servidor (entreno, suplementos, la comida que se
    // dejó y si se ha pasado de macros). Si no llega, el cierre se enseña igual con las
    // preguntas de siempre, que es mejor que no dejarle cerrar el día.
    const fetchHoy = useCallback(async () => {
        try {
            // Con el día del cliente: el cierre pregunta por el día que ÉL está viviendo.
            //
            // Salvo que venga con fecha: es LA VENTANA DE LA MAÑANA (doc «El día», 31-08).
            // Hasta las 15:00 el de ayer sigue abierto, y la fila del Inicio trae aquí con
            // `?fecha=` para que se rellene ese y no el de hoy, que aún no ha pasado.
            const { data } = await api.get(`/checkins/hoy?fecha=${elDiaQueSeCierra}`);
            setHoy(data || null);
        } catch (err) {
            console.error('No se pudo consultar el día de hoy:', err?.response?.data || err);
            setHoy(null);
        }
    }, [api, elDiaQueSeCierra]);

    const loadMoreHistory = async () => {
        if (histShown < checkins.length) { setHistShown(s => s + 12); return; }
        if (!histHasMore) return;
        setHistLoadingMore(true);
        try {
            const res = await api.get(`/checkins?limit=30&skip=${checkins.length}`);
            const more = Array.isArray(res.data) ? res.data : [];
            setCheckins(prev => [...prev, ...more]);
            setHistHasMore(more.length === 30);
            setHistShown(s => s + 12);
        } catch { /* silencioso */ }
        finally { setHistLoadingMore(false); }
    };

    useEffect(() => { fetchAll(); }, [fetchAll]);
    useEffect(() => { if (cierreNuevo) fetchHoy(); }, [cierreNuevo, fetchHoy]);

    // La dieta de HOY, con la fecha que dice el servidor (`/checkins/hoy`), que es el
    // único que sabe qué día es en España: aquí no se saca ninguna fecha del navegador.
    // Si el día no se puede traer, el cierre sale largo, que nunca pregunta de menos.
    const fechaHoy = hoy?.fecha;
    useEffect(() => {
        if (!cierreNuevo || !fechaHoy) return;
        let cancelado = false;
        api.get(`/diets/${fechaHoy}`)
            .then(r => { if (!cancelado) setDiaHoy({ dia: r.data || null, listo: true }); })
            .catch(err => {
                console.error('No se pudo consultar la dieta de hoy:', err?.response?.data || err);
                if (!cancelado) setDiaHoy({ dia: null, listo: true });
            });
        return () => { cancelado = true; };
    }, [cierreNuevo, api, fechaHoy]);

    const todayDaily = checkins.find(c => c.type === 'daily' && isSameDay(c.created_at));

    // EL PESO YA NO SE ESCRIBE AQUÍ, así que tampoco se valida aquí. Los dos filtros del
    // #48 del 15-08 -- el rango, que rechaza, y el salto de 10 kg, que pregunta -- viajaron
    // enteros con el campo a `components/CampoDePeso.jsx`, con la misma `revisarPeso` y el
    // mismo diálogo de confirmación. Allí el peso con el que se compara sale de la serie
    // (la curva de Evolución), que es mejor referencia que la que había aquí: esto miraba
    // solo los check-in y en producción casi ningún cierre trae peso.

    const submitDaily = async () => {
        if (daily.energy == null || daily.hunger_anxiety == null) {
            return toast.error('Dinos cómo vas de energía y de hambre');
        }
        setSubmitting(true);
        try {
            await api.post('/checkins', { type: 'daily', fecha: elDiaQueSeCierra, ...daily });
            toast.success('Check-in diario enviado');
            setDaily({ energy: null, hunger_anxiety: null });
            fetchAll();
        } catch { toast.error('Error al enviar check-in'); }
        finally { setSubmitting(false); }
    };


    if (loading) {
        return (
            <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1100px] mx-auto">
                <div className="animate-pulse space-y-4">
                    <div className="h-20 bg-muted rounded-2xl" />
                    <div className="h-64 bg-muted rounded-2xl" />
                </div>
            </div>
        );
    }

    // Los dos bloques del historial. Se RECORTA ANTES de partir para que «Cargar más»
    // siga contando entradas y no bloques: la paginación es la misma de siempre.
    const visibles = checkins.slice(0, histShown);
    const cierres = visibles.filter(c => c.type === 'daily');
    const reportes = visibles.filter(c => c.type !== 'daily');
    // La píldora de tipo se va: dentro de cada bloque lo dice el título. Se queda solo en
    // «Reportes anteriores» cuando ahí conviven semanales y mensuales -- ahí el título no
    // distingue, y sin ella dos entradas de cosas distintas se leen igual.
    const mezclaDeReportes = new Set(reportes.map(c => c.type)).size > 1;

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5 animate-fade-in" data-testid="checkins-page">
            {/* LA VUELTA. En el teléfono esta pantalla ya no está en el menú: se llega desde
                la tarjeta «Hoy» de Seguimiento, así que tiene que haber una puerta de vuelta
                a mano. En escritorio no hace falta: ahí sigue en la barra lateral.
                Va con `enTelefono` y no con `lg:hidden` a propósito: oculto con CSS el nodo
                sigue en el árbol, y el `space-y-5` del contenedor le da su margen al hermano
                de al lado igualmente. Eran 21 px que aparecían en la vista de escritorio sin
                que nada se viera. */}
            {enTelefono && (
                <button onClick={() => navigate('/dashboard/reports')} data-testid="volver-a-seguimiento"
                    className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground hover:text-foreground">
                    <ChevronLeft className="w-4 h-4" /> Seguimiento
                </button>
            )}

            <header className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-brand/10">
                    <Activity className="w-6 h-6 text-brand" />
                </div>
                <div>
                    {/* Un solo nombre en los dos tamaños (T4): esto es el cierre del día y
                        se llama como lo que pregunta. «Seguimiento» era el nombre de la
                        pestaña de la que se viene, y en escritorio había DOS pantallas
                        llamadas igual. */}
                    {cierreNuevo ? (
                        <>
                            <p className="text-sm text-muted-foreground">{fechaLarga(hoy?.fecha)}</p>
                            <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none mt-1" data-testid="checkins-heading">
                                ¿Cómo fuiste hoy?
                            </h1>
                        </>
                    ) : (
                        <>
                            <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none" data-testid="checkins-heading">
                                <span className="lg:hidden">¿Cómo vas hoy?</span>
                                <span className="hidden lg:inline">Seguimiento</span>
                            </h1>
                            <p className="text-sm text-muted-foreground mt-1">
                                <span className="lg:hidden">Energía y hambre.</span>
                                <span className="hidden lg:inline">Tus check-ins diarios, semanales y mensuales</span>
                            </p>
                        </>
                    )}
                </div>
            </header>

            {/* El cierre del día */}
            {cierreNuevo ? (
                // Si ya cerró hoy lo dice el servidor, que es el único que sabe qué día es
                // en España: aquí el día se sacaba de la fecha UTC del navegador.
                hoy?.hecho && !editando ? (
                    <Card className="p-4 border-l-4 border-l-emerald-500 flex items-start gap-3" data-testid="checkins-content">
                        <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                        <div>
                            <p className="font-bold text-foreground">Anotado. Mañana seguimos.</p>
                            {/* Debajo del Guardar, estas dos y nada más (punto 17 del doc
                                24-08). Guardado no es sellado (P75, doc 23-08): el mismo
                                día se puede reabrir, corregir y volver a guardar. */}
                            <button type="button" onClick={() => setEditando(true)} data-testid="cierre-editar"
                                className="mt-1.5 block text-sm text-brand font-semibold hover:underline underline-offset-4">
                                Editar lo de hoy
                            </button>
                            <button type="button" onClick={() => navigate('/dashboard/reports?abrir=diario')}
                                data-testid="cierre-ver-diario"
                                className="mt-1 block text-sm text-brand font-semibold hover:underline underline-offset-4">
                                Ver mi diario →
                            </button>
                        </div>
                    </Card>
                ) : hoy?.fecha && !diaHoy.listo ? (
                    // Sin la dieta de hoy todavía no se sabe qué avisar arriba ni qué
                    // extras tiene apuntados: mejor un latido que un formulario que cambia
                    // de tamaño delante del cliente.
                    <div className="h-64 bg-muted rounded-2xl animate-pulse" data-testid="checkins-content" />
                ) : (
                    <div data-testid="checkins-content">
                        <CierreDelDia api={api} hoy={hoy} dia={diaHoy.dia}
                            inicial={editando ? hoy?.checkin : null}
                            onGuardado={() => { setEditando(false); fetchAll(); fetchHoy(); }} />
                    </div>
                )
            ) : todayDaily ? (
                <Card className="p-4 border-l-4 border-l-emerald-500 flex items-start gap-3" data-testid="checkins-content">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                    <div>
                        <p className="font-bold text-foreground">Check-in de hoy hecho</p>
                        <p className="text-sm text-foreground/60 mt-0.5">
                            Energía {todayDaily.energy}/5
                            {todayDaily.hunger_anxiety != null && ` · Hambre ${todayDaily.hunger_anxiety}/5`}
                            {/* La dieta la rellena el sistema con lo registrado, no él. */}
                            {todayDaily.nutrition_followed != null && (todayDaily.nutrition_followed ? ' · Dieta registrada' : ' · Sin dieta registrada')}
                        </p>
                    </div>
                </Card>
            ) : (
                <Card className="overflow-hidden" data-testid="checkins-content">
                    <div className="px-5 pt-5 pb-3 flex items-center gap-2">
                        <Activity className="w-4 h-4 text-brand" />
                        <p className="text-xs font-bold text-foreground/40 uppercase tracking-wider">Check-in diario · 10 segundos</p>
                    </div>
                    <div className="px-5 pb-5 space-y-5">
                        {/* DOS campos, ni uno más (documento 31-07, partes 6 y 7.2): solo lo
                            que no está en ningún dato. El ánimo salió, y la dieta y el
                            entreno no se preguntan porque ya constan en lo registrado. */}
                        <div>
                            <span className="text-sm text-foreground/70 mb-2 block">Nivel de energía</span>
                            <div className="flex gap-2">
                                {[1, 2, 3, 4, 5].map(v => {
                                    const active = daily.energy === v;
                                    return (
                                        <button key={v} type="button" onClick={() => setDaily({ ...daily, energy: v })}
                                            data-testid={`daily-energy-${v}`}
                                            className={`flex-1 py-3 rounded-xl border transition-all flex items-center justify-center gap-1 font-bold text-sm ${active ? 'border-brand bg-brand/10 text-brand' : 'border-border bg-muted text-foreground/50 hover:border-white/30'}`}>
                                            <Zap className="w-3.5 h-3.5" />{v}
                                        </button>
                                    );
                                })}
                            </div>
                            {/* Las dos escalas o ninguna: la de hambre decía «1 = nada · 5 =
                                mucha» y esta no decía nada, así que había que adivinar si el 5
                                era mucha energía o poca (Jesús, 11-08). */}
                            <p className="text-[11px] text-foreground/40 mt-1.5">1 = por los suelos · 5 = a tope</p>
                        </div>
                        <div>
                            <span className="text-sm text-foreground/70 mb-2 block">Ansiedad y hambre</span>
                            <div className="flex gap-2">
                                {[1, 2, 3, 4, 5].map(v => {
                                    const active = daily.hunger_anxiety === v;
                                    return (
                                        <button key={v} type="button" onClick={() => setDaily({ ...daily, hunger_anxiety: v })}
                                            data-testid={`daily-hunger-${v}`}
                                            className={`flex-1 py-3 rounded-xl border transition-all flex items-center justify-center gap-1 font-bold text-sm ${active ? 'border-brand bg-brand/10 text-brand' : 'border-border bg-muted text-foreground/50 hover:border-white/30'}`}>
                                            {v}
                                        </button>
                                    );
                                })}
                            </div>
                            <p className="text-[11px] text-foreground/40 mt-1.5">1 = nada · 5 = mucha</p>
                        </div>
                        {/* AQUÍ ESTABA «¿QUÉ HAS COMIDO HOY?», y se cae (T4/T11 del doc
                            16-08). Lo que se come ya se registra en Nutrición, y el cierre
                            del día pregunta por lo que la app no puede saber. El campo
                            `comido_hoy` se sigue aceptando en el backend: los que ya están
                            escritos no se tiran. */}
                        <button onClick={submitDaily} disabled={submitting}
                            className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 disabled:opacity-60">
                            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Enviar check-in
                        </button>
                    </div>
                </Card>
            )}

            {/* AQUÍ ESTABAN EL CHECK-IN SEMANAL Y EL MENSUAL, y se caen (T11 del doc 16-08).
                Lo que pedían vive ya en otro sitio: el peso, el sueño, el estrés y las notas
                del semanal están en el cierre del día; el peso y las medidas del mensual, en
                el reporte del mes. Eran tres puertas para el mismo dato y ninguna decía cuál
                era la buena.
                El backend los sigue aceptando por compatibilidad (`POST /checkins` con type
                weekly o monthly): los que ya están guardados se siguen leyendo, y salen aquí
                abajo en el historial. Lo que desaparece son los formularios. */}

            {/* LAS FOTOS SE FUERON DE AQUÍ (punto 17). Estaban en un `hidden lg:block`, o
                sea solo en escritorio, y es justo donde Jesús las vio: «debajo del
                "Anotado" hay ahora una galería entera de fotos de progreso, con la cara»
                (punto 53). Se ven en Seguimiento -> Evolución. */}

            {/* EL HISTORIAL, EN DOS BLOQUES (24-08).
                «Tus días» es una línea por día con sus huecos (puntos 19 a 21). Los
                reportes NO se filtran: en producción hay 1.593 entradas mensuales y 5
                cierres, y 98 de los 103 clientes con historial solo tienen mensuales, así
                que quitarlos les deja la pantalla vacía. Su etapa anterior también es suya.

                ESTA LISTA TIENE QUE ACABAR EN UN SOLO SITIO, Seguimiento -> Diario (punto
                23), y de momento no puede: el traslado toca `components/Diario.jsx` y
                `ReportsPage.jsx`. `HistorialDeDias` se exporta ya montada para que ese
                traslado sea una importación y no volver a escribirla. Quitarla de aquí
                antes de tiempo dejaría al cliente sin ver ni uno solo de sus días. */}
            <Card className="p-5">
                <p className="text-xs font-bold text-foreground/40 uppercase tracking-wider mb-3">Historial</p>
                {checkins.length === 0 ? (
                    <p className="text-foreground/40 text-center py-8 text-sm">Aún no tienes check-ins</p>
                ) : (
                    <div className="space-y-5">
                        {cierres.length > 0 && (
                            <div data-testid="historial-tus-dias">
                                <p className="text-[11px] font-bold uppercase tracking-wider text-foreground/40 mb-2">
                                    Tus días
                                </p>
                                <HistorialDeDias cierres={cierres} hoyIso={hoy?.fecha || todayKey()} />
                            </div>
                        )}
                        {reportes.length > 0 && (
                            <div data-testid="historial-reportes">
                                <p className="text-[11px] font-bold uppercase tracking-wider text-foreground/40 mb-2">
                                    Reportes anteriores
                                </p>
                                <ul className="space-y-3">
                                    {reportes.map(c => (
                                        <EntradaDelHistorial key={c.id} c={c} conTipo={mezclaDeReportes} />
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                )}
                {(histShown < checkins.length || histHasMore) && (
                    <button onClick={loadMoreHistory} disabled={histLoadingMore} data-testid="checkins-load-more"
                        className="w-full mt-3 py-2.5 rounded-xl border border-border text-sm text-foreground/60 hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50">
                        {histLoadingMore ? 'Cargando...' : 'Cargar más'}
                    </button>
                )}
            </Card>
        </div>
    );
};

export default CheckInsPage;
