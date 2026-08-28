/**
 * DiaVacio - la pantalla del día sin montar (doc de Jesús del 21-08, tarea 6.1).
 *
 * Cuando el día no tiene NINGUNA comida con alimentos, en lugar de la parrilla sale una
 * sola pregunta con tres salidas, para que el cliente sepa por dónde empezar:
 *
 *   - «Crear el día»: abre la parrilla de siempre y arranca de cero.
 *   - «Una de mis dietas»: el selector de favoritas que ya existe, con su número real.
 *   - «Repetir un día»: la lista de sus días recientes montados; cada uno dice su tipo,
 *     sus macros y si «Encaja» (mismo tipo de día que hoy) o «Se adapta» (tipo distinto:
 *     se recuadra sola a los macros de hoy al aplicarlo).
 *
 * Los macros del día siguen arriba, en la cabecera de siempre (DayHeader): esta tarjeta
 * solo sustituye a la parrilla. OJO: un día migrado con alguna comida NO pasa por aquí;
 * el estado vacío es únicamente «ninguna comida con alimentos».
 *
 * El botón dice CREAR a propósito (arrancar de cero); en cuanto el día existe, el
 * vocabulario: se dice CREAR en toda la app (punto 7 del doc del 23-08; la regla
 * vieja de «montar» quedó al revés ese día).
 */
import React, { useState } from 'react';
import { Plus, Star, History, ChevronRight, ChevronUp } from 'lucide-react';

const esDescanso = (t) => t === 'descanso';

// LOS MACROS DEL DÍA LOS CUENTA EL SERVIDOR (punto 211 del 28-08). Esto los sumaba aquí
// leyendo `macros_efectivos` de cada alimento guardado, y ese campo muchas veces no está:
// los días que vinieron de Calma no lo tienen ni uno, así que la lista salía entera a
// «0 P · 0 H · 0 G» aunque la fila dijera «6 comidas». Ahora vienen ya calibrados en
// `dia.macros`, del mismo motor que cuenta el día abierto: una fuente, un número.
// La suma local se queda solo de red de seguridad por si la respuesta viniera sin ellos.
const macrosDelDia = (dia) => dia?.macros || Object.values(dia?.comidas || {}).reduce((acc, m) => {
    for (const a of (m?.alimentos || [])) {
        acc.P += a?.macros_efectivos?.P || 0;
        acc.H += a?.macros_efectivos?.H || 0;
        acc.G += a?.macros_efectivos?.G || 0;
    }
    return acc;
}, { P: 0, H: 0, G: 0 });

const comidasMontadas = (comidas) =>
    Object.values(comidas || {}).filter(m => (m?.alimentos || []).length > 0).length;

/**
 * LA ETIQUETA DE LA FILA (punto 212 del 28-08).
 *
 * Era `tipo_dia === el de hoy` y nada más, así que ponía «Encaja» en el cien por cien de
 * las filas: «si lo lleva el cien por cien, la etiqueta no dice nada». Ahora la calcula el
 * servidor comparando los macros de ese día con los del día que se está montando, y dice
 * una de tres cosas:
 *
 *     Encaja        cabe tal cual, dentro del margen de 4 g
 *     +12 H         por dónde se sale y por cuánto (se canta lo que SOBRA, que es lo que
 *                   estorba: lo que falta se completa añadiendo)
 *     Otro día      era de descanso y hoy toca entrenar, o al revés
 *
 * El color va sólo en la que encaja, que es la que le sirve; el resto en gris. Así la
 * etiqueta elige por él, que es para lo que está.
 */
const MENOS = '−';   // el menos de verdad, no un guion (igual que en lib/estadoDelMacro)

