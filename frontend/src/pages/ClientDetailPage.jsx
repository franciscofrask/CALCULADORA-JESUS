import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import PlantillasFeedback from '../components/PlantillasFeedback';
import GraficaDePeso from '../components/GraficaDePeso';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { useConfirm } from '../components/ui/confirm';
import { PlanBadge } from './ClientDashboard';
import { sexoLabel, objetivoLabel, equipamientoLabel, suplementoCatLabel, EQUIPAMIENTO_OPCIONES, plural, estadoClienteLabel, estadoDeAcceso } from '../lib/labels';
import { construirComparativa, TITULO_ETIQUETA } from '../lib/comparativaFotos';
import { BIBLIOTECA_DE_CLIENTES } from '../lib/menuFuentes';
import { MEDIDAS, valorAnterior, diferencia } from '../lib/medidas';
import CoachCheckins from '../components/CoachCheckins';
import EvolucionMedidas from '../components/EvolucionMedidas';
import InformeMensual from '../components/reports/InformeMensual';
import { FoodFilterBar } from '../components/nutrition/SearchFoodModal';
import {
    ArrowLeft, User, Mail, Phone, Calendar, CreditCard, Dumbbell, Apple,
    FileText, Scale, Target, Zap, Save, Loader2, History, Shield,
    ClipboardList, TrendingUp, Utensils, Activity, ChevronDown, ChevronUp, ChevronRight, SlidersHorizontal, UserCog,
    AlertCircle, CheckCircle2, Pill, Plus, X, Sparkles, Pencil, Trash2, RotateCcw,
    Headphones, CalendarClock, Camera
} from 'lucide-react';
import { etiquetaAcompanamiento, etiquetaFrecuencia } from '../lib/planAccess';
import { revisarPeso } from '../lib/pesoValido';
import { mensajeDeError } from '../lib/mensajeDeError';

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

// El reporte del que sale el peso del ajuste: el ultimo que traiga peso (punto 25). Aqui
// arriba y no dentro del componente porque hace falta en dos sitios: al cargar la ficha,
// para rellenar el editor, y al pintar, para decir de que reporte viene.
// El último punto de una serie {fecha, valor} (punto 30): el peso y el % graso actuales
// SON el último de su serie, y se enseñan con su fecha. Un número sin fecha no se puede
// contrastar con nada, y era la mitad del lío de los dos pesos.
//
// Y HASTA HOY, como todo lo demás (punto 22). El corte de `sin_futuro.py` está puesto en el
// servidor para el historial, la gráfica y los cálculos, pero esta función lo hacía por su
// cuenta aquí y sin filtro: en la ficha de `hola@jesusgallegopt.com`, que arrastra 29 puntos
// con fecha de 2027 y 2028 de la importación, el Resumen enseñaba «118 kg · del 21/02/2028»
// cuando el último pesaje de verdad son 77,1 kg de hoy. Es el punto 9 -- los dos pesos
// distintos -- reapareciendo en otra pantalla.
const _ultimoDeLaSerie = (serie) => {
    const hoy = hoyISO();
    const puntos = (serie || []).filter(x => x?.valor != null && x?.fecha && String(x.fecha).slice(0, 10) <= hoy);
    if (!puntos.length) return null;
    return puntos.reduce((a, b) => String(b.fecha) > String(a.fecha) ? b : a);
};

// "hace 3 días", "ayer", "hoy". Con la fecha exacta al lado cuando ya no es reciente.
const _haceCuanto = (iso) => {
    if (!iso) return '';
    const d = new Date(String(iso).slice(0, 10) + 'T00:00:00');
    if (isNaN(d)) return '';
    const dias = Math.floor((new Date().setHours(0, 0, 0, 0) - d.getTime()) / 86400000);
    if (dias <= 0) return 'hoy';
    if (dias === 1) return 'ayer';
    if (dias < 30) return `hace ${dias} días`;
    return `del ${_fechaCorta(String(iso).slice(0, 10))}`;
};

const _reporteDelPeso = (reports) => {
    const conPeso = (reports || []).filter(r => r?.weight != null && r?.created_at);
    if (!conPeso.length) return null;
    return conPeso.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))[0];
};

