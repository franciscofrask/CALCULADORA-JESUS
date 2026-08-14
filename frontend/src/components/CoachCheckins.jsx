import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import { Heart, Calendar, Camera, Loader2, Save, ChevronRight } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';

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
    if (!iso) return '-';
    try {
        const d = new Date(iso);
        return d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' }) +
            ' · ' + d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    } catch { return '-'; }
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
        return { v: ['chest', 'waist', 'hip', 'arm', 'thigh'].map(k => m[k] != null ? m[k] : '-').join(' / ') };
    } },
    { key: 'goals', label: 'Progreso objetivos', r: e => ({ v: txt(e.goals_progress), t: e.goals_progress ? 'green' : 'muted' }) },
    { key: 'chal', label: 'Retos', r: e => ({ v: txt(e.challenges), t: e.challenges ? 'amber' : 'muted' }) },
    // Las dos respuestas de los reportes de Calma, cada una en su columna. Antes venian
    // dentro de "Comentario cliente" en forma de "Importado de Calma. suplementacion=...
    // cumplimiento=...", o sea que esa columna enseñaba una cadena de la migracion en lugar
    // de lo que escribio el cliente, que ahora es lo unico que sale ahi.
    { key: 'supl', label: 'Suplementación', r: e => ({ v: txt(e.calma_suplementacion), t: e.calma_suplementacion ? 'none' : 'muted' }) },
    { key: 'cdieta', label: 'Cumplimiento dieta', r: e => ({ v: txt(e.calma_cumplimiento_dieta), t: e.calma_cumplimiento_dieta ? 'none' : 'muted' }) },
    { key: 'notes', label: 'Comentario cliente', r: e => ({ v: txt(e.notes), t: e.notes ? 'amber' : 'muted' }) },
];

