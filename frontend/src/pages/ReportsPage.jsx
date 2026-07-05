import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import {
    FileText, TrendingUp, Scale, Ruler,
    Activity, Moon, Zap, Brain, Send, ChevronRight,
    Calendar
} from 'lucide-react';

const ORANGE = '#FF671F';

const inputCls = "w-full bg-muted border border-input rounded-xl px-3 py-2.5 text-foreground text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors";
const labelCls = "block text-xs font-bold text-foreground/40 uppercase tracking-wider mb-1.5";

const SliderRow = ({ icon: Icon, iconColor, label, value, max, unit, onChange }) => (
    <div>
        <div className="flex items-center justify-between mb-2">
            <span className="flex items-center gap-2 text-sm text-foreground/70">
                <Icon className="w-4 h-4" style={{ color: iconColor }} />
                {label}
            </span>
            <span className="font-bold text-sm" style={{ color: iconColor }}>{value}{unit}</span>
        </div>
        <input
            type="range"
            min={0}
            max={max}
            step={max === 10 ? 1 : 5}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            className="w-full h-2 rounded-full appearance-none cursor-pointer"
            style={{
                background: `linear-gradient(to right, ${iconColor} 0%, ${iconColor} ${value / max * 100}%, #333 ${value / max * 100}%, #333 100%)`
            }}
        />
    </div>
);

