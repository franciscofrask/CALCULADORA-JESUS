import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useEsTelefono } from '../lib/esTelefono';
import { revisarPeso, PESO_MIN, PESO_MAX } from '../lib/pesoValido';
import { useConfirm } from '../components/ui/confirm';
import { toast } from 'sonner';
import {
    Activity, CheckCircle2, Smile, Frown, Meh,
    Zap, Apple, Dumbbell, Scale, Send,
    Camera, Trash2, Loader2, ChevronLeft,
} from 'lucide-react';
import { mensajeDeError } from '../lib/mensajeDeError';
import TresFotos from '../components/reports/TresFotos';

const ORANGE = '#FF671F';
const inputCls = "w-full bg-muted border border-input rounded-xl px-3 py-2.5 text-foreground text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors";

// Aquí había una tarjeta con la etiqueta de riesgo del cliente ("Saludable" / "Atención" /
// "En riesgo") y el motivo debajo. Se quitó el 07-08 (punto 6 del documento de Jesús): esa
// etiqueta es una nota de gestión del entrenador, para saber a quién hay que llamar, y sus
// motivos hablan de cobros y de bajas. El cliente no tiene por qué verse etiquetado en su
// propio panel. Vive solo en el lado del entrenador, y su ruta también.

const MOOD_FACES = [
    { value: 1, icon: Frown, color: 'text-red-500', label: 'Mal' },
    { value: 2, icon: Frown, color: 'text-orange-500', label: 'Bajo' },
    { value: 3, icon: Meh, color: 'text-amber-500', label: 'Neutro' },
    { value: 4, icon: Smile, color: 'text-emerald-500', label: 'Bien' },
    { value: 5, icon: Smile, color: 'text-emerald-400', label: 'Genial' },
];

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

// ── El resumen de un cierre en el historial (P76, doc 23-08) ─────────────────
//
// El historial decía dos cosas de siete: «Energía 3/5 · Hambre 4/5» y ya, con el descanso,
// el movimiento, las comidas, los suplementos, las notas y el peso guardados pero mudos.
// Aquí se saca TODO lo que la entrada traiga: los datos cortos como chips y los textos
// como renglones.
// El movimiento del día. UN SOLO VOCABULARIO CON EL FORMULARIO: esto decía «Desgaste:
// menos de lo habitual» mientras la pregunta de arriba habla de moverse y sus botones
// dicen «Menos» / «Como siempre» / «Más». Eran dos maneras de nombrar el mismo dato, y el
// cliente leía en su historial una palabra que nadie le había preguntado. Los valores
// guardados (menos/igual/mas) no cambian: esto es solo cómo se le enseña.
const MOVIMIENTO_HIST = {
    menos: 'Movimiento: menos',
    igual: 'Movimiento: como siempre',
    mas: 'Movimiento: más',
};
const SUPLES_HIST = { si: 'Suplementos: sí', no_todos: 'Suplementos: no todos', no: 'Suplementos: no' };
const NOMBRE_COMIDA = (k) => {
    if (!k) return 'Comida';
    if (k === 'Post') return 'Post-entreno';
    if (k === 'Intra') return 'Intra-entreno';
    return k.startsWith('C') ? `Comida ${k.slice(1)}` : k;
};

const chipsDelCierre = (c) => {
    const chips = [];
    if (c.mood != null) chips.push(`Ánimo ${c.mood}/5`);              // los viejos traían ánimo
    if (c.energy != null) chips.push(`Energía ${c.energy}/5`);
    if (c.hunger_anxiety != null) chips.push(`Hambre ${c.hunger_anxiety}/5`);
    if (c.descanso != null) chips.push(`Descanso ${c.descanso}/5`);
    if (c.movimiento) chips.push(MOVIMIENTO_HIST[c.movimiento] || c.movimiento);
    if (c.weight != null) chips.push(kilos(c.weight));
    if (c.suplementos?.respuesta) chips.push(SUPLES_HIST[c.suplementos.respuesta] || c.suplementos.respuesta);
    if (c.entreno_respuesta === 'no_entrene') chips.push('No entrenó');
    if (c.trained != null) chips.push(c.trained ? 'Entrenó' : 'No entrenó');
    if (c.cena_hecha != null && c.comida_pendiente) {
        chips.push(`${NOMBRE_COMIDA(c.comida_pendiente)}: ${c.cena_hecha ? 'la hizo' : 'sin registrar'}`);
    }
    if (c.nutrition_followed != null) chips.push(c.nutrition_followed ? 'Dieta registrada' : 'Sin dieta registrada');
    return chips;
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

// Una entrada del historial. `conTipo` pinta la píldora («Semanal», «Mensual»): dentro de
// un bloque con título no hace falta, y solo se enciende donde el título no basta.
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
        {c.type === 'daily' ? (
            <>
                {/* TODO lo que trae la entrada, no dos cosas de siete (P76): los datos
                    como chips, los textos debajo. */}
                {chipsDelCierre(c).length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                        {chipsDelCierre(c).map(chip => (
                            <span key={chip}
                                className="text-xs text-foreground/70 bg-card border border-border rounded-full px-2 py-0.5">
                                {chip}
                            </span>
                        ))}
                    </div>
                )}
                {renglonesDelCierre(c).map(r => (
                    <p key={r.titulo}
                        className="text-sm text-foreground/60 mt-2 whitespace-pre-line border-l-2 border-border pl-3">
                        <span className="text-[10px] uppercase tracking-wider font-bold text-foreground/40 mr-2">{r.titulo}</span>
                        {r.texto}
                    </p>
                ))}
            </>
        ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-foreground/70">
                {c.weight != null && <span><Scale className="w-3 h-3 inline mr-1" />{c.weight} kg</span>}
                {c.training_compliance != null && <span>Entreno {c.training_compliance}%</span>}
                {c.nutrition_compliance != null && <span>Nutri {c.nutrition_compliance}%</span>}
                {c.sleep_quality != null && <span>Sueño {c.sleep_quality}/10</span>}
                {c.body_fat_pct != null && <span>Grasa {c.body_fat_pct}%</span>}
            </div>
        )}
        {c.trainer_feedback && (
            <div className="mt-2 p-2 bg-brand/10 border border-brand/20 rounded-lg text-sm text-foreground/80">
                <span className="text-[10px] uppercase tracking-wider text-brand font-bold mr-2">Entrenador:</span>{c.trainer_feedback}
            </div>
        )}
    </li>
);