const etiquetaDelDia = (dia, tipoDiaHoy) => {
    // De un servidor viejo (o de una respuesta en caché) no viene: se vuelve a lo de antes,
    // que al menos distingue el tipo de día.
    if (dia.encaja === undefined) {
        return (dia.tipo_dia || 'entrenamiento') === tipoDiaHoy
            ? { texto: 'Encaja', encaja: true, ayuda: 'Mismo tipo de día que hoy' }
            : { texto: 'Otro día', encaja: false, ayuda: 'Otro tipo de día: se recuadra sola a los macros de hoy' };
    }
    if (dia.encaja) {
        return { texto: 'Encaja', encaja: true,
                 ayuda: 'Sus macros son los de este día: se copia tal cual' };
    }
    if (dia.motivo === 'otro_dia') {
        return { texto: 'Otro día', encaja: false,
                 ayuda: 'Otro tipo de día: se recuadra sola a los macros de este día' };
    }
    if (dia.motivo === 'desvio') {
        const d = Math.round(dia.desvio || 0);
        return { texto: `${d > 0 ? '+' : MENOS}${Math.abs(d)} ${dia.macro}`, encaja: false,
                 ayuda: `Se ${d > 0 ? 'pasa' : 'queda corto'} de ${Math.abs(d)} g: al copiarlo se ajusta a tus macros` };
    }
    return null;   // sin macros asignados no se puede saber, y no se inventa
};

/** Fila de un día reciente en la lista de «Repetir un día». */
const FilaDiaReciente = ({ dia, tipoDiaHoy, formatDate, onElegir, aplicando }) => {
    const macros = macrosDelDia(dia);
    const n = comidasMontadas(dia.comidas);
    const etiqueta = etiquetaDelDia(dia, tipoDiaHoy);
    return (
        <button
            onClick={() => onElegir(dia)}
            disabled={Boolean(aplicando)}
            data-testid={`dia-vacio-reciente-${dia.fecha}`}
            title={etiqueta?.ayuda || ''}
            className="w-full flex items-center gap-3 rounded-xl border border-border bg-muted/40 px-3 py-2.5 text-left transition-colors hover:border-brand disabled:opacity-60"
        >
            <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-foreground truncate">{formatDate(dia.fecha)}</p>
                <p className="text-xs text-muted-foreground">
                    {esDescanso(dia.tipo_dia) ? 'Descanso' : 'Entreno'} · {n === 1 ? '1 comida' : `${n} comidas`}
                </p>
                <p className="text-xs text-muted-foreground tabular-nums">
                    {Math.round(macros.P)} P · {Math.round(macros.H)} H · {Math.round(macros.G)} G
                </p>
            </div>
            {aplicando === dia.fecha ? (
                <div className="w-4 h-4 shrink-0 border-2 border-brand border-t-transparent rounded-full animate-spin" />
            ) : etiqueta && (
                <span data-testid={`dia-vacio-etiqueta-${dia.fecha}`}
                    className={`shrink-0 text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full tabular-nums ${
                        etiqueta.encaja ? 'bg-brand/10 text-brand' : 'bg-muted text-muted-foreground'
                    }`}>
                    {etiqueta.texto}
                </span>
            )}
        </button>
    );
};

