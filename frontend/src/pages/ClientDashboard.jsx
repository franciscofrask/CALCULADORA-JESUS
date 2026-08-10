import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, Outlet, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { leer as leerLocal, escribir as escribirLocal } from '../lib/almacenLocal';
import { plural } from '../lib/labels';
import { useEsTelefono } from '../lib/esTelefono';
import { useOnboarding } from '../context/OnboardingContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import {
    Home, Dumbbell, Apple, FileText, MessageCircle, User,
    LogOut, Bell, ChevronRight, CreditCard, Target, Bot,
    Flame, Activity, Scale, Search, SlidersHorizontal, Pill,
    ClipboardCheck, Menu, X, PanelLeftClose, PanelLeftOpen,
    CheckCircle2, Circle, Sparkles, LayoutDashboard, AlertTriangle, Phone, Clock, TrendingUp
} from 'lucide-react';
import Logo12EN12 from '../components/Logo12EN12';
import ThemeToggle from '../components/ThemeToggle';
import { seLeOfreceLaRevision } from '../lib/revision';
import LimiteDeError from '../components/LimiteDeError';

// ===== Macro colors (identidad 12EN12) =====
const MACRO = { protein: '#FF671F', carbs: '#2196F3', fat: '#FFA500' };

// testids ASCII-estables (sin diacríticos)
const slug = (s) => s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, '-');

// ===== Shared brand bits =====
const JG12Logo = ({ size = 'md', tone = 'dark' }) => <Logo12EN12 size={size} tone={tone} />;

