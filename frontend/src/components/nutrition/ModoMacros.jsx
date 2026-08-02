/**
 * ModoMacros - Ver los macros del método o los de la etiqueta.
 *
 * El método no cuenta todo lo que lleva un alimento: la proteína de un pan no cuenta si
 * es menos de un tercio de sus hidratos, de los frutos secos solo cuenta la grasa, y así.
 * Eso descoloca a quien mira la etiqueta y ve otra cosa: 100 g de almendras son 21 g de
 * proteína en el paquete y 0 para el método.
 *
 * Este switch enseña las dos cifras. Es SOLO informativo: no cambia las cantidades, ni el
 * reparto del día, ni si una comida está cuadrada, ni lo que se guarda. El semáforo de
 * cada comida y el del día siguen siendo los del método, porque son los que dicen si la
 * dieta va bien.
 */
import React from 'react';

export const MODOS = [
    { id: 'metodo', nombre: 'Método', titulo: 'Lo que cuenta el método' },
    { id: 'reales', nombre: 'Reales', titulo: 'Lo que dice la etiqueta del alimento' },
];

const CLAVE = 'nutricion-modo-macros';

export const leerModoMacros = () => {
    try {
        const v = localStorage.getItem(CLAVE);
        return MODOS.some(m => m.id === v) ? v : 'metodo';
    } catch (e) {
        return 'metodo';
    }
};

export const guardarModoMacros = (v) => {
    try { localStorage.setItem(CLAVE, v); } catch (e) {}
};

/** Los macros a ENSEÑAR de un alimento. Nunca para contar: para eso, macros_efectivos. */
export const macrosDeVista = (food, modo) => {
    if (modo !== 'reales') return food?.macros_efectivos || {};
    // macros_brutos es como se llamaba antes; los días viejos solo traen macros_reales,
    // que los rellena el backend al servir el día.
    return food?.macros_reales || food?.macros_brutos || food?.macros_efectivos || {};
};

/** Suma de una lista de alimentos en el modo pedido. Solo para enseñar. */
export const sumaDeVista = (alimentos, modo) =>
    (alimentos || []).reduce((t, f) => {
        const m = macrosDeVista(f, modo);
        return { P: t.P + (m.P || 0), H: t.H + (m.H || 0), G: t.G + (m.G || 0) };
    }, { P: 0, H: 0, G: 0 });

export const ModoMacrosSelector = ({ modo, onCambiar }) => (
    <div className="inline-flex items-center gap-1.5">
        <span className="hidden sm:inline text-[10px] uppercase tracking-wider text-muted-foreground">Macros</span>
        <div className="inline-flex rounded-lg bg-muted p-0.5 border border-border" role="group" aria-label="Qué macros ver">
            {MODOS.map(({ id, nombre, titulo }) => (
                <button
                    key={id}
                    type="button"
                    onClick={() => onCambiar(id)}
                    aria-pressed={modo === id}
                    title={titulo}
                    data-testid={`modo-macros-${id}`}
                    className={`h-7 px-2.5 rounded-md text-[11px] font-bold transition-colors ${
                        modo === id ? 'bg-card text-brand shadow-sm' : 'text-muted-foreground hover:text-foreground'
                    }`}
                >
                    {nombre}
                </button>
            ))}
        </div>
    </div>
);

/** Aviso de que lo que se ve no es lo que cuenta. Solo aparece en modo "reales". */
export const AvisoMacrosReales = () => (
    <p className="text-[11px] text-amber-600 dark:text-amber-400">
        Estás viendo lo que dice la etiqueta. El método no cuenta todo esto, así que las
        cantidades y los objetivos siguen calculándose con los macros del método.
    </p>
);

export default ModoMacrosSelector;