const DiaVacio = ({
    titulo,             // «Hoy · jueves, 21 de agosto» o el día que sea
    tipoDia,            // el tipo del día ABIERTO, para el chip Encaja/Se adapta
    numFavoritas,       // cuántas dietas guardadas tiene (null mientras cargan)
    onCrear,            // abre la parrilla de siempre
    onVerFavoritas,     // abre el selector de favoritas que ya existe
    recientes,          // días de /diets/recent (ya sin el día abierto y sin vacíos)
    cargandoRecientes,
    onRepetir,          // async (dia) -> aplica con el refit de siempre
    formatDate,
}) => {
    const [listaAbierta, setListaAbierta] = useState(false);
    // La fecha que se está aplicando, para el spinner de su fila y para no aplicar dos.
    const [aplicando, setAplicando] = useState(null);

    const elegirDia = async (dia) => {
        if (aplicando) return;
        setAplicando(dia.fecha);
        try { await onRepetir(dia); } finally { setAplicando(null); }
    };

    const hayFavoritas = (numFavoritas || 0) > 0;
    const hayRecientes = (recientes || []).length > 0;

    return (
        <section className="surface p-5 sm:p-6 max-w-xl mx-auto" data-testid="dia-vacio">
            {/* La pregunta */}
            <p className="caption text-brand mb-1">{titulo}</p>
            {/* El texto del punto 7 del 23-08: fuera «montar», se dice crear. */}
            <h2 className="font-heading font-bold text-2xl text-foreground leading-tight">
                Todavía sin crear
            </h2>
            <p className="text-sm text-muted-foreground mt-1 mb-5">
                Puedes repetir una dieta que ya tengas o empezarla de cero.
            </p>

            {/* Salida 1: crear de cero (la primaria) */}
            <button onClick={onCrear} data-testid="dia-vacio-crear"
                className="btn-brand w-full flex items-center justify-center gap-2">
                <Plus size={18} /> Crear el día
            </button>

            {/* Salida 2: una de sus dietas guardadas. Solo si tiene alguna: ofrecer
                «Ver las 0» sería mandarle a una lista vacía. */}
            {hayFavoritas && (
                <button onClick={onVerFavoritas} data-testid="dia-vacio-favoritas"
                    className="mt-2.5 w-full flex items-center gap-3 rounded-xl border border-border px-4 py-3 text-left transition-colors hover:border-brand group">
                    <Star size={18} className="shrink-0 text-brand" />
                    <span className="flex-1 min-w-0 text-sm font-semibold text-foreground">Una de mis dietas</span>
                    <span className="shrink-0 text-sm font-semibold text-muted-foreground group-hover:text-brand flex items-center gap-1">
                        Ver las {numFavoritas} <ChevronRight size={16} />
                    </span>
                </button>
            )}

            {/* Salida 3: repetir un día reciente montado */}
            {(hayRecientes || cargandoRecientes) && (
                <div className="mt-2.5">
                    <button onClick={() => setListaAbierta(v => !v)} data-testid="dia-vacio-repetir"
                        className="w-full flex items-center gap-3 rounded-xl border border-border px-4 py-3 text-left transition-colors hover:border-brand group"
                        aria-expanded={listaAbierta}>
                        <History size={18} className="shrink-0 text-brand" />
                        <span className="flex-1 min-w-0 text-sm font-semibold text-foreground">Repetir un día</span>
                        <span className="shrink-0 text-sm font-semibold text-muted-foreground group-hover:text-brand flex items-center gap-1">
                            {listaAbierta ? <>Cerrar <ChevronUp size={16} /></> : <>Elegir <ChevronRight size={16} /></>}
                        </span>
                    </button>

                    {listaAbierta && (
                        <div className="mt-2 space-y-1.5" data-testid="dia-vacio-recientes">
                            {cargandoRecientes ? (
                                <div className="flex justify-center py-4">
                                    <div className="w-5 h-5 border-2 border-brand border-t-transparent rounded-full animate-spin" />
                                </div>
                            ) : recientes.map(dia => (
                                <FilaDiaReciente
                                    key={dia.fecha}
                                    dia={dia}
                                    tipoDiaHoy={tipoDia}
                                    formatDate={formatDate}
                                    onElegir={elegirDia}
                                    aplicando={aplicando}
                                />
                            ))}
                            {/* PUNTO 213 DEL 28-08. Ponía «El día elegido se ajusta solo a tus
                                macros de este día», y esa frase se lee dos veces: «se ajusta
                                solo» puede ser automáticamente o únicamente, y «este día» puede
                                ser el que copio o el que estoy montando. Las dos dudas caen
                                diciendo qué pasa, en orden y sin pronombres. */}
                            <p className="text-[11px] text-muted-foreground pt-0.5"
                                data-testid="dia-vacio-pie">
                                Se copian las comidas y se ajustan a tus macros de hoy.
                            </p>
                        </div>
                    )}
                </div>
            )}
        </section>
    );
};

export default DiaVacio;