const PlanBadge = ({ plan, planName }) => {
    // Quitar el sufijo "(legacy)" de la insignia: es info interna, no de cara al usuario.
    const label = (planName || plan?.toUpperCase() || '').replace(/\s*\(legacy\)/i, '').trim();
    if (!label) return <span className="badge-silver opacity-70" data-testid="plan-badge">Sin plan</span>;
    const cls = {
        gold: 'badge-gold', silver: 'badge-silver', bronze: 'badge-bronze', elm: 'badge-elm',
        reto12en12_gold: 'badge-gold', reto12en12_silver: 'badge-silver',
    }[plan] || 'badge-elm';
    return <span className={cls} data-testid="plan-badge">{label}</span>;
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

/**
 * UN MACRO DEL DÍA: el número grande, el nombre y cuánto es el objetivo.
 *
 * Sustituye al anillo + barra del panel (documento del 10-08, pantalla 4). Tres decisiones,
 * y las tres son suyas:
 *
 *  - «Los números suben de tamaño y se les quita el anillo». El anillo ocupaba 92 px para
 *    decir lo mismo que dice el número.
 *  - «"de 190" DEBAJO del número, no arriba en una franja aparte»: antes había que mirar a
 *    dos sitios para saber cuánto faltaba.
 *  - El nombre del macro debajo del número y en negrita.
 *
 * La barra fina de abajo se queda: es lo que sustituye al anillo de un vistazo y ocupa, en
 * palabras del documento, «una décima parte». Cuando se pasa del objetivo se pone en rojo,
 * que es la única alarma de esta pantalla.
 */
const MacroGrande = ({ valor, objetivo, label, color }) => {
    const pct = objetivo > 0 ? Math.min((valor / objetivo) * 100, 100) : 0;
    const pasado = valor > objetivo + 4;
    return (
        <div className="text-center" data-testid={`macro-${slug(label)}`}>
            <p className="font-data font-bold leading-none text-foreground text-[34px] sm:text-[40px]">
                {Math.round(valor)}
            </p>
            <p className="text-sm font-bold mt-1.5" style={{ color: pasado ? '#DC2626' : color }}>{label}</p>
            <p className="text-sm text-muted-foreground font-data">de {Math.round(objetivo)}</p>
            <div className="h-1 bg-muted rounded-full overflow-hidden mt-2">
                <div className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${pct}%`, backgroundColor: pasado ? '#DC2626' : color }} />
            </div>
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

// ===== Checklist de primeros pasos (onboarding) =====
const OnboardingChecklist = ({ steps, onDismiss, navigate, onResume, showResume }) => {
    const doneCount = steps.filter(s => s.done).length;
    const pct = Math.round((doneCount / steps.length) * 100);
    return (
        <div className="surface p-5 relative overflow-hidden" data-testid="onboarding-checklist">
            <div className="absolute top-0 right-0 w-40 h-40 bg-brand/5 rounded-full blur-3xl pointer-events-none" />
            <button onClick={onDismiss} data-testid="dismiss-checklist-btn"
                className="absolute top-3 right-3 w-8 h-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                title="Ocultar">
                <X className="w-4 h-4" />
            </button>
            <div className="flex items-center gap-2 mb-1">
                <Sparkles className="w-4 h-4 text-brand" />
                <p className="caption text-brand">Primeros pasos</p>
            </div>
            <h2 className="font-heading text-2xl font-bold uppercase text-foreground leading-none mb-1">Empieza aquí</h2>
            <p className="text-muted-foreground text-sm mb-4">Completa estos pasos para aprovechar al máximo tu plan.</p>

            {/* Barra de progreso */}
            <div className="flex items-center gap-3 mb-4">
                <div className="flex-1 bg-muted rounded-full h-2 overflow-hidden">
                    <div className="bg-brand h-2 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
                </div>
                <span className="text-xs font-data font-bold text-muted-foreground whitespace-nowrap">{doneCount}/{steps.length}</span>
            </div>

            <div className="space-y-2">
                {steps.map((s) => (
                    <button key={s.label} onClick={() => !s.done && navigate(s.path)}
                        disabled={s.done}
                        data-testid={`step-${s.id}`}
                        className={`w-full flex items-center gap-3 rounded-xl px-3.5 py-3 text-left transition-colors ${s.done ? 'bg-muted/50 cursor-default' : 'bg-muted/40 hover:bg-muted'}`}>
                        {s.done
                            ? <CheckCircle2 className="w-5 h-5 text-brand flex-shrink-0" />
                            : <Circle className="w-5 h-5 text-muted-foreground flex-shrink-0" />}
                        <div className="min-w-0 flex-1">
                            <p className={`text-sm font-bold ${s.done ? 'text-muted-foreground line-through' : 'text-foreground'}`}>{s.label}</p>
                            {!s.done && s.sub && <p className="text-xs text-muted-foreground">{s.sub}</p>}
                        </div>
                        {!s.done && <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />}
                    </button>
                ))}
            </div>

            {showResume && (
                <button onClick={onResume} data-testid="resume-tour-btn"
                    className="mt-4 w-full flex items-center justify-center gap-2 rounded-xl bg-brand/10 hover:bg-brand/15 text-brand font-bold text-sm py-3 transition-colors">
                    <Sparkles className="w-4 h-4" /> Continuar recorrido guiado
                </button>
            )}
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

// ─────────────────────────────────────────────────────────────────────────────
// EL PLAN SE ACABÓ (punto 41 del doc del 07-08).
//
// La calculadora antigua ya lo tenía resuelto y es lo que se copia: se corta el acceso, se
// dice que la suscripción ha caducado y se le da a quién escribir - con el chat de WhatsApp
// ya abierto y el mensaje escrito, porque si hay que redactarlo la mitad no escribe. Y se
// añade la salida de la que se habló: la Membresía, que es donde cae el que no renueva.
//
// OJO: el número de soporte hay que ponerlo. No estaba en ninguna parte del código y no me
// lo puedo inventar, así que hasta que Francisco lo diga se enseña el bloque sin el botón de
// WhatsApp en vez de un enlace que no lleva a nadie.
const WHATSAPP_SOPORTE = '';   // ← el número con prefijo y sin signos: "34600111222"
const MENSAJE_SOPORTE = 'Hola, soy {nombre}. Se me ha caducado la suscripción de 12EN12 y quiero saber cómo seguir.';

const PlanCaducado = ({ navigate, nombre }) => {
    const texto = MENSAJE_SOPORTE.replace('{nombre}', nombre || '');
    const enlace = WHATSAPP_SOPORTE
        ? `https://wa.me/${WHATSAPP_SOPORTE}?text=${encodeURIComponent(texto)}`
        : null;
    return (
        <div className="px-4 sm:px-6 lg:px-8 py-8 max-w-2xl mx-auto animate-fade-in" data-testid="plan-caducado">
            <div className="surface p-8 text-center">
                <div className="w-16 h-16 bg-brand/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <Clock className="w-8 h-8 text-brand" />
                </div>
                <h2 className="heading-2 text-foreground mb-2">Tu suscripción ha caducado</h2>
                <p className="text-muted-foreground mb-6 text-sm">
                    Ponte en contacto con nosotros y vemos cómo sigues.
                </p>
                {enlace ? (
                    <a href={enlace} target="_blank" rel="noopener noreferrer"
                        className="btn-brand inline-flex items-center gap-2" data-testid="soporte-whatsapp">
                        Escribir por WhatsApp <ChevronRight className="w-4 h-4" />
                    </a>
                ) : (
                    <p className="text-muted-foreground text-sm mb-2">Escríbenos y lo vemos.</p>
                )}
                {/* La alternativa de la que se habló: seguir con la Membresía en vez de irse. */}
                <div className="mt-6 pt-6 border-t border-border">
                    <p className="text-sm text-foreground font-medium mb-1">¿Prefieres seguir por tu cuenta?</p>
                    <p className="text-muted-foreground text-xs mb-3">
                        La Membresía son 97 €/mes y te deja la calculadora y tus alimentos.
                    </p>
                    <button onClick={() => navigate('/planes')} className="text-brand text-sm hover:underline" data-testid="ver-membresia">
                        Ver la Membresía
                    </button>
                </div>
            </div>
        </div>
    );
};

// =============== CLIENT DASHBOARD ===============

const ClientDashboard = () => {
    const { user, profile, api, myPlan, planUnpaid, can } = useAuth();
    const enTelefono = useEsTelefono();
    const { resumeTour, active: tourActive, completed: tourCompleted } = useOnboarding();
    const navigate = useNavigate();
    const [routine, setRoutine] = useState(null);
    const [unreadMessages, setUnreadMessages] = useState(0);
    const [macros, setMacros] = useState(null);
    const [todayConsumed, setTodayConsumed] = useState({ P: 0, H: 0, G: 0 });
    const [hasPreferences, setHasPreferences] = useState(true); // optimista: evita parpadeo del checklist
    const [hasDiet, setHasDiet] = useState(false);
    // POR CLIENTE (punto 4.7). Esta bandera dice si ya cerró el checklist, y guardada sin
    // dueño el segundo que entrara en el mismo navegador se lo encontraba cerrado sin haberlo
    // tocado. La verdad vive en su perfil, en el servidor; esto es solo caché.
    const [checklistDismissed, setChecklistDismissed] = useState(false);
    useEffect(() => {
        if (user?.id) setChecklistDismissed(leerLocal('onboarding-checklist-dismissed', user.id) === '1');
    }, [user?.id]);
    const [dashDataLoaded, setDashDataLoaded] = useState(false);
    const [dueReports, setDueReports] = useState([]);

    // La compra de la revisión suelta vive ahora en su pantalla (/dashboard/revision):
    // desde aquí solo se entra, que es lo que pide el documento del 06-08-2026.

    // El cierre/completado vive en el perfil (backend); localStorage es solo caché local.
    useEffect(() => {
        if (profile?.checklist_dismissed) {
            escribirLocal('onboarding-checklist-dismissed', user?.id, '1');
            setChecklistDismissed(true);
        }
    }, [profile?.checklist_dismissed, user?.id]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const today = new Date().toISOString().split('T')[0];
                const [routineRes, messagesRes, macrosRes, dietRes, prefsRes, dueRes] = await Promise.all([
                    api.get('/routines/current').catch(() => ({ data: null })),
                    api.get('/messages/unread-count').catch(() => ({ data: { count: 0 } })),
                    api.get('/macros').catch(() => ({ data: null })),
                    api.get(`/diets/${today}`).catch(() => ({ data: { exists: false } })),
                    api.get('/user/preferences').catch(() => ({ data: { has_preferences: true } })),
                    api.get('/reports/due').catch(() => ({ data: { items: [] } })),
                ]);
                setRoutine(routineRes.data);
                setUnreadMessages(messagesRes.data.count);
                setDueReports(dueRes.data.items || []);
                setMacros(macrosRes.data);
                setHasPreferences(!!prefsRes.data?.has_preferences);
                const diet = dietRes.data;
                let dietHasFood = false;
                if (diet && diet.exists && diet.comidas) {
                    let totalP = 0, totalH = 0, totalG = 0;
                    Object.values(diet.comidas).forEach(meal => {
                        (meal.alimentos || []).forEach(a => {
                            const ef = a.macros_efectivos || {};
                            totalP += ef.P || 0; totalH += ef.H || 0; totalG += ef.G || 0;
                            dietHasFood = true;
                        });
                    });
                    setTodayConsumed({ P: Math.round(totalP * 10) / 10, H: Math.round(totalH * 10) / 10, G: Math.round(totalG * 10) / 10 });
                }
                setHasDiet(dietHasFood);
                setDashDataLoaded(true);
            } catch (error) {
                console.error('Error fetching dashboard data:', error);
            }
        };
        if (profile) fetchData();
    }, [api, profile]);

    const dismissChecklist = useCallback(() => {
        escribirLocal('onboarding-checklist-dismissed', user?.id, '1');
        setChecklistDismissed(true);
        api.patch('/clients/onboarding', { checklist_dismissed: true }).catch(() => {});
    }, [api, user?.id]);

    // Al completar los 3 pasos una vez, el checklist queda cerrado para siempre
    // (si no, el paso "primer día de comidas" volvería a salir incompleto cada día).
    useEffect(() => {
        if (!dashDataLoaded || checklistDismissed || !profile) return;
        const mt0 = macros?.training || profile?.macros_training;
        const done = !!(mt0 && (mt0.protein || mt0.proteinas)) && hasPreferences && hasDiet;
        if (done) dismissChecklist();
    }, [dashDataLoaded, checklistDismissed, profile, macros, hasPreferences, hasDiet, dismissChecklist]);

    // AL QUE SE LE ACABÓ EL PLAN NO SE LE DA LA BIENVENIDA (punto 41 del doc del 07-08).
    // Hasta ahora el cliente que llevaba un año pagando y terminaba su ciclo veía la misma
    // pantalla que el que acaba de registrarse: "Bienvenido a 12EN12, selecciona un plan".
    // No es lo mismo no haber empezado que haber terminado. El servidor dice cuál de los
    // tres casos es (profile.acceso.motivo).
    if (profile?.acceso?.motivo === 'caducado') {
        return <PlanCaducado navigate={navigate} nombre={user?.name} />;
    }
    if (!profile || planUnpaid) {
        return (
            <div className="px-4 sm:px-6 lg:px-8 py-8 max-w-2xl mx-auto animate-fade-in">
                <div className="surface p-8 text-center">
                    <div className="w-16 h-16 bg-brand/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <Target className="w-8 h-8 text-brand" />
                    </div>
                    <h2 className="heading-2 text-foreground mb-2">Bienvenido a 12EN12</h2>
                    <p className="text-muted-foreground mb-6 text-sm">
                        {planUnpaid
                            ? 'El pago de tu plan no llegó a completarse. Elige un plan para terminar la compra.'
                            : 'Para comenzar tu transformación, selecciona un plan.'}
                    </p>
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

    const checklistSteps = [
        { id: 'macros', label: 'Tus macros están calculados', sub: 'Revisa tus objetivos', done: !!hasMacros, path: '/dashboard/nutrition' },
        { id: 'preferences', label: 'Configura tus preferencias de comida', sub: 'Qué te gusta y qué evitar', done: hasPreferences, path: '/dashboard/nutrition' },
        { id: 'diet', label: 'Prepara tu primer día de comidas', sub: 'Reparte tus macros en comidas', done: hasDiet, path: '/dashboard/nutrition' },
    ];
    const showChecklist = !checklistDismissed && checklistSteps.some(s => !s.done);

    // Ciclo del plan: nº de semanas (null si es mensual indefinido / variable).
    const cicloSemanas = myPlan?.ciclo?.semanas ?? null;
    const weekProgress = cicloSemanas ? Math.min((profile.week / cicloSemanas) * 100, 100) : null;
    const todayRoutine = routine?.days?.find(d =>
        d.day.toLowerCase() === new Date().toLocaleDateString('es-ES', { weekday: 'long' }).toLowerCase());
    const isRestDay = todayRoutine?.is_rest;
    const activeTarget = isRestDay ? mr : mt;

    // UN AVISO CADA VEZ, EL DE MÁS ARRIBA QUE CUMPLA (documento del 10-08, pantalla 4).
    //
    // Aquí salían apilados: el reporte que toca, la checklist de primeros pasos, el de
    // ajustar macros, el de elegir plan y el del perfil a medias. Cinco tarjetas grandes,
    // una debajo de otra, antes de llegar a nada. Cuando le pides cinco cosas a la vez no
    // le estás pidiendo ninguna.
    //
    // El orden es el del documento, adaptado a los avisos que hoy tienen dato de verdad.
    // Los que faltan por poder calcularlos -- «estos son tus macros provisionales» y «ya
    // puedes hacer tu revisión mensual» -- van cuando exista de dónde sacarlos, y su sitio
    // es esta lista.
    //
    // Y SOLO EN EL TELÉFONO: en escritorio se apilan como estaban, que ahí caben y el
    // rediseño todavía no ha llegado a esa vista. `enTelefono` mira el mismo corte que usa
    // Tailwind para `lg` (1024 px), porque esto no se puede resolver con una clase: no es
    // ocultar una tarjeta, es elegir cuál de las cinco se pinta.
    const avisoPendiente = (() => {
        if (!enTelefono) return null;                                 // en escritorio, todos
        if (!myPlan) return 'plan';                                   // sin plan no puede hacer nada
        if (profile?.questionnaire_completed && !profile?.ajuste_macros_completado
            && !profile?.macros_puestos_por_alguien) return 'ajustar';
        if (can('macros_personalizados') && profile?.questionnaire_completed
            && (profile?.ajuste_macros_completado || profile?.macros_puestos_por_alguien)
            && !profile?.questionnaire_nivel1_completed) return 'perfil';
        if (dueReports.length) return 'reporte';
        if (showChecklist) return 'checklist';
        return null;
    })();
    // En el teléfono manda la lista de arriba (uno solo); en escritorio, la condición de
    // siempre de cada tarjeta, que es como estaba.
    const sale = (id, condicionDeSiempre) => (enTelefono ? avisoPendiente === id : condicionDeSiempre);

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6 animate-fade-in" data-testid="client-dashboard">
            {/* LA CABECERA SE QUEDA como estaba: «Panel del cliente», el saludo y el plan
                contratado. La quité en la primera pasada por ganar los 300 px que ocupa, y
                Francisco la devolvió: «era info que no molestaba». Y es verdad que no
                molesta -- es lo primero que se lee y se lee de un vistazo --, así que lo
                que había que recortar no era esto.

                Lo único que no vuelve es la semana, que aquí salía al lado de la insignia
                del plan y ahora la lleva la tarjeta de Ciclo con su barra. Decirla dos
                veces en la misma pantalla sí sobraba. */}
            <header className="flex items-end justify-between gap-4">
                <div>
                    <p className="caption text-brand mb-1">Panel del cliente</p>
                    <h1 className="font-heading text-4xl md:text-5xl font-bold uppercase text-foreground leading-none">
                        Hola, {user?.name?.split(' ')[0]}
                    </h1>
                    <div className="flex items-center gap-3 mt-2">
                        <PlanBadge plan={profile.plan} planName={myPlan?.name} />
                        {/* La semana, solo en escritorio: en el teléfono la lleva la tarjeta
                            de Ciclo con su barra, y decirla dos veces en la misma pantalla
                            sobra. */}
                        <span className="hidden lg:inline text-muted-foreground text-sm">
                            {cicloSemanas ? `Semana ${profile.week}/${cicloSemanas}` : `Semana ${profile.week}`}
                        </span>
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

            {/* Reporte pendiente esta semana (amarillo en plazo, rojo vencido). Solo el
                primero: si le tocan dos, el segundo sale cuando mande el primero. */}
            {sale('reporte', dueReports.length > 0) && (enTelefono ? dueReports.slice(0, 1) : dueReports).map((r) => (
                <div key={r.tipo}
                    className={`surface p-4 flex flex-col sm:flex-row sm:items-center gap-3 border ${
                        r.overdue ? 'border-red-500/40 bg-red-500/5' : 'border-yellow-500/40 bg-yellow-500/5'
                    }`}
                    data-testid={`due-report-${r.tipo}`}>
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                        r.overdue ? 'bg-red-500/15' : 'bg-yellow-500/15'
                    }`}>
                        <AlertTriangle className={`w-5 h-5 ${r.overdue ? 'text-red-500' : 'text-yellow-500'}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-foreground font-semibold text-sm">
                            {r.overdue
                                ? `Tu ${r.tipo_label.toLowerCase()} está fuera de plazo`
                                : r.is_open
                                    ? `Tienes tu ${r.tipo_label.toLowerCase()} pendiente`
                                    : `Este fin de semana toca tu ${r.tipo_label.toLowerCase()}`}
                        </p>
                        <p className="text-muted-foreground text-xs">
                            {r.overdue
                                ? 'La ventana de esta semana se cerró; podrás enviarlo la próxima.'
                                : r.is_open
                                    ? `Rellénalo antes del ${r.deadline_label}.`
                                    : `La ventana abre el ${r.opens_label}.`}
                        </p>
                    </div>
                    {r.is_open && (
                        <button onClick={() => navigate('/dashboard/reports')}
                            className="btn-brand flex items-center gap-1.5 text-sm flex-shrink-0 self-start sm:self-auto"
                            data-testid={`due-report-btn-${r.tipo}`}>
                            Hacer reporte <ChevronRight className="w-4 h-4" />
                        </button>
                    )}
                </div>
            ))}

            {/* Checklist de primeros pasos */}
            {sale('checklist', showChecklist) && (
                <OnboardingChecklist steps={checklistSteps} onDismiss={dismissChecklist} navigate={navigate}
                    onResume={resumeTour} showResume={!tourCompleted && !tourActive} />
            )}

            {/* Main grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                {/* Macros / Today */}
                <div className="lg:col-span-8">
                    {hasMacros ? (
                        <div className="surface surface-hover overflow-hidden cursor-pointer h-full" data-testid="macro-trackers-card" onClick={() => navigate('/dashboard/nutrition')}>
                            {/* LA FECHA ARRIBA, y el tipo de día detrás (documento del 10-08,
                                pantalla 4). Antes ponía «Hoy · Entreno», que no sitúa: el
                                cliente que abre la app a las once de la noche o el que navega
                                a otro día necesita ver de qué día son estos números. */}
                            <div className="px-5 pt-5 pb-1">
                                <p className="text-sm font-semibold text-foreground first-letter:uppercase" data-testid="hoy-fecha">
                                    {new Date().toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' })}
                                    <span className="text-muted-foreground font-normal"> · {isRestDay ? 'descanso' : 'entreno'}</span>
                                </p>
                            </div>
                            <div className="px-5 pb-5 pt-3">
                                {/* NÚMEROS GRANDES, SIN ANILLO, SOLO EN MÓVIL. Del documento:
                                    «el anillo dice lo mismo que la barra, y la barra ocupa una
                                    décima parte». En el teléfono estaban las dos cosas -- tres
                                    anillos de 92 px y, debajo, tres barras con los mismos
                                    números --, media pantalla para decir una cosa dos veces.

                                    En escritorio se queda como estaba: ahí el sitio no es el
                                    problema y el rediseño todavía no ha llegado a esa vista. */}
                                <div className="grid grid-cols-3 gap-3 lg:hidden">
                                    <MacroGrande valor={todayConsumed.P} objetivo={getP(activeTarget)} label="Proteína" color={MACRO.protein} />
                                    <MacroGrande valor={todayConsumed.H} objetivo={getH(activeTarget)} label="Hidratos" color={MACRO.carbs} />
                                    <MacroGrande valor={todayConsumed.G} objetivo={getG(activeTarget)} label="Grasa" color={MACRO.fat} />
                                </div>
                                <div className="hidden lg:block">
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
                            </div>
                            <div className="border-t border-border px-5 py-3 flex items-center justify-between">
                                <div className="flex items-center gap-4 text-[11px] text-muted-foreground uppercase tracking-wider font-data">
                                    {/* «Perientreno», no «Peri» (punto 4.18). */}
                                    {mp && getP(mp) > 0 && <span>Perientreno {getP(mp)}/{getH(mp)}</span>}
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

                {/* La columna de al lado, tal cual estaba. EL CICLO SE QUEDA también en el
                    teléfono: lo quité en la primera pasada por considerarlo repetido con la
                    semana de la cabecera, y Francisco lo devolvió. El número dice en qué
                    semana está; la barra dice cuánto le queda, que es lo que sitúa en un
                    método que se llama 12 en 12. */}
                <div className="lg:col-span-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-5">
                <div className="surface p-4">
                    <div className="flex items-center justify-between mb-2">
                        <span className="caption">Ciclo</span>
                        <span className="text-xs text-muted-foreground font-data">
                            {cicloSemanas ? `${profile.week}/${cicloSemanas}` : `Semana ${profile.week}`}
                        </span>
                    </div>
                    {cicloSemanas ? (
                        <>
                            <div className="w-full bg-muted rounded-full h-2">
                                <div className="bg-brand h-2 rounded-full transition-all duration-500" style={{ width: `${weekProgress}%` }} />
                            </div>
                            <p className="text-xs text-muted-foreground mt-2">Semana {profile.week} de tu ciclo de {plural(cicloSemanas, 'semana')}</p>
                        </>
                    ) : (
                        <p className="text-xs text-muted-foreground mt-1">Plan mensual · semana {profile.week}</p>
                    )}
                    {(myPlan?.habilitaciones?.reportes?.length > 0) && (
                        <p className="text-[11px] text-muted-foreground mt-2 capitalize">
                            Reportes: {myPlan.habilitaciones.reportes.join(' + ')}
                        </p>
                    )}
                </div>

                {/* La próxima renovación, solo en escritorio: en el teléfono es de Mi perfil,
                    que es donde alguien va a mirar qué paga y cuándo. */}
                {profile.next_payment && (
                    <div className="hidden lg:flex surface p-4 items-center gap-3">
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

            {/* Ajustar macros: el cuestionario del paso 2. Sale mientras tenga los macros
                provisionales del alta, porque hasta que lo rellene sus numeros no estan ajustados.
                En el plan con coach el boton se llama "Rellena tu formulario", que es lo que es:
                el coach lo revisa con el despues. */}
            {/* Aquí se separan los planes: el mismo hueco dice tres cosas distintas.
                El Nivel 3 no rellena nada -- se lo preguntan en la llamada -- así que ni
                se le manda al cuestionario ni se le dice que le falta algo por hacer. */}
            {/* Y SOLO SI DE VERDAD LE FALTA (punto 4.1). `ajuste_macros_completado` es False
                para todo el que no pasó por NUESTRO cuestionario de ajuste, y eso son los 160
                que vinieron de Calma más todo aquel al que el coach le puso los macros a mano:
                medido en producción, 169 de los 174 activos veían este aviso. Gente que lleva
                meses con Jesús, a la que él mismo les pone los números cada quincena, abriendo
                la app y leyendo que les falta terminar de sacar sus macros.
                `macros_puestos_por_alguien` lo calcula el servidor mirando quién escribió su
                último ajuste. */}
            {sale('ajustar', profile?.questionnaire_completed && !profile?.ajuste_macros_completado
                && !profile?.macros_puestos_por_alguien) && (() => {
                const porLlamada = (profile?.plan || '') === 'nivel3';
                const conCoach = can('macros_personalizados');
                const texto = porLlamada
                    ? { titulo: 'Agenda tu llamada',
                        desc: 'Tus macros los sacamos contigo en la llamada. No tienes que rellenar nada.' }
                    : conCoach
                        ? { titulo: 'Completa tu cuestionario inicial',
                            desc: 'Unas preguntas más y tus números pasan a tu entrenador.' }
                        : { titulo: 'Termina de ajustar tus macros iniciales',
                            desc: 'Unas preguntas más y los tienes finos.' };
                return (
                    <button onClick={() => navigate(porLlamada ? '/dashboard/messages' : '/questionnaire?ajustar=1')}
                        data-testid="ajustar-macros-banner"
                        className="surface surface-hover w-full p-4 flex items-center justify-between group border-2 border-brand/40">
                        <div className="flex items-center gap-4">
                            <div className="w-11 h-11 bg-brand/10 rounded-xl flex items-center justify-center">
                                {porLlamada ? <Phone className="w-5 h-5 text-brand" />
                                            : <SlidersHorizontal className="w-5 h-5 text-brand" />}
                            </div>
                            <div className="text-left">
                                <p className="font-bold text-foreground text-sm uppercase tracking-wide">{texto.titulo}</p>
                                <p className="text-muted-foreground text-sm">{texto.desc}</p>
                            </div>
                        </div>
                        <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors" />
                    </button>
                );
            })()}

            {/* Sin plan contratado no puede hacer casi nada, y hasta ahora no habia forma de
                llegar a contratarlo desde dentro de la app. Va lo primero a proposito. */}
            {sale('plan', !myPlan) && (
                <button onClick={() => navigate('/planes')} data-testid="elegir-plan-banner"
                    className="surface surface-hover w-full p-4 flex items-center justify-between group border border-brand/40">
                    <div className="flex items-center gap-4">
                        <div className="w-11 h-11 bg-brand/10 rounded-xl flex items-center justify-center">
                            <Sparkles className="w-5 h-5 text-brand" />
                        </div>
                        <div className="text-left">
                            <p className="font-bold text-foreground text-sm uppercase tracking-wide">
                                {planUnpaid ? 'Te quedó un pago a medias' : 'Elige cómo quieres hacerlo'}
                            </p>
                            <p className="text-muted-foreground text-sm">
                                {planUnpaid
                                    ? 'Retoma donde lo dejaste y empieza.'
                                    : 'Tres niveles, el mismo método. Cambia cuánta gente hay detrás de tus números.'}
                            </p>
                        </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors" />
                </button>
            )}

            {/* Revisión suelta: solo para quien se autogestiona y ya tiene sus macros ajustados.
                Es la puerta de entrada a tener coach: prueba lo que se siente y, si sube de plan
                en 30 días, lo que pagó se le descuenta.

                Era una tarjeta grande con su flecha. El documento de Jesús del 06-08-2026 dice
                que esto va "como una línea pequeña, sin botón grande", y que nunca interrumpa:
                lo que vende es la pantalla (/dashboard/revision), no el sitio desde el que se
                entra. Los dos momentos de verdad son al recibir los macros de inicio y al
                recibir el ajuste del mes; esto es solo la puerta que queda siempre a mano. */}
            {profile?.ajuste_macros_completado && seLeOfreceLaRevision(profile, can) && (
                <p className="text-xs text-muted-foreground px-1" data-testid="revision-suelta-banner">
                    ¿Prefieres que lo miremos nosotros?{' '}
                    <button onClick={() => navigate('/dashboard/revision')}
                        className="underline text-brand hover:text-brand/80 font-medium">
                        Solicita tu revisión personalizada
                    </button>.
                </p>
            )}

            {/* Ya la pagó: que sepa en qué punto está. */}
            {profile?.revision_suelta?.estado === 'pendiente' && (
                <div className="surface w-full p-4 flex items-center gap-4 border border-brand/30">
                    <div className="w-11 h-11 bg-brand/10 rounded-xl flex items-center justify-center">
                        <ClipboardCheck className="w-5 h-5 text-brand" />
                    </div>
                    <div>
                        <p className="font-bold text-foreground text-sm uppercase tracking-wide">Revisión en marcha</p>
                        <p className="text-muted-foreground text-sm">
                            Un entrenador está revisando tus macros. Te avisamos en cuanto los tenga.
                        </p>
                    </div>
                </div>
            )}

            {/* Cuestionario Nivel 1 pendiente (planes con coach): retomable, no bloqueante.
                UN AVISO CADA VEZ, NO DOS (punto 17). Antes este salía a la vez que el de
                arriba, así que el cliente veía «Completa tu cuestionario inicial» y
                «Completa tu perfil para tu coach» uno debajo del otro y parecía que había
                dos cuestionarios. No los hay: es el mismo recorrido, y el de arriba sigue
                de largo hasta aquí sin cortes. Este solo tiene sentido cuando el de arriba
                ya está hecho -- es decir, cuando de verdad se quedó a medias. */}
            {sale('perfil', can('macros_personalizados') && profile?.questionnaire_completed
                && (profile?.ajuste_macros_completado || profile?.macros_puestos_por_alguien)
                && !profile?.questionnaire_nivel1_completed) && (
                <button onClick={() => navigate('/questionnaire')} data-testid="nivel1-pending-banner"
                    className="surface surface-hover w-full p-4 flex items-center justify-between group border-2 border-brand/40">
                    <div className="flex items-center gap-4">
                        <div className="w-11 h-11 bg-brand/10 rounded-xl flex items-center justify-center">
                            <ClipboardCheck className="w-5 h-5 text-brand" />
                        </div>
                        <div className="text-left">
                            {/* «entrenador», no «coach», y sin el «no cambian tus macros»:
                                las dos son decisiones de Jesús (punto 4.18). */}
                            <p className="font-bold text-foreground text-sm uppercase tracking-wide">Completa tu perfil para tu entrenador</p>
                            <p className="text-muted-foreground text-sm">Te quedan unas preguntas: biotipo, salud, entreno...</p>
                        </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors" />
                </button>
            )}

            {/* Today routine highlight (solo si el plan incluye rutina) */}
            {can('rutina') && (
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
                                : <p className="text-muted-foreground text-sm">{plural(todayRoutine.exercises?.length || 0, 'ejercicio')} programados</p>
                        ) : <p className="text-muted-foreground text-sm">Sin rutina asignada</p>}
                    </div>
                </div>
                <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors" />
            </button>
            )}

            {/* LOS OCHO ACCESOS RÁPIDOS, SOLO EN ESCRITORIO (documento del 10-08, pantalla
                4): «repetían la barra de abajo. Eran cuatro cosas que ocupaban media
                pantalla y no llevaban a ningún sitio nuevo». En el teléfono eran ocho, con
                icono, título y subtítulo, y se llevaban 1.000 de los 1.616 px de la pantalla.

                Ahí no se pierde nada: Nutrición y Seguimiento están en la barra de abajo, y
                las otras seis viven en Perfil, que es donde el documento pone «Mis macros».
                En escritorio se quedan como estaban: esa vista no se ha rediseñado. */}
            <div className="hidden lg:block">
                <p className="caption mb-3">Accesos rápidos</p>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <QuickCard icon={Apple} color="#16A34A" label="Nutrición" sub="Montar dieta" path="/dashboard/nutrition" navigate={navigate} testId="nutrition-quick" />
                    <QuickCard icon={SlidersHorizontal} color={MACRO.protein} label="Macros" sub="Ajustar valores" path="/dashboard/macro-calculator" navigate={navigate} testId="macros-card" />
                    <QuickCard icon={Bot} color="#7C3AED" label="Asistente IA" sub="Dieta con IA" path="/dashboard/chatbot" navigate={navigate} testId="chatbot-card" />
                    {can('reportes') && <QuickCard icon={FileText} color="#CA8A04" label="Reportes" sub="Ver evolución" path="/dashboard/reports" navigate={navigate} testId="reports-card" />}
                    <QuickCard icon={Search} color="#0891B2" label="Alimentos" sub="Buscador" path="/dashboard/foods" navigate={navigate} testId="foods-card" />
                    {can('suplementacion') && <QuickCard icon={Pill} color="#DB2777" label="Suplementos" sub="Tu protocolo" path="/dashboard/supplements" navigate={navigate} testId="supplements-card" />}
                    {can('reportes') && <QuickCard icon={ClipboardCheck} color="#2563EB" label="Check-ins" sub="Seguimiento" path="/dashboard/checkins" navigate={navigate} testId="checkins-card" />}
                    {can('chat') && <QuickCard icon={MessageCircle} color="#9333EA" label="Chat" sub={unreadMessages > 0 ? `${unreadMessages} sin leer` : 'Tu entrenador'} path="/dashboard/messages" navigate={navigate} testId="messages-card" badge={unreadMessages} />}
                </div>
            </div>
        </div>
    );
};

// =============== NAV CONFIG ===============

// `cap`: capacidad del plan requerida para ver el ítem (ver lib/planAccess.js).
// Sin `cap` = siempre visible.
const NAV_ITEMS = [
    { path: '/dashboard', icon: Home, label: 'Inicio', end: true },
    { path: '/dashboard/routine', icon: Dumbbell, label: 'Rutina', cap: 'rutina' },
    { path: '/dashboard/nutrition', icon: Apple, label: 'Nutrición' },
    { path: '/dashboard/foods', icon: Search, label: 'Alimentos' },
    { path: '/dashboard/macro-calculator', icon: SlidersHorizontal, label: 'Ajustar macros' },
    { path: '/dashboard/supplements', icon: Pill, label: 'Suplementos', cap: 'suplementacion' },
    { path: '/dashboard/chatbot', icon: Bot, label: 'Asistente IA' },
    { path: '/dashboard/reports', icon: FileText, label: 'Reportes', cap: 'reportes' },
    { path: '/dashboard/checkins', icon: ClipboardCheck, label: 'Check-ins', cap: 'reportes' },
    // El plan «solo app» no lleva entrenador: enseñarle el Chat es prometerle una persona
    // que no tiene (TABLA 20 del documento del 09-08).
    { path: '/dashboard/messages', icon: MessageCircle, label: 'Chat', cap: 'chat' },
    { path: '/dashboard/profile', icon: User, label: 'Mi perfil' },
];

// LAS CUATRO DE ABAJO (documento del 10-08): Inicio · Nutrición · Seguimiento · Perfil.
//
// Antes eran tres más un botón «Más» que abría un cajón con las once. Dos problemas: el
// cajón escondía media app detrás de una palabra que no dice nada, y «Macros» ocupaba un
// hueco de cuatro para una pantalla a la que se entra una vez al mes.
//
// «Seguimiento» en vez de «Reportes» es del documento, y es la unificación de las cuatro
// vías de hoy (reportes, check-ins, fotos e informe). Mientras esas cuatro no se junten de
// verdad -- pantallas 20 a 24 del recorrido -- apunta a Reportes, que es donde está lo
// principal, y las otras siguen alcanzables desde Perfil.
//
// Todo lo que sale de aquí tiene su entrada en Perfil. Ninguna pantalla se queda sin puerta.
const BOTTOM_ITEMS = [
    { path: '/dashboard', icon: Home, label: 'Inicio', end: true },
    { path: '/dashboard/nutrition', icon: Apple, label: 'Nutrición' },
    { path: '/dashboard/reports', icon: TrendingUp, label: 'Seguimiento', cap: 'reportes' },
    { path: '/dashboard/profile', icon: User, label: 'Perfil' },
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
    const { user, logout, profile, api, can, planUnpaid, myPlan } = useAuth();
    const navItems = NAV_ITEMS.filter(i => !i.cap || can(i.cap));
    const bottomItems = BOTTOM_ITEMS.filter(i => !i.cap || can(i.cap));
    const navigate = useNavigate();
    const location = useLocation();
    const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar-collapsed') === '1');
    const [drawerOpen, setDrawerOpen] = useState(false);
    const [unread, setUnread] = useState(0);

    // Campanita: novedades del coach (rutina, macros, feedback, suplementos, coach)
    const [notifCount, setNotifCount] = useState(0);
    const [notifOpen, setNotifOpen] = useState(false);
    const [notifItems, setNotifItems] = useState([]);

    useEffect(() => {
        api.get('/messages/unread-count').then(r => setUnread(r.data.count || 0)).catch(() => {});
        api.get('/notifications/unread-count').then(r => setNotifCount(r.data.count || 0)).catch(() => {});
    }, [api, location.pathname]);

    const openNotifications = async () => {
        setNotifOpen(true);
        try {
            const res = await api.get('/notifications');
            setNotifItems(res.data.notifications || []);
            if (notifCount > 0) {
                await api.put('/notifications/read-all');
                setNotifCount(0);
            }
        } catch { /* silencioso */ }
    };

    const notifTime = (iso) => {
        const d = new Date(iso);
        const days = Math.floor((new Date() - d) / 86400000);
        if (days === 0) return d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
        if (days === 1) return 'Ayer';
        return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
    };

    // Cuestionario inicial: tras contratar un plan (perfil activo), si no lo ha
    // completado, forzar el quiz para calcular sus macros. Mientras el pago esté
    // pendiente (status != 'activo') no se fuerza.
    useEffect(() => {
        if (profile && profile.status === 'activo' && !profile.questionnaire_completed) {
            navigate('/questionnaire', { replace: true });
        }
    }, [profile, navigate]);

    useEffect(() => { setDrawerOpen(false); }, [location.pathname]);

    const toggleCollapsed = useCallback(() => {
        setCollapsed(c => { localStorage.setItem('sidebar-collapsed', !c ? '1' : '0'); return !c; });
    }, []);

    const handleLogout = () => { logout(); navigate('/auth'); toast.success('Sesión cerrada'); };
    const isStaff = ['admin', 'trainer'].includes(user?.role);

    const UserChip = ({ compact }) => (
        <div className={`flex items-center gap-3 ${compact ? 'justify-center' : ''}`}>
            <div className="w-10 h-10 bg-brand/15 rounded-xl flex items-center justify-center flex-shrink-0">
                <span className="text-brand font-bold font-heading text-lg">{user?.name?.charAt(0)?.toUpperCase()}</span>
            </div>
            {!compact && (
                <div className="flex-1 min-w-0">
                    <p className="font-semibold text-white text-sm truncate">{user?.name}</p>
                    {profile && !planUnpaid && <PlanBadge plan={profile.plan} planName={myPlan?.name} />}
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
                    <button onClick={openNotifications} data-testid="client-bell-desktop"
                        title={collapsed ? 'Novedades' : undefined}
                        className={`relative flex items-center gap-3 rounded-xl w-full transition-all text-white/60 hover:text-white hover:bg-white/[0.07] ${collapsed ? 'justify-center px-0 py-3' : 'px-3.5 py-2.5'}`}>
                        <span className="relative flex-shrink-0">
                            <Bell className="w-5 h-5" strokeWidth={2} />
                            {(notifCount + unread) > 0 && (
                                <span className="absolute -top-1.5 -right-1.5 min-w-4 h-4 px-1 bg-brand text-white text-[10px] rounded-full flex items-center justify-center font-bold border border-ink">{notifCount + unread}</span>
                            )}
                        </span>
                        {!collapsed && <span className="text-sm">Novedades</span>}
                    </button>
                    {navItems.map(item => <SidebarLink key={item.path} item={item} collapsed={collapsed} unread={unread} />)}
                </nav>
                <div className="p-3 border-t border-white/10 space-y-2">
                    <UserChip compact={collapsed} />
                    {collapsed
                        ? <div className="flex justify-center"><ThemeToggle variant="icon" testId="theme-toggle-sidebar" /></div>
                        : <ThemeToggle variant="sidebar" testId="theme-toggle-sidebar" />}
                    {isStaff && (
                        <button onClick={() => navigate('/admin')} data-testid="go-admin-btn"
                            className={`flex items-center gap-2 w-full rounded-lg text-white/50 hover:text-brand hover:bg-brand/10 transition-colors ${collapsed ? 'justify-center py-2.5' : 'px-3 py-2.5'}`}>
                            <LayoutDashboard className="w-4 h-4" /> {!collapsed && <span className="text-sm">Volver al panel</span>}
                        </button>
                    )}
                    <button onClick={handleLogout} data-testid="logout-btn"
                        className={`flex items-center gap-2 w-full rounded-lg text-white/50 hover:text-red-400 hover:bg-red-500/10 transition-colors ${collapsed ? 'justify-center py-2.5' : 'px-3 py-2.5'}`}>
                        <LogOut className="w-4 h-4" /> {!collapsed && <span className="text-sm">Cerrar sesión</span>}
                    </button>
                </div>
            </aside>

            {/* ===== Main ===== */}
            <div className="flex-1 min-w-0 flex flex-col">
                {/* Mobile top bar */}
                {/* EL LOGO, CENTRADO DE VERDAD. Con `justify-between` el logo se coloca entre
                    lo que tiene a los lados, y a la izquierda hay un botón y a la derecha
                    dos: quedaba desplazado a la izquierda. Se centra sobre la barra entera y
                    los dos grupos de botones se quedan en sus esquinas. */}
                <header className="lg:hidden sticky top-0 z-40 bg-ink h-14 flex items-center justify-between px-4 relative">
                    <button onClick={() => setDrawerOpen(true)} data-testid="mobile-menu-btn"
                        className="w-10 h-10 -ml-2 rounded-lg flex items-center justify-center text-white/80 hover:bg-white/10 relative z-10">
                        <Menu className="w-6 h-6" />
                    </button>
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <Logo12EN12 size="sm" tone="dark" />
                    </div>
                    <div className="flex items-center -mr-2 relative z-10">
                        <ThemeToggle variant="icon" testId="theme-toggle-topbar" />
                        <button onClick={openNotifications} data-testid="client-bell"
                            className="relative w-10 h-10 rounded-lg flex items-center justify-center text-white/80 hover:bg-white/10">
                            <Bell className="w-5 h-5" />
                            {(notifCount + unread) > 0 && <span className="absolute top-1.5 right-1.5 w-2.5 h-2.5 bg-brand rounded-full" />}
                        </button>
                    </div>
                </header>

                <main className="flex-1 pb-20 lg:pb-0">
                    {/* Igual que en el panel del coach: un fallo de una pantalla no puede
                        dejar al cliente sin app. Ver LimiteDeError. */}
                    <LimiteDeError clave={location.pathname}>
                        <Outlet />
                    </LimiteDeError>
                </main>
            </div>

            {/* ===== Mobile bottom nav ===== */}
            <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-50 bg-ink border-t border-white/10" data-testid="mobile-bottom-nav">
                <div className="flex items-stretch h-16">
                    {bottomItems.map(item => (
                        <NavLink key={item.path} to={item.path} end={item.end}
                            className={({ isActive }) => `flex flex-col items-center justify-center flex-1 gap-1 transition-colors ${isActive ? 'text-brand' : 'text-white/55'}`}
                            data-testid={`bottomnav-${slug(item.label)}`}>
                            {({ isActive }) => (<>
                                <item.icon className="w-[22px] h-[22px]" strokeWidth={isActive ? 2.5 : 2} />
                                <span className={`text-[10px] ${isActive ? 'font-bold' : 'font-medium'}`}>{item.label}</span>
                            </>)}
                        </NavLink>
                    ))}
                    {/* SIN «MÁS» (documento del 10-08): eran cuatro pestañas y un cajón que
                        escondía media app detrás de una palabra que no dice qué hay dentro.
                        Lo que había en el cajón vive ahora en Perfil, con su nombre.
                        El cajón sigue existiendo para el escritorio, donde es la barra
                        lateral entera y ahí sí tiene sentido. */}
                </div>
            </nav>

            {/* ===== Panel de novedades (campanita) ===== */}
            {notifOpen && (
                <div className="fixed inset-0 z-[80] flex items-start justify-center p-4 pt-16 lg:pt-24" data-testid="notif-panel">
                    <div className="absolute inset-0 bg-black/50 animate-fade-in" onClick={() => setNotifOpen(false)} />
                    <div className="relative bg-card border border-border rounded-2xl shadow-xl w-full max-w-sm max-h-[70vh] flex flex-col animate-slide-up">
                        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                            <p className="font-bold text-foreground uppercase tracking-wider text-sm">Novedades</p>
                            <button onClick={() => setNotifOpen(false)} className="w-8 h-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted">
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto">
                            {unread > 0 && (
                                <button onClick={() => { setNotifOpen(false); navigate('/dashboard/messages'); }}
                                    className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-muted border-b border-border">
                                    <Bell className="w-4 h-4 text-brand flex-shrink-0" />
                                    <span className="text-sm text-foreground flex-1">Tienes {unread} mensaje{unread > 1 ? 's' : ''} sin leer de tu entrenador</span>
                                </button>
                            )}
                            {notifItems.map(n => (
                                <button key={n.id} onClick={() => { setNotifOpen(false); if (n.link) navigate(n.link); }}
                                    className="w-full px-4 py-3 text-left hover:bg-muted border-b border-border last:border-0">
                                    <div className="flex items-start gap-2">
                                        {!n.read && <span className="w-2 h-2 rounded-full bg-brand mt-1.5 flex-shrink-0" />}
                                        <div className="flex-1 min-w-0">
                                            <p className={`text-sm ${n.read ? 'text-muted-foreground' : 'text-foreground font-medium'}`}>{n.title}</p>
                                            {/* Entrecomillado solo si lo ha escrito una persona. Los avisos que
                                                genera la app traen `clave`; ponerles comillas hace que parezca
                                                que se lo ha dicho alguien. */}
                                            {n.body && (
                                                <p className="text-xs text-foreground/80 mt-1 whitespace-pre-wrap">
                                                    {n.clave ? n.body : `"${n.body}"`}
                                                </p>
                                            )}
                                            <p className="text-[11px] text-muted-foreground mt-0.5">{notifTime(n.created_at)}</p>
                                        </div>
                                    </div>
                                </button>
                            ))}
                            {notifItems.length === 0 && unread === 0 && (
                                <p className="text-muted-foreground text-sm text-center py-10">No tienes novedades</p>
                            )}
                        </div>
                    </div>
                </div>
            )}

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
                            {navItems.map(item => <SidebarLink key={item.path} item={item} collapsed={false} unread={unread} onClick={() => setDrawerOpen(false)} />)}
                        </nav>
                        <div className="p-3 border-t border-white/10 space-y-2">
                            <UserChip />
                            <ThemeToggle variant="sidebar" testId="theme-toggle-drawer" />
                            {isStaff && (
                                <button onClick={() => navigate('/admin')}
                                    className="flex items-center gap-2 w-full px-3 py-2.5 rounded-lg text-white/50 hover:text-brand hover:bg-brand/10 transition-colors">
                                    <LayoutDashboard className="w-4 h-4" /> <span className="text-sm">Volver al panel</span>
                                </button>
                            )}
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
