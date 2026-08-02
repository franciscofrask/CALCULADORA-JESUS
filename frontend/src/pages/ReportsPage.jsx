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
import InformeMensual from '../components/reports/InformeMensual';

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

const _fmtCorta = (iso) => iso ? new Date(iso).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }) : '';

// Estado de la ventana de envío (viernes 00:00 -> lunes 06:00).
const WindowBanner = ({ w }) => {
    const base = "rounded-2xl p-4 border text-sm flex items-center gap-2";
    if (!w || !w.due) {
        return (
            <div className={`${base} border-border bg-muted text-foreground/60`}>
                <Calendar className="w-4 h-4 text-foreground/40 flex-shrink-0" />
                Esta semana no toca reporte. Te avisaremos cuando abra la ventana.
            </div>
        );
    }
    if (w.submitted) {
        return (
            <div className={`${base} border-green-500/40 bg-green-500/5 text-foreground`}>
                <Calendar className="w-4 h-4 text-green-500 flex-shrink-0" />
                Ya enviaste tu {w.tipo_label?.toLowerCase()} de esta semana. ¡Bien hecho!
            </div>
        );
    }
    if (w.is_open) {
        return (
            <div className={`${base} border-yellow-500/40 bg-yellow-500/5 text-foreground`}>
                <Calendar className="w-4 h-4 text-yellow-500 flex-shrink-0" />
                Ventana abierta: rellena tu {w.tipo_label?.toLowerCase()} antes del {w.closes_label}.
            </div>
        );
    }
    const before = w.opens_at && new Date(w.opens_at).getTime() > Date.now();
    return (
        <div className={`${base} ${before ? 'border-yellow-500/40 bg-yellow-500/5' : 'border-red-500/40 bg-red-500/5'} text-foreground`}>
            <Calendar className={`w-4 h-4 flex-shrink-0 ${before ? 'text-yellow-500' : 'text-red-500'}`} />
            {before
                ? `Tu reporte se rellena el fin de semana. La ventana abre el ${w.opens_label}.`
                : 'La ventana de esta semana se cerró. Espera a la semana que viene.'}
        </div>
    );
};

