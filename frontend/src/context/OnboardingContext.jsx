import React, { createContext, useContext, useRef, useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { driver } from 'driver.js';
import 'driver.js/dist/driver.css';
import { useAuth } from './AuthContext';

// ============================================================================
// Onboarding guiado (product tour): recorrido por toda la app con spotlight,
// tooltips anclados y "bloqueo suave": ciertos pasos avanzan solos cuando el
// usuario hace la acción clave, pero nunca lo encierran (puede pausar y retomar).
// El progreso se guarda por usuario en el backend (onboarding_step / completed).
// ============================================================================

// Cada paso: id, ruta donde vive, selector del elemento a resaltar, textos, y
// opcionalmente `gate` = id de acción que, al ocurrir, auto-avanza el tour, y
// `cap` = capacidad del plan requerida (los pasos de secciones que el plan no
// incluye se omiten del recorrido; ver lib/planAccess.js).
const STEPS = [
    {
        id: 'dash-macros', route: '/dashboard',
        element: '[data-testid="macro-trackers-card"], [data-testid="setup-macros-card"]',
        title: 'Tu resumen del día', side: 'right', align: 'center',
        description: 'Aquí ves tus macros objetivo y cuánto llevas consumido hoy. Es tu vista rápida cada vez que entras.',
    },
    {
        id: 'dash-nav', route: '/dashboard',
        element: '[data-testid="desktop-sidebar"], [data-testid="mobile-bottom-nav"]',
        title: 'Tu menú', side: 'right', align: 'center',
        description: 'Desde aquí llegas a todas las secciones: nutrición, rutina, reportes, asistente IA y más. Te las muestro una por una.',
    },
    {
        id: 'nut-controls', route: '/dashboard/nutrition',
        element: '[data-testid="nutrition-controls"]',
        title: 'Configura tu día', side: 'bottom',
        description: 'Elige si es día de entrenamiento o de descanso. Tus macros se ajustan automáticamente a cada tipo de día.',
    },
    {
        id: 'nut-meals', route: '/dashboard/nutrition',
        element: '[data-testid="meal-selector"], [data-testid="meals-accordion"]',
        title: 'Prepara tus comidas', side: 'right', gate: 'nutrition-add-food',
        description: 'Aquí están tus comidas del día. Toca una y añade un alimento. Si lo haces ahora, te llevo solo al siguiente paso (o sigue con "Siguiente").',
    },
    {
        id: 'nut-prefs', route: '/dashboard/nutrition',
        element: '[data-testid="open-preferences-btn"]',
        title: 'Tus preferencias', side: 'bottom',
        description: 'La calculadora sugiere comida según lo que te gusta. Puedes ajustar tus preferencias desde aquí cuando quieras.',
    },
    {
        id: 'macros', route: '/dashboard/macro-calculator',
        element: '[data-testid="macros-content"]',
        title: 'Ajustar macros', side: 'right', align: 'start',
        description: 'Si tu entrenador lo indica, desde aquí puedes afinar tus macros manualmente. Por defecto los calculamos por ti.',
    },
    {
        id: 'reports', route: '/dashboard/reports', cap: 'reportes',
        element: '[data-testid="weight-input"]',
        title: 'Tus reportes', side: 'bottom', align: 'start',
        description: 'En Reportes registras tu peso y medidas cada semana. Ves tu evolución en gráficos y tu entrenador te da feedback.',
    },
    {
        id: 'ai', route: '/dashboard/chatbot',
        element: '[data-testid="chat-input"]',
        title: 'Asistente IA', side: 'top', align: 'start',
        description: 'El Asistente IA prepara tu dieta conversando: te propone comidas según tus macros y preferencias.',
    },
    {
        id: 'chat', route: '/dashboard/messages',
        element: '[data-testid="messages-content"]',
        title: 'Chat con tu entrenador', side: 'bottom', align: 'start',
        description: 'En Chat hablas directo con tu entrenador. Te responde y te acompaña durante todo el plan.',
    },
    {
        id: 'routine', route: '/dashboard/routine', cap: 'rutina',
        element: '[data-testid="day-selector"], [data-testid="routine-content"]',
        title: 'Tu rutina', side: 'bottom', align: 'start',
        description: 'En Rutina tienes tu plan de entrenamiento semana a semana, día por día, con los ejercicios programados.',
    },
    {
        id: 'checkins', route: '/dashboard/checkins', cap: 'reportes',
        element: '[data-testid="checkins-content"]',
        title: 'Check-ins', side: 'bottom', align: 'start',
        description: 'En Check-ins registras cómo te sientes: energía, sueño, estrés y fotos de progreso. Ayuda a ajustar tu plan.',
    },
    {
        id: 'profile', route: '/dashboard/profile',
        element: '[data-testid="body-data-card"]',
        title: 'Tu perfil', side: 'bottom', align: 'start',
        description: 'En Mi perfil mantén tu peso y % de grasa al día para que tus macros se calculen con precisión. Ahí también editas tus datos.',
    },
    {
        id: 'done', route: '/dashboard', side: 'bottom',
        element: '[data-testid="onboarding-checklist"], [data-testid="macro-trackers-card"], [data-testid="setup-macros-card"], [data-testid="client-dashboard"]',
        title: '¡Listo! 🎉',
        description: 'Ya conoces tu app. Tu siguiente paso es preparar tu primer día de comidas. Puedes repetir este recorrido cuando quieras desde tu perfil.',
    },
];

const OnboardingContext = createContext(null);

export const useOnboarding = () => useContext(OnboardingContext) || {
    // Fallback no-op (por si algún componente se usa fuera del provider)
    startTour: () => {}, resumeTour: () => {}, skipTour: () => {}, notify: () => {}, active: false, available: false,
};

// Devuelve el primer elemento VISIBLE que matchea el selector. Clave para que el
// tour funcione en mobile y desktop con los mismos pasos: muchos anclajes listan el
// elemento de escritorio y su equivalente mobile (ej. barra lateral / barra inferior,
// selector de comidas / acordeón), y solo uno está visible según el ancho. querySelector
// devolvería el primero aunque esté display:none, así que filtramos por visibilidad
// (getClientRects vacío = no renderizado).
const firstVisible = (selector) => {
    const els = document.querySelectorAll(selector);
    for (const el of els) {
        if (el.getClientRects().length > 0) return el;
    }
    return els[0] || null;
};

const waitForEl = (selector, timeout = 3500) => new Promise((resolve) => {
    if (!selector) return resolve(null);
    const start = Date.now();
    const tick = () => {
        const el = firstVisible(selector);
        if (el && el.getClientRects().length > 0) return resolve(el);
        if (Date.now() - start > timeout) return resolve(el || null);
        setTimeout(tick, 120);
    };
    tick();
});

export const OnboardingProvider = ({ children }) => {
    const navigate = useNavigate();
    const location = useLocation();
    const { api, profile, isClient, refreshProfile, can } = useAuth();

    // Pasos visibles según el plan: se omiten las secciones que el plan no incluye
    // (si no, el tour navegaría a una ruta bloqueada y entraría en bucle de redirección).
    const steps = useMemo(() => STEPS.filter((s) => !s.cap || can(s.cap)), [can]);

    const [active, setActive] = useState(false);
    const [index, setIndex] = useState(-1);
    const indexRef = useRef(-1);
    const driverRef = useRef(null);
    const handlersRef = useRef({});
    // Marca en memoria: bloquea el auto-arranque tras cerrar/terminar el tour
    // SOLO en esta carga de página. Al recargar (F5) se limpia, así un reset en
    // la base vuelve a mostrar el recorrido sin tener que abrir pestaña nueva.
    const dismissedRef = useRef(false);

    const setIdx = useCallback((i) => { indexRef.current = i; setIndex(i); }, []);

    const persistStep = useCallback((stepId) => {
        api.patch('/clients/onboarding', { step: stepId }).catch(() => {});
    }, [api]);

    const finish = useCallback((completed) => {
        setActive(false);
        setIdx(-1);
        try { driverRef.current?.destroy(); } catch { /* noop */ }
        driverRef.current = null; // forzar recreación en el próximo arranque
        // Bloqueo en memoria: evita que el auto-arranque se redispare en el instante
        // en que `active` pasa a false (refreshProfile es async). Se limpia al recargar
        // o cuando un botón llama a startTour.
        dismissedRef.current = true;
        if (completed) {
            api.patch('/clients/onboarding', { completed: true }).then(refreshProfile).catch(() => {});
        }
    }, [api, refreshProfile, setIdx]);

    const goNext = useCallback(() => {
        const i = indexRef.current;
        if (i >= steps.length - 1) { finish(true); return; }
        setIdx(i + 1);
    }, [finish, setIdx, steps]);

    const goPrev = useCallback(() => {
        const i = indexRef.current;
        if (i <= 0) return;
        setIdx(i - 1);
    }, [setIdx]);

    // Mantener handlers frescos para los hooks de driver.js
    handlersRef.current = { next: goNext, prev: goPrev, close: () => finish(false) };

    const ensureDriver = useCallback(() => {
        if (driverRef.current) return driverRef.current;
        driverRef.current = driver({
            showProgress: true,
            progressText: '{{current}} de {{total}}',
            allowClose: true,
            overlayColor: 'rgba(0,0,0,0.82)',
            overlayOpacity: 0.82,
            stagePadding: 10,
            stageRadius: 16,
            popoverClass: 'jg-tour',
            nextBtnText: 'Siguiente',
            prevBtnText: 'Atrás',
            doneBtnText: 'Finalizar',
            onNextClick: () => handlersRef.current.next?.(),
            onPrevClick: () => handlersRef.current.prev?.(),
            onCloseClick: () => handlersRef.current.close?.(),
        });
        return driverRef.current;
    }, [steps]);

    const renderPopover = useCallback((step, el, i) => {
        const d = ensureDriver();
        const isLast = i === steps.length - 1;
        const isFirst = i === 0;
        const buttons = [];
        if (!isFirst) buttons.push('previous');
        buttons.push('next');
        buttons.push('close');
        const popover = {
            title: step.title,
            description: step.description,
            side: step.side || 'bottom',
            align: step.align || 'start',
            showButtons: buttons,
            nextBtnText: isLast ? 'Finalizar' : 'Siguiente',
            prevBtnText: 'Atrás',
        };
        try {
            if (el) d.highlight({ element: el, popover });
            else d.highlight({ popover: { ...popover, side: 'over', align: 'center' } });
        } catch {
            // Si el modal centrado falla, ancla al dashboard como último recurso.
            const fallback = document.querySelector('[data-testid="client-dashboard"]');
            if (fallback) d.highlight({ element: fallback, popover });
        }
    }, [ensureDriver]);

    // Bucle principal: cuando el tour está activo, asegura la ruta del paso y
    // luego resalta el elemento (esperando a que aparezca tras navegar).
    useEffect(() => {
        if (!active || index < 0) return;
        const step = steps[index];
        if (!step) return;
        if (step.route && location.pathname !== step.route) {
            navigate(step.route);
            return; // el efecto se reejecuta cuando cambia pathname
        }
        let cancelled = false;
        waitForEl(step.element).then((el) => {
            if (cancelled || !active) return;
            if (step.element && !el) { goNext(); return; } // elemento ausente → saltar
            renderPopover(step, el, index);
            persistStep(step.id);
        });
        return () => { cancelled = true; };
    }, [active, index, location.pathname, navigate, goNext, renderPopover, persistStep, steps]);

    const startTour = useCallback((fromStepId) => {
        let i = 0;
        if (fromStepId) {
            const found = steps.findIndex((s) => s.id === fromStepId);
            if (found >= 0 && found < steps.length - 1) i = found;
        }
        dismissedRef.current = false;
        setIdx(i);
        setActive(true);
    }, [setIdx, steps]);

    // "Explorar por mi cuenta": no arranca el tour en esta carga de página.
    const skipTour = useCallback(() => { dismissedRef.current = true; }, []);

    const resumeTour = useCallback(() => {
        startTour(profile?.onboarding_step);
    }, [startTour, profile]);

    const notify = useCallback((actionId) => {
        if (!active) return;
        const step = steps[indexRef.current];
        if (step?.gate === actionId) goNext();
    }, [active, goNext, steps]);

    // Auto-arranque SOLO la primera vez: cliente que ya hizo el cuestionario,
    // nunca empezó el tour (sin onboarding_step) y no lo completó. Una vez que
    // arranca queda registrado, así no reaparece en cada login; luego se retoma
    // desde el checklist ("Continuar recorrido") o el perfil ("Repetir").
    useEffect(() => {
        if (!isClient || !profile) return;
        if (active) return;
        if (profile.onboarding_completed) return;
        if (profile.onboarding_step) return;          // ya arrancó alguna vez
        if (!profile.questionnaire_completed) return; // primero el cuestionario
        if (dismissedRef.current) return;             // cerrado en esta carga de página
        if (!location.pathname.startsWith('/dashboard')) return;
        startTour();
    }, [isClient, profile, active, location.pathname, startTour]);

    const value = {
        startTour,
        resumeTour,
        skipTour,
        notify,
        active,
        available: !!(isClient && profile && profile.questionnaire_completed),
        completed: !!profile?.onboarding_completed,
    };

    return (
        <OnboardingContext.Provider value={value}>
            {children}
        </OnboardingContext.Provider>
    );
};
