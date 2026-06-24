import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, Outlet, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import {
    Home, Dumbbell, Apple, FileText, MessageCircle, User,
    LogOut, Bell, ChevronRight, CreditCard, Target, Bot,
    Flame, Activity, Scale, Search, SlidersHorizontal, Pill,
    ClipboardCheck, Menu, X, PanelLeftClose, PanelLeftOpen
} from 'lucide-react';
import Logo12EN12 from '../components/Logo12EN12';
import ThemeToggle from '../components/ThemeToggle';

// ===== Macro colors (identidad 12EN12) =====
const MACRO = { protein: '#FF671F', carbs: '#2196F3', fat: '#FFA500' };

// testids ASCII-estables (sin diacríticos)
const slug = (s) => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, '-');

// ===== Shared brand bits =====
const JG12Logo = ({ size = 'md', tone = 'dark' }) => <Logo12EN12 size={size} tone={tone} />;

const PlanBadge = ({ plan }) => {
    const cls = {
        gold: 'badge-gold', silver: 'badge-silver', bronze: 'badge-bronze', elm: 'badge-elm',
    }[plan] || 'badge-silver';
    return <span className={cls} data-testid="plan-badge">{plan?.toUpperCase()}</span>;
};

// ===== Circular tracker (light) =====
const CircularTracker = ({ value, max, label, unit, color, size = 84, strokeWidth = 7 }) => {
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const pct = max > 0 ? Math.min(value / max, 1.2) : 0;
    const offset = circumference - pct * circumference;
    const isOver = value > max + 4;
    const displayColor = isOver ? '#DC2626' : color;
    return (
        <div className="flex flex-col items-center" data-testid={`tracker-${label.toLowerCase()}`}>
            <div className="relative" style={{ width: size, height: size }}>
                <svg width={size} height={size} className="-rotate-90">
                    <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="hsl(var(--track))" strokeWidth={strokeWidth} />
                    <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={displayColor} strokeWidth={strokeWidth}
                        strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
                        className="transition-all duration-700 ease-out" />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="font-data text-foreground font-bold text-lg leading-none">{Math.round(value)}</span>
                    <span className="text-muted-foreground text-[9px] uppercase font-semibold">{unit}</span>
                </div>
            </div>
            <span className="text-[11px] font-bold uppercase tracking-wider mt-2" style={{ color: displayColor }}>{label}</span>
        </div>
    );
};

const MacroBar = ({ label, consumed, target, color }) => {
    const pct = target > 0 ? Math.min((consumed / target) * 100, 100) : 0;
    return (
        <div className="flex items-center gap-2 min-w-0">
            <span className="text-[11px] font-bold uppercase" style={{ color }}>{label}</span>
            <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
            </div>
            <span className="text-[11px] text-muted-foreground font-data">{Math.round(consumed)}/{Math.round(target)}</span>
        </div>
    );
};

const QuickCard = ({ icon: Icon, color, label, sub, path, navigate, testId, badge }) => (
    <button onClick={() => navigate(path)} data-testid={testId}
        className="surface surface-hover text-left p-4 group relative">
        {badge > 0 && <span className="absolute top-3 right-3 w-2.5 h-2.5 bg-brand rounded-full animate-pulse" />}
        <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-3 transition-transform group-hover:scale-105"
            style={{ backgroundColor: `${color}14` }}>
            <Icon className="w-5 h-5" style={{ color }} strokeWidth={2.2} />
        </div>
        <p className="font-bold text-foreground uppercase text-[13px] tracking-wide">{label}</p>
        <p className="text-muted-foreground text-xs mt-0.5">{sub}</p>
    </button>
);

// =============== CLIENT DASHBOARD ===============

