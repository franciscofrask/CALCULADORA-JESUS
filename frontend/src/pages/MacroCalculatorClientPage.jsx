import React, { useState, useEffect, useRef } from 'react';
import { SlidersHorizontal, Calculator, Loader2, CheckCircle2, CalendarDays, Save } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';

const ORANGE = '#FF671F';
const todayISO = () => new Date().toISOString().slice(0, 10);

// One macro input cell (P/H/G)
const Field = ({ label, color, value, onChange, suffix = 'g' }) => (
    <div>
        <label className="block text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color }}>{label}</label>
        <div className="relative">
            <input
                type="number" min="0" step="1" value={value}
                onChange={e => onChange(e.target.value)}
                className="w-full bg-[#1A1A1A] border border-[#333] rounded-xl px-3 py-2.5 text-white text-sm focus:outline-none focus:border-[#FF671F] transition-colors"
                placeholder="0"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-white/30">{suffix}</span>
        </div>
    </div>
);

// Module-level (NOT redefined per render) so inputs keep focus while typing.
const ToggleGroup = ({ options, value, onChange }) => (
    <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${options.length}, 1fr)` }}>
        {options.map(o => (
            <button key={o.value} onClick={() => onChange(o.value)}
                className={`py-2.5 rounded-xl text-sm font-bold uppercase tracking-wider transition-all ${value === o.value ? 'text-white' : 'bg-[#1A1A1A] text-white/40 hover:text-white/70'}`}
                style={value === o.value ? { backgroundColor: ORANGE } : {}}>
                {o.label}
            </button>
        ))}
    </div>
);

const GroupCard = ({ label, group, withFat, macros, setMacro }) => (
    <div className="bg-[#111111] border border-[#222] rounded-2xl p-4">
        <p className="text-xs font-bold uppercase tracking-widest mb-3 text-white/40">{label}</p>
        <div className={`grid gap-2 ${withFat ? 'grid-cols-3' : 'grid-cols-2'}`}>
            <Field label="Proteína" color="#3B82F6" value={macros[group].protein} onChange={v => setMacro(group, 'protein', v)} />
            <Field label="Hidratos" color="#F59E0B" value={macros[group].carbs} onChange={v => setMacro(group, 'carbs', v)} />
            {withFat && <Field label="Grasas" color="#EF4444" value={macros[group].fat} onChange={v => setMacro(group, 'fat', v)} />}
        </div>
    </div>
);

const MacroCalculatorClientPage = () => {
    const { api } = useAuth();

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

    // Preload the macros EFFECTIVE for the chosen date (date-versioned). Re-runs when the date
    // changes so the editor always shows that day's assigned macros, editable.
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
            // Precargar la calculadora con los inputs guardados de ese día (trazabilidad).
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
            await api.put('/macros', {
                training: { protein: num(t.protein), carbs: num(t.carbs), fat: num(t.fat) },
                rest: { protein: num(r.protein), carbs: num(r.carbs), fat: num(r.fat) },
                peri: { protein: num(p.protein) || 0, carbs: num(p.carbs) || 0 },
                note: note || null,
                effective_date: effectiveDate,
                // Inputs para trazabilidad del cambio (cómo se derivaron estos macros).
                peso: isNaN(num(form.peso)) ? null : num(form.peso),
                porcentaje_graso: isNaN(num(form.porcentaje_graso)) ? null : num(form.porcentaje_graso),
                sexo: form.sexo || null,
                objetivo: form.objetivo || null,
            });
            toast.success(`Macros guardados desde ${effectiveDate}`);
            setNote('');
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Error guardando macros');
        } finally {
            setSaving(false);
        }
    };

    // ── Calculator (helper) — fills the editor above ─────────────────────────
    const [form, setForm] = useState({ peso: '', porcentaje_graso: '', sexo: 'hombre', objetivo: 'volumen' });
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const editorRef = useRef(null);

    const set = (field, value) => { setForm(prev => ({ ...prev, [field]: value })); setResults(null); };

    const handleCalculate = async () => {
        const peso = parseFloat(form.peso);
        const bf = parseFloat(form.porcentaje_graso);
        if (!peso || peso < 30 || peso > 200) { toast.error('Peso inválido (30–200 kg)'); return; }
        if (isNaN(bf) || bf < 5 || bf > 60) { toast.error('% graso inválido (5–60%)'); return; }
        setLoading(true);
        try {
            const res = await api.post('/calculator/targets', { peso, porcentaje_graso: bf, sexo: form.sexo, objetivo: form.objetivo });
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
        toast.success('Valores cargados en el editor — elige fecha y guarda');
        editorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    return (
        <div className="px-4 pt-6 pb-28 max-w-md mx-auto space-y-4">
            {/* Header */}
            <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${ORANGE}20` }}>
                    <SlidersHorizontal className="w-5 h-5" style={{ color: ORANGE }} />
                </div>
                <div>
                    <h1 className="text-xl font-bold text-white" style={{ fontFamily: 'Bebas Neue', letterSpacing: '0.05em' }}>AJUSTAR MACROS</h1>
                    <p className="text-xs text-white/30">Modifica tus macros y elige desde qué fecha aplican</p>
                </div>
            </div>

            {loadingMacros ? (
                <div className="flex justify-center py-10"><Loader2 className="w-6 h-6 animate-spin text-white/40" /></div>
            ) : (
                <>
                    {/* ── 1. Calculator ── */}
                    <div>
                        <p className="text-xs font-bold text-white/30 uppercase tracking-widest mb-2 flex items-center gap-2">
                            <Calculator className="w-4 h-4" /> Calcula tus macros
                        </p>
                        <div className="bg-[#111111] border border-[#222] rounded-2xl p-4 space-y-4">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-bold text-white/40 uppercase tracking-wider mb-1.5">Peso (kg)</label>
                                    <input type="number" min="30" max="200" step="0.5" value={form.peso} onChange={e => set('peso', e.target.value)} placeholder="80"
                                        className="w-full bg-[#1A1A1A] border border-[#333] rounded-xl px-3 py-2.5 text-white text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors" />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-white/40 uppercase tracking-wider mb-1.5">% Graso</label>
                                    <input type="number" min="5" max="60" step="0.5" value={form.porcentaje_graso} onChange={e => set('porcentaje_graso', e.target.value)} placeholder="20"
                                        className="w-full bg-[#1A1A1A] border border-[#333] rounded-xl px-3 py-2.5 text-white text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors" />
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-white/40 uppercase tracking-wider mb-1.5">Sexo</label>
                                <ToggleGroup options={[{ value: 'hombre', label: 'Hombre' }, { value: 'mujer', label: 'Mujer' }]} value={form.sexo} onChange={v => set('sexo', v)} />
                            </div>
                            <div>
                                <label className="block text-xs font-bold text-white/40 uppercase tracking-wider mb-1.5">Objetivo</label>
                                <ToggleGroup options={[{ value: 'volumen', label: 'Volumen' }, { value: 'definicion', label: 'Definición' }]} value={form.objetivo} onChange={v => set('objetivo', v)} />
                            </div>
                            <button onClick={handleCalculate} disabled={loading || !form.peso || !form.porcentaje_graso}
                                className="w-full py-3 rounded-xl font-bold text-sm uppercase tracking-wider bg-[#1A1A1A] border border-[#333] text-white flex items-center justify-center gap-2 transition-all disabled:opacity-40 hover:border-[#FF671F]">
                                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calculator className="w-4 h-4" />}
                                {loading ? 'Calculando...' : 'Calcular'}
                            </button>

                            {results && (
                                <div className="space-y-2 pt-1">
                                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                                        {[
                                            ['Entreno', results.macros.entreno.proteina, results.macros.entreno.hidratos, results.macros.entreno.grasa],
                                            ['Peri', results.macros.perientreno.proteina, results.macros.perientreno.hidratos, null],
                                            ['Descanso', results.macros.descanso.proteina, results.macros.descanso.hidratos, results.macros.descanso.grasa],
                                        ].map(([lbl, p, h, g]) => (
                                            <div key={lbl} className="bg-[#1A1A1A] rounded-xl py-2">
                                                <p className="text-[10px] text-white/30 uppercase mb-1">{lbl}</p>
                                                <p className="text-white/80">{Math.round(p)}/{Math.round(h)}{g != null ? `/${Math.round(g)}` : ''}</p>
                                            </div>
                                        ))}
                                    </div>
                                    <button onClick={useCalcResults}
                                        className="w-full py-2.5 rounded-xl font-bold text-sm uppercase tracking-wider text-white flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 transition-all">
                                        <CheckCircle2 className="w-4 h-4" /> Usar estos valores
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* ── 2. Macros editor ── */}
                    <div ref={editorRef} className="space-y-4 pt-2">
                        <p className="text-xs font-bold text-white/30 uppercase tracking-widest flex items-center gap-2">
                            <SlidersHorizontal className="w-4 h-4" /> Mis macros
                        </p>

                        {/* Effective date */}
                        <div className="bg-[#111111] border border-[#222] rounded-2xl p-4">
                            <label className="flex items-center gap-2 text-xs font-bold text-white/40 uppercase tracking-wider mb-2">
                                <CalendarDays className="w-4 h-4" style={{ color: ORANGE }} /> Aplican desde
                            </label>
                            <input
                                type="date" value={effectiveDate} onChange={e => setEffectiveDate(e.target.value)}
                                className="w-full bg-[#1A1A1A] border border-[#333] rounded-xl px-3 py-2.5 text-white text-sm focus:outline-none focus:border-[#FF671F] transition-colors [color-scheme:dark]"
                            />
                            <p className="text-[11px] text-white/30 mt-2">Las dietas de ese día en adelante usarán estos macros. Las anteriores conservan los previos.</p>
                        </div>

                        {/* Editor */}
                        <GroupCard label="Día entrenamiento" group="training" withFat macros={macros} setMacro={setMacro} />
                        <GroupCard label="Día descanso" group="rest" withFat macros={macros} setMacro={setMacro} />
                        <GroupCard label="Perientreno (intra + post)" group="peri" withFat={false} macros={macros} setMacro={setMacro} />

                        {/* Note */}
                        <input
                            type="text" value={note} onChange={e => setNote(e.target.value)}
                            placeholder="Motivo del cambio (opcional)"
                            className="w-full bg-[#1A1A1A] border border-[#333] rounded-xl px-3 py-2.5 text-white text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors"
                        />

                        {/* Save */}
                        <button
                            onClick={handleSaveMacros} disabled={saving}
                            className="w-full py-3 rounded-xl font-bold text-sm uppercase tracking-wider text-white flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                            style={{ backgroundColor: ORANGE }}
                            data-testid="save-my-macros"
                        >
                            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                            {saving ? 'Guardando...' : 'Guardar macros'}
                        </button>
                    </div>
                </>
            )}
        </div>
    );
};

export default MacroCalculatorClientPage;