const BoolPicker = ({ icon: Icon, label, value, onChange }) => (
    <div>
        <span className="text-sm text-foreground/70 mb-2 flex items-center gap-2">
            <Icon className="w-4 h-4" /> {label}
        </span>
        <div className="grid grid-cols-2 gap-2">
            {[{ v: true, l: 'Sí' }, { v: false, l: 'No' }].map(({ v, l }) => {
                const active = value === v;
                const tone = active
                    ? (v ? 'border-emerald-500 bg-emerald-500/10 text-emerald-400' : 'border-red-500 bg-red-500/10 text-red-400')
                    : 'border-border bg-muted text-foreground/50 hover:border-white/30';
                return (
                    <button key={String(v)} type="button" onClick={() => onChange(v)}
                        className={`py-3 rounded-xl border font-bold text-sm transition-all ${tone}`}>
                        {l}
                    </button>
                );
            })}
        </div>
    </div>
);

// Aquí vivía `Collapsible`, la caja plegable del check-in semanal y del mensual. Los dos
// formularios se caen con T11 del doc 16-08, así que la caja se va con ellos.

// ── El cierre del día (T4 del doc 16-08) ─────────────────────────────────────
//
// «Al final del día. Lo primero que sale es lo que no ha marcado». Ese orden -- entreno,
// suplementos, comida sin registrar, macros -- no es decorativo: es lo que hace que el
// cierre valga para algo, porque son las cuatro cosas que la app no puede saber sola.
// Debajo va lo de siempre, que se pregunta todos los días le falte o no le falte nada.
//
// Todo lo condicional lo decide el servidor (`GET /checkins/hoy`): la pantalla pinta lo
// que le digan y no vuelve a calcular por su cuenta si le toca entreno o si se ha pasado
// de hidratos.