const ClientDashboard = () => {
    const { user, profile, api } = useAuth();
    const navigate = useNavigate();
    const [routine, setRoutine] = useState(null);
    const [unreadMessages, setUnreadMessages] = useState(0);
    const [macros, setMacros] = useState(null);
    const [todayConsumed, setTodayConsumed] = useState({ P: 0, H: 0, G: 0 });

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
                const diet = dietRes.data;
                if (diet && diet.exists && diet.comidas) {
                    let totalP = 0, totalH = 0, totalG = 0;
                    Object.values(diet.comidas).forEach(meal => {
                        (meal.alimentos || []).forEach(a => {
                            const ef = a.macros_efectivos || {};
                            totalP += ef.P || 0; totalH += ef.H || 0; totalG += ef.G || 0;
                        });
                    });
                    setTodayConsumed({ P: Math.round(totalP * 10) / 10, H: Math.round(totalH * 10) / 10, G: Math.round(totalG * 10) / 10 });
                }
            } catch (error) {
                console.error('Error fetching dashboard data:', error);
            }
        };
        if (profile) fetchData();
    }, [api, profile]);

    if (!profile) {
        return (
            <div className="px-4 sm:px-6 lg:px-8 py-8 max-w-2xl mx-auto animate-fade-in">
                <div className="surface p-8 text-center">
                    <div className="w-16 h-16 bg-brand/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <Target className="w-8 h-8 text-brand" />
                    </div>
                    <h2 className="heading-2 text-foreground mb-2">Bienvenido a 12EN12</h2>
                    <p className="text-muted-foreground mb-6 text-sm">Para comenzar tu transformación, selecciona un plan.</p>
                    <button onClick={() => navigate('/onboarding')} className="btn-brand inline-flex items-center gap-2" data-testid="onboarding-btn">
                        Seleccionar plan <ChevronRight className="w-4 h-4" />
                    </button>
                </div>
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
        d.day.toLowerCase() === new Date().toLocaleDateString('es-ES', { weekday: 'long' }).toLowerCase());
    const isRestDay = todayRoutine?.is_rest;
    const activeTarget = isRestDay ? mr : mt;

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6 animate-fade-in" data-testid="client-dashboard">
            {/* Header */}
            <header className="flex items-end justify-between gap-4">
                <div>
                    <p className="caption text-brand mb-1">Panel del cliente</p>
                    <h1 className="font-heading text-4xl md:text-5xl font-bold uppercase text-foreground leading-none">
                        Hola, {user?.name?.split(' ')[0]}
                    </h1>
                    <div className="flex items-center gap-3 mt-2">
                        <PlanBadge plan={profile.plan} />
                        <span className="text-muted-foreground text-sm">Semana {profile.week}/4</span>
                    </div>
                </div>
                {unreadMessages > 0 && (
                    <button onClick={() => navigate('/dashboard/messages')} data-testid="notif-btn"
                        className="relative w-11 h-11 rounded-xl border border-border bg-card flex items-center justify-center hover:border-brand transition-colors">
                        <Bell className="w-5 h-5 text-foreground" />
                        <span className="absolute -top-1.5 -right-1.5 min-w-5 h-5 px-1 bg-brand text-white text-xs rounded-full flex items-center justify-center font-bold">{unreadMessages}</span>
                    </button>
                )}
            </header>

            {/* Main grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                {/* Macros / Today */}
                <div className="lg:col-span-8">
                    {hasMacros ? (
                        <div className="surface surface-hover overflow-hidden cursor-pointer h-full" data-testid="macro-trackers-card" onClick={() => navigate('/dashboard/nutrition')}>
                            <div className="px-5 pt-5 pb-3 flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    {isRestDay ? <Activity className="w-4 h-4 text-emerald-500" /> : <Flame className="w-4 h-4 text-brand" />}
                                    <span className="text-xs font-bold text-foreground uppercase tracking-wider">Hoy · {isRestDay ? 'Descanso' : 'Entreno'}</span>
                                </div>
                                <div className="text-right">
                                    <span className="font-data font-bold text-2xl" style={{ color: isRestDay ? '#10B981' : MACRO.protein }} data-testid="kcal-consumed">{consumedKcal}</span>
                                    <span className="text-muted-foreground text-sm font-data"> / {getKcal(activeTarget)} kcal</span>
                                </div>
                            </div>
                            <div className="px-5 pb-5 pt-1">
                                <div className="flex items-center justify-around">
                                    <CircularTracker value={todayConsumed.P} max={getP(activeTarget)} label="Proteína" unit="g" color={MACRO.protein} size={92} />
                                    <CircularTracker value={todayConsumed.H} max={getH(activeTarget)} label="Hidratos" unit="g" color={MACRO.carbs} size={92} />
                                    <CircularTracker value={todayConsumed.G} max={getG(activeTarget)} label="Grasa" unit="g" color={MACRO.fat} size={92} />
                                </div>
                                <div className="flex items-center justify-center gap-5 mt-4 flex-wrap">
                                    <MacroBar label="P" consumed={todayConsumed.P} target={getP(activeTarget)} color={MACRO.protein} />
                                    <MacroBar label="H" consumed={todayConsumed.H} target={getH(activeTarget)} color={MACRO.carbs} />
                                    <MacroBar label="G" consumed={todayConsumed.G} target={getG(activeTarget)} color={MACRO.fat} />
                                </div>
                            </div>
                            <div className="border-t border-border px-5 py-3 flex items-center justify-between">
                                <div className="flex items-center gap-4 text-[11px] text-muted-foreground uppercase tracking-wider font-data">
                                    <span>Entreno {getKcal(mt)}</span>
                                    <span>Descanso {getKcal(mr)}</span>
                                    {mp && getP(mp) > 0 && <span>Peri {getP(mp)}/{getH(mp)}</span>}
                                </div>
                                {source && (
                                    <span className={`text-[10px] px-2 py-0.5 rounded-md font-bold uppercase ${source === 'auto' ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400' : 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400'}`}>{source}</span>
                                )}
                            </div>
                        </div>
                    ) : (
                        <button onClick={() => navigate('/dashboard/macro-calculator')} data-testid="setup-macros-card"
                            className="surface surface-hover w-full p-6 text-center h-full">
                            <Scale className="w-8 h-8 text-brand mx-auto mb-2" />
                            <p className="font-bold text-foreground text-sm uppercase">Configura tus macros</p>
                            <p className="text-muted-foreground text-xs mt-1">Introduce tu peso, % graso y objetivo</p>
                        </button>
                    )}
                </div>

                {/* Side column */}
                <div className="lg:col-span-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-5">
                    {/* Cycle */}
                    <div className="surface p-4">
                        <div className="flex items-center justify-between mb-2">
                            <span className="caption">Ciclo</span>
                            <span className="text-xs text-muted-foreground font-data">{profile.week}/4</span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-2">
                            <div className="bg-brand h-2 rounded-full transition-all duration-500" style={{ width: `${weekProgress}%` }} />
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">Semana {profile.week} de tu ciclo de 4 semanas</p>
                    </div>
                    {/* Next payment */}
                    {profile.next_payment && (
                        <div className="surface p-4 flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-muted flex items-center justify-center flex-shrink-0">
                                <CreditCard className="w-5 h-5 text-muted-foreground" />
                            </div>
                            <div className="min-w-0">
                                <p className="caption">Próxima renovación</p>
                                <p className="text-sm text-foreground mt-0.5">
                                    {new Date(profile.next_payment).toLocaleDateString('es-ES', { day: 'numeric', month: 'long' })} · <span className="text-brand font-bold font-data">{profile.price}€</span>
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Today routine highlight */}
            <button onClick={() => navigate('/dashboard/routine')} data-testid="routine-card"
                className="surface surface-hover w-full p-5 flex items-center justify-between group">
                <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-brand/10 rounded-xl flex items-center justify-center group-hover:bg-brand/15 transition-colors">
                        <Dumbbell className="w-6 h-6 text-brand" />
                    </div>
                    <div className="text-left">
                        <p className="font-bold text-foreground text-sm uppercase tracking-wide">Entreno de hoy · <span className="capitalize font-medium text-muted-foreground">{new Date().toLocaleDateString('es-ES', { weekday: 'long' })}</span></p>
                        {todayRoutine ? (
                            todayRoutine.is_rest
                                ? <p className="text-muted-foreground text-sm">Día de descanso activo</p>
                                : <p className="text-muted-foreground text-sm">{todayRoutine.exercises?.length || 0} ejercicios programados</p>
                        ) : <p className="text-muted-foreground text-sm">Sin rutina asignada</p>}
                    </div>
                </div>
                <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors" />
            </button>

            {/* Quick actions */}
            <div>
                <p className="caption mb-3">Accesos rápidos</p>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <QuickCard icon={Apple} color="#16A34A" label="Nutrición" sub="Montar dieta" path="/dashboard/nutrition" navigate={navigate} testId="nutrition-quick" />
                    <QuickCard icon={SlidersHorizontal} color={MACRO.protein} label="Macros" sub="Ajustar valores" path="/dashboard/macro-calculator" navigate={navigate} testId="macros-card" />
                    <QuickCard icon={Bot} color="#7C3AED" label="Asistente IA" sub="Dieta con IA" path="/dashboard/chatbot" navigate={navigate} testId="chatbot-card" />
                    <QuickCard icon={FileText} color="#CA8A04" label="Reportes" sub="Ver evolución" path="/dashboard/reports" navigate={navigate} testId="reports-card" />
                    <QuickCard icon={Search} color="#0891B2" label="Alimentos" sub="Buscador" path="/dashboard/foods" navigate={navigate} testId="foods-card" />
                    <QuickCard icon={Pill} color="#DB2777" label="Suplementos" sub="Tu protocolo" path="/dashboard/supplements" navigate={navigate} testId="supplements-card" />
                    <QuickCard icon={ClipboardCheck} color="#2563EB" label="Check-ins" sub="Seguimiento" path="/dashboard/checkins" navigate={navigate} testId="checkins-card" />
                    <QuickCard icon={MessageCircle} color="#9333EA" label="Chat" sub={unreadMessages > 0 ? `${unreadMessages} sin leer` : 'Tu entrenador'} path="/dashboard/messages" navigate={navigate} testId="messages-card" badge={unreadMessages} />
                </div>
            </div>
        </div>
    );
};

