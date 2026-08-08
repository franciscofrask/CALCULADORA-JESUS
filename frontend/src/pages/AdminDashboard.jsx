import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Outlet, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { PlanBadge, JG12Logo } from './ClientDashboard';
import {
    LayoutDashboard, Users, CreditCard, Dumbbell,
    MessageCircle, LogOut, Search, Bell,
    ChevronRight, DollarSign, FileText,
    AlertTriangle, UserCheck, UserMinus, UserPlus, Utensils, Apple, Layers,
    Menu, X, Phone
} from 'lucide-react';

// Colores para el desglose por plan (cualquier plan sin color cae en el gris).
const PLAN_COLORS = {
    reto12en12_gold: '#EAB308', gold: '#EAB308',
    reto12en12_silver: '#9CA3AF', silver: '#9CA3AF',
    bronze: '#C2410C', elm: '#FF671F', reto60: '#22C55E',
    calculadora_jp: '#3B82F6', mantenimiento: '#8B5CF6',
    premium: '#EC4899', plan_6m: '#14B8A6', sin_plan: '#555555',
};

// Panel "Por hacer esta semana": tres columnas accionables (sin macros / sin rutina /
// reporte pendiente), con filtro por clientes al corriente de pago (tarea 19).
const TodoSemana = ({ todo, soloAlCorriente, setSoloAlCorriente, navigate }) => {
    if (!todo) return null;
    const flt = (arr) => (arr || []).filter(c => !soloAlCorriente || c.al_corriente);
    const cols = [
        { key: 'macros', label: 'Sin macros', icon: Apple, color: '#FF671F', sub: 'Necesitan macros del coach', items: flt(todo.sin_macros) },
        { key: 'rutina', label: 'Sin rutina', icon: Dumbbell, color: '#3B82F6', sub: 'Plan con rutina, sin una activa', items: flt(todo.sin_rutina) },
        { key: 'reportes', label: 'Reporte pendiente', icon: FileText, color: '#EAB308', sub: 'No enviado esta semana', items: flt(todo.reporte_pendiente) },
        // "Hoy no puedes ver si un cliente de 1.500 lleva tres semanas sin que nadie le
        // hable". Solo salen los planes con chat, ordenados de más abandonado a menos, y
        // con los días a la vista para que se note de un vistazo.
        { key: 'contacto', label: 'Sin contacto', icon: MessageCircle, color: '#A855F7', sub: 'Días desde que alguien le habló', items: flt(todo.sin_contacto) },
    ];
    return (
        <Card className="bg-[#111111] border-[#222]" data-testid="todo-semana">
            <CardContent className="p-5">
                <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
                    <p className="text-xs font-bold text-white/40 uppercase tracking-wider">Por hacer esta semana</p>
                    <label className="flex items-center gap-2 text-xs text-white/50 cursor-pointer select-none">
                        <input type="checkbox" checked={soloAlCorriente} onChange={e => setSoloAlCorriente(e.target.checked)}
                            className="accent-[#FF671F]" data-testid="todo-filter-alcorriente" />
                        Solo al corriente de pago
                    </label>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                    {cols.map(col => (
                        <div key={col.key} className="bg-[#0A0A0A] rounded-xl border border-[#222] p-3">
                            <div className="flex items-center gap-2 mb-1">
                                <col.icon className="w-4 h-4" style={{ color: col.color }} />
                                <span className="text-sm font-bold text-white">{col.label}</span>
                                <span className="ml-auto text-sm font-bold" style={{ color: col.color }}>{col.items.length}</span>
                            </div>
                            <p className="text-[10px] text-white/30 mb-2">{col.sub}</p>
                            <div className="space-y-0.5 max-h-64 overflow-y-auto">
                                {col.items.length === 0 && <p className="text-white/25 text-xs py-3 text-center">Nada pendiente</p>}
                                {col.items.map(c => (
                                    <button key={c.client_id} onClick={() => navigate(`/admin/clients/${c.client_id}`)}
                                        className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/5 text-left">
                                        <span className="flex-1 min-w-0 truncate text-sm text-white/80">{c.name}</span>
                                        {col.key === 'reportes' && c.overdue && <span className="text-[9px] text-red-400 font-bold uppercase tracking-wide">tarde</span>}
                                        {/* Los días, y a partir de dos semanas en rojo: no es
                                            un umbral del servidor, es lo que salta a la vista. */}
                                        {col.key === 'contacto' && (
                                            <span className={`text-[10px] font-bold tabular-nums ${c.dias >= 14 ? 'text-red-400' : 'text-white/40'}`}>
                                                {c.nunca ? 'nunca' : `${c.dias} d`}
                                            </span>
                                        )}
                                        {!c.al_corriente && <span title="Pago pendiente" className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />}
                                        <ChevronRight className="w-3.5 h-3.5 text-white/20 flex-shrink-0" />
                                    </button>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
};

// "Esta semana te tocan estos seis" (punto 29 del doc del 07-08). Es la pregunta que Jesús
// se hace todos los lunes y que hasta ahora resolvía mirando una hoja de cálculo aparte:
// quién lleva más tiempo sin que le muevan los macros. Arriba, el que más.
const CUANTOS_TE_TOCAN = 6;

// EL SEMÁFORO (punto 32 del 07-08). Cinco estados, por celda y no por fila: así se
// distingue quién va regular de quién va mal, y en qué. Los estados los decide el backend
// contra el plazo del plan de cada cliente; aquí solo se pintan.
//
// `info` no es un estado peor ni mejor: es "esta casilla no cuenta para este cliente" (su
// plan no lleva chat, o no hay dato). Por eso va en gris apagado y no en un color de aviso.
const SEMAFORO = {
    ok:           'text-emerald-400',
    regular:      'text-amber-400',
    regular_malo: 'text-orange-400 font-bold',
    malo:         'text-red-400 font-bold',
    info:         'text-white/25',
};

const CeldaSemaforo = ({ celda, testId }) => {
    if (!celda) return <span className="text-white/25 text-sm">-</span>;
    return (
        <span className={`text-sm tabular-nums ${SEMAFORO[celda.estado] || 'text-white/60'}`}
            title={celda.detalle || undefined} data-testid={testId} data-estado={celda.estado}>
            {celda.texto ?? '-'}
        </span>
    );
};

// Días desde una fecha AAAA-MM-DD. null si nunca ha pasado (no es lo mismo que cero).
const diasDesde = (iso) => {
    if (!iso) return null;
    const d = new Date(String(iso).slice(0, 10) + 'T00:00:00');
    if (isNaN(d)) return null;
    return Math.max(0, Math.floor((Date.now() - d.getTime()) / 86400000));
};
const diasSinTocar = (c) => diasDesde(c?.ultimo_ajuste);

const EstaSemanaTeTocan = ({ items, navigate }) => {
    if (!items || items.length === 0) return null;
    const seis = items.slice(0, CUANTOS_TE_TOCAN);
    const _dias = (c) => c.nunca_ajustado ? 'nunca' : `${c.dias_sin_ajuste} d`;
    return (
        <Card className="bg-[#111111] border-[#FF671F]/25" data-testid="te-tocan">
            <CardContent className="p-5">
                <div className="flex items-center justify-between mb-1 gap-3 flex-wrap">
                    <p className="text-xs font-bold text-white/40 uppercase tracking-wider">Esta semana te tocan estos {seis.length}</p>
                    <button onClick={() => navigate('/admin/clients?orden=sin_tocar')}
                        className="text-[11px] text-[#FF671F] hover:underline" data-testid="te-tocan-todos">
                        Ver los {items.length} ordenados
                    </button>
                </div>
                <p className="text-[10px] text-white/30 mb-3">Los que llevan más sin que les muevan los macros</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2">
                    {seis.map(c => (
                        <button key={c.client_id} onClick={() => navigate(`/admin/clients/${c.client_id}`)}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#0A0A0A] border border-[#222] hover:border-[#FF671F]/40 text-left">
                            <span className="flex-1 min-w-0 truncate text-sm text-white/80">{c.name}</span>
                            {/* Los días desde el último ajuste, y desde el mes en naranja: no
                                es un umbral del servidor, es lo que salta a la vista. */}
                            <span className={`text-[11px] font-bold tabular-nums ${c.nunca_ajustado || (c.dias_sin_ajuste || 0) >= 30 ? 'text-[#FF671F]' : 'text-white/40'}`}>
                                {_dias(c)}
                            </span>
                            {!c.al_corriente && <span title="Pago pendiente" className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />}
                            <ChevronRight className="w-3.5 h-3.5 text-white/20 flex-shrink-0" />
                        </button>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
};

// Alerta: quien ha elegido el Nivel 3 en el test y espera que le llamen. Solo aparece
// cuando hay alguna: un aviso que está siempre deja de ser un aviso. Va arriba del todo
// porque es lo único del panel donde hay alguien esperando al otro lado del teléfono.
const LlamadasPendientes = ({ llamadas, onAtendida, onCobrar, generandoEnlace }) => {
    if (!llamadas || llamadas.length === 0) return null;
    return (
        <Card className="bg-[#FF671F]/10 border-[#FF671F]/40" data-testid="llamadas-pendientes">
            <CardContent className="p-5">
                <div className="flex items-center gap-2 mb-3">
                    <Phone className="w-4 h-4 text-[#FF671F]" />
                    <span className="text-sm font-bold text-white uppercase tracking-wider">
                        Piden que les llamemos
                    </span>
                    <Badge className="bg-[#FF671F] text-white border-0 text-xs">{llamadas.length}</Badge>
                    <span className="text-[11px] text-white/40 ml-auto">Nivel 3 desde el test</span>
                </div>
                <div className="space-y-2">
                    {llamadas.map(l => (
                        <div key={l.id} data-testid={`llamada-${l.id}`}
                            className="bg-[#0A0A0A] rounded-xl border border-[#222] p-3 flex flex-wrap items-center gap-x-4 gap-y-2">
                            <div className="min-w-0">
                                <p className="text-sm font-bold text-white truncate">{l.name}</p>
                                <p className="text-[11px] text-white/40 truncate">{l.email}</p>
                            </div>
                            {/* El teléfono es el dato accionable: grande y pulsable para llamar. */}
                            <a href={`tel:${(l.phone || '').replace(/\s/g, '')}`}
                                className="text-base font-bold text-[#FF671F] hover:underline tabular-nums">
                                {l.phone || 'sin teléfono'}
                            </a>
                            {l.dias_esperando > 0 && (
                                <span className={`text-[10px] font-bold uppercase tracking-wide ${
                                    l.dias_esperando >= 2 ? 'text-red-400' : 'text-white/40'}`}>
                                    {l.dias_esperando === 1 ? 'de ayer' : `hace ${l.dias_esperando} días`}
                                </span>
                            )}
                            <div className="ml-auto flex items-center gap-2">
                                {/* Ya hablado: se le cobra con tarjeta como a los demas. */}
                                <Button size="sm" onClick={() => onCobrar(l)} disabled={generandoEnlace === l.id}
                                    data-testid={`enlace-pago-${l.id}`}
                                    className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs disabled:opacity-60">
                                    {generandoEnlace === l.id ? 'Creando...' : 'Enlace de pago'}
                                </Button>
                                <Button size="sm" variant="ghost" onClick={() => onAtendida(l)}
                                    data-testid={`llamada-atendida-${l.id}`}
                                    className="text-xs text-white/60 hover:text-white">
                                    Ya le he llamado
                                </Button>
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
};

// Admin Dashboard Home
const AdminDashboard = () => {
    const { api, planCatalog } = useAuth();
    const navigate = useNavigate();
    const [stats, setStats] = useState(null);
    const [upcoming, setUpcoming] = useState([]);
    const [clients, setClients] = useState([]);
    const [cadence, setCadence] = useState([]);
    const [loading, setLoading] = useState(true);
    // Motor de macros v2: dietas reportadas que no cuadran, pendientes de revisar.
    const [revisiones, setRevisiones] = useState([]);
    // "Por hacer esta semana": sin macros / sin rutina / reporte pendiente (tarea 19).
    const [todo, setTodo] = useState(null);
    const [soloAlCorriente, setSoloAlCorriente] = useState(false);
    // Nivel 3: piden llamada desde el test de nivel y esperan a que alguien marque.
    const [llamadas, setLlamadas] = useState([]);

    const marcarLlamadaAtendida = async (l) => {
        try {
            await api.post(`/leads/${l.id}/llamada-atendida`);
            setLlamadas(prev => prev.filter(x => x.id !== l.id));
            toast.success(`${l.name} queda como contactado`);
        } catch {
            toast.error('No se pudo marcar la llamada');
        }
    };

    // Cobro del Nivel 3 despues de la llamada (doc 03-08): se genera el enlace de pago
    // con tarjeta y se copia para mandarselo por WhatsApp. Es pago unico del ciclo, no
    // suscripcion, y al pagarlo salta el aviso al equipo para darle el alta.
    const [generandoEnlace, setGenerandoEnlace] = useState(null);
    const generarEnlacePago = async (l) => {
        setGenerandoEnlace(l.id);
        try {
            const r = await api.post(`/leads/${l.id}/enlace-pago`, { plan: 'nivel3' });
            const url = r.data?.url;
            try {
                await navigator.clipboard.writeText(url);
                toast.success(`Enlace de pago copiado (${r.data.importe_eur}€). Pégaselo por WhatsApp.`);
            } catch {
                // Sin permiso de portapapeles (http, o el navegador lo bloquea): se enseña
                // para copiar a mano, que es mejor que perder el enlace recien creado.
                toast.success('Enlace de pago creado', { description: url, duration: 30000 });
            }
            setLlamadas(prev => prev.filter(x => x.id !== l.id));
        } catch (e) {
            toast.error(e?.response?.data?.detail || 'No se pudo crear el enlace de pago');
        } finally {
            setGenerandoEnlace(null);
        }
    };

    const resolverRevision = async (rev) => {
        try {
            await api.post(`/admin/macro-revisiones/${rev.id}/resolver`);
            setRevisiones(prev => prev.filter(r => r.id !== rev.id));
            toast.success('Revisión marcada como revisada');
        } catch {
            toast.error('No se pudo marcar la revisión');
        }
    };

    const markReport = async (item, enviado) => {
        try {
            await api.post('/admin/report-cadence/mark', {
                client_id: item.client_id, tipo: item.tipo, due_date: item.due_date, enviado,
            });
            setCadence(prev => prev.map(i =>
                i.client_id === item.client_id && i.tipo === item.tipo && i.due_date === item.due_date
                    ? { ...i, status: enviado ? 'enviado' : 'pendiente' }
                    : i
            ));
            toast.success(enviado ? 'Reporte marcado como enviado' : 'Marca de envío quitada');
        } catch {
            toast.error('No se pudo actualizar el reporte');
        }
    };

    // Campana: novedades reales (leads nuevos sin gestionar + mensajes sin leer)
    const [notif, setNotif] = useState({ leads: 0, messages: 0 });
    const [notifOpen, setNotifOpen] = useState(false);

    useEffect(() => {
        const fetchAll = async () => {
            try {
                const [statsRes, upcomingRes, clientsRes, cadenceRes, revisionesRes, todoRes, llamadasRes] = await Promise.all([
                    api.get('/admin/dashboard-stats'),
                    api.get('/admin/upcoming-payments'),
                    api.get('/admin/clients'),
                    api.get('/admin/report-cadence'),
                    api.get('/admin/macro-revisiones').catch(() => ({ data: { items: [] } })),
                    api.get('/admin/todo-semana').catch(() => ({ data: null })),
                    api.get('/leads/llamadas-pendientes').catch(() => ({ data: { llamadas: [] } })),
                ]);
                setStats(statsRes.data);
                setUpcoming(upcomingRes.data.upcoming || []);
                setClients(clientsRes.data || []);
                setCadence(cadenceRes.data.items || []);
                setRevisiones(revisionesRes.data.items || []);
                setTodo(todoRes.data || null);
                setLlamadas(llamadasRes.data?.llamadas || []);
            } catch (error) {
                console.error('Error fetching dashboard:', error);
                toast.error('Error al cargar dashboard');
            } finally {
                setLoading(false);
            }
        };
        fetchAll();
        const fetchNotif = async () => {
            try {
                const [leadsRes, msgsRes] = await Promise.all([
                    api.get('/leads/stats/summary'),
                    api.get('/messages/unread-count'),
                ]);
                setNotif({ leads: leadsRes.data?.nuevo || 0, messages: msgsRes.data?.count || 0 });
            } catch { /* silencioso */ }
        };
        fetchNotif();
        const id = setInterval(fetchNotif, 60000);
        return () => clearInterval(id);
    }, [api]);

    if (loading) {
        return (
            <div className="p-4 md:p-6 bg-[#0A0A0A] min-h-screen">
                <div className="animate-pulse space-y-4">
                    <div className="h-8 bg-[#222] rounded w-1/2 md:w-1/4" />
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                        {[1,2,3,4,5].map(i => <div key={i} className="h-28 bg-[#111] rounded-xl" />)}
                    </div>
                    <div className="h-48 bg-[#111] rounded-xl" />
                </div>
            </div>
        );
    }

    // Todos los planes con clientes activos, mayor a menor.
    const planEntries = Object.entries(stats?.plans || {}).sort((a, b) => b[1] - a[1]);
    const totalPlanActive = planEntries.reduce((a, [, n]) => a + n, 0);
    const planLabel = (code) => planCatalog?.[code]?.name || (code === 'sin_plan' ? 'Sin plan' : code);
    const planColor = (code) => PLAN_COLORS[code] || '#666666';
    const pendingReports = cadence.filter(i => i.status !== 'enviado');

    return (
        <div className="p-4 md:p-6 space-y-5 md:space-y-6 animate-fade-in bg-[#0A0A0A] min-h-screen" data-testid="admin-dashboard">
            {/* Header */}
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight" style={{ fontFamily: 'Barlow Condensed' }}>PANEL DE CONTROL</h1>
                    <p className="text-white/40 text-sm">Estado del negocio en tiempo real</p>
                </div>
                <div className="relative flex-shrink-0">
                    <Button variant="outline" size="icon" onClick={() => setNotifOpen(o => !o)}
                        className="bg-transparent border-white/20 hover:border-[#FF671F]" data-testid="notif-bell">
                        <Bell className="w-4 h-4 text-white" />
                    </Button>
                    {(notif.leads + notif.messages) > 0 && (
                        <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] px-1 flex items-center justify-center pointer-events-none">
                            {notif.leads + notif.messages > 99 ? '99+' : notif.leads + notif.messages}
                        </span>
                    )}
                    {notifOpen && (
                        <>
                            <div className="fixed inset-0 z-40" onClick={() => setNotifOpen(false)} />
                            <div className="absolute right-0 top-11 z-50 w-72 bg-[#111] border border-[#333] rounded-xl shadow-xl overflow-hidden" data-testid="notif-dropdown">
                                <p className="px-4 py-2.5 text-[10px] font-bold text-white/40 uppercase tracking-wider border-b border-[#222]">Novedades</p>
                                <button onClick={() => { setNotifOpen(false); navigate('/admin/leads'); }}
                                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 text-left">
                                    <UserPlus className="w-4 h-4 text-[#FF671F]" />
                                    <span className="text-white text-sm flex-1">Leads nuevos sin gestionar</span>
                                    <span className={`text-xs font-bold ${notif.leads > 0 ? 'text-red-400' : 'text-white/30'}`}>{notif.leads}</span>
                                </button>
                                <button onClick={() => { setNotifOpen(false); navigate('/admin/messages'); }}
                                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 text-left border-t border-[#1A1A1A]">
                                    <MessageCircle className="w-4 h-4 text-[#FF671F]" />
                                    <span className="text-white text-sm flex-1">Mensajes sin leer</span>
                                    <span className={`text-xs font-bold ${notif.messages > 0 ? 'text-red-400' : 'text-white/30'}`}>{notif.messages}</span>
                                </button>
                                {(notif.leads + notif.messages) === 0 && (
                                    <p className="px-4 py-3 text-white/30 text-xs border-t border-[#1A1A1A]">Todo al día</p>
                                )}
                            </div>
                        </>
                    )}
                </div>
            </div>

            {/* Piden llamada (Nivel 3): por encima de los KPIs porque hay gente esperando */}
            <LlamadasPendientes llamadas={llamadas} onAtendida={marcarLlamadaAtendida}
                onCobrar={generarEnlacePago} generandoEnlace={generandoEnlace} />

            {/* KPI Row */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3" data-testid="kpi-row">
                <KpiCard value={stats?.total_clients || 0} label="Clientes totales" icon={Users} color="#FF671F" testId="kpi-total" />
                <KpiCard value={stats?.active_clients || 0} label="Activos" icon={UserCheck} color="#22C55E" testId="kpi-active" />
                {/* Antes ponía "En riesgo" y saltaba para tres de cada cuatro activos, así
                    que no era una alerta: era el color de fondo de la pantalla. Y sobre
                    todo no decía EN QUÉ. Ahora el número son los que tienen algo en rojo, y
                    debajo va desglosado por celda, que es lo accionable (punto 32). */}
                <KpiCard value={stats?.at_risk_clients || 0} label="Con algo en rojo" icon={AlertTriangle} color="#EAB308" testId="kpi-risk"
                    pie={stats?.semaforo && (
                        <span className="flex flex-wrap items-center gap-x-2 text-[10px] tabular-nums text-white/50 mt-0.5" data-testid="kpi-semaforo">
                            <span>reporte <b className="text-red-400">{stats.semaforo.reporte?.malo || 0}</b></span>
                            <span>peso <b className="text-red-400">{stats.semaforo.peso?.malo || 0}</b></span>
                            <span>contacto <b className="text-red-400">{stats.semaforo.contacto?.malo || 0}</b></span>
                            <span>ajuste <b className="text-red-400">{stats.semaforo.ajuste?.malo || 0}</b></span>
                        </span>
                    )} />
                <KpiCard value={stats?.inactive_clients || 0} label="Bajas" icon={UserMinus} color="#EF4444" testId="kpi-bajas" />
                <KpiCard value={`${stats?.mrr || 0}€`} label="MRR" icon={DollarSign} color="#8B5CF6" testId="kpi-mrr" />
            </div>

            {/* "Esta semana te tocan estos seis" (punto 29). Va antes del resto del panel:
                es lo primero que se pregunta un lunes. */}
            <EstaSemanaTeTocan items={todo?.te_tocan} navigate={navigate} />

            {/* Por hacer esta semana (tarea 19) */}
            <TodoSemana todo={todo} soloAlCorriente={soloAlCorriente} setSoloAlCorriente={setSoloAlCorriente}
                navigate={navigate} />

            {/* Plan Distribution */}
            <Card className="bg-[#111111] border-[#222]" data-testid="plan-distribution">
                <CardContent className="p-5">
                    <p className="text-xs font-bold text-white/40 uppercase tracking-wider mb-4">Distribución por plan</p>
                    <div className="flex flex-col gap-3">
                        {/* Bar */}
                        <div className="w-full flex h-8 rounded-lg overflow-hidden bg-[#1A1A1A]">
                            {planEntries.map(([plan, count]) => {
                                const pct = totalPlanActive > 0 ? (count / totalPlanActive) * 100 : 0;
                                if (pct === 0) return null;
                                return (
                                    <div
                                        key={plan}
                                        className="h-full flex items-center justify-center text-xs font-bold transition-all"
                                        style={{ width: `${pct}%`, backgroundColor: planColor(plan), color: '#fff', minWidth: '40px' }}
                                        title={`${planLabel(plan)}: ${count}`}
                                    >
                                        {count}
                                    </div>
                                );
                            })}
                        </div>
                        {/* Legend */}
                        <div className="flex flex-wrap gap-x-3 gap-y-1.5">
                            {planEntries.map(([plan, count]) => (
                                <div key={plan} className="flex items-center gap-1.5">
                                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: planColor(plan) }} />
                                    <span className="text-xs text-white/50 uppercase">{planLabel(plan)}</span>
                                    <span className="text-xs font-bold text-white">{count}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Reportes del coach que tocan esta semana.
                OCULTO temporalmente (a petición del usuario, 20-07): reactivar quitando el
                `false &&` cuando el panel esté mejorado. */}
            {false && (
            <Card className="bg-[#111111] border-[#222]" data-testid="report-cadence">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center justify-between">
                        <span className="text-base text-white uppercase tracking-wider flex items-center gap-2">
                            <FileText className="w-4 h-4 text-[#FF671F]" />
                            Reportes de esta semana
                        </span>
                        <Badge className={`border-0 text-xs ${pendingReports.length > 0 ? 'bg-[#FF671F]/20 text-[#FF671F]' : 'bg-green-500/10 text-green-500'}`}>
                            {pendingReports.length > 0 ? `${pendingReports.length} por enviar` : 'Al día'}
                        </Badge>
                    </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                    {cadence.length === 0 ? (
                        <p className="text-white/30 text-sm text-center py-4">Ningún cliente tiene reporte programado esta semana</p>
                    ) : (
                        <div className="space-y-2">
                            {cadence.map((item, i) => (
                                <div key={`${item.client_id}-${item.tipo}-${item.due_date}`}
                                    className="flex items-center justify-between gap-2 p-3 bg-[#0A0A0A] rounded-lg border border-[#222] hover:border-[#FF671F]/30 transition-colors"
                                    data-testid={`cadence-${i}`}>
                                    <div className="flex items-center gap-3 min-w-0">
                                        <Badge className={`border-0 text-[10px] flex-shrink-0 ${
                                            item.status === 'vencido' ? 'bg-red-500/15 text-red-400'
                                            : item.status === 'enviado' ? 'bg-green-500/10 text-green-500'
                                            : 'bg-yellow-500/10 text-yellow-500'
                                        }`}>
                                            {item.status}
                                        </Badge>
                                        <div className="min-w-0 cursor-pointer" onClick={() => navigate(`/admin/clients/${item.client_id}`)}>
                                            <p className="text-white text-sm font-medium truncate">{item.client_name || item.client_email}</p>
                                            <p className="text-white/40 text-xs truncate">
                                                {item.tipo_label} · {item.due_label} {new Date(item.due_date).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })} · semana {item.week}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
                                        <span className="hidden sm:inline"><PlanBadge plan={item.plan} planName={item.plan_name} /></span>
                                        {item.status === 'enviado' ? (
                                            <Button variant="ghost" size="sm" className="text-white/40 hover:text-white text-xs uppercase"
                                                onClick={() => markReport(item, false)}>
                                                Desmarcar
                                            </Button>
                                        ) : (
                                            <Button size="sm" className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs uppercase"
                                                onClick={() => markReport(item, true)} data-testid={`mark-sent-${i}`}>
                                                Marcar enviado
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
            )}

            {/* Macros por revisar (motor v2): dieta reportada que no cuadra con lo recomendado */}
            <Card className="bg-[#111111] border-[#222]" data-testid="macro-revisiones">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center justify-between">
                        <span className="text-base text-white uppercase tracking-wider flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4 text-[#FF671F]" />
                            Macros por revisar
                        </span>
                        <Badge className={`border-0 text-xs ${revisiones.length > 0 ? 'bg-[#FF671F]/20 text-[#FF671F]' : 'bg-green-500/10 text-green-500'}`}>
                            {revisiones.length > 0 ? `${revisiones.length} pendientes` : 'Al día'}
                        </Badge>
                    </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                    {revisiones.length === 0 ? (
                        <p className="text-white/30 text-sm text-center py-4">Ninguna dieta reportada pendiente de revisar</p>
                    ) : (
                        <div className="space-y-2">
                            {revisiones.map((rev, i) => (
                                <div key={rev.id}
                                    className="flex items-center justify-between gap-2 p-3 bg-[#0A0A0A] rounded-lg border border-[#222] hover:border-[#FF671F]/30 transition-colors"
                                    data-testid={`revision-${i}`}>
                                    <div className="min-w-0 cursor-pointer" onClick={() => rev.client_id && navigate(`/admin/clients/${rev.client_id}`)}>
                                        <p className="text-white text-sm font-medium truncate">{rev.client_name}</p>
                                        <p className="text-white/40 text-xs truncate">
                                            Come {Math.round(rev.comparacion?.hc_reportados || 0)} g de HC · recomendado {rev.comparacion?.hc_recomendados} g
                                            · diferencia {rev.comparacion?.diferencia > 0 ? '+' : ''}{rev.comparacion?.diferencia} g
                                            · {new Date(rev.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}
                                        </p>
                                    </div>
                                    <Button size="sm" className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs uppercase flex-shrink-0"
                                        onClick={() => resolverRevision(rev)} data-testid={`revision-resolver-${i}`}>
                                        Revisada
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Upcoming Payments */}
            <Card className="bg-[#111111] border-[#222]" data-testid="upcoming-payments">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center justify-between">
                        <span className="text-base text-white uppercase tracking-wider flex items-center gap-2">
                            <CreditCard className="w-4 h-4 text-[#FF671F]" />
                            Próximos cobros (7 días)
                        </span>
                        <Badge className="bg-[#FF671F]/20 text-[#FF671F] border-0 text-xs">{upcoming.length}</Badge>
                    </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                    {upcoming.length === 0 ? (
                        <p className="text-white/30 text-sm text-center py-4">No hay cobros programados en los próximos 7 días</p>
                    ) : (
                        <div className="space-y-2">
                            {upcoming.map((u, i) => {
                                const payDate = u.next_payment ? new Date(u.next_payment) : null;
                                const daysLeft = payDate ? Math.ceil((payDate - new Date()) / (1000 * 60 * 60 * 24)) : '?';
                                return (
                                    <div key={i} className="flex items-center justify-between gap-2 p-3 bg-[#0A0A0A] rounded-lg border border-[#222] hover:border-[#FF671F]/30 transition-colors" data-testid={`upcoming-${i}`}>
                                        <div className="flex items-center gap-3 min-w-0">
                                            <div className="w-9 h-9 bg-[#FF671F]/10 rounded-lg flex items-center justify-center flex-shrink-0">
                                                <span className="text-[#FF671F] font-bold text-sm" style={{ fontFamily: 'Barlow Condensed' }}>{daysLeft}d</span>
                                            </div>
                                            <div className="min-w-0">
                                                <p className="text-white text-sm font-medium truncate">{u.name}</p>
                                                <p className="text-white/40 text-xs">{payDate ? payDate.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }) : '-'}</p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
                                            <PlanBadge plan={u.plan} />
                                            <span className="text-[#FF671F] font-bold text-lg" style={{ fontFamily: 'Barlow Condensed' }}>{u.price != null ? `${u.price}€` : '-'}</span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Client List (compact) */}
            <Card className="bg-[#111111] border-[#222]" data-testid="client-list-compact">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center justify-between">
                        <span className="text-base text-white uppercase tracking-wider flex items-center gap-2">
                            <Users className="w-4 h-4 text-[#FF671F]" />
                            Clientes ({clients.length})
                        </span>
                        <Button variant="ghost" size="sm" className="text-[#FF671F] hover:bg-[#FF671F]/10 uppercase text-xs" onClick={() => navigate('/admin/clients')}>
                            Ver todos <ChevronRight className="w-3 h-3 ml-1" />
                        </Button>
                    </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                    <div className="space-y-1.5">
                        {clients.slice(0, 8).map(c => (
                            <div
                                key={c.id}
                                className="flex items-center justify-between gap-2 p-2.5 rounded-lg hover:bg-white/5 cursor-pointer transition-colors"
                                onClick={() => navigate(`/admin/clients/${c.id}`)}
                                data-testid={`client-row-${c.id}`}
                            >
                                <div className="flex items-center gap-3 min-w-0">
                                    <div className="w-8 h-8 bg-[#222] rounded-lg flex items-center justify-center flex-shrink-0">
                                        <span className="text-[#FF671F] font-bold text-xs">{c.user?.name?.charAt(0)}</span>
                                    </div>
                                    <div className="min-w-0">
                                        <p className="text-white text-sm font-medium truncate">{c.user?.name}</p>
                                        <p className="text-white/30 text-xs truncate">{c.user?.email}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2 flex-shrink-0">
                                    <PlanBadge plan={c.plan} />
                                    <Badge className={c.status === 'activo' ? 'bg-green-500/10 text-green-500 border-0 text-[10px]' : 'bg-red-500/10 text-red-400 border-0 text-[10px]'}>
                                        {c.status || 'sin estado'}
                                    </Badge>
                                </div>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

// KPI Card Component
const KpiCard = ({ value, label, icon: Icon, color, testId, pie = null }) => (
    <Card className="bg-[#111111] border-[#222]" data-testid={testId}>
        <CardContent className="p-4">
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-3xl font-bold mt-1" style={{ fontFamily: 'Barlow Condensed', color }}>{value}</p>
                    <p className="text-[10px] text-white/40 uppercase tracking-wider mt-1">{label}</p>
                    {pie}
                </div>
                <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}15` }}>
                    <Icon className="w-4 h-4" style={{ color }} />
                </div>
            </div>
        </CardContent>
    </Card>
);

// Admin Clients List
const AdminClientsList = () => {
    const { api, user } = useAuth();
    const navigate = useNavigate();
    const [clients, setClients] = useState([]);
    const [trainers, setTrainers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [planFilter, setPlanFilter] = useState('all');
    // Cartera: cada coach lleva la suya, y los que no tienen coach quedan a la vista de
    // todos para que cualquiera pueda cogerlos (documento del 06-08-2026). El admin
    // arranca viéndolo todo; el coach, en los suyos.
    const esAdmin = user?.role === 'admin';
    const [cartera, setCartera] = useState(esAdmin ? 'todos' : 'mios');
    // Orden de la tabla (punto 29): por defecto como venía, y "sin tocar" pone arriba a los
    // que llevan más tiempo sin que les muevan los macros. Desde la home se llega ya
    // ordenado así (/admin/clients?orden=sin_tocar).
    const [orden, setOrden] = useState(
        new URLSearchParams(window.location.search).get('orden') === 'sin_tocar' ? 'sin_tocar' : 'ninguno');

    useEffect(() => {
        fetchClients();
        // eslint-disable-next-line react-hooks/exhaustive-deps -- correr al montar y al cambiar planFilter
    }, [planFilter]);

    useEffect(() => {
        api.get('/admin/trainers').then(r => setTrainers(r.data || [])).catch(() => {});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const trainerName = (id) => trainers.find(t => t.id === id)?.name || id;

    // Un coach solo puede asignarse clientes sin coach (el backend tambien lo valida)
    const assignMe = async (e, clientId) => {
        e.stopPropagation();
        try {
            await api.put(`/admin/clients/${clientId}/trainer`, { trainer_id: user.id });
            toast.success('Cliente asignado');
            fetchClients();
        } catch (err) {
            toast.error(err.response?.data?.detail || 'No se pudo asignar el cliente');
        }
    };

    const fetchClients = async () => {
        try {
            const params = planFilter !== 'all' ? `?plan=${planFilter}` : '?include_incomplete=true';
            const response = await api.get(`/admin/clients${params}`);
            setClients(response.data);
        } catch (error) {
            console.error('Error fetching clients:', error);
            toast.error('Error al cargar clientes');
        } finally {
            setLoading(false);
        }
    };

    const deLaCartera = (c) => {
        if (cartera === 'sin_coach') return !c.trainer_id;
        if (cartera === 'mios') return c.trainer_id === user?.id;
        return true;
    };

    const filteredClients = clients.filter(c => deLaCartera(c) && (
        c.user?.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.user?.email?.toLowerCase().includes(searchQuery.toLowerCase())
    ));
    // Días desde el último ajuste. El que no tiene ninguno va arriba del todo: es
    // justamente el que se pierde cuando esto se lleva en una hoja aparte.
    if (orden === 'sin_tocar') {
        filteredClients.sort((a, b) => {
            const da = diasSinTocar(a), dbb = diasSinTocar(b);
            if (da === null) return dbb === null ? 0 : -1;
            if (dbb === null) return 1;
            return dbb - da;
        });
    }

    const cuantos = (cual) => clients.filter(c =>
        cual === 'sin_coach' ? !c.trainer_id : cual === 'mios' ? c.trainer_id === user?.id : true).length;

    const CARTERAS = esAdmin
        ? [['todos', 'Todos'], ['sin_coach', 'Sin coach']]
        : [['mios', 'Mis clientes'], ['sin_coach', 'Sin coach']];

    return (
        <div className="p-6 space-y-6 animate-fade-in bg-[#0A0A0A] min-h-screen">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="heading-2 text-white">CLIENTES</h1>
                    <p className="text-white/50 uppercase tracking-wider text-sm">{filteredClients.length} {filteredClients.length === 1 ? 'cliente' : 'clientes'}</p>
                </div>
            </div>

            {/* Mi cartera / los que no lleva nadie */}
            <div className="inline-flex rounded-lg bg-[#111111] p-0.5 border border-[#333]">
                {CARTERAS.map(([valor, etiqueta]) => (
                    <button key={valor} onClick={() => setCartera(valor)}
                        data-testid={`cartera-${valor}`}
                        className={`px-4 py-1.5 text-xs font-bold rounded-md transition-colors ${cartera === valor ? 'bg-[#FF671F] text-white' : 'text-white/50 hover:text-white'}`}>
                        {etiqueta} <span className="opacity-60">({cuantos(valor)})</span>
                    </button>
                ))}
            </div>

            {/* Filters */}
            <div className="flex flex-col md:flex-row gap-4">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <Input
                        placeholder="Buscar cliente..."
                        className="pl-10 bg-[#111111] border-[#333] text-white placeholder:text-white/30 focus:border-[#FF671F]"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        data-testid="client-search"
                    />
                </div>
                <Select value={planFilter} onValueChange={setPlanFilter}>
                    <SelectTrigger className="w-[180px] bg-[#111111] border-[#333] text-white" data-testid="plan-filter">
                        <SelectValue placeholder="Filtrar por plan" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#111111] border-[#333]">
                        <SelectItem value="all">Todos los planes</SelectItem>
                        <SelectItem value="gold">Gold</SelectItem>
                        <SelectItem value="silver">Silver</SelectItem>
                        <SelectItem value="bronze">Bronze</SelectItem>
                        <SelectItem value="elm">ELM</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            {/* Clients Table */}
            <Card className="bg-[#111111] border-[#222222]">
                <CardContent className="p-0">
                    {loading ? (
                        <div className="p-8 text-center">
                            <div className="animate-spin w-8 h-8 border-2 border-[#FF671F] border-t-transparent rounded-full mx-auto"></div>
                        </div>
                    ) : filteredClients.length > 0 ? (
                        <Table>
                            <TableHeader>
                                <TableRow className="border-[#333] hover:bg-transparent">
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs">Cliente</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs">Plan</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden md:table-cell">Precio</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden md:table-cell">Semana</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden sm:table-cell">Coach</TableHead>
                                    {/* Punto 29: la columna que contesta "¿quién me toca esta
                                        semana?". Se pincha para ordenar por ella. */}
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden lg:table-cell">
                                        <button onClick={() => setOrden(orden === 'sin_tocar' ? 'ninguno' : 'sin_tocar')}
                                            data-testid="orden-sin-tocar"
                                            className={`uppercase tracking-wider text-xs hover:text-white ${orden === 'sin_tocar' ? 'text-[#FF671F]' : ''}`}
                                            title="Días desde el último ajuste de macros">
                                            Sin tocar {orden === 'sin_tocar' ? '↓' : ''}
                                        </button>
                                    </TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden xl:table-cell">Últ. reporte</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden xl:table-cell">Contacto</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden lg:table-cell">Peso</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs">Estado</TableHead>
                                    <TableHead className="text-right text-white/50 uppercase tracking-wider text-xs">Acciones</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {filteredClients.map((client) => (
                                    <TableRow
                                        key={client.id || client.user_id}
                                        className={`border-[#222] cursor-pointer hover:bg-[#1A1A1A] ${!client.id ? 'opacity-70' : ''}`}
                                        onClick={() => client.id
                                            ? navigate(`/admin/clients/${client.id}`)
                                            : toast.info(`${client.user?.name || client.user?.email} se registró pero no completó el alta (no eligió plan). Aún no tiene ficha.`)}
                                    >
                                        <TableCell>
                                            <div>
                                                <p className="font-medium text-white">{client.user?.name}</p>
                                                <p className="text-sm text-white/50">{client.user?.email}</p>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            {client.id ? <PlanBadge plan={client.plan} /> : <span className="text-white/30 text-sm">-</span>}
                                        </TableCell>
                                        <TableCell className="font-bold text-[#FF671F] hidden md:table-cell" style={{ fontFamily: 'Barlow Condensed' }}>
                                            {client.id && client.price != null ? `${client.price}€` : '-'}
                                        </TableCell>
                                        <TableCell className="hidden md:table-cell">
                                            {client.id ? (
                                                <Badge variant="outline" className="border-[#333] text-white">
                                                    Sem {client.week}
                                                </Badge>
                                            ) : <span className="text-white/30 text-sm">-</span>}
                                        </TableCell>
                                        <TableCell className="hidden sm:table-cell">
                                            {client.trainer_id ? (
                                                <span className="text-sm text-white/70">{trainerName(client.trainer_id)}</span>
                                            ) : client.id && user?.role === 'trainer' ? (
                                                <Button size="sm" onClick={(e) => assignMe(e, client.id)}
                                                    className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs h-7 px-2"
                                                    data-testid={`assign-me-${client.id}`}>
                                                    Asignarme
                                                </Button>
                                            ) : (
                                                <span className="text-sm text-white/30">Sin asignar</span>
                                            )}
                                        </TableCell>
                                        {/* Las cuatro celdas del semáforo (punto 32). El color y
                                            el texto vienen calculados del backend, medidos contra
                                            el plazo del plan de cada cliente: aquí solo se pintan. */}
                                        <TableCell className="hidden lg:table-cell" data-testid={`sin-tocar-${client.id || client.user_id}`}>
                                            <CeldaSemaforo celda={client.semaforo?.ajuste} />
                                        </TableCell>
                                        <TableCell className="hidden xl:table-cell">
                                            <CeldaSemaforo celda={client.semaforo?.reporte} />
                                        </TableCell>
                                        <TableCell className="hidden xl:table-cell">
                                            <CeldaSemaforo celda={client.semaforo?.contacto} />
                                        </TableCell>
                                        <TableCell className="hidden lg:table-cell">
                                            <CeldaSemaforo celda={client.semaforo?.peso} />
                                        </TableCell>
                                        <TableCell>
                                            {client.status === 'registro_incompleto' ? (
                                                <Badge className="bg-yellow-500/15 text-yellow-400 border-0">Registro incompleto</Badge>
                                            ) : (
                                                <Badge className={client.status === 'activo' ? 'bg-green-500/20 text-green-500 border-0' : 'bg-[#333] text-white/50 border-0'}>
                                                    {client.status || 'sin estado'}
                                                </Badge>
                                            )}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <Button variant="ghost" size="sm" className="text-white/50 hover:text-[#FF671F]">
                                                <ChevronRight className="w-4 h-4" />
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    ) : (
                        <div className="p-8 text-center">
                            <Users className="w-12 h-12 text-white/20 mx-auto mb-4" />
                            <p className="text-white/50">No se encontraron clientes</p>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
};

// Admin Layout
const AdminLayout = () => {
    const { user, logout, api } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    // Aviso de leads nuevos y mensajes sin leer: sondeo cada 60s; badges en el menu
    const [newLeadsCount, setNewLeadsCount] = useState(0);
    const [unreadMessages, setUnreadMessages] = useState(0);
    const [moreOpen, setMoreOpen] = useState(false); // drawer "Más" en movil
    const prevLeadsCount = useRef(null);

    // Cerrar el drawer "Más" al navegar entre secciones
    useEffect(() => { setMoreOpen(false); }, [location.pathname]);
    useEffect(() => {
        let active = true;
        const poll = async () => {
            try {
                const r = await api.get('/leads/stats/summary');
                if (!active) return;
                const count = r.data?.nuevo || 0;
                setNewLeadsCount(count);
                if (prevLeadsCount.current !== null && count > prevLeadsCount.current) {
                    toast.info(`Lead nuevo recibido · ${count} sin gestionar`, {
                        action: { label: 'Ver', onClick: () => navigate('/admin/leads') },
                    });
                }
                prevLeadsCount.current = count;
            } catch { /* silencioso: sin red o sesion caducada */ }
            try {
                const m = await api.get('/messages/unread-count');
                if (active) setUnreadMessages(m.data?.count || 0);
            } catch { /* silencioso */ }
        };
        poll();
        const id = setInterval(poll, 60000);
        return () => { active = false; clearInterval(id); };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [api]);

    // adminOnly: solo el admin lo ve; un entrenador no gestiona usuarios/staff.
    const navItems = [
        { path: '/admin', icon: LayoutDashboard, label: 'Dashboard', exact: true },
        { path: '/admin/clients', icon: Users, label: 'Clientes' },
        { path: '/admin/planes', icon: Layers, label: 'Planes' },
        { path: '/admin/usuarios', icon: UserCheck, label: 'Usuarios', adminOnly: true },
        { path: '/admin/leads', icon: UserPlus, label: 'Leads' },
        { path: '/admin/messages', icon: MessageCircle, label: 'Mensajes' },
        { path: '/admin/routines', icon: Dumbbell, label: 'Rutinas' },
        { path: '/admin/menus', icon: Utensils, label: 'Menús' },
        { path: '/admin/alimentos', icon: Apple, label: 'Alimentos' },
    ].filter((i) => !i.adminOnly || user?.role === 'admin');

    // En movil la barra inferior muestra 4 accesos + boton "Mas" (el resto va al drawer).
    const primaryPaths = ['/admin', '/admin/clients', '/admin/leads', '/admin/messages'];
    const primaryNav = navItems.filter((i) => primaryPaths.includes(i.path));
    const secondaryNav = navItems.filter((i) => !primaryPaths.includes(i.path));

    const isActive = (path, exact = false) => {
        if (exact) return location.pathname === path;
        return location.pathname.startsWith(path);
    };

    // Drawer móvil (menú hamburguesa), como en modo cliente
    const [drawerOpen, setDrawerOpen] = useState(false);
    useEffect(() => { setDrawerOpen(false); }, [location.pathname]);

    // Barra inferior móvil: solo los 4 accesos principales; el resto va en el drawer
    const bottomItems = navItems.filter(i =>
        ['/admin', '/admin/clients', '/admin/leads', '/admin/messages'].includes(i.path));

    const badgeFor = (item) => {
        if (item.path === '/admin/leads' && newLeadsCount > 0) return newLeadsCount;
        if (item.path === '/admin/messages' && unreadMessages > 0) return unreadMessages;
        return 0;
    };

    const handleLogout = () => {
        logout();
        navigate('/auth');
        toast.success('Sesión cerrada');
    };

    return (
        <div className="min-h-screen bg-[#0A0A0A] flex">
            {/* Sidebar (desktop) - misma estructura y estilo que el sidebar del modo cliente */}
            <aside className="w-64 bg-[#0A0A0A] border-r border-white/10 h-screen sticky top-0 hidden lg:flex flex-col flex-shrink-0">
                <div className="flex items-center justify-between h-16 px-4 border-b border-white/10">
                    <JG12Logo size="sm" />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#FF671F] bg-[#FF671F]/10 border border-[#FF671F]/25 rounded-md px-2 py-0.5">Admin</span>
                </div>

                <nav className="flex-1 overflow-y-auto no-scrollbar p-3 space-y-1">
                    {navItems.map((item) => (
                        <Link
                            key={item.path}
                            to={item.path}
                            className={`relative flex items-center gap-3 rounded-xl px-3.5 py-2.5 transition-all ${
                                isActive(item.path, item.exact)
                                    ? 'bg-[#FF671F] text-white font-semibold'
                                    : 'text-white/60 hover:text-white hover:bg-white/[0.07]'
                            }`}
                        >
                            <item.icon className="w-5 h-5 flex-shrink-0" strokeWidth={2} />
                            <span className="text-sm">{item.label}</span>
                            {item.path === '/admin/leads' && newLeadsCount > 0 && (
                                <span className="ml-auto bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] px-1 flex items-center justify-center" data-testid="new-leads-badge">
                                    {newLeadsCount > 99 ? '99+' : newLeadsCount}
                                </span>
                            )}
                            {item.path === '/admin/messages' && unreadMessages > 0 && (
                                <span className="ml-auto bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] px-1 flex items-center justify-center" data-testid="unread-messages-badge">
                                    {unreadMessages > 99 ? '99+' : unreadMessages}
                                </span>
                            )}
                        </Link>
                    ))}
                </nav>

                <div className="p-3 border-t border-white/10 space-y-2">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-[#FF671F]/15 rounded-xl flex items-center justify-center flex-shrink-0">
                            <span className="text-[#FF671F] font-bold font-heading text-lg">{user?.name?.charAt(0)?.toUpperCase()}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="font-semibold text-white text-sm truncate">{user?.name}</p>
                            <Badge className="bg-[#FF671F]/20 text-[#FF671F] border-0 text-xs uppercase">{user?.role}</Badge>
                        </div>
                    </div>
                    <button
                        onClick={() => navigate('/dashboard')}
                        data-testid="use-app-btn"
                        className="flex items-center gap-2 w-full rounded-lg px-3 py-2.5 text-white/50 hover:text-[#FF671F] hover:bg-[#FF671F]/10 transition-colors"
                    >
                        <Utensils className="w-4 h-4" /> <span className="text-sm">Usar app (modo cliente)</span>
                    </button>
                    <button
                        onClick={handleLogout}
                        className="flex items-center gap-2 w-full rounded-lg px-3 py-2.5 text-white/50 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    >
                        <LogOut className="w-4 h-4" /> <span className="text-sm">Cerrar sesión</span>
                    </button>
                </div>
            </aside>

            {/* Main Content: scrollea la página entera (como en modo cliente),
                con barra superior móvil de hamburguesa */}
            <div className="flex-1 min-w-0 flex flex-col">
                <header className="lg:hidden sticky top-0 z-40 bg-[#0A0A0A] border-b border-white/10 h-14 flex items-center justify-between px-4">
                    <button onClick={() => setDrawerOpen(true)} data-testid="admin-mobile-menu-btn"
                        className="w-10 h-10 -ml-2 rounded-lg flex items-center justify-center text-white/80 hover:bg-white/10">
                        <Menu className="w-6 h-6" />
                    </button>
                    <JG12Logo size="sm" />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#FF671F] bg-[#FF671F]/10 border border-[#FF671F]/25 rounded-md px-2 py-0.5">Admin</span>
                </header>
                <main className="flex-1 min-w-0 pb-20 lg:pb-0">
                    <Outlet />
                </main>
            </div>

            {/* Mobile bottom nav: 4 accesos principales + "Más" (drawer), como en modo cliente */}
            <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-50 bg-[#0A0A0A] border-t border-white/10" data-testid="admin-mobile-nav">
                <div className="flex items-stretch h-16">
                    {bottomItems.map((item) => {
                        const active = isActive(item.path, item.exact);
                        const badge = badgeFor(item);
                        return (
                            <Link key={item.path} to={item.path}
                                className={`relative flex flex-col items-center justify-center flex-1 gap-1 transition-colors ${active ? 'text-[#FF671F]' : 'text-white/55'}`}
                            >
                                <span className="relative">
                                    <item.icon className="w-[22px] h-[22px]" strokeWidth={active ? 2.5 : 2} />
                                    {badge > 0 && (
                                        <span className="absolute -top-1.5 -right-2 min-w-4 h-4 px-1 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center font-bold">
                                            {badge > 99 ? '99+' : badge}
                                        </span>
                                    )}
                                </span>
                                <span className={`text-[10px] ${active ? 'font-bold' : 'font-medium'}`}>{item.label}</span>
                            </Link>
                        );
                    })}
                    <button onClick={() => setDrawerOpen(true)} data-testid="admin-bottomnav-mas"
                        className="flex flex-col items-center justify-center flex-1 gap-1 text-white/55">
                        <Menu className="w-[22px] h-[22px]" strokeWidth={2} />
                        <span className="text-[10px] font-medium">Más</span>
                    </button>
                </div>
            </nav>

            {/* Mobile drawer (hamburguesa), como en modo cliente */}
            {drawerOpen && (
                <div className="lg:hidden fixed inset-0 z-[60]" data-testid="admin-mobile-drawer">
                    <div className="absolute inset-0 bg-black/50 animate-fade-in" onClick={() => setDrawerOpen(false)} />
                    <div className="absolute inset-y-0 left-0 w-[82%] max-w-xs bg-[#0A0A0A] flex flex-col animate-slide-up">
                        <div className="flex items-center justify-between h-14 px-4 border-b border-white/10">
                            <JG12Logo size="sm" />
                            <button onClick={() => setDrawerOpen(false)} data-testid="admin-drawer-close"
                                className="w-9 h-9 rounded-lg flex items-center justify-center text-white/60 hover:bg-white/10">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <nav className="flex-1 overflow-y-auto no-scrollbar p-3 space-y-1">
                            {navItems.map((item) => {
                                const active = isActive(item.path, item.exact);
                                const badge = badgeFor(item);
                                return (
                                    <Link key={item.path} to={item.path} onClick={() => setDrawerOpen(false)}
                                        className={`relative flex items-center gap-3 rounded-xl px-3.5 py-2.5 transition-all ${active ? 'bg-[#FF671F] text-white font-semibold' : 'text-white/60 hover:text-white hover:bg-white/[0.07]'}`}
                                    >
                                        <item.icon className="w-5 h-5 flex-shrink-0" strokeWidth={2} />
                                        <span className="text-sm">{item.label}</span>
                                        {badge > 0 && (
                                            <span className="ml-auto bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] px-1 flex items-center justify-center">
                                                {badge > 99 ? '99+' : badge}
                                            </span>
                                        )}
                                    </Link>
                                );
                            })}
                        </nav>
                        <div className="p-3 border-t border-white/10 space-y-2">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 bg-[#FF671F]/15 rounded-xl flex items-center justify-center flex-shrink-0">
                                    <span className="text-[#FF671F] font-bold font-heading text-lg">{user?.name?.charAt(0)?.toUpperCase()}</span>
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="font-semibold text-white text-sm truncate">{user?.name}</p>
                                    <Badge className="bg-[#FF671F]/20 text-[#FF671F] border-0 text-xs uppercase">{user?.role}</Badge>
                                </div>
                            </div>
                            <button onClick={() => navigate('/dashboard')}
                                className="flex items-center gap-2 w-full rounded-lg px-3 py-2.5 text-white/50 hover:text-[#FF671F] hover:bg-[#FF671F]/10 transition-colors">
                                <Utensils className="w-4 h-4" /> <span className="text-sm">Usar app (modo cliente)</span>
                            </button>
                            <button onClick={handleLogout}
                                className="flex items-center gap-2 w-full rounded-lg px-3 py-2.5 text-white/50 hover:text-red-400 hover:bg-red-500/10 transition-colors">
                                <LogOut className="w-4 h-4" /> <span className="text-sm">Cerrar sesión</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export { AdminDashboard, AdminClientsList, AdminLayout };
