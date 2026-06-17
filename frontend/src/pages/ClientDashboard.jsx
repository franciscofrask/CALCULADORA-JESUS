import React, { useState, useEffect } from 'react';
import { useNavigate, Outlet, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import {
    Home, Dumbbell, Apple, FileText, MessageCircle, User,
    LogOut, Bell, ChevronRight, CreditCard, Target, ArrowUpRight, Bot,
    Flame, Activity, Zap, Scale, Calculator, Search
} from 'lucide-react';
import BrandArrow from '../components/BrandArrow';

// =============== SHARED COMPONENTS ===============

const JG12Logo = ({ size = 'md' }) => {
    const sizeClasses = { sm: 'text-xl', md: 'text-2xl', lg: 'text-4xl' };
    const iconSizes = { sm: 'w-4 h-4', md: 'w-5 h-5', lg: 'w-8 h-8' };
    return (
        <div className={`jg-logo ${sizeClasses[size]} flex items-center`}>
            <span className="text-white font-bold">JG</span>
            <span className="text-white font-bold">12</span>
            <BrandArrow className="text-[#FF671F] h-[1em] w-[1em] -ml-0.5" />
        </div>
    );
};

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

// =============== CIRCULAR TRACKER ===============

const CircularTracker = ({ value, max, label, unit, color, size = 72, strokeWidth = 6 }) => {
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const pct = max > 0 ? Math.min(value / max, 1.2) : 0;
    const offset = circumference - pct * circumference;
    const isOver = value > max + 4;
    const displayColor = isOver ? '#EF4444' : color;

    return (
        <div className="flex flex-col items-center" data-testid={`tracker-${label.toLowerCase().replace(/\s/g, '-')}`}>
            <div className="relative" style={{ width: size, height: size }}>
                <svg width={size} height={size} className="-rotate-90">
                    <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#1A1A1A" strokeWidth={strokeWidth} />
                    <circle
                        cx={size / 2} cy={size / 2} r={radius}
                        fill="none" stroke={displayColor} strokeWidth={strokeWidth}
                        strokeDasharray={circumference} strokeDashoffset={offset}
                        strokeLinecap="round"
                        className="transition-all duration-700 ease-out"
                    />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-white font-bold text-sm leading-none" style={{ fontFamily: 'Bebas Neue' }}>
                        {Math.round(value)}
                    </span>
                    <span className="text-white/30 text-[9px] uppercase">{unit}</span>
                </div>
            </div>
            <span className="text-xs font-bold uppercase tracking-wider mt-1.5" style={{ color: displayColor }}>
                {label}
            </span>
        </div>
    );
};

// =============== CLIENT DASHBOARD ===============

const ClientDashboard = () => {
    const { user, profile, api } = useAuth();
    const navigate = useNavigate();
    const [routine, setRoutine] = useState(null);
    const [unreadMessages, setUnreadMessages] = useState(0);
    const [loading, setLoading] = useState(true);
    const [macros, setMacros] = useState(null);
    const [todayConsumed, setTodayConsumed] = useState({ P: 0, H: 0, G: 0 });
    const [hasDietToday, setHasDietToday] = useState(false);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const today = new Date().toISOString().split('T')[0];
                const [routineRes, messagesRes, macrosRes, dietRes] = await Promise.all([
                    api.get('/routines/current').catch(() => ({ data: null })),
                    api.get('/messages/unread-count').catch(() => ({ data: { count: 0 } })),
                    api.get('/macros').catch(() => ({ data: null })),
                    api.get(`/diets/${today}`).catch(() => ({ data: { exists: false } })),
                ]);
                setRoutine(routineRes.data);
                setUnreadMessages(messagesRes.data.count);
                setMacros(macrosRes.data);

                // Calculate consumed macros from today's diet
                const diet = dietRes.data;
                if (diet && diet.exists && diet.comidas) {
                    setHasDietToday(true);
                    let totalP = 0, totalH = 0, totalG = 0;
                    Object.values(diet.comidas).forEach(meal => {
                        (meal.alimentos || []).forEach(a => {
                            const ef = a.macros_efectivos || {};
                            totalP += ef.P || 0;
                            totalH += ef.H || 0;
                            totalG += ef.G || 0;
                        });
                    });
                    setTodayConsumed({ P: Math.round(totalP * 10) / 10, H: Math.round(totalH * 10) / 10, G: Math.round(totalG * 10) / 10 });
                }
            } catch (error) {
                console.error('Error fetching dashboard data:', error);
            } finally {
                setLoading(false);
            }
        };
        if (profile) { fetchData(); } else { setLoading(false); }
    }, [api, profile]);

    if (!profile) {
        return (
            <div className="p-4 md:p-6 animate-fade-in">
                <Card className="bg-[#111111] border-[#FF671F]/30">
                    <CardContent className="p-8 text-center">
                        <div className="w-16 h-16 bg-[#FF671F]/20 rounded-lg flex items-center justify-center mx-auto mb-4">
                            <Target className="w-8 h-8 text-[#FF671F]" />
                        </div>
                        <h2 className="text-xl font-bold text-white mb-2" style={{ fontFamily: 'Bebas Neue' }}>BIENVENIDO A JG12</h2>
                        <p className="text-white/60 mb-6 text-sm">Para comenzar tu transformación, selecciona un plan.</p>
                        <Button onClick={() => navigate('/onboarding')} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold uppercase tracking-wider" data-testid="onboarding-btn">
                            Seleccionar Plan <ChevronRight className="w-4 h-4 ml-2" />
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    const mt = macros?.training || profile?.macros_training;
    const mr = macros?.rest || profile?.macros_rest;
    const mp = macros?.periworkout || profile?.macros_periworkout;
    const source = macros?.source || profile?.macros_source;
    const hasMacros = mt && (mt.protein || mt.proteinas);

    const getP = (m) => m?.protein || m?.proteinas || 0;
    const getH = (m) => m?.carbs || m?.hidratos || 0;
    const getG = (m) => m?.fat || m?.grasas || 0;
    const getKcal = (m) => Math.round(getP(m) * 4 + getH(m) * 4 + getG(m) * 9);

    const consumedKcal = Math.round(todayConsumed.P * 4 + todayConsumed.H * 4 + todayConsumed.G * 9);

    const weekProgress = (profile.week / 4) * 100;
    const todayRoutine = routine?.days?.find(d =>
        d.day.toLowerCase() === new Date().toLocaleDateString('es-ES', { weekday: 'long' }).toLowerCase()
    );
    const isRestDay = todayRoutine?.is_rest;
    const activeTarget = isRestDay ? mr : mt;

    return (
        <div className="p-4 md:p-6 space-y-5 animate-fade-in pb-24 md:pb-6" data-testid="client-dashboard">
            {/* Welcome Header */}
            <div className="flex items-start justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: 'Bebas Neue' }}>
                        HOLA, {user?.name?.split(' ')[0]?.toUpperCase()}
                    </h1>
                    <div className="flex items-center gap-3 mt-1">
                        <PlanBadge plan={profile.plan} />
                        <span className="text-white/40 text-xs">Semana {profile.week}/4</span>
                    </div>
                </div>
                {unreadMessages > 0 && (
                    <Button variant="outline" size="icon" className="relative bg-transparent border-white/20 hover:border-[#FF671F] hover:bg-[#FF671F]/10" onClick={() => navigate('/dashboard/messages')} data-testid="notif-btn">
                        <Bell className="w-4 h-4 text-white" />
                        <span className="absolute -top-1 -right-1 w-5 h-5 bg-[#FF671F] text-white text-xs rounded-full flex items-center justify-center font-bold">{unreadMessages}</span>
                    </Button>
                )}
            </div>

            {/* Today's Progress */}
            {hasMacros ? (
                <Card className="bg-[#111111] border-[#222] overflow-hidden" data-testid="macro-trackers-card" onClick={() => navigate('/dashboard/nutrition')} style={{ cursor: 'pointer' }}>
                    <CardContent className="p-0">
                        {/* Today header */}
                        <div className="px-4 pt-4 pb-2 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                {isRestDay
                                    ? <Activity className="w-4 h-4 text-green-400" />
                                    : <Flame className="w-4 h-4 text-[#FF671F]" />
                                }
                                <span className="text-xs font-bold text-white uppercase tracking-wider">
                                    Hoy &middot; {isRestDay ? 'Descanso' : 'Entreno'}
                                </span>
                            </div>
                            <div className="text-right">
                                <span className="text-2xl font-bold" style={{ fontFamily: 'Bebas Neue', color: isRestDay ? '#22C55E' : '#FF671F' }} data-testid="kcal-consumed">
                                    {consumedKcal}
                                </span>
                                <span className="text-white/30 text-xs"> / {getKcal(activeTarget)} kcal</span>
                            </div>
                        </div>

                        {/* Trackers — consumed vs target */}
                        <div className="px-4 pb-4 pt-2">
                            <div className="flex items-center justify-around">
                                <CircularTracker value={todayConsumed.P} max={getP(activeTarget)} label="Proteína" unit="g" color="#3B82F6" size={80} />
                                <CircularTracker value={todayConsumed.H} max={getH(activeTarget)} label="Hidratos" unit="g" color="#F59E0B" size={80} />
                                <CircularTracker value={todayConsumed.G} max={getG(activeTarget)} label="Grasa" unit="g" color="#EF4444" size={80} />
                            </div>
                            {/* Legend row */}
                            <div className="flex items-center justify-center gap-4 mt-3">
                                <MacroBar label="P" consumed={todayConsumed.P} target={getP(activeTarget)} color="#3B82F6" />
                                <MacroBar label="H" consumed={todayConsumed.H} target={getH(activeTarget)} color="#F59E0B" />
                                <MacroBar label="G" consumed={todayConsumed.G} target={getG(activeTarget)} color="#EF4444" />
                            </div>
                        </div>

                        {/* Compact target summary */}
                        <div className="border-t border-[#1A1A1A] px-4 py-2.5 flex items-center justify-between">
                            <div className="flex items-center gap-4 text-[10px] text-white/30 uppercase tracking-wider">
                                <span>Entreno: {getKcal(mt)} kcal</span>
                                <span>Descanso: {getKcal(mr)} kcal</span>
                                {mp && getP(mp) > 0 && <span>Peri: {getP(mp)}P/{getH(mp)}H</span>}
                            </div>
                            {source && (
                                <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${
                                    source === 'auto' ? 'bg-green-500/10 text-green-500/60' : 'bg-yellow-500/10 text-yellow-500/60'
                                }`}>{source}</span>
                            )}
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <Card className="bg-[#111111] border-[#FF671F]/30 cursor-pointer hover:border-[#FF671F]/60 transition-all" onClick={() => navigate('/dashboard/profile')} data-testid="setup-macros-card">
                    <CardContent className="p-5 text-center">
                        <Scale className="w-8 h-8 text-[#FF671F] mx-auto mb-2" />
                        <p className="font-bold text-white text-sm uppercase">Configura tus macros</p>
                        <p className="text-white/40 text-xs mt-1">Introduce tu peso, % graso y objetivo</p>
                    </CardContent>
                </Card>
            )}

            {/* Progress Bar */}
            <div className="bg-[#111111] rounded-xl p-3 border border-[#222]">
                <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-white/50 uppercase tracking-wider">Ciclo</span>
                    <span className="text-xs text-white/40">Semana {profile.week}/4</span>
                </div>
                <div className="w-full bg-[#1A1A1A] rounded-full h-1.5">
                    <div className="bg-[#FF671F] h-1.5 rounded-full transition-all duration-500" style={{ width: `${weekProgress}%` }} />
                </div>
            </div>

            {/* Quick Actions Grid */}
            <div className="grid grid-cols-2 gap-3">
                <Card className="col-span-2 bg-[#111111] border-[#222] cursor-pointer hover:border-[#FF671F]/50 transition-all group" onClick={() => navigate('/dashboard/routine')} data-testid="routine-card">
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 bg-[#FF671F]/10 rounded-lg flex items-center justify-center group-hover:bg-[#FF671F]/20 transition-colors">
                                    <Dumbbell className="w-5 h-5 text-[#FF671F]" />
                                </div>
                                <div>
                                    <p className="font-bold text-white text-sm uppercase">Hoy &middot; <span className="capitalize font-normal text-white/50">{new Date().toLocaleDateString('es-ES', { weekday: 'long' })}</span></p>
                                    {todayRoutine ? (
                                        todayRoutine.is_rest
                                            ? <p className="text-white/50 text-xs">Descanso activo</p>
                                            : <p className="text-white/60 text-xs">{todayRoutine.exercises?.length || 0} ejercicios</p>
                                    ) : (
                                        <p className="text-white/40 text-xs">Sin rutina asignada</p>
                                    )}
                                </div>
                            </div>
                            <ChevronRight className="w-5 h-5 text-white/20 group-hover:text-[#FF671F] transition-colors" />
                        </div>
                    </CardContent>
                </Card>
                <QuickCard icon={Apple} color="#22C55E" label="Nutrición" sub="Montar dieta" path="/dashboard/nutrition" navigate={navigate} testId="macros-card" />
                <QuickCard icon={Bot} color="#8B5CF6" label="Asistente IA" sub="Dieta con IA" path="/dashboard/chatbot" navigate={navigate} testId="chatbot-card" />
                <QuickCard icon={FileText} color="#EAB308" label="Reportes" sub="Ver evolución" path="/dashboard/reports" navigate={navigate} testId="reports-card" />
                <div className="relative">
                    <QuickCard icon={MessageCircle} color="#A855F7" label="Chat" sub={unreadMessages > 0 ? `${unreadMessages} sin leer` : 'Entrenador'} path="/dashboard/messages" navigate={navigate} testId="messages-card" />
                    {unreadMessages > 0 && <span className="absolute top-3 right-3 w-2.5 h-2.5 bg-[#FF671F] rounded-full animate-pulse" />}
                </div>
            </div>

            {/* Next Payment */}
            {profile.next_payment && (
                <div className="bg-[#111111] rounded-xl p-3 border border-[#222] flex items-center gap-3">
                    <CreditCard className="w-4 h-4 text-white/30" />
                    <div className="flex-1">
                        <p className="text-xs text-white/40">Próxima renovación</p>
                        <p className="text-sm text-white/70">
                            {new Date(profile.next_payment).toLocaleDateString('es-ES', { day: 'numeric', month: 'long' })} — <span className="text-[#FF671F] font-bold">{profile.price}</span>
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
};

// =============== MACRO BAR (compact) ===============

const MacroBar = ({ label, consumed, target, color }) => {
    const pct = target > 0 ? Math.min((consumed / target) * 100, 100) : 0;
    return (
        <div className="flex items-center gap-1.5 min-w-0">
            <span className="text-[10px] font-bold uppercase" style={{ color }}>{label}</span>
            <div className="w-16 h-1 bg-[#1A1A1A] rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
            </div>
            <span className="text-[10px] text-white/40 tabular-nums">{Math.round(consumed)}/{Math.round(target)}</span>
        </div>
    );
};

// =============== QUICK CARD ===============

const QuickCard = ({ icon: Icon, color, label, sub, path, navigate, testId }) => (
    <Card className="bg-[#111111] border-[#222] cursor-pointer hover:border-[#FF671F]/50 transition-all group" onClick={() => navigate(path)} data-testid={testId}>
        <CardContent className="p-3.5">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-2 group-hover:scale-105 transition-transform" style={{ backgroundColor: `${color}15` }}>
                <Icon className="w-4.5 h-4.5" style={{ color }} />
            </div>
            <p className="font-bold text-white uppercase text-xs tracking-wider">{label}</p>
            <p className="text-white/40 text-xs mt-0.5">{sub}</p>
        </CardContent>
    </Card>
);

// =============== CLIENT LAYOUT ===============

const ClientLayout = () => {
    const { user, logout, profile } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    const navItems = [
        { path: '/dashboard', icon: Home, label: 'Inicio' },
        { path: '/dashboard/routine', icon: Dumbbell, label: 'Rutina' },
        { path: '/dashboard/nutrition', icon: Apple, label: 'Nutrición' },
        { path: '/dashboard/foods', icon: Search, label: 'Alimentos' },
        { path: '/dashboard/macro-calculator', icon: Calculator, label: 'Ajustar macros' },
        { path: '/dashboard/chatbot', icon: Bot, label: 'Asistente IA' },
        { path: '/dashboard/reports', icon: FileText, label: 'Reportes' },
        { path: '/dashboard/messages', icon: MessageCircle, label: 'Chat' },
    ];

    const isActive = (path) => path === '/dashboard' ? location.pathname === '/dashboard' : location.pathname.startsWith(path);
    const handleLogout = () => { logout(); navigate('/auth'); toast.success('Sesión cerrada'); };

    return (
        <div className="min-h-screen bg-[#0A0A0A] flex">
            <aside className="hidden md:flex flex-col w-64 border-r border-white/10 bg-[#0A0A0A] h-screen sticky top-0 flex-shrink-0">
                <div className="p-6 border-b border-white/10">
                    <JG12Logo size="md" />
                    <p className="text-white/40 text-xs uppercase tracking-wider mt-1">Portal Cliente</p>
                </div>
                <ScrollArea className="flex-1 p-4">
                    <nav className="space-y-1">
                        {navItems.map((item) => (
                            <Link key={item.path} to={item.path} className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${isActive(item.path) ? 'bg-[#FF671F] text-white' : 'text-white/60 hover:text-white hover:bg-white/5'}`}>
                                <item.icon className="w-5 h-5" /><span className="font-medium">{item.label}</span>
                            </Link>
                        ))}
                        <Link to="/dashboard/profile" className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${isActive('/dashboard/profile') ? 'bg-[#FF671F] text-white' : 'text-white/60 hover:text-white hover:bg-white/5'}`}>
                            <User className="w-5 h-5" /><span className="font-medium">Mi Perfil</span>
                        </Link>
                    </nav>
                </ScrollArea>
                <div className="p-4 border-t border-white/10">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 bg-[#222222] rounded-lg flex items-center justify-center"><span className="text-[#FF671F] font-bold">{user?.name?.charAt(0)}</span></div>
                        <div className="flex-1 min-w-0"><p className="font-medium text-white text-sm truncate">{user?.name}</p>{profile && <PlanBadge plan={profile.plan} />}</div>
                    </div>
                    <Button variant="ghost" className="w-full justify-start text-white/50 hover:text-red-500 hover:bg-red-500/10" onClick={handleLogout} data-testid="logout-btn">
                        <LogOut className="w-4 h-4 mr-2" /> Cerrar sesión
                    </Button>
                </div>
            </aside>
            <main className="flex-1 overflow-auto pb-16 md:pb-0"><Outlet /></main>
            <nav className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-gray-200 shadow-lg md:hidden" data-testid="mobile-nav">
                <div className="flex items-center justify-around h-16 px-2">
                    {[
                        { path: '/dashboard', icon: Home, label: 'Inicio' },
                        { path: '/dashboard/nutrition', icon: Apple, label: 'Nutrición' },
                        { path: '/dashboard/routine', icon: Dumbbell, label: 'Rutina' },
                        { path: '/dashboard/macro-calculator', icon: Calculator, label: 'Macros' },
                        { path: '/dashboard/profile', icon: User, label: 'Más' },
                    ].map((item) => {
                        const active = isActive(item.path);
                        return (
                            <Link key={item.path} to={item.path} className={`flex flex-col items-center justify-center flex-1 py-2 transition-all duration-200 ${active ? 'text-[#FFA500]' : 'text-gray-400'}`}>
                                <item.icon className={`w-5 h-5 mb-1 transition-all duration-200 ${active ? 'text-[#FFA500] scale-110' : 'text-gray-400'}`} strokeWidth={active ? 2.5 : 2} />
                                <span className={`text-xs ${active ? 'font-bold' : 'font-medium'}`}>{item.label}</span>
                            </Link>
                        );
                    })}
                </div>
            </nav>
        </div>
    );
};

export { ClientDashboard, ClientLayout, PlanBadge, JG12Logo };
