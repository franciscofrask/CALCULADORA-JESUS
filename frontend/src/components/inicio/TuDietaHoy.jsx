import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Circle, ChevronRight, Zap } from 'lucide-react';
import { leer as leerLocal, escribir as escribirLocal } from '../../lib/almacenLocal';
import { num1 } from '../../lib/numeros';
import ExtrasDelDia from '../nutrition/ExtrasDelDia';

/**
 * «TU DIETA HOY» (doc de Jesús del 21-08, tarea 4.2): el deslizador de cuatro posiciones
 * sobre los tres números grandes, y debajo «Marca lo que ya te has comido».
 *
 *  - Macros  · el objetivo del día CON el perientreno dentro. Es el mismo número que la
 *              cabecera de Nutrición: `resumen.P_total/H_total` del reparto vivo
 *              (`POST /calculator/distribute`) llevan el peri sumado, y `G_total` no lo
 *              lleva porque en el método la grasa del peri no cuenta.
 *  - Dieta   · la suma de lo montado: `servido_comidas` (lo cuenta el servidor, calibrado)
 *              más lo montado en el peri (P/H; la grasa del peri va fuera, como arriba).
 *  - Llevas  · la suma de las comidas MARCADAS con su casilla, MÁS los Extras del día
 *              (lo comido fuera de la dieta; el bloque vive en nutrition/ExtrasDelDia).
 *  - Falta   · Macros menos Llevas. PUEDE quedar en negativo y se dice tal cual («Te has
 *              pasado de 12 g de hidratos»), en tono tostado, sin bronca.
 *
 * LA CASILLA POR COMIDA vive en el servidor: `PATCH /diets/{fecha}/comida-marcada`
 * escribe `comidas.{k}.marcada` dentro del día, así la marca viaja con la cuenta a
 * cualquier aparato. El navegador (`almacenLocal`, por cliente y fecha) queda de red
 * por si la petición no llega; al recargar, lo del servidor manda sobre lo local.
 * Antes del 21-08 esta marca no existía en ninguna parte: los estados «Sin hacer /
 * Cuadrada» se calculan de los macros y nadie guardaba «me la he comido».
 */

const MACRO = { P: '#FF671F', H: '#2196F3', G: '#FFA500' };
const NOMBRE = { P: 'Proteína', H: 'Hidratos', G: 'Grasa' };
const NOMBRE_LLANO = { P: 'proteína', H: 'hidratos', G: 'grasa' };

const VISTAS = [
    { id: 'macros', label: 'Macros' },
    { id: 'dieta', label: 'Dieta' },
    { id: 'llevas', label: 'Llevas' },
    { id: 'falta', label: 'Falta' },
];

const PIE_DE_VISTA = {
    macros: 'Tu objetivo de hoy, con el perientreno dentro',
    dieta: 'Lo que tienes montado en la calculadora',
    falta: 'Lo que te queda para cuadrar el día',
};

// Suma de `macros_efectivos` de los alimentos de una comida guardada. Es el mismo campo
// que suma el Inicio viejo; cuando falta en filas antiguas, esa comida cuenta 0 y el
// total del día lo sigue diciendo el servidor (`servido_comidas`), que calibra de verdad.
const montadoDe = (comida) => (comida?.alimentos || []).reduce((acc, a) => {
    const m = a.macros_efectivos || {};
    return { P: acc.P + (m.P || 0), H: acc.H + (m.H || 0), G: acc.G + (m.G || 0) };
}, { P: 0, H: 0, G: 0 });

const lineaMacros = (m, sinGrasa = false) => [
    `${num1(m.P || 0)}P`, `${num1(m.H || 0)}H`, ...(sinGrasa ? [] : [`${num1(m.G || 0)}G`]),
].join(' · ');

const nombreComida = (k, unica) => (unica ? 'Comida única' : `Comida ${k.slice(1)}`);