const ReportsPage = () => {
    const { api } = useAuth();
    const [reports, setReports] = useState([]);
    const [evolution, setEvolution] = useState(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [activeTab, setActiveTab] = useState('form');
    const [windowState, setWindowState] = useState(null);   // ventana de envío (viernes->lunes 6:00)
    const [prev, setPrev] = useState(null);                 // último reporte (referencia de medidas)
    // Confirmación de huecos: lo que se le pregunta ANTES de rellenar, en vez de pedirle
    // que puntúe su propio cumplimiento (documento, parte 7.1).
    const [huecos, setHuecos] = useState(null);
    const [huecosResp, setHuecosResp] = useState({});
    // Las medidas solo van en el mensual, y allí solo la cintura es obligatoria; el resto,
    // plegado (documento, parte 7.3). Si no se sabe qué toca, no se piden.
    const [verMasMedidas, setVerMasMedidas] = useState(false);

    // El informe del mes: se pide solo cuando abre uno, porque cruza dietas, check-ins
    // y macros de todo el periodo y no tiene sentido calcularlo para la lista entera.
    const [informeAbierto, setInformeAbierto] = useState(null);   // id del reporte abierto
    const [informe, setInforme] = useState(null);
    const [cargandoInforme, setCargandoInforme] = useState(false);

    const verInforme = async (reportId) => {
        if (informeAbierto === reportId) { setInformeAbierto(null); setInforme(null); return; }
        setInformeAbierto(reportId);
        setInforme(null);
        setCargandoInforme(true);
        try {
            const r = await api.get(`/reports/${reportId}/informe`);
            setInforme(r.data);
        } catch (e) {
            toast.error('No hemos podido montar tu informe');
            setInformeAbierto(null);
        } finally {
            setCargandoInforme(false);
        }
    };

    const [reportData, setReportData] = useState({
        weight: '',
        measurements: { chest: '', waist: '', hip: '', arm: '', thigh: '' },
        sleep_quality: 7,
        energy_level: 7,
        stress_level: 5,
        notes: ''
    });

    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetch solo al montar
    useEffect(() => { fetchData(); }, []);

    const fetchData = async () => {
        try {
            const [reportsRes, evolutionRes, dueRes, prevRes, huecosRes] = await Promise.all([
                api.get('/reports'),
                api.get('/reports/evolution'),
                api.get('/reports/due').catch(() => ({ data: { window: null } })),
                api.get('/reports/previous').catch(() => ({ data: null })),
                api.get('/reports/confirmacion-huecos').catch(() => ({ data: null })),
            ]);
            setReports(reportsRes.data);
            setHasMore(reportsRes.data.length === 50);
            setEvolution(evolutionRes.data);
            setWindowState(dueRes.data?.window || null);
            setPrev(prevRes.data && Object.keys(prevRes.data).length ? prevRes.data : null);
            setHuecos(huecosRes.data || null);
        } catch (error) {
            console.error('Error fetching reports:', error);
        } finally {
            setLoading(false);
        }
    };

    // Paginación del historial: "Cargar más" trae el siguiente bloque
    const [hasMore, setHasMore] = useState(false);
    const [loadingMore, setLoadingMore] = useState(false);
    const loadMore = async () => {
        setLoadingMore(true);
        try {
            const res = await api.get('/reports', { params: { skip: reports.length } });
            setReports(prev => [...prev, ...res.data]);
            setHasMore(res.data.length === 50);
        } catch { /* silencioso */ }
        finally { setLoadingMore(false); }
    };

    // Qué reporte toca esta semana. Sin el dato no se piden medidas: es preferible no
    // pedirlas que pedirlas en el quincenal, que es justo lo que el documento quita.
    const esMensual = (windowState?.tipos || []).includes('mensual');

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!reportData.weight) { toast.error('El peso es obligatorio'); return; }
        // En el mensual la cintura es obligatoria; el resto de medidas, no (parte 7.3).
        if (esMensual && !reportData.measurements.waist) {
            toast.error('La cintura es obligatoria en el reporte mensual');
            return;
        }
        setSubmitting(true);
        try {
            const payload = {
                weight: parseFloat(reportData.weight),
                measurements: Object.fromEntries(
                    Object.entries(reportData.measurements)
                        .filter(([_, v]) => v)
                        .map(([k, v]) => [k, parseFloat(v)])
                ),
                // El cumplimiento lo calcula el servidor a partir de esto y del registro.
                huecos: huecosResp,
                sleep_quality: reportData.sleep_quality,
                energy_level: reportData.energy_level,
                stress_level: reportData.stress_level,
                notes: reportData.notes || null
            };
            await api.post('/reports', payload);
            toast.success('Reporte enviado correctamente');
            fetchData();
            setActiveTab('history');
            setHuecosResp({});
            setReportData({
                weight: '',
                measurements: { chest: '', waist: '', hip: '', arm: '', thigh: '' },
                sleep_quality: 7,
                energy_level: 7,
                stress_level: 5,
                notes: ''
            });
        } catch (error) {
            toast.error(error?.response?.data?.detail || 'Error al enviar el reporte');
            if (error?.response?.status === 403) fetchData();  // la ventana pudo cambiar de estado
        } finally {
            setSubmitting(false);
        }
    };

    const set = (field, value) => setReportData(prevData => ({ ...prevData, [field]: value }));
    const formOpen = windowState ? (windowState.is_open && !windowState.submitted) : true;

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
        <div className="px-4 pt-6 pb-28 max-w-2xl mx-auto space-y-4">
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
                    <WindowBanner w={windowState} />
                    <fieldset disabled={!formOpen} className="space-y-4 p-0 m-0 border-0 min-w-0 disabled:opacity-50">
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
                                className="flex-1 min-w-0 bg-muted border border-input rounded-xl px-3 py-3 text-foreground text-2xl font-bold placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors"
                            />
                            <span className="text-lg text-foreground/40 font-bold">kg</span>
                        </div>
                        {prev?.weight != null && (
                            <p className="text-xs text-foreground/40 mt-2">Último: {prev.weight} kg{prev.created_at ? ` · ${_fmtCorta(prev.created_at)}` : ''}</p>
                        )}
                    </div>

                    {/* Medidas: SOLO en el mensual (documento, parte 7.3). En el quincenal
                        no se piden; ahí el reporte es "dos minutos" y sacar la cinta métrica
                        cada dos semanas para un dato que apenas se mueve no compensa.
                        En el mensual, la cintura es obligatoria y el resto va plegado. */}
                    {esMensual && (
                    <div className="bg-card border border-border rounded-2xl p-4" data-testid="medidas">
                        <div className="flex items-center gap-3 mb-3">
                            <div className="w-9 h-9 rounded-xl bg-muted flex items-center justify-center">
                                <Ruler className="w-4 h-4 text-foreground/40" />
                            </div>
                            <div>
                                <p className="text-sm font-bold text-foreground">Cintura (cm)</p>
                                <p className="text-xs text-foreground/30">Obligatoria</p>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            {(verMasMedidas ? [
                                { key: 'waist', label: 'Cintura' },
                                { key: 'chest', label: 'Pecho' },
                                { key: 'hip', label: 'Cadera' },
                                { key: 'arm', label: 'Brazo' },
                                { key: 'thigh', label: 'Muslo' },
                            ] : [{ key: 'waist', label: 'Cintura' }]).map(({ key, label }) => (
                                <div key={key}>
                                    <label className={labelCls}>{label}</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        value={reportData.measurements[key]}
                                        onChange={(e) => set('measurements', { ...reportData.measurements, [key]: e.target.value })}
                                        placeholder={prev?.measurements?.[key] != null ? String(prev.measurements[key]) : '--'}
                                        className={inputCls}
                                    />
                                    {prev?.measurements?.[key] != null && (
                                        <p className="text-[10px] text-foreground/40 mt-1">antes: {prev.measurements[key]} cm</p>
                                    )}
                                </div>
                            ))}
                        </div>
                        <button type="button" onClick={() => setVerMasMedidas(v => !v)}
                            data-testid="ver-mas-medidas"
                            className="mt-3 text-xs text-foreground/50 hover:text-foreground underline underline-offset-4">
                            {verMasMedidas ? 'Solo la cintura' : 'Añadir el resto de medidas (opcional)'}
                        </button>
                    </div>
                    )}

                    {/* Confirmación de huecos: sustituye a los dos deslizadores de
                        cumplimiento (documento 31-07, parte 7.1). El cumplimiento sale del
                        registro, no de que se puntúe a sí mismo. Los deslizadores que
                        quedan son los que NO se pueden deducir: sueño, energía y estrés. */}
                    {huecos?.hay_que_preguntar && (
                        <div className="bg-card border border-border rounded-2xl p-4 space-y-4" data-testid="confirmacion-huecos">
                            <p className="text-sm font-bold text-foreground">Antes de rellenar</p>
                            {huecos.huecos.map(h => (
                                <div key={h.tipo}>
                                    <p className="text-sm text-foreground/70 mb-2">{h.pregunta}</p>
                                    <div className="grid grid-cols-2 gap-2">
                                        {[
                                            { v: 'no_lo_hice', t: h.tipo === 'dieta' ? 'No la hice' : 'No los hice' },
                                            { v: 'si_pero_no_apunte', t: h.tipo === 'dieta' ? 'Sí, no la apunté' : 'Sí, no los apunté' },
                                        ].map(op => (
                                            <button key={op.v} type="button"
                                                onClick={() => setHuecosResp({ ...huecosResp, [h.tipo]: op.v })}
                                                data-testid={`hueco-${h.tipo}-${op.v}`}
                                                className={`py-2.5 px-3 rounded-xl border text-sm transition-all ${
                                                    huecosResp[h.tipo] === op.v
                                                        ? 'border-brand bg-brand/10 text-brand font-bold'
                                                        : 'border-border bg-muted text-foreground/60 hover:border-white/30'}`}>
                                                {op.t}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Sliders: solo lo que no se puede deducir de lo registrado */}
                    <div className="bg-card border border-border rounded-2xl p-4 space-y-5">
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
                    </fieldset>
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
                            <button onClick={() => verInforme(report.id)} data-testid={`ver-informe-${report.id}`}
                                className="w-full text-left flex items-start justify-between mb-3">
                                <div>
                                    <p className="text-xs text-foreground/40 uppercase tracking-wider">
                                        {new Date(report.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}
                                    </p>
                                    <p className="text-2xl font-bold text-foreground" style={{ fontFamily: 'Barlow Condensed' }}>
                                        {report.weight} <span className="text-base text-foreground/40">kg</span>
                                    </p>
                                    <p className="text-[11px] mt-0.5" style={{ color: ORANGE }}>
                                        {informeAbierto === report.id ? 'Ocultar mi informe' : 'Ver mi informe del mes'}
                                    </p>
                                </div>
                                <ChevronRight className={`w-4 h-4 text-foreground/20 mt-1 transition-transform ${informeAbierto === report.id ? 'rotate-90' : ''}`} />
                            </button>

                            {informeAbierto === report.id && (
                                <div className="mb-3">
                                    {cargandoInforme
                                        ? <p className="text-sm text-foreground/40 py-4 text-center">Montando tu informe...</p>
                                        : <InformeMensual informe={informe} onPedirFotos={() => setActiveTab('form')} />}
                                </div>
                            )}
                            {/* Con el informe abierto, estos dos sobran: el cumplimiento de
                                verdad (el de lo registrado) y la explicación del coach ya van
                                dentro, y verlos dos veces confunde sobre cuál es el bueno.
                                Los deslizadores además son justo lo que la especificación
                                manda sustituir por la confirmación de huecos. */}
                            {informeAbierto !== report.id && (report.training_compliance != null || report.nutrition_compliance != null) && (
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
                            {informeAbierto !== report.id && report.trainer_feedback && (
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
                    {hasMore && (
                        <button onClick={loadMore} disabled={loadingMore} data-testid="reports-load-more"
                            className="w-full py-3 rounded-2xl border border-border text-sm text-foreground/60 hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50">
                            {loadingMore ? 'Cargando...' : 'Cargar más reportes'}
                        </button>
                    )}
                </div>
            )}
        </div>
    );
};

export default ReportsPage;
