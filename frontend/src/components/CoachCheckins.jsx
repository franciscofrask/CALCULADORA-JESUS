import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import { Heart, Calendar, Camera, Loader2, Save, Pencil } from 'lucide-react';

// Tonos de celda (tema oscuro) según calidad de la respuesta.
const TONE = {
    green: 'bg-emerald-500/15 text-emerald-300',
    amber: 'bg-amber-500/15 text-amber-300',
    red:   'bg-red-500/15 text-red-300',
    muted: 'text-white/30 italic',
    none:  'text-white/70',
};

const HEALTH = {
    green:  { bg: 'bg-emerald-500/10 border-emerald-500/30', text: 'text-emerald-400', dot: 'bg-emerald-500', label: 'Saludable' },
    yellow: { bg: 'bg-amber-500/10 border-amber-500/30',     text: 'text-amber-400',   dot: 'bg-amber-500',   label: 'Atención' },
    red:    { bg: 'bg-red-500/10 border-red-500/30',         text: 'text-red-400',     dot: 'bg-red-500',     label: 'En riesgo' },
};

const fmt = (iso) => {
    if (!iso) return '—';
    try {
        const d = new Date(iso);
        return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' }) +
            ' · ' + d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    } catch { return '—'; }
};

const percentTone = (v) => v == null ? 'muted' : (v >= 80 ? 'green' : v >= 50 ? 'amber' : 'red');
const sleepTone = (v) => v == null ? 'muted' : (v >= 7 ? 'green' : v >= 5 ? 'amber' : 'red');
const stressTone = (v) => v == null ? 'muted' : (v <= 4 ? 'green' : v <= 7 ? 'amber' : 'red');
const txt = (v) => (v == null || v === '' ? null : String(v));

const WEEKLY_COLS = [
    { key: 'created_at', label: 'Fecha', r: e => ({ v: fmt(e.created_at) }) },
    { key: 'weight', label: 'Peso', r: e => ({ v: e.weight != null ? `${e.weight} kg` : null }) },
    { key: 'tc', label: 'Cumpl. entreno', r: e => ({ v: e.training_compliance != null ? `${e.training_compliance}%` : null, t: percentTone(e.training_compliance) }) },
    { key: 'nc', label: 'Cumpl. nutrición', r: e => ({ v: e.nutrition_compliance != null ? `${e.nutrition_compliance}%` : null, t: percentTone(e.nutrition_compliance) }) },
    { key: 'sleep', label: 'Sueño', r: e => ({ v: e.sleep_quality != null ? `${e.sleep_quality}/10` : null, t: sleepTone(e.sleep_quality) }) },
    { key: 'stress', label: 'Estrés', r: e => ({ v: e.stress_level != null ? `${e.stress_level}/10` : null, t: stressTone(e.stress_level) }) },
    { key: 'notes', label: 'Notas', r: e => ({ v: txt(e.notes) }) },
];

const MONTHLY_COLS = [
    { key: 'created_at', label: 'Fecha', r: e => ({ v: fmt(e.created_at) }) },
    { key: 'weight', label: 'Peso', r: e => ({ v: e.weight != null ? `${e.weight} kg` : null }) },
    { key: 'bf', label: '% Grasa', r: e => ({ v: e.body_fat_pct != null ? `${e.body_fat_pct}%` : null }) },
    { key: 'meas', label: 'Medidas (P/C/Cad/Br/M)', r: e => {
        const m = e.measurements || {};
        return { v: ['chest', 'waist', 'hip', 'arm', 'thigh'].map(k => m[k] != null ? m[k] : '—').join(' / ') };
    } },
    { key: 'goals', label: 'Progreso objetivos', r: e => ({ v: txt(e.goals_progress), t: e.goals_progress ? 'green' : 'muted' }) },
    { key: 'chal', label: 'Retos', r: e => ({ v: txt(e.challenges), t: e.challenges ? 'amber' : 'muted' }) },
    { key: 'notes', label: 'Comentario cliente', r: e => ({ v: txt(e.notes), t: e.notes ? 'amber' : 'muted' }) },
];

