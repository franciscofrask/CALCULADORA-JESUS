import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { useConfirm } from '../components/ui/confirm';
import { PlanBadge } from './ClientDashboard';
import { sexoLabel, objetivoLabel, equipamientoLabel, suplementoCatLabel } from '../lib/labels';
import CoachCheckins from '../components/CoachCheckins';
import { FoodFilterBar } from '../components/nutrition/SearchFoodModal';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import {
    ArrowLeft, User, Mail, Phone, Calendar, CreditCard, Dumbbell, Apple,
    FileText, Scale, Target, Zap, Save, Loader2, History, Shield,
    ClipboardList, TrendingUp, Utensils, Activity, ChevronDown, ChevronUp, ChevronRight,
    AlertCircle, CheckCircle2, Pill, Plus, X, Sparkles, Pencil, Trash2, RotateCcw,
    Headphones, CalendarClock
} from 'lucide-react';
import { etiquetaAcompanamiento, etiquetaFrecuencia } from '../lib/planAccess';

const USER_ROLES = [
    { value: 'client', label: 'Cliente' },
    { value: 'trainer', label: 'Entrenador' },
    { value: 'admin', label: 'Admin' },
];

// Fecha en la zona del coach (+dias opcionales). Con toISOString(), que es UTC, a partir
// de las 22:00 en Espana "hoy" saltaba al dia siguiente y los macros entraban tarde.
const hoyISO = (dias = 0) => {
    const d = new Date();
    d.setDate(d.getDate() + dias);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

// Fecha de una dieta. Hay documentos antiguos con la fecha corrupta (basura que dejo el
// harness de simulacion antes de que la ruta validara el formato): antes salia
// "Invalid Date" y dejaba la lista inservible.
const _fechaDieta = (f, opts = { day: 'numeric', month: 'short', year: 'numeric' }) => {
    if (typeof f !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(f)) return 'Sin fecha válida';
    const d = new Date(f + 'T12:00:00');
    return isNaN(d) ? 'Sin fecha válida' : d.toLocaleDateString('es-ES', opts);
};

// Colores de los dos ejes del perfil (motor y respondedor): alto verde, bajo rojo.
const MOTOR_COLOR = { alto: 'text-emerald-400', medio: 'text-amber-400', bajo: 'text-red-400' };

const _fechaLarga = (iso) => iso
    ? new Date(iso + 'T12:00:00').toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' })
    : '';

// ===== Buscador de menús para el coach (biblioteca real de clientes + recetario) =====
const MenuFinder = ({ api, clientId, clientUserId, clientName }) => {
    const [macros, setMacros] = useState({ P: '', H: '', G: '' });
    const [momento, setMomento] = useState('comida');
    const [fuente, setFuente] = useState('ambas');
    const [foods, setFoods] = useState([]);
    const [resultados, setResultados] = useState(null);
    const [relajado, setRelajado] = useState(false);
    const [buscando, setBuscando] = useState(false);
    const [enviando, setEnviando] = useState(null);   // id del menú que se está enviando

    // Texto plano del menú (para copiar o mandar por el chat)
    const menuATexto = (op) => {
        const t = op.macros_totales || {};
        const lineas = (op.items || []).map(it => `• ${it.nombre}: ${it.cantidad_g} g`).join('\n');
        return `Menú propuesto (${t.P?.toFixed(0)}P · ${t.H?.toFixed(0)}H · ${t.G?.toFixed(0)}G · ${t.kcal} kcal):\n${lineas}`;
    };

    const copiarMenu = async (op) => {
        try {
            await navigator.clipboard.writeText(menuATexto(op));
            toast.success('Menú copiado al portapapeles');
        } catch { toast.error('No se pudo copiar'); }
    };

    // Envía el menú al CHAT del cliente (le llega como mensaje del coach, con su
    // contador de no leídos). Es la forma de "hacer algo" con un menú encontrado.
    const enviarMenu = async (op) => {
        if (!clientUserId) { toast.error('Este cliente no tiene usuario de chat'); return; }
        const key = op.biblioteca_id || op.plantilla_id || op.letra;
        setEnviando(key);
        try {
            await api.post('/messages', { receiver_id: clientUserId, content: menuATexto(op) });
            toast.success(`Menú enviado al chat de ${clientName || 'el cliente'}`);
        } catch { toast.error('No se pudo enviar el menú'); }
        setEnviando(null);
    };

    // FoodFilterBar espera el api estilo fetch del área cliente; adaptamos el axios del admin
    const fetchApi = React.useCallback(
        (endpoint) => api.get(endpoint.replace(/^\/api/, '')).then(r => r.data),
        [api]
    );

    const buscar = async (foodsOverride) => {
        const P = parseFloat(macros.P), H = parseFloat(macros.H), G = parseFloat(macros.G);
        if ([P, H, G].some(v => isNaN(v))) { toast.error('Indica los tres macros objetivo'); return; }
        const f = foodsOverride ?? foods;
        setBuscando(true);
        try {
            const res = await api.post('/calculator/menu-options', {
                momento,
                macros_objetivo: { P, H, G },
                alimento_ids: f.map(x => x.id),
                fuentes: fuente === 'ambas' ? ['recetario', 'clientes'] : [fuente],
                client_id: clientId,
            });
            setResultados(res.data.opciones || []);
            setRelajado(!!res.data.relajado);
        } catch { toast.error('Error buscando menús'); }
        setBuscando(false);
    };

    const cambiarFoods = (f) => { setFoods(f); if (resultados !== null) buscar(f); };

    return (
        <div className="space-y-4">
            <Card className="bg-[#111] border-[#222]"><CardContent className="p-5 space-y-4">
                <p className="text-xs font-bold text-white/40 uppercase tracking-wider">Buscar menús para este cliente</p>
                <div className="grid grid-cols-3 gap-3">
                    {['P', 'H', 'G'].map(m => (
                        <div key={m}>
                            <Label className="text-white/50 text-xs">{{ P: 'Proteína (g)', H: 'Hidratos (g)', G: 'Grasas (g)' }[m]}</Label>
                            <Input type="number" value={macros[m]} onChange={e => setMacros(v => ({ ...v, [m]: e.target.value }))}
                                placeholder="0" className="bg-[#1A1A1A] border-[#333] text-white mt-1" data-testid={`menufinder-${m}`} />
                        </div>
                    ))}
                </div>
                <div className="grid grid-cols-2 gap-3">
                    <div>
                        <Label className="text-white/50 text-xs">Momento (para el recetario)</Label>
                        <select value={momento} onChange={e => setMomento(e.target.value)}
                            className="w-full mt-1 h-10 rounded-md bg-[#1A1A1A] border border-[#333] text-white text-sm px-3">
                            {['desayuno', 'comida', 'merienda', 'cena'].map(x => <option key={x} value={x}>{x}</option>)}
                        </select>
                    </div>
                    <div>
                        <Label className="text-white/50 text-xs">Fuente</Label>
                        <select value={fuente} onChange={e => setFuente(e.target.value)}
                            className="w-full mt-1 h-10 rounded-md bg-[#1A1A1A] border border-[#333] text-white text-sm px-3" data-testid="menufinder-fuente">
                            <option value="ambas">Ambas fuentes</option>
                            <option value="clientes">Solo menús reales (clientes)</option>
                            <option value="recetario">Solo recetario</option>
                        </select>
                    </div>
                </div>
                <div className="rounded-xl border border-[#222]">
                    <FoodFilterBar api={fetchApi} selected={foods} onChange={cambiarFoods} />
                </div>
                <Button onClick={() => buscar()} disabled={buscando}
                    className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold" data-testid="menufinder-buscar">
                    {buscando ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null} Buscar menús
                </Button>
            </CardContent></Card>

            {resultados !== null && (
                <Card className="bg-[#111] border-[#222]"><CardContent className="p-5 space-y-3">
                    {relajado && (
                        <p className="text-xs text-amber-500 font-medium">
                            No hay menús con todos esos alimentos a la vez: se muestran los que más se acercan.
                        </p>
                    )}
                    {resultados.length === 0 ? (
                        <p className="text-white/40 text-sm text-center py-6">Ningún menú encaja con esos macros y alimentos.</p>
                    ) : resultados.map((op) => (
                        <div key={op.biblioteca_id || op.plantilla_id || op.letra} className="border border-[#222] rounded-xl p-4 space-y-2" data-testid={`menufinder-result-${op.letra}`}>
                            <div className="flex items-center justify-between gap-2 flex-wrap">
                                <p className="font-semibold text-white text-sm flex-1 min-w-0 truncate">{op.nombre}</p>
                                <div className="flex items-center gap-1.5 flex-shrink-0">
                                    {op.fuente === 'clientes'
                                        ? <Badge className="bg-[#FF671F]/15 text-[#FF671F] border border-[#FF671F]/30 text-[10px]">REAL · {op.popularidad?.clientes || 0} clientes · {op.popularidad?.usos || 0} usos</Badge>
                                        : <Badge className="bg-white/10 text-white/60 border-0 text-[10px]">RECETARIO</Badge>}
                                    {op.cuadrada
                                        ? <Badge className="bg-green-500/15 text-green-400 border-0 text-[10px]">Cuadrada</Badge>
                                        : <Badge className="bg-amber-500/15 text-amber-400 border-0 text-[10px]">≈ Aproximada</Badge>}
                                </div>
                            </div>
                            <div className="space-y-0.5">
                                {op.items.map((it, i) => (
                                    <div key={i} className="flex justify-between text-sm">
                                        <span className="text-white/70">{it.nombre}</span>
                                        <span className="text-white/40 font-mono">{it.cantidad_g}g</span>
                                    </div>
                                ))}
                            </div>
                            <div className="flex gap-2 pt-1 items-center flex-wrap">
                                <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-green-500/15 text-green-400">{op.macros_totales?.P?.toFixed(0)}P</span>
                                <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-500/15 text-blue-400">{op.macros_totales?.H?.toFixed(0)}H</span>
                                <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/15 text-amber-400">{op.macros_totales?.G?.toFixed(0)}G</span>
                                <span className="px-2 py-0.5 rounded-full text-[11px] text-white/40">{op.macros_totales?.kcal} kcal</span>
                                <span className="flex-1" />
                                <Button size="sm" variant="outline" onClick={() => copiarMenu(op)}
                                    className="h-7 px-2.5 text-xs bg-transparent border-[#333] text-white/70 hover:text-white hover:border-[#FF671F]"
                                    data-testid={`menufinder-copiar-${op.letra}`}>
                                    Copiar
                                </Button>
                                <Button size="sm" onClick={() => enviarMenu(op)}
                                    disabled={enviando === (op.biblioteca_id || op.plantilla_id || op.letra)}
                                    className="h-7 px-2.5 text-xs bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-semibold"
                                    data-testid={`menufinder-enviar-${op.letra}`}>
                                    {enviando === (op.biblioteca_id || op.plantilla_id || op.letra)
                                        ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Enviar por chat'}
                                </Button>
                            </div>
                        </div>
                    ))}
                </CardContent></Card>
            )}
        </div>
    );
};

const ClientDetailPage = () => {
    const { clientId } = useParams();
    const navigate = useNavigate();
    const { api, user: adminUser, planCatalog } = useAuth();
    const { confirm } = useConfirm();
    // Planes asignables del catálogo (excluye complementos), para el selector de plan.
    const assignablePlans = Object.values(planCatalog || {}).filter(p => p.asignable);
    const [client, setClient] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('resumen');

    // Macros: el editor vive en la propia pestaña (precargado con los macros
    // actuales). El modal solo se usa para editar/repetir entradas del historial.
    const [entryModalOpen, setEntryModalOpen] = useState(false);
    const [sugerencia, setSugerencia] = useState(null);
    const [sugiriendo, setSugiriendo] = useState(false);
    const MACROS_FORM_VACIO = {
        training: { protein: '', carbs: '', fat: '' },
        rest: { protein: '', carbs: '', fat: '' },
        peri: { protein: '', carbs: '' },
        note: '',
        // Modelo predictivo (paso 1): criterio interno del coach y % graso del momento.
        criterio: '',
        porcentaje_graso: '',
        effective_date: hoyISO(),
    };
    const [macrosForm, setMacrosForm] = useState(MACROS_FORM_VACIO);
    const [entryForm, setEntryForm] = useState(MACROS_FORM_VACIO);
    const [savingMacros, setSavingMacros] = useState(false);
    const [savingEntry, setSavingEntry] = useState(false);
    // Sugerencia de la IA que dio pie al ajuste que hay ahora en el editor (si la hubo).
    const [sugerenciaId, setSugerenciaId] = useState(null);
    const editorMacrosRef = useRef(null);

    // Routine
    const [generatingRoutine, setGeneratingRoutine] = useState(false);
    const [routineInstructions, setRoutineInstructions] = useState('');
    const [generatedRoutine, setGeneratedRoutine] = useState(null);

    // Suplementos
    const [supProtocol, setSupProtocol] = useState({ actual: [], siguiente: [], siguiente_fecha: '', nota: '' });
    const [supCatalog, setSupCatalog] = useState([]);
    const [supSaving, setSupSaving] = useState(false);
    const [supSuggesting, setSupSuggesting] = useState(false);

    // Visor de dietas (pestaña Nutrición)
    const [selectedDietDate, setSelectedDietDate] = useState(null);
    const [selectedDiet, setSelectedDiet] = useState(null);
    const [dietLoading, setDietLoading] = useState(false);
    const openDiet = async (fecha) => {
        setSelectedDietDate(fecha); setSelectedDiet(null); setDietLoading(true);
        try {
            const r = await api.get(`/admin/clients/${clientId}/diet`, { params: { fecha } });
            setSelectedDiet(r.data);
        } catch {
            toast.error('No se pudo cargar la dieta de esa fecha');
        } finally {
            setDietLoading(false);
        }
    };

    // Asignación de coach
    const [trainers, setTrainers] = useState([]);
    const [assigningTrainer, setAssigningTrainer] = useState(false);
    const changeTrainer = async (value) => {
        setAssigningTrainer(true);
        try {
            const trainerId = value === 'none' ? null : value;
            await api.put(`/admin/clients/${clientId}/trainer`, { trainer_id: trainerId });
            toast.success(trainerId ? 'Coach asignado' : 'Coach quitado');
            fetchClient();
        } catch (e) {
            toast.error(e.response?.data?.detail || 'No se pudo cambiar el coach');
        } finally { setAssigningTrainer(false); }
    };

    useEffect(() => { fetchClient(); }, [clientId]); // eslint-disable-line
    useEffect(() => { api.get('/admin/supplements/catalog').then(r => setSupCatalog(r.data || [])).catch(() => {}); }, []); // eslint-disable-line
    useEffect(() => { api.get('/admin/trainers').then(r => setTrainers(r.data || [])).catch(() => {}); }, []); // eslint-disable-line

    const fetchClient = async () => {
        try {
            const response = await api.get(`/admin/clients/${clientId}`);
            setClient(response.data);
            const sp = response.data.supplement_protocol;
            if (sp) setSupProtocol({ actual: sp.actual || [], siguiente: sp.siguiente || [], siguiente_fecha: sp.siguiente_fecha || '', nota: sp.nota || '' });
            // El editor de la pestana Macros arranca siempre con los macros guardados
            // (mismo criterio que macrosActuales: 0 es un valor valido, no un hueco).
            const p = response.data.profile;
            const _v = (m, k1, k2) => { const v = m?.[k1] ?? m?.[k2]; return v == null ? '' : String(v); };
            setMacrosForm({
                training: { protein: _v(p?.macros_training, 'protein', 'proteinas'), carbs: _v(p?.macros_training, 'carbs', 'hidratos'), fat: _v(p?.macros_training, 'fat', 'grasas') },
                rest: { protein: _v(p?.macros_rest, 'protein', 'proteinas'), carbs: _v(p?.macros_rest, 'carbs', 'hidratos'), fat: _v(p?.macros_rest, 'fat', 'grasas') },
                peri: { protein: _v(p?.macros_periworkout, 'protein', 'proteinas'), carbs: _v(p?.macros_periworkout, 'carbs', 'hidratos') },
                note: '',
                criterio: '',
                porcentaje_graso: p?.body_fat != null ? String(p.body_fat) : '',
                effective_date: hoyISO(),
            });
        } catch (error) {
            toast.error('Error al cargar datos del cliente');
            navigate('/admin/clients');
        } finally { setLoading(false); }
    };

    // Editar/eliminar/repetir entradas del historial de macros
    const [editingEntryId, setEditingEntryId] = useState(null);
    const _g = (m, a, b) => { const v = m?.[a] ?? m?.[b]; return v == null ? '' : v; };
    const macroFormFromEntry = (h, opts = {}) => ({
        training: { protein: _g(h.training, 'protein', 'proteinas'), carbs: _g(h.training, 'carbs', 'hidratos'), fat: _g(h.training, 'fat', 'grasas') },
        rest: { protein: _g(h.rest, 'protein', 'proteinas'), carbs: _g(h.rest, 'carbs', 'hidratos'), fat: _g(h.rest, 'fat', 'grasas') },
        peri: { protein: _g(h.peri, 'protein', 'proteinas'), carbs: _g(h.peri, 'carbs', 'hidratos') },
        effective_date: opts.today ? hoyISO() : (h.effective_date || hoyISO()),
        note: opts.note != null ? opts.note : (h.note || ''),
        criterio: h.criterio || '',
        porcentaje_graso: h.body_fat != null ? String(h.body_fat) : '',
    });
    // Agente de re-ajuste de macros: pide la sugerencia y, si el coach la acepta,
    // pre-rellena el editor de macros con la propuesta (vigente manana).
    const pedirSugerencia = async () => {
        setSugiriendo(true); setSugerencia(null);
        try {
            const r = await api.post(`/admin/clients/${clientId}/sugerir-ajuste`);
            if (r.data?.propuesta) setSugerencia(r.data);
            else toast.error('El asistente no devolvió una propuesta válida');
        } catch (e) { toast.error(e.response?.data?.detail || 'No se pudo obtener la sugerencia'); }
        finally { setSugiriendo(false); }
    };
    // Vuelca la propuesta de la IA en el editor de la pestaña: el coach la ve
    // sobre los macros actuales, la retoca si quiere y guarda desde ahi.
    const usarSugerencia = () => {
        const p = sugerencia?.propuesta; if (!p) return;
        // Arrastramos el id: al guardar, el backend compara lo que propuso la IA con
        // lo que dejaste tu y registra la correccion.
        setSugerenciaId(sugerencia.sugerencia_id || null);
        setMacrosForm({
            training: { protein: p.entreno?.proteina ?? '', carbs: p.entreno?.hidratos ?? '', fat: p.entreno?.grasa ?? '' },
            rest: { protein: p.descanso?.proteina ?? '', carbs: p.descanso?.hidratos ?? '', fat: p.descanso?.grasa ?? '' },
            peri: { protein: p.perientreno?.proteina ?? '', carbs: p.perientreno?.hidratos ?? '' },
            note: (sugerencia?.razonamiento || '').slice(0, 300),
            effective_date: hoyISO(1),
        });
        toast.success('Propuesta cargada en el editor: revísala y guarda');
        editorMacrosRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
    const openEditEntry = (h) => { setEditingEntryId(h.id); setEntryForm(macroFormFromEntry(h)); setEntryModalOpen(true); };
    const openRepeatEntry = (h) => {
        const d = h.effective_date ? new Date(h.effective_date + 'T12:00:00') : new Date(h.created_at);
        setEditingEntryId(null);
        setEntryForm(macroFormFromEntry(h, { today: true, note: `Repetición de los macros del ${d.toLocaleDateString('es-ES')}` }));
        setEntryModalOpen(true);
    };
    // Modelo predictivo (paso 1): evaluar como salio la fase que abrio un ajuste.
    const [evalEntry, setEvalEntry] = useState(null);   // entrada del historial en edicion
    const [evalForm, setEvalForm] = useState({ resultado: 'buena', causa: 'cliente', nota: '' });
    const [savingEval, setSavingEval] = useState(false);
    const openEvaluar = (h) => {
        const ev = h.evaluacion || {};
        setEvalForm({ resultado: ev.resultado || 'buena', causa: ev.causa || 'cliente', nota: ev.nota || '' });
        setEvalEntry(h);
    };
    const guardarEvaluacion = async () => {
        if (!evalEntry) return;
        setSavingEval(true);
        try {
            await api.put(`/admin/clients/${clientId}/macro-history/${evalEntry.id}/evaluacion`, {
                resultado: evalForm.resultado,
                causa: evalForm.resultado === 'mala' ? evalForm.causa : null,
                nota: evalForm.nota.trim() || null,
            });
            toast.success('Evaluación guardada');
            setEvalEntry(null);
            fetchClient();
        } catch (e) { toast.error(e?.response?.data?.detail || 'No se pudo guardar la evaluación'); }
        finally { setSavingEval(false); }
    };

    const deleteMacroEntry = async (h) => {
        if (!await confirm({
            title: '¿Eliminar esta entrada del historial?',
            description: 'Se borra el registro de ese cambio. No afecta a los macros que el cliente tiene ahora.',
            confirmLabel: 'Eliminar', danger: true,
        })) return;
        try { await api.delete(`/admin/clients/${clientId}/macro-history/${h.id}`); toast.success('Entrada eliminada'); fetchClient(); }
        catch { toast.error('No se pudo eliminar la entrada'); }
    };

    // Gestión de usuario (rol, plan cortesía, baja lógica) desde la ficha del cliente
    const [savingMgmt, setSavingMgmt] = useState(false);
    const changeUserRole = async (role) => {
        const uid = client?.user?.id; if (!uid) return;
        setSavingMgmt(true);
        try { await api.put(`/admin/users/${uid}`, { role }); toast.success('Rol actualizado'); fetchClient(); }
        catch (e) { toast.error(e?.response?.data?.detail || 'Error al cambiar el rol'); }
        finally { setSavingMgmt(false); }
    };
    const setUserPlan = async (plan, comp) => {
        const uid = client?.user?.id; if (!uid) return;
        try { await api.put(`/admin/users/${uid}`, { plan: plan || null, comp_plan: comp }); toast.success('Plan actualizado'); fetchClient(); }
        catch { toast.error('Error al actualizar el plan'); }
    };
    const toggleUserBaja = async () => {
        const uid = client?.user?.id; if (!uid) return;
        if (client.user.deleted_at) {
            try { await api.post(`/admin/users/${uid}/restore`); toast.success('Usuario reactivado'); fetchClient(); }
            catch { toast.error('No se pudo reactivar'); }
            return;
        }
        if (!await confirm({
            title: '¿Dar de baja a este usuario?',
            description: 'No podrá entrar, pero los datos se conservan y se puede reactivar cuando quieras.',
            confirmLabel: 'Dar de baja', danger: true,
        })) return;
        try { await api.delete(`/admin/users/${uid}`); toast.success('Usuario dado de baja'); fetchClient(); }
        catch (e) { toast.error(e?.response?.data?.detail || 'No se pudo dar de baja'); }
    };

    const macrosFormToBody = (f) => ({
        training: { protein: parseFloat(f.training.protein), carbs: parseFloat(f.training.carbs), fat: parseFloat(f.training.fat) },
        rest: { protein: parseFloat(f.rest.protein), carbs: parseFloat(f.rest.carbs), fat: parseFloat(f.rest.fat) },
        peri: { protein: parseFloat(f.peri.protein) || 0, carbs: parseFloat(f.peri.carbs) || 0 },
        note: f.note,
        criterio: (f.criterio || '').trim() || null,
        porcentaje_graso: f.porcentaje_graso === '' || f.porcentaje_graso == null ? null : parseFloat(f.porcentaje_graso),
        effective_date: f.effective_date,
    });
    const macrosFormIncompleto = (f) => ['training', 'rest'].some(
        b => ['protein', 'carbs', 'fat'].some(k => f[b][k] === '' || f[b][k] == null || isNaN(parseFloat(f[b][k])))
    );

    // Guarda los macros del cliente desde el editor de la pestaña.
    const handleSaveMacros = async () => {
        if (macrosFormIncompleto(macrosForm)) { toast.error('Completa proteína, hidratos y grasa de entrenamiento y descanso'); return; }
        if (!macrosForm.note.trim()) { toast.error('El feedback para el cliente es obligatorio'); return; }
        setSavingMacros(true);
        try {
            await api.put(`/admin/clients/${clientId}/macros`, { ...macrosFormToBody(macrosForm), sugerencia_id: sugerenciaId });
            toast.success('Macros actualizados');
            setSugerencia(null);
            setSugerenciaId(null);
            fetchClient();
        } catch (error) { toast.error(error?.response?.data?.detail || 'Error al guardar'); }
        finally { setSavingMacros(false); }
    };

    // Guarda una entrada del historial (editar) o la reaplica como macros actuales (repetir).
    const handleSaveEntry = async () => {
        if (macrosFormIncompleto(entryForm)) { toast.error('Completa proteína, hidratos y grasa de entrenamiento y descanso'); return; }
        if (!editingEntryId && !entryForm.note.trim()) { toast.error('El motivo es obligatorio'); return; }
        setSavingEntry(true);
        try {
            const body = macrosFormToBody(entryForm);
            if (editingEntryId) {
                await api.put(`/admin/clients/${clientId}/macro-history/${editingEntryId}`, body);
                toast.success('Entrada del historial actualizada');
            } else {
                await api.put(`/admin/clients/${clientId}/macros`, body);
                toast.success('Macros actualizados');
            }
            setEntryModalOpen(false);
            setEditingEntryId(null);
            fetchClient();
        } catch (error) { toast.error(error?.response?.data?.detail || 'Error al guardar'); }
        finally { setSavingEntry(false); }
    };

    // Calma quiereRepartoDeComidas: coach toggles single-meal mode for this client.
    const handleToggleSingleMeal = async (val) => {
        try {
            await api.put(`/admin/clients/${clientId}`, { single_meal_mode: val });
            toast.success(val ? 'Dieta de comida única activada' : 'Reparto por comidas activado');
            fetchClient();
        } catch (error) { toast.error('Error actualizando estructura de dieta'); }
    };

    const handleGenerateRoutine = async () => {
        setGeneratingRoutine(true);
        try {
            const response = await api.post('/admin/routines/generate', { client_id: clientId, instructions: routineInstructions });
            setGeneratedRoutine(response.data.routine);
            toast.success('Rutina generada con IA');
        } catch (error) { toast.error('Error al generar rutina'); }
        finally { setGeneratingRoutine(false); }
    };

    const handleSaveRoutine = async () => {
        if (!generatedRoutine) return;
        try {
            await api.post(`/admin/routines/save?client_id=${clientId}`, generatedRoutine);
            toast.success('Rutina guardada');
            setGeneratedRoutine(null);
            fetchClient();
        } catch (error) { toast.error('Error al guardar rutina'); }
    };

    // ── Suplementos ──
    const catalogToItem = (c) => ({ catalog_id: c.id, titulo: c.titulo, imagen: c.imagen, enlaces: c.enlaces || [], cuando: c.cuando || '', cuanto: c.cuanto || '', observaciones: c.observaciones || '' });
    const supAdd = (bloque, catId) => {
        const c = supCatalog.find(x => x.id === catId);
        if (!c) return;
        setSupProtocol(prev => ({ ...prev, [bloque]: [...prev[bloque], catalogToItem(c)] }));
    };
    const supRemove = (bloque, idx) => setSupProtocol(prev => ({ ...prev, [bloque]: prev[bloque].filter((_, i) => i !== idx) }));
    const supSuggest = async () => {
        setSupSuggesting(true);
        try {
            const r = await api.post(`/admin/supplements/suggest?client_id=${clientId}`);
            setSupProtocol(prev => ({ ...prev, actual: r.data.actual || [] }));
            toast.success('Protocolo sugerido (revísalo y guarda)');
        } catch (e) { toast.error('Error al sugerir'); }
        finally { setSupSuggesting(false); }
    };
    const supSave = async () => {
        setSupSaving(true);
        try {
            await api.post(`/admin/supplements/save?client_id=${clientId}`, {
                actual: supProtocol.actual, siguiente: supProtocol.siguiente,
                siguiente_fecha: supProtocol.siguiente_fecha || null, nota: supProtocol.nota || null,
            });
            toast.success('Suplementación guardada');
            fetchClient();
        } catch (e) { toast.error('Error al guardar suplementación'); }
        finally { setSupSaving(false); }
    };

    if (loading) return <div className="p-6 bg-[#0A0A0A] min-h-screen"><div className="animate-pulse space-y-4"><div className="h-8 bg-[#222] rounded w-1/4" /><div className="h-48 bg-[#111] rounded-xl" /></div></div>;
    if (!client) return <div className="p-6 bg-[#0A0A0A] min-h-screen text-center text-white/50">Cliente no encontrado</div>;

    const { profile, user, routines, reports, payments, macro_history, nutrition_stats, calma_raw } = client;
    const mt = profile?.macros_training;
    const mr = profile?.macros_rest;
    const mp = profile?.macros_periworkout;
    const activeRoutine = routines?.find(r => r.status === 'active');

    // Macros guardados ahora mismo, en el mismo formato que el formulario: sirven
    // para precargar el editor, marcar lo que el coach ha tocado y poder descartar.
    const _cur = (m, k1, k2) => { const v = m?.[k1] ?? m?.[k2]; return v == null ? '' : String(v); };
    const macrosActuales = {
        training: { protein: _cur(mt, 'protein', 'proteinas'), carbs: _cur(mt, 'carbs', 'hidratos'), fat: _cur(mt, 'fat', 'grasas') },
        rest: { protein: _cur(mr, 'protein', 'proteinas'), carbs: _cur(mr, 'carbs', 'hidratos'), fat: _cur(mr, 'fat', 'grasas') },
        peri: { protein: _cur(mp, 'protein', 'proteinas'), carbs: _cur(mp, 'carbs', 'hidratos') },
    };
    const bfActual = profile?.body_fat != null ? String(profile.body_fat) : '';
    const macrosTocados = ['training', 'rest', 'peri'].some(
        b => Object.keys(macrosActuales[b]).some(k => String(macrosForm[b][k] ?? '') !== macrosActuales[b][k])
    ) || String(macrosForm.porcentaje_graso ?? '') !== bfActual;
    const setMacroCampo = (bloque, campo, valor) => setMacrosForm(prev => ({ ...prev, [bloque]: { ...prev[bloque], [campo]: valor } }));
    const descartarCambiosMacros = () => (setSugerenciaId(null), setMacrosForm({
        ...macrosActuales, note: '', criterio: '', porcentaje_graso: bfActual,
        effective_date: hoyISO(),
    }));

    const TAB_CONFIG = [
        { id: 'resumen', label: 'Resumen', icon: User },
        { id: 'macros', label: 'Macros', icon: Apple },
        { id: 'membresia', label: 'Membresía', icon: CreditCard },
        { id: 'cuestionario', label: 'Cuestionario', icon: ClipboardList },
        { id: 'entrenamiento', label: 'Entreno', icon: Dumbbell },
        { id: 'nutricion', label: 'Nutrición', icon: Utensils },
        { id: 'menus', label: 'Menús', icon: ClipboardList },
        { id: 'suplementos', label: 'Suplementos', icon: Pill },
        { id: 'seguimiento', label: 'Seguimiento', icon: TrendingUp },
    ];

    return (
        <div className="p-4 md:p-6 space-y-5 animate-fade-in bg-[#0A0A0A] min-h-screen" data-testid="client-detail">
            {/* Header */}
            <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" onClick={() => navigate('/admin/clients')} className="text-white/50 hover:text-white"><ArrowLeft className="w-5 h-5" /></Button>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                        <h1 className="text-2xl font-bold text-white truncate" style={{ fontFamily: 'Barlow Condensed' }}>{user?.name?.toUpperCase()}</h1>
                        <PlanBadge plan={profile?.plan} />
                        <Badge className={profile?.status === 'activo' ? 'bg-green-500/20 text-green-500 border-0' : 'bg-red-500/20 text-red-400 border-0'}>{profile?.status}</Badge>
                    </div>
                    <p className="text-white/40 text-sm truncate">{user?.email}</p>
                </div>
            </div>

            {/* 8 Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <div className="overflow-x-auto -mx-4 px-4">
                    <TabsList className="inline-flex w-auto min-w-full bg-[#111] p-1 rounded-xl gap-0.5">
                        {TAB_CONFIG.map(t => (
                            <TabsTrigger key={t.id} value={t.id} className="text-xs px-3 py-2 data-[state=active]:bg-[#FF671F] data-[state=active]:text-white text-white/50 rounded-lg whitespace-nowrap" data-testid={`tab-${t.id}`}>
                                <t.icon className="w-3.5 h-3.5 mr-1.5" />{t.label}
                            </TabsTrigger>
                        ))}
                    </TabsList>
                </div>

                {/* ========== TAB 1: RESUMEN ========== */}
                <TabsContent value="resumen">
                    <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                            <InfoItem icon={User} label="Nombre" value={user?.name} />
                            <InfoItem icon={Mail} label="Email" value={user?.email} />
                            <InfoItem icon={Phone} label="Teléfono" value={user?.phone || '-'} />
                            <InfoItem icon={Shield} label="Plan" value={<PlanBadge plan={profile?.plan} planName={planCatalog?.[profile?.plan]?.name} />} />
                            <InfoItem icon={Activity} label="Estado" value={profile?.status} />
                            <InfoItem icon={Calendar} label="Semana" value={(() => {
                                const sem = planCatalog?.[profile?.plan]?.ciclo?.semanas;
                                return sem ? `${profile?.week || 1}/${sem}` : `${profile?.week || 1}`;
                            })()} />
                            {/* Lo que le corresponde por plan: si le toca entrenador y cada
                                cuánto se le escribe. Sale del catálogo, no de este cliente. */}
                            <InfoItem icon={Headphones} label="Acompañamiento"
                                value={etiquetaAcompanamiento(planCatalog?.[profile?.plan]?.habilitaciones?.acompanamiento)} />
                            <InfoItem icon={CalendarClock} label="Contacto"
                                value={etiquetaFrecuencia(planCatalog?.[profile?.plan]?.habilitaciones?.frecuencia_contacto)} />
                            <InfoItem icon={Dumbbell} label="Entrenador" value={(() => {
                                const trainerId = profile?.trainer_id || null;
                                const trainerName = trainers.find(t => t.id === trainerId)?.name || trainerId;
                                const isCoach = adminUser?.role === 'trainer';
                                // Coach viendo un cliente de otro coach: solo lectura
                                if (isCoach && trainerId && trainerId !== adminUser?.id) return trainerName;
                                // Coach y cliente sin coach: solo puede asignarse a si mismo
                                if (isCoach && !trainerId) return (
                                    <Button size="sm" disabled={assigningTrainer} onClick={() => changeTrainer(adminUser.id)}
                                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs h-7 px-2" data-testid="assign-me-trainer">
                                        Asignarme
                                    </Button>
                                );
                                // Admin, o el coach actual: puede asignar, traspasar o quitar
                                return (
                                    <select value={trainerId || 'none'} disabled={assigningTrainer} onChange={e => changeTrainer(e.target.value)}
                                        className="bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-1" data-testid="trainer-select">
                                        <option value="none">Sin asignar</option>
                                        {trainerId && !trainers.some(t => t.id === trainerId) && <option value={trainerId}>{trainerName}</option>}
                                        {trainers.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                                    </select>
                                );
                            })()} />
                            <InfoItem icon={Target} label="Rutina" value={activeRoutine ? `${activeRoutine.days?.filter(d => !d.is_rest).length || 0} días` : 'Sin rutina'} />
                            <InfoItem icon={CreditCard} label="Próx. cobro" value={profile?.next_payment ? new Date(profile.next_payment).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }) : '-'} />
                            <InfoItem icon={Calendar} label="Inicio" value={profile?.created_at ? new Date(profile.created_at).toLocaleDateString('es-ES') : '-'} />
                            <InfoItem icon={Scale} label="Peso" value={profile?.weight ? `${profile.weight} kg` : '-'} />
                            <InfoItem icon={Target} label="Objetivo" value={objetivoLabel(profile?.goal)} />
                        </div>
                    </CardContent></Card>
                </TabsContent>

                {/* ========== TAB 2: MACROS ========== */}
                <TabsContent value="macros" className="space-y-4">
                    {/* Editor de macros siempre a la vista, precargado con los actuales:
                        el coach edita a mano o vuelca la propuesta de la IA y guarda aqui. */}
                    <Card className="bg-[#111] border-[#222]" ref={editorMacrosRef}><CardContent className="p-5">
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                            <div className="flex items-center gap-2">
                                <p className="text-xs font-bold text-white/40 uppercase tracking-wider">Macros del cliente</p>
                                {mt && <Badge className={`border-0 text-[10px] ${profile?.macros_source === 'auto' ? 'bg-green-500/20 text-green-500' : 'bg-yellow-500/20 text-yellow-400'}`}>{profile?.macros_source || 'manual'}</Badge>}
                                {macrosTocados && <Badge className="border-0 text-[10px] bg-[#FF671F]/20 text-[#FF671F]">sin guardar</Badge>}
                            </div>
                            <Button size="sm" variant="outline" className="bg-transparent border-[#FF671F]/40 text-[#FF671F] hover:bg-[#FF671F]/10 text-xs" onClick={pedirSugerencia} disabled={sugiriendo} data-testid="suggest-macros-btn">{sugiriendo ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Sparkles className="w-3 h-3 mr-1" />}Sugerir ajuste (IA)</Button>
                        </div>
                        {!mt && <p className="text-white/40 text-xs mb-3">Este cliente aún no tiene macros asignados: rellénalos aquí o pídele una propuesta al asistente.</p>}
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                            <MacroEditGroup title="Entrenamiento" icon={Zap} color="#FF671F" fields={[
                                { label: 'Proteína', value: macrosForm.training.protein, actual: macrosActuales.training.protein, onChange: v => setMacroCampo('training', 'protein', v), testId: 'macro-input-tp' },
                                { label: 'Hidratos', value: macrosForm.training.carbs, actual: macrosActuales.training.carbs, onChange: v => setMacroCampo('training', 'carbs', v) },
                                { label: 'Grasa', value: macrosForm.training.fat, actual: macrosActuales.training.fat, onChange: v => setMacroCampo('training', 'fat', v) },
                            ]} />
                            <MacroEditGroup title="Perientreno" icon={Activity} color="#EAB308" fields={[
                                { label: 'Proteína', value: macrosForm.peri.protein, actual: macrosActuales.peri.protein, onChange: v => setMacroCampo('peri', 'protein', v) },
                                { label: 'Hidratos', value: macrosForm.peri.carbs, actual: macrosActuales.peri.carbs, onChange: v => setMacroCampo('peri', 'carbs', v) },
                            ]} />
                            <MacroEditGroup title="Descanso" icon={Scale} color="#22C55E" fields={[
                                { label: 'Proteína', value: macrosForm.rest.protein, actual: macrosActuales.rest.protein, onChange: v => setMacroCampo('rest', 'protein', v) },
                                { label: 'Hidratos', value: macrosForm.rest.carbs, actual: macrosActuales.rest.carbs, onChange: v => setMacroCampo('rest', 'carbs', v) },
                                { label: 'Grasa', value: macrosForm.rest.fat, actual: macrosActuales.rest.fat, onChange: v => setMacroCampo('rest', 'fat', v) },
                            ]} />
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <Label className="text-white/60 text-xs">Vigente desde</Label>
                                    <Input type="date" value={macrosForm.effective_date} onChange={e => setMacrosForm({ ...macrosForm, effective_date: e.target.value })} className={`bg-[#0A0A0A] text-white mt-1 ${macrosForm.effective_date !== hoyISO() ? 'border-[#FF671F]' : 'border-[#333]'}`} data-testid="macro-effective-date" />
                                    {macrosForm.effective_date !== hoyISO() ? (
                                        <p className="text-[10px] text-[#FF671F] mt-1 leading-relaxed">
                                            {macrosForm.effective_date > hoyISO()
                                                ? `No se aplican hasta el ${_fechaLarga(macrosForm.effective_date)}: hasta ese día sigue con los actuales. `
                                                : `Se aplican hacia atrás, desde el ${_fechaLarga(macrosForm.effective_date)}. `}
                                            <button type="button" className="underline font-bold"
                                                onClick={() => setMacrosForm({ ...macrosForm, effective_date: hoyISO() })}>Poner hoy</button>
                                        </p>
                                    ) : (
                                        <p className="text-[10px] text-white/30 mt-1">Las dietas anteriores conservan los macros previos.</p>
                                    )}
                                </div>
                                <div>
                                    <Label className="text-white/60 text-xs">% graso</Label>
                                    <Input type="number" step="0.1" min="3" max="60" value={macrosForm.porcentaje_graso}
                                        onChange={e => setMacrosForm({ ...macrosForm, porcentaje_graso: e.target.value })}
                                        placeholder="-" className="bg-[#0A0A0A] border-[#333] text-white mt-1" data-testid="macro-body-fat" />
                                    <p className="text-[10px] text-white/30 mt-1">El del momento del ajuste. Queda en el historial.</p>
                                </div>
                            </div>
                            <div className="grid grid-cols-1 gap-3">
                                <div>
                                    <Label className="text-white/60 text-xs">Criterio del ajuste (interno)</Label>
                                    <Textarea value={macrosForm.criterio} onChange={e => setMacrosForm({ ...macrosForm, criterio: e.target.value })} placeholder="Ej: estancado dos meses cumpliendo, recorto un escalón de hidratos..." className="bg-[#0A0A0A] border-[#333] text-white mt-1 min-h-[38px]" data-testid="macro-criterio" />
                                    <p className="text-[10px] text-white/30 mt-1">Por qué haces este ajuste. No lo ve el cliente: es lo que aprende el modelo.</p>
                                </div>
                                <div>
                                    <Label className="text-white/60 text-xs">Feedback para el cliente (obligatorio)</Label>
                                    <Textarea value={macrosForm.note} onChange={e => setMacrosForm({ ...macrosForm, note: e.target.value })} placeholder="Ej: Bajamos un poco los hidratos por la pérdida de peso, sigue así..." className="bg-[#0A0A0A] border-[#333] text-white mt-1 min-h-[38px]" data-testid="macro-note" />
                                    <p className="text-[10px] text-white/30 mt-1">Le llega al cliente como novedad al guardar (sustituye al audio).</p>
                                </div>
                            </div>
                        </div>
                        <div className="flex items-center justify-end gap-2 mt-4">
                            {macrosTocados && <Button size="sm" variant="ghost" className="text-white/50 hover:text-white text-xs" onClick={descartarCambiosMacros}>Descartar cambios</Button>}
                            <Button onClick={handleSaveMacros} disabled={savingMacros || !macrosTocados} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white disabled:opacity-40" data-testid="save-macros-btn">{savingMacros ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save className="w-4 h-4 mr-1" />Guardar macros</>}</Button>
                        </div>
                    </CardContent></Card>

                    {/* Sugerencia del agente de re-ajuste de macros (revisar y confirmar) */}
                    {sugerencia?.propuesta && (
                        <Card className="bg-[#111] border-[#FF671F]/30">
                            <CardContent className="p-5 space-y-3">
                                <div className="flex items-center gap-2">
                                    <Sparkles className="w-4 h-4 text-[#FF671F]" />
                                    <p className="text-xs font-bold text-white uppercase tracking-wider">Ajuste sugerido por el asistente</p>
                                    <span className="text-white/30 text-[10px] ml-auto">confianza: {sugerencia.confianza || '—'}{sugerencia._modelo ? ` · ${sugerencia._modelo}` : ''}</span>
                                </div>
                                {/* Perfil derivado del camino del cliente (motor x respondedor) */}
                                {sugerencia.perfil && (
                                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs bg-[#0A0A0A] rounded-lg p-3 border border-[#222]">
                                        <span className="text-white/40 uppercase tracking-wider text-[10px]">Perfil</span>
                                        <span className="text-white/50">Motor <b className={MOTOR_COLOR[sugerencia.perfil.motor] || 'text-white'}>{sugerencia.perfil.motor || 'sin dato'}</b>
                                            {sugerencia.perfil.hc_kg_techo != null && <span className="text-white/30"> ({sugerencia.perfil.hc_kg_techo} g HC/kg en su techo)</span>}</span>
                                        <span className="text-white/50">Respondedor <b className={MOTOR_COLOR[sugerencia.perfil.respondedor] || 'text-white/40'}>{sugerencia.perfil.respondedor === 'sin_dato' ? 'sin dato' : sugerencia.perfil.respondedor}</b>
                                            {sugerencia.perfil.indice_hidrato_grasa_techo != null && <span className="text-white/30"> (índice {sugerencia.perfil.indice_hidrato_grasa_techo})</span>}</span>
                                        {sugerencia.perfil.techo_hc != null && <span className="text-white/50">Techo/suelo <b className="text-white">{sugerencia.perfil.techo_hc}/{sugerencia.perfil.suelo_hc} g</b></span>}
                                        {sugerencia.perfil.umbral_definicion != null && <span className="text-white/50">Umbral def. <b className="text-white">{sugerencia.perfil.umbral_definicion} g</b></span>}
                                        {sugerencia.perfil.umbral_volumen != null && <span className="text-white/50">Umbral vol. <b className="text-white">{sugerencia.perfil.umbral_volumen} g</b></span>}
                                        {sugerencia.contexto_usado?.n_reglas_perfil > 0 && <span className="text-white/30">{sugerencia.contexto_usado.n_reglas_perfil} reglas de su perfil</span>}
                                    </div>
                                )}
                                {sugerencia.contexto_decision && Object.keys(sugerencia.contexto_decision).length > 0 && (
                                    <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs bg-[#0A0A0A] rounded-lg p-3 border border-[#222]">
                                        {sugerencia.contexto_decision.peso_actual != null && (
                                            <span className="text-white/50">Último peso: <b className="text-white">{sugerencia.contexto_decision.peso_actual} kg</b>{sugerencia.contexto_decision.fecha_actual ? <span className="text-white/30"> · {sugerencia.contexto_decision.fecha_actual}</span> : null}</span>
                                        )}
                                        {sugerencia.contexto_decision.delta_ultimo != null && (
                                            <span className="text-white/50">Desde el anterior: <b className="text-white">{sugerencia.contexto_decision.delta_ultimo > 0 ? '+' : ''}{sugerencia.contexto_decision.delta_ultimo} kg</b>{sugerencia.contexto_decision.dias_desde_anterior != null ? <span className="text-white/30"> ({sugerencia.contexto_decision.dias_desde_anterior} días)</span> : null}</span>
                                        )}
                                        {sugerencia.contexto_decision.delta_inicio != null && (
                                            <span className="text-white/50">Desde el inicio: <b className="text-white">{sugerencia.contexto_decision.delta_inicio > 0 ? '+' : ''}{sugerencia.contexto_decision.delta_inicio} kg</b></span>
                                        )}
                                        {sugerencia.contexto_decision.cumplimiento_dieta && (
                                            <span className="text-white/50">Cumplimiento: <b className="text-white">{sugerencia.contexto_decision.cumplimiento_dieta}</b></span>
                                        )}
                                    </div>
                                )}
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                    {[['Entrenamiento', sugerencia.propuesta.entreno, true], ['Perientreno', sugerencia.propuesta.perientreno, false], ['Descanso', sugerencia.propuesta.descanso, true]].map(([t, mm, g]) => (
                                        <div key={t} className="bg-[#0A0A0A] rounded-xl p-3 border border-[#222]">
                                            <p className="text-[10px] text-white/40 uppercase tracking-wider mb-1">{t}</p>
                                            <p className="text-sm font-bold"><span className="text-orange-400">{mm?.proteina}P</span> · <span className="text-blue-400">{mm?.hidratos}H</span>{g && <> · <span className="text-yellow-400">{mm?.grasa}G</span></>}</p>
                                        </div>
                                    ))}
                                </div>
                                {sugerencia.cambios?.length > 0 && <p className="text-white/60 text-xs"><span className="text-white/40">Cambios: </span>{sugerencia.cambios.join('  ·  ')}</p>}
                                {sugerencia.razonamiento && <p className="text-white/80 text-sm leading-relaxed">{sugerencia.razonamiento}</p>}
                                {sugerencia.avisos?.length > 0 && (
                                    <ul className="space-y-1">{sugerencia.avisos.map((a, i) => <li key={i} className="text-amber-500/90 text-xs flex gap-1.5"><AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" /><span>{a}</span></li>)}</ul>
                                )}
                                {sugerencia.guardarrail?.length > 0 && (
                                    <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-2">
                                        <p className="text-red-400 text-[11px] font-bold mb-0.5">Revisar (guardarraíl):</p>
                                        <ul className="space-y-0.5">{sugerencia.guardarrail.map((w, i) => <li key={i} className="text-red-400/90 text-xs">· {w}</li>)}</ul>
                                    </div>
                                )}
                                <div className="flex items-center gap-2 pt-1">
                                    <Button size="sm" className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs" onClick={usarSugerencia} data-testid="use-suggestion-btn"><CheckCircle2 className="w-3 h-3 mr-1" />Usar esta propuesta</Button>
                                    <Button size="sm" variant="ghost" className="text-white/50 hover:text-white text-xs" onClick={() => setSugerencia(null)}>Descartar</Button>
                                </div>
                                <p className="text-white/30 text-[10px] leading-relaxed">Es una sugerencia para que la revises. Al usarla se cargan estos valores en el editor de arriba (vigentes mañana); nada se guarda hasta que le des a "Guardar macros".</p>
                            </CardContent>
                        </Card>
                    )}

                    {/* Estructura de dieta (Calma quiereRepartoDeComidas) */}
                    <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                        <p className="text-xs font-bold text-white/40 uppercase tracking-wider mb-3">Estructura de dieta</p>
                        <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0">
                                <p className="text-sm text-white font-medium">{profile?.single_meal_mode ? 'Comida única' : 'Reparto por comidas'}</p>
                                <p className="text-xs text-white/40">{profile?.single_meal_mode ? 'Todo el presupuesto del día en una sola comida, sin reparto.' : 'Reparto estándar en 4 comidas + peri.'}</p>
                            </div>
                            <button
                                onClick={() => handleToggleSingleMeal(!profile?.single_meal_mode)}
                                className={`shrink-0 px-4 py-2 rounded-lg text-xs font-bold transition-all ${profile?.single_meal_mode ? 'bg-[#FF671F] text-white' : 'bg-[#1a1a1a] text-white/60 border border-[#222] hover:text-white'}`}
                            >{profile?.single_meal_mode ? 'Comida única: ON' : 'Activar comida única'}</button>
                        </div>
                    </CardContent></Card>

                    {/* Historial de macros (tabla + filtro por fechas) */}
                    <MacroHistoryTable items={macro_history} onEdit={openEditEntry} onRepeat={openRepeatEntry} onDelete={deleteMacroEntry} onEvaluar={openEvaluar} />

                    {/* Evaluacion de la fase que abrio un ajuste (modelo predictivo, paso 1) */}
                    <Dialog open={!!evalEntry} onOpenChange={(o) => !o && setEvalEntry(null)}>
                        {evalEntry && (
                            <DialogContent className="bg-[#111] border-[#333] max-w-md text-white" data-testid="eval-dialog">
                                <DialogHeader><DialogTitle className="uppercase tracking-wider">Cómo salió la fase</DialogTitle></DialogHeader>
                                <p className="text-white/50 text-xs -mt-2">
                                    Macros del {_fechaCorta(evalEntry.effective_date || (evalEntry.created_at || '').slice(0, 10))}.
                                    Se evalúa a toro pasado, cuando ya sabes qué dio de sí.
                                </p>
                                <div className="space-y-3">
                                    <div>
                                        <Label className="text-white/60 text-xs">Resultado</Label>
                                        <div className="grid grid-cols-2 gap-2 mt-1">
                                            {[['buena', 'Buena'], ['mala', 'Mala']].map(([v, l]) => (
                                                <button key={v} onClick={() => setEvalForm(f => ({ ...f, resultado: v }))}
                                                    className={`py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${evalForm.resultado === v ? (v === 'buena' ? 'bg-emerald-600 text-white' : 'bg-red-600 text-white') : 'bg-[#1A1A1A] text-white/40 hover:text-white'}`}
                                                    data-testid={`eval-resultado-${v}`}>{l}</button>
                                            ))}
                                        </div>
                                    </div>
                                    {evalForm.resultado === 'mala' && (
                                        <div>
                                            <Label className="text-white/60 text-xs">¿De quién fue?</Label>
                                            <div className="grid grid-cols-3 gap-2 mt-1">
                                                {[['ajuste', 'Del ajuste'], ['cliente', 'No cumplió'], ['otro', 'Otro']].map(([v, l]) => (
                                                    <button key={v} onClick={() => setEvalForm(f => ({ ...f, causa: v }))}
                                                        className={`py-2 rounded-lg text-[11px] font-bold uppercase tracking-wider transition-all ${evalForm.causa === v ? 'bg-[#FF671F] text-white' : 'bg-[#1A1A1A] text-white/40 hover:text-white'}`}>{l}</button>
                                                ))}
                                            </div>
                                            <p className="text-[10px] text-white/30 mt-1">"Del ajuste" = te pasaste o te quedaste corto tú. "No cumplió" = el ajuste estaba bien.</p>
                                        </div>
                                    )}
                                    <div>
                                        <Label className="text-white/60 text-xs">Nota (opcional)</Label>
                                        <Textarea value={evalForm.nota} onChange={e => setEvalForm(f => ({ ...f, nota: e.target.value }))}
                                            placeholder="Ej: bajó 2 kg pero se quedó sin fuerza la última semana" className="bg-[#0A0A0A] border-[#333] text-white mt-1" />
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setEvalEntry(null)} className="bg-transparent border-[#333] text-white">Cancelar</Button>
                                    <Button onClick={guardarEvaluacion} disabled={savingEval} className="bg-[#FF671F] text-white" data-testid="save-eval-btn">
                                        {savingEval ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save className="w-4 h-4 mr-1" />Guardar</>}
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        )}
                    </Dialog>

                    {/* Modal del historial: editar una entrada pasada o reaplicarla como macros actuales */}
                    <Dialog open={entryModalOpen} onOpenChange={(o) => { setEntryModalOpen(o); if (!o) setEditingEntryId(null); }}>
                        <DialogContent className="bg-[#111] border-[#333] max-w-lg" data-testid="macros-modal">
                            <DialogHeader><DialogTitle className="text-white uppercase tracking-wider">{editingEntryId ? 'Editar entrada del historial' : 'Repetir estos macros'}</DialogTitle></DialogHeader>
                            <div className="space-y-4">
                                <div>
                                    <p className="text-xs text-white/40 uppercase tracking-wider mb-2">Entrenamiento</p>
                                    <div className="grid grid-cols-3 gap-2">
                                        <div><Label className="text-white/60 text-xs">Proteína</Label><Input type="number" value={entryForm.training.protein} onChange={e => setEntryForm({...entryForm, training: {...entryForm.training, protein: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" data-testid="macro-input-tp" /></div>
                                        <div><Label className="text-white/60 text-xs">Hidratos</Label><Input type="number" value={entryForm.training.carbs} onChange={e => setEntryForm({...entryForm, training: {...entryForm.training, carbs: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                        <div><Label className="text-white/60 text-xs">Grasa</Label><Input type="number" value={entryForm.training.fat} onChange={e => setEntryForm({...entryForm, training: {...entryForm.training, fat: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                    </div>
                                </div>
                                <div>
                                    <p className="text-xs text-white/40 uppercase tracking-wider mb-2">Descanso</p>
                                    <div className="grid grid-cols-3 gap-2">
                                        <div><Label className="text-white/60 text-xs">Proteína</Label><Input type="number" value={entryForm.rest.protein} onChange={e => setEntryForm({...entryForm, rest: {...entryForm.rest, protein: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                        <div><Label className="text-white/60 text-xs">Hidratos</Label><Input type="number" value={entryForm.rest.carbs} onChange={e => setEntryForm({...entryForm, rest: {...entryForm.rest, carbs: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                        <div><Label className="text-white/60 text-xs">Grasa</Label><Input type="number" value={entryForm.rest.fat} onChange={e => setEntryForm({...entryForm, rest: {...entryForm.rest, fat: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                    </div>
                                </div>
                                <div>
                                    <p className="text-xs text-white/40 uppercase tracking-wider mb-2">Perientreno</p>
                                    <div className="grid grid-cols-2 gap-2">
                                        <div><Label className="text-white/60 text-xs">Proteína</Label><Input type="number" value={entryForm.peri.protein} onChange={e => setEntryForm({...entryForm, peri: {...entryForm.peri, protein: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                        <div><Label className="text-white/60 text-xs">Hidratos</Label><Input type="number" value={entryForm.peri.carbs} onChange={e => setEntryForm({...entryForm, peri: {...entryForm.peri, carbs: e.target.value}})} className="bg-[#0A0A0A] border-[#333] text-white" /></div>
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-2">
                                    <div>
                                        <Label className="text-white/60 text-xs">Vigente desde</Label>
                                        <Input type="date" value={entryForm.effective_date} onChange={e => setEntryForm({...entryForm, effective_date: e.target.value})} className="bg-[#0A0A0A] border-[#333] text-white mt-1" data-testid="macro-effective-date" />
                                        <p className="text-[10px] text-white/30 mt-1">Las dietas anteriores conservan los macros previos.</p>
                                    </div>
                                    <div>
                                        <Label className="text-white/60 text-xs">% graso</Label>
                                        <Input type="number" step="0.1" min="3" max="60" value={entryForm.porcentaje_graso} onChange={e => setEntryForm({...entryForm, porcentaje_graso: e.target.value})} placeholder="-" className="bg-[#0A0A0A] border-[#333] text-white mt-1" />
                                    </div>
                                </div>
                                <div>
                                    <Label className="text-white/60 text-xs">Criterio del ajuste (interno)</Label>
                                    <Textarea value={entryForm.criterio} onChange={e => setEntryForm({...entryForm, criterio: e.target.value})} placeholder="Por qué se hizo este ajuste" className="bg-[#0A0A0A] border-[#333] text-white mt-1 min-h-[38px]" />
                                </div>
                                <div>
                                    <Label className="text-white/60 text-xs">Feedback para el cliente {editingEntryId ? '(opcional)' : '(obligatorio)'}</Label>
                                    <Textarea value={entryForm.note} onChange={e => setEntryForm({...entryForm, note: e.target.value})} placeholder="Ej: Bajamos un poco los hidratos por la pérdida de peso, sigue así..." className="bg-[#0A0A0A] border-[#333] text-white mt-1" data-testid="macro-note" />
                                    <p className="text-[10px] text-white/30 mt-1">Le llega al cliente como novedad al guardar (sustituye al audio).</p>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button variant="outline" onClick={() => setEntryModalOpen(false)} className="bg-transparent border-[#333] text-white">Cancelar</Button>
                                <Button onClick={handleSaveEntry} disabled={savingEntry} className="bg-[#FF671F] text-white" data-testid="save-entry-btn">{savingEntry ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save className="w-4 h-4 mr-1" />Guardar</>}</Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </TabsContent>

                {/* ========== TAB 3: MEMBRESÍA ========== */}
                <TabsContent value="membresia" className="space-y-4">
                    {/* Gestión de usuario: rol, plan (cortesía) y baja lógica */}
                    <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2"><Shield className="w-4 h-4" />Gestión de usuario</CardTitle></CardHeader>
                        <CardContent className="space-y-3">
                            {user?.deleted_at && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2">Usuario dado de baja: no puede entrar en la app.</div>}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div><Label className="text-white/60 text-xs">Rol</Label>
                                    <select value={user?.role || 'client'} onChange={e => changeUserRole(e.target.value)} disabled={savingMgmt} className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                        {USER_ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                                    </select>
                                </div>
                                <div><Label className="text-white/60 text-xs">Plan</Label>
                                    <select value={profile?.plan || ''} onChange={e => setUserPlan(e.target.value, !!profile?.comp_plan)} className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                                        <option value="">Sin plan</option>
                                        {['activo', 'legacy', 'especial'].map(estado => {
                                            const grupo = assignablePlans.filter(p => p.estado === estado);
                                            if (!grupo.length) return null;
                                            const gl = { activo: 'Activos', legacy: 'Legacy', especial: 'Especiales' }[estado];
                                            return (
                                                <optgroup key={estado} label={gl}>
                                                    {grupo.map(p => <option key={p.code} value={p.code}>{p.name}</option>)}
                                                </optgroup>
                                            );
                                        })}
                                    </select>
                                </div>
                            </div>
                            <label className="flex items-center gap-2 text-sm text-white/70 cursor-pointer select-none">
                                <input type="checkbox" checked={!!profile?.comp_plan} onChange={e => setUserPlan(profile?.plan || '', e.target.checked)} className="accent-[#FF671F] w-4 h-4" />
                                Plan de cortesía (sin pago)
                            </label>
                            <div className="pt-1">
                                {user?.deleted_at
                                    ? <Button onClick={toggleUserBaja} className="bg-green-600 hover:bg-green-700 text-white text-sm"><RotateCcw className="w-4 h-4 mr-1" /> Reactivar usuario</Button>
                                    : <Button onClick={toggleUserBaja} variant="outline" className="bg-transparent border-red-500/40 text-red-400 hover:bg-red-500/10 text-sm"><Trash2 className="w-4 h-4 mr-1" /> Dar de baja (lógica)</Button>}
                            </div>
                        </CardContent>
                    </Card>
                    <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <InfoItem icon={Shield} label="Plan" value={<PlanBadge plan={profile?.plan} />} />
                            <InfoItem icon={CreditCard} label="Precio" value={`${profile?.price || 0}€/ciclo`} />
                            <InfoItem icon={Calendar} label="Inicio" value={profile?.created_at ? new Date(profile.created_at).toLocaleDateString('es-ES') : '-'} />
                            <InfoItem icon={Calendar} label="Próx. cobro" value={profile?.next_payment ? new Date(profile.next_payment).toLocaleDateString('es-ES') : '-'} />
                        </div>
                    </CardContent></Card>
                    <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Historial de pagos</CardTitle></CardHeader>
                        <CardContent>{payments?.length > 0 ? (
                            <div className="space-y-2">{payments.map(p => (
                                <div key={p.id} className="flex items-center justify-between p-3 bg-[#0A0A0A] rounded-lg border border-[#222]">
                                    <div><p className="text-white text-sm font-medium">{p.amount}€</p><p className="text-white/40 text-xs">{new Date(p.created_at).toLocaleDateString('es-ES')}</p></div>
                                    <Badge className={p.status === 'success' ? 'bg-green-500/20 text-green-500 border-0' : 'bg-red-500/20 text-red-400 border-0'}>{p.status === 'success' ? 'Exitoso' : 'Fallido'}</Badge>
                                </div>
                            ))}</div>
                        ) : <p className="text-white/30 text-sm text-center py-4">Sin pagos registrados</p>}</CardContent>
                    </Card>
                    {calma_raw?.membresia?.length > 0 && <CalmaMembresias membresia={calma_raw.membresia} />}
                </TabsContent>

                {/* ========== TAB 4: REPORTES ========== */}

                {/* ========== TAB 5: CUESTIONARIO ========== */}
                <TabsContent value="cuestionario" className="space-y-4">
                    {(profile?.goal || profile?.weight || profile?.equipment?.length) ? (
                        <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                                <InfoItem icon={Target} label="Objetivo" value={objetivoLabel(profile?.goal)} />
                                <InfoItem icon={Scale} label="Peso inicial" value={profile?.weight ? `${profile.weight} kg` : '-'} />
                                <InfoItem icon={User} label="Sexo" value={sexoLabel(profile?.sex)} />
                                <InfoItem icon={Activity} label="% Graso" value={profile?.body_fat ? `${profile.body_fat}%` : '-'} />
                                <InfoItem icon={Calendar} label="Edad" value={profile?.age || '-'} />
                                <InfoItem icon={Scale} label="Altura" value={profile?.height ? `${profile.height} cm` : '-'} />
                            </div>
                            {Array.isArray(profile?.equipment) && profile.equipment.length > 0 && (
                                <div className="mt-4"><p className="text-xs text-white/40 uppercase tracking-wider mb-2">Equipamiento</p>
                                    <div className="flex flex-wrap gap-1.5">{profile.equipment.map((e, i) => <Badge key={i} className="bg-[#FF671F]/10 text-[#FF671F] border-0 text-xs">{equipamientoLabel(e)}</Badge>)}</div>
                                </div>
                            )}
                            {Array.isArray(profile?.injuries) && profile.injuries.length > 0 && (
                                <div className="mt-4"><p className="text-xs text-white/40 uppercase tracking-wider mb-2">Lesiones</p>
                                    <div className="flex flex-wrap gap-1.5">{profile.injuries.map((l, i) => <Badge key={i} className="bg-red-500/10 text-red-400 border-0 text-xs">{l}</Badge>)}</div>
                                </div>
                            )}
                        </CardContent></Card>
                    ) : (!calma_raw?.formulario_inicial && <EmptyState icon={ClipboardList} message="Cuestionario pendiente." />)}
                    {calma_raw?.formulario_inicial && <CalmaCuestionario fi={calma_raw.formulario_inicial} />}
                </TabsContent>

                {/* ========== TAB 6: ENTRENAMIENTO ========== */}
                <TabsContent value="entrenamiento" className="space-y-4">
                    {/* Equipment & injuries */}
                    <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div><p className="text-xs text-white/40 uppercase tracking-wider mb-2">Equipamiento</p>
                                {Array.isArray(profile?.equipment) && profile.equipment.length > 0 ? <div className="flex flex-wrap gap-1.5">{profile.equipment.map((e, i) => <Badge key={i} className="bg-[#FF671F]/10 text-[#FF671F] border-0 text-xs">{equipamientoLabel(e)}</Badge>)}</div> : <p className="text-white/30 text-sm">No especificado</p>}
                            </div>
                            <div><p className="text-xs text-white/40 uppercase tracking-wider mb-2">Lesiones activas</p>
                                {Array.isArray(profile?.injuries) && profile.injuries.length > 0 ? <div className="flex flex-wrap gap-1.5">{profile.injuries.map((l, i) => <Badge key={i} className="bg-red-500/10 text-red-400 border-0 text-xs">{l}</Badge>)}</div> : <p className="text-white/30 text-sm">Sin lesiones</p>}
                            </div>
                        </div>
                    </CardContent></Card>

                    {/* Current routine */}
                    {activeRoutine ? (
                        <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Rutina actual</CardTitle></CardHeader>
                            <CardContent><div className="space-y-2">{activeRoutine.days?.map((d, i) => (
                                <div key={i} className="flex items-center justify-between p-2.5 bg-[#0A0A0A] rounded-lg border border-[#222]">
                                    <span className="text-white text-sm font-medium capitalize">{d.day}</span>
                                    {d.is_rest ? <Badge className="bg-purple-500/10 text-purple-400 border-0 text-xs">Descanso</Badge> : <span className="text-white/40 text-xs">{d.exercises?.length || 0} ejercicios</span>}
                                </div>
                            ))}</div>
                            {activeRoutine.trainer_notes && <p className="text-white/30 text-xs mt-3 italic">{activeRoutine.trainer_notes}</p>}
                            </CardContent>
                        </Card>
                    ) : <EmptyState icon={Dumbbell} message="Sin rutina asignada." />}

                    {/* Generate routine */}
                    <Card className="bg-[#111] border-[#FF671F]/20"><CardHeader className="pb-2"><CardTitle className="text-sm text-white uppercase tracking-wider flex items-center gap-2"><Zap className="w-4 h-4 text-[#FF671F]" />Generar rutina con IA</CardTitle></CardHeader>
                        <CardContent className="space-y-3">
                            <Textarea value={routineInstructions} onChange={e => setRoutineInstructions(e.target.value)} placeholder="Instrucciones para la IA..." className="bg-[#0A0A0A] border-[#333] text-white" rows={2} data-testid="routine-instructions" />
                            <Button onClick={handleGenerateRoutine} disabled={generatingRoutine} className="bg-[#FF671F] text-white" data-testid="generate-routine-btn">
                                {generatingRoutine ? <><Loader2 className="w-4 h-4 mr-1 animate-spin" />Generando...</> : <><Zap className="w-4 h-4 mr-1" />Generar</>}
                            </Button>
                            {generatedRoutine && (
                                <div className="p-3 bg-[#0A0A0A] rounded-lg border border-[#333] mt-3">
                                    <ScrollArea className="h-48">{generatedRoutine.days?.map((d, i) => <div key={i} className="mb-2"><p className="text-white text-xs font-bold capitalize">{d.day}</p>{d.is_rest ? <p className="text-white/30 text-xs">Descanso</p> : <ul className="text-white/50 text-xs">{d.exercises?.map((ex, j) => <li key={j}>• {ex.name}: {ex.sets}x{ex.reps}</li>)}</ul>}</div>)}</ScrollArea>
                                    <div className="flex gap-2 mt-3"><Button size="sm" onClick={handleSaveRoutine} className="bg-[#FF671F] text-white" data-testid="save-routine-btn"><Save className="w-3 h-3 mr-1" />Guardar</Button><Button size="sm" variant="outline" onClick={() => setGeneratedRoutine(null)} className="bg-transparent border-[#333] text-white">Descartar</Button></div>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ========== TAB: SUPLEMENTOS ========== */}
                <TabsContent value="suplementos" className="space-y-4">
                    <div className="flex items-center justify-between flex-wrap gap-2">
                        <p className="text-xs text-white/40 uppercase tracking-wider">Protocolo de suplementación</p>
                        <div className="flex gap-2">
                            <Button size="sm" variant="outline" onClick={supSuggest} disabled={supSuggesting} className="bg-transparent border-[#333] text-white" data-testid="suggest-supplements-btn">
                                {supSuggesting ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Sparkles className="w-3 h-3 mr-1 text-[#FF671F]" />}Auto-sugerir
                            </Button>
                            <Button size="sm" onClick={supSave} disabled={supSaving} className="bg-[#FF671F] text-white" data-testid="save-supplements-btn">
                                {supSaving ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Save className="w-3 h-3 mr-1" />}Guardar
                            </Button>
                        </div>
                    </div>

                    {[['actual', 'Suplementación actual'], ['siguiente', 'Suplementación siguiente']].map(([bloque, titulo]) => (
                        <Card key={bloque} className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">{titulo}</CardTitle></CardHeader>
                            <CardContent className="space-y-2">
                                {supProtocol[bloque].length === 0 && <p className="text-white/30 text-sm">Sin suplementos.</p>}
                                {supProtocol[bloque].map((it, i) => (
                                    <div key={i} className="flex items-start justify-between gap-2 p-2.5 bg-[#0A0A0A] rounded-lg border border-[#222]">
                                        <div className="min-w-0">
                                            <p className="text-white text-sm font-medium">{it.titulo}</p>
                                            <p className="text-white/40 text-xs">{[it.cuanto, it.cuando].filter(Boolean).join(' · ')}</p>
                                        </div>
                                        <button onClick={() => supRemove(bloque, i)} className="text-white/30 hover:text-red-400 flex-shrink-0"><X className="w-4 h-4" /></button>
                                    </div>
                                ))}
                                {bloque === 'siguiente' && (
                                    <div className="pt-1">
                                        <Label className="text-white/40 text-xs">A partir del día</Label>
                                        <Input type="date" value={supProtocol.siguiente_fecha || ''} onChange={e => setSupProtocol(p => ({ ...p, siguiente_fecha: e.target.value }))} className="bg-[#0A0A0A] border-[#333] text-white mt-1 w-full sm:w-48" />
                                    </div>
                                )}
                                <select onChange={e => { if (e.target.value) { supAdd(bloque, e.target.value); e.target.value = ''; } }} defaultValue=""
                                    className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-3 py-2 mt-1">
                                    <option value="">+ Añadir del catálogo…</option>
                                    {supCatalog.map(c => <option key={c.id} value={c.id}>{c.titulo}{c.sexo !== 'ambos' ? ` (${sexoLabel(c.sexo)})` : ''} - {suplementoCatLabel(c.categoria)}</option>)}
                                </select>
                            </CardContent>
                        </Card>
                    ))}

                    <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Nota personal</CardTitle></CardHeader>
                        <CardContent>
                            <Textarea value={supProtocol.nota || ''} onChange={e => setSupProtocol(p => ({ ...p, nota: e.target.value }))} placeholder="Nota para el cliente…" className="bg-[#0A0A0A] border-[#333] text-white" rows={2} />
                        </CardContent>
                    </Card>

                    <p className="text-white/30 text-xs">El catálogo se gestiona en <button onClick={() => navigate('/admin/supplements-catalog')} className="text-[#FF671F] hover:underline">Catálogo de suplementos</button>.</p>
                    {calma_raw?.suplementacion && <CalmaSuplementos sup={calma_raw.suplementacion} />}
                </TabsContent>

                {/* ========== TAB 7: NUTRICIÓN ========== */}
                <TabsContent value="nutricion" className="space-y-4">
                    {nutrition_stats?.total_diets > 0 ? (<>
                        <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Top 5 alimentos</CardTitle></CardHeader>
                            <CardContent><div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">{nutrition_stats.top_foods?.map((f, i) => (
                                <div key={i} className="flex items-center justify-between p-2.5 bg-[#0A0A0A] rounded-lg">
                                    <span className="text-white text-sm truncate flex-1">{f.nombre}</span>
                                    <Badge className="bg-[#FF671F]/10 text-[#FF671F] border-0 text-xs ml-2">{f.count}x</Badge>
                                </div>
                            ))}</div></CardContent>
                        </Card>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <Card className="bg-[#111] border-[#222] md:col-span-1"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Dietas ({nutrition_stats.total_diets})</CardTitle></CardHeader>
                                <CardContent>
                                    <ScrollArea className="h-[28rem] pr-2">
                                        <div className="space-y-1">{nutrition_stats.diet_dates?.map((d, i) => (
                                            <button key={i} onClick={() => openDiet(d.fecha)}
                                                className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left transition-colors ${selectedDietDate === d.fecha ? 'bg-[#FF671F]/15 border border-[#FF671F]/40' : 'bg-[#0A0A0A] border border-transparent hover:bg-[#1a1a1a]'}`}>
                                                <span className="text-white text-sm">{_fechaDieta(d.fecha)}</span>
                                                <Badge className={d.tipo_dia === 'entrenamiento' ? 'bg-[#FF671F]/10 text-[#FF671F] border-0 text-[10px]' : 'bg-green-500/10 text-green-500 border-0 text-[10px]'}>{d.tipo_dia}</Badge>
                                            </button>
                                        ))}</div>
                                    </ScrollArea>
                                </CardContent>
                            </Card>
                            <Card className="bg-[#111] border-[#222] md:col-span-2"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">{selectedDietDate ? `Dieta del ${_fechaDieta(selectedDietDate, { day: 'numeric', month: 'long', year: 'numeric' })}` : 'Dieta'}</CardTitle></CardHeader>
                                <CardContent>
                                    {dietLoading ? <div className="flex justify-center py-10"><Loader2 className="w-6 h-6 animate-spin text-[#FF671F]" /></div>
                                        : selectedDiet ? <DietDetail diet={selectedDiet} />
                                            : <p className="text-white/30 text-sm text-center py-10">Elige una fecha de la lista para ver la dieta de ese día.</p>}
                                </CardContent>
                            </Card>
                        </div>
                    </>) : <EmptyState icon={Utensils} message="Sin datos de nutrición aún." />}
                </TabsContent>

                {/* ========== TAB MENÚS (buscador biblioteca + recetario) ========== */}
                <TabsContent value="menus" className="space-y-4">
                    <MenuFinder api={api} clientId={clientId} clientUserId={client?.user_id} clientName={client?.name} />
                </TabsContent>

                {/* ========== TAB: SEGUIMIENTO (evolución de peso + check-ins + reportes) ========== */}
                <TabsContent value="seguimiento" className="space-y-4">
                    <WeightEvolution reports={reports} />
                    <ProgressComparator api={api} clientId={clientId} calmaFotos={calma_raw?.fotos_descargadas} reports={reports} macroHistory={macro_history} />
                    <EvolutionTimeline api={api} clientId={clientId} reportes={calma_raw?.formularios_mensuales} calmaFotos={calma_raw?.fotos_descargadas} reports={reports} macroHistory={macro_history} />
                    <CoachCheckins clientId={clientId} />
                    <ReportsFeedbackList initialReports={reports} />
                </TabsContent>
            </Tabs>
        </div>
    );
};

// ========== SUB-COMPONENTS ==========

const InfoItem = ({ icon: Icon, label, value }) => (
    <div className="flex items-start gap-2">
        <Icon className="w-4 h-4 text-[#FF671F] mt-0.5 flex-shrink-0" />
        <div><p className="text-[10px] text-white/40 uppercase tracking-wider">{label}</p><div className="text-white text-sm font-medium">{value}</div></div>
    </div>
);

// Bloque de macros editable (entrenamiento / perientreno / descanso). Cuando el
// coach cambia un valor, debajo de la etiqueta queda el que hay guardado ahora.
const MacroEditGroup = ({ title, icon: Icon, color, fields }) => (
    <div className="bg-[#0A0A0A] rounded-xl p-3 border border-[#222]">
        <div className="flex items-center gap-1.5 mb-3"><Icon className="w-3.5 h-3.5" style={{ color }} /><span className="text-xs font-bold uppercase tracking-wider" style={{ color }}>{title}</span></div>
        <div className="space-y-2">{fields.map(f => {
            const cambiado = String(f.value ?? '') !== String(f.actual ?? '');
            return (
                <div key={f.label} className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                        <span className="text-white/50 text-xs">{f.label}</span>
                        {cambiado && f.actual !== '' && <span className="block text-[10px] text-white/30">ahora {f.actual}g</span>}
                    </div>
                    <div className="relative w-[88px] flex-shrink-0">
                        <Input type="number" min="0" value={f.value} onChange={e => f.onChange(e.target.value)} data-testid={f.testId}
                            className={`h-9 pr-5 text-right font-bold bg-[#111] text-white [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none ${cambiado ? 'border-[#FF671F]/60' : 'border-[#333]'}`} />
                        <span className="absolute right-2 top-1/2 -translate-y-1/2 text-white/30 text-xs pointer-events-none">g</span>
                    </div>
                </div>
            );
        })}</div>
    </div>
);

const _mv = (m, keys) => { for (const k of keys) if (m && m[k] != null) return Math.round(m[k]); return 0; };

// Fecha por la que se ordena y filtra: manda effective_date (desde cuando aplican
// esos macros); si la entrada es antigua y no la trae, se usa el created_at.
const _fechaEntrada = (h) => h.effective_date || (h.created_at || '').slice(0, 10) || '';
const _fechaCorta = (f) => f ? f.split('-').reverse().join('/') : '-';

// Celdas P/H/G de un bloque de macros dentro de la tabla del historial.
const MacroCeldas = ({ m, showG = true }) => (
    <>
        <td className="px-2 py-2 text-right tabular-nums font-bold text-orange-400">{m ? _mv(m, ['protein', 'proteinas']) : '-'}</td>
        <td className="px-2 py-2 text-right tabular-nums font-bold text-blue-400">{m ? _mv(m, ['carbs', 'hidratos']) : '-'}</td>
        {showG && <td className="px-2 py-2 text-right tabular-nums font-bold text-yellow-400">{m ? _mv(m, ['fat', 'grasas']) : '-'}</td>}
    </>
);

const CAUSA_LABEL = { ajuste: 'fallo del ajuste', cliente: 'no cumplió', otro: 'otros motivos' };

const EvaluacionBadge = ({ ev }) => (
    <span className={`text-xs font-semibold ${ev.resultado === 'buena' ? 'text-emerald-400' : 'text-red-400'}`}
        title={[ev.resultado === 'buena' ? 'Fase buena' : 'Fase mala', CAUSA_LABEL[ev.causa], ev.nota].filter(Boolean).join(' · ')}>
        {ev.resultado === 'buena' ? 'Buena' : 'Mala'}
        {ev.causa && <span className="text-white/40 font-normal"> · {CAUSA_LABEL[ev.causa]}</span>}
    </span>
);

// Historial de macros en tabla, con filtro por rango de fechas.
const MacroHistoryTable = ({ items, onEdit, onRepeat, onDelete, onEvaluar }) => {
    const [desde, setDesde] = useState('');
    const [hasta, setHasta] = useState('');
    const todas = useMemo(
        () => [...(items || [])].sort((a, b) => _fechaEntrada(b).localeCompare(_fechaEntrada(a))),
        [items]);
    const filas = useMemo(() => todas.filter(h => {
        const f = _fechaEntrada(h);
        return !((desde && f < desde) || (hasta && f > hasta));
    }), [todas, desde, hasta]);
    const filtrando = !!(desde || hasta);
    const inputFecha = "bg-[#0A0A0A] border border-[#333] text-white text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:border-[#FF671F]";

    return (
        <Card className="bg-[#111] border-[#222] text-white">
            <CardHeader className="pb-2">
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
                    <CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2">
                        <History className="w-4 h-4" />Historial de macros
                    </CardTitle>
                    <div className="flex items-center gap-2">
                        <span className="text-white/30 text-[11px] tabular-nums">{filtrando ? `${filas.length} de ${todas.length}` : `${todas.length} cambios`}</span>
                        <input type="date" value={desde} max={hasta || undefined} onChange={e => setDesde(e.target.value)} title="Desde" className={inputFecha} data-testid="macro-hist-desde" />
                        <span className="text-white/30 text-xs">a</span>
                        <input type="date" value={hasta} min={desde || undefined} onChange={e => setHasta(e.target.value)} title="Hasta" className={inputFecha} data-testid="macro-hist-hasta" />
                        {filtrando && (
                            <button onClick={() => { setDesde(''); setHasta(''); }} title="Quitar filtro"
                                className="p-1 rounded text-white/40 hover:text-white hover:bg-white/10"><X className="w-3.5 h-3.5" /></button>
                        )}
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                {todas.length === 0 ? (
                    <p className="text-white/30 text-sm text-center py-4">Sin cambios registrados</p>
                ) : filas.length === 0 ? (
                    <p className="text-white/30 text-sm text-center py-4">Ningún cambio entre esas fechas</p>
                ) : (
                    <div className="overflow-x-auto -mx-2">
                        <table className="w-full text-sm min-w-[720px]">
                            <thead>
                                <tr className="text-white/40 text-[10px] uppercase tracking-wider border-b border-[#222]">
                                    <th rowSpan={2} className="px-2 py-1.5 text-left font-medium">Vigente desde</th>
                                    <th rowSpan={2} className="px-2 py-1.5 text-right font-medium">Peso<span className="block text-white/25 normal-case">y %graso</span></th>
                                    <th colSpan={3} className="px-2 py-1.5 text-center font-bold border-l border-[#222]" style={{ color: '#FF671F' }}>Entrenamiento</th>
                                    <th colSpan={2} className="px-2 py-1.5 text-center font-bold border-l border-[#222]" style={{ color: '#EAB308' }}>Perientreno</th>
                                    <th colSpan={3} className="px-2 py-1.5 text-center font-bold border-l border-[#222]" style={{ color: '#22C55E' }}>Descanso</th>
                                    <th rowSpan={2} className="px-2 py-1.5 text-left font-medium border-l border-[#222]">Criterio<span className="block text-white/25 normal-case">interno</span></th>
                                    <th rowSpan={2} className="px-2 py-1.5 text-left font-medium">Feedback</th>
                                    <th rowSpan={2} className="px-2 py-1.5 text-left font-medium border-l border-[#222]">Cómo salió</th>
                                    {(onEdit || onRepeat || onDelete) && <th rowSpan={2} className="px-2 py-1.5" />}
                                </tr>
                                <tr className="text-white/30 text-[10px] uppercase border-b border-[#222]">
                                    <th className="px-2 pb-1.5 text-right font-medium border-l border-[#222]">P</th><th className="px-2 pb-1.5 text-right font-medium">H</th><th className="px-2 pb-1.5 text-right font-medium">G</th>
                                    <th className="px-2 pb-1.5 text-right font-medium border-l border-[#222]">P</th><th className="px-2 pb-1.5 text-right font-medium">H</th>
                                    <th className="px-2 pb-1.5 text-right font-medium border-l border-[#222]">P</th><th className="px-2 pb-1.5 text-right font-medium">H</th><th className="px-2 pb-1.5 text-right font-medium">G</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filas.map((h, i) => {
                                    const peso = h.peso ?? h.client_weight;
                                    const peri = h.peri || h.macros_periworkout;
                                    const nota = h.note && h.note !== 'Importado de Calma' ? h.note : '';
                                    return (
                                        <tr key={h.id || i} className="border-b border-[#1a1a1a] last:border-0 hover:bg-white/[0.03]">
                                            <td className="px-2 py-2 whitespace-nowrap font-medium tabular-nums">
                                                {_fechaCorta(_fechaEntrada(h))}
                                                {h.origen === 'ia' && <span className="ml-1.5 text-[9px] uppercase text-[#FF671F]" title="Propuesta de la IA aceptada tal cual">IA</span>}
                                                {h.origen === 'ia_corregida' && <span className="ml-1.5 text-[9px] uppercase text-amber-500" title={`Propuesta de la IA corregida por el coach: ${JSON.stringify(h.correccion_coach || {})}`}>IA·corr</span>}
                                            </td>
                                            <td className="px-2 py-2 text-right whitespace-nowrap tabular-nums">
                                                <span className="text-[#FF671F] font-bold">{peso != null ? `${peso} kg` : '-'}</span>
                                                {h.body_fat != null && <span className="text-white/40 text-xs"> · {h.body_fat}%</span>}
                                            </td>
                                            <MacroCeldas m={h.training} />
                                            <MacroCeldas m={peri} showG={false} />
                                            <MacroCeldas m={h.rest} />
                                            <td className="px-2 py-2 text-white/50 text-xs max-w-[200px]"><span className="block truncate" title={h.criterio || ''}>{h.criterio || '-'}</span></td>
                                            <td className="px-2 py-2 text-white/50 text-xs max-w-[200px]"><span className="block truncate" title={nota}>{nota || '-'}</span></td>
                                            <td className="px-2 py-2 whitespace-nowrap">
                                                {onEvaluar && h.id ? (
                                                    <button onClick={() => onEvaluar(h)} title="Cómo salió la fase que abrió este ajuste"
                                                        className="text-xs rounded px-1.5 py-0.5 transition-colors hover:bg-white/10">
                                                        {h.evaluacion?.resultado ? <EvaluacionBadge ev={h.evaluacion} /> : <span className="text-white/30">Evaluar</span>}
                                                    </button>
                                                ) : (h.evaluacion?.resultado ? <EvaluacionBadge ev={h.evaluacion} /> : <span className="text-white/30 text-xs">-</span>)}
                                            </td>
                                            {(onEdit || onRepeat || onDelete) && (
                                                <td className="px-2 py-2">
                                                    <div className="flex items-center justify-end gap-0.5">
                                                        {onRepeat && <button onClick={() => onRepeat(h)} title="Repetir estos macros (aplicar hoy)" className="p-1 rounded text-white/40 hover:text-[#FF671F] hover:bg-[#FF671F]/10"><RotateCcw className="w-3.5 h-3.5" /></button>}
                                                        {onEdit && <button onClick={() => onEdit(h)} title="Editar esta entrada" className="p-1 rounded text-white/40 hover:text-white hover:bg-white/10"><Pencil className="w-3.5 h-3.5" /></button>}
                                                        {onDelete && <button onClick={() => onDelete(h)} title="Eliminar esta entrada" className="p-1 rounded text-white/40 hover:text-red-400 hover:bg-red-500/10"><Trash2 className="w-3.5 h-3.5" /></button>}
                                                    </div>
                                                </td>
                                            )}
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

const MiniStat = ({ label, value }) => (
    <div className="bg-[#0A0A0A] rounded p-2 border border-[#222]">
        <span className="text-white/40 text-[10px] uppercase">{label}</span>
        <span className="text-white font-bold text-sm ml-1">{value}</span>
    </div>
);

// ========== CALMA (datos importados, solo lectura) ==========
const CalmaBadge = () => (
    <Badge className="bg-amber-500/15 text-amber-400 border-0 text-[10px] uppercase tracking-wide">Importado de Calma</Badge>
);

// Los campos de texto de Calma a veces acaban con un código interno del formulario
// (p. ej. "Descanso OK|A", "...semanales|I"): lo quitamos para mostrarlo limpio.
const _limpiaCodigo = (s) => typeof s === 'string' ? s.replace(/\s*\|[A-Za-z0-9]{1,2}\s*$/, '').trim() : s;

const CalmaField = ({ label, value }) => {
    if (value == null || value === '' || (Array.isArray(value) && !value.length)) return null;
    const text = Array.isArray(value) ? value.join(', ') : _limpiaCodigo(String(value));
    return (
        <div>
            <p className="text-[10px] text-white/40 uppercase tracking-wider mb-0.5">{label}</p>
            <p className="text-white/90 text-sm whitespace-pre-wrap break-words">{text}</p>
        </div>
    );
};

const CalmaCuestionario = ({ fi }) => {
    if (!fi) return null;
    const med = fi.mediciones?.valores?.filter(v => v != null);
    const fnac = fi.fechaNacimiento ? new Date(fi.fechaNacimiento).toLocaleDateString('es-ES') : null;
    return (
        <Card className="bg-[#111] border-[#222]">
            <CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2"><ClipboardList className="w-4 h-4" />Cuestionario inicial <CalmaBadge /></CardTitle></CardHeader>
            <CardContent className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-3">
                    <CalmaField label="Nombre" value={fi.nombre} />
                    <CalmaField label="Fecha nacimiento" value={fnac} />
                    <CalmaField label="Teléfono" value={fi.telefono} />
                    <CalmaField label="Instagram" value={fi.instagram} />
                    <CalmaField label="Dirección" value={fi.direccion} />
                    <CalmaField label="Profesión" value={fi.profesion} />
                    <CalmaField label="Cómo nos conoció" value={fi.fuenteCliente} />
                    <CalmaField label="Estatura" value={fi.estatura ? `${fi.estatura} cm` : null} />
                    <CalmaField label="Peso inicial" value={fi.peso ? `${fi.peso} kg` : null} />
                    <CalmaField label="Peso máximo" value={fi.pesoMaximo ? `${fi.pesoMaximo} kg` : null} />
                    <CalmaField label="Objetivo" value={fi.objetivo} />
                    <CalmaField label="Estilo de vida" value={fi.estiloVida} />
                    <CalmaField label="Experiencia con preparadores" value={fi.preparadores} />
                    <CalmaField label="Estado de forma anterior" value={fi.estadoFormaAnterior} />
                    <CalmaField label="Entrena actualmente" value={fi.entrenamientoActual} />
                    <CalmaField label="Rutina inicial" value={fi.rutinaInicial} />
                    <CalmaField label="Descanso" value={fi.descanso} />
                    <CalmaField label="Interés en suplementación" value={fi.interesEnSuplementacion} />
                </div>
                <div className="space-y-3 border-t border-[#222] pt-3">
                    <CalmaField label="Medidas (cm)" value={med?.length ? med.join(' · ') : (fi.mediciones?.raw || null)} />
                    <CalmaField label="Medicación" value={fi.medicacion} />
                    <CalmaField label="Fármacos actuales" value={fi.farmacosActuales} />
                    <CalmaField label="Maquinaria disponible" value={fi.maquinaria} />
                    <CalmaField label="Lesiones" value={fi.lesiones} />
                    <CalmaField label="Dieta de ejemplo" value={fi.ejemploDieta} />
                    <CalmaField label="Interés en otros servicios" value={fi.informacionSobreServicios} />
                    <CalmaField label="Comentario del cliente" value={fi.comentarioCliente} />
                </div>
            </CardContent>
        </Card>
    );
};

const _resp = (r) => {
    if (!r) return null;
    const extra = [r.nota, r.score != null ? r.score : null].filter(v => v != null && v !== '').join(' · ');
    return [r.texto, extra ? `(${extra})` : ''].filter(Boolean).join(' ');
};

const CalmaReportItem = ({ r, hideHeader }) => {
    const med = r.mediciones?.valores?.filter(v => v != null);
    const fecha = r.fecha ? new Date(r.fecha + 'T12:00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' }) : '';
    const filas = [
        ['Compromiso', r.compromiso], ['Objetivo', r.objetivo], ['Cumplimiento dieta', r.cumplimientoDieta],
        ['Esfuerzo con la dieta', r.esfuerzoParaCumplirDieta], ['Suplementación', r.suplementacion],
        ['Entrenamiento', r.cumplimientoEntrenamiento], ['Cardio', r.cumplimientoCardio], ['Descanso', r.descanso],
    ].filter(([, v]) => v && v.texto);
    return (
        <div className="p-3.5 bg-[#0A0A0A] rounded-xl border border-[#222]">
            {!hideHeader && (
                <div className="flex items-center justify-between mb-2">
                    <span className="text-white text-sm font-semibold">{fecha}</span>
                    {r.peso != null && <span className="text-[#FF671F] font-bold text-base" style={{ fontFamily: 'Barlow Condensed' }}>{r.peso} kg</span>}
                </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                {filas.map(([label, v]) => (
                    <div key={label} className="flex justify-between gap-2 text-xs">
                        <span className="text-white/40 shrink-0">{label}</span>
                        <span className="text-white/80 text-right">{_resp(v)}</span>
                    </div>
                ))}
            </div>
            {med?.length > 0 && <p className="text-white/40 text-xs mt-2">Medidas: {med.join(' · ')}</p>}
            {r.problemasParaEntrenar && <p className="text-white/60 text-xs mt-2"><span className="text-white/40">Problemas para entrenar: </span>{r.problemasParaEntrenar}</p>}
            {r.comentarioCliente && <p className="text-white/60 text-xs mt-1 italic">"{r.comentarioCliente}"</p>}
        </div>
    );
};

// Foto subida desde la app (client_photos) como miniatura; abre la original al hacer clic.
const AppFoto = ({ api, foto }) => {
    const [thumb, setThumb] = useState(null);
    useEffect(() => {
        let url; let alive = true;
        api.get(`/reports/photos/${foto.id}`, { responseType: 'blob' })
            .then(r => { if (!alive) return; url = URL.createObjectURL(r.data); setThumb(url); })
            .catch(() => {});
        return () => { alive = false; if (url) URL.revokeObjectURL(url); };
    }, [api, foto.id]);
    const openFull = async (e) => {
        e.preventDefault();
        try {
            const r = await api.get(`/reports/photos/${foto.id}`, { responseType: 'blob' });
            window.open(URL.createObjectURL(r.data), '_blank', 'noopener');
        } catch { /* noop */ }
    };
    return (
        <a href="#foto" onClick={openFull} className="block group">
            {thumb
                ? <img src={thumb} alt={foto.fecha || ''} className="w-full aspect-[3/4] object-cover rounded-lg border border-[#222] group-hover:border-[#FF671F]/50 bg-[#0A0A0A]" />
                : <div className="w-full aspect-[3/4] rounded-lg border border-[#222] bg-[#0A0A0A] animate-pulse" />}
            <p className="text-[9px] text-white/40 mt-0.5 truncate">{foto.fecha}</p>
        </a>
    );
};

// Línea temporal de evolución: agrupa por mes el peso (+ variación), las fotos de
// ese mes (miniaturas por pose) y el reporte mensual, unificando las dos fuentes
// (Calma + app) en una sola vista cronológica.
const EvolutionTimeline = ({ api, clientId, reportes, calmaFotos, reports, macroHistory }) => {
    const [appFotos, setAppFotos] = useState([]);
    useEffect(() => {
        let alive = true;
        api.get(`/admin/clients/${clientId}/photos`)
            .then(r => { if (alive) setAppFotos(r.data?.photos || []); })
            .catch(() => {});
        return () => { alive = false; };
    }, [api, clientId]);

    // Timeline de pesos (reportes de la app + historial de macros + reportes Calma).
    const pesos = useMemo(() => {
        const arr = [];
        (reports || []).forEach(r => { if (r.weight != null && r.created_at) arr.push({ date: r.created_at, w: r.weight }); });
        (macroHistory || []).forEach(h => {
            const w = h.peso ?? h.client_weight;
            const d = h.effective_date || h.created_at;
            if (w != null && d) arr.push({ date: d, w });
        });
        (reportes || []).forEach(r => { if (r.peso != null && r.fecha) arr.push({ date: r.fecha, w: r.peso }); });
        return arr;
    }, [reports, macroHistory, reportes]);

    // Hitos por mes: reporte + fotos (Calma y app) + peso, más reciente primero.
    const meses = useMemo(() => {
        const map = new Map();
        const get = (k) => { if (!map.has(k)) map.set(k, { key: k, reporte: null, cal: [], app: [] }); return map.get(k); };
        (reportes || []).forEach(r => { if (r.fecha) get(_mesKey(r.fecha)).reporte = r; });
        (calmaFotos || []).forEach(f => { if (f.fecha) get(_mesKey(f.fecha)).cal.push(f); });
        (appFotos || []).forEach(p => {
            const d = (p.taken_at || p.uploaded_at || '').slice(0, 10);
            if (d) get(_mesKey(d)).app.push({ ...p, fecha: d });
        });
        const arr = [...map.values()].filter(m => m.reporte || m.cal.length || m.app.length);
        arr.sort((a, b) => b.key.localeCompare(a.key));
        arr.forEach(m => {
            m.peso = m.reporte?.peso != null ? m.reporte.peso : _pesoCercano(pesos, m.key + '-15');
            m.cal.sort((a, b) => _POSE_ORDER.indexOf(_poseDeKind(a.kind)) - _POSE_ORDER.indexOf(_poseDeKind(b.kind)));
        });
        // Variación de peso respecto al hito anterior (el siguiente en el array = más antiguo).
        arr.forEach((m, i) => {
            const prev = arr[i + 1]?.peso;
            m.delta = (m.peso != null && prev != null) ? Math.round((m.peso - prev) * 10) / 10 : null;
        });
        return arr;
    }, [reportes, calmaFotos, appFotos, pesos]);

    if (!meses.length) return null;

    return (
        <Card className="bg-[#111] border-[#222]">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2">
                    <TrendingUp className="w-4 h-4" />Evolución del cliente <span className="text-white/30">({meses.length})</span>
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-5">
                    {meses.map(m => (
                        <div key={m.key} className="relative pl-4 border-l-2 border-[#222]">
                            <div className="absolute -left-[7px] top-1.5 w-3 h-3 rounded-full bg-[#FF671F]" />
                            <div className="flex items-center gap-3 mb-2">
                                <span className="text-white text-sm font-semibold capitalize">{_mesLabel(m.key)}</span>
                                {m.peso != null && <span className="text-[#FF671F] font-bold text-base" style={{ fontFamily: 'Barlow Condensed' }}>{m.peso} kg</span>}
                                {m.delta != null && m.delta !== 0 && (
                                    <span className={`text-xs font-bold ${m.delta < 0 ? 'text-green-400' : 'text-[#FF671F]'}`}>
                                        {m.delta < 0 ? '▼' : '▲'} {Math.abs(m.delta)} kg
                                    </span>
                                )}
                            </div>
                            {(m.cal.length > 0 || m.app.length > 0) && (
                                <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2 mb-2">
                                    {m.cal.map((f, i) => <CalmaFoto key={'c' + i} api={api} clientId={clientId} foto={f} />)}
                                    {m.app.map((f, i) => <AppFoto key={'a' + i} api={api} foto={f} />)}
                                </div>
                            )}
                            {m.reporte && <CalmaReportItem r={m.reporte} hideHeader />}
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
};

// ========== COMPARADOR DE FOTOS (antes / después) ==========
//
// Unifica las dos fuentes de fotos del cliente: las importadas de Calma
// (calma_raw.fotos_descargadas, con la pose en el nombre) y las que sube desde
// la app (client_photos). Agrupa por pose, arranca en la primera vs la última y
// deja al coach cambiar cada lado.

// El "kind" de Calma es texto libre sacado del nombre del archivo; lo mapeamos a
// una pose por palabras clave. Lo que no encaje va a "Otras".
const _poseDeKind = (kind) => {
    const k = (kind || '').toLowerCase();
    if (/frent|frontal|delante|front/.test(k)) return 'Frontal';
    if (/espald|atr[aá]s|trasera|back|dorsal/.test(k)) return 'Espalda';
    if (/lateral|perfil|lado|side/.test(k)) return 'Lateral';
    return 'Otras';
};
const _POSE_ORDER = ['Frontal', 'Lateral', 'Espalda', 'Otras', 'Sin clasificar'];

const _mesKey = (fecha) => (fecha || '').slice(0, 7);  // YYYY-MM
const _mesLabel = (key) => {
    const [y, m] = key.split('-');
    const dt = new Date(+y, +m - 1, 1);
    return isNaN(dt) ? key : dt.toLocaleDateString('es-ES', { month: 'long', year: 'numeric' });
};

const _fmtFotoFecha = (d) => {
    if (!d) return '?';
    const dt = new Date(d.length <= 10 ? d + 'T12:00:00' : d);
    return isNaN(dt) ? d : dt.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' });
};

// Peso más cercano a una fecha (dentro de ~21 días), best-effort para anotar la foto.
const _pesoCercano = (pesos, fecha) => {
    if (!fecha || !pesos?.length) return null;
    const target = new Date(fecha.length <= 10 ? fecha + 'T12:00:00' : fecha).getTime();
    let best = null, bestDiff = Infinity;
    for (const p of pesos) {
        const diff = Math.abs(new Date(p.date.length <= 10 ? p.date + 'T12:00:00' : p.date).getTime() - target);
        if (diff < bestDiff) { bestDiff = diff; best = p.w; }
    }
    return bestDiff <= 21 * 864e5 ? best : null;
};

// Carga el blob de una foto (Calma o subida por la app) y la muestra a tamaño grande.
const ComparePhoto = ({ api, clientId, foto }) => {
    const [url, setUrl] = useState(null);
    const [err, setErr] = useState(false);
    useEffect(() => {
        let obj; let alive = true;
        setUrl(null); setErr(false);
        const req = foto.source === 'calma'
            ? api.get(`/admin/clients/${clientId}/calma-foto`, { params: { file: foto.file }, responseType: 'blob' })
            : api.get(`/reports/photos/${foto.id}`, { responseType: 'blob' });
        req.then(r => { if (!alive) return; obj = URL.createObjectURL(r.data); setUrl(obj); })
            .catch(() => { if (alive) setErr(true); });
        return () => { alive = false; if (obj) URL.revokeObjectURL(obj); };
    }, [api, clientId, foto.key, foto.source, foto.file, foto.id]);
    if (err) return <div className="w-full aspect-[3/4] rounded-lg border border-[#222] bg-[#0A0A0A] flex items-center justify-center text-white/30 text-xs">No disponible</div>;
    if (!url) return <div className="w-full aspect-[3/4] rounded-lg border border-[#222] bg-[#0A0A0A] animate-pulse" />;
    return <img src={url} alt={foto.date} className="w-full aspect-[3/4] object-cover rounded-lg border border-[#222] bg-[#0A0A0A]" />;
};

const DateSelect = ({ fotos, value, onChange, pesos }) => (
    <select value={value || ''} onChange={e => onChange(e.target.value)}
        className="w-full bg-[#0A0A0A] border border-[#222] rounded-lg px-2 py-1.5 text-xs text-white/80 focus:border-[#FF671F]/50 outline-none">
        {fotos.map(f => {
            const peso = _pesoCercano(pesos, f.date);
            return <option key={f.key} value={f.key}>{_fmtFotoFecha(f.date)}{peso != null ? ` · ${peso} kg` : ''}</option>;
        })}
    </select>
);

const ProgressComparator = ({ api, clientId, calmaFotos, reports, macroHistory }) => {
    const [appFotos, setAppFotos] = useState([]);
    const [pose, setPose] = useState(null);
    const [leftKey, setLeftKey] = useState(null);
    const [rightKey, setRightKey] = useState(null);

    // Fotos subidas desde la app (client_photos). Las de Calma llegan por prop.
    useEffect(() => {
        let alive = true;
        api.get(`/admin/clients/${clientId}/photos`)
            .then(r => { if (alive) setAppFotos(r.data?.photos || []); })
            .catch(() => {});
        return () => { alive = false; };
    }, [api, clientId]);

    // Timeline de pesos (reportes de la app + historial de macros) para anotar cada foto.
    const pesos = useMemo(() => {
        const arr = [];
        (reports || []).forEach(r => { if (r.weight != null && r.created_at) arr.push({ date: r.created_at, w: r.weight }); });
        (macroHistory || []).forEach(h => {
            const w = h.peso ?? h.client_weight;
            const d = h.effective_date || h.created_at;
            if (w != null && d) arr.push({ date: d, w });
        });
        return arr;
    }, [reports, macroHistory]);

    // Lista unificada de fotos (Calma + app), descartando las que no tienen fecha.
    const todas = useMemo(() => {
        const cal = (calmaFotos || []).map(f => ({
            key: `calma:${f.file}`, source: 'calma', file: f.file,
            date: f.fecha || '', pose: _poseDeKind(f.kind),
        }));
        const app = (appFotos || []).map(p => ({
            key: `app:${p.id}`, source: 'app', id: p.id,
            date: (p.taken_at || p.uploaded_at || '').slice(0, 10), pose: 'Sin clasificar',
        }));
        return [...cal, ...app].filter(f => f.date);
    }, [calmaFotos, appFotos]);

    // Poses con al menos una foto, en el orden canónico.
    const poses = useMemo(() => {
        const set = new Set(todas.map(f => f.pose));
        return _POSE_ORDER.filter(p => set.has(p));
    }, [todas]);

    useEffect(() => {
        if (poses.length && (!pose || !poses.includes(pose))) setPose(poses[0]);
    }, [poses, pose]);

    // Fotos de la pose actual, ordenadas por fecha ascendente.
    const fotosPose = useMemo(
        () => todas.filter(f => f.pose === pose).sort((a, b) => a.date.localeCompare(b.date)),
        [todas, pose]
    );

    // Al cambiar de pose: izquierda = primera, derecha = última.
    useEffect(() => {
        if (!fotosPose.length) { setLeftKey(null); setRightKey(null); return; }
        setLeftKey(fotosPose[0].key);
        setRightKey(fotosPose[fotosPose.length - 1].key);
    }, [pose, fotosPose.length]);  // eslint-disable-line react-hooks/exhaustive-deps

    if (!todas.length) return null;

    const left = fotosPose.find(f => f.key === leftKey) || fotosPose[0];
    const right = fotosPose.find(f => f.key === rightKey) || fotosPose[fotosPose.length - 1];
    const pLeft = left && _pesoCercano(pesos, left.date);
    const pRight = right && _pesoCercano(pesos, right.date);
    const dPeso = (pLeft != null && pRight != null) ? Math.round((pRight - pLeft) * 10) / 10 : null;

    return (
        <Card className="bg-[#111] border-[#222]">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2">
                    <TrendingUp className="w-4 h-4" />Comparador antes / después
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
                {poses.length > 1 && (
                    <div className="flex flex-wrap gap-1.5">
                        {poses.map(p => (
                            <button key={p} onClick={() => setPose(p)}
                                className={`px-3 py-1 rounded-full text-xs font-medium transition ${p === pose ? 'bg-[#FF671F] text-white' : 'bg-[#0A0A0A] text-white/50 border border-[#222] hover:text-white/80'}`}>
                                {p}
                            </button>
                        ))}
                    </div>
                )}
                {fotosPose.length === 0 ? (
                    <p className="text-white/30 text-sm text-center py-4">Sin fotos en esta pose</p>
                ) : (
                    <>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1.5">
                                {left && <ComparePhoto api={api} clientId={clientId} foto={left} />}
                                <DateSelect fotos={fotosPose} value={leftKey} onChange={setLeftKey} pesos={pesos} />
                            </div>
                            <div className="space-y-1.5">
                                {right && <ComparePhoto api={api} clientId={clientId} foto={right} />}
                                <DateSelect fotos={fotosPose} value={rightKey} onChange={setRightKey} pesos={pesos} />
                            </div>
                        </div>
                        {dPeso != null && (
                            <div className="text-center text-sm">
                                <span className="text-white/40">Diferencia de peso: </span>
                                <span className={`font-bold ${dPeso < 0 ? 'text-green-400' : dPeso > 0 ? 'text-[#FF671F]' : 'text-white'}`}>
                                    {dPeso > 0 ? '+' : ''}{dPeso} kg
                                </span>
                            </div>
                        )}
                    </>
                )}
            </CardContent>
        </Card>
    );
};

// Cada foto se carga por fetch autenticado (blob) para no llevar el token en la URL.
const CalmaFoto = ({ api, clientId, foto }) => {
    const [thumb, setThumb] = useState(null);
    useEffect(() => {
        let url; let alive = true;
        api.get(`/admin/clients/${clientId}/calma-foto`, { params: { file: foto.file, w: 300 }, responseType: 'blob' })
            .then(r => { if (!alive) return; url = URL.createObjectURL(r.data); setThumb(url); })
            .catch(() => {});
        return () => { alive = false; if (url) URL.revokeObjectURL(url); };
    }, [api, clientId, foto.file]);
    const openFull = async (e) => {
        e.preventDefault();
        try {
            const r = await api.get(`/admin/clients/${clientId}/calma-foto`, { params: { file: foto.file }, responseType: 'blob' });
            window.open(URL.createObjectURL(r.data), '_blank', 'noopener');
        } catch { /* noop */ }
    };
    return (
        <a href="#foto" onClick={openFull} className="block group">
            {thumb
                ? <img src={thumb} alt={`${foto.kind || ''} ${foto.fecha || ''}`}
                    className="w-full aspect-[3/4] object-cover rounded-lg border border-[#222] group-hover:border-[#FF671F]/50 bg-[#0A0A0A]" />
                : <div className="w-full aspect-[3/4] rounded-lg border border-[#222] bg-[#0A0A0A] animate-pulse" />}
            <p className="text-[9px] text-white/40 mt-0.5 truncate">{foto.fecha} {foto.kind}</p>
        </a>
    );
};

const CalmaMembresias = ({ membresia }) => {
    if (!membresia?.length) return null;
    const fmt = (d) => d ? new Date(d).toLocaleDateString('es-ES') : '?';
    const ordenadas = [...membresia].sort((a, b) => (b.inicio || '').localeCompare(a.inicio || ''));
    return (
        <Card className="bg-[#111] border-[#222]">
            <CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2">Historial de membresías <CalmaBadge /></CardTitle></CardHeader>
            <CardContent><div className="space-y-2">{ordenadas.map((m, i) => (
                <div key={i} className="flex items-center justify-between p-3 bg-[#0A0A0A] rounded-lg border border-[#222]">
                    <span className="text-white text-sm font-medium">{m.nombre || 'Plan'}</span>
                    <span className="text-white/40 text-xs">{fmt(m.inicio)} a {fmt(m.fin)}</span>
                </div>
            ))}</div></CardContent>
        </Card>
    );
};

const CalmaSuplementos = ({ sup }) => {
    if (!sup || (!sup.protocolos?.length && !sup.observaciones)) return null;
    return (
        <Card className="bg-[#111] border-[#222]">
            <CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2">Suplementación <CalmaBadge /></CardTitle></CardHeader>
            <CardContent className="space-y-3">
                {sup.protocolos?.length > 0 && (
                    <div className="space-y-1">
                        {sup.protocolos.map((p, i) => (
                            <div key={i} className="flex items-center justify-between p-2.5 bg-[#0A0A0A] rounded-lg border border-[#222]">
                                <span className="text-white/50 text-xs">{p.fecha}</span>
                                <span className="text-white/70 text-xs">códigos: {p.raw || (p.codigos || []).join('|')}</span>
                            </div>
                        ))}
                    </div>
                )}
                {sup.observaciones && (
                    <div>
                        <p className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Observaciones del coach</p>
                        <p className="text-white/80 text-sm whitespace-pre-wrap">{sup.observaciones}</p>
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

const WeightEvolution = ({ reports }) => {
    const data = (reports || [])
        .filter(r => r.weight != null)
        .map(r => ({ ts: new Date(r.created_at).getTime(), date: new Date(r.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: '2-digit' }), peso: r.weight }))
        .sort((a, b) => a.ts - b.ts);
    if (!data.length) return null;
    const first = data[0].peso, last = data[data.length - 1].peso;
    const diff = Math.round((last - first) * 10) / 10;
    return (
        <Card className="bg-[#111] border-[#222]">
            <CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2"><Scale className="w-4 h-4" />Evolución del peso ({data.length})</CardTitle></CardHeader>
            <CardContent>
                <div className="flex items-center gap-5 mb-3 text-sm">
                    <div><span className="text-white/40 text-xs mr-1">Inicio</span><span className="text-white font-bold">{first} kg</span></div>
                    <div><span className="text-white/40 text-xs mr-1">Actual</span><span className="text-white font-bold">{last} kg</span></div>
                    <div><span className="text-white/40 text-xs mr-1">Cambio</span><span className="text-white font-bold">{diff > 0 ? '+' : ''}{diff} kg</span></div>
                </div>
                <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data} margin={{ top: 5, right: 8, bottom: 0, left: -8 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#222" />
                            <XAxis dataKey="date" tick={{ fill: '#ffffff66', fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={28} />
                            <YAxis domain={['auto', 'auto']} tick={{ fill: '#ffffff66', fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
                            <Tooltip contentStyle={{ backgroundColor: '#1A1A1A', border: '1px solid #333', borderRadius: 12, color: '#fff' }} labelStyle={{ color: '#fff' }} formatter={(v) => [`${v} kg`, 'Peso']} />
                            <Line type="monotone" dataKey="peso" stroke="#FF671F" strokeWidth={2} dot={{ fill: '#FF671F', r: 2 }} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </CardContent>
        </Card>
    );
};

const MEAL_ORDER = { C1: 1, C2: 2, C3: 3, C4: 4, C5: 5, C6: 6, Intra: 7, Post: 8 };
const MEAL_LABEL = { Intra: 'Intra-entreno', Post: 'Post-entreno', C1: 'Comida 1', C2: 'Comida 2', C3: 'Comida 3', C4: 'Comida 4', C5: 'Comida 5', C6: 'Comida 6' };

// Reportes del cliente con feedback editable por el coach (cierra el circuito de ReportsPage)
const ReportsFeedbackList = ({ initialReports }) => {
    const { api } = useAuth();
    const [reports, setReports] = useState(initialReports || []);
    const [drafts, setDrafts] = useState({});
    const [savingId, setSavingId] = useState(null);
    const [showAll, setShowAll] = useState(false);
    const [detalleId, setDetalleId] = useState(null);   // reporte abierto en el modal

    const saveFeedback = async (reportId) => {
        const text = (drafts[reportId] ?? '').trim();
        setSavingId(reportId);
        try {
            await api.put(`/reports/${reportId}/feedback`, { feedback: text });
            setReports(prev => prev.map(r => r.id === reportId ? { ...r, trainer_feedback: text || null } : r));
            setDrafts(prev => { const d = { ...prev }; delete d[reportId]; return d; });
            toast.success('Feedback guardado');
        } catch {
            toast.error('Error guardando el feedback');
        } finally { setSavingId(null); }
    };

    // Sin reportes no se pinta nada: en una ficha nueva solo seria ruido.
    if (!reports.length) return null;
    // Listado de fechas y el detalle en un modal: con decenas de reportes, verlos todos
    // desplegados a la vez no hay quien lo lea.
    const visible = showAll ? reports : reports.slice(0, 8);
    const abierto = reports.find(r => r.id === detalleId) || null;
    const draftAbierto = abierto ? (drafts[abierto.id] ?? (abierto.trainer_feedback || '')) : '';
    const dirtyAbierto = abierto ? draftAbierto !== (abierto.trainer_feedback || '') : false;

    return (
        <Card className="bg-[#111] border-[#222] text-white"><CardContent className="p-5">
            <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-bold text-white/40 uppercase tracking-wider">Reportes del cliente</p>
                <span className="text-white/25 text-xs">{reports.length} en total</span>
            </div>
            <div className="space-y-1">
                {visible.map(r => (
                    <button key={r.id} onClick={() => setDetalleId(r.id)} data-testid={`report-${r.id}`}
                        className="w-full flex items-center gap-3 px-3 py-2 rounded-lg bg-[#0A0A0A] border border-[#222] hover:border-[#FF671F]/40 transition-colors text-left">
                        <span className="text-white text-sm font-medium tabular-nums whitespace-nowrap">
                            {new Date(r.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })}
                        </span>
                        {r.weight != null && <span className="text-[#FF671F] font-bold text-sm tabular-nums">{r.weight} kg</span>}
                        <span className="ml-auto flex items-center gap-2 flex-shrink-0">
                            {r.trainer_feedback
                                ? <span className="text-emerald-400 text-[10px] uppercase tracking-wider">con feedback</span>
                                : <span className="text-white/25 text-[10px] uppercase tracking-wider">sin feedback</span>}
                            <ChevronRight className="w-4 h-4 text-white/30" />
                        </span>
                    </button>
                ))}
            </div>
            {reports.length > 8 && (
                <button onClick={() => setShowAll(v => !v)} className="text-[#FF671F] text-xs mt-3 hover:underline">
                    {showAll ? 'Ver menos' : `Ver los ${reports.length}`}
                </button>
            )}

            <Dialog open={!!abierto} onOpenChange={(o) => !o && setDetalleId(null)}>
                {abierto && (
                    <DialogContent className="bg-[#111] border-[#333] max-w-lg text-white" data-testid="report-detail">
                        <DialogHeader>
                            <DialogTitle className="uppercase tracking-wider">
                                Reporte del {new Date(abierto.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' })}
                            </DialogTitle>
                        </DialogHeader>
                        <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm bg-[#0A0A0A] rounded-lg p-3 border border-[#222]">
                            {abierto.weight != null && <span className="text-white/50">Peso <b className="text-white">{abierto.weight} kg</b></span>}
                            {abierto.training_compliance != null && <span className="text-white/50">Entreno <b className="text-white">{abierto.training_compliance}%</b></span>}
                            {abierto.nutrition_compliance != null && <span className="text-white/50">Nutrición <b className="text-white">{abierto.nutrition_compliance}%</b></span>}
                        </div>
                        {abierto.notes && <p className="text-white/70 text-sm italic">"{abierto.notes}"</p>}
                        <div>
                            <Label className="text-white/60 text-xs">Feedback para el cliente</Label>
                            <Textarea value={draftAbierto} onChange={e => setDrafts(prev => ({ ...prev, [abierto.id]: e.target.value }))}
                                placeholder="Escribe feedback para el cliente..." rows={3}
                                className="bg-[#0A0A0A] border-[#333] text-white mt-1" />
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setDetalleId(null)} className="bg-transparent border-[#333] text-white">Cerrar</Button>
                            <Button onClick={() => saveFeedback(abierto.id)} disabled={!dirtyAbierto || savingId === abierto.id}
                                className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white disabled:opacity-40">
                                {savingId === abierto.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save className="w-4 h-4 mr-1" />Guardar feedback</>}
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                )}
            </Dialog>
        </CardContent></Card>
    );
};

const DietDetail = ({ diet }) => {
    const comidas = diet?.comidas || {};
    const keys = Object.keys(comidas).sort((a, b) => (MEAL_ORDER[a] || 99) - (MEAL_ORDER[b] || 99));
    const dayTotal = { P: 0, H: 0, G: 0 };
    const meals = keys.map((k) => {
        const foods = comidas[k]?.alimentos || [];
        const mt = { P: 0, H: 0, G: 0 };
        foods.forEach((a) => {
            const e = a.macros_efectivos || {};
            mt.P += e.P || 0; mt.H += e.H || 0; mt.G += e.G || 0;
            dayTotal.P += e.P || 0; dayTotal.H += e.H || 0; dayTotal.G += e.G || 0;
        });
        return { k, foods, mt };
    });
    return (
        <div className="space-y-2.5">
            {meals.map(({ k, foods, mt }) => (
                <div key={k} className="bg-[#0A0A0A] rounded-lg p-3 border border-[#222]">
                    <div className="flex items-center justify-between mb-1.5">
                        <span className="text-white text-sm font-semibold">{MEAL_LABEL[k] || k}</span>
                        <span className="text-[11px]"><span className="text-orange-400">P{Math.round(mt.P)}</span> <span className="text-blue-400">H{Math.round(mt.H)}</span> <span className="text-yellow-400">G{Math.round(mt.G)}</span></span>
                    </div>
                    <div className="space-y-1">
                        {foods.length ? foods.map((a, i) => {
                            const e = a.macros_efectivos || {};
                            return (
                                <div key={i} className="flex items-center gap-2 text-xs">
                                    <span className="text-white/80 flex-1 min-w-0 truncate">{a.nombre}</span>
                                    <span className="text-white/40 whitespace-nowrap w-12 text-right">{Math.round(a.cantidad_g)} g</span>
                                    <span className="whitespace-nowrap tabular-nums w-24 text-right">
                                        <span className="text-orange-400">P{Math.round(e.P || 0)}</span> <span className="text-blue-400">H{Math.round(e.H || 0)}</span> <span className="text-yellow-400">G{Math.round(e.G || 0)}</span>
                                    </span>
                                </div>
                            );
                        }) : <span className="text-white/30 text-xs">Vacía</span>}
                    </div>
                </div>
            ))}
            <div className="flex items-center justify-between pt-2 border-t border-[#222]">
                <span className="text-white/60 text-sm font-semibold">Total del día</span>
                <span className="text-sm font-bold"><span className="text-orange-400">P{Math.round(dayTotal.P)}</span> · <span className="text-blue-400">H{Math.round(dayTotal.H)}</span> · <span className="text-yellow-400">G{Math.round(dayTotal.G)}</span></span>
            </div>
        </div>
    );
};

const EmptyState = ({ icon: Icon, message, action }) => (
    <Card className="bg-[#111] border-[#222]"><CardContent className="p-8 text-center">
        <Icon className="w-10 h-10 text-white/10 mx-auto mb-3" />
        <p className="text-white/30 text-sm">{message}</p>
        {action}
    </CardContent></Card>
);

export default ClientDetailPage;