// Las tres escalas del doc, cada una con sus extremos escritos.
const Escala = ({ titulo, subtitulo, minLabel, maxLabel, value, onChange, testId }) => (
    <div>
        <span className="text-sm text-foreground/70 block">{titulo}</span>
        {subtitulo && <p className="text-[11px] text-foreground/40 mt-0.5">{subtitulo}</p>}
        <div className="flex gap-2 mt-2">
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

// ── Corta o larga (apartado 9 del doc del lunes) ─────────────────────────────
//
// Si el cliente YA FUE MARCANDO sus comidas durante el día -- la casilla del Inicio
// nuevo, que vive en el día (`comidas.{k}.marcada`) --, el cierre no le vuelve a
// preguntar si cumplió: le quedan solo las cinco cosas que la app no puede saber sola.
// La versión larga es para el que no marca sobre la marcha. El peri no cuenta: no se
// marca. Sin día guardado, o sin nada montado, la larga de siempre.

const NUMERAL = { 1: 'una', 2: 'dos', 3: 'tres', 4: 'cuatro' };
// Las cosas que quedan por contestar en el cierre corto, escritas. Van de cuatro (las
// escalas y el movimiento, que salen siempre) a ocho.
const CUANTAS = { 4: 'cuatro', 5: 'cinco', 6: 'seis', 7: 'siete', 8: 'ocho' };

// Suma de `macros_efectivos` de una comida guardada, como la lista del Inicio: cuando el
// campo falta en filas antiguas esa comida suma 0, y aquí el número es informativo.
// Las comidas PRINCIPALES del día (C1..Cn): las que se marcan. Intra y Post, fuera.
const comidasPrincipales = (dia) => (dia?.exists
    ? ['C1', 'C2', 'C3', 'C4'].slice(0, Math.max(1, Math.min(4, dia.num_comidas || 4)))
    : []);

// `inicial` es el cierre ya guardado hoy cuando se entra a EDITARLO (P75, doc 23-08): el
// formulario arranca con lo que puso, lo toca y al guardar SUSTITUYE al de antes. Sin
// `inicial` es el cierre en blanco de siempre.
const CierreDelDia = ({ api, hoy, dia, onGuardado, pesoAceptado, inicial = null }) => {
    const navigate = useNavigate();
    const [enviando, setEnviando] = useState(false);
    const [f, setF] = useState(() => ({
        entreno_respuesta: inicial?.entreno_respuesta ?? null,
        entreno_nota: inicial?.entreno_nota || '',
        suplementos: inicial?.suplementos?.respuesta ?? null,
        suplementos_detalle: inicial?.suplementos?.detalle || '',
        cena_hecha: inicial?.cena_hecha ?? false,
        exceso_nota: inicial?.exceso_nota || '',
        descanso: inicial?.descanso ?? null,
        energy: inicial?.energy ?? null,
        hunger_anxiety: inicial?.hunger_anxiety ?? null,
        movimiento: inicial?.movimiento ?? null,
        notas: inicial?.notas?.texto || '',
        compartida: inicial?.notas?.compartida ?? false,
        weight: inicial?.weight != null ? String(inicial.weight) : '',
    }));
    const set = (campo, valor) => setF(prev => ({ ...prev, [campo]: valor }));

    // La decisión corta/larga, con lo que dice el servidor del día de hoy. `marcada` solo
    // vale si lo dice el día guardado: si la marca no llegó a la base, larga, que nunca
    // pregunta de menos.
    const comidas = (dia?.exists && dia.comidas) || {};
    const claves = comidasPrincipales(dia);
    const algoMontado = claves.some(k => (comidas[k]?.alimentos || []).length > 0);
    const corta = claves.length > 0 && algoMontado && claves.every(k => comidas[k]?.marcada === true);

    // ── REEDITAR NO PUEDE ESCONDER LO QUE YA CONTESTÓ (24-08) ────────────────
    //
    // El cierre corto esconde las notas y el peso a quien ya marcó todas sus comidas, y
    // eso está bien la PRIMERA vez del día. Pero el cierre se puede reabrir para
    // corregirlo (P75), y quien anotó sus notas y su peso por la mañana -- cuando aún era
    // largo -- por la noche reabría y no los veía: no podía corregirlos, no podía
    // borrarlos, y le quedaba la sensación de que se habían perdido. Y encima el peso
    // seguía viajando escondido, así que «Confírmame el peso» le podía saltar por un
    // número que la pantalla no le estaba enseñando.
    //
    // La regla es por campo y no en bloque: EDITANDO, lo que trae respuesta se enseña
    // siempre; lo que viene vacío se sigue escondiendo, que para eso existe el corto.
    const editando = inicial != null;
    const verNotas = !corta || (editando && !!inicial?.notas?.texto);
    const verPeso = !corta || (editando && inicial?.weight != null);

    // LA CUENTA DE LA CABECERA CUENTA LO QUE VA A SALIR, ni una más. Era fija («cinco», o
    // «cuatro» sin protocolo de suplementos) y ya mentía antes de esto: al que no tiene
    // rutina con nosotros le sale además la nota de entreno libre, que tampoco se calla en
    // el corto. Y desde hoy, al que reabre su cierre le vuelven las notas y el peso.
    // Prometerle cinco y enseñarle siete es de las cosas por las que se deja de leer lo
    // que pone la pantalla. Las cuatro fijas son descanso, energía, hambre y movimiento.
    const cosas = CUANTAS[4 + [hoy?.suplementos, hoy?.tiene_rutina === false, verNotas, verPeso]
        .filter(Boolean).length];

    const guardar = async () => {
        const algo = ['entreno_respuesta', 'suplementos', 'descanso', 'energy', 'hunger_anxiety', 'movimiento']
            .some(k => f[k] != null) || f.cena_hecha || f.notas.trim() || f.entreno_nota.trim() || f.weight;
        if (!algo) return toast.error('Cuéntame algo antes de guardar.');
        if (f.weight && !await pesoAceptado(f.weight)) return;

        setEnviando(true);
        try {
            await api.post('/checkins', {
                type: 'daily',
                // El día del RELOJ DEL CLIENTE (bloque F): su cierre se archiva en SU día.
                fecha: todayKey(),
                descanso: f.descanso, energy: f.energy, hunger_anxiety: f.hunger_anxiety,
                movimiento: f.movimiento,
                entreno_respuesta: f.entreno_respuesta,
                entreno_nota: f.entreno_nota.trim() || null,
                suplementos: f.suplementos
                    ? { respuesta: f.suplementos, detalle: f.suplementos_detalle.trim() || null }
                    : null,
                // El check de la comida se guarda AQUÍ y ya: no toca la dieta ni le manda
                // a Nutrición. Se anota de cuál hablaba, o el sí/no no se puede leer luego.
                // LO QUE NO SE VUELVE A PREGUNTAR, NO SE BORRA: el guardado sustituye la
                // fila entera, y mandar null aquí tiraba el «La hice» de esta mañana en
                // cuanto la comida dejaba de estar pendiente (porque la registró después,
                // o porque el cierre pasó a corto). Si la pregunta no sale, viaja lo que
                // ya había contestado.
                cena_hecha: !corta && hoy?.comida_pendiente ? f.cena_hecha : (inicial?.cena_hecha ?? null),
                comida_pendiente: (!corta && hoy?.comida_pendiente?.key) || inicial?.comida_pendiente || null,
                exceso_nota: f.exceso_nota.trim() || null,
                notas: f.notas.trim() ? { texto: f.notas.trim(), compartida: f.compartida } : null,
                weight: f.weight ? parseFloat(String(f.weight).replace(',', '.')) : null,
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
        <Card className="p-5 space-y-6" data-testid="cierre-del-dia">
            {/* La cabecera de la versión CORTA: marcó todas sus comidas durante el día,
                así que aquí no se le vuelve a preguntar por ellas. */}
            {corta && (
                <div className="flex items-start gap-3" data-testid="cierre-corto">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                    <p className="text-sm font-bold text-foreground">
                        Ya marcaste {claves.length === 1 ? 'tu comida' : `las ${NUMERAL[claves.length]} comidas`}.
                        {' '}Solo quedan {cosas} cosas.
                    </p>
                </div>
            )}

            {/* Aquí vivía la lista informativa de comidas sin registrar («Te quedan
                cuatro comidas...»). FUERA (P77 del doc 23-08, decidido por Francisco el
                23-08): preguntaba dos veces lo mismo que el bloque de la comida pendiente
                de abajo, que es el del doc original (T4 del 16-08) y el único que guarda
                algo (el «La hice» viaja al cierre y al coach). */}

            {/* 1 · El entreno que no marcó. «Sí, pero no lo puse» le lleva a registrarlo,
                que es donde de verdad se arregla; no se apaña con un sí a secas aquí.
                En la versión corta no sale: solo quedan las cinco de siempre. */}
            {!corta && hoy?.entreno && (
                <div data-testid="cierre-entreno">
                    <span className="text-sm text-foreground/70 mb-2 block">Hoy no entrenaste.</span>
                    <Opciones columnas={2} testId="cierre-entreno-op" value={f.entreno_respuesta}
                        onChange={(v) => {
                            if (v === 'si_no_lo_puse') return navigate('/dashboard/entreno');
                            set('entreno_respuesta', v);
                        }}
                        opciones={[
                            { v: 'si_no_lo_puse', l: 'Sí, pero no lo puse' },
                            { v: 'no_entrene', l: 'No entrené' },
                        ]} />
                    <textarea rows={2} value={f.entreno_nota} onChange={e => set('entreno_nota', e.target.value)}
                        data-testid="cierre-entreno-nota"
                        placeholder="Cuéntame si quieres qué pasó. Opcional."
                        className={inputCls + ' resize-none mt-2'} />
                </div>
            )}

            {/* 1b · Sin rutina con nosotros no había dónde apuntar el entreno (P80, doc
                23-08): una nota corta y opcional. Quien tiene rutina apunta lo suyo en su
                registro de entreno, así que a él esta caja no le sale y nada se duplica. */}
            {hoy?.tiene_rutina === false && (
                <div data-testid="cierre-entreno-libre">
                    <span className="text-sm text-foreground/70 block">Tu entreno de hoy</span>
                    <p className="text-[11px] text-foreground/40 mt-0.5 mb-2">
                        Si entrenaste por tu cuenta, apúntalo aquí (opcional).
                    </p>
                    <input value={f.entreno_nota} onChange={e => set('entreno_nota', e.target.value)}
                        data-testid="cierre-entreno-libre-nota"
                        placeholder="Qué entrenaste hoy" className={inputCls} />
                </div>
            )}

            {/* 2 · Los suplementos, solo a quien tenga protocolo. */}
            {hoy?.suplementos && (
                <div data-testid="cierre-suplementos">
                    <span className="text-sm text-foreground/70 mb-2 block">¿Tomaste tus suplementos?</span>
                    <Opciones testId="cierre-suplementos-op" value={f.suplementos}
                        onChange={(v) => set('suplementos', v)}
                        opciones={[{ v: 'si', l: 'Sí' }, { v: 'no_todos', l: 'No todos' }, { v: 'no', l: 'No' }]} />
                    {f.suplementos === 'no_todos' && (
                        <input value={f.suplementos_detalle} onChange={e => set('suplementos_detalle', e.target.value)}
                            data-testid="cierre-suplementos-detalle"
                            placeholder="¿Cuál y por qué?" className={inputCls + ' mt-2'} />
                    )}
                </div>
            )}

            {/* 3 · La comida que le quedó sin registrar: un check y ya. Con todas
                marcadas no hay nada que preguntar. */}
            {!corta && hoy?.comida_pendiente && (
                <div data-testid="cierre-comida">
                    <span className="text-sm text-foreground/70 mb-2 block">
                        Te queda la {hoy.comida_pendiente.etiqueta} sin registrar.
                    </span>
                    <label className="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox" checked={f.cena_hecha} data-testid="cierre-comida-hecha"
                            onChange={e => set('cena_hecha', e.target.checked)}
                            className="w-4 h-4 accent-[#FF671F]" />
                        <span className="text-sm text-foreground/80">La hice</span>
                    </label>
                </div>
            )}

            {/* 4 · Si se ha pasado de macros. En la corta tampoco sale. */}
            {!corta && hoy?.exceso && (
                <div data-testid="cierre-exceso">
                    <span className="text-sm text-foreground/70 mb-2 block">
                        Hoy te has pasado {hoy.exceso.gramos} g de {hoy.exceso.macro}.
                    </span>
                    <textarea rows={2} value={f.exceso_nota} onChange={e => set('exceso_nota', e.target.value)}
                        data-testid="cierre-exceso-nota"
                        placeholder="Cuéntame si quieres qué pasó. Opcional."
                        className={inputCls + ' resize-none'} />
                </div>
            )}

            {/* Y luego lo de siempre, con los literales del doc 23-08 (P81). El descanso
                se pregunta aquí, referido a la noche de ayer, y sale del reporte del mes:
                así son 28 datos al mes en vez de uno. */}
            <Escala titulo="¿Cómo descansaste la noche de ayer?"
                subtitulo="Fundamental tener una buena rutina de sueño si no la tienes ya"
                minLabel="fatal" maxLabel="genial" testId="cierre-descanso"
                value={f.descanso} onChange={v => set('descanso', v)} />
            {/* «Fuera de tu entrenamiento»: sin eso el que acaba de entrenar contesta por
                cómo se encontró en el gimnasio, que no es lo que se le pregunta. */}
            <Escala titulo="Niveles de energía durante el día"
                subtitulo="Fuera de tu entrenamiento, en tu día normal"
                minLabel="bajita" maxLabel="pletórico" testId="cierre-energia"
                value={f.energy} onChange={v => set('energy', v)} />
            {/* Hambre y ansiedad, juntas: es como lo dice él y es una sola escala. Y «con
                la dieta», que es de lo que se pregunta y no de la ansiedad de la vida. */}
            <Escala titulo="Hambre / ansiedad con la dieta" minLabel="nada" maxLabel="mucha" testId="cierre-hambre"
                value={f.hunger_anxiety} onChange={v => set('hunger_anxiety', v)} />

            <div>
                {/* LA PREGUNTA ES LA SUYA. El 23-08 la cambiamos por «¿Tuviste más
                    desgaste de lo normal?» y no es lo que él pide: «desgaste» es palabra
                    de entrenador, y además la respuesta se guarda en `movimiento`. */}
                <span className="text-sm text-foreground/70 block">¿Te moviste lo suficiente?</span>
                {/* En cursiva y sin punto final, tal cual lo pide el doc. */}
                <p className="text-[11px] text-foreground/40 mt-0.5 mb-2 italic">
                    Moverte es salud y menos grasa: a más te muevas, más gastas
                </p>
                {/* Etiquetas cortas: los tres botones van en fila y en el móvil tres
                    frases no caben -- se partían en tres renglones dentro del botón. Los
                    valores guardados (menos/igual/mas) son los de siempre. */}
                <Opciones testId="cierre-movimiento" value={f.movimiento} onChange={v => set('movimiento', v)}
                    opciones={[
                        { v: 'menos', l: 'Menos' },
                        { v: 'igual', l: 'Como siempre' },
                        { v: 'mas', l: 'Más' },
                    ]} />
            </div>

            {/* Las notas y el peso son de la versión larga: el mockup corto no los lleva.
                Quien quiera pesarse ese día lo hace desde Evolución. Al REEDITAR salen
                igualmente si ya traen respuesta (ver `verNotas` / `verPeso` arriba). */}
            {verNotas && (
            <div>
                <span className="text-sm text-foreground/70 block">Notas personales</span>
                <p className="text-[11px] text-foreground/40 mt-0.5 mb-2">
                    Compártelo si quieres que lo veamos, o déjalo para ti (opcional).
                </p>
                <textarea rows={3} value={f.notas} onChange={e => set('notas', e.target.value)}
                    data-testid="cierre-notas" placeholder="De lo que quieras acordarte"
                    className={inputCls + ' resize-none'} />
                <label className="flex items-center gap-3 cursor-pointer mt-2">
                    <input type="checkbox" checked={f.compartida} data-testid="cierre-compartir"
                        onChange={e => set('compartida', e.target.checked)}
                        className="w-4 h-4 accent-[#FF671F]" />
                    <span className="text-sm text-foreground/80">Compartir con nosotros</span>
                </label>
            </div>
            )}

            {verPeso && (
            <div>
                <span className="text-sm text-foreground/70 block">Peso</span>
                {/* DOS RENGLONES, como los pide él: arriba para qué sirve pesarse aquí y
                    debajo el último que tenemos. Iba todo en una línea que empezaba por
                    «Opcional ·» y el «sólo para ti» -- que es lo que quita el reparo de
                    apuntarlo -- no se decía en ninguna parte. */}
                <div className="mt-0.5 mb-2">
                    <p className="text-[11px] text-foreground/40">
                        Registrarlo es opcional, sólo para ti. Te lo pediremos sólo para los reportes
                    </p>
                    {hoy?.ultimo_peso && (
                        <p className="text-[11px] text-foreground/40">
                            Último registro: {kilos(hoy.ultimo_peso.valor)} · {cuando(hoy.ultimo_peso.fecha)}
                        </p>
                    )}
                </div>
                <input type="number" step="0.1" min={PESO_MIN} max={PESO_MAX} value={f.weight}
                    onChange={e => set('weight', e.target.value)} data-testid="cierre-peso"
                    placeholder="kg" className={inputCls} />
            </div>
            )}

            <button onClick={guardar} disabled={enviando} data-testid="cierre-guardar"
                className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 disabled:opacity-60">
                {enviando && <Loader2 className="w-4 h-4 animate-spin" />} Guardar
            </button>
        </Card>
    );
};

// ── Fotos de progreso ────────────────────────────────────────────────────────
const PhotoThumb = ({ photo, api, onDeleted }) => {
    const [url, setUrl] = useState(null);
    useEffect(() => {
        let alive = true; let objUrl = null;
        api.get(`/reports/photos/${photo.id}`, { responseType: 'blob' })
            .then(res => { if (!alive) return; objUrl = URL.createObjectURL(res.data); setUrl(objUrl); })
            .catch(() => {});
        return () => { alive = false; if (objUrl) URL.revokeObjectURL(objUrl); };
    }, [api, photo.id]);

    return (
        <div className="relative group rounded-xl overflow-hidden border border-border bg-muted aspect-[3/4]">
            {url
                ? <img src={url} alt="" className="w-full h-full object-cover" />
                : <div className="w-full h-full flex items-center justify-center"><Loader2 className="w-4 h-4 animate-spin text-foreground/40" /></div>}
            {/* La inicial no lleva papelera. El backend también la protege, pero enseñar
                un botón que va a fallar es peor que no enseñarlo: la app le dice que esa
                foto no se puede recuperar y a la vez le ofrece borrarla. */}
            {photo.inicial ? (
                <span title="Tu foto inicial: no se puede borrar"
                    className="absolute top-1.5 right-1.5 text-[9px] font-bold uppercase tracking-wide bg-black/60 text-white/90 px-1.5 py-1 rounded">
                    inicial
                </span>
            ) : (
                <button onClick={() => onDeleted(photo.id)}
                    className="absolute top-1.5 right-1.5 w-7 h-7 rounded-lg bg-black/60 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <Trash2 className="w-3.5 h-3.5" />
                </button>
            )}
            {/* La pose, arriba a la izquierda. Sin ella tres fotos de un mes son tres
                fotos sueltas; con ella son la misma foto desde tres sitios, que es lo
                único que se puede comparar de un mes a otro. Las subidas antes del 06-08
                no la tienen y ahí no se pinta nada, en vez de inventarse una. */}
            {photo.pose && (
                <span className="absolute top-1.5 left-1.5 text-[9px] font-bold uppercase tracking-wide bg-black/60 text-white/90 px-1.5 py-1 rounded">
                    {POSE_LABEL[photo.pose] || photo.pose}
                </span>
            )}
            <span className="absolute bottom-1 left-1.5 text-[10px] text-white/90 bg-black/50 px-1.5 py-0.5 rounded">
                {new Date(photo.taken_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}
            </span>
        </div>
    );
};

// Las tres poses, con el nombre que ve el cliente y el orden en que se miran.
const POSE_LABEL = { frente: 'Frente', espalda: 'Espalda', perfil: 'Perfil' };
const POSE_ORDEN = ['frente', 'perfil', 'espalda'];

const _mesDe = (iso) => String(iso || '').slice(0, 7);
const _mesTitulo = (key) => {
    const [y, m] = key.split('-');
    const d = new Date(+y, +m - 1, 1);
    return isNaN(d) ? key : d.toLocaleDateString('es-ES', { month: 'long', year: 'numeric' });
};

/**
 * La rejilla de fotos: solo para VERLAS.
 *
 * Se subían aquí y también se borraban aquí. Desde el 06-08-2026 hay un solo sitio para
 * subirlas -- el reporte, con sus tres poses y la del mes pasado al lado para colocarse
 * igual -- y esta pantalla se queda para mirarlas, que es lo que se viene a hacer aquí.
 */
const PhotosSection = ({ api, token }) => {
    const [photos, setPhotos] = useState([]);
    // Si acaba de subir su primera foto en esta visita, la subida se queda a la vista:
    // cambiarla por la rejilla a mitad le quitaría el hueco de las otras dos poses.
    const [subiendoAhora, setSubiendoAhora] = useState(false);
    const navigate = useNavigate();

    const load = useCallback(() => {
        api.get('/reports/photos').then(r => setPhotos(r.data?.photos || [])).catch(() => {});
    }, [api]);
    useEffect(() => { load(); }, [load]);

    const remove = async (id) => {
        try { await api.delete(`/reports/photos/${id}`); setPhotos(p => p.filter(x => x.id !== id)); }
        catch (err) { toast.error(mensajeDeError(err, 'Error borrando la foto')); }
    };

    // POR MESES, Y DENTRO DEL MES POR POSE. Era una parrilla plana de todas las fotos de
    // todos los meses mezcladas -- frente, espalda y perfil seguidas, con la fecha diminuta
    // en una esquina -- y por eso Jesús la llamó «un álbum»: para ver si alguien ha
    // cambiado hay que poder poner el mes de al lado debajo, y así no se podía.
    const meses = useMemo(() => {
        const mapa = new Map();
        for (const p of photos) {
            const k = _mesDe(p.taken_at);
            if (!mapa.has(k)) mapa.set(k, []);
            mapa.get(k).push(p);
        }
        return [...mapa.entries()]
            .sort((a, b) => b[0].localeCompare(a[0]))            // el mes más reciente arriba
            .map(([key, fotos]) => ({
                key,
                fotos: fotos.sort((a, b) => {
                    const d = POSE_ORDEN.indexOf(a.pose) - POSE_ORDEN.indexOf(b.pose);
                    // Las que no tienen pose (las de antes del 06-08) al final, por fecha.
                    return d !== 0 ? d : String(a.taken_at).localeCompare(String(b.taken_at));
                }),
            }));
    }, [photos]);

    return (
        <Card className="p-5">
            <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                    <Camera className="w-4 h-4 text-brand" />
                    <p className="text-xs font-bold text-foreground/40 uppercase tracking-wider">Fotos de progreso</p>
                </div>
                {/* Con fotos ya subidas, la puerta para añadir más sigue en Seguimiento;
                    sin ninguna, la subida está aquí mismo y este enlace sobra. */}
                {photos.length > 0 && (
                    <button onClick={() => navigate('/dashboard/reports')}
                        className="text-xs text-brand hover:underline underline-offset-4 font-semibold">
                        Sube más en Seguimiento
                    </button>
                )}
            </div>
            {/* Vuelve a decir «tu reporte» a secas, y ahora es verdad. El 09-08 esto decía
                «mensual» como parche: las fotos solo se pedían en el reporte mensual y en una
                semana normal el cliente venía aquí, iba a Reportes y no encontraba dónde
                subirlas. El parche avisaba de la contradicción pero no la quitaba -- seguía
                sin haber sitio 3 de cada 4 semanas. Ahora el bloque de fotos está siempre en
                Reportes (punto 21), así que el enlace lleva a algo. */}
            {photos.length === 0 || subiendoAhora ? (
                // SIN FOTOS, LA PUERTA VA AQUÍ (doc 23-08, bloque 10, y lo decidido el
                // 19-08): en autogestión las fotos no se piden, se recomiendan, y esto
                // decía «se piden en el reporte mensual» sin dejar hacer nada. Ahora se
                // recomienda y debajo va la subida de siempre, la misma de los reportes
                // (POST /reports/photos), que no distingue de planes.
                <div>
                    {photos.length === 0 && (
                        <p className="text-foreground/50 text-sm mb-4">
                            Todavía no has subido fotos. Te recomendamos hacértelas cada cuatro
                            semanas: son la forma más honesta de ver tu cambio. Puedes subirlas
                            aquí cuando quieras.
                        </p>
                    )}
                    <TresFotos api={api} token={token}
                        onSubida={() => { setSubiendoAhora(true); load(); }} />
                </div>
            ) : (
                <div className="space-y-5">
                    {meses.map(m => (
                        <div key={m.key}>
                            <p className="text-[11px] font-bold uppercase tracking-wider text-foreground/40 mb-2 capitalize">
                                {_mesTitulo(m.key)}
                            </p>
                            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2">
                                {m.fotos.map(p => <PhotoThumb key={p.id} photo={p} api={api} onDeleted={remove} />)}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </Card>
    );
};

const CheckInsPage = () => {
    const { api, token, pantalla } = useAuth();
    // El cierre del día nuevo, detrás de su interruptor del panel (T4). Con él apagado se
    // queda el check-in diario de siempre, que es lo que hay hoy en producción.
    const cierreNuevo = pantalla('t4_cierre_nuevo');
    const [hoy, setHoy] = useState(null);
    // El día de la dieta de hoy, para decidir cierre corto o largo. `listo` evita el
    // parpadeo: sin él la larga saldría un instante y se encogería a corta delante
    // del cliente.
    const [diaHoy, setDiaHoy] = useState({ dia: null, listo: false });
    const { confirm } = useConfirm();
    const navigate = useNavigate();
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
            const { data } = await api.get(`/checkins/hoy?fecha=${todayKey()}`);
            setHoy(data || null);
        } catch (err) {
            console.error('No se pudo consultar el día de hoy:', err?.response?.data || err);
            setHoy(null);
        }
    }, [api]);

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

    // EL PESO DEL CHECK-IN TAMBIÉN ESCRIBE EN EL HISTÓRICO (#48 del 15-08). Aquí no había
    // ninguna validación: entraba un 50 detrás de un 94 sin decir nada, y de esa serie
    // salen la gráfica y el ritmo de cambio. Se compara con el último peso que conocemos
    // -- el del check-in más reciente que traiga uno -- y si el salto canta, se pregunta.
    //
    // SALE DE LA LISTA ENTERA, NO DE LOS CIERRES. Aunque el historial se pinte en dos
    // bloques, este peso se busca en `checkins` completo a propósito: en producción casi
    // todos los pesos conocidos vienen de los reportes mensuales importados de Calma (los
    // cierres del día casi nunca traen peso), así que mirar solo los cierres dejaría el
    // aviso del 50 detrás del 94 sin nada con lo que comparar y no saltaría nunca.
    const ultimoPeso = checkins.find(c => c.weight != null)?.weight ?? null;
    const pesoAceptado = async (valor) => {
        const chequeo = revisarPeso(valor, ultimoPeso);
        if (!chequeo.ok) { toast.error(chequeo.error); return false; }
        if (!chequeo.confirmar) return true;
        return confirm({
            title: 'Confírmame el peso',
            description: chequeo.confirmar,
            confirmLabel: 'Sí, es correcto', cancelLabel: 'Lo corrijo',
        });
    };

    const submitDaily = async () => {
        if (daily.energy == null || daily.hunger_anxiety == null) {
            return toast.error('Dinos cómo vas de energía y de hambre');
        }
        setSubmitting(true);
        try {
            await api.post('/checkins', { type: 'daily', fecha: todayKey(), ...daily });
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
                            {/* Guardado no es sellado (P75, doc 23-08): el mismo día se puede
                                reabrir, corregir y volver a guardar; lo nuevo sustituye. */}
                            <button type="button" onClick={() => setEditando(true)} data-testid="cierre-editar"
                                className="mt-1.5 text-sm text-brand font-semibold hover:underline underline-offset-4">
                                Editar lo de hoy
                            </button>
                        </div>
                    </Card>
                ) : hoy?.fecha && !diaHoy.listo ? (
                    // Sin la dieta de hoy aún no se sabe si el cierre es corto o largo:
                    // mejor un latido que un formulario que cambia de tamaño al llegar.
                    <div className="h-64 bg-muted rounded-2xl animate-pulse" data-testid="checkins-content" />
                ) : (
                    <div data-testid="checkins-content">
                        <CierreDelDia api={api} hoy={hoy} dia={diaHoy.dia} pesoAceptado={pesoAceptado}
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

            {/* LAS FOTOS NO PINTAN NADA AQUÍ.
                Este bloque decía «se suben en tu reporte» y justo debajo «aún no has subido
                fotos»: un cajón entero para mandarte a otro sitio. Esta es la pantalla de los
                diez segundos -- energía, hambre y qué has comido --, y todo lo que no sean esos
                dos campos le quita el sentido (Jesús, 11-08).
                Las fotos siguen donde se suben, en el reporte, y se ven en Mi evolución; aquí
                no se pierde ninguna forma de llegar a ellas. En escritorio se queda, que ahí
                sobra sitio y el bloque no estorba a nadie. */}
            <div className="hidden lg:block">
                <PhotosSection api={api} token={token} />
            </div>

            {/* EL HISTORIAL, EN DOS BLOQUES (24-08).
                Caían mezclados los cierres del día y los reportes mensuales importados de
                Calma, cada uno con su píldora de tipo y su hora. Filtrar a los cierres a
                secas NO vale: en producción hay 1.593 entradas mensuales y 5 cierres, y 98
                de los 103 clientes con historial solo tienen mensuales, así que se
                quedarían con la pantalla vacía. Su etapa anterior también es suya. */}
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
                                <ul className="space-y-3">
                                    {cierres.map(c => <EntradaDelHistorial key={c.id} c={c} />)}
                                </ul>
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