const FeedbackCell = ({ entry, onSave }) => {
    const [editing, setEditing] = useState(false);
    const [val, setVal] = useState(entry.trainer_feedback || '');
    const [saving, setSaving] = useState(false);

    const save = async () => {
        setSaving(true);
        try { await onSave(entry.id, val); setEditing(false); }
        finally { setSaving(false); }
    };

    if (editing) {
        return (
            <td className="px-3 py-2.5 align-top border-r border-[#222] last:border-r-0 min-w-[200px]">
                <textarea value={val} onChange={e => setVal(e.target.value)} rows={2} autoFocus
                    className="w-full bg-[#0A0A0A] border border-[#333] rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-[#FF671F]" />
                <div className="flex gap-1.5 mt-1.5">
                    <button onClick={save} disabled={saving}
                        className="inline-flex items-center gap-1 text-[11px] font-bold text-white bg-[#FF671F] px-2 py-1 rounded-md disabled:opacity-60">
                        {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />} Guardar
                    </button>
                    <button onClick={() => { setVal(entry.trainer_feedback || ''); setEditing(false); }}
                        className="text-[11px] text-white/40 px-2 py-1">Cancelar</button>
                </div>
            </td>
        );
    }
    return (
        <td onClick={() => setEditing(true)}
            className={`px-3 py-2.5 text-xs align-top border-r border-[#222] last:border-r-0 cursor-pointer hover:bg-white/5 ${entry.trainer_feedback ? 'text-emerald-300' : 'text-white/30 italic'}`}>
            <span className="whitespace-pre-wrap leading-relaxed block max-w-[240px]">
                {entry.trainer_feedback || <span className="inline-flex items-center gap-1"><Pencil className="w-3 h-3" /> Añadir feedback</span>}
            </span>
        </td>
    );
};

