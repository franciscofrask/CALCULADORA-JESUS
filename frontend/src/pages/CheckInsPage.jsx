import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import {
    Heart, Activity, TrendingUp, CheckCircle2, Smile, Frown, Meh,
    Zap, Apple, Dumbbell, Scale, Send, ChevronDown, ChevronUp, Calendar,
    Camera, Trash2, Loader2,
} from 'lucide-react';

const ORANGE = '#FF671F';
const inputCls = "w-full bg-muted border border-input rounded-xl px-3 py-2.5 text-foreground text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors";
const labelCls = "block text-xs font-bold text-foreground/40 uppercase tracking-wider mb-1.5";

const HEALTH_TONES = {
    green:  { ring: 'border-emerald-500/30', bg: 'bg-emerald-500/10', text: 'text-emerald-400', dot: 'bg-emerald-500', label: 'Saludable' },
    yellow: { ring: 'border-amber-500/30',   bg: 'bg-amber-500/10',   text: 'text-amber-400',   dot: 'bg-amber-500',   label: 'Atención' },
    red:    { ring: 'border-red-500/30',     bg: 'bg-red-500/10',     text: 'text-red-400',     dot: 'bg-red-500',     label: 'En riesgo' },
};

const MOOD_FACES = [
    { value: 1, icon: Frown, color: 'text-red-500', label: 'Mal' },
    { value: 2, icon: Frown, color: 'text-orange-500', label: 'Bajo' },
    { value: 3, icon: Meh, color: 'text-amber-500', label: 'Neutro' },
    { value: 4, icon: Smile, color: 'text-emerald-500', label: 'Bien' },
    { value: 5, icon: Smile, color: 'text-emerald-400', label: 'Genial' },
];

const todayKey = () => new Date().toISOString().slice(0, 10);
const isSameDay = (iso) => iso && new Date(iso).toISOString().slice(0, 10) === todayKey();

// ── Subcomponentes a nivel de módulo (mantienen el foco al teclear) ──────────
const Card = ({ className = '', children }) => (
    <div className={`bg-card border border-border rounded-2xl ${className}`}>{children}</div>
);

const Field = ({ label, children }) => (
    <div>
        <label className={labelCls}>{label}</label>
        {children}
    </div>
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

const Collapsible = ({ open, onToggle, icon: Icon, title, subtitle, children }) => (
    <Card className="overflow-hidden">
        <button type="button" onClick={onToggle}
            className="w-full text-left flex items-center justify-between p-4 hover:bg-muted/50 transition-colors">
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-brand/10 flex items-center justify-center">
                    <Icon className="w-4 h-4 text-brand" />
                </div>
                <div>
                    <p className="font-bold text-foreground text-sm">{title}</p>
                    <p className="text-xs text-foreground/50">{subtitle}</p>
                </div>
            </div>
            {open ? <ChevronUp className="w-4 h-4 text-foreground/40" /> : <ChevronDown className="w-4 h-4 text-foreground/40" />}
        </button>
        {open && <div className="border-t border-border p-4 space-y-4">{children}</div>}
    </Card>
);

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
            <button onClick={() => onDeleted(photo.id)}
                className="absolute top-1.5 right-1.5 w-7 h-7 rounded-lg bg-black/60 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                <Trash2 className="w-3.5 h-3.5" />
            </button>
            <span className="absolute bottom-1 left-1.5 text-[10px] text-white/90 bg-black/50 px-1.5 py-0.5 rounded">
                {new Date(photo.taken_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}
            </span>
        </div>
    );
};

