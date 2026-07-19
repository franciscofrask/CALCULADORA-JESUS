import React, { useState, useEffect, useRef } from 'react';
import { SlidersHorizontal, Calculator, Loader2, CheckCircle2, CalendarDays, Save } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { MACRO } from './ClientDashboard';
import DesgloseChips from '../components/DesgloseChips';

const todayISO = () => new Date().toISOString().slice(0, 10);

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
const ToggleGroup = ({ options, value, onChange }) => (
    <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${options.length}, 1fr)` }}>
        {options.map(o => (
            <button key={o.value} onClick={() => onChange(o.value)}
                className={`py-2.5 rounded-xl text-sm font-bold uppercase tracking-wider transition-all border ${value === o.value ? 'bg-brand text-white border-brand' : 'bg-card text-muted-foreground border-border hover:border-neutral-400'}`}>
                {o.label}
            </button>
        ))}
    </div>
);

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
    sigue_dieta: null, dieta_texto: '', dieta_hc_entreno: '', dieta_grasa_entreno: '',
};

const MacroCalculatorClientPage = () => {
    const { api, profile } = useAuth();

    // ── Manual macros editor (the primary feature) ───────────────────────────
    const [macros, setMacros] = useState({
        training: { protein: '', carbs: '', fat: '' },
        rest: { protein: '', carbs: '', fat: '' },
        peri: { protein: '', carbs: '' },
    });
    const [effectiveDate, setEffectiveDate] = useState(todayISO());
    const [note, setNote] = useState('');
    const [loadingMacros, setLoadingMacros] = useState(true);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        let alive = true;
        if (!effectiveDate) return;
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
    }, [api, effectiveDate]);

    const setMacro = (group, key, value) =>
        setMacros(prev => ({ ...prev, [group]: { ...prev[group], [key]: value } }));

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
            toast.error(err.response?.data?.detail || 'Error guardando macros');
        } finally {
            setSaving(false);
        }
    };

    // ── Calculator (helper) - fills the editor above ─────────────────────────
    const [form, setForm] = useState({ peso: '', porcentaje_graso: '', sexo: 'hombre', objetivo: 'volumen' });
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const editorRef = useRef(null);

    // Preguntas 5-8 del quiz ("Afina tus macros"): mueven el motor v2.
    // Precarga: última versión guardada en el perfil; si no hay, mapea el
    // activity_level del cuestionario antiguo a la escala nueva de 3.
    const [ajustes, setAjustes] = useState(AJUSTES_VACIOS);
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

    const setAjuste = (field, value) => { setAjustes(prev => ({ ...prev, [field]: value })); setResults(null); };

    // Payload de ajustes para el backend (números parseados, vacíos como null)
    const ajustesPayload = () => {
        const num = v => { const n = parseFloat(v); return isNaN(n) ? null : n; };
        return {
            actividad_diaria: ajustes.actividad_diaria,
            deporte_extra: ajustes.deporte_extra,
            facilidad_engordar: ajustes.facilidad_engordar,
            sigue_dieta: ajustes.sigue_dieta,
            dieta_texto: ajustes.sigue_dieta ? (ajustes.dieta_texto || null) : null,
            dieta_hc_entreno: ajustes.sigue_dieta ? num(ajustes.dieta_hc_entreno) : null,
            dieta_grasa_entreno: ajustes.sigue_dieta ? num(ajustes.dieta_grasa_entreno) : null,
        };
    };

    const set = (field, value) => { setForm(prev => ({ ...prev, [field]: value })); setResults(null); };

    const handleCalculate = async () => {
        const peso = parseFloat(form.peso);
        const bf = parseFloat(form.porcentaje_graso);
        if (!peso || peso < 30 || peso > 200) { toast.error('Peso inválido (30-200 kg)'); return; }
        if (isNaN(bf) || bf < 5 || bf > 60) { toast.error('% graso inválido (5-60%)'); return; }
        setLoading(true);
        try {
            const res = await api.post('/calculator/targets', {
                peso, porcentaje_graso: bf, sexo: form.sexo, objetivo: form.objetivo,
                ajustes: ajustesPayload(),
            });
            setResults(res.data);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Error calculando macros');
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

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-6 animate-fade-in">
            {/* Header */}
            <header className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-brand/10">
                    <SlidersHorizontal className="w-6 h-6 text-brand" />
                </div>
                <div>
                    <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none" data-testid="macros-heading">Ajustar macros</h1>
                    <p className="text-sm text-muted-foreground mt-1">Modifica tus macros y elige desde qué fecha aplican</p>
                </div>
            </header>

            {loadingMacros ? (
                <div className="flex justify-center py-16"><Loader2 className="w-7 h-7 animate-spin text-muted-foreground" /></div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                    {/* ── Calculator (helper) ── */}
                    <section className="space-y-3">
                        <p className="caption flex items-center gap-2"><Calculator className="w-4 h-4" /> Calcula tus macros</p>
                        <div className="surface p-5 space-y-4" data-testid="macros-content">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">Peso (kg)</label>
                                    <input type="number" min="30" max="200" step="0.5" value={form.peso} onChange={e => set('peso', e.target.value)} placeholder="80" className="input-light font-data" />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">% Graso</label>
                                    <input type="number" min="5" max="60" step="0.5" value={form.porcentaje_graso} onChange={e => set('porcentaje_graso', e.target.value)} placeholder="20" className="input-light font-data" />
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">Sexo</label>
                                <ToggleGroup options={[{ value: 'hombre', label: 'Hombre' }, { value: 'mujer', label: 'Mujer' }]} value={form.sexo} onChange={v => set('sexo', v)} />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">Objetivo</label>
                                <ToggleGroup options={[{ value: 'volumen', label: 'Volumen' }, { value: 'definicion', label: 'Definición' }]} value={form.objetivo} onChange={v => set('objetivo', v)} />
                            </div>

                            {/* Afina tus macros (preguntas 5-8 del quiz, motor v2) */}
                            <div className="border-t border-border pt-4 space-y-4" data-testid="afina-tus-macros">
                                <p className="caption">Afina tus macros</p>
                                <div>
                                    <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">Actividad diaria (fuera del gym)</label>
                                    <ToggleGroup options={[{ value: 'sedentario', label: 'Sedentario' }, { value: 'normal', label: 'Normal' }, { value: 'muy_activo', label: 'Muy activo' }]}
                                        value={ajustes.actividad_diaria} onChange={v => setAjuste('actividad_diaria', v)} />
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
                                    <label className="block text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1.5">¿Sigues una dieta ahora y sabes lo que comes?</label>
                                    <ToggleGroup options={[{ value: true, label: 'Sí' }, { value: false, label: 'No' }]}
                                        value={ajustes.sigue_dieta} onChange={v => setAjuste('sigue_dieta', v)} />
                                </div>
                                {ajustes.sigue_dieta && (
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
                                            placeholder="Cuéntanos qué comes en un día normal (se guarda tal cual para tu entrenador)"
                                            rows={3} className="input-light resize-none text-sm" />
                                    </div>
                                )}
                            </div>

                            <button onClick={handleCalculate} disabled={loading || !form.peso || !form.porcentaje_graso}
                                className="btn-outline-brand w-full flex items-center justify-center gap-2 uppercase tracking-wider disabled:opacity-40">
                                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calculator className="w-4 h-4" />}
                                {loading ? 'Calculando...' : 'Calcular'}
                            </button>

                            {results && (
                                <div className="space-y-3 pt-1">
                                    <div className="grid grid-cols-3 gap-2 text-center">
                                        {[
                                            ['Entreno', results.macros.entreno.proteina, results.macros.entreno.hidratos, results.macros.entreno.grasa],
                                            ['Peri', results.macros.perientreno.proteina, results.macros.perientreno.hidratos, null],
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
