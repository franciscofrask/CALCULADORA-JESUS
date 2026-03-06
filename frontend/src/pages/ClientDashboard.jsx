import React, { useState, useEffect } from 'react';
import { useNavigate, Outlet, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import { 
    Home, Dumbbell, Apple, FileText, MessageCircle, User, 
    LogOut, Bell, Calendar, TrendingUp, ChevronRight, 
    AlertCircle, Clock, CreditCard, Flame, Target
} from 'lucide-react';

// Plan Badge Component
const PlanBadge = ({ plan }) => {
    const badgeClass = {
        gold: 'badge-gold',
        silver: 'badge-silver',
        bronze: 'badge-bronze',
        elm: 'badge-elm'
    }[plan] || 'bg-gray-500 text-white';
    
    return <span className={badgeClass}>{plan?.toUpperCase()}</span>;
};

// Client Dashboard Page
const ClientDashboard = () => {
    const { user, profile, api } = useAuth();
    const navigate = useNavigate();
    const [routine, setRoutine] = useState(null);
    const [unreadMessages, setUnreadMessages] = useState(0);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [routineRes, messagesRes] = await Promise.all([
                    api.get('/routines/current').catch(() => ({ data: null })),
                    api.get('/messages/unread-count').catch(() => ({ data: { count: 0 } }))
                ]);
                setRoutine(routineRes.data);
                setUnreadMessages(messagesRes.data.count);
            } catch (error) {
                console.error('Error fetching dashboard data:', error);
            } finally {
                setLoading(false);
            }
        };
        
        if (profile) {
            fetchData();
        } else {
            setLoading(false);
        }
    }, [api, profile]);

    if (!profile) {
        return (
            <div className="p-4 md:p-6 animate-fade-in">
                <Card className="bg-primary/5 border-primary/20">
                    <CardContent className="p-6 text-center">
                        <Target className="w-12 h-12 text-primary mx-auto mb-4" />
                        <h2 className="heading-3 mb-2">¡Bienvenido a 12EN12!</h2>
                        <p className="text-muted-foreground mb-4">
                            Para comenzar tu transformación, selecciona un plan de entrenamiento.
                        </p>
                        <Button onClick={() => navigate('/onboarding')} className="btn-primary">
                            Seleccionar Plan <ChevronRight className="w-4 h-4 ml-2" />
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    const weekProgress = (profile.week / 4) * 100;
    const todayRoutine = routine?.days?.find(d => 
        d.day.toLowerCase() === new Date().toLocaleDateString('es-ES', { weekday: 'long' }).toLowerCase()
    );

    return (
        <div className="p-4 md:p-6 space-y-6 animate-fade-in pb-24 md:pb-6">
            {/* Welcome Header */}
            <div className="flex items-start justify-between">
                <div>
                    <h1 className="heading-2 text-foreground">
                        ¡Hola, {user?.name?.split(' ')[0]}!
                    </h1>
                    <p className="text-muted-foreground flex items-center gap-2 mt-1">
                        <PlanBadge plan={profile.plan} />
                        <span>Semana {profile.week} de 4</span>
                    </p>
                </div>
                {unreadMessages > 0 && (
                    <Button variant="outline" size="icon" className="relative" onClick={() => navigate('/dashboard/messages')}>
                        <Bell className="w-4 h-4" />
                        <span className="absolute -top-1 -right-1 w-5 h-5 bg-destructive text-destructive-foreground text-xs rounded-full flex items-center justify-center">
                            {unreadMessages}
                        </span>
                    </Button>
                )}
            </div>

            {/* Progress Card */}
            <Card className="bg-gradient-to-r from-primary/10 to-secondary/10 border-primary/20">
                <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Progreso del ciclo</span>
                        <span className="text-sm text-muted-foreground">Semana {profile.week}/4</span>
                    </div>
                    <Progress value={weekProgress} className="h-2" />
                </CardContent>
            </Card>

            {/* Alert Cards */}
            {profile.week === 3 && (
                <Card className="border-accent/50 bg-accent/5">
                    <CardContent className="p-4 flex items-center gap-3">
                        <AlertCircle className="w-5 h-5 text-accent flex-shrink-0" />
                        <div>
                            <p className="font-medium text-sm">Reporte pendiente</p>
                            <p className="text-xs text-muted-foreground">Es tu semana de reporte mensual</p>
                        </div>
                        <Button size="sm" variant="outline" className="ml-auto" onClick={() => navigate('/dashboard/reports')}>
                            Rellenar
                        </Button>
                    </CardContent>
                </Card>
            )}

            {/* Bento Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {/* Today's Routine */}
                <Card 
                    className="col-span-2 cursor-pointer hover:shadow-lg transition-all hover:-translate-y-1"
                    onClick={() => navigate('/dashboard/routine')}
                    data-testid="routine-card"
                >
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                                <div className="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center">
                                    <Dumbbell className="w-5 h-5 text-primary" />
                                </div>
                                <div>
                                    <p className="font-semibold">Hoy</p>
                                    <p className="text-xs text-muted-foreground capitalize">
                                        {new Date().toLocaleDateString('es-ES', { weekday: 'long' })}
                                    </p>
                                </div>
                            </div>
                            <ChevronRight className="w-4 h-4 text-muted-foreground" />
                        </div>
                        {todayRoutine ? (
                            todayRoutine.is_rest ? (
                                <p className="text-sm text-muted-foreground">Día de descanso activo</p>
                            ) : (
                                <p className="text-sm">
                                    <span className="font-bold text-lg text-primary">{todayRoutine.exercises?.length || 0}</span>
                                    {' '}ejercicios programados
                                </p>
                            )
                        ) : (
                            <p className="text-sm text-muted-foreground">Sin rutina asignada</p>
                        )}
                    </CardContent>
                </Card>

                {/* Macros Card */}
                <Card 
                    className="cursor-pointer hover:shadow-lg transition-all hover:-translate-y-1"
                    onClick={() => navigate('/dashboard/nutrition')}
                    data-testid="macros-card"
                >
                    <CardContent className="p-4">
                        <div className="w-10 h-10 bg-secondary/10 rounded-xl flex items-center justify-center mb-2">
                            <Apple className="w-5 h-5 text-secondary" />
                        </div>
                        <p className="font-semibold text-sm">Nutrición</p>
                        {profile.macros_training ? (
                            <p className="text-xs text-muted-foreground mt-1">
                                {Math.round(profile.macros_training.calories)} kcal
                            </p>
                        ) : (
                            <p className="text-xs text-muted-foreground mt-1">Pendiente</p>
                        )}
                    </CardContent>
                </Card>

                {/* Reports Card */}
                <Card 
                    className="cursor-pointer hover:shadow-lg transition-all hover:-translate-y-1"
                    onClick={() => navigate('/dashboard/reports')}
                    data-testid="reports-card"
                >
                    <CardContent className="p-4">
                        <div className="w-10 h-10 bg-accent/10 rounded-xl flex items-center justify-center mb-2">
                            <FileText className="w-5 h-5 text-accent" />
                        </div>
                        <p className="font-semibold text-sm">Reportes</p>
                        <p className="text-xs text-muted-foreground mt-1">Ver evolución</p>
                    </CardContent>
                </Card>

                {/* Messages Card */}
                <Card 
                    className="cursor-pointer hover:shadow-lg transition-all hover:-translate-y-1 relative"
                    onClick={() => navigate('/dashboard/messages')}
                    data-testid="messages-card"
                >
                    <CardContent className="p-4">
                        <div className="w-10 h-10 bg-purple-500/10 rounded-xl flex items-center justify-center mb-2">
                            <MessageCircle className="w-5 h-5 text-purple-500" />
                        </div>
                        <p className="font-semibold text-sm">Mensajes</p>
                        <p className="text-xs text-muted-foreground mt-1">
                            {unreadMessages > 0 ? `${unreadMessages} sin leer` : 'Chatear'}
                        </p>
                        {unreadMessages > 0 && (
                            <span className="absolute top-2 right-2 w-3 h-3 bg-destructive rounded-full"></span>
                        )}
                    </CardContent>
                </Card>

                {/* Profile Card */}
                <Card 
                    className="cursor-pointer hover:shadow-lg transition-all hover:-translate-y-1"
                    onClick={() => navigate('/dashboard/profile')}
                    data-testid="profile-card"
                >
                    <CardContent className="p-4">
                        <div className="w-10 h-10 bg-pink-500/10 rounded-xl flex items-center justify-center mb-2">
                            <User className="w-5 h-5 text-pink-500" />
                        </div>
                        <p className="font-semibold text-sm">Mi Perfil</p>
                        <p className="text-xs text-muted-foreground mt-1">Datos y ajustes</p>
                    </CardContent>
                </Card>
            </div>

            {/* Next Payment Info */}
            {profile.next_payment && (
                <Card className="bg-muted/50">
                    <CardContent className="p-4 flex items-center gap-3">
                        <CreditCard className="w-5 h-5 text-muted-foreground" />
                        <div className="flex-1">
                            <p className="text-sm font-medium">Próxima renovación</p>
                            <p className="text-xs text-muted-foreground">
                                {new Date(profile.next_payment).toLocaleDateString('es-ES', { 
                                    day: 'numeric', 
                                    month: 'long' 
                                })} — {profile.price}€
                            </p>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
};

// Client Layout with Navigation
const ClientLayout = () => {
    const { user, logout, profile } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    const navItems = [
        { path: '/dashboard', icon: Home, label: 'Inicio' },
        { path: '/dashboard/routine', icon: Dumbbell, label: 'Rutina' },
        { path: '/dashboard/nutrition', icon: Apple, label: 'Nutrición' },
        { path: '/dashboard/reports', icon: FileText, label: 'Reportes' },
        { path: '/dashboard/messages', icon: MessageCircle, label: 'Chat' },
    ];

    const isActive = (path) => {
        if (path === '/dashboard') {
            return location.pathname === '/dashboard';
        }
        return location.pathname.startsWith(path);
    };

    const handleLogout = () => {
        logout();
        navigate('/auth');
        toast.success('Sesión cerrada');
    };

    return (
        <div className="min-h-screen bg-background">
            {/* Desktop Sidebar */}
            <aside className="hidden md:flex flex-col w-64 border-r border-border bg-card h-screen sticky top-0">
                <div className="p-6 border-b border-border">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center">
                            <Dumbbell className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h1 className="font-bold text-lg" style={{ fontFamily: 'Barlow Condensed' }}>12EN12</h1>
                            <p className="text-xs text-muted-foreground">Portal Cliente</p>
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
                                    isActive(item.path)
                                        ? 'bg-primary text-primary-foreground'
                                        : 'hover:bg-muted text-muted-foreground hover:text-foreground'
                                }`}
                            >
                                <item.icon className="w-5 h-5" />
                                <span className="font-medium">{item.label}</span>
                            </Link>
                        ))}
                        <Link
                            to="/dashboard/profile"
                            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${
                                isActive('/dashboard/profile')
                                    ? 'bg-primary text-primary-foreground'
                                    : 'hover:bg-muted text-muted-foreground hover:text-foreground'
                            }`}
                        >
                            <User className="w-5 h-5" />
                            <span className="font-medium">Mi Perfil</span>
                        </Link>
                    </nav>
                </ScrollArea>
                
                <div className="p-4 border-t border-border">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 bg-muted rounded-full flex items-center justify-center">
                            <User className="w-5 h-5" />
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm truncate">{user?.name}</p>
                            {profile && <PlanBadge plan={profile.plan} />}
                        </div>
                    </div>
                    <Button 
                        variant="ghost" 
                        className="w-full justify-start text-muted-foreground hover:text-destructive"
                        onClick={handleLogout}
                        data-testid="logout-btn"
                    >
                        <LogOut className="w-4 h-4 mr-2" />
                        Cerrar sesión
                    </Button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="md:ml-0 flex-1">
                <Outlet />
            </main>

            {/* Mobile Bottom Navigation */}
            <nav className="mobile-nav" data-testid="mobile-nav">
                {navItems.map((item) => (
                    <Link
                        key={item.path}
                        to={item.path}
                        className={`mobile-nav-item ${isActive(item.path) ? 'active' : ''}`}
                    >
                        <item.icon className="w-5 h-5" />
                        <span className="text-xs">{item.label}</span>
                    </Link>
                ))}
            </nav>
        </div>
    );
};

export { ClientDashboard, ClientLayout, PlanBadge };
