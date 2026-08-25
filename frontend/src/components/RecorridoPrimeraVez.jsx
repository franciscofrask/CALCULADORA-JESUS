import React from 'react';
import { Check, Plus } from 'lucide-react';

// ============================================================================
// EL RECORRIDO DE LA PRIMERA VEZ (doc de Jesús del 21-08, apartado 23).
//
// Cinco tarjetas que no explican pantallas: explican las TRES REGLAS del método
// que, si no se entienden, hacen que la app parezca rara (el día es lo que
// cuadra, el perientreno tiene su bloque, los extras se apuntan y no cuentan).
//
// A PROPÓSITO SIN ANCLAR AL DOM: el tour anterior (driver.js) señalaba elementos
// concretos y se rompía según qué interruptor estuviera encendido (el paso 2
// habla del deslizador del Inicio nuevo, que con `t1_inicio_nuevo` apagado no
// existe). Cada tarjeta trae su propio esquema dibujado, así el recorrido vale
// con cualquier Inicio y nunca señala algo que no está. El doc no exige flechas:
// «tarjeta inferior: título, párrafo, Saltar / Siguiente y el X de 5».
// ============================================================================

// Los colores de macro de toda la app (WelcomePage, Inicio): P naranja, H azul, G ámbar.
const MACRO = { P: '#FF671F', H: '#2196F3', G: '#FFA500' };

// --- Los esquemas de cada paso (dibujo simple, sin depender de ninguna pantalla) ---

const Fila = ({ children, className = '' }) => (
    <div className={`flex items-center justify-between rounded-xl bg-background border border-border px-3 py-2 ${className}`}>
        {children}
    </div>
);

// Paso 1: el día son comidas que se montan.
const EsquemaMontar = () => (
    <div className="w-full space-y-2">
        {[['Desayuno', 3], ['Comida', 4], ['Cena', 2]].map(([nombre, n]) => (
            <Fila key={nombre}>
                <span className="text-xs font-bold uppercase tracking-wide text-foreground">{nombre}</span>
                <span className="flex gap-1.5">
                    {Array.from({ length: n }).map((_, i) => (
                        <span key={i} className="w-2 h-2 rounded-full bg-brand/70" />
                    ))}
                    <span className="w-2 h-2 rounded-full border border-brand/50" />
                </span>
            </Fila>
        ))}
    </div>
);

// Paso 2: las cuatro vistas del deslizador, tal cual se leen.
const EsquemaDeslizador = () => (
    <div className="w-full">
        <div className="flex rounded-full bg-background border border-border p-1 text-[11px] font-bold uppercase tracking-wide">
            {['Macros', 'Dieta', 'Llevas', 'Falta'].map((t, i) => (
                <span key={t} className={`flex-1 text-center py-1.5 rounded-full ${i === 0 ? 'bg-brand text-white' : 'text-muted-foreground'}`}>
                    {t}
                </span>
            ))}
        </div>
        <div className="flex justify-center gap-8 mt-4">
            {[['180', 'P', MACRO.P], ['220', 'H', MACRO.H], ['70', 'G', MACRO.G]].map(([v, l, c]) => (
                <span key={l} className="flex flex-col items-center">
                    <span className="font-data font-extrabold text-2xl leading-none" style={{ color: c }}>{v}</span>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mt-1">{l}</span>
                </span>
            ))}
        </div>
    </div>
);

// Paso 3: una comida pasada, otra corta, y el día cuadrado igual.
const BarraComida = ({ nombre, pct }) => (
    <div className="flex items-center gap-3">
        <span className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground w-16 shrink-0">{nombre}</span>
        <span className="flex-1 h-2 rounded-full bg-background border border-border overflow-hidden">
            <span className="block h-full rounded-full bg-muted-foreground/50" style={{ width: `${Math.min(pct, 100)}%` }} />
        </span>
    </div>
);

const EsquemaDiaCuadrado = () => (
    <div className="w-full space-y-2.5">
        <BarraComida nombre="Comida 1" pct={100} />
        <BarraComida nombre="Comida 2" pct={55} />
        <BarraComida nombre="Comida 3" pct={85} />
        <div className="flex items-center gap-3 pt-1 border-t border-border">
            <span className="text-[11px] font-bold uppercase tracking-wide text-brand w-16 shrink-0">El día</span>
            <span className="flex-1 h-2.5 rounded-full bg-background border border-brand/40 overflow-hidden">
                <span className="block h-full rounded-full bg-brand" style={{ width: '100%' }} />
            </span>
            <Check className="w-4 h-4 text-brand shrink-0" />
        </div>
    </div>
);

// Paso 4: el bloque del perientreno, al final y ya contado arriba.
const EsquemaPerientreno = () => (
    <div className="w-full space-y-2">
        {['Comida 1', 'Comida 2', 'Comida 3'].map((n) => (
            <Fila key={n} className="py-1.5">
                <span className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">{n}</span>
            </Fila>
        ))}
        <div className="flex items-center justify-between rounded-xl border border-brand/60 bg-brand/10 px-3 py-2">
            <span className="text-xs font-bold uppercase tracking-wide text-brand">Perientreno</span>
            <span className="text-[10px] font-semibold text-brand/80 uppercase tracking-wide">Ya en el total del día</span>
        </div>
    </div>
);

