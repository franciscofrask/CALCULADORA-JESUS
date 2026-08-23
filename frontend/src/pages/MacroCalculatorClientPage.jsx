import React, { useState, useEffect, useRef } from 'react';
import { SlidersHorizontal, Calculator, Loader2, CheckCircle2, CalendarDays, Save, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { seLeOfreceLaRevision } from '../lib/revision';
import { MACRO } from './ClientDashboard';
import DesgloseChips from '../components/DesgloseChips';
import MisMacrosPage from './MisMacrosPage';
import { mensajeDeError } from '../lib/mensajeDeError';

// Fecha de HOY en la zona del usuario. Con toISOString() (que es UTC) a partir de las
// 22:00 en Espana el "hoy" saltaba al dia siguiente.
const todayISO = () => {
    const d = new Date();
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

const fechaLarga = (iso) => {
    if (!iso) return '';
    const d = new Date(iso + 'T12:00:00');
    return d.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
};

// One macro input cell (P/H/G)
const Field = ({ label, color, value, onChange, suffix = 'g' }) => (
    <div>
        <label className="block text-[11px] font-bold uppercase tracking-wider mb-1.5" style={{ color }}>{label}</label>
        <div className="relative">
            <input
                type="number" min="0" step="1" value={value}
                onChange={e => onChange(e.target.value)}
                className="input-light font-data pr-7" placeholder="0"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">{suffix}</span>
        </div>
    </div>
);

// Module-level so inputs keep focus while typing.
// `vertical`: una opción por línea, alineada a la izquierda y sin mayúsculas. Es para las
// respuestas que son frases ("Pesar no, pero me cuido bastante"), que en columnas de un
// cuarto de ancho salen partidas en cuatro líneas y en versales, ilegibles.
const ToggleGroup = ({ options, value, onChange, vertical = false }) => (
    <div className={vertical ? 'grid gap-2' : 'grid gap-2'}
        style={vertical ? undefined : { gridTemplateColumns: `repeat(${options.length}, 1fr)` }}>
        {options.map(o => (
            <button key={String(o.value)} onClick={() => onChange(o.value)} type="button"
                className={`rounded-xl transition-all border ${vertical ? 'py-2.5 px-3 text-left text-sm font-semibold' : 'py-2.5 text-sm font-bold uppercase tracking-wider'} ${value === o.value ? 'bg-brand text-white border-brand' : 'bg-card text-muted-foreground border-border hover:border-neutral-400'}`}>
                {o.label}
            </button>
        ))}
    </div>
);

// Las cuatro de la pantalla 5 del documento de textos, literales y con los mismos valores
// que el cuestionario. `sedentario` es «muy sedentario» y `normal` «ligeramente activo»: los
// valores viejos se conservan para no invalidar lo que ya contestaron los clientes.
const OPCIONES_ACTIVIDAD = [
    { value: 'sedentario', label: 'Muy sedentario: paso casi todo el día sentado, apenas me muevo.' },
    { value: 'normal', label: 'Ligeramente activo: me muevo algo, pero sin esfuerzos físicos.' },
    { value: 'moderado', label: 'Moderadamente activo: estoy de pie o en movimiento buena parte del día.' },
    { value: 'muy_activo', label: 'Muy activo: mi día a día es muy demandante físicamente, no paro.' },
];

// Las cuatro respuestas de «¿Sigues algún tipo de dieta?» (punto 19). Son literalmente las
// del cuestionario de alta -- mismos textos y mismos valores -- porque es la misma pregunta:
// si aquí dijera Sí/No y allí cuatro cosas, el mismo cliente contestaría distinto según por
// dónde entrara, y el motor recibiría dos datos que no se pueden comparar.
const OPCIONES_DIETA = [
    { value: true, label: 'Estricta, mido todo lo que como.' },
    { value: 'parecido', label: 'Pesar no, pero me cuido bastante.' },
    { value: false, label: 'Sin control, pero no como mal.' },
    { value: 'desorganizado', label: 'Como mal y desorganizado.' },
];

// Las dos primeras traen una dieta de la que partir; las dos últimas no. Es la misma regla
// que `traeDieta` en el cuestionario y que `trae_dieta` en macro_engine.py.
const traeDieta = (a) => a?.sigue_dieta === true || a?.sigue_dieta === 'parecido';

// «¿Mantienes el peso, ganas o pierdes?» (punto 19, con el 4.1). El cuestionario de alta se
// la hace a todo el mundo desde el 06-08 y esta pantalla no la hacía nunca, así que el
// motor recibía `como_va: null` y caía en su valor por defecto -- "mantengo" -- para
// TODOS los reajustes hechos desde aquí. Es la pregunta que sitúa lo que come respecto a su
// mantenimiento sin pedirle un número, y era justo la que faltaba.
const OPCIONES_COMO_VA = (objetivo) => (objetivo === 'volumen' ? [
    { value: 'bien', label: 'Bien: estoy subiendo peso.' },
    { value: 'lento', label: 'Regular: subo, pero muy lento.' },
    { value: 'mucha_grasa', label: 'Regular: subo, pero cojo más grasa de la cuenta.' },
    { value: 'mantengo', label: 'Me mantengo igual, siento que necesito comer más.' },
    { value: 'bajando', label: 'Mal: en lugar de subir, estoy bajando.' },
] : [
    { value: 'bien', label: 'Bien: estoy bajando a buen ritmo.' },
    { value: 'lento', label: 'Estoy bajando, pero muy lento.' },
    { value: 'mantengo', label: 'Me mantengo.' },
    { value: 'cogiendo_peso', label: 'Mal: estoy cogiendo peso.' },
]);

const GroupCard = ({ label, group, withFat, macros, setMacro }) => (
    <div className="surface p-4">
        <p className="caption mb-3">{label}</p>
        <div className={`grid gap-3 ${withFat ? 'grid-cols-3' : 'grid-cols-2'}`}>
            <Field label="Proteína" color={MACRO.protein} value={macros[group].protein} onChange={v => setMacro(group, 'protein', v)} />
            <Field label="Hidratos" color={MACRO.carbs} value={macros[group].carbs} onChange={v => setMacro(group, 'carbs', v)} />
            {withFat && <Field label="Grasas" color={MACRO.fat} value={macros[group].fat} onChange={v => setMacro(group, 'fat', v)} />}
        </div>
    </div>
);

// Mapa del activity_level legado (4 valores) a la escala nueva de 3 del quiz
const mapActividadLegacy = (nivel) => {
    if (!nivel) return null;
    if (nivel === 'sedentario') return 'sedentario';
    if (nivel === 'activo' || nivel === 'muy_activo') return 'muy_activo';
    return 'normal'; // ligero | moderado
};

const AJUSTES_VACIOS = {
    actividad_diaria: null, deporte_extra: null, facilidad_engordar: null,
    sigue_dieta: null, como_va: null,
    dieta_texto: '', dieta_hc_entreno: '', dieta_grasa_entreno: '',
};

const MacroCalculatorClientPage = () => {
    const { api, profile, can } = useAuth();
    const navigate = useNavigate();

    // ── Manual macros editor (the primary feature) ───────────────────────────
    const [macros, setMacros] = useState({
        training: { protein: '', carbs: '', fat: '' },
        rest: { protein: '', carbs: '', fat: '' },
        peri: { protein: '', carbs: '' },
    });
    const [effectiveDate, setEffectiveDate] = useState(todayISO());
    const [note, setNote] = useState('');
    // La portada de la pestaña es «Mis macros» (doc 19-08); esto abre el formulario.
    const [ajustando, setAjustando] = useState(false);
    const [loadingMacros, setLoadingMacros] = useState(true);
    const [saving, setSaving] = useState(false);
    // Macros escritos a mano y sin guardar. Si cambias la fecha de aplicacion NO se
    // pueden pisar con los de esa fecha: mas de una vez se ha guardado sin querer la
    // version vieja por eso.
    const [macrosTocados, setMacrosTocados] = useState(false);

    useEffect(() => {
        let alive = true;
        if (!effectiveDate) return;
        if (macrosTocados) { setLoadingMacros(false); return; }
        api.get('/macros', { params: { fecha: effectiveDate } }).then(res => {
            if (!alive || !res.data) return;
            const d = res.data;
            const pick = (m, a, b) => (m?.[a] ?? m?.[b] ?? '');
            setMacros({
                training: { protein: pick(d.training, 'protein', 'proteinas'), carbs: pick(d.training, 'carbs', 'hidratos'), fat: pick(d.training, 'fat', 'grasas') },
                rest: { protein: pick(d.rest, 'protein', 'proteinas'), carbs: pick(d.rest, 'carbs', 'hidratos'), fat: pick(d.rest, 'fat', 'grasas') },
                peri: { protein: pick(d.periworkout, 'protein', 'proteinas'), carbs: pick(d.periworkout, 'carbs', 'hidratos') },
            });
            setForm(prev => ({
                peso: d.peso != null ? String(d.peso) : '',
                porcentaje_graso: d.porcentaje_graso != null ? String(d.porcentaje_graso) : '',
                sexo: d.sexo || prev.sexo,
                objetivo: d.objetivo || prev.objetivo,
            }));
        }).catch(() => {}).finally(() => { if (alive) setLoadingMacros(false); });
        return () => { alive = false; };
    }, [api, effectiveDate]); // eslint-disable-line react-hooks/exhaustive-deps

    const setMacro = (group, key, value) => {
        setMacrosTocados(true);
        setMacros(prev => ({ ...prev, [group]: { ...prev[group], [key]: value } }));
    };

    const handleSaveMacros = async () => {
        const num = v => parseFloat(v);
        const t = macros.training, r = macros.rest, p = macros.peri;
        if ([t.protein, t.carbs, t.fat, r.protein, r.carbs, r.fat].some(v => isNaN(num(v)))) {
            toast.error('Completa proteínas, hidratos y grasas (entreno y descanso)');
            return;
        }
        if (!effectiveDate) { toast.error('Elige una fecha de aplicación'); return; }
        setSaving(true);
        try {
            const res = await api.put('/macros', {
                training: { protein: num(t.protein), carbs: num(t.carbs), fat: num(t.fat) },
                rest: { protein: num(r.protein), carbs: num(r.carbs), fat: num(r.fat) },
                peri: { protein: num(p.protein) || 0, carbs: num(p.carbs) || 0 },
                note: note || null,
                effective_date: effectiveDate,
                peso: isNaN(num(form.peso)) ? null : num(form.peso),
                porcentaje_graso: isNaN(num(form.porcentaje_graso)) ? null : num(form.porcentaje_graso),
                sexo: form.sexo || null,
                objetivo: form.objetivo || null,
                // Motor v2: las respuestas viajan con el guardado (se versionan en
                // macro_history y el servidor recalcula la revisión).
                ajustes: ajustesPayload(),
                desglose: results?.desglose || null,
            });
            toast.success(`Macros guardados desde ${effectiveDate}`);
            if (res.data?.revision_avisada) {
                toast.info('Tu dieta reportada no cuadra con lo recomendado: se ha avisado a tu entrenador para que lo revise.');
            }
            setNote('');
        } catch (err) {
            toast.error(mensajeDeError(err, 'Error guardando macros'));
        } finally {
            setSaving(false);
        }
    };

    // ── Calculator (helper) - fills the editor above ─────────────────────────
    const [form, setForm] = useState({ peso: '', porcentaje_graso: '', sexo: 'hombre', objetivo: 'volumen' });
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    // Su % graso vigente: lo decide el servidor (punto 47), incluido si ya toca pedirlo.
    const grasa = profile?.grasa || {};
    const grasaVale = grasa.valor != null && !grasa.hay_que_pedirlo;
    const [cambiarGrasa, setCambiarGrasa] = useState(false);
    const editorRef = useRef(null);

    // Preguntas 5-8 del quiz ("Ajusta tus macros"): mueven el motor v2.
    // Precarga: última versión guardada en el perfil; si no hay, mapea el
    // activity_level del cuestionario antiguo a la escala nueva de 3.
    const [ajustes, setAjustes] = useState(AJUSTES_VACIOS);
    // El resultado que hay en pantalla ya no corresponde a lo que está contestado.
    const [resultsViejos, setResultsViejos] = useState(false);
    const refResultados = useRef(null);
    // Las cinco preguntas contestadas. `sigue_dieta` puede ser `false` y eso ES una
    // respuesta, así que se compara contra null y no por si es "vacío".
    const ajustesCompletos = ['actividad_diaria', 'deporte_extra', 'facilidad_engordar', 'sigue_dieta', 'como_va']
        .every(k => ajustes[k] !== null && ajustes[k] !== undefined);
    useEffect(() => {
        const guardados = profile?.ajustes_macros;
        if (guardados) {
            setAjustes({
                ...AJUSTES_VACIOS,
                ...guardados,
                dieta_texto: guardados.dieta_texto || '',
                dieta_hc_entreno: guardados.dieta_hc_entreno ?? '',
                dieta_grasa_entreno: guardados.dieta_grasa_entreno ?? '',
            });
        } else if (profile?.activity_level) {
            setAjustes(prev => ({ ...prev, actividad_diaria: mapActividadLegacy(profile.activity_level) }));
        }
    }, [profile]);

    // Cambiar una respuesta NO borra el resultado: lo marca como viejo.
    //
    // Antes se hacía `setResults(null)` y el bloque entero desaparecía, con lo que la
    // página se encogía y la vista saltaba arriba. El ciclo era: contestar, bajar,
    // calcular, bajar otra vez (punto 15 del 07-08). Dejándolo en pantalla con el aviso de
    // que hay que recalcular, ni salta ni se pierde lo que ya había.
    const setAjuste = (field, value) => { setAjustes(prev => ({ ...prev, [field]: value })); setResultsViejos(true); };

    // Payload de ajustes para el backend (números parseados, vacíos como null)
    const ajustesPayload = () => {
        const num = v => { const n = parseFloat(v); return isNaN(n) ? null : n; };
        return {
            actividad_diaria: ajustes.actividad_diaria,
            deporte_extra: ajustes.deporte_extra,
            facilidad_engordar: ajustes.facilidad_engordar,
            sigue_dieta: ajustes.sigue_dieta,
            como_va: ajustes.como_va,
            // Los datos de la dieta solo viajan si TRAE una dieta de la que partir. Antes
            // bastaba con que `sigue_dieta` fuera truthy, y con cuatro respuestas
            // 'desorganizado' también lo es: se habrían mandado los gramos de una dieta que
            // el cliente acaba de decir que no lleva.
            dieta_texto: traeDieta(ajustes) ? (ajustes.dieta_texto || null) : null,
            dieta_hc_entreno: traeDieta(ajustes) ? num(ajustes.dieta_hc_entreno) : null,
            dieta_grasa_entreno: traeDieta(ajustes) ? num(ajustes.dieta_grasa_entreno) : null,
        };
    };

    const set = (field, value) => { setForm(prev => ({ ...prev, [field]: value })); setResultsViejos(true); };

    const handleCalculate = async () => {
        const peso = parseFloat(form.peso);
        // Si el suyo sigue valiendo y no ha querido cambiarlo, se usa ese (punto 47).
        const bf = (grasaVale && !cambiarGrasa) ? parseFloat(grasa.valor) : parseFloat(form.porcentaje_graso);
        if (!peso || peso < 30 || peso > 200) { toast.error('Peso inválido (30-200 kg)'); return; }
        if (isNaN(bf) || bf < 5 || bf > 60) { toast.error('% graso inválido (5-60%)'); return; }
        setLoading(true);
        try {
            const res = await api.post('/calculator/targets', {
                peso, porcentaje_graso: bf, sexo: form.sexo, objetivo: form.objetivo,
                ajustes: ajustesPayload(),
            });
            setResults(res.data);
            setResultsViejos(false);
            // Al resultado, sin que tenga que buscarlo: el bloque se pinta debajo del botón
            // y quedaba fuera de pantalla justo en el momento más importante del alta.
            setTimeout(() => refResultados.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 60);
        } catch (err) {
            toast.error(mensajeDeError(err, 'Error calculando macros'));
        } finally { setLoading(false); }
    };

    const useCalcResults = () => {
        if (!results) return;
        const e = results.macros.entreno, d = results.macros.descanso, pe = results.macros.perientreno;
        setMacros({
            training: { protein: Math.round(e.proteina), carbs: Math.round(e.hidratos), fat: Math.round(e.grasa) },
            rest: { protein: Math.round(d.proteina), carbs: Math.round(d.hidratos), fat: Math.round(d.grasa) },
            peri: { protein: Math.round(pe.proteina), carbs: Math.round(pe.hidratos) },
        });
        toast.success('Valores cargados en el editor - elige fecha y guarda');
        editorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    // ¿PUEDE ESTE CLIENTE AJUSTARSE LOS MACROS? (punto 4.10). Lo decide el servidor a partir
    // del campo `calculadora` de su plan.
    const ajustables = profile?.macros_ajustables;
    const puedeAjustar = ajustables ? ajustables.puede !== false : true;

    // «MIS MACROS» PARA TODOS, EN SOLO LECTURA PARA QUIEN NO EDITA (tarea 7.3 del 21-08,
    // hueco 1c). El doc 19-08 rebotaba al de coach a Seguimiento → Evolución; el de Jesús
    // lo revierte: la pestaña existe en todos los planes. Sin `onAjustar` no hay
    // formulario ni botón de guardar -- el candado `macros_ajustables.puede` sigue
    // mandando --, y el botón Revisar se enciende solo cuando su ciclo lo abre
    // (ventana_revision, la calcula el servidor).
    if (!puedeAjustar) return <MisMacrosPage />;

    // Y PARA QUIEN SÍ ES SU HERRAMIENTA, la portada es el mock del doc: última y próxima
    // revisión, el último ajuste en una frase, los ocho números, el histórico y «Ver mi
    // evolución». El formulario de ajustar queda a un botón. Quien todavía no tiene ningún
    // número entra directo al ajuste: no hay nada que resumir.
    if (!ajustando && profile?.macros_training) return <MisMacrosPage onAjustar={() => setAjustando(true)} />;

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-6 animate-fade-in">
            {/* Header */}
            <header className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-brand/10">
                    <SlidersHorizontal className="w-6 h-6 text-brand" />
                </div>
                <div>
                    <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none" data-testid="macros-heading">
                        Ajustar macros
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Modifica tus macros y elige desde qué fecha aplican
                    </p>
                    {/* Datos del perfil faltantes o imposibles (tarea 1.4): lo dice el
                        servidor en el perfil. Rótulo discreto, y el empujón a la pantalla
                        de completar que ya existe (solo rellena huecos). */}
                    {(profile?.datos_dudosos || []).length > 0 && (
                        <p className="text-xs text-amber-600 dark:text-amber-400 mt-1" data-testid="macros-provisionales">
                            Macros provisionales · Para poder darte tus macros definitivos necesitas completar tus datos.{' '}
                            <button type="button" onClick={() => navigate('/questionnaire?completar=1')}
                                className="underline font-semibold">
                                Completar mis datos
                            </button>
                        </p>
                    )}
                </div>
            </header>

            {/* MOMENTO 2 de la revisión suelta (documento del 06-08-2026): al recibir su
                ajuste del mes. Línea pequeña y sin botón, nunca un popup. La pantalla de
                venta entera vive en /dashboard/revision. */}
            {seLeOfreceLaRevision(profile, can) && (
                <p className="text-xs text-muted-foreground" data-testid="revision-personalizada">
                    El ajuste mira tus números.{' '}
                    <button onClick={() => navigate('/dashboard/revision')}
                        className="underline text-brand hover:text-brand/80 font-medium">
                        Solicita tu revisión personalizada
                    </button>{' '}
                    si quieres que lo miremos nosotros.
                </p>
            )}

            {loadingMacros ? (
                <div className="flex justify-center py-16"><Loader2 className="w-7 h-7 animate-spin text-muted-foreground" /></div>
            ) : (
                <div className="grid grid-cols-1 gap-6 items-start lg:grid-cols-2">
                    {/* ── Calculator (helper) ── */}
                    <section className="space-y-3">
                        <p className="caption flex items-center gap-2"><Calculator className="w-4 h-4" /> Calcula tus macros</p>
                        <div className="surface p-5 space-y-4" data-testid="macros-content">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">Peso (kg)</label>
                                    <input type="number" min="30" max="200" step="0.5" value={form.peso} onChange={e => set('peso', e.target.value)} placeholder="80" className="input-light font-data" />
                                </div>
                                {/* EL % GRASO SE PIDE CADA 12 SEMANAS, NO CADA 2 (punto 47 del
                                    doc del 07-08). Los ajustes son quincenales, así que antes
                                    se lo pedíamos seis veces por ciclo. Un dato que se estima
                                    a ojo mirando fotos no cambia cada quince días: preguntarlo
                                    tan seguido solo consigue que lo repita sin mirarlo o que
                                    se lo invente. Si el suyo tiene menos de 12 semanas se
                                    reutiliza y solo se le enseña, con la opción de cambiarlo. */}
                                <div>
                                    <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">% Graso</label>
                                    {grasaVale && !cambiarGrasa ? (
                                        <div className="input-light font-data flex items-center justify-between gap-2" data-testid="grasa-reutilizada">
                                            <span>{grasa.valor}%</span>
                                            <button type="button" onClick={() => setCambiarGrasa(true)}
                                                className="text-xs text-brand hover:underline font-sans normal-case tracking-normal">
                                                cambiar
                                            </button>
                                        </div>
                                    ) : (
                                        <input type="number" min="5" max="60" step="0.5" value={form.porcentaje_graso} onChange={e => set('porcentaje_graso', e.target.value)} placeholder="20" className="input-light font-data" />
                                    )}
                                    {grasaVale && !cambiarGrasa && (
                                        <p className="text-[11px] text-muted-foreground mt-1">
                                            {grasa.semanas === 0 ? 'De esta semana' : `De hace ${grasa.semanas} ${grasa.semanas === 1 ? 'semana' : 'semanas'}`}.
                                            {' '}Se vuelve a pedir a las 12.
                                        </p>
                                    )}
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">Sexo</label>
                                <ToggleGroup options={[{ value: 'hombre', label: 'Hombre' }, { value: 'mujer', label: 'Mujer' }]} value={form.sexo} onChange={v => set('sexo', v)} />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">Objetivo</label>
                                {/* Al cambiar de objetivo, «cómo te va» se borra: las respuestas
                                    de volumen ("subo pero muy lento") no existen en definición,
                                    y dejarla marcada mandaría al motor un valor que no está en
                                    su matriz -- que él descarta en silencio. */}
                                <ToggleGroup options={[{ value: 'volumen', label: 'Volumen' }, { value: 'definicion', label: 'Definición' }]}
                                    value={form.objetivo}
                                    onChange={v => {
                                        set('objetivo', v);
                                        if (!OPCIONES_COMO_VA(v).some(o => o.value === ajustes.como_va)) setAjuste('como_va', null);
                                    }} />
                            </div>

                            {/* Ajusta tus macros (preguntas 5-8 del quiz, motor v2) */}
                            <div className="border-t border-border pt-4 space-y-4" data-testid="ajusta-tus-macros">
                                <p className="caption">Ajusta tus macros</p>
                                <div>
                                    {/* LAS CUATRO, y con los textos de la pantalla 5 del documento
                                        (punto 4.1). Aquí había tres -- Sedentario / Normal / Muy
                                        activo -- y eso no es un detalle de redacción: el +10 % de
                                        hidratos lo cobra SOLO «muy activo», así que a quien está
                                        de pie todo el día no le quedaba más remedio que elegir
                                        entre «Normal» (correcto, +0 %) y «Muy activo» (+10 % que
                                        no le tocan). La opción que le corresponde -- moderadamente
                                        activo, que tampoco suma -- no existía en esta pantalla y
                                        sí en el cuestionario. */}
                                    <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">¿Cómo describirías tu nivel de actividad diaria?</label>
                                    <ToggleGroup vertical options={OPCIONES_ACTIVIDAD}
                                        value={ajustes.actividad_diaria} onChange={v => setAjuste('actividad_diaria', v)} />
                                    <p className="text-[11px] text-foreground/40 mt-1.5">
                                        Ir al gimnasio 1 hora 4-5 veces a la semana no te convierte en una persona
                                        activa, OJO. Piensa en lo mucho o lo poco que te mueves en tu día a día.
                                    </p>
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">¿Practicas otro deporte además de las pesas?</label>
                                    <ToggleGroup options={[{ value: true, label: 'Sí' }, { value: false, label: 'No' }]}
                                        value={ajustes.deporte_extra} onChange={v => setAjuste('deporte_extra', v)} />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">Cuando te pasas comiendo, ¿engordas?</label>
                                    <ToggleGroup options={[{ value: 'enseguida', label: 'Enseguida' }, { value: 'normal', label: 'Normal' }, { value: 'casi_no', label: 'Casi no' }]}
                                        value={ajustes.facilidad_engordar} onChange={v => setAjuste('facilidad_engordar', v)} />
                                </div>
                                <div>
                                    {/* LAS CUATRO RESPUESTAS (punto 19). Aquí seguía con Sí/No
                                        mientras el cuestionario de alta ya preguntaba las
                                        cuatro del documento de textos (06-08, pantalla 12), así
                                        que la misma pregunta daba respuestas distintas según
                                        por dónde entrara el cliente. Los valores son los
                                        mismos que allí para no romper lo ya guardado. */}
                                    <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">¿Sigues algún tipo de dieta en este momento?</label>
                                    <ToggleGroup vertical options={OPCIONES_DIETA}
                                        value={ajustes.sigue_dieta} onChange={v => setAjuste('sigue_dieta', v)} />
                                </div>
                                {traeDieta(ajustes) && (
                                    <div className="space-y-3 bg-muted/60 border border-border rounded-xl p-3">
                                        <div className="grid grid-cols-2 gap-3">
                                            <div>
                                                <label className="block text-[11px] font-bold text-muted-foreground uppercase tracking-wider mb-1.5">HC totales de tu día de entreno (g)</label>
                                                <input type="number" min="0" step="5" value={ajustes.dieta_hc_entreno}
                                                    onChange={e => setAjuste('dieta_hc_entreno', e.target.value)}
                                                    placeholder="250" className="input-light font-data" data-testid="dieta-hc-entreno" />
                                            </div>
                                            <div>
                                                <label className="block text-[11px] font-bold text-muted-foreground uppercase tracking-wider mb-1.5">Grasa aprox (g, opcional)</label>
                                                <input type="number" min="0" step="5" value={ajustes.dieta_grasa_entreno}
                                                    onChange={e => setAjuste('dieta_grasa_entreno', e.target.value)}
                                                    placeholder="60" className="input-light font-data" />
                                            </div>
                                        </div>
                                        <textarea value={ajustes.dieta_texto} onChange={e => setAjuste('dieta_texto', e.target.value)}
                                            placeholder="Ponnos un día tipo. El de ayer, por ejemplo (se guarda tal cual para tu entrenador)"
                                            rows={3} className="input-light resize-none text-sm" />
                                    </div>
                                )}
                                <div>
                                    <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">
                                        {traeDieta(ajustes)
                                            ? '¿Cómo te está funcionando?'
                                            : 'Con lo que comes ahora, ¿mantienes el peso, ganas o pierdes?'}
                                    </label>
                                    <ToggleGroup vertical options={OPCIONES_COMO_VA(form.objetivo)}
                                        value={ajustes.como_va} onChange={v => setAjuste('como_va', v)} />
                                    <p className="text-[11px] text-foreground/40 mt-1.5">
                                        Sé sincero: de esto depende que partamos de lo que comes o de lo que te toca comer.
                                    </p>
                                </div>
                            </div>

                            {/* Bloqueado hasta que estén contestadas las preguntas, no solo
                                el peso y la grasa (punto 14 del 07-08): sin ellas calculaba
                                igual y devolvía la tabla pelada, sin modificadores, y el
                                cliente se quedaba con unos macros que no son los suyos sin
                                enterarse de que le faltaba media pantalla. */}
                            {!ajustesCompletos && (
                                <p className="text-xs text-foreground/50 text-center" data-testid="faltan-preguntas">
                                    Contesta las preguntas de arriba para poder calcular.
                                </p>
                            )}
                            <button onClick={handleCalculate}
                                disabled={loading || !form.peso || !(form.porcentaje_graso || (grasaVale && !cambiarGrasa)) || !ajustesCompletos}
                                data-testid="btn-calcular"
                                className="btn-outline-brand w-full flex items-center justify-center gap-2 uppercase tracking-wider disabled:opacity-40">
                                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calculator className="w-4 h-4" />}
                                {loading ? 'Calculando...' : 'Calcular'}
                            </button>

                            {results && (
                                <div ref={refResultados} className={`space-y-3 pt-1 transition-opacity ${resultsViejos ? 'opacity-50' : ''}`}>
                                    {resultsViejos && (
                                        <p className="text-xs text-amber-400 text-center" data-testid="resultado-viejo">
                                            Has cambiado algo: vuelve a pulsar Calcular para actualizar estos números.
                                        </p>
                                    )}
                                    <div className="grid grid-cols-3 gap-2 text-center">
                                        {[
                                            ['Entreno', results.macros.entreno.proteina, results.macros.entreno.hidratos, results.macros.entreno.grasa],
                                            // «Perientreno», nunca «Peri» (punto 4.18): el bloque
                                            // se llamaba de tres maneras distintas por la app y
                                            // el cliente no tenía por qué saber que son lo mismo.
                                            ['Perientreno', results.macros.perientreno.proteina, results.macros.perientreno.hidratos, null],
                                            ['Descanso', results.macros.descanso.proteina, results.macros.descanso.hidratos, results.macros.descanso.grasa],
                                        ].map(([lbl, p, h, g]) => (
                                            <div key={lbl} className="bg-muted border border-border rounded-xl py-2.5">
                                                <p className="text-[10px] text-muted-foreground uppercase mb-1 font-semibold">{lbl}</p>
                                                <p className="text-foreground text-sm font-data font-semibold">{Math.round(p)}/{Math.round(h)}{g != null ? `/${Math.round(g)}` : ''}</p>
                                            </div>
                                        ))}
                                    </div>

                                    <DesgloseChips desglose={results.desglose} />

                                    {/* Dieta reportada: comparación con lo recomendado (humano en el bucle) */}
                                    {results.revision && (
                                        <div className={`rounded-xl border p-3 text-sm ${results.revision.requiere_revision ? 'bg-amber-500/10 border-amber-500/40' : 'bg-emerald-500/10 border-emerald-500/40'}`}
                                            data-testid="revision-dieta">
                                            <div className="grid grid-cols-3 gap-2 text-center mb-2">
                                                <div>
                                                    <p className="text-[10px] text-muted-foreground uppercase font-semibold">Comes (HC)</p>
                                                    <p className="font-data font-bold text-foreground">{Math.round(results.revision.hc_reportados)} g</p>
                                                </div>
                                                <div>
                                                    <p className="text-[10px] text-muted-foreground uppercase font-semibold">Recomendado</p>
                                                    <p className="font-data font-bold text-foreground">{results.revision.hc_recomendados} g</p>
                                                </div>
                                                <div>
                                                    <p className="text-[10px] text-muted-foreground uppercase font-semibold">Diferencia</p>
                                                    <p className="font-data font-bold text-foreground">{results.revision.diferencia > 0 ? '+' : ''}{results.revision.diferencia} g</p>
                                                </div>
                                            </div>
                                            <p className="text-xs text-muted-foreground">
                                                {results.revision.requiere_revision
                                                    ? 'No cuadra con lo esperado para tu % graso: al guardar se avisará a tu entrenador para que lo revise.'
                                                    : 'Tu dieta actual cuadra con lo recomendado: se aplica el reparto automáticamente.'}
                                            </p>
                                        </div>
                                    )}

                                    <button onClick={useCalcResults}
                                        className="w-full py-2.5 rounded-xl font-bold text-sm uppercase tracking-wider text-white flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-700 transition-all active:scale-[0.98]">
                                        <CheckCircle2 className="w-4 h-4" /> Usar estos valores
                                    </button>
                                </div>
                            )}
                        </div>
                    </section>

                    {/* ── Macros editor ── */}
                    <section ref={editorRef} className="space-y-3">
                        <p className="caption flex items-center gap-2"><SlidersHorizontal className="w-4 h-4" /> Mis macros</p>

                        <div className="surface p-4">
                            <label className="flex items-center gap-2 text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
                                <CalendarDays className="w-4 h-4 text-brand" /> Aplican desde
                            </label>
                            <input type="date" value={effectiveDate} onChange={e => setEffectiveDate(e.target.value)} className="input-light font-data" />
                            <p className="text-xs text-muted-foreground mt-2">Las dietas de ese día en adelante usarán estos macros. Las anteriores conservan los previos.</p>
                            {/* Si la fecha no es hoy hay que cantarlo: se han guardado macros
                                con fecha futura sin darse cuenta y el cliente seguia con los viejos. */}
                            {effectiveDate && effectiveDate !== todayISO() && (
                                <div className={`mt-3 rounded-xl border p-3 flex items-start gap-2 ${effectiveDate > todayISO() ? 'border-brand/50 bg-brand/10' : 'border-amber-500/50 bg-amber-500/10'}`}>
                                    <AlertTriangle className="w-4 h-4 text-brand flex-shrink-0 mt-0.5" />
                                    <div className="min-w-0">
                                        <p className="text-sm font-semibold text-foreground">
                                            {effectiveDate > todayISO()
                                                ? `Estos macros NO se aplican hasta el ${fechaLarga(effectiveDate)}.`
                                                : `Se aplicarán hacia atrás, desde el ${fechaLarga(effectiveDate)}.`}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-0.5">
                                            {effectiveDate > todayISO()
                                                ? 'Hasta ese día se seguirán usando los macros anteriores.'
                                                : 'Las dietas de esos días pasarán a usar estos macros.'}
                                        </p>
                                        <button type="button" onClick={() => setEffectiveDate(todayISO())}
                                            className="text-xs font-bold text-brand underline mt-1.5">Aplicar desde hoy</button>
                                    </div>
                                </div>
                            )}
                        </div>

                        <GroupCard label="Día entrenamiento" group="training" withFat macros={macros} setMacro={setMacro} />
                        <GroupCard label="Perientreno (intra + post)" group="peri" withFat={false} macros={macros} setMacro={setMacro} />
                        <GroupCard label="Día descanso" group="rest" withFat macros={macros} setMacro={setMacro} />

                        <input type="text" value={note} onChange={e => setNote(e.target.value)} placeholder="Motivo del cambio (opcional)" className="input-light" />

                        <button onClick={handleSaveMacros} disabled={saving}
                            className="btn-brand w-full flex items-center justify-center gap-2 uppercase tracking-wider"
                            data-testid="save-my-macros">
                            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                            {saving ? 'Guardando...' : 'Guardar macros'}
                        </button>
                    </section>
                </div>
            )}
        </div>
    );
};

export default MacroCalculatorClientPage;
