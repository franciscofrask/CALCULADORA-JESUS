import React, { useState } from 'react';
import { Calculator, Loader2, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';

const ORANGE = '#FF671F';

const MacroCard = ({ label, P, H, G, kcal, accent }) => (
    <div className={`rounded-2xl p-4 border ${accent ? 'border-[#FF671F]/40 bg-[#FF671F]/5' : 'border-[#222] bg-[#111111]'}`}>
        <p className={`text-xs font-bold uppercase tracking-widest mb-3 ${accent ? 'text-[#FF671F]' : 'text-white/40'}`}>
            {label}
        </p>
        <div className="grid grid-cols-3 gap-2 text-center">
            {[
                { key: 'P', val: P, color: '#3B82F6' },
                { key: 'H', val: H, color: '#F59E0B' },
                { key: 'G', val: G, color: '#EF4444' },
            ].map(({ key, val, color }) => val !== undefined && (
                <div key={key} className="bg-[#1A1A1A] rounded-xl py-3">
                    <p className="text-2xl font-bold" style={{ color, fontFamily: 'Bebas Neue' }}>
                        {Math.round(val)}
                    </p>
                    <p className="text-xs text-white/30 mt-0.5">{key}</p>
                </div>
            ))}
        </div>
        {kcal !== undefined && (
            <p className="text-center text-xs text-white/30 mt-2">{Math.round(kcal)} kcal</p>
        )}
    </div>
);

const MacroCalculatorClientPage = () => {
    const { api } = useAuth();

    const [form, setForm] = useState({
        peso: '',
        porcentaje_graso: '',
        sexo: 'hombre',
        objetivo: 'volumen',
    });
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [applying, setApplying] = useState(false);
    const [applied, setApplied] = useState(false);

    const set = (field, value) => {
        setForm(prev => ({ ...prev, [field]: value }));
        setResults(null);
        setApplied(false);
    };

    const handleCalculate = async () => {
        const peso = parseFloat(form.peso);
        const bf = parseFloat(form.porcentaje_graso);
        if (!peso || peso < 30 || peso > 200) { toast.error('Peso inválido (30–200 kg)'); return; }
        if (isNaN(bf) || bf < 5 || bf > 60) { toast.error('% graso inválido (5–60%)'); return; }
        setLoading(true);
        try {
            const res = await api.post('/calculator/targets', {
                peso, porcentaje_graso: bf, sexo: form.sexo, objetivo: form.objetivo,
            });
            setResults(res.data);
            setApplied(false);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Error calculando macros');
        } finally {
            setLoading(false);
        }
    };

    const handleApply = async () => {
        if (!results) return;
        setApplying(true);
        try {
            await api.post('/calculator/targets/apply', {
                peso: parseFloat(form.peso),
                porcentaje_graso: parseFloat(form.porcentaje_graso),
                sexo: form.sexo,
                objetivo: form.objetivo,
            });
            setApplied(true);
            toast.success('Macros aplicados a tu perfil');
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Error aplicando macros');
        } finally {
            setApplying(false);
        }
    };

    const kcal_entreno = results
        ? results.macros.entreno.proteina * 4 + results.macros.entreno.hidratos * 4 + results.macros.entreno.grasa * 9
        : 0;
    const kcal_descanso = results
        ? results.macros.descanso.proteina * 4 + results.macros.descanso.hidratos * 4 + results.macros.descanso.grasa * 9
        : 0;

    const ToggleGroup = ({ options, value, onChange }) => (
        <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${options.length}, 1fr)` }}>
            {options.map(o => (
                <button
                    key={o.value}
                    onClick={() => onChange(o.value)}
                    className={`py-2.5 rounded-xl text-sm font-bold uppercase tracking-wider transition-all ${
                        value === o.value
                            ? 'text-white'
                            : 'bg-[#1A1A1A] text-white/40 hover:text-white/70'
                    }`}
                    style={value === o.value ? { backgroundColor: ORANGE } : {}}
                >
                    {o.label}
                </button>
            ))}
        </div>
    );

    return (
        <div className="px-4 pt-6 pb-28 max-w-md mx-auto space-y-4">
            {/* Header */}
            <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${ORANGE}20` }}>
                    <Calculator className="w-5 h-5" style={{ color: ORANGE }} />
                </div>
                <div>
                    <h1 className="text-xl font-bold text-white" style={{ fontFamily: 'Bebas Neue', letterSpacing: '0.05em' }}>
                        CALCULADORA DE MACROS
                    </h1>
                    <p className="text-xs text-white/30">Método Jesús Gallego</p>
                </div>
            </div>

            {/* Form */}
            <div className="bg-[#111111] border border-[#222] rounded-2xl p-4 space-y-4">
                {/* Peso + % graso */}
                <div className="grid grid-cols-2 gap-3">
                    <div>
                        <label className="block text-xs font-bold text-white/40 uppercase tracking-wider mb-1.5">Peso (kg)</label>
                        <input
                            type="number"
                            min="30" max="200" step="0.5"
                            value={form.peso}
                            onChange={e => set('peso', e.target.value)}
                            placeholder="80"
                            className="w-full bg-[#1A1A1A] border border-[#333] rounded-xl px-3 py-2.5 text-white text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors"
                        />
                    </div>
                    <div>
                        <label className="block text-xs font-bold text-white/40 uppercase tracking-wider mb-1.5">% Graso</label>
                        <input
                            type="number"
                            min="5" max="60" step="0.5"
                            value={form.porcentaje_graso}
                            onChange={e => set('porcentaje_graso', e.target.value)}
                            placeholder="20"
                            className="w-full bg-[#1A1A1A] border border-[#333] rounded-xl px-3 py-2.5 text-white text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors"
                        />
                    </div>
                </div>

                {/* Sexo */}
                <div>
                    <label className="block text-xs font-bold text-white/40 uppercase tracking-wider mb-1.5">Sexo</label>
                    <ToggleGroup
                        options={[{ value: 'hombre', label: 'Hombre' }, { value: 'mujer', label: 'Mujer' }]}
                        value={form.sexo}
                        onChange={v => set('sexo', v)}
                    />
                </div>

                {/* Objetivo */}
                <div>
                    <label className="block text-xs font-bold text-white/40 uppercase tracking-wider mb-1.5">Objetivo</label>
                    <ToggleGroup
                        options={[{ value: 'volumen', label: 'Volumen' }, { value: 'definicion', label: 'Definición' }]}
                        value={form.objetivo}
                        onChange={v => set('objetivo', v)}
                    />
                </div>

                {/* Calcular */}
                <button
                    onClick={handleCalculate}
                    disabled={loading || !form.peso || !form.porcentaje_graso}
                    className="w-full py-3 rounded-xl font-bold text-sm uppercase tracking-wider text-white flex items-center justify-center gap-2 transition-all disabled:opacity-40"
                    style={{ backgroundColor: ORANGE }}
                >
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calculator className="w-4 h-4" />}
                    {loading ? 'Calculando...' : 'Calcular mis macros'}
                </button>
            </div>

            {/* Results */}
            {results && (
                <div className="space-y-3">
                    {/* Composición */}
                    <div className="bg-[#111111] border border-[#222] rounded-2xl p-4">
                        <p className="text-xs font-bold text-white/40 uppercase tracking-widest mb-3">Composición corporal</p>
                        <div className="grid grid-cols-3 gap-2 text-center">
                            {[
                                { label: 'Masa magra', val: results.derivacion.masa_magra },
                                { label: 'Masa grasa', val: results.derivacion.masa_grasa },
                                { label: 'M. trabajo', val: results.derivacion.masa_trabajo },
                            ].map(({ label, val }) => (
                                <div key={label} className="bg-[#1A1A1A] rounded-xl py-2.5">
                                    <p className="text-lg font-bold text-white" style={{ fontFamily: 'Bebas Neue' }}>
                                        {val.toFixed(1)}
                                    </p>
                                    <p className="text-[10px] text-white/30 uppercase">{label}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    <MacroCard
                        label="Día entrenamiento"
                        P={results.macros.entreno.proteina}
                        H={results.macros.entreno.hidratos}
                        G={results.macros.entreno.grasa}
                        kcal={kcal_entreno}
                        accent
                    />
                    <MacroCard
                        label="Perientreno"
                        P={results.macros.perientreno.proteina}
                        H={results.macros.perientreno.hidratos}
                    />
                    <MacroCard
                        label="Día descanso"
                        P={results.macros.descanso.proteina}
                        H={results.macros.descanso.hidratos}
                        G={results.macros.descanso.grasa}
                        kcal={kcal_descanso}
                    />

                    {/* Apply */}
                    <button
                        onClick={handleApply}
                        disabled={applying || applied}
                        className={`w-full py-3 rounded-xl font-bold text-sm uppercase tracking-wider text-white flex items-center justify-center gap-2 transition-all disabled:opacity-60 ${
                            applied ? 'bg-green-600' : 'bg-[#1A1A1A] border border-[#333] hover:border-[#FF671F]'
                        }`}
                    >
                        {applying ? <Loader2 className="w-4 h-4 animate-spin" /> : applied ? <CheckCircle2 className="w-4 h-4" /> : null}
                        {applying ? 'Aplicando...' : applied ? 'Macros aplicados' : 'Aplicar a mi perfil'}
                    </button>
                    {applied && (
                        <p className="text-center text-xs text-white/30">
                            Tus macros de nutrición se actualizaron con estos valores.
                        </p>
                    )}
                </div>
            )}
        </div>
    );
};

export default MacroCalculatorClientPage;
