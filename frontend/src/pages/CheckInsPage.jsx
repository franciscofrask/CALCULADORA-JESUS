import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { MEDIDAS } from '../lib/medidas';
import { useEsTelefono } from '../lib/esTelefono';
import { revisarPeso, PESO_MIN, PESO_MAX } from '../lib/pesoValido';
import { useConfirm } from '../components/ui/confirm';
import { toast } from 'sonner';
import {
    Activity, TrendingUp, CheckCircle2, Smile, Frown, Meh,
    Zap, Apple, Dumbbell, Scale, Send, ChevronDown, ChevronUp, Calendar,
    Camera, Trash2, Loader2, ChevronLeft,
} from 'lucide-react';

const ORANGE = '#FF671F';
const inputCls = "w-full bg-muted border border-input rounded-xl px-3 py-2.5 text-foreground text-sm placeholder-white/20 focus:outline-none focus:border-[#FF671F] transition-colors";
const labelCls = "block text-xs font-bold text-foreground/40 uppercase tracking-wider mb-1.5";

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
const PhotosSection = ({ api }) => {
    const [photos, setPhotos] = useState([]);
    const navigate = useNavigate();

    const load = useCallback(() => {
        api.get('/reports/photos').then(r => setPhotos(r.data?.photos || [])).catch(() => {});
    }, [api]);
    useEffect(() => { load(); }, [load]);

    const remove = async (id) => {
        try { await api.delete(`/reports/photos/${id}`); setPhotos(p => p.filter(x => x.id !== id)); }
        catch (err) { toast.error(err.response?.data?.detail || 'Error borrando la foto'); }
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
                <button onClick={() => navigate('/dashboard/reports')}
                    className="text-xs text-brand hover:underline underline-offset-4 font-semibold">
                    Se suben en tu reporte
                </button>
            </div>
            {/* Vuelve a decir «tu reporte» a secas, y ahora es verdad. El 09-08 esto decía
                «mensual» como parche: las fotos solo se pedían en el reporte mensual y en una
                semana normal el cliente venía aquí, iba a Reportes y no encontraba dónde
                subirlas. El parche avisaba de la contradicción pero no la quitaba -- seguía
                sin haber sitio 3 de cada 4 semanas. Ahora el bloque de fotos está siempre en
                Reportes (punto 21), así que el enlace lleva a algo. */}
            {photos.length === 0 ? (
                <p className="text-foreground/40 text-center py-6 text-sm">
                    Aún no has subido fotos. Se piden en el reporte mensual, junto con las medidas.
                </p>
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
    const { api } = useAuth();
    const { confirm } = useConfirm();
    const navigate = useNavigate();
    const [checkins, setCheckins] = useState([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [openForm, setOpenForm] = useState(null);
    // En el teléfono, el semanal y el mensual empiezan detrás de una línea (ver abajo).
    const enTelefono = useEsTelefono();
    const [otrosAbiertos, setOtrosAbiertos] = useState(false);

    const [daily, setDaily] = useState({ energy: null, hunger_anxiety: null, comido_hoy: '' });
    const [weekly, setWeekly] = useState({ weight: '', training_compliance: '', nutrition_compliance: '', sleep_quality: '', stress_level: '', notes: '' });
    const [monthly, setMonthly] = useState({ weight: '', body_fat_pct: '', goals_progress: '', challenges: '', notes: '',
        ...Object.fromEntries(MEDIDAS.map(m => [m.key, ''])) });

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

    const todayDaily = checkins.find(c => c.type === 'daily' && isSameDay(c.created_at));

    // EL PESO DEL CHECK-IN TAMBIÉN ESCRIBE EN EL HISTÓRICO (#48 del 15-08). Aquí no había
    // ninguna validación: entraba un 50 detrás de un 94 sin decir nada, y de esa serie
    // salen la gráfica y el ritmo de cambio. Se compara con el último peso que conocemos
    // -- el del check-in más reciente que traiga uno -- y si el salto canta, se pregunta.
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
            await api.post('/checkins', {
                type: 'daily', ...daily,
                comido_hoy: (daily.comido_hoy || '').trim() || null,
            });
            toast.success('Check-in diario enviado');
            setDaily({ energy: null, hunger_anxiety: null, comido_hoy: '' });
            fetchAll();
        } catch { toast.error('Error al enviar check-in'); }
        finally { setSubmitting(false); }
    };

    const submitWeekly = async () => {
        if (!weekly.weight) return toast.error('Indica tu peso');
        if (!await pesoAceptado(weekly.weight)) return;
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
        if (!await pesoAceptado(monthly.weight)) return;
        setSubmitting(true);
        try {
            const measurements = {};
            MEDIDAS.forEach(({ key }) => { if (monthly[key]) measurements[key] = parseFloat(monthly[key]); });
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
                    {/* En el teléfono se entra aquí desde la tarjeta «Hoy · 10 segundos» de
                        Seguimiento, así que la pantalla se llama como lo que promete esa
                        tarjeta. «Seguimiento» era el nombre de la pestaña de la que viene, y
                        el subtítulo anunciaba tres check-ins cuando el documento deja uno. */}
                    <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none" data-testid="checkins-heading">
                        <span className="lg:hidden">¿Cómo vas hoy?</span>
                        <span className="hidden lg:inline">Seguimiento</span>
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        <span className="lg:hidden">Energía, hambre y qué has comido.</span>
                        <span className="hidden lg:inline">Tus check-ins diarios, semanales y mensuales</span>
                    </p>
                </div>
            </header>

            {/* Diario */}
            {todayDaily ? (
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
                        {/* Lo que ha comido de verdad, con sus palabras. No es su dieta: esa ya
                            está en la app. Es el picoteo, la cerveza y el trozo de tarta que no
                            aparecen en ningún sitio, y que son justo lo que explica por qué
                            alguien coge peso sin saber por qué. */}
                        <div>
                            <span className="text-sm text-foreground/70 mb-2 block">¿Qué has comido hoy?</span>
                            <textarea
                                rows={3}
                                value={daily.comido_hoy}
                                onChange={e => setDaily({ ...daily, comido_hoy: e.target.value })}
                                data-testid="daily-comido"
                                placeholder="Cuéntalo a tu manera, sin pesar nada. Incluye lo que picaste entre horas."
                                className={inputCls + ' resize-none'} />
                            <p className="text-[11px] text-foreground/40 mt-1.5">
                                Opcional, pero es lo que más ayuda a entender cómo te va.
                            </p>
                        </div>
                        <button onClick={submitDaily} disabled={submitting}
                            className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 disabled:opacity-60">
                            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Enviar check-in
                        </button>
                    </div>
                </Card>
            )}

            {/* EL SEMANAL Y EL MENSUAL, DETRÁS DE UNA LÍNEA EN EL TELÉFONO.
                El documento del 10-08 los quita del todo: «desaparecen el check-in semanal y
                el mensual como formularios sueltos; el peso se pide una vez, no tres; el
                sueño y el estrés, una vez, no dos». Y tiene razón en el diagnóstico: lo que
                piden está también en el reporte del mes.

                Pero borrarlos es quitar dos formularios que hoy funcionan y a los que el
                reporte solo llega cuando su ventana está abierta, así que aquí se DEMOTAN en
                vez de borrarse: dejan de ocupar media pantalla y se abren desde una línea.
                Si Francisco confirma que se van, es quitar este bloque.

                En escritorio siguen los dos como estaban. */}
            {enTelefono && !otrosAbiertos && (
                <button onClick={() => setOtrosAbiertos(true)} data-testid="ver-otros-checkins"
                    className="text-sm text-muted-foreground hover:text-foreground underline underline-offset-2">
                    Ver el check-in semanal y el mensual
                </button>
            )}
            <div className={`grid grid-cols-1 md:grid-cols-2 gap-4 ${enTelefono && !otrosAbiertos ? 'hidden' : ''}`}>
                <Collapsible open={openForm === 'weekly'} onToggle={() => setOpenForm(openForm === 'weekly' ? null : 'weekly')}
                    icon={Calendar} title="Check-in semanal" subtitle="Peso + adherencia + sueño">
                    <Field label="Peso (kg)">
                        <input type="number" step="0.1" min={PESO_MIN} max={PESO_MAX} value={weekly.weight} onChange={e => setWeekly({ ...weekly, weight: e.target.value })} className={inputCls} />
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
                    icon={TrendingUp} title="Check-in mensual" subtitle="Peso y medidas">
                    {/* EL % GRASO NO SE PIDE TODOS LOS MESES (punto 53 del doc del 07-08).
                        Aquí había un campo «% Grasa» que le salía al cliente cada mes. Es un
                        dato que estima Jesús mirando las fotos, y solo en tres momentos: al
                        principio, al empezar una fase y al acabarla. Pedírselo al cliente
                        cada cuatro semanas lo convierte en ruido - nadie nota su cambio en un
                        mes, así que repite el mismo número o pone uno al azar -, y ese ruido
                        entra luego en el eje respondedor del perfil.
                        Se anota desde la comparativa de fotos de su ficha, que es donde el
                        coach lo está mirando. */}
                    <div className="grid grid-cols-2 gap-3">
                        <Field label="Peso (kg)"><input type="number" step="0.1" min={PESO_MIN} max={PESO_MAX} value={monthly.weight} onChange={e => setMonthly({ ...monthly, weight: e.target.value })} className={inputCls} /></Field>
                    </div>
                    {/* Las MISMAS diez que en el reporte y en el punto de partida. Había
                        tres listas distintas en la app y ninguna era la suya, así que la
                        medida de un sitio no se podía comparar con la de otro. */}
                    <span className="text-xs font-bold text-foreground/40 uppercase tracking-wider block">Medidas (cm)</span>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                        {MEDIDAS.map(({ key, label }) => (
                            <Field key={key} label={label}>
                                <input type="number" step="0.1" value={monthly[key] ?? ''}
                                    onChange={e => setMonthly({ ...monthly, [key]: e.target.value })}
                                    className={inputCls} />
                            </Field>
                        ))}
                    </div>
                    <Field label="Progreso hacia tus objetivos"><textarea rows={2} value={monthly.goals_progress} onChange={e => setMonthly({ ...monthly, goals_progress: e.target.value })} className={inputCls} /></Field>
                    <Field label="Dificultades / retos"><textarea rows={2} value={monthly.challenges} onChange={e => setMonthly({ ...monthly, challenges: e.target.value })} className={inputCls} /></Field>
                    <button onClick={submitMonthly} disabled={submitting} className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 disabled:opacity-60">
                        {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Enviar
                    </button>
                </Collapsible>
            </div>

            {/* LAS FOTOS NO PINTAN NADA AQUÍ.
                Este bloque decía «se suben en tu reporte» y justo debajo «aún no has subido
                fotos»: un cajón entero para mandarte a otro sitio. Esta es la pantalla de los
                diez segundos -- energía, hambre y qué has comido --, y todo lo que no sean esos
                dos campos le quita el sentido (Jesús, 11-08).
                Las fotos siguen donde se suben, en el reporte, y se ven en Mi evolución; aquí
                no se pierde ninguna forma de llegar a ellas. En escritorio se queda, que ahí
                sobra sitio y el bloque no estorba a nadie. */}
            <div className="hidden lg:block">
                <PhotosSection api={api} />
            </div>

            {/* Historial */}
            <Card className="p-5">
                <p className="text-xs font-bold text-foreground/40 uppercase tracking-wider mb-3">Historial</p>
                {checkins.length === 0 ? (
                    <p className="text-foreground/40 text-center py-8 text-sm">Aún no tienes check-ins</p>
                ) : (
                    <ul className="space-y-3">
                        {checkins.slice(0, histShown).map(c => (
                            <li key={c.id} className="rounded-xl border border-border bg-muted p-3">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-[10px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full bg-card border border-border text-foreground/60">{c.type}</span>
                                    <span className="text-[11px] text-foreground/50">
                                        {new Date(c.created_at).toLocaleString('es-ES', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                </div>
                                {c.type === 'daily' ? (
                                    <>
                                        <p className="text-sm text-foreground/70">
                                            {/* Los check-ins viejos traen ánimo y entreno; los nuevos, no. */}
                                            {c.mood != null && `Ánimo ${c.mood}/5 · `}
                                            {c.energy != null && `Energía ${c.energy}/5`}
                                            {c.hunger_anxiety != null && ` · Hambre ${c.hunger_anxiety}/5`}
                                            {c.trained != null && (c.trained ? ' · Entrenó' : ' · No entrenó')}
                                            {c.nutrition_followed != null && (c.nutrition_followed ? ' · Dieta ✓' : ' · Dieta ✗')}
                                        </p>
                                        {c.comido_hoy && (
                                            <p className="text-sm text-foreground/60 mt-2 whitespace-pre-line border-l-2 border-border pl-3">
                                                {c.comido_hoy}
                                            </p>
                                        )}
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
                        ))}
                    </ul>
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
