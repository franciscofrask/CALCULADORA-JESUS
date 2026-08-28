import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, Outlet, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { PlanBadge, JG12Logo } from './ClientDashboard';
import LimiteDeError from '../components/LimiteDeError';
import { AvisosDelEquipo, PeticionesDeCompra } from '../components/AvisosDelEquipo';
import { prettyToken } from '../lib/labels';
import { estadoClienteLabel, estadoDeAcceso } from '../lib/labels';
import { contarClientes, contarRegistrosSinTerminar, cuentaComoCliente } from '../lib/cuentaClientes';
import AsignarTarea from '../components/AsignarTarea';
import {
    LayoutDashboard, Users, CreditCard, Dumbbell,
    MessageCircle, LogOut, Search, Bell,
    ChevronRight, DollarSign, FileText,
    AlertTriangle, UserCheck, UserMinus, UserPlus, Utensils, Apple, Layers,
    Menu, X, Phone, Receipt, ClipboardList, CalendarClock, Gauge, SlidersHorizontal
} from 'lucide-react';
import { mensajeDeError } from '../lib/mensajeDeError';

// Colores para el desglose por plan (cualquier plan sin color cae en el gris).
// UN COLOR POR PLAN, Y NINGUNO SIN COLOR. Faltaban los cuatro que se venden hoy y los que
// llegaron el 17-08 desde Calma (Reto 12en12, Plan Personalizado, Básica): salían todos en
// el mismo gris de «desconocido», y en un reparto por colores dos planes del mismo gris son
// un plan. `calma` (sin normalizar) comparte el de CALMA 12 porque son el mismo.
const PLAN_COLORS = {
    nivel1: '#F59E0B', nivel2: '#FF671F', nivel3: '#DC2626', membresia: '#0EA5E9',
    reto12en12_gold: '#EAB308', gold: '#EAB308',
    reto12en12_silver: '#9CA3AF', silver: '#9CA3AF',
    bronze: '#C2410C', elm: '#FF671F', reto60: '#22C55E',
    calculadora_jp: '#3B82F6', mantenimiento: '#8B5CF6',
    premium: '#EC4899', plan_6m: '#14B8A6', sin_plan: '#555555',
    reto12en12: '#A16207', personalizado: '#7C3AED', basica: '#64748B',
    calma12: '#06B6D4', CalMa: '#06B6D4', calma: '#06B6D4',
};