// Paso 5: los extras se apuntan y no tocan los macros.
//
// AQUÍ DECÍA «Cuenta igual que lo demás», Y ERA MENTIRA DESDE EL 24-08. Este dibujo y su
// texto se escribieron el 21-08, cuando los extras SÍ sumaban en «Llevas». El punto 28 del
// doc del 24-08 lo cambió -- van en su lista, aparte, y los macros de la dieta no se mueven
// -- y esta tarjeta se quedó atrás. Es lo PRIMERO que lee del método quien entra por
// primera vez, así que si vuelve a cambiar la regla de los extras, se cambia también aquí.
const EsquemaExtras = () => (
    <div className="w-full flex flex-col items-center gap-3 py-2">
        <span className="inline-flex items-center gap-2 rounded-xl border border-dashed border-brand/60 px-4 py-3 text-brand text-sm font-bold uppercase tracking-wide">
            <Plus className="w-4 h-4" /> Extras del día
        </span>
        <span className="text-[11px] text-muted-foreground">No toca tus macros</span>
    </div>
);

// --- Los cinco pasos, con los textos LITERALES del doc del 21-08 ---

export const PASOS_RECORRIDO = [
    {
        id: 'montar',
        titulo: 'Aquí montas lo que vas a comer',
        texto: 'Cada día tienes unos macros. La app te ayuda a repartirlos en tus comidas y a llevar la cuenta de lo que llevas.',
        Esquema: EsquemaMontar,
    },
    {
        id: 'deslizador',
        titulo: 'Macros, Dieta, Llevas, Falta',
        texto: 'Macros es lo que te toca hoy. Dieta, lo que has dejado montado. Llevas, lo que ya has marcado como comido. Y Falta, lo que te queda.',
        Esquema: EsquemaDeslizador,
    },
    {
        id: 'dia',
        titulo: 'Lo que tiene que cuadrar es el día, no cada comida',
        texto: 'Si en una comida te pasas, lo compensas en las otras. El reparto por comidas es una comodidad; el objetivo es el total del día.',
        Esquema: EsquemaDiaCuadrado,
    },
    {
        id: 'peri',
        // «Va aparte» era mentira a medias desde el Inicio nuevo (P32 del 23-08): sus
        // macros van DENTRO del total del día; lo que tiene propio es el bloque.
        titulo: 'El perientreno tiene su propio bloque',
        texto: 'Lo que tomas durante y después de entrenar tiene su propio bloque, al final. Sus macros ya están contados en el total del día que ves arriba.',
        Esquema: EsquemaPerientreno,
    },
    {
        id: 'extras',
        // «Cuenta igual» era la regla del 21-08 y dejó de serlo el 24-08 (punto 28: los
        // extras no tocan ni «Llevas» ni «Falta»). Prometer aquí que suman era enseñarle a
        // compensar antes de que hubiera empezado: si se comió una tarta, la app no le va
        // a decir que se salte la comida 4. La última frase es de Jesús, literal.
        titulo: '¿Te has comido algo que no estaba?',
        texto: 'Apúntalo en Extras del día. No cuenta contra tus macros ni te cambia la dieta: se te fue algo, lo apuntas, y te sigues comiendo tus comidas.',
        Esquema: EsquemaExtras,
    },
];

// La tarjeta: abajo en el teléfono (como el mockup del doc), centrada en escritorio.
const RecorridoPrimeraVez = ({ paso, onSaltar, onSiguiente }) => {
    const total = PASOS_RECORRIDO.length;
    const p = PASOS_RECORRIDO[paso];
    if (!p) return null;
    const esUltimo = paso === total - 1;
    const { Esquema } = p;

    return (
        <div
            className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center sm:p-6"
            data-testid="recorrido-overlay"
            role="dialog"
            aria-modal="true"
            aria-label="Recorrido de la primera vez"
        >
            <div className="w-full sm:max-w-md max-h-[92dvh] overflow-y-auto bg-card border-t sm:border border-border rounded-t-3xl sm:rounded-3xl p-6 pb-7 animate-fade-in">
                <div className="rounded-2xl bg-muted/40 border border-border p-4 mb-5 min-h-[9rem] flex items-center" data-testid={`recorrido-esquema-${p.id}`}>
                    <Esquema />
                </div>

                {/* Los puntos de progreso: se ve cuánto queda sin leer el contador */}
                <div className="flex gap-1.5 mb-3">
                    {PASOS_RECORRIDO.map((s, i) => (
                        <span key={s.id} className={`h-1 rounded-full transition-all ${i === paso ? 'w-6 bg-brand' : 'w-2.5 bg-muted'}`} />
                    ))}
                </div>

                <h2 className="font-heading font-bold text-2xl uppercase tracking-tight text-foreground leading-none mb-2" data-testid="recorrido-titulo">
                    {p.titulo}
                </h2>
                <p className="text-muted-foreground text-sm leading-relaxed mb-6">{p.texto}</p>

                <div className="flex items-center justify-between gap-3">
                    <button
                        onClick={onSaltar}
                        data-testid="recorrido-saltar"
                        className="text-muted-foreground hover:text-foreground font-semibold text-sm px-2 py-2 transition-colors"
                    >
                        Saltar
                    </button>
                    <span className="text-xs font-data font-bold text-muted-foreground uppercase tracking-wider" data-testid="recorrido-contador">
                        {paso + 1} de {total}
                    </span>
                    <button
                        onClick={onSiguiente}
                        data-testid="recorrido-siguiente"
                        className="btn-brand px-6 py-2.5 text-sm font-bold"
                    >
                        {esUltimo ? 'Empezar' : 'Siguiente'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default RecorridoPrimeraVez;