const ReportsPage = () => {
    const { api } = useAuth();
    const [reports, setReports] = useState([]);
    const [evolution, setEvolution] = useState(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [activeTab, setActiveTab] = useState('form');

    const [reportData, setReportData] = useState({
        weight: '',
        measurements: { chest: '', waist: '', hip: '', arm: '', thigh: '' },
        training_compliance: 80,
        nutrition_compliance: 80,
        sleep_quality: 7,
        energy_level: 7,
        stress_level: 5,
        notes: ''
    });

    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetch solo al montar
    useEffect(() => { fetchData(); }, []);

    const fetchData = async () => {
        try {
            const [reportsRes, evolutionRes] = await Promise.all([
                api.get('/reports'),
                api.get('/reports/evolution')
            ]);
            setReports(reportsRes.data);
            setEvolution(evolutionRes.data);
        } catch (error) {
            console.error('Error fetching reports:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!reportData.weight) { toast.error('El peso es obligatorio'); return; }
        setSubmitting(true);
        try {
            const payload = {
                weight: parseFloat(reportData.weight),
                measurements: Object.fromEntries(
                    Object.entries(reportData.measurements)
                        .filter(([_, v]) => v)
                        .map(([k, v]) => [k, parseFloat(v)])
                ),
                training_compliance: reportData.training_compliance,
                nutrition_compliance: reportData.nutrition_compliance,
                sleep_quality: reportData.sleep_quality,
                energy_level: reportData.energy_level,
                stress_level: reportData.stress_level,
                notes: reportData.notes || null
            };
            await api.post('/reports', payload);
            toast.success('Reporte enviado correctamente');
            fetchData();
            setActiveTab('history');
            setReportData({
                weight: '',
                measurements: { chest: '', waist: '', hip: '', arm: '', thigh: '' },
                training_compliance: 80,
                nutrition_compliance: 80,
                sleep_quality: 7,
                energy_level: 7,
                stress_level: 5,
                notes: ''
            });
        } catch (error) {
            toast.error('Error al enviar el reporte');
        } finally {
            setSubmitting(false);
        }
    };

    const set = (field, value) => setReportData(prev => ({ ...prev, [field]: value }));

    const weightData = evolution?.weight?.map(w => ({
        date: new Date(w.date).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }),
        peso: w.value
    })) || [];

    const tabs = [
        { id: 'form', icon: FileText, label: 'Nuevo' },
        { id: 'evolution', icon: TrendingUp, label: 'Evolución' },
        { id: 'history', icon: Calendar, label: 'Historial' },
    ];

    if (loading) {
        return (
            <div className="px-4 pt-6 pb-28">
                <div className="animate-pulse space-y-4">
                    <div className="h-8 bg-muted rounded w-1/3" />
                    <div className="h-48 bg-card rounded-2xl" />
                </div>
            </div>
        );
    }

    return (
        <div className="px-4 pt-6 pb-28 max-w-md mx-auto space-y-4">
            {/* Header */}
            <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${ORANGE}20` }}>
                    <FileText className="w-5 h-5" style={{ color: ORANGE }} />
                </div>
                <div>
                    <h1 className="text-xl font-bold text-foreground" style={{ fontFamily: 'Barlow Condensed', letterSpacing: '0.05em' }} data-testid="reports-heading">
                        MIS REPORTES
                    </h1>
                    <p className="text-xs text-foreground/30">Seguimiento semanal</p>
                </div>
            </div>

            {/* Tab bar */}
            <div className="grid grid-cols-3 gap-1 bg-card border border-border rounded-2xl p-1">
                {tabs.map(({ id, icon: Icon, label }) => (
                    <button
                        key={id}
                        onClick={() => setActiveTab(id)}
                        className={`flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all ${
                            activeTab === id ? 'text-foreground' : 'text-foreground/40 hover:text-foreground/70'
                        }`}
                        style={activeTab === id ? { backgroundColor: ORANGE } : {}}
                    >
                        <Icon className="w-3.5 h-3.5" />
                        {label}
                    </button>
                ))}
            </div>

            {/* ── FORM TAB ── */}
            {activeTab === 'form' && (
                <form onSubmit={handleSubmit} className="space-y-4">
                    {/* Weight */}
                    <div className="bg-card border border-border rounded-2xl p-4">
                        <div className="flex items-center gap-3 mb-3">
                            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${ORANGE}20` }}>
                                <Scale className="w-4 h-4" style={{ color: ORANGE }} />
                            </div>
                            <div>
                                <p className="text-sm font-bold text-foreground">Peso actual *</p>
                                <p className="text-xs text-foreground/30">En ayunas, sin ropa</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <input
                                type="number"
                                step="0.1"
                                value={reportData.weight}
                                onChange={(e) => set('weight', e.target.value)}
                                placeholder="75.5"
                                data-testid="weight-input"
                                className="flex-1 bg-muted border border-input rounded-xl px-3 py-3 text-foreground text-2xl font-bold placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors"
                            />
                            <span className="text-lg text-foreground/40 font-bold">kg</span>
                        </div>
                    </div>

                    {/* Measurements */}
                    <div className="bg-card border border-border rounded-2xl p-4">
                        <div className="flex items-center gap-3 mb-3">
                            <div className="w-9 h-9 rounded-xl bg-muted flex items-center justify-center">
                                <Ruler className="w-4 h-4 text-foreground/40" />
                            </div>
                            <div>
                                <p className="text-sm font-bold text-foreground">Medidas (cm)</p>
                                <p className="text-xs text-foreground/30">Opcional</p>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            {[
                                { key: 'chest', label: 'Pecho' },
                                { key: 'waist', label: 'Cintura' },
                                { key: 'hip', label: 'Cadera' },
                                { key: 'arm', label: 'Brazo' },
                                { key: 'thigh', label: 'Muslo' }
                            ].map(({ key, label }) => (
                                <div key={key}>
                                    <label className={labelCls}>{label}</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        value={reportData.measurements[key]}
                                        onChange={(e) => set('measurements', { ...reportData.measurements, [key]: e.target.value })}
                                        placeholder="--"
                                        className={inputCls}
                                    />
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Sliders */}
                    <div className="bg-card border border-border rounded-2xl p-4 space-y-5">
                        <SliderRow icon={Activity} iconColor={ORANGE}    label="Cumplimiento entrenamiento" value={reportData.training_compliance}  max={100} unit="%" onChange={(v) => set('training_compliance', v)} />
                        <SliderRow icon={Activity} iconColor="#22C55E"   label="Cumplimiento nutrición"      value={reportData.nutrition_compliance} max={100} unit="%" onChange={(v) => set('nutrition_compliance', v)} />
                        <SliderRow icon={Moon}     iconColor="#818CF8"   label="Calidad del sueño"           value={reportData.sleep_quality}        max={10}  unit="/10" onChange={(v) => set('sleep_quality', v)} />
                        <SliderRow icon={Zap}      iconColor="#F59E0B"   label="Nivel de energía"            value={reportData.energy_level}         max={10}  unit="/10" onChange={(v) => set('energy_level', v)} />
                        <SliderRow icon={Brain}    iconColor="#F43F5E"   label="Nivel de estrés"             value={reportData.stress_level}         max={10}  unit="/10" onChange={(v) => set('stress_level', v)} />
                    </div>

                    {/* Notes */}
                    <div className="bg-card border border-border rounded-2xl p-4">
                        <label className={labelCls}>Notas adicionales</label>
                        <textarea
                            value={reportData.notes}
                            onChange={(e) => set('notes', e.target.value)}
                            placeholder="¿Cómo te has sentido esta semana? ¿Alguna dificultad o logro?"
                            rows={4}
                            data-testid="notes-textarea"
                            className="w-full bg-muted border border-input rounded-xl px-3 py-2.5 text-foreground text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors resize-none"
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={submitting}
                        data-testid="submit-report-btn"
                        className="w-full py-3 rounded-xl font-bold text-sm uppercase tracking-wider text-foreground flex items-center justify-center gap-2 transition-all disabled:opacity-40"
                        style={{ backgroundColor: ORANGE }}
                    >
                        <Send className="w-4 h-4" />
                        {submitting ? 'Enviando...' : 'Enviar reporte'}
                    </button>
                </form>
            )}

            {/* ── EVOLUTION TAB ── */}
            {activeTab === 'evolution' && (
                <div className="space-y-4">
                    {weightData.length > 0 ? (
                        <div className="bg-card border border-border rounded-2xl p-4">
                            <div className="flex items-center gap-2 mb-4">
                                <Scale className="w-4 h-4" style={{ color: ORANGE }} />
                                <p className="text-sm font-bold text-foreground uppercase tracking-wider">Evolución del peso</p>
                            </div>
                            <div className="h-56">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={weightData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#222" />
                                        <XAxis dataKey="date" tick={{ fill: '#ffffff66', fontSize: 11 }} axisLine={false} tickLine={false} />
                                        <YAxis domain={['auto', 'auto']} tick={{ fill: '#ffffff66', fontSize: 11 }} axisLine={false} tickLine={false} />
                                        <Tooltip
                                            contentStyle={{ backgroundColor: '#1A1A1A', border: '1px solid #333', borderRadius: 12, color: '#fff' }}
                                            labelStyle={{ color: '#fff' }}
                                        />
                                        <Line type="monotone" dataKey="peso" stroke={ORANGE} strokeWidth={2} dot={{ fill: ORANGE, r: 3 }} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    ) : (
                        <div className="bg-card border border-border rounded-2xl p-8 text-center">
                            <TrendingUp className="w-10 h-10 text-foreground/20 mx-auto mb-3" />
                            <p className="text-foreground font-bold mb-1">Sin datos de evolución</p>
                            <p className="text-xs text-foreground/30">Envía tu primer reporte para ver tu progreso.</p>
                        </div>
                    )}
                </div>
            )}

            {/* ── HISTORY TAB ── */}
            {activeTab === 'history' && (
                <div className="space-y-3">
                    {reports.length > 0 ? reports.map((report) => (
                        <div key={report.id} className="bg-card border border-border rounded-2xl p-4">
                            <div className="flex items-start justify-between mb-3">
                                <div>
                                    <p className="text-xs text-foreground/40 uppercase tracking-wider">
                                        {new Date(report.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}
                                    </p>
                                    <p className="text-2xl font-bold text-foreground" style={{ fontFamily: 'Barlow Condensed' }}>
                                        {report.weight} <span className="text-base text-foreground/40">kg</span>
                                    </p>
                                </div>
                                <ChevronRight className="w-4 h-4 text-foreground/20 mt-1" />
                            </div>
                            {(report.training_compliance != null || report.nutrition_compliance != null) && (
                                <div className="grid grid-cols-2 gap-2">
                                    <div className="bg-muted rounded-xl px-3 py-2 flex items-center gap-2">
                                        <Activity className="w-3.5 h-3.5" style={{ color: ORANGE }} />
                                        <span className="text-xs text-foreground/60">Entreno <span className="text-foreground font-bold">{report.training_compliance != null ? `${report.training_compliance}%` : '-'}</span></span>
                                    </div>
                                    <div className="bg-muted rounded-xl px-3 py-2 flex items-center gap-2">
                                        <Activity className="w-3.5 h-3.5 text-green-400" />
                                        <span className="text-xs text-foreground/60">Nutrición <span className="text-foreground font-bold">{report.nutrition_compliance != null ? `${report.nutrition_compliance}%` : '-'}</span></span>
                                    </div>
                                </div>
                            )}
                            {report.trainer_feedback && (
                                <div className="mt-3 p-3 rounded-xl border" style={{ backgroundColor: `${ORANGE}10`, borderColor: `${ORANGE}30` }}>
                                    <p className="text-xs font-bold mb-1" style={{ color: ORANGE }}>Feedback del entrenador</p>
                                    <p className="text-sm text-foreground/70">{report.trainer_feedback}</p>
                                </div>
                            )}
                        </div>
                    )) : (
                        <div className="bg-card border border-border rounded-2xl p-8 text-center">
                            <Calendar className="w-10 h-10 text-foreground/20 mx-auto mb-3" />
                            <p className="text-foreground/40 text-sm">No hay reportes anteriores.</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default ReportsPage;