const CheckinsTable = ({ title, columns, rows, onFeedback, empty }) => (
    <div className="bg-[#111] border border-[#222] rounded-2xl overflow-hidden">
        <div className="px-5 pt-5 pb-3 border-b border-[#222] flex items-baseline justify-between gap-3">
            <p className="text-xs font-bold text-white/40 uppercase tracking-wider flex items-center gap-2">
                <Calendar className="w-4 h-4 text-[#FF671F]" /> {title}
            </p>
            <span className="text-xs text-white/40">{rows.length} {rows.length === 1 ? 'envío' : 'envíos'}</span>
        </div>
        {rows.length === 0 ? (
            <p className="text-sm text-white/40 text-center py-10">{empty}</p>
        ) : (
            <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                    <thead>
                        <tr>
                            {columns.map(c => (
                                <th key={c.key} className="sticky top-0 bg-[#FF671F] text-white text-[11px] font-bold uppercase tracking-wider px-3 py-2 text-left whitespace-nowrap">{c.label}</th>
                            ))}
                            <th className="bg-[#FF671F] text-white text-[11px] font-bold uppercase tracking-wider px-3 py-2 text-left whitespace-nowrap">Feedback coach</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((e, i) => (
                            <tr key={e.id || i} className="border-t border-[#222]">
                                {columns.map(c => {
                                    const { v, t = 'none' } = c.r(e) || {};
                                    return (
                                        <td key={c.key} className={`px-3 py-2.5 text-xs align-top border-r border-[#222] last:border-r-0 ${v == null ? TONE.muted : (TONE[t] || TONE.none)}`}>
                                            <span className="whitespace-pre-wrap leading-relaxed block max-w-[260px]">{v == null ? 'sin respuesta' : v}</span>
                                        </td>
                                    );
                                })}
                                <FeedbackCell entry={e} onSave={onFeedback} />
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        )}
    </div>
);

const PhotoTile = ({ photo, token }) => {
    const [src, setSrc] = useState(null);
    const [err, setErr] = useState(false);
    useEffect(() => {
        let alive = true; let url = null;
        const base = process.env.REACT_APP_BACKEND_URL;
        fetch(`${base}/api/reports/photos/${photo.id}`, { headers: { Authorization: `Bearer ${token}` } })
            .then(r => { if (!r.ok) throw new Error(); return r.blob(); })
            .then(b => { if (!alive) return; url = URL.createObjectURL(b); setSrc(url); })
            .catch(() => { if (alive) setErr(true); });
        return () => { alive = false; if (url) URL.revokeObjectURL(url); };
    }, [photo.id, token]);
    return (
        <figure className="relative rounded-xl overflow-hidden bg-[#0A0A0A] aspect-[3/4] border border-[#222]">
            {src ? <img src={src} alt="" className="absolute inset-0 w-full h-full object-cover" loading="lazy" />
                : err ? <div className="absolute inset-0 flex items-center justify-center text-white/30 text-xs">Error</div>
                : <div className="absolute inset-0 flex items-center justify-center"><Loader2 className="w-4 h-4 animate-spin text-white/30" /></div>}
            <figcaption className="absolute top-1 left-1 right-1 text-[10px] font-semibold bg-black/70 text-white px-2 py-0.5 rounded truncate">
                {photo.taken_at ? new Date(photo.taken_at).toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' }) : ''}
            </figcaption>
        </figure>
    );
};

const CoachCheckins = ({ clientId }) => {
    const { api, token } = useAuth();
    const [checkins, setCheckins] = useState([]);
    const [health, setHealth] = useState(null);
    const [photos, setPhotos] = useState([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        if (!clientId) return;
        setLoading(true);
        try {
            const [ci, hs, ph] = await Promise.all([
                api.get(`/admin/clients/${clientId}/checkins?limit=200`).catch(() => ({ data: [] })),
                api.get(`/admin/clients/${clientId}/health-score`).catch(() => ({ data: null })),
                api.get(`/admin/clients/${clientId}/photos`).catch(() => ({ data: { photos: [] } })),
            ]);
            setCheckins(Array.isArray(ci.data) ? ci.data : []);
            setHealth(hs.data);
            setPhotos(ph.data?.photos || []);
        } finally {
            setLoading(false);
        }
    }, [api, clientId]);

    useEffect(() => { load(); }, [load]);

    const weekly = useMemo(() => checkins.filter(c => c.type === 'weekly'), [checkins]);
    const monthly = useMemo(() => checkins.filter(c => c.type === 'monthly'), [checkins]);
    const daily = useMemo(() => checkins.filter(c => c.type === 'daily').slice(0, 14), [checkins]);

    const saveFeedback = async (checkinId, feedback) => {
        try {
            await api.post(`/admin/clients/${clientId}/checkins/${checkinId}/feedback`, { feedback });
            setCheckins(cs => cs.map(c => c.id === checkinId ? { ...c, trainer_feedback: feedback } : c));
            toast.success('Feedback guardado');
        } catch {
            toast.error('Error guardando feedback');
        }
    };

    if (loading) {
        return <div className="flex items-center justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-white/30" /></div>;
    }

    const tone = health && HEALTH[health.score];

    return (
        <div className="space-y-4">
            {tone && (
                <div className={`p-4 rounded-2xl border flex items-center gap-3 ${tone.bg}`}>
                    <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${tone.dot}`}>
                        <Heart className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className={`font-bold uppercase tracking-wider text-sm ${tone.text}`}>{tone.label}</p>
                        <p className="text-sm text-white/60">
                            {health.factors?.length ? health.factors.join(' · ') : 'Vas por buen camino'}
                            {health.days_since_checkin != null && ` · último check-in hace ${health.days_since_checkin}d`}
                        </p>
                    </div>
                </div>
            )}

            <CheckinsTable title="Check-ins semanales" columns={WEEKLY_COLS} rows={weekly} onFeedback={saveFeedback}
                empty="Este cliente no ha enviado ningún check-in semanal todavía." />
            <CheckinsTable title="Check-ins mensuales" columns={MONTHLY_COLS} rows={monthly} onFeedback={saveFeedback}
                empty="Este cliente no ha enviado ningún check-in mensual todavía." />

            {/* Diarios: resumen compacto, sin feedback */}
            <div className="bg-[#111] border border-[#222] rounded-2xl overflow-hidden">
                <div className="px-5 pt-5 pb-3 border-b border-[#222]">
                    <p className="text-xs font-bold text-white/40 uppercase tracking-wider">Check-ins diarios (últimos 14)</p>
                </div>
                {daily.length === 0 ? (
                    <p className="text-sm text-white/40 text-center py-8">Sin check-ins diarios.</p>
                ) : (
                    <ul className="divide-y divide-[#222]">
                        {daily.map(c => (
                            <li key={c.id} className="px-5 py-2.5 flex items-center justify-between text-xs">
                                <span className="text-white/50">{fmt(c.created_at)}</span>
                                <span className="text-white/70">
                                    Ánimo {c.mood}/5 · Energía {c.energy}/5 ·
                                    <span className={c.trained ? 'text-emerald-300' : 'text-red-300'}>{c.trained ? ' Entrenó' : ' No entrenó'}</span> ·
                                    <span className={c.nutrition_followed ? 'text-emerald-300' : 'text-red-300'}>{c.nutrition_followed ? ' Plan ✓' : ' Plan ✗'}</span>
                                </span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            {/* Fotos */}
            <div className="bg-[#111] border border-[#222] rounded-2xl overflow-hidden">
                <div className="px-5 pt-5 pb-3 border-b border-[#222] flex items-baseline justify-between gap-3">
                    <p className="text-xs font-bold text-white/40 uppercase tracking-wider flex items-center gap-2">
                        <Camera className="w-4 h-4 text-[#FF671F]" /> Fotos de progreso
                    </p>
                    <span className="text-xs text-white/40">{photos.length} {photos.length === 1 ? 'foto' : 'fotos'}</span>
                </div>
                <div className="px-5 py-4">
                    {photos.length === 0 ? (
                        <p className="text-sm text-white/40 text-center py-6">El cliente no ha subido fotos todavía.</p>
                    ) : (
                        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
                            {photos.map(p => <PhotoTile key={p.id} photo={p} token={token} />)}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default CoachCheckins;