// Listado de fechas + detalle en modal. Con decenas de envíos, la tabla entera
// desplegada era ilegible; y si el cliente no ha enviado nada, el bloque no se pinta.
const CheckinsLista = ({ title, columns, rows, onFeedback, resumen }) => {
    const [abiertoId, setAbiertoId] = useState(null);
    const [borrador, setBorrador] = useState('');
    const [guardando, setGuardando] = useState(false);

    if (!rows.length) return null;

    const abierto = rows.find(r => r.id === abiertoId) || null;
    const abrir = (e) => { setBorrador(e.trainer_feedback || ''); setAbiertoId(e.id); };
    const guardar = async () => {
        setGuardando(true);
        try { await onFeedback(abierto.id, borrador); setAbiertoId(null); }
        finally { setGuardando(false); }
    };

    return (
        <div className="bg-[#111] border border-[#222] rounded-2xl overflow-hidden">
            <div className="px-5 pt-5 pb-3 border-b border-[#222] flex items-baseline justify-between gap-3">
                <p className="text-xs font-bold text-white/40 uppercase tracking-wider flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-[#FF671F]" /> {title}
                </p>
                <span className="text-xs text-white/40">{rows.length} {rows.length === 1 ? 'envío' : 'envíos'}</span>
            </div>
            <ul className="divide-y divide-[#1a1a1a] max-h-[22rem] overflow-y-auto">
                {rows.map((e, i) => (
                    <li key={e.id || i}>
                        <button onClick={() => abrir(e)}
                            className="w-full flex items-center gap-3 px-5 py-2.5 text-left hover:bg-white/[0.03] transition-colors">
                            <span className="text-white text-sm tabular-nums whitespace-nowrap">{fmt(e.created_at)}</span>
                            <span className="text-white/50 text-xs truncate">{resumen(e)}</span>
                            <span className="ml-auto flex items-center gap-2 flex-shrink-0">
                                {e.trainer_feedback
                                    ? <span className="text-emerald-400 text-[10px] uppercase tracking-wider">con feedback</span>
                                    : <span className="text-white/25 text-[10px] uppercase tracking-wider">sin feedback</span>}
                                <ChevronRight className="w-4 h-4 text-white/30" />
                            </span>
                        </button>
                    </li>
                ))}
            </ul>

            <Dialog open={!!abierto} onOpenChange={(o) => !o && setAbiertoId(null)}>
                {abierto && (
                    <DialogContent className="bg-[#111] border-[#333] max-w-lg text-white" data-testid="checkin-detail">
                        <DialogHeader>
                            <DialogTitle className="uppercase tracking-wider">{title.replace('Check-ins', 'Check-in')}</DialogTitle>
                        </DialogHeader>
                        <p className="text-white/40 text-xs -mt-2">{fmt(abierto.created_at)}</p>
                        <dl className="grid grid-cols-[9rem_1fr] gap-x-4 gap-y-2 text-sm">
                            {columns.filter(c => c.key !== 'created_at').map(c => {
                                const { v, t = 'none' } = c.r(abierto) || {};
                                return (
                                    <React.Fragment key={c.key}>
                                        <dt className="text-white/40 text-xs uppercase tracking-wider pt-0.5">{c.label}</dt>
                                        <dd className={v == null ? TONE.muted : (TONE[t] || TONE.none)}>
                                            <span className="whitespace-pre-wrap leading-relaxed">{v == null ? 'sin respuesta' : v}</span>
                                        </dd>
                                    </React.Fragment>
                                );
                            })}
                        </dl>
                        <div>
                            <p className="text-white/60 text-xs mb-1">Feedback para el cliente</p>
                            <textarea value={borrador} onChange={e => setBorrador(e.target.value)} rows={3}
                                placeholder="Escribe feedback para el cliente..."
                                className="w-full bg-[#0A0A0A] border border-[#333] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#FF671F]" />
                        </div>
                        <DialogFooter>
                            <button onClick={() => setAbiertoId(null)}
                                className="px-4 py-2 rounded-lg text-sm border border-[#333] text-white">Cerrar</button>
                            <button onClick={guardar} disabled={guardando || borrador === (abierto.trainer_feedback || '')}
                                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold bg-[#FF671F] text-white disabled:opacity-40">
                                {guardando ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Guardar feedback
                            </button>
                        </DialogFooter>
                    </DialogContent>
                )}
            </Dialog>
        </div>
    );
};

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

            <CheckinsLista title="Check-ins semanales" columns={WEEKLY_COLS} rows={weekly} onFeedback={saveFeedback}
                resumen={e => [e.weight != null && `${e.weight} kg`,
                               e.training_compliance != null && `entreno ${e.training_compliance}%`,
                               e.nutrition_compliance != null && `nutrición ${e.nutrition_compliance}%`]
                               .filter(Boolean).join(' · ')} />
            <CheckinsLista title="Check-ins mensuales" columns={MONTHLY_COLS} rows={monthly} onFeedback={saveFeedback}
                resumen={e => [e.weight != null && `${e.weight} kg`,
                               e.body_fat_pct != null && `${e.body_fat_pct}% graso`]
                               .filter(Boolean).join(' · ')} />

            {/* Diarios: resumen compacto, sin feedback. Si no hay, no se pinta.
                CADA DATO SOLO SI EXISTE. Desde el 31-07 el check-in diario son dos preguntas
                (energía y hambre/ansiedad): `mood` y `trained` ya no se piden y
                `nutrition_followed` lo deduce el servidor del registro de dieta. Pintarlos a
                secas ponía "Ánimo undefined/5" y, peor, "No entrenó" en rojo sobre alguien al
                que nunca se le preguntó: información falsa delante de quien decide el ajuste. */}
            {daily.length > 0 && (
                <div className="bg-[#111] border border-[#222] rounded-2xl overflow-hidden">
                    <div className="px-5 pt-5 pb-3 border-b border-[#222]">
                        <p className="text-xs font-bold text-white/40 uppercase tracking-wider">Check-ins diarios (últimos 14)</p>
                    </div>
                    <ul className="divide-y divide-[#222]">
                        {daily.map(c => {
                            const escalas = [
                                c.energy != null && `Energía ${c.energy}/5`,
                                c.hunger_anxiety != null && `Hambre y ansiedad ${c.hunger_anxiety}/5`,
                                c.mood != null && `Ánimo ${c.mood}/5`,
                            ].filter(Boolean);
                            const sinDatos = !escalas.length && c.trained == null && c.nutrition_followed == null;
                            return (
                                <li key={c.id} className="px-5 py-2.5 text-xs">
                                    <div className="flex items-center justify-between gap-3">
                                        <span className="text-white/50 whitespace-nowrap">{fmt(c.created_at)}</span>
                                        <span className="text-white/70 text-right">
                                            {escalas.join(' · ')}
                                            {c.trained != null && (
                                                <span className={c.trained ? 'text-emerald-300' : 'text-red-300'}>
                                                    {escalas.length ? ' · ' : ''}{c.trained ? 'Entrenó' : 'No entrenó'}
                                                </span>
                                            )}
                                            {c.nutrition_followed != null && (
                                                <span className={c.nutrition_followed ? 'text-emerald-300' : 'text-red-300'}>
                                                    {(escalas.length || c.trained != null) ? ' · ' : ''}
                                                    {c.nutrition_followed ? 'Dieta registrada' : 'Sin dieta registrada'}
                                                </span>
                                            )}
                                            {sinDatos && !c.comido_hoy && <span className="text-white/30 italic">sin respuestas</span>}
                                        </span>
                                    </div>
                                    {/* Lo que dice que ha comido, con sus palabras. Es donde aparece
                                        el picoteo que no está en ninguna dieta, y suele ser la
                                        explicación de por qué alguien coge peso sin entender nada. */}
                                    {c.comido_hoy && (
                                        <p className="text-white/60 mt-1.5 whitespace-pre-line border-l-2 border-[#333] pl-3 leading-relaxed">
                                            {c.comido_hoy}
                                        </p>
                                    )}
                                </li>
                            );
                        })}
                    </ul>
                </div>
            )}

            {/* Fotos: igual, solo si las hay */}
            {photos.length > 0 && (
                <div className="bg-[#111] border border-[#222] rounded-2xl overflow-hidden">
                    <div className="px-5 pt-5 pb-3 border-b border-[#222] flex items-baseline justify-between gap-3">
                        <p className="text-xs font-bold text-white/40 uppercase tracking-wider flex items-center gap-2">
                            <Camera className="w-4 h-4 text-[#FF671F]" /> Fotos de progreso
                        </p>
                        <span className="text-xs text-white/40">{photos.length} {photos.length === 1 ? 'foto' : 'fotos'}</span>
                    </div>
                    <div className="px-5 py-4">
                        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
                            {photos.map(p => <PhotoTile key={p.id} photo={p} token={token} />)}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default CoachCheckins;