// =============== NAV CONFIG ===============

const NAV_ITEMS = [
    { path: '/dashboard', icon: Home, label: 'Inicio', end: true },
    { path: '/dashboard/routine', icon: Dumbbell, label: 'Rutina' },
    { path: '/dashboard/nutrition', icon: Apple, label: 'Nutrición' },
    { path: '/dashboard/foods', icon: Search, label: 'Alimentos' },
    { path: '/dashboard/macro-calculator', icon: SlidersHorizontal, label: 'Ajustar macros' },
    { path: '/dashboard/supplements', icon: Pill, label: 'Suplementos' },
    { path: '/dashboard/chatbot', icon: Bot, label: 'Asistente IA' },
    { path: '/dashboard/reports', icon: FileText, label: 'Reportes' },
    { path: '/dashboard/checkins', icon: ClipboardCheck, label: 'Check-ins' },
    { path: '/dashboard/messages', icon: MessageCircle, label: 'Chat' },
    { path: '/dashboard/profile', icon: User, label: 'Mi perfil' },
];

const BOTTOM_ITEMS = [
    { path: '/dashboard', icon: Home, label: 'Inicio', end: true },
    { path: '/dashboard/nutrition', icon: Apple, label: 'Nutrición' },
    { path: '/dashboard/routine', icon: Dumbbell, label: 'Rutina' },
    { path: '/dashboard/macro-calculator', icon: SlidersHorizontal, label: 'Macros' },
];

