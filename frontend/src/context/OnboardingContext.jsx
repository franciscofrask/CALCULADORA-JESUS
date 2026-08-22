import React, { createContext, useContext, useRef, useState, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { guardarAjusteEnFicha, AJUSTE_RECORRIDO } from '../lib/ajustesEnFicha';
import RecorridoPrimeraVez, { PASOS_RECORRIDO } from '../components/RecorridoPrimeraVez';

// ============================================================================
// EL RECORRIDO DE LA PRIMERA VEZ (doc de Jesús del 21-08, apartado 23).
//
// Sustituye al tour de driver.js que vivía aquí (apagado con RECORRIDO_ACTIVO
// desde el 11-08: por eso a Juan no le salía nada). Aquel recorría pantallas;
// este explica las TRES REGLAS del método en cinco tarjetas propias, sin anclar
// nada al DOM (ver components/RecorridoPrimeraVez.jsx).
//
// Las reglas de comportamiento, decididas en el doc:
// - Sale LA PRIMERA VEZ que el cliente entra al Inicio, después de los tres
//   pasos del alta (registro, plan, cuestionario) y antes de que monte nada.
// - Se puede saltar desde el primer paso. Si lo salta, NO se le vuelve a
//   ofrecer solo: que se lo busque él en Mi perfil («Ver el recorrido»).
// - El estado (visto/saltado) se persiste EN LA FICHA (ajustes_app.recorrido),
//   no solo en el navegador: cambiar de móvil no lo resucita. Y el disparo lee
//   SOLO la ficha, nunca localStorage: en un ordenador compartido el «saltado»
//   de uno no puede tapárselo al siguiente.
// ============================================================================

const OnboardingContext = createContext(null);

export const useOnboarding = () => useContext(OnboardingContext) || {
    // Fallback no-op (por si algún componente se usa fuera del provider)
    startTour: () => {}, resumeTour: () => {}, skipTour: () => {}, notify: () => {}, active: false, available: false, completed: true,
};

export const OnboardingProvider = ({ children }) => {
    const location = useLocation();
    const { profile, isClient, planUnpaid, refreshProfile, pantalla } = useAuth();
    // El recorrido explica el Inicio nuevo (el deslizador es su paso 2): va detrás del
    // MISMO interruptor t1_inicio_nuevo, para que el lunes se encienda todo junto y a
    // nadie le cuenten una pantalla que todavía no tiene.
    const inicioNuevoEncendido = !!pantalla?.('t1_inicio_nuevo');

    // -1 = cerrado; 0..4 = el paso que se está viendo.
    const [paso, setPaso] = useState(-1);
    const activo = paso >= 0;

    // Cierra el hueco entre «guardado en la ficha» y «perfil refrescado»: sin esto,
    // el efecto de auto-arranque volvería a abrir el recorrido en ese instante.
    const decididoRef = useRef(false);

    const cerrar = useCallback((estado) => {
        setPaso(-1);
        decididoRef.current = true;
        // 'visto' o 'saltado', a la ficha: el mismo patrón que Método/Reales y la vista
        // (lib/ajustesEnFicha.js). Si la red falla, decididoRef aguanta esta sesión.
        guardarAjusteEnFicha(AJUSTE_RECORRIDO, estado);
        if (refreshProfile) refreshProfile();
    }, [refreshProfile]);

    const siguiente = useCallback(() => {
        if (paso >= PASOS_RECORRIDO.length - 1) { cerrar('visto'); return; } // «Empezar»
        setPaso(paso + 1);
    }, [paso, cerrar]);

    const saltar = useCallback(() => cerrar('saltado'), [cerrar]);

    // Repetir a mano (Mi perfil): arranca siempre desde el primer paso.
    const startTour = useCallback(() => {
        decididoRef.current = true; // un arranque a mano nunca deja armado el automático
        setPaso(0);
    }, []);

    // Auto-arranque: la primera vez, sobre el Inicio, con el alta terminada.
    useEffect(() => {
        if (!inicioNuevoEncendido) return;               // con t1 apagado, ni solo ni desde el perfil
        if (activo || decididoRef.current) return;
        if (!isClient || !profile || planUnpaid) return;
        if (!profile.questionnaire_completed) return;        // el alta primero
        if (profile.acceso?.motivo === 'caducado') return;   // al caducado no se le enseña a montar nada
        if (profile.ajustes_app?.recorrido) return;          // visto o saltado: nunca se ofrece solo
        if (location.pathname !== '/dashboard') return;      // sobre el Inicio, no en mitad de otra pantalla
        setPaso(0);
    }, [activo, isClient, profile, planUnpaid, location.pathname]);

    const value = {
        startTour,
        // Compatibilidad con los consumidores del tour viejo (checklist del Inicio,
        // WelcomePage): resume = empezar de cero, notify ya no hace nada (no hay
        // pasos con «gate»), y completed en true deja el «Continuar recorrido» del
        // checklist apagado para siempre, que ya no existe tal cosa.
        resumeTour: startTour,
        skipTour: () => {},
        notify: () => {},
        active: activo,
        // Lo que mira Mi perfil para ofrecer «Ver el recorrido».
        available: !!(inicioNuevoEncendido && isClient && profile && profile.questionnaire_completed),
        completed: true,
    };

    return (
        <OnboardingContext.Provider value={value}>
            {children}
            {activo && (
                <RecorridoPrimeraVez
                    paso={paso}
                    onSaltar={saltar}
                    onSiguiente={siguiente}
                />
            )}
        </OnboardingContext.Provider>
    );
};
