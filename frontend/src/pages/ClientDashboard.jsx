import React, { useState, useEffect } from 'react';
import { useNavigate, Outlet, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import { 
    Home, Dumbbell, Apple, FileText, MessageCircle, User, 
    LogOut, Bell, ChevronRight, CreditCard, Target, ArrowUpRight, Bot
} from 'lucide-react';

// JG12 Logo Component
const JG12Logo = ({ size = 'md' }) => {
    const sizeClasses = {
        sm: 'text-xl',
        md: 'text-2xl',
        lg: 'text-4xl'
    };
    const iconSizes = {
        sm: 'w-4 h-4',
        md: 'w-5 h-5',
        lg: 'w-8 h-8'
    };
    
    return (
        <div className={`jg-logo ${sizeClasses[size]} flex items-center`}>
            <span className="text-white font-bold">JG</span>
            <span className="text-white font-bold">12</span>
            <ArrowUpRight className={`text-[#FF671F] ${iconSizes[size]} -ml-0.5`} strokeWidth={3} />
        </div>
    );
};

// Plan Badge Component
const PlanBadge = ({ plan }) => {
    const badgeClass = {
        gold: 'bg-gradient-to-r from-yellow-500 via-yellow-400 to-yellow-600 text-black',
        silver: 'bg-gradient-to-r from-gray-300 via-gray-200 to-gray-400 text-black',
        bronze: 'bg-gradient-to-r from-orange-700 via-orange-600 to-orange-800 text-white',
        elm: 'bg-[#FF671F] text-white'
    }[plan] || 'bg-gray-600 text-white';
    
    return (
        <span className={`${badgeClass} font-bold px-2 py-0.5 rounded text-xs uppercase tracking-wider`}>
            {plan?.toUpperCase()}
        </span>
    );
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
                <Card className="bg-[#111111] border-[#FF671F]/30">
                    <CardContent className="p-8 text-center">
                        <div className="w-16 h-16 bg-[#FF671F]/20 rounded-lg flex items-center justify-center mx-auto mb-4">
                            <Target className="w-8 h-8 text-[#FF671F]" />
                        </div>
                        <h2 className="heading-3 text-white mb-2">¡BIENVENIDO A JG12!</h2>
                        <p className="text-white/60 mb-6">
                            Para comenzar tu transformación, selecciona un plan de entrenamiento.
                        </p>
                        <Button 
                            onClick={() => navigate('/onboarding')} 
                            className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold uppercase tracking-wider"
                        >
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
                    <h1 className="heading-2 text-white">
                        ¡HOLA, {user?.name?.split(' ')[0]?.toUpperCase()}!
                    </h1>
                    <div className="flex items-center gap-3 mt-2">
                        <PlanBadge plan={profile.plan} />
                        <span className="text-white/60 text-sm">Semana {profile.week} de 4</span>
                    </div>
                </div>
                {unreadMessages > 0 && (
                    <Button 
                        variant="outline" 
                        size="icon" 
                        className="relative bg-transparent border-white/20 hover:border-[#FF671F] hover:bg-[#FF671F]/10"
                        onClick={() => navigate('/dashboard/messages')}
                    >
                        <Bell className="w-4 h-4 text-white" />
                        <span className="absolute -top-1 -right-1 w-5 h-5 bg-[#FF671F] text-white text-xs rounded-full flex items-center justify-center font-bold">
                            {unreadMessages}
                        </span>
                    </Button>
                )}
            </div>

            {/* Progress Card */}
            <Card className="bg-gradient-to-r from-[#FF671F]/20 to-[#FF671F]/5 border-[#FF671F]/30">
                <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-bold text-white uppercase tracking-wider">Progreso del ciclo</span>
                        <span className="text-sm text-white/60">Semana {profile.week}/4</span>
                    </div>
                    <div className="w-full bg-black/30 rounded-full h-2">
                        <div 
                            className="bg-[#FF671F] h-2 rounded-full transition-all duration-500"
                            style={{ width: `${weekProgress}%` }}
                        ></div>
                    </div>
                </CardContent>
            </Card>

            {/* Bento Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {/* Today's Routine */}
                <Card 
                    className="col-span-2 bg-[#111111] border-[#222222] cursor-pointer hover:border-[#FF671F]/50 transition-all group"
                    onClick={() => navigate('/dashboard/routine')}
                    data-testid="routine-card"
                >
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-3">
                                <div className="w-12 h-12 bg-[#FF671F]/10 rounded-lg flex items-center justify-center group-hover:bg-[#FF671F]/20 transition-colors">
                                    <Dumbbell className="w-6 h-6 text-[#FF671F]" />
                                </div>
                                <div>
                                    <p className="font-bold text-white uppercase">HOY</p>
                                    <p className="text-sm text-white/50 capitalize">
                                        {new Date().toLocaleDateString('es-ES', { weekday: 'long' })}
                                    </p>
                                </div>
                            </div>
                            <ChevronRight className="w-5 h-5 text-white/30 group-hover:text-[#FF671F] transition-colors" />
                        </div>
                        {todayRoutine ? (
                            todayRoutine.is_rest ? (
                                <p className="text-white/60">Día de descanso activo</p>
                            ) : (
                                <p className="text-white">
                                    <span className="text-3xl font-bold text-[#FF671F]" style={{ fontFamily: 'Bebas Neue' }}>
                                        {todayRoutine.exercises?.length || 0}
                                    </span>
                                    <span className="ml-2">ejercicios programados</span>
                                </p>
                            )
                        ) : (
                            <p className="text-white/50">Sin rutina asignada</p>
                        )}
                    </CardContent>
                </Card>

                {/* Macros Card */}
                <Card 
                    className="bg-[#111111] border-[#222222] cursor-pointer hover:border-[#FF671F]/50 transition-all group"
                    onClick={() => navigate('/dashboard/nutrition')}
                    data-testid="macros-card"
                >
                    <CardContent className="p-4">
                        <div className="w-10 h-10 bg-green-500/10 rounded-lg flex items-center justify-center mb-3 group-hover:bg-green-500/20 transition-colors">
                            <Apple className="w-5 h-5 text-green-500" />
                        </div>
                        <p className="font-bold text-white uppercase text-sm">Nutrición</p>
                        {profile.macros_training ? (
                            <p className="text-2xl font-bold text-green-500 mt-1" style={{ fontFamily: 'Bebas Neue' }}>
                                {Math.round(profile.macros_training.calories)} <span className="text-sm text-white/50">kcal</span>
                            </p>
                        ) : (
                            <p className="text-white/50 text-sm mt-1">Pendiente</p>
                        )}
                    </CardContent>
                </Card>

                {/* Reports Card */}
                <Card 
                    className="bg-[#111111] border-[#222222] cursor-pointer hover:border-[#FF671F]/50 transition-all group"
                    onClick={() => navigate('/dashboard/reports')}
                    data-testid="reports-card"
                >
                    <CardContent className="p-4">
                        <div className="w-10 h-10 bg-yellow-500/10 rounded-lg flex items-center justify-center mb-3 group-hover:bg-yellow-500/20 transition-colors">
                            <FileText className="w-5 h-5 text-yellow-500" />
                        </div>
                        <p className="font-bold text-white uppercase text-sm">Reportes</p>
                        <p className="text-white/50 text-sm mt-1">Ver evolución</p>
                    </CardContent>
                </Card>

                {/* Messages Card */}
                <Card 
                    className="bg-[#111111] border-[#222222] cursor-pointer hover:border-[#FF671F]/50 transition-all group relative"
                    onClick={() => navigate('/dashboard/messages')}
                    data-testid="messages-card"
                >
                    <CardContent className="p-4">
                        <div className="w-10 h-10 bg-purple-500/10 rounded-lg flex items-center justify-center mb-3 group-hover:bg-purple-500/20 transition-colors">
                            <MessageCircle className="w-5 h-5 text-purple-500" />
                        </div>
                        <p className="font-bold text-white uppercase text-sm">Mensajes</p>
                        <p className="text-white/50 text-sm mt-1">
                            {unreadMessages > 0 ? `${unreadMessages} sin leer` : 'Chatear'}
                        </p>
                        {unreadMessages > 0 && (
                            <span className="absolute top-3 right-3 w-3 h-3 bg-[#FF671F] rounded-full animate-pulse"></span>
                        )}
                    </CardContent>
                </Card>

                {/* Profile Card */}
                <Card 
                    className="bg-[#111111] border-[#222222] cursor-pointer hover:border-[#FF671F]/50 transition-all group"
                    onClick={() => navigate('/dashboard/profile')}
                    data-testid="profile-card"
                >
                    <CardContent className="p-4">
                        <div className="w-10 h-10 bg-pink-500/10 rounded-lg flex items-center justify-center mb-3 group-hover:bg-pink-500/20 transition-colors">
                            <User className="w-5 h-5 text-pink-500" />
                        </div>
                        <p className="font-bold text-white uppercase text-sm">Mi Perfil</p>
                        <p className="text-white/50 text-sm mt-1">Datos y ajustes</p>
                    </CardContent>
                </Card>
            </div>

            {/* Next Payment Info */}
            {profile.next_payment && (
                <Card className="bg-[#111111] border-[#222222]">
                    <CardContent className="p-4 flex items-center gap-3">
                        <CreditCard className="w-5 h-5 text-white/50" />
                        <div className="flex-1">
                            <p className="text-sm font-bold text-white uppercase tracking-wider">Próxima renovación</p>
                            <p className="text-sm text-white/50">
                                {new Date(profile.next_payment).toLocaleDateString('es-ES', { 
                                    day: 'numeric', 
                                    month: 'long' 
                                })} — <span className="text-[#FF671F] font-bold">{profile.price}€</span>
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
        { path: '/dashboard/chatbot', icon: Bot, label: 'Asistente IA' },
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
        <div className="min-h-screen bg-[#0A0A0A] flex">
            {/* Desktop Sidebar */}
            <aside className="hidden md:flex flex-col w-64 border-r border-white/10 bg-[#0A0A0A] h-screen sticky top-0 flex-shrink-0">
                <div className="p-6 border-b border-white/10">
                    <JG12Logo size="md" />
                    <p className="text-white/40 text-xs uppercase tracking-wider mt-1">Portal Cliente</p>
                </div>
                
                <ScrollArea className="flex-1 p-4">
                    <nav className="space-y-1">
                        {navItems.map((item) => (
                            <Link
                                key={item.path}
                                to={item.path}
                                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                                    isActive(item.path)
                                        ? 'bg-[#FF671F] text-white'
                                        : 'text-white/60 hover:text-white hover:bg-white/5'
                                }`}
                            >
                                <item.icon className="w-5 h-5" />
                                <span className="font-medium">{item.label}</span>
                            </Link>
                        ))}
                        <Link
                            to="/dashboard/profile"
                            className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                                isActive('/dashboard/profile')
                                    ? 'bg-[#FF671F] text-white'
                                    : 'text-white/60 hover:text-white hover:bg-white/5'
                            }`}
                        >
                            <User className="w-5 h-5" />
                            <span className="font-medium">Mi Perfil</span>
                        </Link>
                    </nav>
                </ScrollArea>
                
                <div className="p-4 border-t border-white/10">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 bg-[#222222] rounded-lg flex items-center justify-center">
                            <span className="text-[#FF671F] font-bold">{user?.name?.charAt(0)}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="font-medium text-white text-sm truncate">{user?.name}</p>
                            {profile && <PlanBadge plan={profile.plan} />}
                        </div>
                    </div>
                    <Button 
                        variant="ghost" 
                        className="w-full justify-start text-white/50 hover:text-red-500 hover:bg-red-500/10"
                        onClick={handleLogout}
                        data-testid="logout-btn"
                    >
                        <LogOut className="w-4 h-4 mr-2" />
                        Cerrar sesión
                    </Button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-auto pb-16 md:pb-0">
                <Outlet />
            </main>

            {/* Mobile Bottom Navigation - Redesigned */}
            <nav className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-gray-200 shadow-lg md:hidden" data-testid="mobile-nav">
                <div className="flex items-center justify-around h-16 px-2">
                    {[
                        { path: '/dashboard', icon: Home, label: 'Inicio' },
                        { path: '/dashboard/nutrition', icon: Apple, label: 'Nutrición' },
                        { path: '/dashboard/routine', icon: Dumbbell, label: 'Rutina' },
                        { path: '/dashboard/messages', icon: MessageCircle, label: 'Chat' },
                        { path: '/dashboard/profile', icon: User, label: 'Más' },
                    ].map((item) => {
                        const active = isActive(item.path);
                        return (
                            <Link
                                key={item.path}
                                to={item.path}
                                className={`flex flex-col items-center justify-center flex-1 py-2 transition-all duration-200 ${
                                    active ? 'text-[#FFA500]' : 'text-gray-400'
                                }`}
                            >
                                <item.icon 
                                    className={`w-5 h-5 mb-1 transition-all duration-200 ${
                                        active ? 'text-[#FFA500] scale-110' : 'text-gray-400'
                                    }`} 
                                    strokeWidth={active ? 2.5 : 2}
                                />
                                <span className={`text-xs ${active ? 'font-bold' : 'font-medium'}`}>
                                    {item.label}
                                </span>
                            </Link>
                        );
                    })}
                </div>
            </nav>
        </div>
    );
};

export { ClientDashboard, ClientLayout, PlanBadge, JG12Logo };