const SidebarLink = ({ item, collapsed, unread, onClick }) => (
    <NavLink to={item.path} end={item.end} onClick={onClick}
        title={collapsed ? item.label : undefined}
        className={({ isActive }) => `relative flex items-center gap-3 rounded-xl transition-all ${collapsed ? 'justify-center px-0 py-3' : 'px-3.5 py-2.5'} ${isActive ? 'bg-brand text-white font-semibold' : 'text-white/60 hover:text-white hover:bg-white/[0.07]'}`}
        data-testid={`nav-${slug(item.label)}`}>
        <span className="relative flex-shrink-0">
            <item.icon className="w-5 h-5" strokeWidth={2} />
            {item.path.includes('messages') && unread > 0 && (
                <span className="absolute -top-1.5 -right-1.5 min-w-4 h-4 px-1 bg-brand text-white text-[10px] rounded-full flex items-center justify-center font-bold border border-ink">{unread}</span>
            )}
        </span>
        {!collapsed && <span className="text-sm">{item.label}</span>}
    </NavLink>
);

// =============== CLIENT LAYOUT ===============

const ClientLayout = () => {
    const { user, logout, profile, api } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar-collapsed') === '1');
    const [drawerOpen, setDrawerOpen] = useState(false);
    const [unread, setUnread] = useState(0);

    useEffect(() => {
        api.get('/messages/unread-count').then(r => setUnread(r.data.count || 0)).catch(() => {});
    }, [api, location.pathname]);

    // Cuestionario inicial obligatorio: tras elegir plan (perfil creado), si no lo ha
    // completado, forzar el quiz.
    useEffect(() => {
        if (profile && !profile.questionnaire_completed) {
            navigate('/questionnaire', { replace: true });
        }
    }, [profile, navigate]);

    useEffect(() => { setDrawerOpen(false); }, [location.pathname]);

    const toggleCollapsed = useCallback(() => {
        setCollapsed(c => { localStorage.setItem('sidebar-collapsed', !c ? '1' : '0'); return !c; });
    }, []);

    const handleLogout = () => { logout(); navigate('/auth'); toast.success('Sesión cerrada'); };

    const UserChip = ({ compact }) => (
        <div className={`flex items-center gap-3 ${compact ? 'justify-center' : ''}`}>
            <div className="w-10 h-10 bg-brand/15 rounded-xl flex items-center justify-center flex-shrink-0">
                <span className="text-brand font-bold font-heading text-lg">{user?.name?.charAt(0)?.toUpperCase()}</span>
            </div>
            {!compact && (
                <div className="flex-1 min-w-0">
                    <p className="font-semibold text-white text-sm truncate">{user?.name}</p>
                    {profile && <PlanBadge plan={profile.plan} />}
                </div>
            )}
        </div>
    );

    return (
        <div className="min-h-screen bg-background flex">
            {/* ===== Desktop sidebar ===== */}
            <aside className={`hidden lg:flex flex-col bg-ink h-screen sticky top-0 flex-shrink-0 transition-[width] duration-300 ${collapsed ? 'w-[78px]' : 'w-64'}`} data-testid="desktop-sidebar">
                <div className={`flex items-center h-16 border-b border-white/10 ${collapsed ? 'justify-center px-0' : 'justify-between px-4'}`}>
                    {!collapsed && <Logo12EN12 size="sm" tone="dark" />}
                    <button onClick={toggleCollapsed} data-testid="sidebar-toggle"
                        className="w-9 h-9 rounded-lg flex items-center justify-center text-white/50 hover:text-white hover:bg-white/10 transition-colors">
                        {collapsed ? <PanelLeftOpen className="w-5 h-5" /> : <PanelLeftClose className="w-5 h-5" />}
                    </button>
                </div>
                <nav className="flex-1 overflow-y-auto no-scrollbar p-3 space-y-1">
                    {NAV_ITEMS.map(item => <SidebarLink key={item.path} item={item} collapsed={collapsed} unread={unread} />)}
                </nav>
                <div className="p-3 border-t border-white/10 space-y-2">
                    <UserChip compact={collapsed} />
                    {collapsed
                        ? <div className="flex justify-center"><ThemeToggle variant="icon" testId="theme-toggle-sidebar" /></div>
                        : <ThemeToggle variant="sidebar" testId="theme-toggle-sidebar" />}
                    <button onClick={handleLogout} data-testid="logout-btn"
                        className={`flex items-center gap-2 w-full rounded-lg text-white/50 hover:text-red-400 hover:bg-red-500/10 transition-colors ${collapsed ? 'justify-center py-2.5' : 'px-3 py-2.5'}`}>
                        <LogOut className="w-4 h-4" /> {!collapsed && <span className="text-sm">Cerrar sesión</span>}
                    </button>
                </div>
            </aside>

            {/* ===== Main ===== */}
            <div className="flex-1 min-w-0 flex flex-col">
                {/* Mobile top bar */}
                <header className="lg:hidden sticky top-0 z-40 bg-ink h-14 flex items-center justify-between px-4">
                    <button onClick={() => setDrawerOpen(true)} data-testid="mobile-menu-btn"
                        className="w-10 h-10 -ml-2 rounded-lg flex items-center justify-center text-white/80 hover:bg-white/10">
                        <Menu className="w-6 h-6" />
                    </button>
                    <Logo12EN12 size="sm" tone="dark" />
                    <div className="flex items-center -mr-2">
                        <ThemeToggle variant="icon" testId="theme-toggle-topbar" />
                        <button onClick={() => navigate('/dashboard/messages')}
                            className="relative w-10 h-10 rounded-lg flex items-center justify-center text-white/80 hover:bg-white/10">
                            <Bell className="w-5 h-5" />
                            {unread > 0 && <span className="absolute top-1.5 right-1.5 w-2.5 h-2.5 bg-brand rounded-full" />}
                        </button>
                    </div>
                </header>

                <main className="flex-1 pb-20 lg:pb-0">
                    <Outlet />
                </main>
            </div>

            {/* ===== Mobile bottom nav ===== */}
            <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-50 bg-ink border-t border-white/10" data-testid="mobile-bottom-nav">
                <div className="flex items-stretch h-16">
                    {BOTTOM_ITEMS.map(item => (
                        <NavLink key={item.path} to={item.path} end={item.end}
                            className={({ isActive }) => `flex flex-col items-center justify-center flex-1 gap-1 transition-colors ${isActive ? 'text-brand' : 'text-white/55'}`}
                            data-testid={`bottomnav-${slug(item.label)}`}>
                            {({ isActive }) => (<>
                                <item.icon className="w-[22px] h-[22px]" strokeWidth={isActive ? 2.5 : 2} />
                                <span className={`text-[10px] ${isActive ? 'font-bold' : 'font-medium'}`}>{item.label}</span>
                            </>)}
                        </NavLink>
                    ))}
                    <button onClick={() => setDrawerOpen(true)} data-testid="bottomnav-mas"
                        className="flex flex-col items-center justify-center flex-1 gap-1 text-white/55">
                        <Menu className="w-[22px] h-[22px]" strokeWidth={2} />
                        <span className="text-[10px] font-medium">Más</span>
                    </button>
                </div>
            </nav>

            {/* ===== Mobile drawer ===== */}
            {drawerOpen && (
                <div className="lg:hidden fixed inset-0 z-[60]" data-testid="mobile-drawer">
                    <div className="absolute inset-0 bg-black/50 animate-fade-in" onClick={() => setDrawerOpen(false)} />
                    <div className="absolute inset-y-0 left-0 w-[82%] max-w-xs bg-ink flex flex-col animate-slide-up">
                        <div className="flex items-center justify-between h-14 px-4 border-b border-white/10">
                            <Logo12EN12 size="sm" tone="dark" />
                            <button onClick={() => setDrawerOpen(false)} data-testid="drawer-close"
                                className="w-9 h-9 rounded-lg flex items-center justify-center text-white/60 hover:bg-white/10">
                                <X className="w-5 h-5" />
                            </button>
                        </div>
                        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
                            {NAV_ITEMS.map(item => <SidebarLink key={item.path} item={item} collapsed={false} unread={unread} onClick={() => setDrawerOpen(false)} />)}
                        </nav>
                        <div className="p-3 border-t border-white/10 space-y-2">
                            <UserChip />
                            <ThemeToggle variant="sidebar" testId="theme-toggle-drawer" />
                            <button onClick={handleLogout}
                                className="flex items-center gap-2 w-full px-3 py-2.5 rounded-lg text-white/50 hover:text-red-400 hover:bg-red-500/10 transition-colors">
                                <LogOut className="w-4 h-4" /> <span className="text-sm">Cerrar sesión</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export { ClientDashboard, ClientLayout, PlanBadge, JG12Logo, MACRO };
