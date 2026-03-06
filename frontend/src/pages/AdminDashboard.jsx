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
import { PlanBadge } from './ClientDashboard';
import { 
    LayoutDashboard, Users, CreditCard, Dumbbell, 
    MessageCircle, Settings, LogOut, Search, Bell,
    TrendingUp, AlertTriangle, CheckCircle, Clock,
    ChevronRight, Filter, UserPlus, DollarSign,
    Activity, FileText, Zap
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
            <div className="p-6">
                <div className="animate-pulse space-y-4">
                    <div className="h-8 bg-muted rounded w-1/4"></div>
                    <div className="grid grid-cols-4 gap-4">
                        {[1, 2, 3, 4].map(i => (
                            <div key={i} className="h-32 bg-muted rounded"></div>
                        ))}
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="p-6 space-y-6 animate-fade-in">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="heading-2">Dashboard</h1>
                    <p className="text-muted-foreground">Panel de operaciones 12EN12</p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="icon">
                        <Bell className="w-4 h-4" />
                    </Button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card className="bg-gradient-to-br from-primary/10 to-primary/5">
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-muted-foreground">Clientes Activos</p>
                                <p className="stat-number text-primary">{stats?.total_clients || 0}</p>
                            </div>
                            <div className="w-12 h-12 bg-primary/20 rounded-xl flex items-center justify-center">
                                <Users className="w-6 h-6 text-primary" />
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-gradient-to-br from-secondary/10 to-secondary/5">
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-muted-foreground">MRR</p>
                                <p className="stat-number text-secondary">{stats?.mrr || 0}€</p>
                            </div>
                            <div className="w-12 h-12 bg-secondary/20 rounded-xl flex items-center justify-center">
                                <DollarSign className="w-6 h-6 text-secondary" />
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-gradient-to-br from-accent/10 to-accent/5">
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-muted-foreground">Reportes Pendientes</p>
                                <p className="stat-number text-accent">{stats?.pending_reports || 0}</p>
                            </div>
                            <div className="w-12 h-12 bg-accent/20 rounded-xl flex items-center justify-center">
                                <FileText className="w-6 h-6 text-accent" />
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-gradient-to-br from-purple-500/10 to-purple-500/5">
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-muted-foreground">Rutinas Pendientes</p>
                                <p className="stat-number text-purple-500">{stats?.pending_routines || 0}</p>
                            </div>
                            <div className="w-12 h-12 bg-purple-500/20 rounded-xl flex items-center justify-center">
                                <Dumbbell className="w-6 h-6 text-purple-500" />
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Clients by Plan */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Clientes por Plan</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-3">
                            {Object.entries(stats?.clients_by_plan || {}).map(([plan, count]) => (
                                <div key={plan} className="flex items-center justify-between">
                                    <PlanBadge plan={plan} />
                                    <span className="font-bold">{count}</span>
                                </div>
                            ))}
                            {Object.keys(stats?.clients_by_plan || {}).length === 0 && (
                                <p className="text-muted-foreground text-center py-4">Sin clientes aún</p>
                            )}
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Pagos de Hoy</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-3">
                            <div className="flex items-center justify-between p-3 bg-green-500/10 rounded-lg">
                                <div className="flex items-center gap-2">
                                    <CheckCircle className="w-5 h-5 text-green-500" />
                                    <span>Exitosos</span>
                                </div>
                                <span className="font-bold">{stats?.today_payments?.count || 0}</span>
                            </div>
                            <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                                <div className="flex items-center gap-2">
                                    <DollarSign className="w-5 h-5 text-muted-foreground" />
                                    <span>Total recaudado</span>
                                </div>
                                <span className="font-bold">{stats?.today_payments?.total || 0}€</span>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Quick Actions */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-lg">Acciones Rápidas</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <Button variant="outline" className="h-20 flex-col" onClick={() => navigate('/admin/clients')}>
                            <Users className="w-5 h-5 mb-2" />
                            Ver Clientes
                        </Button>
                        <Button variant="outline" className="h-20 flex-col" onClick={() => navigate('/admin/routines')}>
                            <Dumbbell className="w-5 h-5 mb-2" />
                            Generar Rutina
                        </Button>
                        <Button variant="outline" className="h-20 flex-col" onClick={() => toast.info('Próximamente')}>
                            <MessageCircle className="w-5 h-5 mb-2" />
                            Mensajes
                        </Button>
                        <Button variant="outline" className="h-20 flex-col" onClick={() => toast.info('Próximamente')}>
                            <CreditCard className="w-5 h-5 mb-2" />
                            Pagos
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
        <div className="p-6 space-y-6 animate-fade-in">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="heading-2">Clientes</h1>
                    <p className="text-muted-foreground">{clients.length} clientes activos</p>
                </div>
            </div>

            {/* Filters */}
            <div className="flex flex-col md:flex-row gap-4">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                        placeholder="Buscar cliente..."
                        className="pl-10"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        data-testid="client-search"
                    />
                </div>
                <Select value={planFilter} onValueChange={setPlanFilter}>
                    <SelectTrigger className="w-[180px]" data-testid="plan-filter">
                        <SelectValue placeholder="Filtrar por plan" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">Todos los planes</SelectItem>
                        <SelectItem value="gold">Gold</SelectItem>
                        <SelectItem value="silver">Silver</SelectItem>
                        <SelectItem value="bronze">Bronze</SelectItem>
                        <SelectItem value="elm">ELM</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            {/* Clients Table */}
            <Card>
                <CardContent className="p-0">
                    {loading ? (
                        <div className="p-8 text-center">
                            <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full mx-auto"></div>
                        </div>
                    ) : filteredClients.length > 0 ? (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Cliente</TableHead>
                                    <TableHead>Plan</TableHead>
                                    <TableHead>Precio</TableHead>
                                    <TableHead>Semana</TableHead>
                                    <TableHead>Estado</TableHead>
                                    <TableHead className="text-right">Acciones</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {filteredClients.map((client) => (
                                    <TableRow key={client.id} className="cursor-pointer" onClick={() => navigate(`/admin/clients/${client.id}`)}>
                                        <TableCell>
                                            <div>
                                                <p className="font-medium">{client.user?.name}</p>
                                                <p className="text-sm text-muted-foreground">{client.user?.email}</p>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <PlanBadge plan={client.plan} />
                                        </TableCell>
                                        <TableCell className="font-semibold">{client.price}€</TableCell>
                                        <TableCell>
                                            <Badge variant="outline">Sem {client.week}</Badge>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={client.status === 'activo' ? 'default' : 'secondary'}>
                                                {client.status}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <Button variant="ghost" size="sm">
                                                <ChevronRight className="w-4 h-4" />
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    ) : (
                        <div className="p-8 text-center">
                            <Users className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                            <p className="text-muted-foreground">No se encontraron clientes</p>
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
        <div className="min-h-screen bg-background flex">
            {/* Sidebar */}
            <aside className="w-64 border-r border-border bg-card h-screen sticky top-0 hidden lg:flex flex-col">
                <div className="p-6 border-b border-border">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center">
                            <Dumbbell className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h1 className="font-bold text-lg" style={{ fontFamily: 'Barlow Condensed' }}>12EN12</h1>
                            <p className="text-xs text-muted-foreground">Panel Admin</p>
                        </div>
                    </div>
                </div>
                
                <ScrollArea className="flex-1 p-4">
                    <nav className="space-y-1">
                        {navItems.map((item) => (
                            <Link
                                key={item.path}
                                to={item.path}
                                className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${
                                    isActive(item.path, item.exact)
                                        ? 'bg-primary text-primary-foreground'
                                        : 'hover:bg-muted text-muted-foreground hover:text-foreground'
                                }`}
                            >
                                <item.icon className="w-5 h-5" />
                                <span className="font-medium">{item.label}</span>
                            </Link>
                        ))}
                    </nav>
                </ScrollArea>
                
                <div className="p-4 border-t border-border">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 bg-muted rounded-full flex items-center justify-center">
                            <span className="font-bold text-sm">{user?.name?.charAt(0)}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm truncate">{user?.name}</p>
                            <Badge variant="secondary" className="text-xs">{user?.role}</Badge>
                        </div>
                    </div>
                    <Button 
                        variant="ghost" 
                        className="w-full justify-start text-muted-foreground hover:text-destructive"
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