// ===== Buscador de menús para el coach (biblioteca real de clientes + recetario) =====
const MenuFinder = ({ api, clientId, clientUserId, clientName }) => {
    const [macros, setMacros] = useState({ P: '', H: '', G: '' });
    const [momento, setMomento] = useState('comida');
    const [fuente, setFuente] = useState(BIBLIOTECA_DE_CLIENTES ? 'ambas' : 'recetario');
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
                    {/* Con la biblioteca de clientes apagada (06-08-2026) solo queda una
                        fuente: un desplegable de una opción es ruido. */}
                    {BIBLIOTECA_DE_CLIENTES && (
                        <div>
                            <Label className="text-white/50 text-xs">Fuente</Label>
                            <select value={fuente} onChange={e => setFuente(e.target.value)}
                                className="w-full mt-1 h-10 rounded-md bg-[#1A1A1A] border border-[#333] text-white text-sm px-3" data-testid="menufinder-fuente">
                                <option value="ambas">Ambas fuentes</option>
                                <option value="clientes">Solo menús reales (clientes)</option>
                                <option value="recetario">Solo recetario</option>
                            </select>
                        </div>
                    )}
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

/**
 * LAS RUTINAS QUE EL EQUIPO YA TIENE ESCRITAS, para ponérsela a este cliente.
 *
 * Se escriben en el panel de Rutinas y aquí solo se eligen. Al asignarla se COPIA: si luego
 * se le retoca un ejercicio a este cliente, no se le cambia a los demás que la tienen.
 *
 * Si la biblioteca está vacía no se pinta nada: una tarjeta que solo dice «no hay nada» es
 * ruido en una pantalla que ya tiene diez.
 */
const RutinasGuardadas = ({ api, clientId, onAsignada }) => {
    const [rutinas, setRutinas] = useState([]);
    const [poniendo, setPoniendo] = useState(null);

    useEffect(() => {
        api.get('/admin/routines/biblioteca')
            .then(r => setRutinas(r.data?.rutinas || []))
            .catch(() => { /* sin biblioteca, esta tarjeta no sale */ });
    }, [api]);

    const asignar = (r) => {
        setPoniendo(r.id);
        api.post(`/admin/routines/biblioteca/${r.id}/asignar`, { client_id: clientId })
            .then(() => { toast.success(`Le hemos puesto «${r.nombre}»`); onAsignada?.(); })
            .catch(e => toast.error(e?.response?.data?.detail || 'No hemos podido asignársela. Inténtalo de nuevo.'))
            .finally(() => setPoniendo(null));
    };

    if (!rutinas.length) return null;

    return (
        <Card className="bg-[#111] border-[#222]">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm text-white/40 uppercase tracking-wider">Ponerle una rutina guardada</CardTitle>
            </CardHeader>
            <CardContent><div className="space-y-2">
                {rutinas.map(r => (
                    <div key={r.id} className="flex items-center justify-between gap-3 p-3 bg-[#0A0A0A] rounded-lg border border-[#222]">
                        <div className="min-w-0">
                            <p className="text-white text-sm">{r.nombre}</p>
                            <p className="text-white/40 text-xs">
                                {r.dias_de_entreno} {r.dias_de_entreno === 1 ? 'día' : 'días'} · {r.ejercicios} ejercicios
                                {r.objetivo ? ` · ${r.objetivo}` : ''}{r.nivel ? ` · ${r.nivel}` : ''}
                            </p>
                        </div>
                        <Button size="sm" variant="outline" disabled={poniendo === r.id}
                            onClick={() => asignar(r)} data-testid={`asignar-rutina-${r.id}`}
                            className="shrink-0 bg-transparent border-[#FF671F]/40 text-[#FF671F] hover:bg-[#FF671F]/10 text-xs">
                            {poniendo === r.id ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Ponérsela'}
                        </Button>
                    </div>
                ))}
            </div></CardContent>
        </Card>
    );
};

const ClientDetailPage = () => {
    const { clientId } = useParams();
    const navigate = useNavigate();
    const { api, user: adminUser, planCatalog, actuarComo } = useAuth();
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
        // El peso con el que se hace el ajuste: el del reporte que se esta leyendo (punto 25).
        peso: '',
        // Y la fecha en que se peso, que NO es la del ajuste (punto 27): se archiva ahi.
        peso_fecha: '',
        // Manana, no hoy (2.3): el ajuste se pone para que empiece al dia siguiente.
        effective_date: hoyISO(),
    };
    const [macrosForm, setMacrosForm] = useState(MACROS_FORM_VACIO);
    const [entryForm, setEntryForm] = useState(MACROS_FORM_VACIO);
    const [savingMacros, setSavingMacros] = useState(false);
    // Lo ultimo que se guardo de verdad, para dejarlo escrito en pantalla (punto 28). El aviso
    // flotante se va solo a los tres segundos: si el coach mira despues, no sabe si guardo, y
    // entonces guarda otra vez (y el ajuste duplicado se le queda como el ultimo).
    const [ultimoGuardado, setUltimoGuardado] = useState(null);
    const [savingEntry, setSavingEntry] = useState(false);
    // Sugerencia de la IA que dio pie al ajuste que hay ahora en el editor (si la hubo).
    const [sugerenciaId, setSugerenciaId] = useState(null);
    const editorMacrosRef = useRef(null);

    // Routine
    const [generatingRoutine, setGeneratingRoutine] = useState(false);
    const [routineInstructions, setRoutineInstructions] = useState('');
    const [generatedRoutine, setGeneratedRoutine] = useState(null);

    // Suplementos
    // El protocolo, versionado por fecha (punto 33). `actual` y `siguiente` los resuelve el
    // backend por fecha; `versiones` es el histórico completo, que antes no existía.
    const [supProtocol, setSupProtocol] = useState({ actual: [], siguiente: [], actual_fecha: '', siguiente_fecha: '', nota: '', versiones: [] });
    // Pestaña de entrenamiento: maquinaria, lesiones y observaciones (2.5)
    const [entrenoForm, setEntrenoForm] = useState({ equipment: [], injuries: [], training_notes: '' });
    const [nuevaLesion, setNuevaLesion] = useState('');
    const [savingEntreno, setSavingEntreno] = useState(false);
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
            toast.success(trainerId ? 'Entrenador asignado' : 'Entrenador quitado');
            fetchClient();
        } catch (e) {
            toast.error(mensajeDeError(e, 'No se pudo cambiar el entrenador'));
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
            if (sp) setSupProtocol({
                actual: sp.actual || [], siguiente: sp.siguiente || [],
                actual_fecha: sp.actual_fecha || '', siguiente_fecha: sp.siguiente_fecha || '',
                nota: sp.nota || '', versiones: sp.versiones || [],
            });
            // El editor de la pestana Macros arranca siempre con los macros guardados
            // (mismo criterio que macrosActuales: 0 es un valor valido, no un hueco).
            const p = response.data.profile;
            const _v = (m, k1, k2) => { const v = m?.[k1] ?? m?.[k2]; return v == null ? '' : String(v); };
            // El peso del editor sale del reporte que se esta ajustando, con SU fecha (puntos
            // 25 y 27). Si el cliente no ha mandado ninguno todavia, se cae al de la ficha, y
            // entonces no hay fecha de pesaje que valga: se archiva con la del ajuste.
            const repPeso = _reporteDelPeso(response.data.reports);
            setMacrosForm({
                training: { protein: _v(p?.macros_training, 'protein', 'proteinas'), carbs: _v(p?.macros_training, 'carbs', 'hidratos'), fat: _v(p?.macros_training, 'fat', 'grasas') },
                rest: { protein: _v(p?.macros_rest, 'protein', 'proteinas'), carbs: _v(p?.macros_rest, 'carbs', 'hidratos'), fat: _v(p?.macros_rest, 'fat', 'grasas') },
                peri: { protein: _v(p?.macros_periworkout, 'protein', 'proteinas'), carbs: _v(p?.macros_periworkout, 'carbs', 'hidratos') },
                note: '',
                criterio: '',
                porcentaje_graso: p?.body_fat != null ? String(p.body_fat) : '',
                peso: repPeso ? String(repPeso.weight) : (p?.weight != null ? String(p.weight) : ''),
                peso_fecha: repPeso ? String(repPeso.created_at).slice(0, 10) : '',
                effective_date: hoyISO(),
            });
            setEntrenoForm({
                equipment: Array.isArray(p?.equipment) ? p.equipment : [],
                injuries: Array.isArray(p?.injuries) ? p.injuries : [],
                training_notes: p?.training_notes || '',
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
        } catch (e) { toast.error(mensajeDeError(e, 'No se pudo obtener la sugerencia')); }
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
            // EL RAZONAMIENTO VA AL CRITERIO INTERNO, NO AL FEEDBACK DEL CLIENTE (punto 4.2).
            // Estaba al revés: se escribía en «Feedback para el cliente», que es lo que le
            // llega como novedad, y el criterio interno se quedaba vacío. Ese texto está
            // escrito para el entrenador -- habla del cliente en tercera persona y con jerga
            // ("venía sin intra", "el coach ya le había dejado contenido de hidrato") --, así
            // que el cliente recibía un informe sobre sí mismo escrito como si no lo fuera a
            // leer.
            // El feedback se deja EN BLANCO a propósito: es obligatorio para guardar, así que
            // el entrenador tiene que escribirlo. Rellenarlo con algo genérico solo
            // conseguiría que se enviara sin mirarlo.
            criterio: (sugerencia?.razonamiento || '').slice(0, 1000),
            note: '',
            effective_date: hoyISO(),
        });
        toast.success('Propuesta cargada: el razonamiento va en el criterio interno. Escribe el feedback del cliente');
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
        } catch (e) { toast.error(mensajeDeError(e, 'No se pudo guardar la evaluación')); }
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
        catch (e) { toast.error(mensajeDeError(e, 'Error al cambiar el rol')); }
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
        catch (e) { toast.error(mensajeDeError(e, 'No se pudo dar de baja')); }
    };

    const macrosFormToBody = (f) => ({
        training: { protein: parseFloat(f.training.protein), carbs: parseFloat(f.training.carbs), fat: parseFloat(f.training.fat) },
        rest: { protein: parseFloat(f.rest.protein), carbs: parseFloat(f.rest.carbs), fat: parseFloat(f.rest.fat) },
        peri: { protein: parseFloat(f.peri.protein) || 0, carbs: parseFloat(f.peri.carbs) || 0 },
        note: f.note,
        criterio: (f.criterio || '').trim() || null,
        porcentaje_graso: f.porcentaje_graso === '' || f.porcentaje_graso == null ? null : parseFloat(f.porcentaje_graso),
        peso: f.peso === '' || f.peso == null ? null : parseFloat(f.peso),
        // La fecha del pesaje viaja aparte de la del ajuste (punto 27): el peso se archiva en
        // el dia en que se peso el cliente, no en el dia en que el coach mueve los macros.
        peso_fecha: f.peso_fecha || null,
        effective_date: f.effective_date,
    });
    const macrosFormIncompleto = (f) => ['training', 'rest'].some(
        b => ['protein', 'carbs', 'fat'].some(k => f[b][k] === '' || f[b][k] == null || isNaN(parseFloat(f[b][k])))
    );

    // Guarda los macros del cliente desde el editor de la pestaña.
    const handleSaveMacros = async () => {
        if (macrosFormIncompleto(macrosForm)) { toast.error('Completa proteína, hidratos y grasa de entrenamiento y descanso'); return; }
        if (!macrosForm.note.trim()) { toast.error('El feedback para el cliente es obligatorio'); return; }
        const f = macrosForm;
        // EL PESO DEL AJUSTE TAMBIÉN ENTRA EN EL HISTÓRICO (#48 del 15-08: «77,1 → 94 → 75 →
        // 94 → 50 kg, saltos de 44 kg entre ajustes seguidos»). El campo ya no acepta
        // cualquier número, pero 94 y 50 son los dos pesos posibles: lo que canta es el
        // salto, y eso solo se ve comparando con el ajuste anterior.
        if (f.peso) {
            const chequeo = revisarPeso(f.peso, pesoUltimoAjuste);
            if (!chequeo.ok) { toast.error(chequeo.error); return; }
            if (chequeo.confirmar && !await confirm({
                title: 'Ese peso da un salto grande',
                description: `${chequeo.confirmar} Si es un dedazo, corrígelo: de este peso salen `
                    + 'la gráfica del cliente y el ritmo con el que se decide el próximo ajuste.',
                confirmLabel: 'Es correcto', cancelLabel: 'Lo corrijo',
            })) return;
        }
        // Confirmación antes de guardar (2.4): "a veces guardo por error y ya me salta como
        // último macro". Se resume lo que se va a guardar para poder repasarlo de un vistazo.
        if (!await confirm({
            title: '¿Guardar estos macros?',
            // La excepción del cliente, la primera línea (punto 39): este es uno de los
            // momentos en que hay que acordarse de ella, y el coach está mirando aquí.
            description: (client?.profile?.excepcion ? `⚠ ${client.profile.excepcion}\n\n` : '')
                + `Entreno ${f.training.protein}/${f.training.carbs}/${f.training.fat} · `
                // «Perientreno», que es como se llama el bloque en el editor de arriba y en
                // el resto de la app (punto 4.18). Aquí decía «Intra», que además es solo uno
                // de sus cuatro modos: el coach confirmaba un número con el nombre de otra cosa.
                + `Perientreno ${f.peri.protein || 0}/${f.peri.carbs || 0} · `
                + `Descanso ${f.rest.protein}/${f.rest.carbs}/${f.rest.fat}`
                + `\nVigente desde el ${_fechaLarga(f.effective_date)}`
                + (f.peso ? ` · peso ${f.peso} kg${f.peso_fecha ? ` del ${_fechaCorta(f.peso_fecha)}` : ''}` : '')
                + '\nEl cliente recibe el feedback como novedad.',
            confirmLabel: 'Guardar macros',
        })) return;
        setSavingMacros(true);
        try {
            await api.put(`/admin/clients/${clientId}/macros`, { ...macrosFormToBody(macrosForm), sugerencia_id: sugerenciaId });
            toast.success('Macros actualizados');
            // Y ademas queda escrito, con la hora (punto 28).
            setUltimoGuardado({
                hora: new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' }),
                desde: f.effective_date,
                peso: f.peso || null,
                pesoFecha: f.peso_fecha || null,
            });
            setSugerencia(null);
            setSugerenciaId(null);
            fetchClient();
        } catch (error) { toast.error(mensajeDeError(error, 'Error al guardar')); }
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
        } catch (error) { toast.error(mensajeDeError(error, 'Error al guardar')); }
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

    // Farmacologia en uso ACTUAL: +10 g de proteina en descanso (doc 03-08). Lo marca el
    // coach, nunca el cliente. Es un dato del perfil: entra en juego en el siguiente
    // calculo de macros con el motor, no reescribe los macros vigentes.
    const handleToggleFarmacologia = async (val) => {
        try {
            await api.put(`/admin/clients/${clientId}`, { farmacologia: val });
            toast.success(val
                ? 'Farmacología activada: +10 g de proteína en descanso al recalcular'
                : 'Farmacología desactivada: proteína normal al recalcular');
            fetchClient();
        } catch (error) { toast.error('Error actualizando la farmacología'); }
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
    // Editar un suplemento ya puesto (2.7): dosis, momento u observaciones.
    const supEdit = (bloque, idx, campo, valor) => setSupProtocol(prev => ({
        ...prev,
        [bloque]: prev[bloque].map((it, i) => i === idx ? { ...it, [campo]: valor } : it),
    }));
    const supSuggest = async () => {
        setSupSuggesting(true);
        try {
            const r = await api.post(`/admin/supplements/suggest?client_id=${clientId}`);
            setSupProtocol(prev => ({ ...prev, actual: r.data.actual || [] }));
            toast.success('Protocolo sugerido (revísalo y guarda)');
        } catch (e) { toast.error('Error al sugerir'); }
        finally { setSupSuggesting(false); }
    };
    // Maquinaria, lesiones y observaciones del entrenamiento (2.5)
    const guardarEntreno = async () => {
        setSavingEntreno(true);
        try {
            await api.put(`/admin/clients/${clientId}`, {
                equipment: entrenoForm.equipment,
                injuries: entrenoForm.injuries,
                training_notes: entrenoForm.training_notes || '',
            });
            toast.success('Entrenamiento actualizado');
            fetchClient();
        } catch (e) { toast.error('No se pudo guardar'); }
        finally { setSavingEntreno(false); }
    };

    const supSave = async () => {
        // Misma confirmación que en macros (2.4): "lo mismo al guardar la suplementación".
        const n = (supProtocol.actual || []).length, s = (supProtocol.siguiente || []).length;
        if (!await confirm({
            title: '¿Guardar la suplementación?',
            description: (client?.profile?.excepcion ? `⚠ ${client.profile.excepcion}\n\n` : '')
                + `${n} suplemento${n === 1 ? '' : 's'} ahora`
                + (s ? ` y ${s} para el siguiente protocolo${supProtocol.siguiente_fecha ? ` (desde el ${_fechaLarga(supProtocol.siguiente_fecha)})` : ''}` : '')
                + '. El cliente lo ve en su apartado de suplementación.',
            confirmLabel: 'Guardar',
        })) return;
        setSupSaving(true);
        try {
            await api.post(`/admin/supplements/save?client_id=${clientId}`, {
                actual: supProtocol.actual, siguiente: supProtocol.siguiente,
                // Desde cuándo aplica cada bloque (punto 33): son dos versiones fechadas.
                actual_fecha: supProtocol.actual_fecha || null,
                siguiente_fecha: supProtocol.siguiente_fecha || null, nota: supProtocol.nota || null,
            });
            toast.success('Suplementación guardada');
            fetchClient();
        } catch (e) { toast.error('Error al guardar suplementación'); }
        finally { setSupSaving(false); }
    };

    // La excepción del cliente (punto 39). Texto libre y vacío = quitarla.
    const [guardandoExcepcion, setGuardandoExcepcion] = useState(false);
    const guardarExcepcion = async (texto) => {
        setGuardandoExcepcion(true);
        try {
            await api.put(`/admin/clients/${clientId}`, { excepcion: texto });
            toast.success(texto.trim() ? 'Excepción guardada' : 'Excepción quitada');
            fetchClient();
        } catch (e) { toast.error(mensajeDeError(e, 'No se pudo guardar la excepción')); }
        finally { setGuardandoExcepcion(false); }
    };

    // Borrar una versión del histórico del protocolo (punto 33).
    const supBorrarVersion = async (fecha) => {
        if (!await confirm({
            title: `¿Borrar el protocolo del ${_fechaCorta(fecha)}?`,
            description: 'Se borra ese registro del histórico. El resto de versiones se queda.',
            confirmLabel: 'Borrar', destructive: true,
        })) return;
        try {
            await api.delete(`/admin/supplements/version/${fecha}?client_id=${clientId}`);
            toast.success('Versión borrada');
            fetchClient();
        } catch (e) { toast.error(mensajeDeError(e, 'No se pudo borrar')); }
    };

    if (loading) return <div className="p-6 bg-[#0A0A0A] min-h-screen"><div className="animate-pulse space-y-4"><div className="h-8 bg-[#222] rounded w-1/4" /><div className="h-48 bg-[#111] rounded-xl" /></div></div>;
    if (!client) return <div className="p-6 bg-[#0A0A0A] min-h-screen text-center text-white/50">Cliente no encontrado</div>;

    const { profile, user, routines, reports, payments, macro_history, nutrition_stats, calma_raw, acceso } = client;
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

    // El peso con el que se ajusta es el DEL REPORTE que se está ajustando, no el último que
    // conste en la ficha (punto 25 del doc del 07-08). Son cosas distintas y por eso salían
    // dos pesos en la app: en Reportes el del último reporte y aquí el de la ficha, que se
    // actualiza por otras vías (un check-in semanal, una edición a mano). Jesús ajusta leyendo
    // un reporte concreto, así que el número que tiene que ver es el de ese reporte.
    //
    // Sin useMemo a propósito, igual que el de abajo: aquí ya se ha pasado por los early
    // returns del componente y un hook a estas alturas rompe el orden entre renders.
    const reporteDelAjuste = _reporteDelPeso(reports);
    // Si el cliente todavía no ha mandado ningún reporte, se sigue usando el de la ficha.
    const pesoActual = reporteDelAjuste
        ? String(reporteDelAjuste.weight)
        : (profile?.weight != null ? String(profile.weight) : '');
    // La fecha del pesaje que se guardará con ese peso (punto 27). Vacía si no hay reporte.
    const pesoFechaActual = reporteDelAjuste ? String(reporteDelAjuste.created_at).slice(0, 10) : '';
    // ¿Se ha tocado algo de la pestaña de entrenamiento respecto a lo guardado?
    const _mismo = (a, b) => JSON.stringify([...(a || [])].sort()) === JSON.stringify([...(b || [])].sort());
    const entrenoTocado = !_mismo(entrenoForm.equipment, profile?.equipment)
        || !_mismo(entrenoForm.injuries, profile?.injuries)
        || (entrenoForm.training_notes || '') !== (profile?.training_notes || '');
    // Peso con el que se hizo el ajuste anterior: es contra el que compara el coach.
    // Sin useMemo a propósito: aquí ya se ha pasado por los early returns del componente
    // y un hook a estas alturas rompe las reglas de hooks (y el orden entre renders).
    const pesoUltimoAjuste = (() => {
        const orden = [...(macro_history || [])].sort((a, b) => _fechaEntrada(b).localeCompare(_fechaEntrada(a)));
        for (const h of orden) { const p = h.peso ?? h.client_weight; if (typeof p === 'number') return p; }
        return null;
    })();
    const macrosTocados = ['training', 'rest', 'peri'].some(
        b => Object.keys(macrosActuales[b]).some(k => String(macrosForm[b][k] ?? '') !== macrosActuales[b][k])
    ) || String(macrosForm.porcentaje_graso ?? '') !== bfActual
      || String(macrosForm.peso ?? '') !== pesoActual;
    const setMacroCampo = (bloque, campo, valor) => setMacrosForm(prev => ({ ...prev, [bloque]: { ...prev[bloque], [campo]: valor } }));
    const descartarCambiosMacros = () => (setSugerenciaId(null), setMacrosForm({
        ...macrosActuales, note: '', criterio: '', porcentaje_graso: bfActual, peso: pesoActual,
        peso_fecha: pesoFechaActual, effective_date: hoyISO(),
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
                        {/* El estado con palabras: «pendiente_pago» es el código de la base (#64). */}
                        {(() => {
                            /* El mismo estado que ve él al entrar, no la etiqueta del perfil. */
                            const e = estadoDeAcceso({ ...(profile || {}), acceso });
                            return <Badge className={`${e.tono === 'ok' ? 'bg-green-500/20 text-green-500'
                                : e.tono === 'aviso' ? 'bg-yellow-500/20 text-yellow-400'
                                : 'bg-red-500/20 text-red-400'} border-0`}>{e.texto}</Badge>;
                        })()}
                    </div>
                    <p className="text-white/40 text-sm truncate">{user?.email}</p>
                </div>
            </div>

            {/* LA EXCEPCIÓN (punto 39). Va aquí arriba, antes de las pestañas y sin poder
                plegarse: si hay que abrir algo para verla, ya está tan escondida como en la
                hoja de la que viene. Esto le costó dinero a Jesús: se le cobró una renovación
                a una clienta a la que le había perdonado un mes, porque la excepción solo
                estaba en su cabeza. */}
            <ExcepcionDelCliente
                excepcion={profile?.excepcion}
                guardando={guardandoExcepcion}
                onGuardar={guardarExcepcion} />

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
                            <InfoItem icon={Activity} label="Estado" value={estadoClienteLabel(profile?.status)} />
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
                            <InfoItem icon={Target} label="Rutina" value={activeRoutine ? plural(activeRoutine.days?.filter(d => !d.is_rest).length || 0, 'día') : 'Sin rutina'} />
                            <InfoItem icon={CreditCard} label="Próx. cobro" value={profile?.next_payment ? new Date(profile.next_payment).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }) : '-'} />
                            <InfoItem icon={Calendar} label="Inicio" value={profile?.created_at ? new Date(profile.created_at).toLocaleDateString('es-ES') : '-'} />
                            {/* Punto 30: el peso, con su fecha. "94 kg · hace 3 días". El
                                número es el último de la serie; si el cliente es antiguo y
                                no tiene serie todavía, se cae al campo de la ficha. */}
                            <InfoItem icon={Scale} label="Peso" value={(() => {
                                const p = _ultimoDeLaSerie(profile?.pesos);
                                if (p) return <>{p.valor} kg <span className="text-white/40 font-normal">· {_haceCuanto(p.fecha)}</span></>;
                                return profile?.weight ? `${profile.weight} kg` : '-';
                            })()} />
                            <InfoItem icon={Scale} label="% graso" value={(() => {
                                const g = _ultimoDeLaSerie(profile?.porcentajes_grasos);
                                if (g) return <>{g.valor}% <span className="text-white/40 font-normal">· {_haceCuanto(g.fecha)}</span></>;
                                return profile?.body_fat != null ? `${profile.body_fat}%` : '-';
                            })()} />
                            <InfoItem icon={Target} label="Objetivo" value={objetivoLabel(profile?.goal)} />
                        </div>
                    </CardContent></Card>
                </TabsContent>

                {/* ========== TAB 2: MACROS ========== */}
                <TabsContent value="macros" className="space-y-4">
                    {/* Lo primero que se lee para decidir: lo que contestó en su último reporte
                        (Parte 7 del 09-08). Debajo van la escalera, las fotos y el formulario,
                        que ya estaban, para que la decisión entera quepa en esta pestaña. */}
                    <ReporteParaDecidir reporte={reporteDelAjuste} reportes={reports}
                        pesoUltimoAjuste={pesoUltimoAjuste} onVerReportes={() => setActiveTab('seguimiento')} />

                    {/* LA TABLA VA ARRIBA, ANTES DEL EDITOR (vídeo del 05-08): el coach no pone un
                        número en abstracto, decide comparando con la escalera anterior. Con la
                        tabla debajo tenía que subir y bajar por la pantalla o acordarse. La fila
                        que está escribiendo aparece aquí en gris hasta que guarda. */}
                    <MacroHistoryTable items={macro_history} onEdit={openEditEntry} onRepeat={openRepeatEntry}
                        onDelete={deleteMacroEntry} onEvaluar={openEvaluar}
                        borrador={macrosTocados ? {
                            _borrador: true,
                            effective_date: macrosForm.effective_date,
                            training: macrosForm.training, peri: macrosForm.peri, rest: macrosForm.rest,
                            peso: profile?.weight,
                            // «80 kg · NaN%» antes de guardar (punto 4.18). `Number('')` da 0
                            // pero `Number(undefined)` y `Number('25,5')` dan NaN, y el NaN se
                            // colaba tal cual a la pantalla. Con coma decimal, que es como se
                            // escribe aquí, pasaba siempre.
                            body_fat: _numeroOno(macrosForm.porcentaje_graso),
                            criterio: macrosForm.criterio, note: macrosForm.note,
                        } : null} />

                    {/* Las fotos, todas juntas y aquí mismo (3.1): las mira mientras ajusta y
                        no quiere un comparador en este punto del flujo. */}
                    <MuralFotos api={api} clientId={clientId} calmaFotos={calma_raw?.fotos_descargadas}
                        reports={reports} macroHistory={macro_history} />

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
                        {/* LO QUE COME HOY, CUANDO NO ES LO QUE PONE AQUÍ (17-08-2026).
                            Este editor carga `macros_training`, que es un espejo; el reparto
                            del día usa la fila vigente del historial, que es lo que el cliente
                            tiene delante en Nutrición. Cuando alguien escribe uno sin el otro
                            -- la sincronización de Calma lo ha hecho hoy mismo en dos --, el
                            coach ajustaría sobre un número que el cliente no tiene. */}
                        {profile?.macros_descuadrados && profile?.macros_vigentes && (
                            <div className="mb-3 rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-3">
                                <p className="text-white text-sm">
                                    Ojo: hoy está comiendo con{' '}
                                    <b className="text-yellow-400">
                                        {profile.macros_vigentes.entreno?.protein} P ·{' '}
                                        {profile.macros_vigentes.entreno?.carbs} H ·{' '}
                                        {profile.macros_vigentes.entreno?.fat} G
                                    </b>{' '}
                                    en día de entreno, que no es lo que hay escrito aquí.
                                </p>
                                <p className="text-white/50 text-xs mt-1">
                                    Es lo que manda desde el {profile.macros_vigentes.desde}
                                    {profile.macros_vigentes.quien ? ` · lo puso ${profile.macros_vigentes.quien}` : ''}
                                    {' '}· Al guardar aquí, estos pasan a ser los suyos.
                                </p>
                            </div>
                        )}
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
                            <div className="grid grid-cols-3 gap-3">
                                <div>
                                    <Label className="text-white/60 text-xs">Vigente desde</Label>
                                    {/* POR DEFECTO HOY (orden de Francisco, 11-08-2026). Antes venía con la
                                        fecha de mañana, por el punto 2.3: se entendía que el ajuste arranca al
                                        día siguiente. En la práctica no es así -- el cambio se quiere aplicar
                                        el día que se hace --, y quien quisiera lo contrario tenía que corregir
                                        la fecha en cada ajuste.
                                        Se sigue avisando solo si se sale de hoy, hacia delante o hacia atrás. */}
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
                                        <p className="text-[10px] text-white/30 mt-1">Empiezan hoy. Los días anteriores conservan los macros previos.</p>
                                    )}
                                </div>
                                <div>
                                    <Label className="text-white/60 text-xs">Peso</Label>
                                    <Input type="number" step="0.1" min="25" max="300" value={macrosForm.peso}
                                        onChange={e => setMacrosForm({ ...macrosForm, peso: e.target.value })}
                                        placeholder="-" className="bg-[#0A0A0A] border-[#333] text-white mt-1" data-testid="macro-peso" />
                                    {/* Viene del reporte que se está ajustando, y se dice de cuál:
                                        un peso sin fecha al lado no se puede contrastar con nada.
                                        Debajo, la diferencia con el del ajuste anterior, que es lo
                                        primero que mira el coach. */}
                                    {reporteDelAjuste && (
                                        <p className="text-[10px] mt-1 text-white/40" data-testid="peso-origen">
                                            Del reporte del <b className="text-white/60">{_fechaCorta(String(reporteDelAjuste.created_at).slice(0, 10))}</b>
                                        </p>
                                    )}
                                    {(() => {
                                        const p = parseFloat(macrosForm.peso);
                                        // Punto 27: se archiva con la fecha en que se peso, no con la del ajuste.
                                        const dondeQueda = macrosForm.peso_fecha
                                            ? `Queda registrado el ${_fechaCorta(macrosForm.peso_fecha)}, el día del pesaje.`
                                            : 'Sin reporte: queda registrado con la fecha del ajuste.';
                                        if (isNaN(p) || pesoUltimoAjuste == null) return <p className="text-[10px] text-white/30 mt-1">{dondeQueda}</p>;
                                        const d = Math.round((p - pesoUltimoAjuste) * 10) / 10;
                                        return (
                                            <p className="text-[10px] mt-0.5 text-white/40">
                                                Últimos macros: {pesoUltimoAjuste} kg ·{' '}
                                                <b className={d > 0 ? 'text-red-400' : d < 0 ? 'text-emerald-400' : 'text-white/50'}>
                                                    {d > 0 ? `ha ganado ${d}` : d < 0 ? `ha perdido ${Math.abs(d)}` : 'sin cambios'}{d !== 0 ? ' kg' : ''}
                                                </b>
                                            </p>
                                        );
                                    })()}
                                </div>
                                <div>
                                    <Label className="text-white/60 text-xs">% graso</Label>
                                    <Input type="number" step="0.1" min="3" max="60" value={macrosForm.porcentaje_graso}
                                        onChange={e => setMacrosForm({ ...macrosForm, porcentaje_graso: e.target.value })}
                                        placeholder="-" className="bg-[#0A0A0A] border-[#333] text-white mt-1" data-testid="macro-body-fat" />
                                    <p className="text-[10px] text-white/30 mt-1">Opcional. Solo cuando lo estimes.</p>
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
                                    {/* Aquí es donde más falta hacen: el feedback es obligatorio
                                        para guardar un ajuste, así que se escribe uno por cada
                                        cliente y cada quincena (punto 4.1). */}
                                    <PlantillasFeedback actual={macrosForm.note} testid="plantillas-macros"
                                        onInsertar={t => setMacrosForm({ ...macrosForm, note: t })} />
                                </div>
                            </div>
                        </div>
                        {/* Punto 28: que se vea que ha guardado. El aviso flotante se va solo; esto
                            se queda mientras el coach siga en la ficha, y dice QUE quedo guardado. */}
                        {ultimoGuardado && !macrosTocados && (
                            <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 flex items-start gap-2" data-testid="macros-guardado">
                                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                                <p className="text-xs text-emerald-300/90">
                                    <b>Guardado a las {ultimoGuardado.hora}.</b>{' '}
                                    Vigente desde el {_fechaLarga(ultimoGuardado.desde)}
                                    {ultimoGuardado.peso ? ` · peso ${ultimoGuardado.peso} kg${ultimoGuardado.pesoFecha ? ` del ${_fechaCorta(ultimoGuardado.pesoFecha)}` : ''}` : ''}.
                                    {' '}El cliente ya lo tiene.
                                </p>
                            </div>
                        )}
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
                                            <span className="text-white/50">Desde el anterior: <b className="text-white">{sugerencia.contexto_decision.delta_ultimo > 0 ? '+' : ''}{sugerencia.contexto_decision.delta_ultimo} kg</b>{sugerencia.contexto_decision.dias_desde_anterior != null ? <span className="text-white/30"> ({plural(sugerencia.contexto_decision.dias_desde_anterior, 'día')})</span> : null}</span>
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
                                <p className="text-white/30 text-[10px] leading-relaxed">Es una sugerencia para que la revises. Al usarla se cargan estos valores en el editor de arriba (vigentes hoy); nada se guarda hasta que le des a "Guardar macros".</p>
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

                    {/* Farmacologia en uso actual: excepcion de proteina del doc 03-08 */}
                    <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                        <p className="text-xs font-bold text-white/40 uppercase tracking-wider mb-3">Farmacología</p>
                        <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0">
                                <p className="text-sm text-white font-medium">
                                    {profile?.farmacologia ? 'La usa actualmente' : 'No la usa'}
                                </p>
                                <p className="text-xs text-white/40">
                                    {profile?.farmacologia
                                        ? '+10 g de proteína en el día de descanso (y otros 10 en entreno si hiciera falta para que entreno + peri siga por encima).'
                                        : 'Marcar solo si la usa AHORA. Si la usó en el pasado y ya no, va con proteína normal.'}
                                </p>
                            </div>
                            <button
                                onClick={() => handleToggleFarmacologia(!profile?.farmacologia)}
                                data-testid="toggle-farmacologia"
                                className={`shrink-0 px-4 py-2 rounded-lg text-xs font-bold transition-all ${profile?.farmacologia ? 'bg-[#FF671F] text-white' : 'bg-[#1a1a1a] text-white/60 border border-[#222] hover:text-white'}`}
                            >{profile?.farmacologia ? 'Farmacología: ON' : 'Marcar farmacología'}</button>
                        </div>
                        <p className="text-white/30 text-[10px] leading-relaxed mt-3">
                            Es un dato del perfil: entra en el siguiente cálculo de macros con el motor. No toca los macros que tiene puestos hoy.
                        </p>
                    </CardContent></Card>


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
                                    <PlantillasFeedback actual={entryForm.note} testid="plantillas-entrada"
                                        onInsertar={t => setEntryForm({ ...entryForm, note: t })} />
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
                            {/* Del catálogo cuando el perfil no trae precio propio (punto 2.4c).
                                Lo resuelve el servidor: aquí salía «0€/ciclo» en la ficha del
                                mismo cliente al que la lista le pone bien su precio. */}
                            <InfoItem icon={CreditCard} label="Precio"
                                value={profile?.precio_cortesia ? 'Cortesía' : `${profile?.precio_ciclo ?? profile?.price ?? 0}€/ciclo`} />
                            <InfoItem icon={Calendar} label="Inicio" value={profile?.created_at ? new Date(profile.created_at).toLocaleDateString('es-ES') : '-'} />
                            <InfoItem icon={Calendar} label="Próx. cobro" value={profile?.next_payment ? new Date(profile.next_payment).toLocaleDateString('es-ES') : '-'} />
                        </div>
                        {/* Punto 39: aquí es donde se mira antes de cobrar, y aquí es donde la
                            excepción tiene que estar delante. El caso que costó dinero fue
                            exactamente este: cobrarle la renovación a quien tenía un mes
                            perdonado. */}
                        {profile?.excepcion && (
                            <div className="mt-4 flex items-start gap-2 rounded-lg border border-[#FF671F]/40 bg-[#FF671F]/10 p-3" data-testid="excepcion-en-cobro">
                                <AlertCircle className="w-4 h-4 text-[#FF671F] shrink-0 mt-0.5" />
                                <p className="text-sm text-white"><b className="text-[#FF671F]">Antes de cobrarle:</b> {profile.excepcion}</p>
                            </div>
                        )}
                    </CardContent></Card>
                    <Card className="bg-[#111] border-[#222]"><CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">Historial de pagos</CardTitle></CardHeader>
                        {/* Los cobros llegan de dos sitios con dos formas (punto 5 del 17-08):
                            los de Cobros (`pagos_historicos`: importe/fecha/concepto/origen) y
                            los que escribió el checkout de la app (amount/created_at/status).
                            Se normalizan aquí para que la tarjeta no tenga que saberlo. */}
                        <CardContent>{payments?.length > 0 ? (
                            <div className="space-y-2">{payments.map((p, i) => {
                                // El importe con la coma y sus dos decimales, igual que en
                                // Cobros: «60,50 €», no «60.5€».
                                const bruto = Number(p.importe ?? p.amount);
                                const importe = Number.isFinite(bruto)
                                    ? bruto.toLocaleString('es-ES', { style: 'currency', currency: p.moneda || 'EUR' })
                                    : '-';
                                const cuando = p.fecha || p.created_at;
                                const fallido = p.status ? p.status !== 'success' : p.es_dinero === false;
                                return (
                                <div key={p.id || p.referencia || i} className="flex items-center justify-between p-3 bg-[#0A0A0A] rounded-lg border border-[#222] gap-3">
                                    <div className="min-w-0">
                                        <p className="text-white text-sm font-medium">{importe}</p>
                                        <p className="text-white/40 text-xs">
                                            {cuando ? new Date(cuando).toLocaleDateString('es-ES') : '-'}
                                            {p.concepto ? ` · ${p.concepto}` : ''}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2 flex-shrink-0">
                                        {p.origen && <span className="text-white/30 text-[11px] uppercase tracking-wider">{p.origen}</span>}
                                        <Badge className={fallido ? 'bg-red-500/20 text-red-400 border-0' : 'bg-green-500/20 text-green-500 border-0'}>
                                            {fallido ? 'Fallido' : 'Cobrado'}
                                        </Badge>
                                    </div>
                                </div>
                            );})}</div>
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
                    {/* Las respuestas que deciden sus macros (punto 17). Van ANTES del
                        cuestionario largo porque son las que se miran para ajustar. */}
                    <AjustesDelCuestionario ajustes={profile?.ajustes_macros} />
                    {/* El cuestionario largo. Se rellenaba entero y NO se veía en ninguna
                        parte de la ficha: treinta preguntas de historia, salud, entreno,
                        suplementación y comida que el cliente contestaba para nadie. */}
                    <PerfilLargo nivel1={profile?.nivel1} />
                    {calma_raw?.formulario_inicial && <CalmaCuestionario fi={calma_raw.formulario_inicial} />}
                </TabsContent>

                {/* ========== TAB 6: ENTRENAMIENTO ========== */}
                <TabsContent value="entrenamiento" className="space-y-4">
                    {/* Maquinaria, lesiones y observaciones: EDITABLES aquí (2.5). Es lo que el
                        coach actualiza al leer el reporte, y el entrenamiento lo lleva aparte
                        de la nutrición, así que no tiene sentido que estuvieran de solo lectura. */}
                    <Card className="bg-[#111] border-[#222]"><CardContent className="p-5">
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                            <p className="text-xs font-bold text-white/40 uppercase tracking-wider">Maquinaria, lesiones y observaciones</p>
                            <div className="flex items-center gap-2">
                                {entrenoTocado && <Badge className="border-0 text-[10px] bg-[#FF671F]/20 text-[#FF671F]">sin guardar</Badge>}
                                <Button size="sm" onClick={guardarEntreno} disabled={savingEntreno || !entrenoTocado}
                                    className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs disabled:opacity-40" data-testid="save-entreno-btn">
                                    {savingEntreno ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <><Save className="w-3.5 h-3.5 mr-1" />Guardar</>}
                                </Button>
                            </div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                            <div>
                                <p className="text-xs text-white/40 uppercase tracking-wider mb-2">Maquinaria disponible</p>
                                <div className="flex flex-wrap gap-1.5">
                                    {EQUIPAMIENTO_OPCIONES.map(o => {
                                        const activo = entrenoForm.equipment.includes(o.value);
                                        return (
                                            <button key={o.value} type="button" data-testid={`equip-${o.value}`}
                                                onClick={() => setEntrenoForm(f => ({ ...f, equipment: activo ? f.equipment.filter(x => x !== o.value) : [...f.equipment, o.value] }))}
                                                className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-colors ${
                                                    activo ? 'bg-[#FF671F]/15 text-[#FF671F] border-[#FF671F]/40' : 'bg-[#0A0A0A] text-white/40 border-[#222] hover:text-white/70'}`}>
                                                {o.label}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                            <div>
                                <p className="text-xs text-white/40 uppercase tracking-wider mb-2">Lesiones activas</p>
                                <div className="flex flex-wrap gap-1.5 mb-2">
                                    {entrenoForm.injuries.length === 0 && <span className="text-white/30 text-sm">Sin lesiones</span>}
                                    {entrenoForm.injuries.map((l, i) => (
                                        <span key={i} className="inline-flex items-center gap-1 bg-red-500/10 text-red-400 rounded-lg px-2 py-1 text-xs">
                                            {l}
                                            <button type="button" onClick={() => setEntrenoForm(f => ({ ...f, injuries: f.injuries.filter((_, j) => j !== i) }))}
                                                className="hover:text-white"><X className="w-3 h-3" /></button>
                                        </span>
                                    ))}
                                </div>
                                <Input value={nuevaLesion} onChange={e => setNuevaLesion(e.target.value)}
                                    onKeyDown={e => {
                                        if (e.key === 'Enter' && nuevaLesion.trim()) {
                                            e.preventDefault();
                                            setEntrenoForm(f => ({ ...f, injuries: [...f.injuries, nuevaLesion.trim()] }));
                                            setNuevaLesion('');
                                        }
                                    }}
                                    placeholder="Escribe una lesión y pulsa Enter" className="bg-[#0A0A0A] border-[#333] text-white text-sm" data-testid="nueva-lesion" />
                            </div>
                        </div>
                        <div className="mt-4">
                            <Label className="text-white/60 text-xs">Observaciones del entrenamiento</Label>
                            <Textarea value={entrenoForm.training_notes} onChange={e => setEntrenoForm(f => ({ ...f, training_notes: e.target.value }))}
                                placeholder="Ej: no le va bien la sentadilla libre, la sustituye por hack…"
                                className="bg-[#0A0A0A] border-[#333] text-white mt-1 min-h-[60px]" data-testid="entreno-notas" />
                            <p className="text-[10px] text-white/30 mt-1">Para ti. Aquí, no en suplementación: el entrenamiento va aparte.</p>
                        </div>
                    </CardContent></Card>

                    {/* ELEGIR UNA DE LAS GUARDADAS (17-08-2026). Antes solo se podía escribir
                        a mano aquí o pedírsela a la IA; las que el equipo tiene hechas no se
                        podían reutilizar. Al asignarla se copia, así que retocársela luego a
                        este cliente no se la cambia a los demás. */}
                    <RutinasGuardadas api={api} clientId={clientId} onAsignada={fetchClient} />

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
                                {/* La dosis, el momento y las observaciones se EDITAN aquí aunque el
                                    suplemento venga del catálogo (2.7): el protocolo cargado es el punto
                                    de partida, no algo cerrado. El título se queda fijo para que siga
                                    correspondiendo con su ficha del catálogo. */}
                                {supProtocol[bloque].map((it, i) => (
                                    <div key={i} className="p-2.5 bg-[#0A0A0A] rounded-lg border border-[#222]">
                                        <div className="flex items-start justify-between gap-2">
                                            <p className="text-white text-sm font-medium min-w-0">{it.titulo}</p>
                                            <button onClick={() => supRemove(bloque, i)} className="text-white/30 hover:text-red-400 flex-shrink-0"><X className="w-4 h-4" /></button>
                                        </div>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
                                            <Input value={it.cuanto || ''} onChange={e => supEdit(bloque, i, 'cuanto', e.target.value)}
                                                placeholder="Cuánto (ej: 1 cápsula)" data-testid={`sup-cuanto-${bloque}-${i}`}
                                                className="bg-[#111] border-[#333] text-white text-xs h-8" />
                                            <Input value={it.cuando || ''} onChange={e => supEdit(bloque, i, 'cuando', e.target.value)}
                                                placeholder="Cuándo (ej: con el desayuno)" data-testid={`sup-cuando-${bloque}-${i}`}
                                                className="bg-[#111] border-[#333] text-white text-xs h-8" />
                                        </div>
                                        <Input value={it.observaciones || ''} onChange={e => supEdit(bloque, i, 'observaciones', e.target.value)}
                                            placeholder="Observaciones (opcional)" data-testid={`sup-obs-${bloque}-${i}`}
                                            className="bg-[#111] border-[#333] text-white text-xs h-8 mt-2" />
                                    </div>
                                ))}
                                {/* Cada bloque es una VERSIÓN con su fecha (punto 33). El de
                                    arriba es el que toma hoy; el de abajo, uno preparado para
                                    más adelante. Cambiar una dosis del de arriba corrige esa
                                    versión y no abre una nueva: abrir una versión nueva es una
                                    decisión, y para eso está la fecha. */}
                                <div className="pt-1">
                                    <Label className="text-white/40 text-xs">
                                        {bloque === 'actual' ? 'Lo toma desde el día' : 'A partir del día'}
                                    </Label>
                                    <Input type="date"
                                        value={(bloque === 'actual' ? supProtocol.actual_fecha : supProtocol.siguiente_fecha) || ''}
                                        onChange={e => setSupProtocol(p => ({ ...p, [bloque === 'actual' ? 'actual_fecha' : 'siguiente_fecha']: e.target.value }))}
                                        data-testid={`sup-fecha-${bloque}`}
                                        className="bg-[#0A0A0A] border-[#333] text-white mt-1 w-full sm:w-48" />
                                    {bloque === 'actual' && !supProtocol.actual_fecha && (
                                        <p className="text-[10px] text-white/30 mt-1">Si lo dejas vacío, empieza hoy.</p>
                                    )}
                                </div>
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

                    {/* EL HISTÓRICO (punto 33). Antes no quedaba registro de qué tomaba el
                        cliente en cada momento: cada guardado pisaba al anterior. */}
                    {supProtocol.versiones?.length > 0 && (
                        <Card className="bg-[#111] border-[#222]" data-testid="sup-historial">
                            <CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider">
                                Histórico del protocolo ({supProtocol.versiones.length})
                            </CardTitle></CardHeader>
                            <CardContent className="space-y-1.5">
                                {[...supProtocol.versiones].reverse().map(v => {
                                    const esHoy = v.fecha === supProtocol.actual_fecha;
                                    const esFuturo = v.fecha > hoyISO();
                                    return (
                                        <div key={v.fecha} className={`flex items-start gap-2 p-2 rounded-lg border ${
                                            esHoy ? 'border-[#FF671F]/40 bg-[#FF671F]/5' : 'border-[#222] bg-[#0A0A0A]'}`}>
                                            <div className="min-w-[120px]">
                                                <p className="text-white text-sm font-medium tabular-nums">{_fechaCorta(v.fecha)}</p>
                                                {esHoy && <span className="text-[9px] uppercase tracking-wide text-[#FF671F]">lo toma ahora</span>}
                                                {esFuturo && <span className="text-[9px] uppercase tracking-wide text-white/40">preparado</span>}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-white/70 text-xs">{(v.items || []).map(i => i.titulo).join(' · ') || 'Sin suplementos'}</p>
                                                {v.nota && <p className="text-white/30 text-[11px] mt-0.5 truncate" title={v.nota}>{v.nota}</p>}
                                                {v.guardado_por && <p className="text-white/25 text-[10px] mt-0.5">lo puso {v.guardado_por}</p>}
                                            </div>
                                            <button onClick={() => supBorrarVersion(v.fecha)} title="Borrar esta versión"
                                                className="text-white/25 hover:text-red-400 flex-shrink-0"><Trash2 className="w-3.5 h-3.5" /></button>
                                        </div>
                                    );
                                })}
                            </CardContent>
                        </Card>
                    )}

                    <p className="text-white/30 text-xs">El catálogo se gestiona en <button onClick={() => navigate('/admin/supplements-catalog')} className="text-[#FF671F] hover:underline">Catálogo de suplementos</button>.</p>
                    {calma_raw?.suplementacion && <CalmaSuplementos sup={calma_raw.suplementacion} />}
                </TabsContent>

                {/* ========== TAB 7: NUTRICIÓN ========== */}
                <TabsContent value="nutricion" className="space-y-4">
                    {/* ENTRAR EN SU CALCULADORA (punto 4.11). Esta pestaña era de solo
                        lectura: se veían sus dietas, sus alimentos y sus gramos, y no había
                        forma de añadir nada ni de montarle una comida. Desde aquí se abre el
                        MISMO editor que usa él, con una barra naranja arriba que no deja
                        olvidarse de en qué cuenta estás. */}
                    <Card className="bg-[#111] border-[#222]">
                        <CardContent className="p-4 flex items-center gap-3 flex-wrap">
                            <UserCog className="w-5 h-5 text-[#FF671F] shrink-0" />
                            <div className="min-w-0 flex-1">
                                <p className="text-white text-sm font-semibold">Montarle el día tú mismo</p>
                                <p className="text-white/40 text-xs">
                                    Abre su calculadora tal y como la ve él. Lo que guardes queda
                                    firmado con tu nombre y él lo verá.
                                </p>
                            </div>
                            <Button onClick={() => actuarComo({
                                userId: profile?.user_id,
                                clientId: clientId,
                                nombre: user?.name || profile?.name || 'tu cliente',
                            })} data-testid="entrar-en-su-calculadora"
                                className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white">
                                Entrar en su calculadora
                            </Button>
                        </CardContent>
                    </Card>
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
                    {/* Las diez medidas comparadas en el tiempo (punto 35): hasta ahora solo
                        se veía el último dato. */}
                    <EvolucionMedidas reports={reports} tono="admin" />
                    {/* La comparativa con etiquetas (3.2): cuatro fotos como mucho y cada una
                        responde a algo. Sustituye al comparador de dos con selectores de pose,
                        que ya no hace falta (decisión del 05-08). */}
                    <ComparativaFases api={api} clientId={clientId} calmaFotos={calma_raw?.fotos_descargadas}
                        reports={reports} macroHistory={macro_history} faseDesde={profile?.fase_desde} fase={profile?.goal}
                        porcentajesGrasos={[...(calma_raw?.porcentajes_grasos || []), ...(profile?.porcentajes_grasos || [])]} />
                    <EvolutionTimeline api={api} clientId={clientId} reportes={calma_raw?.formularios_mensuales} calmaFotos={calma_raw?.fotos_descargadas} reports={reports} macroHistory={macro_history} />
                    <CoachCheckins clientId={clientId} />
                    {/* Meter el reporte de un cliente que lo mandó por WhatsApp (punto 45) */}
                    <ReportePorElCliente api={api} clientId={clientId} onHecho={fetchClient} />
                    <ReportsFeedbackList initialReports={reports} />
                </TabsContent>
            </Tabs>
        </div>
    );
};

// ========== SUB-COMPONENTS ==========

// Un número, o null si no lo es. Acepta la coma decimal, que es como se escribe aquí:
// `Number('25,5')` es NaN, y ese NaN acababa pintado en pantalla (punto 4.18).
const _numeroOno = (v) => {
    if (v === '' || v === null || v === undefined) return null;
    const n = Number(String(v).replace(',', '.'));
    return Number.isFinite(n) ? n : null;
};

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
// EN ROJO LO QUE CAMBIÓ respecto al ajuste anterior, como en Calma: el coach no lee
// números sueltos, lee la escalera. Con todo del mismo color hay que comparar fila a
// fila a ojo; en rojo, el cambio salta solo (vídeo del 05-08, minuto 1:47).
//
// Desde el punto 31 (07-08) el cambio viene GUARDADO en la entrada (`cambios`), calculado
// al guardar contra los macros que el cliente tenía en ese momento. Se usa ese cuando está,
// porque es el que dice la verdad; comparar con la fila de arriba solo acierta si la tabla
// está entera y en orden. Para las entradas viejas y para la fila sin guardar se sigue
// comparando, que es lo que había.
const _CAMPOS = [['protein', 'proteinas'], ['carbs', 'hidratos'], ['fat', 'grasas']];
const _NOMBRE_CAMPO = ['proteina', 'hidratos', 'grasa'];
const MacroCeldas = ({ m, prev, showG = true, apagado = false, cambios = null }) => (
    <>
        {(showG ? _CAMPOS : _CAMPOS.slice(0, 2)).map((keys, i) => {
            const v = m ? _mv(m, keys) : null;
            const p = prev ? _mv(prev, keys) : null;
            const cambio = cambios
                ? !!cambios[_NOMBRE_CAMPO[i]]
                : (v != null && p != null && v !== p);
            return (
                <td key={i} className={`px-2 py-2 text-right tabular-nums font-bold ${
                    apagado ? 'text-white/40' : cambio ? 'text-red-400' : 'text-white/70'}`}
                    title={cambio && p != null ? `antes ${p} g (${v > p ? '+' : ''}${v - p})` : undefined}>
                    {v ?? '-'}
                </td>
            );
        })}
    </>
);

// LA EVOLUCIÓN DE CADA MEDIDA (punto 35 del doc del 07-08) vive ahora en
// `components/EvolucionMedidas.jsx`, compartida con la pantalla de Evolución del cliente
// (T6 del doc 16-08): es la misma tabla y tiene que decir lo mismo en los dos sitios. Aquí
// se pinta con `tono="admin"`, que es lo único que cambiaba.

// LA EXCEPCIÓN DEL CLIENTE (punto 39 del doc del 07-08).
//
// Hay 17 clientes con una excepción apuntada a mano en una hoja, y no se parecen entre sí:
// uno cuya membresía paga su marido, uno que paga en efectivo, uno al que no se le genera
// rutina, uno que no paga nada y aun así se le hace, uno con ciclo de 4 semanas en vez de
// 12, otro al que se le manda el reporte por WhatsApp. Por eso es texto libre y no un juego
// de casillas: modelarlas sería inventarse las categorías antes de conocerlas, y la de la
// número 18 no entraría en ninguna.
//
// Cuando hay excepción se ve SIEMPRE, en naranja y arriba del todo. Cuando no la hay, un
// enlace pequeño que no molesta: la mayoría de los clientes no tienen ninguna.
const ExcepcionDelCliente = ({ excepcion, guardando, onGuardar }) => {
    const [editando, setEditando] = useState(false);
    const [texto, setTexto] = useState(excepcion || '');
    useEffect(() => { setTexto(excepcion || ''); }, [excepcion]);

    if (!excepcion && !editando) {
        return (
            <button onClick={() => setEditando(true)} data-testid="anadir-excepcion"
                className="text-xs text-white/30 hover:text-[#FF671F] flex items-center gap-1.5">
                <AlertCircle className="w-3.5 h-3.5" /> Añadir una excepción
            </button>
        );
    }

    return (
        <div className="rounded-xl border border-[#FF671F]/50 bg-[#FF671F]/10 p-4" data-testid="excepcion-cliente">
            <div className="flex items-start gap-2.5">
                <AlertCircle className="w-5 h-5 text-[#FF671F] shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                    <p className="text-[10px] font-bold text-[#FF671F] uppercase tracking-wider mb-1">Excepción de este cliente</p>
                    {editando ? (
                        <>
                            <Textarea value={texto} onChange={e => setTexto(e.target.value)} autoFocus
                                placeholder="Ej: la membresía se la paga su marido · paga en efectivo · no se le genera rutina · ciclo de 4 semanas · el reporte se lo manda por WhatsApp"
                                data-testid="excepcion-texto"
                                className="bg-[#0A0A0A] border-[#333] text-white text-sm" rows={2} />
                            <div className="flex items-center gap-2 mt-2">
                                <Button size="sm" onClick={() => { onGuardar(texto); setEditando(false); }} disabled={guardando}
                                    className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs" data-testid="guardar-excepcion">
                                    {guardando ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <><Save className="w-3.5 h-3.5 mr-1" />Guardar</>}
                                </Button>
                                <button onClick={() => { setTexto(excepcion || ''); setEditando(false); }}
                                    className="text-xs text-white/40 hover:text-white">Cancelar</button>
                                {excepcion && <span className="text-[10px] text-white/30 ml-auto">Vacío = quitar la excepción</span>}
                            </div>
                        </>
                    ) : (
                        <div className="flex items-start justify-between gap-3">
                            <p className="text-white text-sm whitespace-pre-wrap">{excepcion}</p>
                            <button onClick={() => setEditando(true)} className="text-white/40 hover:text-white shrink-0" title="Editar la excepción">
                                <Pencil className="w-3.5 h-3.5" />
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

// METER EL REPORTE DE UN CLIENTE QUE LO MANDÓ POR OTRA VÍA (punto 45 del doc del 07-08).
//
// Los Premium no rellenan el formulario: mandan el reporte y las fotos por WhatsApp y alguien
// del equipo se lo pasa a la app. Hasta ahora eso solo se podía hacer entrando con la cuenta
// del cliente - "subiendo las fotos con el correo del cliente para que se enlacen a su ficha",
// dice el punto -, y lo que no se metía se perdía: ni curva de peso, ni comparativa, ni modelo.
//
// Va plegado porque no es lo normal: se abre cuando toca.
const ReportePorElCliente = ({ api, clientId, onHecho }) => {
    const [abierto, setAbierto] = useState(false);
    const [guardando, setGuardando] = useState(false);
    const [subiendo, setSubiendo] = useState(false);
    const [datos, setDatos] = useState({ weight: '', notes: '', proximo_objetivo: '', measurements: {} });
    const [fotos, setFotos] = useState([]);

    const guardar = async () => {
        const peso = parseFloat(datos.weight);
        if (isNaN(peso) || peso < 25 || peso > 300) { toast.error('Pon su peso (25-300 kg)'); return; }
        setGuardando(true);
        try {
            const medidas = Object.fromEntries(
                Object.entries(datos.measurements).filter(([, v]) => v !== '' && v != null)
                    .map(([k, v]) => [k, parseFloat(v)]));
            await api.post(`/admin/clients/${clientId}/reporte`, {
                weight: peso,
                measurements: Object.keys(medidas).length ? medidas : null,
                notes: datos.notes || null,
                proximo_objetivo: datos.proximo_objetivo || null,
            });
            toast.success('Reporte guardado', { description: 'Queda anotado que lo metiste tú.' });
            setDatos({ weight: '', notes: '', proximo_objetivo: '', measurements: {} });
            setFotos([]);
            setAbierto(false);
            onHecho?.();
        } catch (e) { toast.error(mensajeDeError(e, 'No se pudo guardar el reporte')); }
        finally { setGuardando(false); }
    };

    const subirFoto = async (archivo, pose) => {
        if (!archivo) return;
        setSubiendo(true);
        try {
            const fd = new FormData();
            fd.append('file', archivo);
            const r = await api.post(
                `/admin/clients/${clientId}/reports/photos?pose=${encodeURIComponent(pose || '')}`,
                fd, { headers: { 'Content-Type': 'multipart/form-data' } });
            setFotos(f => [...f, { ...r.data, pose }]);
            toast.success(`Foto subida${pose ? ` (${pose})` : ''}`);
        } catch (e) { toast.error(mensajeDeError(e, 'No se pudo subir la foto')); }
        finally { setSubiendo(false); }
    };

    if (!abierto) {
        return (
            <button onClick={() => setAbierto(true)} data-testid="abrir-reporte-por-el"
                className="text-xs text-white/40 hover:text-[#FF671F] flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5" /> Meter un reporte por él (llegó por WhatsApp)
            </button>
        );
    }

    return (
        <Card className="bg-[#111] border-[#FF671F]/30" data-testid="reporte-por-el-cliente">
            <CardContent className="p-5 space-y-3">
                <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-bold text-white/40 uppercase tracking-wider">Reporte en su nombre</p>
                    <button onClick={() => setAbierto(false)} className="text-white/30 hover:text-white"><X className="w-4 h-4" /></button>
                </div>
                <p className="text-[11px] text-white/30">
                    Para el que manda el reporte por WhatsApp. Se guarda como suyo y queda anotado que lo metiste tú.
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <Label className="text-white/60 text-xs">Peso (kg)</Label>
                        <Input type="number" step="0.1" min="25" max="300" value={datos.weight}
                            onChange={e => setDatos(d => ({ ...d, weight: e.target.value }))}
                            data-testid="reporte-peso" className="bg-[#0A0A0A] border-[#333] text-white mt-1" />
                    </div>
                    <div>
                        <Label className="text-white/60 text-xs">Objetivo que marca</Label>
                        <select value={datos.proximo_objetivo}
                            onChange={e => setDatos(d => ({ ...d, proximo_objetivo: e.target.value }))}
                            className="w-full bg-[#0A0A0A] border border-[#333] text-white text-sm rounded-lg px-2 py-2 mt-1">
                            <option value="">Sin cambio</option>
                            <option value="definicion">Definición</option>
                            <option value="volumen">Volumen</option>
                            <option value="mantenimiento">Mantenimiento</option>
                        </select>
                    </div>
                </div>

                {/* Las diez medidas, opcionales: en WhatsApp no siempre llegan todas. */}
                <details className="rounded-lg border border-[#222] bg-[#0A0A0A] p-3">
                    <summary className="text-xs text-white/50 cursor-pointer">Medidas (opcionales)</summary>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-3">
                        {MEDIDAS.map(({ key, label }) => (
                            <div key={key}>
                                <Label className="text-white/40 text-[10px]">{label}</Label>
                                <Input type="number" step="0.1" value={datos.measurements[key] ?? ''}
                                    onChange={e => setDatos(d => ({ ...d, measurements: { ...d.measurements, [key]: e.target.value } }))}
                                    className="bg-[#111] border-[#333] text-white text-xs h-8 mt-0.5" />
                            </div>
                        ))}
                    </div>
                </details>

                {/* Las fotos, con su pose: sin pose son tres fotos sueltas, con ella son la
                    misma foto de tres meses distintos y entran en la comparativa. */}
                <div className="rounded-lg border border-[#222] bg-[#0A0A0A] p-3">
                    <p className="text-xs text-white/50 mb-2">Fotos {subiendo && <Loader2 className="w-3 h-3 animate-spin inline ml-1" />}</p>
                    <div className="flex flex-wrap gap-2">
                        {['frente', 'espalda', 'perfil'].map(pose => (
                            <label key={pose} className="px-3 py-1.5 rounded-lg bg-[#111] border border-[#333] text-xs text-white/70 cursor-pointer hover:border-[#FF671F]/50">
                                <Camera className="w-3.5 h-3.5 inline mr-1" />{pose}
                                <input type="file" accept="image/*" className="hidden" data-testid={`foto-${pose}`}
                                    onChange={e => { subirFoto(e.target.files?.[0], pose); e.target.value = ''; }} />
                            </label>
                        ))}
                    </div>
                    {fotos.length > 0 && (
                        <p className="text-[11px] text-emerald-400 mt-2">
                            {fotos.length} {fotos.length === 1 ? 'foto subida' : 'fotos subidas'}: {fotos.map(f => f.pose).join(', ')}
                        </p>
                    )}
                </div>

                <div>
                    <Label className="text-white/60 text-xs">Lo que ha contado</Label>
                    <Textarea value={datos.notes} onChange={e => setDatos(d => ({ ...d, notes: e.target.value }))}
                        placeholder="Pega aquí lo que te ha escrito por WhatsApp…" rows={3}
                        data-testid="reporte-notas" className="bg-[#0A0A0A] border-[#333] text-white mt-1" />
                </div>

                <div className="flex justify-end">
                    <Button onClick={guardar} disabled={guardando} data-testid="guardar-reporte-por-el"
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white">
                        {guardando ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save className="w-4 h-4 mr-1" />Guardar el reporte</>}
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
};

const CAUSA_LABEL = { ajuste: 'fallo del ajuste', cliente: 'no cumplió', otro: 'otros motivos' };

// Respuestas de las tres preguntas del reporte (punto 5 del 05-08), en legible.
/**
 * QUÉ SE ENSEÑA EN «CRITERIO INTERNO» Y «FEEDBACK» CUANDO LA FILA NO LOS TRAE.
 *
 * Parte 7 del documento del 09-08: «Las columnas Criterio interno y Feedback del histórico
 * están vacías en las filas antiguas. Son justo lo que convierte un histórico de números en
 * un histórico de decisiones. Hay que decidir qué se enseña ahí.»
 *
 * Decidido: en vez de un guion, POR QUÉ está vacía. No todas las filas son una decisión del
 * coach. Las hay importadas de Calma, calculadas por un cuestionario o cambiadas por el
 * propio cliente desde su calculadora, y esas no tienen criterio que enseñar ni feedback que
 * mandar: el hueco no es un olvido, es que ahí no decidió nadie. Es la misma distinción que
 * ya hace el agente al leer el historial (`NO_ES_DEL_COACH` en `macro_agent.py`), que hasta
 * ahora solo existía del lado del modelo y no se veía en pantalla.
 *
 * Las filas que SÍ son del coach y están vacías se quedan con el guion: ahí el hueco sí es
 * un olvido y tiene que seguir viéndose como tal.
 */
const _ORIGEN_SIN_CRITERIO = {
    quiz_alta: 'lo calculó el cuestionario de alta',
    quiz_ajuste: 'lo recalculó el cliente con el cuestionario',
    cliente_calculadora: 'lo cambió el cliente desde su calculadora',
    revision_suelta: 'revisión suelta del cliente',
};
const _huecoExplicado = (h) => {
    if (h?.calma_migrated || h?.changed_by === 'migracion') return 'importado de Calma';
    return _ORIGEN_SIN_CRITERIO[h?.origen] || null;
};
const CeldaHistorial = ({ texto, hueco, testid }) => (
    <td className="px-2 py-2 text-white/50 text-xs max-w-[200px]" data-testid={testid}>
        {texto
            ? <span className="block truncate" title={texto}>{texto}</span>
            : hueco
                ? <span className="block truncate italic text-white/25" title={hueco}>{hueco}</span>
                : <span className="text-white/30">-</span>}
    </td>
);

const OBJETIVO_REPORTE = { definicion: 'Definición', volumen: 'Volumen', mantenimiento: 'Mantenimiento' };
const VIABILIDAD_REPORTE = {
    me_adapto: 'se adapta a lo que le pongas',
    necesito_mas: 'necesita comer MÁS para cumplir',
    necesito_menos: 'necesita comer MENOS para cumplir',
};
const ENTRENO_REPORTE = {
    todos: 'todos', casi_todos: 'casi todos', la_mitad: 'la mitad', pocos: 'pocos', ninguno: 'ninguno',
};

/**
 * EL REPORTE CON EL QUE SE AJUSTA, en la misma pestaña en la que se ajusta.
 *
 * Parte 7 del documento del 09-08: «para decidir un ajuste tiene que ir a cuatro pestañas:
 * reporte, peso, fotos y macros. Cuatro idas y venidas para una decisión de treinta
 * segundos. Con 20 clientes, 80 cada lunes.»
 *
 * Tres de las cuatro ya vivían aquí: la escalera (`MacroHistoryTable`), las fotos
 * (`MuralFotos`) y el peso con su variación (dentro del editor). La que faltaba era esta,
 * y es la que abre la decisión: lo que el cliente contestó. Va arriba del todo porque es
 * lo primero que se lee, y va ENTERA -- no un resumen -- para que no haya que abrir el
 * reporte en Seguimiento a comprobar nada.
 *
 * No sustituye a la pestaña de Seguimiento: ahí está el histórico y el feedback de cada
 * reporte. Aquí está el último, que es el único que se usa para ajustar.
 */
const ReporteParaDecidir = ({ reporte, reportes, pesoUltimoAjuste, onVerReportes }) => {
    if (!reporte) return (
        <Card className="bg-[#111] border-[#222]"><CardContent className="p-4">
            <p className="text-white/40 text-sm" data-testid="decidir-sin-reporte">
                Sin reportes todavía: el ajuste va con el peso de la ficha y sin nada de lo que
                el cliente contesta.
            </p>
        </CardContent></Card>
    );

    const fecha = String(reporte.created_at).slice(0, 10);
    // Aquí los días se dicen SIEMPRE, también pasado el mes. `_haceCuanto` se cae a la fecha
    // a los 30 días, y en esta pantalla el dato que decide es justo ese: con qué antigüedad
    // se está ajustando. Un reporte de hace 40 días no es «del 06/07», es viejo.
    const dias = Math.floor((new Date().setHours(0, 0, 0, 0) - new Date(fecha + 'T00:00:00').getTime()) / 86400000);
    const cuando = isNaN(dias) ? '' : dias <= 0 ? 'hoy' : dias === 1 ? 'ayer' : `hace ${dias} días`;
    const viejo = dias >= 30;
    // El texto que dejó la migración no es lo que escribió el cliente: en el histórico ya se
    // filtra igual, y enseñarlo entrecomillado como una nota suya sería mentir.
    const notas = reporte.notes && reporte.notes !== 'Importado de Calma' ? reporte.notes : '';
    const importado = !!(reporte.calma_migrated || reporte.notes === 'Importado de Calma');
    const dif = (pesoUltimoAjuste != null && reporte.weight != null)
        ? Math.round((reporte.weight - pesoUltimoAjuste) * 10) / 10
        : null;
    // Las medidas se leen contra las del reporte anterior QUE TRAIGA MEDIDAS, no contra el
    // reporte de antes sin más: no se piden todos los meses y comparar con un hueco daría
    // una diferencia inventada.
    const medidas = reporte.measurements || null;
    const previoConMedidas = (reportes || [])
        .filter(r => r.id !== reporte.id && r.measurements && String(r.created_at) < String(reporte.created_at))
        .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))[0] || null;
    // Se lee con `valorAnterior`, que además de la medida por su nombre entiende los dos
    // nombres viejos (cintura/cadera). Y lo que quede fuera de las diez -- pecho, brazo y
    // muslo de los reportes de antes -- se pinta igual con su nombre: son medidas que el
    // cliente mandó, y descartarlas en silencio es peor que enseñarlas etiquetadas.
    const _VIEJAS = { chest: 'Pecho (medida antigua)', arm: 'Brazo (medida antigua)', thigh: 'Muslo (medida antigua)' };
    const _DE_LAS_DIEZ = new Set([...MEDIDAS.map(m => m.key), 'waist', 'hip']);
    const filasMedidas = medidas ? [
        ...MEDIDAS
            .map(m => ({ key: m.key, label: m.label, valor: valorAnterior(medidas, m.key) }))
            .filter(f => f.valor != null),
        ...Object.entries(medidas)
            .filter(([k, v]) => v != null && v !== '' && !_DE_LAS_DIEZ.has(k))
            .map(([k, v]) => ({ key: k, label: _VIEJAS[k] || k, valor: Number(v) })),
    ] : [];
    const rangos = [
        ['Sueño', reporte.sleep_quality],
        ['Energía', reporte.energy_level],
        ['Estrés', reporte.stress_level],
    ].filter(([, v]) => v != null);

    return (
        <Card className="bg-[#111] border-[#222] text-white" data-testid="decidir-reporte">
            <CardHeader className="pb-2">
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                    <CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2">
                        <FileText className="w-4 h-4" />Su último reporte
                    </CardTitle>
                    <div className="flex items-center gap-3">
                        {importado && <CalmaBadge />}
                        <span className={`text-[11px] ${viejo ? 'text-amber-500' : 'text-white/30'}`} data-testid="decidir-fecha">
                            {_fechaCorta(fecha)} · {cuando}
                        </span>
                        {onVerReportes && (
                            <button onClick={onVerReportes} className="text-[#FF671F] text-[11px] hover:underline"
                                data-testid="decidir-ver-reportes">Ver todos</button>
                        )}
                    </div>
                </div>
            </CardHeader>
            <CardContent className="space-y-3">
                {/* El peso y su variación: el número con el que arranca la decisión. */}
                <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                    <span className="text-2xl font-bold text-[#FF671F] tabular-nums">{String(reporte.weight).replace('.', ',')} kg</span>
                    {dif != null && (
                        <span className="text-sm tabular-nums" data-testid="decidir-variacion">
                            <span className={dif > 0 ? 'text-red-400' : dif < 0 ? 'text-emerald-400' : 'text-white/50'}>
                                {dif === 0 ? 'sin cambios' : `${dif > 0 ? '+' : ''}${String(dif).replace('.', ',')} kg`}
                            </span>
                            <span className="text-white/30"> desde los últimos macros ({String(pesoUltimoAjuste).replace('.', ',')} kg)</span>
                        </span>
                    )}
                </div>

                {/* Lo que contestó. Las tres preguntas nuevas primero: son las que mueven el
                    ajuste. Los porcentajes y los rangos van detrás, que son contexto. */}
                {(reporte.proximo_objetivo || reporte.viabilidad_ajuste || reporte.cumplimiento_entreno) && (
                    <div className="space-y-1 text-sm bg-[#0A0A0A] rounded-lg p-3 border border-[#222]">
                        {reporte.proximo_objetivo && (
                            <p className="text-white/50">Próximo objetivo{' '}
                                <b className="text-[#FF671F] uppercase">{OBJETIVO_REPORTE[reporte.proximo_objetivo] || reporte.proximo_objetivo}</b></p>
                        )}
                        {reporte.viabilidad_ajuste && (
                            <p className="text-white/50">Margen para ajustar{' '}
                                <b className="text-white">{VIABILIDAD_REPORTE[reporte.viabilidad_ajuste] || reporte.viabilidad_ajuste}</b></p>
                        )}
                        {reporte.cumplimiento_entreno && (
                            <p className="text-white/50">Entrenamientos{' '}
                                <b className="text-white">{ENTRENO_REPORTE[reporte.cumplimiento_entreno] || reporte.cumplimiento_entreno}</b></p>
                        )}
                    </div>
                )}

                {(reporte.training_compliance != null || reporte.nutrition_compliance != null || rangos.length > 0) && (
                    <div className="flex flex-wrap gap-2">
                        {reporte.training_compliance != null && <MiniStat label="Entreno" value={`${reporte.training_compliance}%`} />}
                        {reporte.nutrition_compliance != null && <MiniStat label="Nutrición" value={`${reporte.nutrition_compliance}%`} />}
                        {rangos.map(([l, v]) => <MiniStat key={l} label={l} value={`${v}/10`} />)}
                    </div>
                )}

                {/* Las medidas, con la diferencia contra el último reporte que las traiga.
                    Plegadas: son diez y no siempre se leen, pero cuando se leen se leen aquí
                    y no en otra pestaña. */}
                {filasMedidas.length > 0 && (
                    <details className="group">
                        <summary className="cursor-pointer text-white/40 text-xs hover:text-white/70 select-none">
                            Medidas del reporte ({filasMedidas.length})
                            {previoConMedidas && <span className="text-white/25"> · contra las del {_fechaCorta(String(previoConMedidas.created_at).slice(0, 10))}</span>}
                        </summary>
                        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 mt-2">
                            {filasMedidas.map(m => {
                                const prev = previoConMedidas?.measurements;
                                const antes = prev ? (valorAnterior(prev, m.key) ?? (prev[m.key] != null ? Number(prev[m.key]) : null)) : null;
                                const d = diferencia(m.valor, antes);
                                return (
                                    <div key={m.key} className="bg-[#0A0A0A] rounded p-2 border border-[#222]">
                                        <p className="text-white/40 text-[10px] uppercase truncate" title={m.label}>{m.label}</p>
                                        <p className="text-white text-sm font-bold tabular-nums">
                                            {String(m.valor).replace('.', ',')}
                                            {d && <span className={`ml-1 text-xs font-normal ${d.signo > 0 ? 'text-red-400' : d.signo < 0 ? 'text-emerald-400' : 'text-white/40'}`}>{d.texto}</span>}
                                        </p>
                                    </div>
                                );
                            })}
                        </div>
                    </details>
                )}

                {notas && (
                    <p className="text-white/70 text-sm italic border-l-2 border-[#333] pl-3" data-testid="decidir-notas">"{notas}"</p>
                )}
            </CardContent>
        </Card>
    );
};

const EvaluacionBadge = ({ ev }) => (
    <span className={`text-xs font-semibold ${ev.resultado === 'buena' ? 'text-emerald-400' : 'text-red-400'}`}
        title={[ev.resultado === 'buena' ? 'Fase buena' : 'Fase mala', CAUSA_LABEL[ev.causa], ev.nota].filter(Boolean).join(' · ')}>
        {ev.resultado === 'buena' ? 'Buena' : 'Mala'}
        {ev.causa && <span className="text-white/40 font-normal"> · {CAUSA_LABEL[ev.causa]}</span>}
    </span>
);

// Historial de macros en tabla, con filtro por rango de fechas.
const MacroHistoryTable = ({ items, onEdit, onRepeat, onDelete, onEvaluar, borrador }) => {
    const [desde, setDesde] = useState('');
    const [hasta, setHasta] = useState('');
    // El ajuste que se está escribiendo abajo entra como una fila más, en gris, en el sitio
    // que le toca por fecha: así se ve cómo queda la escalera ANTES de guardar.
    const todas = useMemo(
        () => [...(items || []), ...(borrador ? [borrador] : [])]
            .sort((a, b) => _fechaEntrada(b).localeCompare(_fechaEntrada(a))),
        [items, borrador]);
    // Peso máximo y mínimo del recorrido. Se marca UNA sola fila de cada: con 170 ajustes
    // hay empates de sobra y pintar quince "máximos" no señala nada.
    const { filaMax, filaMin } = useMemo(() => {
        let max = null, min = null;
        for (const h of (items || [])) {
            const p = h.peso ?? h.client_weight;
            if (typeof p !== 'number') continue;
            if (!max || p > (max.peso ?? max.client_weight)) max = h;
            if (!min || p < (min.peso ?? min.client_weight)) min = h;
        }
        return { filaMax: max, filaMin: min };
    }, [items]);
    const filas = useMemo(() => todas.filter(h => {
        const f = _fechaEntrada(h);
        return !((desde && f < desde) || (hasta && f > hasta));
    }), [todas, desde, hasta]);
    // La tabla va arriba para poder comparar antes de ajustar, pero un cliente con 170
    // ajustes dejaría el editor a media pantalla de scroll. Por defecto se ven los últimos
    // (que es con los que se compara) y el resto se despliega, como el "ocultar macros" de Calma.
    const [verTodo, setVerTodo] = useState(false);
    const RECIENTES = 12;
    const visibles = useMemo(() => {
        if (verTodo) return filas;
        const corte = filas.slice(0, RECIENTES);
        // El ajuste en curso se ve SIEMPRE, aunque su fecha lo mande fuera del recorte:
        // si el coach lo pone vigente desde una fecha vieja, la fila no puede desaparecer.
        const b = filas.find(h => h._borrador);
        return (!b || corte.includes(b)) ? corte
            : [...corte, b].sort((x, y) => _fechaEntrada(y).localeCompare(_fechaEntrada(x)));
    }, [filas, verTodo]);
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
                        {/* El ajuste en curso no cuenta como cambio: todavía no está guardado */}
                        <span className="text-white/30 text-[11px] tabular-nums">{filtrando ? `${filas.length} de ${(items || []).length}` : `${(items || []).length} cambios`}</span>
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
                                {visibles.map((h, i) => {
                                    const peso = h.peso ?? h.client_weight;
                                    const peri = h.peri || h.macros_periworkout;
                                    const nota = h.note && h.note !== 'Importado de Calma' ? h.note : '';
                                    // El ajuste inmediatamente ANTERIOR en el tiempo (la tabla va de más
                                    // reciente a más antigua, así que es el siguiente de la lista). Se busca
                                    // en `filas`, no en las visibles: si no, la última fila a la vista no
                                    // tendría con qué compararse y parecería que no cambió nada.
                                    const ant = filas[filas.indexOf(h) + 1];
                                    const antPeri = ant && (ant.peri || ant.macros_periworkout);
                                    const esBorrador = !!h._borrador;
                                    const esMax = h === filaMax, esMin = h === filaMin;
                                    const tonoPeso = esMax ? 'bg-red-500/20 text-red-300'
                                        : esMin ? 'bg-emerald-500/20 text-emerald-300'
                                        : 'text-[#FF671F]';
                                    return (
                                        <tr key={h.id || i} data-testid={esBorrador ? 'macro-fila-borrador' : undefined}
                                            className={`border-b border-[#1a1a1a] last:border-0 ${
                                                esBorrador ? 'bg-white/[0.06] border-dashed border-[#FF671F]/40' : 'hover:bg-white/[0.03]'}`}>
                                            <td className="px-2 py-2 whitespace-nowrap font-medium tabular-nums">
                                                <span className={esBorrador ? 'text-white/50' : ''}>{_fechaCorta(_fechaEntrada(h))}</span>
                                                {esBorrador && <span className="ml-1.5 text-[9px] uppercase text-[#FF671F]">sin guardar</span>}
                                                {h.origen === 'ia' && <span className="ml-1.5 text-[9px] uppercase text-[#FF671F]" title="Propuesta de la IA aceptada tal cual">IA</span>}
                                                {h.origen === 'ia_corregida' && <span className="ml-1.5 text-[9px] uppercase text-amber-500" title={`Propuesta de la IA corregida por el entrenador: ${JSON.stringify(h.correccion_coach || {})}`}>IA·corr</span>}
                                            </td>
                                            <td className="px-2 py-2 text-right whitespace-nowrap tabular-nums">
                                                <span className={`font-bold rounded px-1 ${esBorrador ? 'text-white/40' : tonoPeso}`}
                                                    title={esMax ? 'Peso máximo del recorrido' : esMin ? 'Peso mínimo del recorrido' : undefined}>
                                                    {peso != null ? `${peso} kg` : '-'}
                                                </span>
                                                {h.body_fat != null && <span className="text-white/40 text-xs"> · {h.body_fat}%</span>}
                                            </td>
                                            <MacroCeldas m={h.training} prev={ant?.training} apagado={esBorrador} cambios={h.cambios?.entreno} />
                                            <MacroCeldas m={peri} prev={antPeri} showG={false} apagado={esBorrador} cambios={h.cambios?.perientreno} />
                                            <MacroCeldas m={h.rest} prev={ant?.rest} apagado={esBorrador} cambios={h.cambios?.descanso} />
                                            <CeldaHistorial texto={h.criterio} hueco={_huecoExplicado(h)} testid="hist-criterio" />
                                            <CeldaHistorial texto={nota} hueco={_huecoExplicado(h)} testid="hist-feedback" />
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
                                                    {/* La fila en curso todavía no existe: no se puede repetir, editar ni borrar */}
                                                    {!esBorrador && (
                                                        <div className="flex items-center justify-end gap-0.5">
                                                            {onRepeat && <button onClick={() => onRepeat(h)} title="Repetir estos macros (aplicar hoy)" className="p-1 rounded text-white/40 hover:text-[#FF671F] hover:bg-[#FF671F]/10"><RotateCcw className="w-3.5 h-3.5" /></button>}
                                                            {onEdit && <button onClick={() => onEdit(h)} title="Editar esta entrada" className="p-1 rounded text-white/40 hover:text-white hover:bg-white/10"><Pencil className="w-3.5 h-3.5" /></button>}
                                                            {onDelete && <button onClick={() => onDelete(h)} title="Eliminar esta entrada" className="p-1 rounded text-white/40 hover:text-red-400 hover:bg-red-500/10"><Trash2 className="w-3.5 h-3.5" /></button>}
                                                        </div>
                                                    )}
                                                </td>
                                            )}
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                        {filas.length > RECIENTES && (
                            <button onClick={() => setVerTodo(!verTodo)} data-testid="macro-hist-ver-todo"
                                className="w-full mt-2 py-2 text-xs font-semibold text-white/50 hover:text-[#FF671F] transition-colors">
                                {verTodo ? `Ver solo los ${RECIENTES} últimos` : `Ver el historial entero (${filas.length} ajustes)`}
                            </button>
                        )}
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

/**
 * El cuestionario largo del cliente (perfil.nivel1), agrupado como en el documento.
 *
 * Existe porque no existía: el cliente contestaba las treinta preguntas -- su historia,
 * su salud, con qué entrena, qué suplementos toma -- y no se pintaban en ninguna parte de
 * la ficha. Se le vendía "tu coach usará todo esto para tu estrategia" y el coach no
 * tenía dónde leerlo.
 *
 * Se pinta lo que HAY: si un bloque está vacío no se enseña, para que no parezca que el
 * cliente dejó cosas sin contestar cuando lo que pasa es que no se le preguntaron.
 */
const ETIQUETAS_NIVEL1 = {
    // Tu historia
    peso_maximo: 'Peso máximo', peso_maximo_cuando: '¿Cuándo?',
    peso_minimo: 'Peso mínimo', peso_habitual: 'Peso habitual',
    peso_mejor_momento: 'Peso en su mejor momento',
    mejor_definicion_cuando: 'Mejor punto de definición',
    hasta_donde: 'Hasta dónde quiere llegar',
    vario_peso_3m: '¿Ha variado su peso en 3 meses?',
    tiempo_intentandolo: 'Tiempo intentándolo',
    motivo_apuntarse: 'Por qué se apuntó',
    dietas_previas: 'Dietas que ha hecho',
    dieta_que_funciona: 'La que mejor le funcionó',
    por_que_fallaron: 'Por qué fallaron',
    entrenador_anterior: 'Entrenador anterior',
    // Tu entrenamiento
    training_experience: 'Años entrenando',
    entrena_ahora: '¿Entrena ahora?',
    material: 'Material',
    maquinas_que_faltan: 'Máquinas que le faltan',
    ejercicios_imposibles: 'Ejercicios que no puede hacer',
    cardio: 'Cardio',
    dias_entreno: 'Días de entreno',
    // Tu salud
    trt: 'TRT', farmacologia_uso: 'Farmacología',
    zona_grasa: 'Dónde acumula grasa',
    // Tu suplementación
    suplementos_ahora: 'Toma ahora',
    suplementos_antes: 'Ha tomado antes',
    quiere_pauta_suplementos: '¿Quiere que le pauten?',
    // Tu comida
    cocina_o_rapido: '¿Cocina o quiere rápido?',
    conserva_o_fresco: '¿Conserva o fresco?',
    come_fuera: '¿Come fuera?',
    que_le_apetece: 'Qué le apetece en cada comida',
    favoritos_y_no_gustos: 'Favoritos y no-gustos',
    plato_imprescindible: 'Plato imprescindible',
    lactosa: 'Lactosa',
    gluten: 'Gluten',
    alergias: 'Otras alergias',
    num_comidas: 'Comidas al día',
    // Otros
    biotype: 'Biotipo', height: 'Altura', birthdate: 'Fecha de nacimiento',
};

const BLOQUES_NIVEL1 = [
    ['Su historia', ['peso_maximo', 'peso_maximo_cuando', 'peso_minimo', 'peso_habitual',
                     'peso_mejor_momento', 'mejor_definicion_cuando', 'hasta_donde',
                     'vario_peso_3m', 'tiempo_intentandolo', 'motivo_apuntarse',
                     'dietas_previas', 'dieta_que_funciona', 'por_que_fallaron',
                     'entrenador_anterior']],
    ['Su entrenamiento', ['training_experience', 'entrena_ahora', 'material',
                          'maquinas_que_faltan', 'ejercicios_imposibles', 'cardio',
                          'dias_entreno']],
    ['Su salud', ['trt', 'farmacologia_uso', 'zona_grasa']],
    ['Su suplementación', ['suplementos_ahora', 'suplementos_antes', 'quiere_pauta_suplementos']],
    ['Su comida', ['cocina_o_rapido', 'conserva_o_fresco', 'come_fuera', 'que_le_apetece',
                   'favoritos_y_no_gustos', 'plato_imprescindible', 'lactosa', 'gluten',
                   'alergias', 'num_comidas']],
];

// Los valores se guardan en clave ('3_10', 'irregular'); el coach lee castellano.
const VALORES_NIVEL1 = {
    menos_1: 'Menos de 1 año', '1_3': 'Entre 1 y 3 años', '3_10': 'Entre 3 y 10 años',
    mas_10: 'Más de 10 años', parado: 'Entrenó antes, lleva tiempo parado',
    si: 'Sí', no: 'No', antes: 'Antes sí, ahora no',
    irregular: 'Va, pero de forma irregular',
    uso: 'Sí, ahora mismo', use: 'Ha usado antes, ahora no',
    intencion: 'No, pero tiene intención', nunca: 'No, ni se lo plantea',
    lo_justo: 'Solo lo imprescindible',
    // Su comida
    cocinar: 'Le gusta cocinar y tiene tiempo', normal: 'Cocina lo justo',
    rapido: 'Cuanto más rápido, mejor',
    conserva: 'La conserva le facilita la vida', ambos: 'Le da igual', fresco: 'Lo prefiere fresco',
    '1_2': '1 o 2 días por semana', '3_4': '3 o 4 días', casi_todos: 'Casi todos los días',
    // Intolerancias
    bien: 'Sin problema', tolera_algo: 'Tolera yogur y queso curado', nada: 'Nada de lactosa',
    sensibilidad: 'Sensibilidad, no celiaquía', celiaquia: 'Celiaquía diagnosticada',
};

/**
 * LO QUE CONTESTÓ Y MUEVE SUS MACROS (punto 17 del doc del 07-08).
 *
 * La pestaña Cuestionario enseñaba seis campos -- objetivo, peso, sexo, % graso, edad y
 * altura -- y el cuestionario largo. Faltaba justo lo que decide los números: cuánto se
 * mueve al día, si hace otro deporte, si engorda con facilidad, qué dieta trae y cómo le
 * está funcionando. Eso vive en `ajustes_macros`, se guarda desde el 06-08 y no se pintaba
 * en ningún sitio: el coach ajustaba a ciegas sobre unas respuestas que no podía leer.
 *
 * `como_va` es la que más pesa -- sitúa lo que come respecto a su mantenimiento -- y va la
 * primera a propósito.
 */
const ETIQUETAS_AJUSTES = {
    como_va: 'Cómo le va',
    sigue_dieta: '¿Sigue una dieta?',
    tiempo_dieta: 'Cuánto lleva con ella',
    hambre_saturacion: 'Hambre / saturación',
    actividad_diaria: 'Actividad diaria',
    deporte_extra: 'Otro deporte además de pesas',
    facilidad_engordar: 'Engorda al pasarse',
    dieta_hc_entreno: 'HC del día de entreno (g)',
    dieta_grasa_entreno: 'Grasa aprox. (g)',
    dieta_texto: 'Su día tipo, tal cual lo escribió',
};

// Los valores se guardan en clave; el coach lee castellano. Los textos son los mismos que
// ve el cliente al contestar, para que no haya dos vocabularios para lo mismo.
const VALORES_AJUSTES = {
    // sigue_dieta -- las cuatro del punto 19
    true: 'Estricta, mide todo lo que come', parecido: 'No pesa, pero se cuida bastante',
    false: 'Sin control, pero no come mal', desorganizado: 'Come mal y desorganizado',
    // como_va
    bien: 'Bien, va a buen ritmo', lento: 'Va, pero muy lento',
    mucha_grasa: 'Sube, pero coge más grasa de la cuenta',
    mantengo: 'Se mantiene igual', bajando: 'Mal: en vez de subir, baja',
    cogiendo_peso: 'Mal: está cogiendo peso',
    // actividad_diaria / facilidad_engordar / hambre / tiempo
    sedentario: 'Sedentario', normal: 'Normal', muy_activo: 'Muy activo',
    enseguida: 'Enseguida', casi_no: 'Casi no',
    mucho: 'Mucha hambre', aguanto_mas: 'Ninguna: aguanta más',
    no_puedo_mas: 'No saturado, pero no puede comer más', puedo_mas: 'Puede comer más sin problema',
    menos_1m: 'Menos de un mes', '1_3m': 'Entre 1 y 3 meses',
    '3_6m': 'Entre 3 y 6 meses', mas_6m: 'Más de 6 meses',
};

const AjustesDelCuestionario = ({ ajustes }) => {
    const filas = Object.keys(ETIQUETAS_AJUSTES)
        .map(k => {
            const v = ajustes?.[k];
            if (v == null || v === '') return null;
            const texto = typeof v === 'boolean' ? (VALORES_AJUSTES[String(v)] || (v ? 'Sí' : 'No'))
                : (VALORES_AJUSTES[v] || String(v));
            return [k, ETIQUETAS_AJUSTES[k], texto];
        })
        .filter(Boolean);
    if (!filas.length) return null;

    return (
        <Card className="bg-[#111] border-[#222]" data-testid="ajustes-del-cuestionario">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2">
                    <SlidersHorizontal className="w-4 h-4" />Lo que contestó y mueve sus macros
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
                {filas.map(([k, etiqueta, texto]) => (
                    <div key={k} className="grid grid-cols-[minmax(0,13rem)_1fr] gap-3 text-sm">
                        <span className="text-white/40">{etiqueta}</span>
                        <span className="text-white/90 whitespace-pre-wrap break-words">{texto}</span>
                    </div>
                ))}
            </CardContent>
        </Card>
    );
};

const PerfilLargo = ({ nivel1 }) => {
    if (!nivel1 || !Object.keys(nivel1).length) return null;

    const valor = (v) => {
        if (v == null || v === '') return null;
        if (Array.isArray(v)) return v.length ? v.map(equipamientoLabel).join(' · ') : null;
        return VALORES_NIVEL1[v] || String(v);
    };

    const salud = nivel1.salud || {};
    const hayAlgoDeSalud = Object.values(salud).some(v => v);

    return (
        <Card className="bg-[#111] border-[#222]" data-testid="perfil-largo">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2">
                    <ClipboardList className="w-4 h-4" />Cuestionario completo
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
                {BLOQUES_NIVEL1.map(([titulo, claves]) => {
                    const filas = claves
                        .map(k => [ETIQUETAS_NIVEL1[k] || k, valor(nivel1[k])])
                        .filter(([, v]) => v);
                    if (!filas.length) return null;
                    return (
                        <div key={titulo}>
                            <p className="text-xs text-[#FF671F] uppercase tracking-wider font-bold mb-2">{titulo}</p>
                            <div className="space-y-2">
                                {filas.map(([etiqueta, v]) => (
                                    <div key={etiqueta} className="grid grid-cols-[minmax(0,11rem)_1fr] gap-3 text-sm">
                                        <span className="text-white/40">{etiqueta}</span>
                                        <span className="text-white/90 whitespace-pre-wrap break-words">{v}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    );
                })}

                {hayAlgoDeSalud && (
                    <div>
                        <p className="text-xs text-[#FF671F] uppercase tracking-wider font-bold mb-2">Sueño, estrés y lesiones</p>
                        <div className="space-y-2">
                            {[['sueno', 'Sueño'], ['estres', 'Estrés'], ['medicacion', 'Medicación'],
                              ['hormonal', 'Hormonal'], ['lesiones', 'Lesiones']]
                                .filter(([k]) => salud[k])
                                .map(([k, etiqueta]) => (
                                    <div key={k} className="grid grid-cols-[minmax(0,11rem)_1fr] gap-3 text-sm">
                                        <span className="text-white/40">{etiqueta}</span>
                                        <span className="text-white/90 whitespace-pre-wrap break-words">{String(salud[k])}</span>
                                    </div>
                                ))}
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
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

// Cache de miniaturas por foto. La misma foto la piden ahora varios sitios de la ficha
// (la comparativa, el mural de la pestaña de macros, la línea temporal y el comparador),
// y sin esto se pedían 108 veces para 49 fotos: el navegador encolaba y no se pintaba
// ninguna. Con la caché, cada foto se descarga UNA vez y la comparten todos.
const _thumbs = new Map();   // clave -> Promise<objectURL>

// Y con la cola de descargas limitada. El navegador solo abre 6 conexiones por host: al
// abrir la ficha se piden decenas de fotos de golpe y CUALQUIER otra llamada (guardar el
// % graso, los macros...) se queda en cola detrás de todas ellas, sin salir ni fallar.
// Con tres a la vez, las fotos siguen entrando rápido y el resto de la ficha responde.
const _MAX_EN_VUELO = 3;
let _enVuelo = 0;
const _cola = [];
const _tirarDeLaCola = () => {
    if (_enVuelo >= _MAX_EN_VUELO || !_cola.length) return;
    const { fn, ok, ko } = _cola.shift();
    _enVuelo++;
    fn().then(ok, ko).finally(() => { _enVuelo--; _tirarDeLaCola(); });
};
const _encolar = (fn) => new Promise((ok, ko) => { _cola.push({ fn, ok, ko }); _tirarDeLaCola(); });

const _thumb = (clave, descargar) => {
    if (!_thumbs.has(clave)) {
        _thumbs.set(clave, _encolar(descargar)
            .then(blob => URL.createObjectURL(blob))
            .catch(e => { _thumbs.delete(clave); throw e; }));   // si falla, se puede reintentar
    }
    return _thumbs.get(clave);
};

// Foto subida desde la app (client_photos) como miniatura; abre la original al hacer clic.
const AppFoto = ({ api, foto }) => {
    const [thumb, setThumb] = useState(null);
    useEffect(() => {
        let alive = true;
        _thumb(`app:${foto.id}`, () => api.get(`/reports/photos/${foto.id}`, { responseType: 'blob' }).then(r => r.data))
            .then(url => { if (alive) setThumb(url); })
            .catch(() => {});
        // El objectURL lo comparte la caché: no se revoca al desmontar, o la siguiente
        // pantalla que pida esa foto se quedaría con una imagen rota.
        return () => { alive = false; };
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
            // Siempre en el mismo orden -- frontal, lateral, espalda -- en los dos orígenes.
            // Las de la app se quedaban sin ordenar, así que dentro de un mes salían por
            // fecha de subida: una espalda, un frente, otra espalda.
            m.cal.sort((a, b) => _POSE_ORDER.indexOf(_poseDeKind(a.kind)) - _POSE_ORDER.indexOf(_poseDeKind(b.kind)));
            m.app.sort((a, b) => _POSE_ORDER.indexOf(_poseDeFoto(a)) - _POSE_ORDER.indexOf(_poseDeFoto(b)));
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

// La pose de una foto subida desde la app. El backend la guarda en `pose` desde el 06-08
// ('frente' | 'espalda' | 'perfil') y aquí se ignoraba: todas entraban como "Sin
// clasificar", así que la comparativa no podía poner una espalda debajo de otra espalda,
// que es lo único que se puede comparar. Se pasa por el mismo mapeo que las de Calma
// porque las palabras coinciden.
// Sin pose se queda en "Sin clasificar" a propósito: las que ya estaban subidas no la
// tienen (las 180 de producción), y meterlas en "Otras" las colaría por delante.
const _poseDeFoto = (p) => (p?.pose ? _poseDeKind(p.pose) : 'Sin clasificar');

const _mesKey = (fecha) => (fecha || '').slice(0, 7);  // YYYY-MM
const _mesLabel = (key) => {
    const [y, m] = key.split('-');
    const dt = new Date(+y, +m - 1, 1);
    return isNaN(dt) ? key : dt.toLocaleDateString('es-ES', { month: 'long', year: 'numeric' });
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

// MURAL DE FOTOS para la pantalla donde el coach ajusta (punto 3.1 del documento del
// 05-08): "yo las veo todas de golpe, y así las quiero; no me montes aquí un comparador".
// Una fila por día con fotos, con la fecha y el peso de ese día, de lo más reciente a lo
// más antiguo. El comparador de dos sigue existiendo en Seguimiento, que es otra cosa
// (la del cliente en su informe, punto 3.2).
const MuralFotos = ({ api, clientId, calmaFotos, reports, macroHistory }) => {
    const [appFotos, setAppFotos] = useState([]);
    const [verTodas, setVerTodas] = useState(false);
    const [abierto, setAbierto] = useState(true);

    useEffect(() => {
        let alive = true;
        api.get(`/admin/clients/${clientId}/photos`)
            .then(r => { if (alive) setAppFotos(r.data?.photos || []); })
            .catch(() => {});
        return () => { alive = false; };
    }, [api, clientId]);

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

    // Todas las fotos (Calma + app) agrupadas por día, del más reciente al más antiguo.
    const sesiones = useMemo(() => {
        const todas = [
            ...(calmaFotos || []).map(f => ({ key: `calma:${f.file}`, source: 'calma', file: f.file, date: f.fecha || '', pose: _poseDeKind(f.kind) })),
            ...(appFotos || []).map(p => ({ key: `app:${p.id}`, source: 'app', foto: p, date: (p.taken_at || p.uploaded_at || '').slice(0, 10), pose: _poseDeFoto(p) })),
        ].filter(f => f.date);
        const porDia = new Map();
        for (const f of todas) {
            if (!porDia.has(f.date)) porDia.set(f.date, []);
            porDia.get(f.date).push(f);
        }
        return [...porDia.entries()]
            .sort((a, b) => b[0].localeCompare(a[0]))
            .map(([date, fotos]) => ({
                date,
                peso: _pesoCercano(pesos, date),
                fotos: fotos.sort((a, b) => _POSE_ORDER.indexOf(a.pose) - _POSE_ORDER.indexOf(b.pose)),
            }));
    }, [calmaFotos, appFotos, pesos]);

    if (!sesiones.length) return null;
    const visibles = verTodas ? sesiones : sesiones.slice(0, 3);
    const totalFotos = sesiones.reduce((n, s) => n + s.fotos.length, 0);

    return (
        <Card className="bg-[#111] border-[#222]">
            <CardHeader className="pb-2">
                <button onClick={() => setAbierto(!abierto)} className="flex items-center justify-between w-full gap-2">
                    <CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2">
                        <Camera className="w-4 h-4 text-[#FF671F]" />Fotos ({totalFotos})
                    </CardTitle>
                    <span className="text-white/30 text-xs">{abierto ? 'ocultar' : 'ver'}</span>
                </button>
            </CardHeader>
            {abierto && (
                <CardContent className="space-y-4" data-testid="mural-fotos">
                    {visibles.map(s => (
                        <div key={s.date}>
                            <p className="text-xs text-white/50 mb-1.5 tabular-nums">
                                {_fechaCorta(s.date)}
                                {s.peso != null && <span className="text-[#FF671F] font-bold"> · {s.peso} kg</span>}
                            </p>
                            <div className="flex flex-wrap gap-2">
                                {s.fotos.map(f => (
                                    <div key={f.key} className="w-28">
                                        {f.source === 'calma'
                                            ? <CalmaFoto api={api} clientId={clientId} foto={{ file: f.file }} />
                                            : <AppFoto api={api} foto={f.foto} />}
                                        <p className="text-[10px] text-white/30 text-center mt-0.5 truncate">{f.pose}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                    {sesiones.length > 3 && (
                        <button onClick={() => setVerTodas(!verTodas)} data-testid="mural-ver-todas"
                            className="w-full py-2 text-xs font-semibold text-white/50 hover:text-[#FF671F] transition-colors">
                            {verTodas ? 'Ver solo las últimas' : `Ver todas (${plural(sesiones.length, 'día')} con fotos)`}
                        </button>
                    )}
                </CardContent>
            )}
        </Card>
    );
};

// COMPARATIVA CON ETIQUETAS (documento del 05-08, punto 3.2). Cuatro fotos como mucho,
// cada una respondiendo a algo, con la fecha, el peso de ese día y las medidas debajo.
// Las reglas viven en lib/comparativaFotos.js, compartidas con el informe del cliente.
// Campo para anotar el % graso de una sesión de fotos. Se guarda al salir del campo:
// es un dato que el coach pone de pasada mientras mira, no un formulario.
const BodyFatFoto = ({ api, clientId, fecha, valor, onGuardado }) => {
    const [v, setV] = useState(valor != null ? String(valor) : '');
    const [guardando, setGuardando] = useState(false);
    useEffect(() => { setV(valor != null ? String(valor) : ''); }, [valor]);

    const guardar = async () => {
        const limpio = v.trim();
        if (limpio === (valor != null ? String(valor) : '')) return;   // no ha cambiado
        setGuardando(true);
        try {
            const r = await api.put(`/admin/clients/${clientId}/body-fat`, { fecha, valor: limpio === '' ? null : limpio });
            onGuardado?.(r.data?.porcentajes_grasos || []);
            toast.success(limpio === '' ? '% graso quitado' : `% graso de ${_fechaCorta(fecha)} guardado`);
        } catch (e) {
            toast.error(mensajeDeError(e, 'No se pudo guardar el % graso'));
            setV(valor != null ? String(valor) : '');
        } finally { setGuardando(false); }
    };

    return (
        <div className="flex items-center gap-1 mt-1">
            <input type="number" step="0.1" min="3" max="60" value={v} placeholder="% graso"
                onChange={e => setV(e.target.value)} onBlur={guardar}
                onKeyDown={e => { if (e.key === 'Enter') e.target.blur(); }}
                data-testid={`body-fat-${fecha}`} disabled={guardando}
                className="w-full bg-[#0A0A0A] border border-[#222] rounded px-1.5 py-1 text-[11px] text-white/80 focus:border-[#FF671F]/60 outline-none disabled:opacity-50" />
            {v !== '' && <span className="text-[11px] text-white/30">%</span>}
        </div>
    );
};

// Las medidas que van debajo de una foto de la comparativa (punto 52). Cintura y cadera a la
// vista - son las que se miran al lado de una foto - y las demás en el tooltip.
const DESTACADAS = ['cintura', 'cadera'];
const MedidasDeLaFoto = ({ medidas }) => {
    const conNombre = MEDIDAS
        .map(({ key, label }) => ({ key, label, valor: valorAnterior(medidas, key) }))
        .filter(m => m.valor != null);
    if (!conNombre.length) return null;
    const arriba = conNombre.filter(m => DESTACADAS.includes(m.key));
    const resto = conNombre.filter(m => !DESTACADAS.includes(m.key));
    const alPasar = resto.map(m => `${m.label}: ${m.valor} cm`).join('\n');
    return (
        <p className="text-[11px] text-white/40 leading-tight" title={alPasar || undefined}>
            {(arriba.length ? arriba : conNombre.slice(0, 2)).map(m => (
                <span key={m.key} className="block">{m.label} <b className="text-white/60">{m.valor}</b> cm</span>
            ))}
            {resto.length > 0 && arriba.length > 0 && (
                <span className="block text-white/25 cursor-help">y {resto.length} medidas más</span>
            )}
        </p>
    );
};

const ComparativaFases = ({ api, clientId, calmaFotos, reports, macroHistory, faseDesde, fase, porcentajesGrasos }) => {
    const [appFotos, setAppFotos] = useState([]);
    const [ampliada, setAmpliada] = useState(false);
    const [verTodas, setVerTodas] = useState(false);
    // Serie de % grasos. `recien` son los que se acaban de anotar aquí; mientras no se
    // toque nada mandan los que vienen del cliente.
    // OJO: `porcentajesGrasos` llega como array nuevo en cada render del padre, así que NO
    // puede ser dependencia de un useEffect con setState: eso monta un bucle de renders que
    // llega a abortar la petición de guardado a medio vuelo. Con useMemo solo recalcula.
    const [recien, setRecien] = useState(null);
    const grasosPorFecha = useMemo(() => {
        const m = {};
        (recien || porcentajesGrasos || []).forEach(g => { if (g?.fecha) m[String(g.fecha).slice(0, 10)] = g.valor; });
        return m;
    }, [recien, porcentajesGrasos]);

    useEffect(() => {
        let alive = true;
        api.get(`/admin/clients/${clientId}/photos`)
            .then(r => { if (alive) setAppFotos(r.data?.photos || []); })
            .catch(() => {});
        return () => { alive = false; };
    }, [api, clientId]);

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

    // Medidas por fecha, para poder ponerlas debajo de su foto.
    const medidasPorFecha = useMemo(() => {
        const m = {};
        (reports || []).forEach(r => {
            const f = (r.created_at || '').slice(0, 10);
            if (f && r.measurements && Object.keys(r.measurements).length) m[f] = r.measurements;
        });
        return m;
    }, [reports]);

    const sesiones = useMemo(() => {
        const todas = [
            ...(calmaFotos || []).map(f => ({ key: `calma:${f.file}`, source: 'calma', file: f.file, date: f.fecha || '', pose: _poseDeKind(f.kind) })),
            ...(appFotos || []).map(p => ({ key: `app:${p.id}`, source: 'app', foto: p, date: (p.taken_at || p.uploaded_at || '').slice(0, 10), pose: _poseDeFoto(p) })),
        ].filter(f => f.date);
        const porDia = new Map();
        for (const f of todas) {
            if (!porDia.has(f.date)) porDia.set(f.date, []);
            porDia.get(f.date).push(f);
        }
        return [...porDia.entries()].map(([fecha, fotos]) => ({
            fecha,
            peso: _pesoCercano(pesos, fecha),
            medidas: medidasPorFecha[fecha] || null,
            fotos: fotos.sort((a, b) => _POSE_ORDER.indexOf(a.pose) - _POSE_ORDER.indexOf(b.pose)),
        }));
    }, [calmaFotos, appFotos, pesos, medidasPorFecha]);

    const comparativa = useMemo(() => construirComparativa(sesiones, faseDesde), [sesiones, faseDesde]);

    // SIN FOTOS NO HAY COMPARACIÓN, Y HAY QUE DECIRLO (punto 54 del doc del 07-08). Antes
    // esto hacía `return null`: la comparativa desaparecía entera y el coach abría
    // Seguimiento sin saber si es que no hay fotos o si la pantalla está rota. Y esta es la
    // pantalla que mira para cambiarle los macros a alguien.
    if (!comparativa.length) {
        return (
            <Card className="bg-[#111] border-[#222]" data-testid="comparativa-sin-fotos">
                <CardContent className="p-5 flex items-start gap-3">
                    <Camera className="w-5 h-5 text-white/25 shrink-0 mt-0.5" />
                    <div>
                        <p className="text-sm text-white/70 font-medium">Todavía no hay fotos suyas</p>
                        <p className="text-xs text-white/35 mt-0.5">
                            Sin fotos no hay comparación, y sin comparación esta pantalla no dice
                            gran cosa. Al cliente ya le salta el aviso para que las suba; si las
                            manda por WhatsApp, se pueden subir por él desde aquí abajo.
                        </p>
                    </div>
                </CardContent>
            </Card>
        );
    }

    const pintaFoto = (f) => f.source === 'calma'
        ? <CalmaFoto api={api} clientId={clientId} foto={{ file: f.file }} />
        : <AppFoto api={api} foto={f.foto} />;

    return (
        <Card className="bg-[#111] border-[#222]">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2">
                    <Camera className="w-4 h-4 text-[#FF671F]" />Comparativa
                    {fase && <span className="text-white/25 normal-case">· en {fase}{faseDesde ? ` desde el ${_fechaCorta(faseDesde)}` : ''}</span>}
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3" data-testid="comparativa-fases">
                {verTodas ? (
                    <div className="flex flex-wrap gap-2">
                        {[...sesiones].sort((a, b) => b.fecha.localeCompare(a.fecha)).map(s => s.fotos.map(f => (
                            <div key={f.key} className="w-24">
                                {pintaFoto(f)}
                                <p className="text-[10px] text-white/30 text-center mt-0.5">{_fechaCorta(s.fecha)}</p>
                            </div>
                        )))}
                    </div>
                ) : (
                    /* SIEMPRE CUATRO COLUMNAS, aunque haya menos fotos. Antes la rejilla se
                       repartía entre las que hubiera, así que con una sola -- el mes 1, o
                       sea todo cliente nuevo -- la foto salía a pantalla completa y había
                       que hacer scroll para pasar de ella, en la pantalla que justamente
                       tiene que darlo todo de un vistazo (bloque F).
                       Con cuatro columnas fijas cada foto ocupa siempre lo mismo, van
                       creciendo hacia la derecha según se van teniendo, y la inicial se
                       queda a la izquierda - que es la regla de Jesús. */
                    <div className="grid gap-3 grid-cols-4">
                        {comparativa.map(c => (
                            <div key={c.fecha} className="space-y-1">
                                <div className={ampliada ? 'grid grid-cols-2 gap-1' : ''}>
                                    {(ampliada ? c.fotos : c.fotos.slice(0, 1)).map(f => (
                                        <div key={f.key}>{pintaFoto(f)}</div>
                                    ))}
                                </div>
                                <p className="text-[10px] font-bold uppercase tracking-wider text-[#FF671F] leading-tight">
                                    {c.etiquetas.map(e => TITULO_ETIQUETA[e] || e).join(' · ')}
                                </p>
                                <p className="text-[11px] text-white/40 leading-tight">
                                    {_fechaCorta(c.fecha)}
                                    {c.peso != null && <span className="block text-white font-bold">{c.peso} kg</span>}
                                </p>
                                {/* LAS MEDIDAS DE ESE MOMENTO (punto 52 del doc del 07-08).
                                    Antes salían las TRES PRIMERAS del objeto - o sea las que
                                    cayeran, con su nombre interno (`brazo_d 38 cm`). Ahora
                                    salen cintura y cadera, que son las que se miran junto a
                                    una foto, con su nombre de verdad, y el resto está en el
                                    tooltip: debajo de una foto de 1/4 de ancho no caben diez
                                    filas, y la comparación completa ya la da la tabla de
                                    evolución de medidas (punto 35), aquí arriba. */}
                                {c.medidas && <MedidasDeLaFoto medidas={c.medidas} />}
                                {/* El % graso se estima MIRANDO LA FOTO y solo cuando toca (3.3),
                                    así que se anota aquí, no en un campo suelto. Cada anotación
                                    engorda la serie por fecha, que es de donde sale el eje
                                    respondedor del perfil. */}
                                <BodyFatFoto api={api} clientId={clientId} fecha={c.fecha}
                                    valor={grasosPorFecha[c.fecha]} onGuardado={setRecien} />
                            </div>
                        ))}
                    </div>
                )}
                <div className="flex gap-2">
                    <button onClick={() => { setAmpliada(!ampliada); setVerTodas(false); }} data-testid="ampliar-comparativa"
                        className="flex-1 py-2 text-xs font-semibold text-white/50 hover:text-[#FF671F] border border-[#222] rounded-lg transition-colors">
                        {ampliada ? 'Ver solo de frente' : 'Ampliar comparativa'}
                    </button>
                    <button onClick={() => setVerTodas(!verTodas)} data-testid="mostrar-todas-fotos"
                        className="flex-1 py-2 text-xs font-semibold text-white/50 hover:text-[#FF671F] border border-[#222] rounded-lg transition-colors">
                        {verTodas ? 'Volver a la comparativa' : 'Mostrar todas'}
                    </button>
                </div>
                {!faseDesde && (
                    <p className="text-[10px] text-white/25 leading-relaxed">
                        Sin cambio de fase registrado: la comparativa se queda en tres. La fase se
                        fecha cuando el cliente marca otro objetivo en su reporte.
                    </p>
                )}
            </CardContent>
        </Card>
    );
};

// Cada foto se carga por fetch autenticado (blob) para no llevar el token en la URL.
const CalmaFoto = ({ api, clientId, foto }) => {
    const [thumb, setThumb] = useState(null);
    useEffect(() => {
        let alive = true;
        // Por la caché compartida: la misma foto sale en la comparativa, en el mural y en la
        // línea temporal, y antes se descargaba una vez por sitio.
        _thumb(`calma:${clientId}:${foto.file}`,
            () => api.get(`/admin/clients/${clientId}/calma-foto`, { params: { file: foto.file, w: 300 }, responseType: 'blob' }).then(r => r.data))
            .then(url => { if (alive) setThumb(url); })
            .catch(() => {});
        return () => { alive = false; };
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
                        <p className="text-[10px] text-white/40 uppercase tracking-wider mb-1">Observaciones del entrenador</p>
                        <p className="text-white/80 text-sm whitespace-pre-wrap">{sup.observaciones}</p>
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

// La MISMA gráfica que ve el cliente (punto 4.13). Antes eran dos, con los mismos fallos
// escritos dos veces: el eje por categorías juntando todos los «9 ago» de cuatro años y los
// colores a pelo. Ahora hay una sola y las dos pantallas enseñan lo mismo.
const WeightEvolution = ({ reports }) => {
    const puntos = (reports || [])
        .filter(r => r.weight != null)
        .map(r => ({ fecha: r.created_at, peso: r.weight }));
    if (!puntos.length) return null;
    return (
        <Card className="bg-[#111] border-[#222]">
            <CardHeader className="pb-2"><CardTitle className="text-sm text-white/40 uppercase tracking-wider flex items-center gap-2"><Scale className="w-4 h-4" />Evolución del peso ({puntos.length})</CardTitle></CardHeader>
            <CardContent>
                <GraficaDePeso puntos={puntos} />
            </CardContent>
        </Card>
    );
};

const MEAL_ORDER = { C1: 1, C2: 2, C3: 3, C4: 4, C5: 5, C6: 6, Intra: 7, Post: 8 };
const MEAL_LABEL = { Intra: 'Intra-entreno', Post: 'Post-entreno', C1: 'Comida 1', C2: 'Comida 2', C3: 'Comida 3', C4: 'Comida 4', C5: 'Comida 5', C6: 'Comida 6' };

// Lo que el cliente contestó en el reporte nuevo, con las palabras del formulario.
// Los reportes viejos no traen nada de esto y el bloque no sale.
const RESPUESTA_LABEL = {
    dieta_dificultad: { nada: 'Nada, la llevo bien', algun_dia: 'Algún día suelto',
                        bastante: 'Bastante', no_he_podido: 'No he podido' },
    cardio_proximo_mes: { mismas: 'Puedo con las mismas sesiones', mas: 'Puedo con más sesiones',
                          menos: 'Necesito menos sesiones' },
    suplementacion: { todos: 'Todos', alguno_no: 'Alguno no', ninguno: 'Ninguno' },
    energia_motivo: { duermo_poco: 'Duermo poco', estres_trabajo: 'Estrés del trabajo',
                      como_poco: 'Como poco', no_lo_se: 'No lo sé' },
    regularidad: { a_mi_manera_sigo: 'A su manera, quiere seguir así',
                   a_mi_manera_quiero_rutina: 'A su manera, quiere probar una rutina tuya',
                   con_tu_rutina_sigo: 'Con tu rutina, quiere seguir así' },
    rutina_del_mes: { basica: 'La quiere · básica', avanzada: 'La quiere · avanzada', ahora_no: 'Ahora no' },
};

const Fila = ({ que, valor }) => (valor ? (
    <p className="text-white/50">{que} <b className="text-white">{valor}</b></p>
) : null);

// LO QUE CONTESTÓ EN EL REPORTE MENSUAL DE CALMA. Las ocho preguntas de siempre, con las
// palabras del cliente. Se traen tal cual y no como un porcentaje: la respuesta es «Salvo
// algún día puntual, he cumplido con todo lo que me has marcado», y convertir eso en un
// «85 %» es inventárselo.
//
// El orden es el del formulario, que es el que Jesús lee: primero cómo fue el mes, luego el
// entreno y el cardio, luego la dieta y el esfuerzo que le costó, y al final el descanso, la
// suplementación y hacia dónde quiere ir el mes que viene.
const PREGUNTAS_CALMA = [
    ['compromiso', 'Su compromiso'],
    ['cumplimientoEntrenamiento', 'El entreno'],
    ['problemasParaEntrenar', 'Problemas para entrenar'],
    ['cumplimientoCardio', 'El cardio'],
    ['cumplimientoDieta', 'La dieta'],
    ['esfuerzoParaCumplirDieta', 'Lo que le costó'],
    ['descanso', 'El descanso'],
    ['tomaDeSuplementos', 'Suplementos'],
    ['detalleSuplementos', 'Cuáles'],
    ['objetivo', 'Su objetivo ahora'],
];

const RespuestasDeCalma = ({ respuestas }) => {
    const filas = PREGUNTAS_CALMA.filter(([k]) => (respuestas || {})[k]);
    if (!filas.length) return null;
    return (
        <div className="space-y-1.5 text-sm bg-[#0A0A0A] rounded-lg p-3 border border-[#222]"
            data-testid="respuestas-calma">
            <p className="text-white/40 text-[11px] uppercase tracking-wider">
                Lo que contestó en su reporte mensual
            </p>
            {filas.map(([k, etiqueta]) => (
                <p key={k} className="text-white/50 leading-snug">
                    {etiqueta} <b className="text-white font-normal">{respuestas[k]}</b>
                </p>
            ))}
        </div>
    );
};

const RespuestasDelReporte = ({ reporte: r }) => {
    const e = r.entreno || {};
    const s = r.suplementacion || {};
    const hayAlgo = r.tipo || r.molestias || r.sensaciones || r.dieta_dificultad || e.regularidad
        || e.estrellas || e.rutina_del_mes || s.respuesta || r.cardio_proximo_mes
        || (r.lesiones || []).length || r.valoracion_resultado || r.motivacion || r.sugerencias;
    if (!hayAlgo) return null;
    const estrellas = (n) => (n ? '★'.repeat(n) + '☆'.repeat(5 - n) : null);

    return (
        <div className="space-y-1.5 text-sm bg-[#0A0A0A] rounded-lg p-3 border border-[#222]"
            data-testid="respuestas-reporte">
            {r.tipo && (
                <p className="text-white/40 text-[11px] uppercase tracking-wider">Reporte {r.tipo}</p>
            )}
            <Fila que="Molestias" valor={r.molestias} />
            <Fila que="Sensaciones" valor={estrellas(r.sensaciones)} />
            <Fila que="La dieta" valor={RESPUESTA_LABEL.dieta_dificultad[r.dieta_dificultad]} />
            <Fila que="Entreno del mes" valor={RESPUESTA_LABEL.regularidad[e.regularidad]} />
            <Fila que="Qué tal el entreno" valor={estrellas(e.estrellas)} />
            <Fila que="Del entreno" valor={e.nota} />
            <Fila que="La rutina del mes" valor={RESPUESTA_LABEL.rutina_del_mes[e.rutina_del_mes]} />
            {e.quiere_saber_del_silver && (
                <p className="text-[#FF671F]">Quiere que le cuentes el plan de arriba</p>
            )}
            {(r.lesiones || []).filter(l => l.estado_mes).map((l, i) => (
                <p key={i} className="text-white/50">
                    {l.zona} <b className="text-white">{l.estado_mes}</b>
                    {(l.ejercicios || []).length ? (
                        <span className="text-white/40"> · no puede: {l.ejercicios.join(', ')}</span>
                    ) : null}
                </p>
            ))}
            <Fila que="Lesión nueva" valor={r.lesion_nueva} />
            <Fila que="Cardio" valor={RESPUESTA_LABEL.cardio_proximo_mes[r.cardio_proximo_mes]} />
            <Fila que="Suplementación" valor={RESPUESTA_LABEL.suplementacion[s.respuesta]} />
            <Fila que="Cuál y por qué" valor={s.detalle} />
            <Fila que="Energía" valor={RESPUESTA_LABEL.energia_motivo[r.energia_motivo]} />
            <Fila que="Cómo lo valora" valor={estrellas(r.valoracion_resultado)} />
            <Fila que="Motivación" valor={estrellas(r.motivacion)} />
            <Fila que="Sugerencias" valor={r.sugerencias} />
        </div>
    );
};

// Reportes del cliente con feedback editable por el coach (cierra el circuito de ReportsPage)
const ReportsFeedbackList = ({ initialReports }) => {
    const { api } = useAuth();
    const [reports, setReports] = useState(initialReports || []);
    const [drafts, setDrafts] = useState({});
    const [savingId, setSavingId] = useState(null);
    const [showAll, setShowAll] = useState(false);
    const [detalleId, setDetalleId] = useState(null);   // reporte abierto en el modal
    // EL INFORME, AQUÍ DENTRO (T9 del doc 16-08). Se genera solo al enviar el reporte y
    // espera a que Jesús lo mire: hasta ahora el endpoint ya se lo permitía y no había
    // pantalla, así que el informe del cliente salía sin que nadie lo hubiera visto.
    const [informe, setInforme] = useState(null);
    const [cargandoInforme, setCargandoInforme] = useState(false);
    const [publicando, setPublicando] = useState(false);

    const verInforme = async (reportId) => {
        setCargandoInforme(true);
        setInforme(null);
        try {
            const r = await api.get(`/reports/${reportId}/informe`);
            setInforme(r.data);
        } catch (e) {
            console.error('No se pudo montar el informe del reporte', e);
            toast.error('No hemos podido montar el informe de este reporte');
        } finally { setCargandoInforme(false); }
    };

    const publicar = async (reportId) => {
        setPublicando(true);
        try {
            const r = await api.post(`/reports/${reportId}/informe/publicar`);
            setReports(prev => prev.map(x => x.id === reportId
                ? { ...x, informe_estado: 'entregado' } : x));
            setInforme(r.data?.informe || informe);
            toast.success('Informe publicado', {
                description: 'El cliente ya lo tiene y le ha llegado el aviso.',
            });
        } catch (e) {
            console.error('No se pudo publicar el informe', e);
            toast.error('No hemos podido publicar el informe');
        } finally { setPublicando(false); }
    };

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
                    <button key={r.id} onClick={() => { setDetalleId(r.id); setInforme(null); }} data-testid={`report-${r.id}`}
                        className="w-full flex items-center gap-3 px-3 py-2 rounded-lg bg-[#0A0A0A] border border-[#222] hover:border-[#FF671F]/40 transition-colors text-left">
                        <span className="text-white text-sm font-medium tabular-nums whitespace-nowrap">
                            {new Date(r.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })}
                        </span>
                        {r.weight != null && <span className="text-[#FF671F] font-bold text-sm tabular-nums">{r.weight} kg</span>}
                        <span className="ml-auto flex items-center gap-2 flex-shrink-0">
                            {/* Lo primero que hay que ver de un reporte es si su informe
                                está esperando: es trabajo pendiente, no un adorno. */}
                            {r.informe_estado === 'pendiente_revision' && (
                                <span className="text-[#FF671F] text-[10px] uppercase tracking-wider">informe por revisar</span>
                            )}
                            {r.informe_estado === 'entregado' && (
                                <span className="text-emerald-400 text-[10px] uppercase tracking-wider">informe entregado</span>
                            )}
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
                    <DialogContent className="bg-[#111] border-[#333] max-w-2xl max-h-[90vh] overflow-y-auto text-white" data-testid="report-detail">
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
                        {/* Las tres preguntas del formulario de siempre (punto 5 del 05-08).
                            El próximo objetivo es el que dispara el cambio de fase, así que se
                            marca cuando cambia respecto a la fase que tenía. */}
                        {(abierto.proximo_objetivo || abierto.viabilidad_ajuste || abierto.cumplimiento_entreno) && (
                            <div className="space-y-1.5 text-sm bg-[#0A0A0A] rounded-lg p-3 border border-[#222]">
                                {abierto.proximo_objetivo && (
                                    <p className="text-white/50">Próximo objetivo{' '}
                                        <b className="text-[#FF671F] uppercase">{OBJETIVO_REPORTE[abierto.proximo_objetivo] || abierto.proximo_objetivo}</b>
                                    </p>
                                )}
                                {abierto.viabilidad_ajuste && (
                                    <p className="text-white/50">Margen para ajustar{' '}
                                        <b className="text-white">{VIABILIDAD_REPORTE[abierto.viabilidad_ajuste] || abierto.viabilidad_ajuste}</b>
                                    </p>
                                )}
                                {abierto.cumplimiento_entreno && (
                                    <p className="text-white/50">Entrenamientos{' '}
                                        <b className="text-white">{ENTRENO_REPORTE[abierto.cumplimiento_entreno] || abierto.cumplimiento_entreno}</b>
                                    </p>
                                )}
                            </div>
                        )}
                        {/* LO QUE CONTESTÓ EN EL FORMULARIO NUEVO (T7 y T8). Sin esto, el
                            panel enseñaba peso, cumplimiento y tres preguntas viejas: todo
                            lo que el cliente cuenta del entreno, las lesiones, el cardio o
                            la suplementación se quedaba guardado y sin ver. */}
                        <RespuestasDelReporte reporte={abierto} />

                        {/* Y LO QUE CONTESTÓ EN CALMA, para los meses de antes de la app. Es
                            el mismo formulario mensual, y hasta hoy de esos meses solo se
                            guardaba el peso: las respuestas estaban escritas en la base y no
                            las enseñaba ninguna pantalla. */}
                        <RespuestasDeCalma respuestas={abierto.calma_respuestas} />

                        {abierto.notes && <p className="text-white/70 text-sm italic">"{abierto.notes}"</p>}

                        {/* EL INFORME MONTADO. Se pide al abrirlo y no al cargar la ficha:
                            cruza dietas, cierres y macros de todo el mes, y no tiene
                            sentido montar los cincuenta de la lista para pintar una fila. */}
                        <div className="rounded-lg border border-[#222] bg-[#0A0A0A] p-3 space-y-2">
                            <div className="flex items-center justify-between gap-2">
                                <span className="text-white/60 text-xs uppercase tracking-wider">Informe del mes</span>
                                <Button size="sm" variant="outline" data-testid="ver-informe"
                                    onClick={() => verInforme(abierto.id)} disabled={cargandoInforme}
                                    className="bg-transparent border-[#333] text-white h-7 text-xs">
                                    {cargandoInforme ? 'Montando...' : informe ? 'Actualizar' : 'Ver el informe'}
                                </Button>
                            </div>
                            {informe && (
                                <div className="max-h-[45vh] overflow-y-auto pr-1" data-testid="informe-montado">
                                    {informe.generado === false
                                        ? <p className="text-white/50 text-sm">{informe.mensaje || 'Todavía no se puede montar.'}</p>
                                        : <InformeMensual informe={informe} />}
                                </div>
                            )}
                            {abierto.informe_estado === 'pendiente_revision' ? (
                                <>
                                    <p className="text-white/40 text-[11px]">
                                        El cliente no lo ve hasta que lo publiques. Escribe tu feedback abajo y publícalo.
                                    </p>
                                    <Button size="sm" onClick={() => publicar(abierto.id)} disabled={publicando}
                                        data-testid="publicar-informe"
                                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white h-8 text-xs">
                                        {publicando ? 'Publicando...' : 'Publicar el informe'}
                                    </Button>
                                </>
                            ) : abierto.informe_estado === 'entregado' ? (
                                <p className="text-emerald-400 text-[11px]">Publicado. El cliente ya lo tiene.</p>
                            ) : null}
                        </div>

                        <div>
                            <Label className="text-white/60 text-xs">Feedback para el cliente</Label>
                            <Textarea value={draftAbierto} onChange={e => setDrafts(prev => ({ ...prev, [abierto.id]: e.target.value }))}
                                placeholder="Escribe feedback para el cliente..." rows={3}
                                className="bg-[#0A0A0A] border-[#333] text-white mt-1" />
                            {/* Los cuatro mensajes de siempre, en un botón (punto 4.1). */}
                            <PlantillasFeedback actual={draftAbierto}
                                onInsertar={t => setDrafts(prev => ({ ...prev, [abierto.id]: t }))} />
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
    // QUIÉN GUARDÓ ESTE DÍA (punto 4.11). Se anota desde que el entrenador puede entrar en la
    // calculadora de un cliente, y no se veía en ninguna pantalla. Aquí es donde contesta a la
    // pregunta de Jesús: si le montaste el martes una dieta y el miércoles aparece firmada por
    // él, es que la ha cambiado -- y esa es justo la conversación que hay que tener.
    const loGuardo = diet?.editado_por;
    const loGuardoElCoach = diet?.editado_como === 'entrenador';
    return (
        <div className="space-y-2.5">
            {loGuardo && (
                <p className="text-[11px] text-white/40" data-testid="dieta-quien-la-guardo">
                    Lo guardó{' '}
                    <span className={loGuardoElCoach ? 'text-[#FF671F] font-semibold' : 'text-white/70 font-semibold'}>
                        {loGuardo}
                    </span>
                    {loGuardoElCoach ? ' (del equipo)' : ' (el cliente)'}
                    {diet?.updated_at ? ` · ${_fechaCorta(String(diet.updated_at).slice(0, 10))}` : ''}
                </p>
            )}
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
                                    {/* LA CANTIDAD, CON SU UNIDAD. Aquí se pintaba el número
                                        pelado con una «g» pegada detrás, así que un huevo salía
                                        como «1 g» y una lata de atún, también (Jesús, 16-08).
                                        Ahora el texto viene resuelto del backend -- «2 ud
                                        (126 g)» --, que es el único que sabe si el alimento va
                                        por unidades y cuánto pesa una. */}
                                    <span className="text-white/40 whitespace-nowrap w-24 text-right" title="Cantidad">
                                        {a.cantidad_texto || `${Math.round(a.cantidad_g || 0)} g`}
                                    </span>
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
