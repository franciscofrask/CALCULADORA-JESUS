import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Outlet, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { PlanBadge, JG12Logo } from './ClientDashboard';
import { 
    LayoutDashboard, Users, CreditCard, Dumbbell,
    MessageCircle, LogOut, Search, Bell,
    ChevronRight, DollarSign, FileText,
    AlertTriangle, UserCheck, UserMinus, UserPlus, Utensils
} from 'lucide-react';

// Admin Dashboard Home
const AdminDashboard = () => {
    const { api } = useAuth();
    const navigate = useNavigate();
    const [stats, setStats] = useState(null);
    const [upcoming, setUpcoming] = useState([]);
    const [clients, setClients] = useState([]);
    const [loading, setLoading] = useState(true);

    // Campana: novedades reales (leads nuevos sin gestionar + mensajes sin leer)
    const [notif, setNotif] = useState({ leads: 0, messages: 0 });
    const [notifOpen, setNotifOpen] = useState(false);

    useEffect(() => {
        const fetchAll = async () => {
            try {
                const [statsRes, upcomingRes, clientsRes] = await Promise.all([
                    api.get('/admin/dashboard-stats'),
                    api.get('/admin/upcoming-payments'),
                    api.get('/admin/clients'),
                ]);
                setStats(statsRes.data);
                setUpcoming(upcomingRes.data.upcoming || []);
                setClients(clientsRes.data || []);
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
            <div className="p-6 bg-[#0A0A0A] min-h-screen">
                <div className="animate-pulse space-y-4">
                    <div className="h-8 bg-[#222] rounded w-1/4" />
                    <div className="grid grid-cols-5 gap-4">
                        {[1,2,3,4,5].map(i => <div key={i} className="h-28 bg-[#111] rounded-xl" />)}
                    </div>
                    <div className="h-48 bg-[#111] rounded-xl" />
                </div>
            </div>
        );
    }

    const planColors = { gold: '#EAB308', silver: '#9CA3AF', bronze: '#C2410C', elm: '#FF671F' };
    const totalPlanActive = Object.values(stats?.plans || {}).reduce((a, b) => a + b, 0);

    return (
        <div className="p-6 space-y-6 animate-fade-in bg-[#0A0A0A] min-h-screen" data-testid="admin-dashboard">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-white tracking-tight" style={{ fontFamily: 'Barlow Condensed' }}>PANEL DE CONTROL</h1>
                    <p className="text-white/40 text-sm">Estado del negocio en tiempo real</p>
                </div>
                <div className="relative">
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
                    <div className="flex items-center gap-3">
                        {/* Bar */}
                        <div className="flex-1 flex h-8 rounded-lg overflow-hidden bg-[#1A1A1A]">
                            {['gold', 'silver', 'bronze', 'elm'].map(plan => {
                                const count = stats?.plans?.[plan] || 0;
                                const pct = totalPlanActive > 0 ? (count / totalPlanActive) * 100 : 0;
                                if (pct === 0) return null;
                                return (
                                    <div
                                        key={plan}
                                        className="h-full flex items-center justify-center text-xs font-bold transition-all"
                                        style={{ width: `${pct}%`, backgroundColor: planColors[plan], color: plan === 'silver' ? '#000' : '#fff', minWidth: count > 0 ? '40px' : 0 }}
                                        title={`${plan}: ${count}`}
                                    >
                                        {count}
                                    </div>
                                );
                            })}
                        </div>
                        {/* Legend */}
                        <div className="flex gap-3 flex-shrink-0">
                            {['gold', 'silver', 'bronze', 'elm'].map(plan => (
                                <div key={plan} className="flex items-center gap-1.5">
                                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: planColors[plan] }} />
                                    <span className="text-xs text-white/50 uppercase">{plan}</span>
                                    <span className="text-xs font-bold text-white">{stats?.plans?.[plan] || 0}</span>
                                </div>
                            ))}
                        </div>
                    </div>
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
                                    <div key={i} className="flex items-center justify-between p-3 bg-[#0A0A0A] rounded-lg border border-[#222] hover:border-[#FF671F]/30 transition-colors" data-testid={`upcoming-${i}`}>
                                        <div className="flex items-center gap-3">
                                            <div className="w-9 h-9 bg-[#FF671F]/10 rounded-lg flex items-center justify-center">
                                                <span className="text-[#FF671F] font-bold text-sm" style={{ fontFamily: 'Barlow Condensed' }}>{daysLeft}d</span>
                                            </div>
                                            <div>
                                                <p className="text-white text-sm font-medium">{u.name}</p>
                                                <p className="text-white/40 text-xs">{payDate ? payDate.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' }) : '-'}</p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <PlanBadge plan={u.plan} />
                                            <span className="text-[#FF671F] font-bold text-lg" style={{ fontFamily: 'Barlow Condensed' }}>{u.price}€</span>
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
                                className="flex items-center justify-between p-2.5 rounded-lg hover:bg-white/5 cursor-pointer transition-colors"
                                onClick={() => navigate(`/admin/clients/${c.id}`)}
                                data-testid={`client-row-${c.id}`}
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 bg-[#222] rounded-lg flex items-center justify-center">
                                        <span className="text-[#FF671F] font-bold text-xs">{c.user?.name?.charAt(0)}</span>
                                    </div>
                                    <div>
                                        <p className="text-white text-sm font-medium">{c.user?.name}</p>
                                        <p className="text-white/30 text-xs">{c.user?.email}</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <PlanBadge plan={c.plan} />
                                    <Badge className={c.status === 'activo' ? 'bg-green-500/10 text-green-500 border-0 text-[10px]' : 'bg-red-500/10 text-red-400 border-0 text-[10px]'}>
                                        {c.status}
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
            const params = planFilter !== 'all' ? `?plan=${planFilter}` : '';
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
                    <p className="text-white/50 uppercase tracking-wider text-sm">{clients.length} clientes activos</p>
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
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs">Precio</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs">Semana</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs">Coach</TableHead>
                                    <TableHead className="text-white/50 uppercase tracking-wider text-xs">Estado</TableHead>
                                    <TableHead className="text-right text-white/50 uppercase tracking-wider text-xs">Acciones</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {filteredClients.map((client) => (
                                    <TableRow 
                                        key={client.id} 
                                        className="border-[#222] cursor-pointer hover:bg-[#1A1A1A]" 
                                        onClick={() => navigate(`/admin/clients/${client.id}`)}
                                    >
                                        <TableCell>
                                            <div>
                                                <p className="font-medium text-white">{client.user?.name}</p>
                                                <p className="text-sm text-white/50">{client.user?.email}</p>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <PlanBadge plan={client.plan} />
                                        </TableCell>
                                        <TableCell className="font-bold text-[#FF671F]" style={{ fontFamily: 'Barlow Condensed' }}>
                                            {client.price}€
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline" className="border-[#333] text-white">
                                                Sem {client.week}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            {client.trainer_id ? (
                                                <span className="text-sm text-white/70">{trainerName(client.trainer_id)}</span>
                                            ) : user?.role === 'trainer' ? (
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
                                            <Badge className={client.status === 'activo' ? 'bg-green-500/20 text-green-500 border-0' : 'bg-[#333] text-white/50 border-0'}>
                                                {client.status}
                                            </Badge>
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
    const prevLeadsCount = useRef(null);
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
        { path: '/admin/usuarios', icon: UserCheck, label: 'Usuarios' },
        { path: '/admin/leads', icon: UserPlus, label: 'Leads' },
        { path: '/admin/messages', icon: MessageCircle, label: 'Mensajes' },
        { path: '/admin/routines', icon: Dumbbell, label: 'Rutinas' },
        { path: '/admin/menus', icon: Utensils, label: 'Menús' },
        { path: '/admin/payments', icon: CreditCard, label: 'Pagos' },
    ];

    const isActive = (path, exact = false) => {
        if (exact) return location.pathname === path;
        return location.pathname.startsWith(path);
    };

    const handleLogout = () => {
        logout();
        navigate('/auth');
        toast.success('Sesión cerrada');
    };

    return (
        <div className="min-h-screen bg-[#0A0A0A] flex">
            {/* Sidebar (desktop) */}
            <aside className="w-64 border-r border-white/10 bg-[#0A0A0A] h-screen sticky top-0 hidden lg:flex flex-col">
                <div className="p-6 border-b border-white/10">
                    <JG12Logo size="md" />
                    <p className="text-white/40 text-xs uppercase tracking-wider mt-1">Panel Admin</p>
                </div>
                
                <ScrollArea className="flex-1 p-4">
                    <nav className="space-y-1">
                        {navItems.map((item) => (
                            <Link
                                key={item.path}
                                to={item.path}
                                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                                    isActive(item.path, item.exact)
                                        ? 'bg-[#FF671F] text-white'
                                        : 'text-white/60 hover:text-white hover:bg-white/5'
                                }`}
                            >
                                <item.icon className="w-5 h-5" />
                                <span className="font-medium uppercase tracking-wider text-sm">{item.label}</span>
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
                </ScrollArea>
                
                <div className="p-4 border-t border-white/10">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 bg-[#222] rounded-lg flex items-center justify-center">
                            <span className="font-bold text-[#FF671F]">{user?.name?.charAt(0)}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="font-medium text-white text-sm truncate">{user?.name}</p>
                            <Badge className="bg-[#FF671F]/20 text-[#FF671F] border-0 text-xs uppercase">{user?.role}</Badge>
                        </div>
                    </div>
                    <Button
                        variant="ghost"
                        className="w-full justify-start text-white/60 hover:text-[#FF671F] hover:bg-[#FF671F]/10 mb-1"
                        onClick={() => navigate('/dashboard')}
                        data-testid="use-app-btn"
                    >
                        <Utensils className="w-4 h-4 mr-2" />
                        Usar app (modo cliente)
                    </Button>
                    <Button
                        variant="ghost"
                        className="w-full justify-start text-white/50 hover:text-red-500 hover:bg-red-500/10"
                        onClick={handleLogout}
                    >
                        <LogOut className="w-4 h-4 mr-2" />
                        Cerrar sesión
                    </Button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-auto pb-16 lg:pb-0">
                <Outlet />
            </main>

            {/* Mobile Bottom Nav */}
            <nav className="fixed bottom-0 left-0 right-0 z-50 bg-[#111] border-t border-[#222] lg:hidden" data-testid="admin-mobile-nav">
                <div className="flex items-center justify-around h-14 px-1">
                    {navItems.map((item) => {
                        const active = isActive(item.path, item.exact);
                        return (
                            <Link key={item.path} to={item.path}
                                className={`relative flex flex-col items-center justify-center flex-1 py-1.5 transition-all ${active ? 'text-[#FF671F]' : 'text-white/40'}`}
                            >
                                <item.icon className={`w-5 h-5 mb-0.5 ${active ? 'text-[#FF671F]' : ''}`} strokeWidth={active ? 2.5 : 2} />
                                <span className={`text-[9px] uppercase tracking-wider ${active ? 'font-bold' : ''}`}>{item.label}</span>
                                {item.path === '/admin/leads' && newLeadsCount > 0 && (
                                    <span className="absolute top-0.5 right-[calc(50%-16px)] bg-red-500 text-white text-[9px] font-bold rounded-full min-w-[15px] h-[15px] px-0.5 flex items-center justify-center">
                                        {newLeadsCount > 99 ? '99+' : newLeadsCount}
                                    </span>
                                )}
                                {item.path === '/admin/messages' && unreadMessages > 0 && (
                                    <span className="absolute top-0.5 right-[calc(50%-16px)] bg-red-500 text-white text-[9px] font-bold rounded-full min-w-[15px] h-[15px] px-0.5 flex items-center justify-center">
                                        {unreadMessages > 99 ? '99+' : unreadMessages}
                                    </span>
                                )}
                            </Link>
                        );
                    })}
                </div>
            </nav>
        </div>
    );
};

export { AdminDashboard, AdminClientsList, AdminLayout };