// Panel "Por hacer esta semana": tres columnas accionables (sin macros / sin rutina /
// reporte pendiente), con filtro por clientes al corriente de pago (tarea 19).
const TodoSemana = ({ todo, soloAlCorriente, setSoloAlCorriente, navigate }) => {
    if (!todo) return null;
    const flt = (arr) => (arr || []).filter(c => !soloAlCorriente || c.al_corriente);
    // «SIN RUTINA» NO ES UNA LISTA DE PENDIENTES SI ESTÁN TODOS.
    //
    // Con 227 de 228 en rojo, esa columna no ayuda a priorizar: no es trabajo pendiente, es el
    // estado de la casa, y ocupa un cuarto de la mejor herramienta del panel. Jesús, 11-08:
    // «si es verdad, no es un aviso: es el estado normal, y conviene sacarlo de la lista de
    // pendientes hasta que se empiecen a poner rutinas».
    // Vuelve sola en cuanto deje de serlo: el criterio es que falten menos de nueve de cada
    // diez. Y no se esconde nada, porque la pantalla de Rutinas la lista entera.
    const conRutinaEnPlan = Number(todo.con_rutina_en_plan || 0);
    const sinRutina = todo.sin_rutina || [];
    const rutinaEsLoNormal = conRutinaEnPlan > 0 && sinRutina.length >= conRutinaEnPlan * 0.9;

    const cols = [
        { key: 'macros', label: 'Sin macros', icon: Apple, color: '#FF671F', sub: 'Necesitan macros del entrenador', items: flt(todo.sin_macros) },
        ...(rutinaEsLoNormal ? [] : [
            /* «SIN PONER» Y NO «SIN UNA ACTIVA» (puntos 67 y 69, 28-08). Desde hoy esta
               columna cuenta también la rutina entregada en PDF, igual que la pantalla de
               Rutinas, así que «sin una activa» describía la cuenta vieja: al que tiene su
               PDF no le falta rutina, le falta estar en la tabla de rutinas estructuradas,
               que es otra cosa y no es trabajo pendiente de nadie. */
            { key: 'rutina', label: 'Sin rutina', icon: Dumbbell, color: '#3B82F6', sub: 'Plan con rutina y ninguna puesta', items: flt(sinRutina) },
        ]),
        { key: 'reportes', label: 'Reporte pendiente', icon: FileText, color: '#EAB308', sub: 'No enviado esta semana', items: flt(todo.reporte_pendiente) },
        // «No puedo esta semana»: avisaron con el botón, así que no ensucian la lista de
        // los que faltan (doc 19-08). Con lo que hayan escrito, y en rojo el que ya lleva
        // dos seguidos (ese además dispara la tarea automática de contactarle).
        ...((todo.reporte_aplazado || []).length ? [
            { key: 'aplazados', label: 'Aplazados a la semana que viene', icon: CalendarClock, color: '#22C55E', sub: 'Pidieron aplazarlo: han avisado', items: flt(todo.reporte_aplazado) },
        ] : []),
        // «Sin contacto» NO SE PINTA (doc 21-08). El dato solo cuenta el chat interno y
        // el webhook de GHL: ni el feedback de reportes ni los ajustes de macros cuentan
        // como contacto, así que «177 · nunca» era falso. Fuera hasta que el contacto se
        // pueda registrar de verdad; el backend sigue mandando `sin_contacto` por si acaso.
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
                                        className="w-full px-2 py-1.5 rounded-lg hover:bg-white/5 text-left">
                                        <span className="flex items-center gap-2 w-full">
                                        <span className="flex-1 min-w-0 truncate text-sm text-white/80">{c.name}</span>
                                        {col.key === 'reportes' && c.overdue && <span className="text-[9px] text-red-400 font-bold uppercase tracking-wide">tarde</span>}
                                        {col.key === 'aplazados' && c.seguidos >= 2 && <span className="text-[9px] text-red-400 font-bold uppercase tracking-wide">{c.seguidos} seguidos</span>}
                                        {!c.al_corriente && <span title="Pago pendiente" className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />}
                                        <ChevronRight className="w-3.5 h-3.5 text-white/20 flex-shrink-0" />
                                        </span>
                                        {/* Lo que escribió al aplazar («¿Quieres decirme algo?»), debajo del nombre. */}
                                        {col.key === 'aplazados' && c.nota && (
                                            <span className="block text-[11px] text-white/40 italic truncate" title={c.nota}>«{c.nota}»</span>
                                        )}
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

// El dinero se escribe como en Paneles > Dirección: miles con punto, sin decimales y el
// euro detrás. Es la misma receta que el `eur()` de AdminPanelesPage.jsx, a propósito.
const eurosRedondos = (n) => (n === null || n === undefined || isNaN(Number(n)))
    ? '0 €'
    : `${new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 }).format(Number(n))} €`;

// Admin Dashboard Home
const AdminDashboard = () => {
    const { api, planCatalog, user } = useAuth();
    const navigate = useNavigate();
    // EL DINERO, SOLO AL ADMIN (P62, doc 23-08). El entrenador también entra en esta
    // portada, y aquí le salían el MRR, los próximos cobros con importes y los avisos de
    // pagos. La regla ya regía en las secciones; ahora también aquí, y el backend además
    // ha dejado de mandarle los importes (no es solo esconderlos).
    const esAdmin = user?.role === 'admin';
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
    // Avisos del sistema: cobros fallidos, bajas automáticas y reportes vencidos. Se venían
    // guardando desde marzo y NO SE ENSEÑABAN EN NINGUNA PANTALLA (14-08-2026): el endpoint
    // existía, el panel no lo pedía, y lo único que veía el equipo de un cobro fallido era
    // que el cliente dejaba de estar activo.
    const [avisos, setAvisos] = useState([]);

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
            toast.error(mensajeDeError(e, 'No se pudo crear el enlace de pago'));
        } finally {
            setGenerandoEnlace(null);
        }
    };

    // Los que van uno a uno (cuestan dinero, los mira una persona) y los que van contados.
    // Los graves primero: un cobro fallido antes que una tarjeta que caduca el mes que viene.
    const avisosDeReportes = avisos.filter(a => a.type === 'report_overdue');
    const avisosSueltos = avisos
        .filter(a => a.type !== 'report_overdue')
        .sort((a, b) => (a.severity === 'critical' ? 0 : 1) - (b.severity === 'critical' ? 0 : 1));

    // Dar por visto un aviso. Desaparece de la lista en cuanto se pulsa: la respuesta del
    // servidor no cambia nada en pantalla y esperarla solo hace que el botón parezca roto.
    const cerrarAviso = async (aviso) => {
        setAvisos(prev => prev.filter(a => a.id !== aviso.id));
        try {
            await api.post(`/admin/stripe/alerts/${aviso.id}/resolve`);
        } catch {
            toast.error('No se pudo cerrar el aviso');
            setAvisos(prev => [aviso, ...prev]);   // se devuelve a su sitio
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

    // Campana: novedades reales (leads nuevos sin gestionar + mensajes sin leer + los avisos
    // que el backend le deja al equipo, que hasta ahora se escribían y no los leía nadie).
    const [notif, setNotif] = useState({ leads: 0, messages: 0, equipo: 0, ventas: 0 });
    const [notifOpen, setNotifOpen] = useState(false);

    // Los avisos del equipo, con su lista y todo, EN LA PÁGINA y no dentro de la campana:
    // las peticiones de compra se pintan además como tarjeta arriba, y para eso hacen falta
    // aquí. Una venta que solo se ve abriendo un desplegable depende de que a alguien se le
    // ocurra abrirlo.
    const [avisosEquipo, setAvisosEquipo] = useState({ items: [], cargando: true, error: false });

    // Los contadores de la campana, cada uno por su lado: si falla el de leads, los avisos
    // del equipo se siguen contando. En un solo try, una llamada mala dejaba la campana a
    // cero, que se lee como "no hay nada".
    const fetchNotif = useCallback(async () => {
        const pedir = (url) => api.get(url).then(r => r.data).catch(e => {
            console.error('Campana:', url, e);
            return null;
        });
        const [leads, msgs, equipo] = await Promise.all([
            pedir('/leads/stats/summary'),
            pedir('/messages/unread-count'),
            pedir('/notifications/equipo'),
        ]);
        if (equipo) {
            setAvisosEquipo({
                items: Array.isArray(equipo.notifications) ? equipo.notifications : [],
                cargando: false, error: false,
            });
        } else {
            setAvisosEquipo(prev => ({ ...prev, cargando: false, error: true }));
        }
        setNotif(prev => ({
            leads: leads ? (leads.nuevo || 0) : prev.leads,
            messages: msgs ? (msgs.count || 0) : prev.messages,
            // El número sale de la MISMA lista que se pinta: con dos fuentes, el globo dice
            // tres y la lista enseña dos, y entonces no te crees ninguno de los dos.
            equipo: equipo ? (equipo.unread || 0) : prev.equipo,
            ventas: equipo ? (equipo.dinero_sin_leer || 0) : prev.ventas,
        }));
    }, [api]);

    /** Marca un aviso del equipo como leído (al abrirlo o al despacharlo desde la tarjeta). */
    const marcarAvisoEquipo = useCallback(async (aviso) => {
        if (!aviso || aviso.read) return;
        setAvisosEquipo(prev => ({
            ...prev,
            items: prev.items.map(a => (a.id === aviso.id ? { ...a, read: true } : a)),
        }));
        setNotif(prev => ({
            ...prev,
            equipo: Math.max(0, prev.equipo - 1),
            ventas: aviso.dinero ? Math.max(0, prev.ventas - 1) : prev.ventas,
        }));
        try {
            await api.put(`/notifications/equipo/${aviso.id}/read`);
        } catch (e) {
            // Al usuario no se le cuenta: el aviso sigue en la base y vuelve en el próximo
            // repaso. El detalle, a la consola.
            console.error('No se pudo marcar el aviso del equipo:', e);
        }
    }, [api]);

    /** Abrir un aviso: se da por leído y se va a la ficha del cliente, si la tiene. */
    const abrirAvisoEquipo = useCallback((aviso) => {
        marcarAvisoEquipo(aviso);
        if (aviso?.link) {
            setNotifOpen(false);
            navigate(aviso.link);
        }
    }, [marcarAvisoEquipo, navigate]);

    const marcarTodosLosAvisosEquipo = useCallback(async () => {
        try {
            await api.put('/notifications/equipo/read-all');
            setAvisosEquipo(prev => ({ ...prev, items: prev.items.map(a => ({ ...a, read: true })) }));
            setNotif(prev => ({ ...prev, equipo: 0, ventas: 0 }));
        } catch (e) {
            console.error('No se pudieron marcar los avisos del equipo:', e);
            toast.error('No se han podido marcar como leídos');
        }
    }, [api]);

    // El reparto por plan enseña los que se venden; los antiguos, aquí detrás.
    const [verAntiguos, setVerAntiguos] = useState(false);

    useEffect(() => {
        const fetchAll = async () => {
            try {
                const [statsRes, upcomingRes, clientsRes, cadenceRes, revisionesRes, todoRes, llamadasRes, avisosRes] = await Promise.all([
                    api.get('/admin/dashboard-stats'),
                    // Los próximos cobros son dinero: al entrenador ni se le piden (el
                    // backend le contestaría 403 igualmente).
                    esAdmin ? api.get('/admin/upcoming-payments') : Promise.resolve({ data: { upcoming: [] } }),
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

                // Los avisos del sistema (cobros fallidos, bajas, reportes vencidos) se piden
                // DESPUÉS y no dentro del grupo de arriba: es la llamada a la cadencia la que
                // crea los de reporte vencido y la que caduca los de semanas pasadas, así que
                // pedidos a la vez se enseñaría la lista de antes de ese repaso.
                // Los avisos de pagos (cobros fallidos, bajas por impago, tarjetas) son
                // dinero: solo para el admin (P62).
                if (esAdmin) {
                    try {
                        const avisosRes = await api.get('/admin/stripe/alerts', { params: { resolved: false } });
                        setAvisos(Array.isArray(avisosRes.data) ? avisosRes.data : []);
                    } catch { /* sin avisos: la tarjeta se queda vacía, no rompe el panel */ }
                }
            } catch (error) {
                console.error('Error fetching dashboard:', error);
                toast.error('Error al cargar dashboard');
            } finally {
                setLoading(false);
            }
        };
        fetchAll();
        fetchNotif();
        const id = setInterval(fetchNotif, 60000);
        return () => clearInterval(id);
    }, [api, fetchNotif, esAdmin]);

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
    const totalNotif = notif.leads + notif.messages + notif.equipo;

    // Los que están a la venta, cada uno con su trozo. Los que ya no se venden se juntan en
    // uno solo: siguen contando en el total y siguen listados debajo, pero no se llevan
    // catorce franjas de la barra. Sin minWidth: el ancho es el porcentaje y nada más, que
    // para eso es una barra de reparto.
    const pctDe = (n) => (totalPlanActive > 0 ? (n / totalPlanActive) * 100 : 0);
    const seVende = (code) => planCatalog?.[code]?.estado === 'activo';
    const antiguos = planEntries.filter(([plan]) => !seVende(plan));
    const antiguosTotal = antiguos.reduce((a, [, n]) => a + n, 0);
    // LA BARRA PINTA LOS PLANES QUE TIENE LA GENTE, NO LOS QUE ESTÁN A LA VENTA
    // (Francisco, 17-08: «no hay distribución de color, el 176 está en gris»).
    //
    // Se dibujaba un trozo por plan EN VENTA y el resto en un gris común. Como hoy los
    // cuatro que se venden tienen cero clientes -- todo el mundo viene de Calma y está en un
    // plan legacy --, la barra entera era un solo bloque gris con el total dentro: un
    // gráfico de reparto que no repartía nada. Ahora salen los seis mayores con su color y
    // la cola se junta, que es lo que decía este comentario desde el principio.
    const TOPE_BARRA = 6;
    const conGente = planEntries.filter(([, count]) => count > 0);
    const cola = conGente.slice(TOPE_BARRA);
    const colaTotal = cola.reduce((a, [, n]) => a + n, 0);
    const barraPlanes = [
        ...conGente.slice(0, TOPE_BARRA).map(([plan, count]) => ({
            plan, count, pct: pctDe(count), color: planColor(plan), label: planLabel(plan),
        })),
        ...(colaTotal > 0 ? [{
            plan: '__cola__', count: colaTotal, pct: pctDe(colaTotal), color: '#3F3F46',
            label: `Otros ${cola.length} planes: ${cola.map(([p, n]) => `${planLabel(p)} ${n}`).join(' · ')}`,
        }] : []),
    ];

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
                        className={`bg-transparent hover:border-[#FF671F] ${
                            notif.ventas > 0 ? 'border-[#FF671F]' : 'border-white/20'}`} data-testid="notif-bell">
                        <Bell className={`w-4 h-4 ${notif.ventas > 0 ? 'text-[#FF671F]' : 'text-white'}`} />
                    </Button>
                    {totalNotif > 0 && (
                        <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] px-1 flex items-center justify-center pointer-events-none">
                            {totalNotif > 99 ? '99+' : totalNotif}
                        </span>
                    )}
                    {notifOpen && (
                        <>
                            <div className="fixed inset-0 z-40" onClick={() => setNotifOpen(false)} />
                            <div className="absolute right-0 top-11 z-50 w-[min(21rem,calc(100vw-2rem))] max-h-[70vh] overflow-y-auto bg-[#111] border border-[#333] rounded-xl shadow-xl" data-testid="notif-dropdown">
                                {/* «Avisos» también aquí (Jesús, 18-08): es la misma campana
                                    con el mismo nombre a los dos lados de la app. */}
                                <p className="px-4 py-2.5 text-[10px] font-bold text-white/40 uppercase tracking-wider border-b border-[#222]">Avisos</p>
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
                                {totalNotif === 0 && (
                                    <p className="px-4 py-3 text-white/30 text-xs border-t border-[#1A1A1A]">Todo al día</p>
                                )}
                                {/* Los avisos que el backend le escribe al equipo, que hasta
                                    ahora no leía nadie. */}
                                <AvisosDelEquipo estado={avisosEquipo} onAbrir={abrirAvisoEquipo}
                                    onMarcarTodos={marcarTodosLosAvisosEquipo} />
                            </div>
                        </>
                    )}
                </div>
            </div>

            {/* Piden comprar: lo de la campana, además, aquí fuera. Un cliente que marca la
                rutina del mes o «Cuéntame el Silver» está pidiendo comprar, y eso no puede
                depender de que alguien abra un desplegable. */}
            <PeticionesDeCompra estado={avisosEquipo} onAbrir={abrirAvisoEquipo}
                onAtendida={marcarAvisoEquipo} />

            {/* Piden llamada (Nivel 3): por encima de los KPIs porque hay gente esperando */}
            <LlamadasPendientes llamadas={llamadas} onAtendida={marcarLlamadaAtendida}
                onCobrar={generarEnlacePago} generandoEnlace={generandoEnlace} />

            {/* KPI Row */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3" data-testid="kpi-row">
                <KpiCard value={stats?.total_clients || 0} label="Clientes totales" icon={Users} color="#FF671F" testId="kpi-total" />
                {/* P63: activos = con acceso vigente, el MISMO criterio que la pestaña
                    «Activos» de Clientes. Los marcados «activo» sin acceso van debajo,
                    con su nombre, para que este número cuadre con aquella lista. */}
                <KpiCard value={stats?.active_clients || 0} label="Activos" icon={UserCheck} color="#22C55E" testId="kpi-active"
                    pie={stats?.caducados_clients > 0 ? (
                        <span className="text-[10px] text-white/50 mt-0.5" data-testid="kpi-caducados">
                            y {stats.caducados_clients} caducados
                        </span>
                    ) : null} />
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
                            <span>perfil <b className="text-red-400">{stats.semaforo.perfil_largo?.malo || 0}</b></span>
                        </span>
                    )} />
                {/* Punto 2.4g: «"0 bajas" con 188 totales y 184 activos: faltan cuatro por
                    algún sitio». Los que no son ni activos ni bajas -- pendiente de pago,
                    checkout sin terminar -- no aparecían en ninguna casilla, y un total que
                    no cuadra con sus partes tira por tierra el panel entero. */}
                <KpiCard value={stats?.inactive_clients || 0} label="Bajas" icon={UserMinus} color="#EF4444" testId="kpi-bajas"
                    pie={stats?.otros_clients ? (
                        // Y CON NOMBRE, que la suma ya cuadraba pero «ni activos ni de
                        // baja» no le dice a nadie qué hacer con ellos (punto 63, QA del
                        // 15-08). «4 pendientes de pago · 1 registrado» sí.
                        <span className="text-[10px] text-white/50 mt-0.5" data-testid="kpi-otros">
                            + {stats.otros_clients}{' '}
                            {stats.otros_por_estado?.length
                                ? stats.otros_por_estado
                                    .map((o) => `${o.n} ${prettyToken(o.estado).toLowerCase()}`)
                                    .join(' · ')
                                : 'ni activos ni de baja'}
                        </span>
                    ) : null} />
                {/* El MRR es dinero: solo admin (P62). Al entrenador el backend ni se lo manda.
                    Y ES EL MISMO NÚMERO QUE «FACTURA AL MES» DE PANELES > DIRECCIÓN (punto 46
                    del 24-08): eran dos cuentas distintas y daban 20.062 € y 31.945 € de los
                    mismos clientes el mismo día. Ahora las dos salen de la misma función y del
                    mismo cobro real, así que si vuelven a discrepar es que algo se ha roto. */}
                {/* Y ESCRITO IGUAL QUE ALLÍ, que si no la comprobación no se puede hacer de
                    un vistazo: aquí ponía «22485.53€» y Dirección «22.486 €». Es el mismo
                    dinero, pero con el punto de los decimales a la inglesa y sin miles no lo
                    parece, y el punto 46 va justo de leer dos pantallas y creerlas. */}
                {esAdmin && (
                    <KpiCard value={eurosRedondos(stats?.mrr)} label="MRR" icon={DollarSign} color="#8B5CF6" testId="kpi-mrr"
                        pie={stats?.mrr_criterio && (
                            <span className="text-[10px] text-white/50 mt-0.5" data-testid="kpi-mrr-criterio">
                                {stats.mrr_criterio.clientes} con acceso · {stats.mrr_criterio.cobro_real} con cobro real
                                <span className="block text-white/30">Igual que «Factura al mes» de Dirección</span>
                            </span>
                        )} />
                )}
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
                        {/* LA BARRA MENTÍA CON 17 PLANES.
                            Cada trozo llevaba minWidth 40px, así que los planes de uno o dos
                            clientes se inflaban hasta ocupar lo mismo que uno de cuarenta, la
                            suma se pasaba del ancho y el reparto que se veía no era el real.
                            Ahora la barra dibuja los seis primeros a escala de verdad y junta
                            la cola en un trozo gris, que es como se lee un reparto. El detalle
                            no se pierde: la leyenda de abajo sigue listando los 17 con su
                            número (Jesús, 11-08). */}
                        <div className="w-full flex h-8 rounded-lg overflow-hidden bg-[#1A1A1A]">
                            {barraPlanes.map(({ plan, count, pct, color, label }) => (
                                <div
                                    key={plan}
                                    className="h-full flex items-center justify-center text-xs font-bold transition-all overflow-hidden"
                                    style={{ width: `${pct}%`, backgroundColor: color, color: '#fff' }}
                                    title={`${label}: ${count}`}
                                >
                                    {/* Por debajo de un 6% no cabe el número sin pisar al vecino. */}
                                    {pct >= 6 ? count : ''}
                                </div>
                            ))}
                        </div>
                        {/* La leyenda es la de la barra: los mismos seis y sus colores. Antes
                            listaba solo los planes en venta y, con todos los clientes en planes
                            legacy, se quedaba vacía debajo de una barra llena. El resto sigue
                            detrás del desplegable de abajo, con su número. */}
                        <div className="flex flex-wrap gap-x-3 gap-y-1.5">
                            {barraPlanes.filter(({ plan }) => plan !== '__cola__').map(({ plan, count }) => (
                                <div key={plan} className="flex items-center gap-1.5">
                                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: planColor(plan) }} />
                                    <span className="text-xs text-white/50 uppercase">{planLabel(plan)}</span>
                                    <span className="text-xs font-bold text-white">{count}</span>
                                    {!seVende(plan) && <span className="text-[10px] text-white/25">legacy</span>}
                                </div>
                            ))}
                        </div>
                        {antiguos.length > 0 && (
                            <div>
                                <button type="button" onClick={() => setVerAntiguos(v => !v)}
                                    data-testid="ver-planes-antiguos"
                                    className="text-xs text-white/40 hover:text-white/70 underline underline-offset-2">
                                    {verAntiguos
                                        ? 'Ocultar los planes que ya no se venden'
                                        : `Ver los ${antiguos.length} planes que ya no se venden (${antiguosTotal} clientes)`}
                                </button>
                                {verAntiguos && (
                                    <div className="flex flex-wrap gap-x-3 gap-y-1.5 mt-2.5">
                                        {antiguos.map(([plan, count]) => (
                                            <div key={plan} className="flex items-center gap-1.5">
                                                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: planColor(plan) }} />
                                                <span className="text-xs text-white/40 uppercase">{planLabel(plan)}</span>
                                                <span className="text-xs font-bold text-white/70">{count}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
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

            {/* AVISOS DEL SISTEMA. Solo sale si hay alguno: una tarjeta que pone «todo bien»
                todos los días acaba siendo invisible el día que pone otra cosa.

                LOS DE REPORTE VENCIDO VAN CONTADOS, NO EN LISTA. Se crea uno por cliente y por
                semana, así que aquí eran 95 de 99 avisos, todos con el mismo texto, tapando los
                cuatro que de verdad hay que mirar. Quién va con retraso ya se ve en «Por hacer
                esta semana», y estos se cierran solos a las tres semanas.

                Lo que sí va uno a uno es lo que cuesta dinero y necesita a una persona: un
                cobro que ha fallado, una baja automática o una tarjeta caducada. */}
            {esAdmin && avisos.length > 0 && (
            <Card className="bg-[#111111] border-[#222]" data-testid="avisos-sistema">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center justify-between">
                        <span className="text-base text-white uppercase tracking-wider flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4 text-[#FF671F]" />
                            Avisos
                        </span>
                        <Badge className={`border-0 text-xs ${avisosSueltos.length > 0 ? 'bg-[#FF671F]/20 text-[#FF671F]' : 'bg-green-500/10 text-green-500'}`}>
                            {avisosSueltos.length > 0
                                ? (avisosSueltos.length === 1 ? '1 por mirar' : `${avisosSueltos.length} por mirar`)
                                : 'Nada urgente'}
                        </Badge>
                    </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                    <div className="space-y-2">
                        {avisosSueltos
                            .map((aviso, i) => {
                                const grave = aviso.severity === 'critical';
                                const cliente = clients.find(c => c.id === aviso.client_id);
                                return (
                                    <div key={aviso.id} data-testid={`aviso-${i}`}
                                        className={`flex items-start justify-between gap-3 p-3 bg-[#0A0A0A] rounded-lg border transition-colors ${
                                            grave ? 'border-red-500/40 hover:border-red-500/70' : 'border-[#222] hover:border-[#FF671F]/30'}`}>
                                        <div className="min-w-0 cursor-pointer"
                                            onClick={() => aviso.client_id && navigate(`/admin/clients/${aviso.client_id}`)}>
                                            <p className="text-white text-sm font-medium truncate">
                                                {aviso.title}
                                                {cliente?.name && <span className="text-white/40 font-normal"> · {cliente.name}</span>}
                                            </p>
                                            <p className="text-white/40 text-xs">{aviso.message}</p>
                                            <p className="text-white/25 text-[11px] mt-0.5">
                                                {new Date(aviso.created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })}
                                            </p>
                                        </div>
                                        <Button size="sm" variant="ghost" data-testid={`aviso-cerrar-${i}`}
                                            className="text-white/50 hover:text-white hover:bg-white/10 text-xs uppercase flex-shrink-0"
                                            onClick={() => cerrarAviso(aviso)}>
                                            Visto
                                        </Button>
                                    </div>
                                );
                            })}
                    </div>

                    {/* Esta frase nació de coletilla de la lista de arriba, y por eso empezaba
                        por «Y». El 24-08, en producción, los 105 avisos abiertos eran TODOS de
                        reporte vencido: la lista salía vacía y la tarjeta se quedaba con una
                        línea suelta que arrancaba por «Y», sin nada delante a lo que sumarse.
                        Si no hay avisos sueltos, la frase se sostiene sola. */}
                    {avisosDeReportes.length > 0 && (
                        <p className={`text-white/35 text-xs ${avisosSueltos.length > 0 ? 'pt-3' : ''}`}
                            data-testid="avisos-reportes-contados">
                            {avisosSueltos.length > 0 ? 'Y' : 'Hay'} {avisosDeReportes.length} reporte{avisosDeReportes.length === 1 ? '' : 's'} de coach
                            sin marcar como enviado{avisosDeReportes.length === 1 ? '' : 's'}.{' '}
                            {avisosDeReportes.length === 1 ? 'Se cierra solo' : 'Se cierran solos'} a las tres semanas.
                        </p>
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
                                    {/* «Revisada» a secas se leia como el estado de la fila,
                                        no como el boton que la resuelve. */}
                                    <Button size="sm" className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs uppercase flex-shrink-0"
                                        onClick={() => resolverRevision(rev)} data-testid={`revision-resolver-${i}`}>
                                        Marcar revisada
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Upcoming Payments: importes de cobro, solo admin (P62) */}
            {esAdmin && (
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
            )}

            {/* Client List (compact) */}
            <Card className="bg-[#111111] border-[#222]" data-testid="client-list-compact">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center justify-between">
                        <span className="text-base text-white uppercase tracking-wider flex items-center gap-2">
                            <Users className="w-4 h-4 text-[#FF671F]" />
                            Clientes ({contarClientes(clients)})
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
                                    {(() => {
                                        const e = estadoDeAcceso(c);
                                        return (
                                            <Badge className={`${e.tono === 'ok' ? 'bg-green-500/10 text-green-500'
                                                : e.tono === 'aviso' ? 'bg-yellow-500/10 text-yellow-400'
                                                : 'bg-red-500/10 text-red-400'} border-0 text-[10px]`}>
                                                {e.texto}
                                            </Badge>
                                        );
                                    })()}
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

// LOS QUE DE VERDAD NO LLEVA NADIE (punto 61 del doc del 24-08).
//
// Lo decide el SERVIDOR (`sin_entrenador` de /admin/clients), con el mismo criterio que
// Paneles > Operaciones: sin entrenador asignado Y con un plan que lleve entrenador detrás.
// Aquí se miraba solo `trainer_id`, así que la pestaña decía 83 donde Operaciones decía 10:
// los 73 de diferencia son ELM, Mantenimiento y Calculadora JP, planes de autogestión que no
// tienen entrenador QUE ASIGNAR. Dos consultas para la misma pregunta, una en el servidor y
// otra en el navegador, y solo una miraba el plan.
//
// Si la fila viene sin el campo (un backend viejo detrás), se cae al criterio de antes: es
// preferible una pestaña de más que una pestaña vacía sin explicación.
const leFaltaEntrenador = (c) => (
    c?.sin_entrenador !== undefined ? !!c.sin_entrenador : !c?.trainer_id);

// Admin Clients List
const AdminClientsList = () => {
    // `planCatalog` lo usa el filtro de planes de más abajo. Faltaba aquí -- lo sacaba solo
    // AdminDashboard, que es otro componente y otro ámbito -- y la pantalla entera reventaba
    // con «planCatalog is not defined» nada más entrar en /admin/clients.
    const { api, user, planCatalog } = useAuth();
    const navigate = useNavigate();
    const [clients, setClients] = useState([]);
    const [trainers, setTrainers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [planFilter, setPlanFilter] = useState('all');
    // Cartera: cada coach lleva la suya, y los que no tienen coach quedan a la vista de
    // todos para que cualquiera pueda cogerlos (documento del 06-08-2026). Se abre por los
    // que no lleva nadie, que es lo que hay que repartir; si no hay ninguno, por la vista
    // general, porque abrir en una lista vacía no le dice nada a nadie (ver CARTERAS).
    const esAdmin = user?.role === 'admin';
    const general = esAdmin ? 'todos' : 'mios';
    const [cartera, setCartera] = useState('sin_coach');
    // Se abre en «Activos»: lo que se mira a diario son los que estan dentro, y los
    // caducados estaban mezclados sin forma de distinguirlos.
    const [acceso, setAcceso] = useState('activos');
    const carteraElegida = useRef(false);
    // Orden de la tabla (punto 29): por defecto como venía, y "sin tocar" pone arriba a los
    // que llevan más tiempo sin que les muevan los macros. Desde la home se llega ya
    // ordenado así (/admin/clients?orden=sin_tocar).
    const [orden, setOrden] = useState(
        new URLSearchParams(window.location.search).get('orden') === 'sin_tocar' ? 'sin_tocar' : 'ninguno');
    // ASIGNAR A VARIOS DE GOLPE (doc 19-08, apartado 05): «los nueve que renuevan el 21 de
    // septiembre: los marcas, "contactar", a Jenny, y ya está». Las casillas seleccionan y
    // la barra de abajo abre el formulario con todos dentro.
    const [seleccionados, setSeleccionados] = useState(new Set());
    const [modalTarea, setModalTarea] = useState(false);
    const alternar = (id) => setSeleccionados(s => {
        const n = new Set(s);
        n.has(id) ? n.delete(id) : n.add(id);
        return n;
    });

    useEffect(() => {
        fetchClients();
        // eslint-disable-next-line react-hooks/exhaustive-deps -- correr al montar y al cambiar planFilter
    }, [planFilter]);

    useEffect(() => {
        api.get('/admin/trainers').then(r => setTrainers(r.data || [])).catch(() => {});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Al llegar la lista: si no hay nadie sin entrenador, la pestaña de arriba no tiene
    // nada que enseñar y se pasa a la general. Solo la primera vez -- después manda lo
    // que haya pulsado el usuario.
    useEffect(() => {
        if (carteraElegida.current || loading || !clients.length) return;
        carteraElegida.current = true;
        if (!clients.some(leFaltaEntrenador)) setCartera(general);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [loading, clients]);

    const trainerName = (id) => trainers.find(t => t.id === id)?.name || id;

    // Un coach solo puede asignarse clientes sin coach (el backend tambien lo valida)
    const assignMe = async (e, clientId) => {
        e.stopPropagation();
        try {
            await api.put(`/admin/clients/${clientId}/trainer`, { trainer_id: user.id });
            toast.success('Cliente asignado');
            fetchClients();
        } catch (err) {
            toast.error(mensajeDeError(err, 'No se pudo asignar el cliente'));
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
        if (cartera === 'sin_coach') return leFaltaEntrenador(c);
        if (cartera === 'mios') return c.trainer_id === user?.id;
        return true;
    };

    // ACTIVOS Y CADUCADOS, SEPARADOS (Francisco, 17-08-2026: «aparta en el panel los
    // usuarios activos de los inactivos»). Se mira `acceso`, que lo calcula el servidor con
    // la misma regla que la puerta de la app, no el `status` del perfil: en producción hay
    // 57 marcados «activo» a los que la app ya no deja entrar, y mezclados en la misma
    // lista no hay forma de saber a quién estás mirando.
    //
    // OJO AL LEER ESTE COMENTARIO: hasta el 24-08 acababa diciendo que los registros a
    // medias «salen solo en Todos», y ya no es verdad -- desde el cambio de abajo van a
    // «Fuera» con los caducados. Se corrige aquí porque la nota vieja fue justo la que
    // hizo creer que «Todos» y las pestañas contaban lo mismo.
    const tieneAcceso = (c) => (c.acceso ? c.acceso.activo : c.status === 'activo');
    // LOS QUE NO TRABAJAN VAN JUNTOS Y FUERA (Jesús, 24-08: «a los que no tienen plan sácalos
    // de la lista, ponlos en otro lado; a los caducados también, ambos en la misma lista»).
    //
    // Son dos cosas distintas y antes estaban en dos sitios distintos: el caducado tenía su
    // pestaña y el que se registró sin elegir plan salía EN GRIS dentro de «Todos», mezclado
    // con la gente a la que sí hay que atender. Para el trabajo del día da igual por qué no
    // está dentro: lo que importa es que no está. Una sola lista, «Fuera».
    const estaFuera = (c) => c.status === 'registro_incompleto' || !c.plan || !tieneAcceso(c);
    // UN SOLO CRITERIO PARA LA PESTAÑA Y PARA SU NÚMERO (la regla de lib/cuentaClientes.js).
    // Antes esto estaba escrito dos veces -- aquí para filtrar la tabla y más abajo, con otras
    // condiciones, para contar la pestaña -- y por eso los números dejaron de sumar. Ahora la
    // pregunta «¿esta fila sale en la pestaña X?» se responde en un sitio y las dos la usan.
    const esDelAcceso = (c, cual) => (cual === 'todos' ? true
        : cual === 'activos' ? !estaFuera(c) : estaFuera(c));
    const delAcceso = (c) => esDelAcceso(c, acceso);

    const filteredClients = clients.filter(c => deLaCartera(c) && delAcceso(c) && (
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

    // Las pestañas cuentan con el MISMO criterio que el contador del panel (#56): sin los
    // registros a medias y sin la ficha propia. Antes contaban filas a secas y por eso
    // «Todos» decía 182 donde el panel decía 178.
    const cuantos = (cual) => clients.filter(c => cuentaComoCliente(c) && (
        cual === 'sin_coach' ? leFaltaEntrenador(c) : cual === 'mios' ? c.trainer_id === user?.id : true)).length;
    // Los que no tienen entrenador porque su plan no lo lleva. No son un problema, pero
    // sin decirlo la pestaña pasa de 83 a 10 y parece que se han perdido 73 clientes.
    const sinCoachPorPlan = clients.filter(
        c => cuentaComoCliente(c) && !c.trainer_id && !leFaltaEntrenador(c)).length;
    const sinTerminar = contarRegistrosSinTerminar(clients);

    // LOS QUE NO LLEVA NADIE, PRIMERO.
    // «Sin entrenador: 233 de 247. Esa pestaña debería ser lo primero que se abre, no la
    // segunda» (Jesús, 11-08). Es la única de las dos que es trabajo: un cliente sin
    // entrenador no lo mira nadie. Va delante y es la que se abre; el resto está a un clic.
    // «Todos los clientes» y no «Todos» a secas: al lado hay otra pestaña que también se
    // llama «Todos» (la de acceso) y desde el arreglo del fallo 12 las dos enseñan números
    // muy distintos -- 200 contra 317 -- porque contestan a preguntas distintas: esta
    // cuenta CLIENTES y aquella cuenta FILAS, con los registros sin terminar dentro. Dos
    // botones pegados con la misma palabra y cifras que no se parecen es exactamente la
    // lectura que provocó el fallo 12; con la palabra «clientes» delante ya no hay duda.
    const CARTERAS = esAdmin
        ? [['sin_coach', 'Sin entrenador'], ['todos', 'Todos los clientes']]
        : [['sin_coach', 'Sin entrenador'], ['mios', 'Mis clientes']];

    // Cuenta con el filtro de cartera puesto: si estás mirando «Sin entrenador», los
    // números de «Activos» y «Fuera» tienen que ser los de esa cartera, no los del total.
    //
    // ESTAS TRES CUENTAS TIENEN QUE SUMAR (fallo 12 de la verificación del 24-08). Al llevar
    // los registros sin terminar a «Fuera» -- que es lo que pidió Jesús: «a los que no tienen
    // plan sácalos de la lista... a los caducados también, ambos en la misma lista» -- «Fuera»
    // empezó a contarlos y «Todos» no, porque «Todos» seguía filtrando por
    // `cuentaComoCliente`. En la app viva se leía «Activos (92) · Fuera (71) · Todos (105)», y
    // 92 + 71 no son 105: sobraban los 58 registros a medias. Peor todavía, «Todos» decía 105
    // y su propia tabla enseñaba 163 filas.
    //
    // La regla, y no se vuelve a romper: CADA NÚMERO CUENTA LAS FILAS QUE VA A ENSEÑAR SU
    // PESTAÑA -- menos la ficha del propio miembro del equipo, que se ve pero no cuenta desde
    // el #56 --, con el mismo `esDelAcceso` que filtra la tabla. Activos y Fuera son las dos
    // mitades disjuntas de Todos, así que suman por construcción. Quién es CLIENTE del negocio
    // es otra pregunta distinta -- esa la contesta `cuentaComoCliente` en el total de arriba --
    // y se dice con palabras en la nota de debajo de las pestañas.
    const cuantosAcceso = (cual) => clients.filter(
        c => !c.es_tu_ficha && deLaCartera(c) && esDelAcceso(c, cual)).length;
    const ACCESOS = [['activos', 'Activos'], ['fuera', 'Fuera'], ['todos', 'Todos']];
    // Los registros a medias de la cartera que se está mirando: son los que hacen que el
    // número de las pestañas y el total de clientes de la cabecera no puedan coincidir.
    const sinTerminarEnVista = clients.filter(
        c => !c.es_tu_ficha && deLaCartera(c) && c.status === 'registro_incompleto').length;

    return (
        <div className="p-6 space-y-6 animate-fade-in bg-[#0A0A0A] min-h-screen">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="heading-2 text-white">CLIENTES</h1>
                    {/* EL TOTAL ES EL TOTAL, Y LO QUE SE ESTÁ VIENDO SE DICE APARTE (#56).
                        Aquí ponía las filas de la pestaña abierta con la etiqueta «clientes»
                        a secas: con «Sin entrenador» delante salía «180 CLIENTES» y parecía
                        otro total distinto del panel. */}
                    <p className="text-white/50 uppercase tracking-wider text-sm" data-testid="clientes-total">
                        {contarClientes(clients)} {contarClientes(clients) === 1 ? 'cliente' : 'clientes'}
                        {filteredClients.length !== contarClientes(clients) && (
                            <span className="text-white/30"> · viendo {filteredClients.length}</span>
                        )}
                    </p>
                    {/* YA NO SALEN EN GRIS EN MEDIO DE LA TABLA: están en «Fuera», con los
                        caducados. La línea se queda para que el total siga cuadrando a la
                        vista, pero ahora dice dónde encontrarlos en vez de dónde estorban. */}
                    {/* UNA FRASE ENTERA, NO MEDIA (punto 62). Empezaba por «Y», colgando de la
                        línea de arriba: pero es otro párrafo, en otro color y en otro tamaño,
                        así que se leía como si faltara el principio. Cada línea tiene que
                        entenderse sola, que es como se leen. */}
                    {sinTerminar > 0 && (
                        <p className="text-white/30 text-xs mt-0.5" data-testid="registros-sin-terminar">
                            Hay {sinTerminar} {sinTerminar === 1 ? 'registro' : 'registros'} más sin
                            terminar: {sinTerminar === 1 ? 'entró' : 'entraron'} y no{' '}
                            {sinTerminar === 1 ? 'eligió' : 'eligieron'} plan, así que no {sinTerminar === 1 ? 'cuenta' : 'cuentan'} como
                            {sinTerminar === 1 ? ' cliente' : ' clientes'}. {sinTerminar === 1 ? 'Está' : 'Están'} en «Fuera».
                        </p>
                    )}
                    {/* EL SALTO DE 83 A 10 SE EXPLICA (punto 61). La pestaña «Sin entrenador»
                        es la que se abre por defecto: sin esta línea, quien entre mañana verá
                        diez filas donde ayer había ochenta y tres y pensará lo peor. */}
                    {cartera === 'sin_coach' && sinCoachPorPlan > 0 && (
                        <p className="text-white/30 text-xs mt-0.5" data-testid="sin-coach-por-plan">
                            Aquí solo salen los que su plan lleva entrenador. Otros {sinCoachPorPlan} no
                            tienen entrenador porque su plan es de autogestión (ELM, Mantenimiento,
                            Calculadora JP): están como su plan manda y no le faltan a nadie. Es el
                            mismo criterio que Paneles &gt; Operaciones.
                        </p>
                    )}
                </div>
            </div>

            {/* Mi cartera / los que no lleva nadie, y al lado «Activos» o «Fuera» */}
            <div className="flex flex-wrap items-center gap-3">
                <div className="inline-flex rounded-lg bg-[#111111] p-0.5 border border-[#333]">
                    {CARTERAS.map(([valor, etiqueta]) => (
                        <button key={valor} onClick={() => setCartera(valor)}
                            data-testid={`cartera-${valor}`}
                            className={`px-4 py-1.5 text-xs font-bold rounded-md transition-colors ${cartera === valor ? 'bg-[#FF671F] text-white' : 'text-white/50 hover:text-white'}`}>
                            {etiqueta} <span className="opacity-60">({cuantos(valor)})</span>
                        </button>
                    ))}
                </div>
                <div className="inline-flex rounded-lg bg-[#111111] p-0.5 border border-[#333]">
                    {ACCESOS.map(([valor, etiqueta]) => (
                        <button key={valor} onClick={() => setAcceso(valor)}
                            data-testid={`acceso-${valor}`}
                            className={`px-4 py-1.5 text-xs font-bold rounded-md transition-colors ${acceso === valor ? 'bg-[#FF671F] text-white' : 'text-white/50 hover:text-white'}`}>
                            {etiqueta} <span className="opacity-60">({cuantosAcceso(valor)})</span>
                        </button>
                    ))}
                </div>
                {/* POR QUÉ LAS PESTAÑAS SUMAN MÁS QUE EL TOTAL DE CLIENTES (fallo 12). Ya suman
                    entre ellas, pero «Todos» enseña también los registros a medias y el contador
                    de clientes de la cabecera no los cuenta: son dos preguntas distintas. Los
                    números de las pestañas se leen antes que ninguna frase, así que la diferencia
                    se explica aquí al lado, con los números delante, y no en una nota suelta
                    arriba del todo. */}
                {sinTerminarEnVista > 0 && (
                    <p className="basis-full text-white/30 text-xs" data-testid="cuadre-pestanas">
                        «Todos» ({cuantosAcceso('todos')}) son Activos ({cuantosAcceso('activos')})
                        más Fuera ({cuantosAcceso('fuera')}), y ahí
                        van {sinTerminarEnVista} {sinTerminarEnVista === 1 ? 'registro' : 'registros'} sin
                        terminar que no suman al total de clientes.
                    </p>
                )}
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
                        {/* Del CATÁLOGO, no cableados (punto 40). Estaban puestos a mano los
                            cuatro de siempre, así que con 17 planes en el catálogo había 13
                            por los que no se podía filtrar - entre ellos los tres niveles
                            nuevos, que son con los que entra todo el mundo desde ahora.
                            Y en DOS bloques (2.8 del 21-08): 21 opciones en una lista plana
                            escondían los cuatro que se venden entre retirados a cero. Primero
                            lo vivo (activo/especial), y el resto agrupado en «Planes antiguos»
                            - agrupado, no quitado: los legacy siguen teniendo clientes. */}
                        {Object.entries(planCatalog || {})
                            .filter(([, p]) => p.estado !== 'complemento' && ['activo', 'especial'].includes(p.estado))
                            .map(([code, p]) => (
                                <SelectItem key={code} value={code}>{p.name}</SelectItem>
                            ))}
                        {Object.values(planCatalog || {}).some(p => p.estado !== 'complemento' && !['activo', 'especial'].includes(p.estado)) && (
                            <SelectGroup>
                                <SelectLabel className="text-white/40 text-xs uppercase tracking-wider">Planes antiguos</SelectLabel>
                                {Object.entries(planCatalog || {})
                                    .filter(([, p]) => p.estado !== 'complemento' && !['activo', 'especial'].includes(p.estado))
                                    .map(([code, p]) => (
                                        <SelectItem key={code} value={code}>{p.name}</SelectItem>
                                    ))}
                            </SelectGroup>
                        )}
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
                                    {/* La casilla de asignar en bloque (doc 19-08). La de la
                                        cabecera marca lo que se está viendo con los filtros. */}
                                    <TableHead className="w-8">
                                        <input type="checkbox" data-testid="marcar-todos"
                                            className="accent-[#FF671F] w-4 h-4 align-middle"
                                            checked={filteredClients.filter(c => c.id).length > 0
                                                && filteredClients.filter(c => c.id).every(c => seleccionados.has(c.id))}
                                            onChange={(e) => {
                                                const ids = filteredClients.filter(c => c.id).map(c => c.id);
                                                setSeleccionados(e.target.checked ? new Set(ids) : new Set());
                                            }} />
                                    </TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs">Cliente</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs">Plan</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden md:table-cell">Precio</TableHead>
                                    {/* QUIÉN RENUEVA SOLO (punto 45 del 24-08). No había ni una
                                        pantalla que lo dijera: el único sitio de todo el panel
                                        era un punto de color de seis píxeles en Dirección. */}
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden lg:table-cell">Renueva</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden md:table-cell">Semana</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden sm:table-cell">Entrenador</TableHead>
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
                                    {/* «Tiempo dentro de la app» (doc 19-08): lo que se registra
                                        hoy es su última entrada; el tiempo de verdad no lo
                                        registra nada, y el propio doc lo admite. */}
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden xl:table-cell">Entrada</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden lg:table-cell">Peso</TableHead>
                                    {/* EL PERFIL LARGO. Al que lleva entrenador no se le puede
                                        trabajar sin él, y hasta ahora la única señal era una
                                        tarjeta en SU Inicio, que es justo la que ignora. */}
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs hidden xl:table-cell">Perfil</TableHead>
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
                                        <TableCell onClick={(e) => e.stopPropagation()} className="w-8">
                                            {client.id && (
                                                <input type="checkbox" data-testid={`marcar-${client.id}`}
                                                    className="accent-[#FF671F] w-4 h-4 align-middle"
                                                    checked={seleccionados.has(client.id)}
                                                    onChange={() => alternar(client.id)} />
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <div>
                                                <p className="font-medium text-white flex items-center gap-1.5">
                                                    {client.user?.name}
                                                    {/* Punto 39: el que tiene excepción se marca aquí. Si
                                                        solo estuviera dentro de su ficha, para saber quién
                                                        tiene una habría que entrar en las 232 - o sea, lo
                                                        mismo que tenerlas en una hoja aparte. */}
                                                    {client.excepcion && (
                                                        <span title={client.excepcion} data-testid={`excepcion-${client.id}`}
                                                            className="text-[#FF671F] cursor-help"><AlertTriangle className="w-3.5 h-3.5" /></span>
                                                    )}
                                                </p>
                                                <p className="text-sm text-white/50">{client.user?.email}</p>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            {client.id ? <PlanBadge plan={client.plan} /> : <span className="text-white/30 text-sm">-</span>}
                                        </TableCell>
                                        {/* Lo que paga y el DESGLOSE AL MES (doc 19-08): «si es
                                            trimestral, lo que ese plan deja al mes». Solo se pinta
                                            cuando difiere del precio del ciclo. */}
                                        <TableCell className="hidden md:table-cell">
                                            <p className="font-bold text-[#FF671F]" style={{ fontFamily: 'Barlow Condensed' }}>
                                                {client.id && client.price != null ? `${client.price}€` : '-'}
                                            </p>
                                            {client.id && client.precio_mensual != null
                                                && client.precio_mensual !== client.price && (
                                                // Y DE DÓNDE SALE (punto 43): el «al mes» se
                                                // calcula con el último cobro real, que puede
                                                // no ser el precio de la ficha. Sin decirlo,
                                                // «450 € · 306,68 €/mes» parece una división
                                                // mal hecha.
                                                <p className="text-[11px] text-white/40"
                                                    title={client.precio_fuente === 'cobro_real'
                                                        ? 'Calculado con lo último que se le cobró de verdad, no con el precio de la ficha'
                                                        : undefined}>
                                                    {/* Con la coma de los decimales: la fila
                                                        ponía «306.68€/mes», que en castellano
                                                        son trescientos seis euros escritos a
                                                        la inglesa. */}
                                                    {Number(client.precio_mensual).toLocaleString('es-ES', { maximumFractionDigits: 2 })}€/mes
                                                    {client.precio_fuente === 'cobro_real' && (
                                                        <span className="text-white/30"> · por su último cobro</span>
                                                    )}
                                                </p>
                                            )}
                                        </TableCell>
                                        {/* Sola con Stripe detrás, «según el plan» cuando lo
                                            dice el catálogo pero no hay suscripción viva, y a
                                            mano el resto: son tres cosas distintas y hasta hoy
                                            se pintaban del mismo color (punto 45). */}
                                        <TableCell className="hidden lg:table-cell">
                                            {!client.id ? <span className="text-white/30 text-sm">-</span> : (() => {
                                                const r = client.renueva_solo || {};
                                                const [texto, clase, ayuda] = r.automatica && r.via === 'stripe'
                                                    ? ['Sola', 'text-emerald-400', 'Stripe le cobra solo']
                                                    : r.automatica
                                                        ? ['Según el plan', 'text-amber-400', 'Su plan renueva automático, pero no hay suscripción viva en Stripe']
                                                        : ['A mano', 'text-white/40', 'No se le cobra solo: hay que pedirle la renovación'];
                                                return <span className={`text-xs ${clase}`} title={ayuda}
                                                    data-testid={`renueva-${client.id}`}>{texto}</span>;
                                            })()}
                                        </TableCell>
                                        {/* Las DOS semanas (doc 19-08): la de plan y la de rutina,
                                            que es la que decide cuándo le llega el reporte. Sin
                                            rutina cargada no hay contador y se dice. */}
                                        <TableCell className="hidden md:table-cell">
                                            {client.id ? (
                                                <div>
                                                    <Badge variant="outline" className="border-[#333] text-white">
                                                        Sem {client.week}
                                                    </Badge>
                                                    <p className="text-[11px] text-white/40 mt-0.5"
                                                        data-testid={`semana-rutina-${client.id}`}>
                                                        {client.semana_rutina != null
                                                            ? `rutina S${client.semana_rutina}`
                                                            : 'sin rutina'}
                                                    </p>
                                                </div>
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
                                            {/* Las dos cuentas del 19-08: recogidas del lunes en
                                                vacío y reportes que le tocaban y no mandó. Solo
                                                cuando debe algo: al que está al día, ni una línea. */}
                                            {(client.semanas_sin_reporte > 0 || client.reportes_sin_responder > 0) && (
                                                <p className="text-[11px] text-white/40 mt-0.5"
                                                    data-testid={`sin-reporte-${client.id}`}>
                                                    {client.semanas_sin_reporte > 0 && `${client.semanas_sin_reporte} sem sin reporte`}
                                                    {client.semanas_sin_reporte > 0 && client.reportes_sin_responder > 0 && ' · '}
                                                    {client.reportes_sin_responder > 0 && `debe ${client.reportes_sin_responder}`}
                                                </p>
                                            )}
                                        </TableCell>
                                        <TableCell className="hidden xl:table-cell">
                                            <CeldaSemaforo celda={client.semaforo?.contacto} />
                                        </TableCell>
                                        <TableCell className="hidden xl:table-cell">
                                            <span className="text-sm text-white/60" data-testid={`entrada-${client.id}`}>
                                                {client.ultima_entrada
                                                    ? new Date(client.ultima_entrada + 'T12:00:00').toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })
                                                    : <span className="text-white/25">-</span>}
                                            </span>
                                        </TableCell>
                                        <TableCell className="hidden lg:table-cell">
                                            <CeldaSemaforo celda={client.semaforo?.peso} />
                                        </TableCell>
                                        <TableCell className="hidden xl:table-cell">
                                            <CeldaSemaforo celda={client.semaforo?.perfil_largo} />
                                        </TableCell>
                                        <TableCell>
                                            {/* El estado con palabras, no con el código de la base
                                                («pendiente_pago» era lo que leía Jesús en la tabla, #64),
                                                y el MISMO que ve el cliente al entrar: ver
                                                `estadoDeAcceso`. */}
                                            {(() => {
                                                const e = estadoDeAcceso(client);
                                                const color = e.tono === 'ok' ? 'bg-green-500/20 text-green-500'
                                                    : e.tono === 'aviso' ? 'bg-yellow-500/15 text-yellow-400'
                                                    : 'bg-[#333] text-white/50';
                                                return <Badge className={`${color} border-0`}>{e.texto}</Badge>;
                                            })()}
                                        </TableCell>
                                        {/* LA FLECHA QUE ABRE LA FICHA.
                                            Estaba, pero en gris tenue y sin acción propia: si el
                                            clic de la fila se lo comía otro elemento, no había
                                            otra salida (a Jesús no se le abrió ninguna ficha en
                                            todo el repaso, 11-08). Ahora se ve, dice lo que hace
                                            y navega ella sola. */}
                                        <TableCell className="text-right">
                                            <Button variant="ghost" size="sm" title="Abrir la ficha"
                                                aria-label={`Abrir la ficha de ${client.user?.name || client.user?.email || 'este cliente'}`}
                                                data-testid={`abrir-ficha-${client.id || client.user_id}`}
                                                disabled={!client.id}
                                                onClick={(e) => { e.stopPropagation(); if (client.id) navigate(`/admin/clients/${client.id}`); }}
                                                className="text-[#FF671F] hover:bg-[#FF671F]/10 disabled:opacity-30">
                                                <ChevronRight className="w-5 h-5" />
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

            {/* LA BARRA DEL «A VARIOS DE GOLPE» (doc 19-08): con gente marcada, flota abajo
                y abre el formulario con todos dentro. Una tarea por cliente. */}
            {seleccionados.size > 0 && (
                <div className="fixed bottom-20 lg:bottom-6 left-1/2 -translate-x-1/2 z-40 bg-[#181818] border border-[#333] rounded-xl shadow-xl px-4 py-2.5 flex items-center gap-3"
                    data-testid="barra-asignar-bloque">
                    <span className="text-sm text-white/80">
                        {seleccionados.size} {seleccionados.size === 1 ? 'cliente marcado' : 'clientes marcados'}
                    </span>
                    <Button size="sm" onClick={() => setModalTarea(true)} data-testid="asignar-a-marcados"
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-xs h-8">
                        Asignar tarea
                    </Button>
                    <button onClick={() => setSeleccionados(new Set())}
                        className="text-white/40 hover:text-white text-xs">Quitar</button>
                </div>
            )}
            <AsignarTarea abierto={modalTarea} onClose={() => setModalTarea(false)}
                sobre={clients.filter(c => seleccionados.has(c.id))
                    .map(c => ({ id: c.id, nombre: c.user?.name || c.user?.email }))}
                onCreada={() => setSeleccionados(new Set())} />
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
        // Las tareas (doc 19-08, apartado 05): lo que cada uno tiene hoy, lo vencido y lo
        // que asignó. Sustituye al «todo va por WhatsApp y no queda en ningún sitio».
        { path: '/admin/tareas', icon: ClipboardList, label: 'Tareas' },
        // Los cuatro paneles del doc 19-08: el entrenador entra y ve solo el suyo.
        { path: '/admin/paneles', icon: Gauge, label: 'Paneles' },
        { path: '/admin/planes', icon: Layers, label: 'Planes', adminOnly: true },
        // Los interruptores de la app (punto 64): estaban al final de Planes, donde nadie
        // los encontraba. Solo admin, que apagan pantallas a TODOS los clientes.
        { path: '/admin/ajustes', icon: SlidersHorizontal, label: 'Ajustes', adminOnly: true },
        { path: '/admin/usuarios', icon: UserCheck, label: 'Usuarios', adminOnly: true },
        { path: '/admin/pagos', icon: Receipt, label: 'Cobros', adminOnly: true },
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
                    {/* Si una pantalla revienta, que se caiga ELLA y no la app entera: el
                        menú y el resto de secciones siguen accesibles. Ver LimiteDeError. */}
                    <LimiteDeError clave={location.pathname + location.search}>
                        <Outlet />
                    </LimiteDeError>
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