const PhotosSection = ({ api }) => {
    const [photos, setPhotos] = useState([]);
    const [uploading, setUploading] = useState(false);

    const load = useCallback(() => {
        api.get('/reports/photos').then(r => setPhotos(r.data?.photos || [])).catch(() => {});
    }, [api]);
    useEffect(() => { load(); }, [load]);

    const onPick = async (e) => {
        const file = e.target.files?.[0];
        e.target.value = '';
        if (!file) return;
        setUploading(true);
        try {
            const fd = new FormData();
            fd.append('file', file);
            await api.post('/reports/photos', fd);
            toast.success('Foto subida');
            load();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Error subiendo la foto');
        } finally {
            setUploading(false);
        }
    };

    const remove = async (id) => {
        try { await api.delete(`/reports/photos/${id}`); setPhotos(p => p.filter(x => x.id !== id)); }
        catch { toast.error('Error borrando la foto'); }
    };

    return (
        <Card className="p-5">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <Camera className="w-4 h-4 text-brand" />
                    <p className="text-xs font-bold text-foreground/40 uppercase tracking-wider">Fotos de progreso</p>
                </div>
                <label className="cursor-pointer inline-flex items-center gap-2 text-sm font-bold text-white bg-[#FF671F] hover:bg-[#FF671F]/90 px-3 py-2 rounded-xl transition-colors">
                    {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
                    {uploading ? 'Subiendo...' : 'Subir foto'}
                    <input type="file" accept="image/*" className="hidden" onChange={onPick} disabled={uploading} />
                </label>
            </div>
            {photos.length === 0 ? (
                <p className="text-foreground/40 text-center py-6 text-sm">Aún no has subido fotos</p>
            ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2">
                    {photos.map(p => <PhotoThumb key={p.id} photo={p} api={api} onDeleted={remove} />)}
                </div>
            )}
        </Card>
    );
};

const CheckInsPage = () => {
    const { api } = useAuth();
    const [healthScore, setHealthScore] = useState(null);
    const [checkins, setCheckins] = useState([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [openForm, setOpenForm] = useState(null);

    const [daily, setDaily] = useState({ mood: null, energy: null, trained: null, nutrition_followed: null, notes: '' });
    const [weekly, setWeekly] = useState({ weight: '', training_compliance: '', nutrition_compliance: '', sleep_quality: '', stress_level: '', notes: '' });
    const [monthly, setMonthly] = useState({ weight: '', body_fat_pct: '', chest: '', waist: '', hip: '', arm: '', thigh: '', goals_progress: '', challenges: '', notes: '' });

    const fetchAll = useCallback(async () => {
        try {
            const [hsRes, ciRes] = await Promise.all([
                api.get('/health-score').catch(() => ({ data: null })),
                api.get('/checkins?limit=30'),
            ]);
            setHealthScore(hsRes.data);
            setCheckins(Array.isArray(ciRes.data) ? ciRes.data : []);
        } catch {
            toast.error('Error al cargar check-ins');
        } finally {
            setLoading(false);
        }
    }, [api]);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    const todayDaily = checkins.find(c => c.type === 'daily' && isSameDay(c.created_at));

    const submitDaily = async () => {
        if (daily.mood == null || daily.energy == null || daily.trained == null || daily.nutrition_followed == null) {
            return toast.error('Completa todos los campos');
        }
        setSubmitting(true);
        try {
            await api.post('/checkins', { type: 'daily', ...daily, notes: daily.notes || null });
            toast.success('Check-in diario enviado');
            setDaily({ mood: null, energy: null, trained: null, nutrition_followed: null, notes: '' });
            fetchAll();
        } catch { toast.error('Error al enviar check-in'); }
        finally { setSubmitting(false); }
    };

    const submitWeekly = async () => {
        if (!weekly.weight) return toast.error('Indica tu peso');
        setSubmitting(true);
        try {
            await api.post('/checkins', {
                type: 'weekly',
                weight: parseFloat(weekly.weight),
                training_compliance: weekly.training_compliance ? parseInt(weekly.training_compliance) : null,
                nutrition_compliance: weekly.nutrition_compliance ? parseInt(weekly.nutrition_compliance) : null,
                sleep_quality: weekly.sleep_quality ? parseInt(weekly.sleep_quality) : null,
                stress_level: weekly.stress_level ? parseInt(weekly.stress_level) : null,
                notes: weekly.notes || null,
            });
            toast.success('Check-in semanal enviado');
            setWeekly({ weight: '', training_compliance: '', nutrition_compliance: '', sleep_quality: '', stress_level: '', notes: '' });
            setOpenForm(null);
            fetchAll();
        } catch { toast.error('Error al enviar check-in semanal'); }
        finally { setSubmitting(false); }
    };

    const submitMonthly = async () => {
        if (!monthly.weight) return toast.error('Indica tu peso');
        setSubmitting(true);
        try {
            const measurements = {};
            ['chest', 'waist', 'hip', 'arm', 'thigh'].forEach(k => { if (monthly[k]) measurements[k] = parseFloat(monthly[k]); });
            await api.post('/checkins', {
                type: 'monthly',
                weight: parseFloat(monthly.weight),
                body_fat_pct: monthly.body_fat_pct ? parseFloat(monthly.body_fat_pct) : null,
                measurements: Object.keys(measurements).length ? measurements : null,
                goals_progress: monthly.goals_progress || null,
                challenges: monthly.challenges || null,
                notes: monthly.notes || null,
            });
            toast.success('Check-in mensual enviado');
            setMonthly({ weight: '', body_fat_pct: '', chest: '', waist: '', hip: '', arm: '', thigh: '', goals_progress: '', challenges: '', notes: '' });
            setOpenForm(null);
            fetchAll();
        } catch { toast.error('Error al enviar check-in mensual'); }
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

    const tone = healthScore && HEALTH_TONES[healthScore.score];

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5 animate-fade-in" data-testid="checkins-page">
            <header className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-brand/10">
                    <Activity className="w-6 h-6 text-brand" />
                </div>
                <div>
                    <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none" data-testid="checkins-heading">Seguimiento</h1>
                    <p className="text-sm text-muted-foreground mt-1">Tus check-ins diarios, semanales y mensuales</p>
                </div>
            </header>

            {tone && (
                <Card className={`p-4 flex items-center gap-3 ${tone.bg} ${tone.ring}`}>
                    <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${tone.dot}`}>
                        <Heart className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className={`font-bold uppercase tracking-wider text-sm ${tone.text}`}>{tone.label}</p>
                        <p className="text-sm text-foreground/60 truncate">{healthScore.factors?.[0] || 'Vas por buen camino'}</p>
                    </div>
                </Card>
            )}

            {/* Diario */}
            {todayDaily ? (
                <Card className="p-4 border-l-4 border-l-emerald-500 flex items-start gap-3" data-testid="checkins-content">
                    <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                    <div>
                        <p className="font-bold text-foreground">Check-in de hoy hecho</p>
                        <p className="text-sm text-foreground/60 mt-0.5">
                            Ánimo {todayDaily.mood}/5 · Energía {todayDaily.energy}/5 ·
                            {todayDaily.trained ? ' Entrenó' : ' Sin entrenar'} ·
                            {todayDaily.nutrition_followed ? ' Plan ✓' : ' Plan ✗'}
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
                        <div>
                            <span className="text-sm text-foreground/70 mb-2 block">¿Cómo te sientes hoy?</span>
                            <div className="flex gap-2 justify-between">
                                {MOOD_FACES.map(m => {
                                    const Icon = m.icon; const active = daily.mood === m.value;
                                    return (
                                        <button key={m.value} type="button" onClick={() => setDaily({ ...daily, mood: m.value })}
                                            className={`flex-1 p-3 rounded-xl border transition-all ${active ? 'border-brand bg-brand/10' : 'border-border bg-muted hover:border-white/30'}`}>
                                            <Icon className={`w-5 h-5 mx-auto ${active ? m.color : 'text-foreground/30'}`} />
                                            <p className="text-[10px] text-foreground/50 mt-1">{m.label}</p>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                        <div>
                            <span className="text-sm text-foreground/70 mb-2 block">Nivel de energía</span>
                            <div className="flex gap-2">
                                {[1, 2, 3, 4, 5].map(v => {
                                    const active = daily.energy === v;
                                    return (
                                        <button key={v} type="button" onClick={() => setDaily({ ...daily, energy: v })}
                                            className={`flex-1 py-3 rounded-xl border transition-all flex items-center justify-center gap-1 font-bold text-sm ${active ? 'border-brand bg-brand/10 text-brand' : 'border-border bg-muted text-foreground/50 hover:border-white/30'}`}>
                                            <Zap className="w-3.5 h-3.5" />{v}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                        <BoolPicker icon={Dumbbell} label="¿Entrenaste hoy?" value={daily.trained} onChange={v => setDaily({ ...daily, trained: v })} />
                        <BoolPicker icon={Apple} label="¿Seguiste tu plan nutricional?" value={daily.nutrition_followed} onChange={v => setDaily({ ...daily, nutrition_followed: v })} />
                        <Field label="Notas (opcional)">
                            <textarea value={daily.notes} onChange={e => setDaily({ ...daily, notes: e.target.value })}
                                placeholder="¿Algo que quieras compartir con tu coach?" rows={2} className={inputCls} />
                        </Field>
                        <button onClick={submitDaily} disabled={submitting}
                            className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 disabled:opacity-60">
                            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Enviar check-in
                        </button>
                    </div>
                </Card>
            )}

            {/* Semanal + Mensual */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Collapsible open={openForm === 'weekly'} onToggle={() => setOpenForm(openForm === 'weekly' ? null : 'weekly')}
                    icon={Calendar} title="Check-in semanal" subtitle="Peso + adherencia + sueño">
                    <Field label="Peso (kg)">
                        <input type="number" step="0.1" value={weekly.weight} onChange={e => setWeekly({ ...weekly, weight: e.target.value })} className={inputCls} />
                    </Field>
                    <div className="grid grid-cols-2 gap-3">
                        <Field label="Adherencia entreno (%)"><input type="number" min="0" max="100" value={weekly.training_compliance} onChange={e => setWeekly({ ...weekly, training_compliance: e.target.value })} className={inputCls} /></Field>
                        <Field label="Adherencia nutri (%)"><input type="number" min="0" max="100" value={weekly.nutrition_compliance} onChange={e => setWeekly({ ...weekly, nutrition_compliance: e.target.value })} className={inputCls} /></Field>
                        <Field label="Sueño (1-10)"><input type="number" min="1" max="10" value={weekly.sleep_quality} onChange={e => setWeekly({ ...weekly, sleep_quality: e.target.value })} className={inputCls} /></Field>
                        <Field label="Estrés (1-10)"><input type="number" min="1" max="10" value={weekly.stress_level} onChange={e => setWeekly({ ...weekly, stress_level: e.target.value })} className={inputCls} /></Field>
                    </div>
                    <Field label="Notas"><textarea rows={2} value={weekly.notes} onChange={e => setWeekly({ ...weekly, notes: e.target.value })} className={inputCls} /></Field>
                    <button onClick={submitWeekly} disabled={submitting} className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 disabled:opacity-60">
                        {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Enviar
                    </button>
                </Collapsible>

                <Collapsible open={openForm === 'monthly'} onToggle={() => setOpenForm(openForm === 'monthly' ? null : 'monthly')}
                    icon={TrendingUp} title="Check-in mensual" subtitle="Medidas + composición">
                    <div className="grid grid-cols-2 gap-3">
                        <Field label="Peso (kg)"><input type="number" step="0.1" value={monthly.weight} onChange={e => setMonthly({ ...monthly, weight: e.target.value })} className={inputCls} /></Field>
                        <Field label="% Grasa"><input type="number" step="0.1" value={monthly.body_fat_pct} onChange={e => setMonthly({ ...monthly, body_fat_pct: e.target.value })} className={inputCls} /></Field>
                    </div>
                    <span className="text-xs font-bold text-foreground/40 uppercase tracking-wider block">Medidas (cm)</span>
                    <div className="grid grid-cols-3 gap-2">
                        {[['chest', 'Pecho'], ['waist', 'Cintura'], ['hip', 'Cadera'], ['arm', 'Brazo'], ['thigh', 'Muslo']].map(([k, l]) => (
                            <Field key={k} label={l}><input type="number" step="0.1" value={monthly[k]} onChange={e => setMonthly({ ...monthly, [k]: e.target.value })} className={inputCls} /></Field>
                        ))}
                    </div>
                    <Field label="Progreso hacia tus objetivos"><textarea rows={2} value={monthly.goals_progress} onChange={e => setMonthly({ ...monthly, goals_progress: e.target.value })} className={inputCls} /></Field>
                    <Field label="Dificultades / retos"><textarea rows={2} value={monthly.challenges} onChange={e => setMonthly({ ...monthly, challenges: e.target.value })} className={inputCls} /></Field>
                    <button onClick={submitMonthly} disabled={submitting} className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 disabled:opacity-60">
                        {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Enviar
                    </button>
                </Collapsible>
            </div>

            <PhotosSection api={api} />

            {/* Historial */}
            <Card className="p-5">
                <p className="text-xs font-bold text-foreground/40 uppercase tracking-wider mb-3">Historial</p>
                {checkins.length === 0 ? (
                    <p className="text-foreground/40 text-center py-8 text-sm">Aún no tienes check-ins</p>
                ) : (
                    <ul className="space-y-3">
                        {checkins.slice(0, 12).map(c => (
                            <li key={c.id} className="rounded-xl border border-border bg-muted p-3">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full bg-card border border-border text-foreground/60">{c.type}</span>
                                    <span className="text-[11px] text-foreground/50">
                                        {new Date(c.created_at).toLocaleString('es-ES', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                </div>
                                {c.type === 'daily' ? (
                                    <p className="text-sm text-foreground/70">
                                        Ánimo {c.mood}/5 · Energía {c.energy}/5 ·
                                        {c.trained ? ' Entrenó' : ' No entrenó'} ·
                                        {c.nutrition_followed ? ' Plan ✓' : ' Plan ✗'}
                                    </p>
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
                                        <span className="text-[10px] uppercase tracking-wider text-brand font-bold mr-2">Coach:</span>{c.trainer_feedback}
                                    </div>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </Card>
        </div>
    );
};

export default CheckInsPage;
