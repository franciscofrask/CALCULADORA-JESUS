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
    Menu, X
} from 'lucide-react';

// Colores para el desglose por plan (cualquier plan sin color cae en el gris).
const PLAN_COLORS = {
    reto12en12_gold: '#EAB308', gold: '#EAB308',
    reto12en12_silver: '#9CA3AF', silver: '#9CA3AF',
    bronze: '#C2410C', elm: '#FF671F', reto60: '#22C55E',
    calculadora_jp: '#3B82F6', mantenimiento: '#8B5CF6',
    premium: '#EC4899', plan_6m: '#14B8A6', sin_plan: '#555555',
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
                const [statsRes, upcomingRes, clientsRes, cadenceRes, revisionesRes] = await Promise.all([
                    api.get('/admin/dashboard-stats'),
                    api.get('/admin/upcoming-payments'),
                    api.get('/admin/clients'),
                    api.get('/admin/report-cadence'),
                    api.get('/admin/macro-revisiones').catch(() => ({ data: { items: [] } })),
                ]);
                setStats(statsRes.data);
                setUpcoming(upcomingRes.data.upcoming || []);
                setClients(clientsRes.data || []);
                setCadence(cadenceRes.data.items || []);
                setRevisiones(revisionesRes.data.items || []);
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

            {/* KPI Row */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3" data-testid="kpi-row">
                <KpiCard value={stats?.total_clients || 0} label="Clientes totales" icon={Users} color="#FF671F" testId="kpi-total" />
                <KpiCard value={stats?.active_clients || 0} label="Activos" icon={UserCheck} color="#22C55E" testId="kpi-active" />
                <KpiCard value={stats?.at_risk_clients || 0} label="En riesgo" icon={AlertTriangle} color="#EAB308" testId="kpi-risk" />
                <KpiCard value={stats?.inactive_clients || 0} label="Bajas" icon={UserMinus} color="#EF4444" testId="kpi-bajas" />
                <KpiCard value={`${stats?.mrr || 0}€`} label="MRR" icon={DollarSign} color="#8B5CF6" testId="kpi-mrr" />
            </div>

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

            {/* Reportes del coach que tocan esta semana */}
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
const KpiCard = ({ value, label, icon: Icon, color, testId }) => (
    <Card className="bg-[#111111] border-[#222]" data-testid={testId}>
        <CardContent className="p-4">
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-3xl font-bold mt-1" style={{ fontFamily: 'Barlow Condensed', color }}>{value}</p>
                    <p className="text-[10px] text-white/40 uppercase tracking-wider mt-1">{label}</p>
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

    const filteredClients = clients.filter(c => 
        c.user?.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.user?.email?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="p-6 space-y-6 animate-fade-in bg-[#0A0A0A] min-h-screen">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="heading-2 text-white">CLIENTES</h1>
                    <p className="text-white/50 uppercase tracking-wider text-sm">{clients.length} {clients.length === 1 ? 'cliente' : 'clientes'}</p>
                </div>
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

    const navItems = [
        { path: '/admin', icon: LayoutDashboard, label: 'Dashboard', exact: true },
        { path: '/admin/clients', icon: Users, label: 'Clientes' },
        { path: '/admin/planes', icon: Layers, label: 'Planes' },
        { path: '/admin/usuarios', icon: UserCheck, label: 'Usuarios' },
        { path: '/admin/leads', icon: UserPlus, label: 'Leads' },
        { path: '/admin/messages', icon: MessageCircle, label: 'Mensajes' },
        { path: '/admin/routines', icon: Dumbbell, label: 'Rutinas' },
        { path: '/admin/menus', icon: Utensils, label: 'Menús' },
        { path: '/admin/alimentos', icon: Apple, label: 'Alimentos' },
    ];

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