const TuDietaHoy = ({ api, userId, fecha, dieta, objetivo, servido, navigate }) => {
    const [vista, setVista] = useState('macros');
    // El reparto vivo del día: los totales con el peri y el objetivo de cada comida.
    const [reparto, setReparto] = useState(null);
    const [marcadas, setMarcadas] = useState({});
    // Los Extras del día: lo comido fuera de la dieta. Llegan con el documento del día
    // (`extras`), y añadir o quitar actualiza aquí -- este estado es el que suma en
    // Llevas, así que vive en este componente y no en el bloque que los pinta.
    const [extrasDia, setExtrasDia] = useState([]);
    useEffect(() => { setExtrasDia((dieta?.exists && dieta.extras) || []); }, [dieta]);

    const comidasGuardadas = (dieta?.exists && dieta.comidas) || {};

    // La marca de cada comida: manda el servidor (`comidas.{k}.marcada`, la escribe
    // PATCH /diets/{fecha}/comida-marcada) y el navegador queda de red por si la
    // peticion no llega: la marca es del cliente en cualquier aparato, no de un
    // navegador (bloque 4 del doc 21-08).
    useEffect(() => {
        let delNavegador = {};
        try { delNavegador = JSON.parse(leerLocal(`inicio-marcadas-${fecha}`, userId) || '{}') || {}; }
        catch { delNavegador = {}; }
        const delServidor = Object.fromEntries(
            Object.entries(comidasGuardadas).filter(([, c]) => c?.marcada === true).map(([k]) => [k, true]));
        setMarcadas({ ...delNavegador, ...delServidor });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [fecha, userId, dieta]);

    const marcar = (k) => {
        setMarcadas((prev) => {
            const sig = { ...prev, [k]: !prev[k] };
            escribirLocal(`inicio-marcadas-${fecha}`, userId, JSON.stringify(sig));
            api.patch(`/diets/${fecha}/comida-marcada`, { comida: k, marcada: !prev[k] })
                .catch((e) => console.error('No se pudo guardar la marca de la comida', e));
            return sig;
        });
    };

    // El reparto se pide UNA vez con la configuración del día: la de la dieta si está
    // guardada y, si no, la que el cliente tiene puesta (`/user/diet-config`), que es la
    // misma precedencia que aplica el servidor al resolver `objetivo_comidas`.
    useEffect(() => {
        let cancelado = false;
        const cargar = async () => {
            try {
                let cfg;
                if (dieta?.exists) {
                    cfg = {
                        tipo_dia: dieta.tipo_dia || 'entrenamiento',
                        num_comidas: dieta.num_comidas || 4,
                        momento_entreno: dieta.momento_entreno != null ? dieta.momento_entreno : 1,
                        opcion_peri: dieta.opcion_peri || 'intra_post',
                    };
                } else {
                    const r = await api.get('/user/diet-config').catch(() => ({ data: {} }));
                    cfg = {
                        tipo_dia: 'entrenamiento',
                        num_comidas: r.data?.num_comidas || 4,
                        momento_entreno: r.data?.momento_entreno != null ? r.data.momento_entreno : 1,
                        opcion_peri: r.data?.opcion_peri || 'intra_post',
                    };
                }
                const res = await api.post('/calculator/distribute', {
                    fecha, ...cfg, single_meal: cfg.num_comidas === 1,
                });
                if (!cancelado) setReparto(res.data);
            } catch (err) {
                // Sin reparto no se rompe nada: los totales caen al objetivo sin peri, que
                // ya viene resuelto con la dieta. El porqué, a la consola.
                console.error('[inicio] no se pudo traer el reparto del día', err);
            }
        };
        cargar();
        return () => { cancelado = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [api, fecha, dieta]);

    // ── Las cuatro cuentas ──
    // Macros: con el peri dentro (resumen del reparto). Mientras el reparto no llega, el
    // objetivo sin peri, que es lo que hay: un número de menos, nunca uno inventado.
    const conPeri = reparto?.resumen
        ? { P: reparto.resumen.P_total || 0, H: reparto.resumen.H_total || 0, G: reparto.resumen.G_total || 0 }
        : objetivo;

    const periMontado = useMemo(() => {
        const intra = montadoDe(comidasGuardadas.Intra);
        const post = montadoDe(comidasGuardadas.Post);
        return { P: intra.P + post.P, H: intra.H + post.H };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dieta]);

    // Dieta: lo montado del día entero. Las comidas las cuenta el servidor (calibradas);
    // el peri se suma aquí en P/H. Su grasa no entra, igual que en Nutrición.
    const totalDieta = {
        P: (servido?.P || 0) + periMontado.P,
        H: (servido?.H || 0) + periMontado.H,
        G: servido?.G || 0,
    };

    // Qué comidas tiene el día, en su orden. Del reparto si llegó; si no, de lo guardado.
    const numComidas = dieta?.exists ? (dieta.num_comidas || 4)
        : (reparto?.comidas ? Object.keys(reparto.comidas).length : 4);
    const esUnica = numComidas === 1;
    const claves = ['C1', 'C2', 'C3', 'C4'].slice(0, Math.max(1, Math.min(4, numComidas)));

    const montadoPorComida = useMemo(() => Object.fromEntries(
        claves.map((k) => [k, montadoDe(comidasGuardadas[k])])),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [dieta, numComidas]);

    const hechas = claves.filter((k) => marcadas[k]);
    const deComidas = hechas.reduce((acc, k) => ({
        P: acc.P + montadoPorComida[k].P,
        H: acc.H + montadoPorComida[k].H,
        G: acc.G + montadoPorComida[k].G,
    }), { P: 0, H: 0, G: 0 });
    // Los Extras del día cuentan en Llevas y NO tocan la dieta: por eso se suman aquí
    // (donde se cuenta lo comido) y no en `totalDieta` (donde se cuenta lo montado).
    // Sus macros vienen calculados del servidor, del añadirlos.
    const deExtras = extrasDia.reduce((acc, e) => ({
        P: acc.P + (e.macros?.P || 0),
        H: acc.H + (e.macros?.H || 0),
        G: acc.G + (e.macros?.G || 0),
    }), { P: 0, H: 0, G: 0 });
    const llevas = {
        P: deComidas.P + deExtras.P,
        H: deComidas.H + deExtras.H,
        G: deComidas.G + deExtras.G,
    };

    const falta = conPeri ? {
        P: Math.round(conPeri.P - llevas.P),
        H: Math.round(conPeri.H - llevas.H),
        G: Math.round(conPeri.G - llevas.G),
    } : null;
    const pasadas = falta ? ['P', 'H', 'G'].filter((k) => falta[k] < 0) : [];

    // El peri del día: sus objetivos (del reparto) o lo que tenga montado.
    const periObjetivo = (() => {
        const p = reparto?.periworkout || {};
        const intra = p.Intra || {}; const post = p.Post || {};
        return { P: (intra.P || 0) + (post.P || 0), H: (intra.H || 0) + (post.H || 0) };
    })();
    const hayPeri = periObjetivo.P > 0 || periObjetivo.H > 0 || periMontado.P > 0 || periMontado.H > 0;

    const valoresDeVista = { macros: conPeri, dieta: totalDieta, llevas, falta };
    const valores = valoresDeVista[vista];
    // Un extra apuntado también es «llevar algo»: con extras, Llevas enseña números
    // aunque no haya ninguna comida marcada.
    const nadaMarcado = hechas.length === 0 && extrasDia.length === 0;

    const irANutricion = () => navigate('/dashboard/nutrition');

    return (
        <>
            <section className="space-y-3" data-testid="tu-dieta-hoy">
                <p className="caption">Tu dieta hoy</p>
                <div className="surface p-4 sm:p-5" data-testid="macros-de-hoy">
                    {/* El deslizador de CUATRO posiciones, clonado del de Mi semana (tres). */}
                    <div className="grid grid-cols-4 bg-muted rounded-xl p-1 gap-1" role="tablist"
                        data-testid="deslizador-dieta">
                        {VISTAS.map((v) => (
                            <button key={v.id} role="tab" aria-selected={vista === v.id}
                                onClick={() => setVista(v.id)} data-testid={`vista-${v.id}`}
                                className={`px-2 py-1.5 rounded-lg text-sm font-semibold transition-colors
                                    ${vista === v.id ? 'bg-brand text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}>
                                {v.label}
                            </button>
                        ))}
                    </div>

                    {vista === 'llevas' && nadaMarcado ? (
                        /* Sin nada marcado, Llevas no es un 0 en rojo: se dice y ya está. */
                        <p className="text-center text-sm py-8" data-testid="llevas-vacio">
                            <span className="text-foreground font-semibold">Todavía no has marcado nada.</span>
                            <br />
                            <span className="text-muted-foreground">Marca abajo lo que ya te has comido.</span>
                        </p>
                    ) : (
                        <>
                            <div className="grid grid-cols-3 gap-3 mt-4">
                                {['P', 'H', 'G'].map((k) => {
                                    /* En Falta, el negativo NO se deja en cero (doc 21-08,
                                       apartado 5): se enseña lo pasado, en tostado, con
                                       «de más» debajo. La bronca no existe: es un dato. */
                                    const crudo = valores ? Math.round(valores[k] || 0) : null;
                                    const pasado = vista === 'falta' && crudo != null && crudo < 0;
                                    return (
                                        <div key={k} className="text-center" data-testid={`dieta-hoy-${vista}-${k}`}>
                                            <p className={`font-data font-bold leading-none text-[34px] sm:text-[40px] ${pasado ? 'text-amber-600' : 'text-foreground'}`}>
                                                {crudo == null ? '·' : (pasado ? Math.abs(crudo) : Math.max(0, crudo))}
                                            </p>
                                            <p className="text-sm font-bold mt-1.5" style={{ color: MACRO[k] }}>{NOMBRE[k]}</p>
                                            {pasado && (
                                                <p className="text-sm text-amber-600 font-data">de más</p>
                                            )}
                                            {(vista === 'dieta' || vista === 'llevas') && conPeri && (
                                                <p className="text-sm text-muted-foreground font-data">de {Math.round(conPeri[k] || 0)}</p>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                            {/* Lo pasado se dice tal cual, en tono tostado y sin bronca. */}
                            {vista === 'falta' && pasadas.length > 0 && (
                                <div className="mt-3 space-y-0.5" data-testid="falta-pasado">
                                    {pasadas.map((k) => (
                                        <p key={k} className="text-sm text-center font-medium text-amber-600 dark:text-amber-400">
                                            Te has pasado de {Math.abs(falta[k])} g de {NOMBRE_LLANO[k]}
                                        </p>
                                    ))}
                                </div>
                            )}
                            {vista === 'llevas' ? (
                                <p className="text-xs text-muted-foreground text-center mt-3">
                                    {[
                                        hechas.length === 1 ? '1 comida marcada' : `${hechas.length} comidas marcadas`,
                                        extrasDia.length > 0
                                            ? (extrasDia.length === 1 ? '1 extra' : `${extrasDia.length} extras`)
                                            : null,
                                    ].filter(Boolean).join(' · ')}
                                </p>
                            ) : PIE_DE_VISTA[vista] ? (
                                <p className="text-xs text-muted-foreground text-center mt-3">{PIE_DE_VISTA[vista]}</p>
                            ) : null}
                        </>
                    )}
                </div>
            </section>

            <section className="space-y-3" data-testid="marca-comidas">
                <p className="caption">
                    Marca lo que ya te has comido
                    {hechas.length > 0 && (
                        <span className="normal-case tracking-normal text-muted-foreground font-normal" data-testid="resumen-hechas">
                            {' '}· {hechas.length === 1 ? '1 hecha' : `${hechas.length} hechas`}
                        </span>
                    )}
                </p>

                {claves.map((k) => {
                    const marcada = !!marcadas[k];
                    const montado = montadoPorComida[k];
                    const tieneAlimentos = (comidasGuardadas[k]?.alimentos || []).length > 0;
                    const objetivoComida = reparto?.comidas?.[k];
                    return (
                        <div key={k} data-testid={`comida-hoy-${k}`}
                            className={`surface p-3.5 sm:p-4 flex items-center gap-3 transition-opacity ${marcada ? 'opacity-55' : ''}`}>
                            {/* La casilla. Persistencia: ver el comentario de cabecera. */}
                            <button onClick={() => marcar(k)} role="checkbox" aria-checked={marcada}
                                aria-label={`${nombreComida(k, esUnica)}: ${marcada ? 'comida ya marcada' : 'marcar como comida'}`}
                                data-testid={`marcar-${k}`} className="flex-shrink-0 p-1 -m-1">
                                {marcada
                                    ? <CheckCircle2 className="w-6 h-6 text-brand" />
                                    : <Circle className="w-6 h-6 text-muted-foreground" />}
                            </button>
                            <button onClick={irANutricion} className="flex-1 min-w-0 flex items-center gap-3 text-left group">
                                <div className="min-w-0 flex-1">
                                    <p className={`font-bold text-sm text-foreground ${marcada ? 'line-through' : ''}`}>
                                        {nombreComida(k, esUnica)}
                                    </p>
                                    {/* Sin `truncate`: en 390 px «Sin hacer · objetivo 47,5P · 72H · 12G»
                                        no cabe en una línea y cortaba la grasa. Que salte de línea. */}
                                    <p className="text-sm text-muted-foreground font-data">
                                        {tieneAlimentos
                                            ? lineaMacros(montado)
                                            : objetivoComida
                                                ? `Sin hacer · objetivo ${lineaMacros(objetivoComida)}`
                                                : 'Sin hacer'}
                                    </p>
                                </div>
                                <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors flex-shrink-0" />
                            </button>
                        </div>
                    );
                })}

                {/* El peri va después y SIN casilla: el peri no se marca. */}
                {hayPeri && (
                    <button onClick={irANutricion} data-testid="peri-hoy"
                        className="surface surface-hover w-full p-3.5 sm:p-4 flex items-center gap-3 text-left group border-l-4 border-l-brand">
                        <div className="w-9 h-9 bg-brand/10 rounded-xl flex items-center justify-center flex-shrink-0">
                            <Zap className="w-4 h-4 text-brand" />
                        </div>
                        <div className="min-w-0 flex-1">
                            <p className="font-bold text-sm text-foreground">Perientreno</p>
                            <p className="text-sm text-muted-foreground font-data truncate">
                                {(periMontado.P > 0 || periMontado.H > 0)
                                    ? lineaMacros(periMontado, true)
                                    : `Objetivo ${lineaMacros(periObjetivo, true)}`}
                            </p>
                            <p className="text-xs text-muted-foreground mt-0.5">
                                Va aparte y no se marca: se ajusta con tu entreno.
                            </p>
                        </div>
                        <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors flex-shrink-0" />
                    </button>
                )}
            </section>

            {/* «EXTRAS DEL DÍA», debajo de las comidas y del peri: lo comido fuera de la
                dieta. Cuentan en Llevas (la suma de arriba) y no tocan la dieta. */}
            <ExtrasDelDia api={api} fecha={fecha} extras={extrasDia}
                onAnadido={(e) => setExtrasDia((prev) => [...prev, e])}
                onQuitado={(id) => setExtrasDia((prev) => prev.filter((x) => x.id !== id))} />
        </>
    );
};

export default TuDietaHoy;
