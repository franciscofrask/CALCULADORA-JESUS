import React, { useState, useEffect } from 'react';
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
    ChevronRight, DollarSign, FileText, ArrowUpRight
} from 'lucide-react';

// Admin Dashboard Home
const AdminDashboard = () => {
    const { api } = useAuth();
    const navigate = useNavigate();
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchStats();
    }, []);

    const fetchStats = async () => {
        try {
            const response = await api.get('/admin/dashboard');
            setStats(response.data);
        } catch (error) {
            console.error('Error fetching stats:', error);
            toast.error('Error al cargar estadísticas');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="p-6 bg-[#0A0A0A] min-h-screen">
                <div className="animate-pulse space-y-4">
                    <div className="h-8 bg-[#222] rounded w-1/4"></div>
                    <div className="grid grid-cols-4 gap-4">
                        {[1, 2, 3, 4].map(i => (
                            <div key={i} className="h-32 bg-[#111] rounded"></div>
                        ))}
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="p-6 space-y-6 animate-fade-in bg-[#0A0A0A] min-h-screen">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="heading-2 text-white">DASHBOARD</h1>
                    <p className="text-white/50 uppercase tracking-wider text-sm">Panel de operaciones JG12</p>
                </div>
                <Button variant="outline" size="icon" className="bg-transparent border-white/20 hover:border-[#FF671F]">
                    <Bell className="w-4 h-4 text-white" />
                </Button>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card className="bg-[#111111] border-[#222222]">
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-white/50 uppercase tracking-wider">Clientes Activos</p>
                                <p className="text-4xl font-bold text-[#FF671F] mt-1" style={{ fontFamily: 'Bebas Neue' }}>
                                    {stats?.total_clients || 0}
                                </p>
                            </div>
                            <div className="w-12 h-12 bg-[#FF671F]/10 rounded-lg flex items-center justify-center">
                                <Users className="w-6 h-6 text-[#FF671F]" />
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-[#111111] border-[#222222]">
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-white/50 uppercase tracking-wider">MRR</p>
                                <p className="text-4xl font-bold text-green-500 mt-1" style={{ fontFamily: 'Bebas Neue' }}>
                                    {stats?.mrr || 0}€
                                </p>
                            </div>
                            <div className="w-12 h-12 bg-green-500/10 rounded-lg flex items-center justify-center">
                                <DollarSign className="w-6 h-6 text-green-500" />
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-[#111111] border-[#222222]">
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-white/50 uppercase tracking-wider">Reportes Pend.</p>
                                <p className="text-4xl font-bold text-yellow-500 mt-1" style={{ fontFamily: 'Bebas Neue' }}>
                                    {stats?.pending_reports || 0}
                                </p>
                            </div>
                            <div className="w-12 h-12 bg-yellow-500/10 rounded-lg flex items-center justify-center">
                                <FileText className="w-6 h-6 text-yellow-500" />
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-[#111111] border-[#222222]">
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-white/50 uppercase tracking-wider">Rutinas Pend.</p>
                                <p className="text-4xl font-bold text-purple-500 mt-1" style={{ fontFamily: 'Bebas Neue' }}>
                                    {stats?.pending_routines || 0}
                                </p>
                            </div>
                            <div className="w-12 h-12 bg-purple-500/10 rounded-lg flex items-center justify-center">
                                <Dumbbell className="w-6 h-6 text-purple-500" />
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Bottom Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card className="bg-[#111111] border-[#222222]">
                    <CardHeader>
                        <CardTitle className="text-lg text-white uppercase tracking-wider">Clientes por Plan</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-3">
                            {Object.entries(stats?.clients_by_plan || {}).map(([plan, count]) => (
                                <div key={plan} className="flex items-center justify-between p-3 bg-[#1A1A1A] rounded-lg">
                                    <PlanBadge plan={plan} />
                                    <span className="font-bold text-white text-xl" style={{ fontFamily: 'Bebas Neue' }}>{count}</span>
                                </div>
                            ))}
                            {Object.keys(stats?.clients_by_plan || {}).length === 0 && (
                                <p className="text-white/50 text-center py-4">Sin clientes aún</p>
                            )}
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-[#111111] border-[#222222]">
                    <CardHeader>
                        <CardTitle className="text-lg text-white uppercase tracking-wider">Pagos de Hoy</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-3">
                            <div className="flex items-center justify-between p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
                                <div className="flex items-center gap-2">
                                    <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                                    <span className="text-white">Exitosos</span>
                                </div>
                                <span className="font-bold text-green-500 text-xl" style={{ fontFamily: 'Bebas Neue' }}>
                                    {stats?.today_payments?.count || 0}
                                </span>
                            </div>
                            <div className="flex items-center justify-between p-3 bg-[#1A1A1A] rounded-lg">
                                <div className="flex items-center gap-2">
                                    <DollarSign className="w-5 h-5 text-white/50" />
                                    <span className="text-white">Total recaudado</span>
                                </div>
                                <span className="font-bold text-[#FF671F] text-xl" style={{ fontFamily: 'Bebas Neue' }}>
                                    {stats?.today_payments?.total || 0}€
                                </span>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Quick Actions */}
            <Card className="bg-[#111111] border-[#222222]">
                <CardHeader>
                    <CardTitle className="text-lg text-white uppercase tracking-wider">Acciones Rápidas</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <Button 
                            variant="outline" 
                            className="h-20 flex-col bg-transparent border-[#333] hover:border-[#FF671F] hover:bg-[#FF671F]/10 text-white" 
                            onClick={() => navigate('/admin/clients')}
                        >
                            <Users className="w-5 h-5 mb-2 text-[#FF671F]" />
                            <span className="uppercase text-xs tracking-wider">Ver Clientes</span>
                        </Button>
                        <Button 
                            variant="outline" 
                            className="h-20 flex-col bg-transparent border-[#333] hover:border-[#FF671F] hover:bg-[#FF671F]/10 text-white" 
                            onClick={() => navigate('/admin/routines')}
                        >
                            <Dumbbell className="w-5 h-5 mb-2 text-[#FF671F]" />
                            <span className="uppercase text-xs tracking-wider">Generar Rutina</span>
                        </Button>
                        <Button 
                            variant="outline" 
                            className="h-20 flex-col bg-transparent border-[#333] hover:border-[#FF671F] hover:bg-[#FF671F]/10 text-white" 
                            onClick={() => toast.info('Próximamente')}
                        >
                            <MessageCircle className="w-5 h-5 mb-2 text-[#FF671F]" />
                            <span className="uppercase text-xs tracking-wider">Mensajes</span>
                        </Button>
                        <Button 
                            variant="outline" 
                            className="h-20 flex-col bg-transparent border-[#333] hover:border-[#FF671F] hover:bg-[#FF671F]/10 text-white" 
                            onClick={() => toast.info('Próximamente')}
                        >
                            <CreditCard className="w-5 h-5 mb-2 text-[#FF671F]" />
                            <span className="uppercase text-xs tracking-wider">Pagos</span>
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
};

// Admin Clients List
const AdminClientsList = () => {
    const { api } = useAuth();
    const navigate = useNavigate();
    const [clients, setClients] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [planFilter, setPlanFilter] = useState('all');

    useEffect(() => {
        fetchClients();
    }, [planFilter]);

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
                                        <TableCell className="font-bold text-[#FF671F]" style={{ fontFamily: 'Bebas Neue' }}>
                                            {client.price}€
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline" className="border-[#333] text-white">
                                                Sem {client.week}
                                            </Badge>
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
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    const navItems = [
        { path: '/admin', icon: LayoutDashboard, label: 'Dashboard', exact: true },
        { path: '/admin/clients', icon: Users, label: 'Clientes' },
        { path: '/admin/routines', icon: Dumbbell, label: 'Rutinas' },
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
            {/* Sidebar */}
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
                        className="w-full justify-start text-white/50 hover:text-red-500 hover:bg-red-500/10"
                        onClick={handleLogout}
                    >
                        <LogOut className="w-4 h-4 mr-2" />
                        Cerrar sesión
                    </Button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-auto">
                <Outlet />
            </main>
        </div>
    );
};

export { AdminDashboard, AdminClientsList, AdminLayout };
