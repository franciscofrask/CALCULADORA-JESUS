import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, CheckSquare, ChevronRight, Circle, Square, Zap } from 'lucide-react';
import { leer as leerLocal, escribir as escribirLocal } from '../../lib/almacenLocal';
import { num0, num1 } from '../../lib/numeros';
import { leerMacro } from '../../lib/estadoDelMacro';
import ExtrasDelDia from '../nutrition/ExtrasDelDia';

/**
 * «TU DIETA HOY» (doc de Jesús del 21-08, tarea 4.2; repintado con el doc del 23-08,
 * punto 1): el deslizador de cuatro posiciones sobre los tres números por macro -- el
 * nombre encima, el número en naranja y, en Falta, «para llegar» con su barra --, y
 * debajo «Marca lo que ya te has comido» con las hechas contraídas y el peri en su
 * propia tarjeta, con lo que lleva dentro.
 *
 *  - Macros  · el objetivo del día CON el perientreno dentro. Es el mismo número que la
 *              cabecera de Nutrición: `resumen.P_total/H_total` del reparto vivo
 *              (`POST /calculator/distribute`) llevan el peri sumado, y `G_total` no lo
 *              lleva porque en el método la grasa del peri no cuenta.
 *  - Dieta   · la suma de lo montado: `servido_comidas` (lo cuenta el servidor, calibrado)
 *              más lo montado en el peri (P/H; la grasa del peri va fuera, como arriba).
 *  - Llevas  · la suma de las comidas MARCADAS con su casilla. Los Extras del día NO
 *              entran (punto 28 del doc del 24-08): ver abajo.
 *  - Falta   · Macros menos Llevas. PUEDE quedar en negativo y se dice tal cual («Te has
 *              pasado de 12 g de hidratos»), en tono tostado, sin bronca.
 *
 * LOS EXTRAS NO TOCAN NADA DE ESTO. Hasta el 24-08 se sumaban en Llevas y por eso le
 * encogían el Falta: si se comía una tarta a media tarde, la app le decía «ya no te comas
 * la comida 4». Eso es enseñarle a compensar, que es justo lo contrario del método. Van en
 * su lista, aparte (nutrition/ExtrasDelDia), y aquí solo se pintan.
 *
 * LA CASILLA POR COMIDA vive en el servidor: `PATCH /diets/{fecha}/comida-marcada`
 * escribe `comidas.{k}.marcada` dentro del día, así la marca viaja con la cuenta a
 * cualquier aparato. El navegador (`almacenLocal`, por cliente y fecha) queda de red
 * por si la petición no llega; al recargar, lo del servidor manda sobre lo local.
 * Antes del 21-08 esta marca no existía en ninguna parte: los estados «Sin hacer /
 * Cuadrada» se calculan de los macros y nadie guardaba «me la he comido».
 */

const NOMBRE = { P: 'Proteína', H: 'Hidratos', G: 'Grasa' };
const NOMBRE_LLANO = { P: 'proteína', H: 'hidratos', G: 'grasa' };

const VISTAS = [
    { id: 'macros', label: 'Macros' },
    { id: 'dieta', label: 'Dieta' },
    { id: 'llevas', label: 'Llevas' },
    { id: 'falta', label: 'Falta' },
];

const PIE_DE_VISTA = {
    // El texto del punto 2 del doc del 23-08, palabra por palabra.
    macros: 'Los macros totales a los que tienes que llegar hoy. Debajo verás el desglose por comidas.',
    dieta: 'Lo que tienes creado en la calculadora',
    falta: 'Lo que te queda para cuadrar el día',
};

// Suma de `macros_efectivos` de los alimentos de una comida guardada. Es el mismo campo
// que suma el Inicio viejo; cuando falta en filas antiguas, esa comida cuenta 0 y el
// total del día lo sigue diciendo el servidor (`servido_comidas`), que calibra de verdad.
const montadoDe = (comida) => (comida?.alimentos || []).reduce((acc, a) => {
    const m = a.macros_efectivos || {};
    return { P: acc.P + (m.P || 0), H: acc.H + (m.H || 0), G: acc.G + (m.G || 0) };
}, { P: 0, H: 0, G: 0 });

// SIN LETRAS Y REDONDOS (punto 98 del 25-08). Hasta hoy: «61P · 30,2H · 19,6G». Queda
// «61 · 30 · 20»: el orden es siempre el mismo y ya está escrito arriba, en los rótulos de
// los tres números, así que la P, la H y la G solo añaden ruido. Y el decimal en una lista
// que se lee de un vistazo tampoco decide nada.
const lineaMacros = (m, sinGrasa = false) => [
    num0(m.P || 0), num0(m.H || 0), ...(sinGrasa ? [] : [num0(m.G || 0)]),
].join(' · ');

const nombreComida = (k, unica) => (unica ? 'Comida única' : `Comida ${k.slice(1)}`);

// El intra y el post, en el orden en que se toman: uno detrás del otro (punto 97).
const ORDEN_PERI = ['Intra', 'Post'];

const TuDietaHoy = ({ api, userId, fecha, dieta, objetivo, servido, navigate }) => {
    const [vista, setVista] = useState('macros');
    // Las comidas ya marcadas se CONTRAEN («2 hechas · ocultas — Ver», punto 1 del doc
    // del 23-08): la lista enseña solo lo que queda por comer, y el «Ver» las despliega.
    const [verHechas, setVerHechas] = useState(false);
    // El peri va DENTRO del total por defecto (punto 87): el 250 ya lleva los 40 del peri.
    // Desmarcarlo es una forma de mirar la cuenta, no un ajuste que se guarde, así que
    // vuelve a su sitio al cambiar de día.
    const [periDentro, setPeriDentro] = useState(true);
    useEffect(() => { setVerHechas(false); setPeriDentro(true); }, [fecha]);
    // El reparto vivo del día: los totales con el peri y el objetivo de cada comida.
    const [reparto, setReparto] = useState(null);
    const [marcadas, setMarcadas] = useState({});
    // Los Extras del día: lo comido fuera de la dieta. Llegan con el documento del día
    // (`extras`) y el estado se queda aquí, en el padre, para que la lista sobreviva a un
    // repintado del bloque; añadir o quitar avisa hacia arriba. No se suman en ningún sitio.
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

    // EL DOCUMENTO DEL DÍA PUEDE EXISTIR SIN DIETA MONTADA. Desde el 24-08 apuntar un extra
    // es un campo de texto y un toque, y ese POST hace upsert del día: quien apunta el café
    // de las 10:00 antes de montar nada ya tiene documento, con `exists: true` y sin
    // configuración dentro. Si eso se diera por «día configurado», a quien tiene 3 comidas
    // le pintaríamos 4 vacías. El marcador bueno es `num_comidas`, que lo escribe siempre
    // `upsert_diet_doc` en cuanto se guarda una dieta de verdad.
    const diaConfigurado = Boolean(dieta?.exists && dieta.num_comidas);

    // El reparto se pide UNA vez con la configuración del día: la de la dieta si está
    // guardada y, si no, la que el cliente tiene puesta (`/user/diet-config`), que es la
    // misma precedencia que aplica el servidor al resolver `objetivo_comidas`.
    useEffect(() => {
        let cancelado = false;
        const cargar = async () => {
            try {
                let cfg;
                if (diaConfigurado) {
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

    // Qué comidas tiene el día, en su orden. De lo guardado si el día lleva su
    // configuración dentro; si no, del reparto (que salió de la del cliente).
    const numComidas = diaConfigurado ? dieta.num_comidas
        : (reparto?.comidas ? Object.keys(reparto.comidas).length : 4);
    const esUnica = numComidas === 1;
    const claves = ['C1', 'C2', 'C3', 'C4'].slice(0, Math.max(1, Math.min(4, numComidas)));

    const montadoPorComida = useMemo(() => Object.fromEntries(
        claves.map((k) => [k, montadoDe(comidasGuardadas[k])])),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [dieta, numComidas]);

    // EL INTRA Y EL POST, CADA UNO EL SUYO (puntos 96 y 97 del 25-08). Hasta hoy se fundían
    // en una sola tarjeta llamada «Perientreno», sin casilla, y por eso Llevas no llegaba
    // NUNCA al total: marcabas las cuatro comidas, te tomabas el batido y te seguían
    // faltando los 40 de proteína. Son dos tomas con nombre propio, como la Comida 1 y la 2.
    //
    // Lo que suma al marcarlo es lo que la fila enseña: lo montado si lo hay y, si no, su
    // objetivo. En las comidas eso no vale (lo que te comes depende de lo que montes), pero
    // el peri es una toma fija -- el batido de siempre --, así que el número se sabe sin
    // montarlo, y es el que hay que poder marcar para que la cuenta cierre.
    const periPorBloque = useMemo(() => {
        const objetivos = reparto?.periworkout || {};
        const res = {};
        for (const k of ORDEN_PERI) {
            const guardada = comidasGuardadas[k];
            const tiene = (guardada?.alimentos || []).length > 0;
            const obj = objetivos[k];
            if (!tiene && !obj) continue;
            const montado = montadoDe(guardada);
            res[k] = {
                tiene,
                montado,
                objetivo: obj ? { P: obj.P || 0, H: obj.H || 0, G: 0 } : null,
                // La grasa del peri no cuenta en el método, así que ni se pinta ni se suma.
                suma: tiene ? { ...montado, G: 0 } : { P: obj.P || 0, H: obj.H || 0, G: 0 },
            };
        }
        return res;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dieta, reparto]);

    const clavesPeri = ORDEN_PERI.filter((k) => periPorBloque[k]);

    // El sitio del peri en la lista: justo después de la comida tras la que se entrena
    // (`momento_entreno`, 0 en ayunas, 1 después de la C1...). Y los dos juntos, que se
    // toman uno detrás de otro. Si el día tiene menos comidas que el momento apuntado, van
    // al final: nunca desaparecen de la lista por un dato viejo.
    const momentoEntreno = diaConfigurado
        ? (dieta.momento_entreno != null ? dieta.momento_entreno : 1)
        : (reparto?.config?.momento_entreno != null ? reparto.config.momento_entreno : 1);
    const trasComida = Math.max(0, Math.min(claves.length, Number(momentoEntreno) || 0));

    const filas = useMemo(() => {
        const lista = [];
        const meterPeri = () => clavesPeri.forEach((k) => lista.push({ clave: k, esPeri: true }));
        if (trasComida === 0) meterPeri();
        claves.forEach((k, i) => {
            lista.push({ clave: k, esPeri: false });
            if (i + 1 === trasComida) meterPeri();
        });
        return lista;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [claves.join(','), clavesPeri.join(','), trasComida]);

    const hechas = filas.filter((f) => marcadas[f.clave]);
    // «Llevas» son las comidas marcadas y nada más: los extras NO se suman (punto 28 del
    // doc del 24-08). Ya mordió una vez -- sumarlos encogía el «Falta» del resto del día y
    // la app acababa diciéndole que se saltara una comida por haberse comido una tarta --,
    // así que si alguien vuelve a plantearlo, la respuesta es que no.
    const llevas = hechas.reduce((acc, f) => {
        const m = f.esPeri ? periPorBloque[f.clave].suma : montadoPorComida[f.clave];
        return { P: acc.P + m.P, H: acc.H + m.H, G: acc.G + (m.G || 0) };
    }, { P: 0, H: 0, G: 0 });

    // Lo que falta, redondeado, que es lo que se pinta. El desvío EXACTO se guarda aparte:
    // es el único decimal que sobrevive en todo el Inicio (punto 80), y solo para la línea
    // de aviso, que es donde el gramo de verdad sirve para algo.
    const faltaExacto = conPeri ? {
        P: conPeri.P - llevas.P, H: conPeri.H - llevas.H, G: conPeri.G - llevas.G,
    } : null;
    const falta = faltaExacto ? {
        P: Math.round(faltaExacto.P), H: Math.round(faltaExacto.H), G: Math.round(faltaExacto.G),
    } : null;
    const pasadas = falta ? ['P', 'H', 'G'].filter((k) => falta[k] < 0) : [];

    // EL PERIENTRENO, DENTRO O APARTE (puntos 86 a 88). Los dos números salen del MISMO
    // reparto, así que la resta cuadra siempre: el total lleva el peri sumado
    // (`resumen.P_total`) y quitárselo da exactamente el objetivo de las comidas, que es el
    // número que enseña Mis macros. La grasa no se toca: en el método la del peri no cuenta,
    // y por eso `G_total` nunca la llevó.
    const periTotal = useMemo(() => ORDEN_PERI.reduce((acc, k) => {
        const o = (reparto?.periworkout || {})[k];
        return o ? { P: acc.P + (o.P || 0), H: acc.H + (o.H || 0) } : acc;
    }, { P: 0, H: 0 }), [reparto]);
    const hayPeriEnElDia = periTotal.P > 0 || periTotal.H > 0;
    const sinPeri = conPeri
        ? { P: conPeri.P - periTotal.P, H: conPeri.H - periTotal.H, G: conPeri.G }
        : conPeri;

    const valoresDeVista = {
        macros: periDentro ? conPeri : sinPeri,
        dieta: totalDieta, llevas, falta,
    };
    const valores = valoresDeVista[vista];
    // Con un extra apuntado y ninguna comida marcada, Llevas vuelve a decir «Todavía no
    // has marcado nada»: desde que los extras no suman, el número sería un 0 pelado.
    const nadaMarcado = hechas.length === 0;

    const irANutricion = () => navigate('/dashboard/nutrition');
    // El peri aterriza EN el peri (P32 del 23-08): pinchar su tarjeta te dejaba en la
    // cocina con la Comida 1 delante. Se va al bloque que el día tenga (Intra o Post).
    const irAlPeri = (clave) => navigate(`/dashboard/nutrition?comida=${clave}`);

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
                                /* `min-w-0` para que las 4 columnas sean de verdad iguales: sin él,
                                   la celda no baja del ancho de su texto y «Macros» ensancha su
                                   columna y su pastilla invadía la de «Dieta» en pantalla estrecha.
                                   Poco padding para que los labels quepan enteros sin cortarse. */
                                className={`min-w-0 px-1 py-1.5 rounded-lg text-xs sm:text-sm font-semibold text-center transition-colors
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
                            {/* Se pintan POR MACRO y las cuatro pestañas se pintan IGUAL: el
                                nombre con su punto encima, el número grande, la palabra del
                                estado debajo y la barra. La regla de qué estado es cada cosa
                                vive entera en lib/estadoDelMacro; aquí solo se pinta.

                                EL NÚMERO VA EN BLANCO (punto 75 del 25-08). Iba en el naranja
                                de la marca, el mismo del botón de Guardar y de la pestaña
                                activa: cinco cosas distintas pintadas del mismo color, así que
                                el color no decía nada. El estado lo dirán la palabra, el punto
                                y la barra (puntos 82 y 83); el número solo dice cuánto. */}
                            <div className="grid grid-cols-3 gap-3 mt-4">
                                {['P', 'H', 'G'].map((k) => {
                                    const crudo = valores ? Math.round(valores[k] || 0) : null;
                                    const objetivoK = conPeri ? Math.round(conPeri[k] || 0) : 0;
                                    /* LO QUE HAY YA, que es de donde sale el estado: lo creado
                                       en Dieta y lo comido en Llevas y en Falta (Falta enseña
                                       el mismo dato del revés, así que su estado es el mismo).
                                       En Macros no hay estado: el número ES el objetivo. */
                                    const hayK = vista === 'dieta' ? Math.round(totalDieta[k] || 0)
                                        : Math.round(llevas[k] || 0);
                                    const lectura = leerMacro({ vista, hay: hayK, objetivo: objetivoK });
                                    /* En Falta, el negativo NO se deja en cero (doc 21-08,
                                       apartado 5): se enseña lo pasado. La bronca no existe:
                                       es un dato, y la palabra de debajo ya dice qué es. */
                                    const impreso = crudo == null ? null
                                        : (vista === 'falta' ? Math.abs(crudo) : Math.max(0, crudo));
                                    return (
                                        <div key={k} className="text-center" data-testid={`dieta-hoy-${vista}-${k}`}>
                                            {/* EL PUNTO, JUNTO AL NOMBRE (punto 82). Sin punto
                                                significa que no hay nada que mirar, y por eso no
                                                hace falta leyenda que aprenderse. */}
                                            <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center justify-center gap-1">
                                                {NOMBRE[k]}
                                                {lectura.color && (
                                                    <span data-testid={`punto-${vista}-${k}`}
                                                        className={`w-1.5 h-1.5 rounded-full ${lectura.color === 'ok' ? 'bg-ok' : 'bg-pasado'}`} />
                                                )}
                                            </p>
                                            <p className="numero-grande font-data leading-none text-[34px] sm:text-[40px] mt-1.5 text-foreground">
                                                {impreso == null ? '·' : impreso}
                                            </p>
                                            <p data-testid={`palabra-${vista}-${k}`}
                                                className={`text-xs mt-1 ${lectura.color === 'ok' ? 'text-ok font-medium'
                                                    : lectura.color === 'pasado' ? 'text-pasado font-medium' : 'text-muted-foreground'}`}>
                                                {lectura.palabra}
                                            </p>
                                            {/* La barra, en las cuatro menos en Macros: allí no
                                                hay nada que recorrer. */}
                                            {lectura.barra && (
                                                <div className="h-1 rounded-full bg-muted mt-1.5 overflow-hidden">
                                                    <div data-testid={`barra-${vista}-${k}`}
                                                        className={`h-full rounded-full ${lectura.barra.color === 'ok' ? 'bg-ok'
                                                            : lectura.barra.color === 'pasado' ? 'bg-pasado' : 'bg-neutro'}`}
                                                        style={{ width: `${lectura.barra.largo}%` }} />
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                            {/* Lo pasado se dice tal cual, en el naranja de «te has pasado»
                                (#FF5A2E, punto 76) y sin bronca. Es el ÚNICO sitio del Inicio
                                donde el número puede llevar decimal (punto 80). */}
                            {vista === 'falta' && pasadas.length > 0 && (
                                <div className="mt-3 space-y-0.5" data-testid="falta-pasado">
                                    {pasadas.map((k) => (
                                        <p key={k} className="text-sm text-center font-medium text-pasado">
                                            Te has pasado {num1(Math.abs(faltaExacto[k]))} g de {NOMBRE_LLANO[k]}
                                        </p>
                                    ))}
                                </div>
                            )}
                            {vista === 'llevas' ? (
                                /* Solo las comidas: los extras no se nombran aquí porque no
                                   entran en la cuenta, y verlos al lado del número sería
                                   volver a prometer que suman. */
                                <p className="text-xs text-muted-foreground text-center mt-3">
                                    {hechas.length === 1 ? '1 comida marcada' : `${hechas.length} comidas marcadas`}
                                </p>
                            ) : PIE_DE_VISTA[vista] ? (
                                <p className="text-xs text-muted-foreground text-center mt-3">{PIE_DE_VISTA[vista]}</p>
                            ) : null}

                            {/* EL INTERRUPTOR DEL PERIENTRENO, Y SOLO EN MACROS (puntos 86 a
                                88). En Dieta, Llevas y Falta no aparece: ahí el peri ya va
                                contado como una comida más, con su fila y su casilla.

                                LA CASILLA VA DELANTE DEL TEXTO. Puesta ahí se lee como lo que
                                es -- algo que se puede desmarcar -- y no hace falta explicarlo;
                                detrás habría que contarlo, y en el móvil competiría por el
                                ancho con la frase.

                                Y al desmarcarlo se ve la cuenta: 210 + 40 = 250 de proteína.
                                Con eso se acaba el lío entre este número y el de Mis macros,
                                que enseña el mismo día sin el peri y parecía un error. */}
                            {vista === 'macros' && hayPeriEnElDia && (
                                <button type="button" role="checkbox" aria-checked={periDentro}
                                    onClick={() => setPeriDentro((v) => !v)}
                                    data-testid="interruptor-peri"
                                    className="mt-2 mx-auto flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors">
                                    {periDentro
                                        ? <CheckSquare className="w-4 h-4 text-ok flex-shrink-0" />
                                        : <Square className="w-4 h-4 flex-shrink-0" />}
                                    <span>
                                        {periDentro
                                            ? 'Perientreno incluido'
                                            : `Perientreno aparte · ${num0(periTotal.P)} P · ${num0(periTotal.H)} H`}
                                    </span>
                                </button>
                            )}
                        </>
                    )}
                </div>
            </section>

            <section className="space-y-3" data-testid="marca-comidas">
                <p className="caption">Marca lo que ya te has comido</p>

                {/* Las hechas, contraídas en una fila: la lista queda para lo que falta
                    por comer. El «Ver» las despliega (y ahí se pueden desmarcar). */}
                {hechas.length > 0 && (
                    <div className="surface p-3.5 sm:p-4 flex items-center justify-between gap-3"
                        data-testid="resumen-hechas">
                        <p className="text-sm text-muted-foreground">
                            <span className="font-bold text-foreground">
                                {hechas.length === 1 ? '1 hecha' : `${hechas.length} hechas`}
                            </span>
                            {!verHechas && ' · ocultas'}
                        </p>
                        <button onClick={() => setVerHechas((v) => !v)} data-testid="ver-hechas"
                            className="text-sm font-semibold text-brand flex items-center gap-0.5">
                            {verHechas ? 'Ocultar' : 'Ver'} <ChevronRight className={`w-4 h-4 transition-transform ${verHechas ? 'rotate-90' : ''}`} />
                        </button>
                    </div>
                )}

                {/* UNA FILA POR TOMA, TODAS IGUALES (puntos 96, 97 y 101). El intra y el
                    post llevan su círculo a la izquierda, como las comidas, y el rayo pasa
                    a ir junto al nombre, que es donde dice algo y no donde estorba. Al
                    marcarlos no pasa nada especial: tick verde y la línea apagada.
                    Y no llevan suplemento debajo (punto 100): el intra y el post SON el
                    suplemento, y colgarles otro confunde. */}
                {filas.map(({ clave: k, esPeri }) => {
                    const marcada = !!marcadas[k];
                    if (marcada && !verHechas) return null;
                    const peri = esPeri ? periPorBloque[k] : null;
                    const tieneAlimentos = esPeri
                        ? peri.tiene
                        : (comidasGuardadas[k]?.alimentos || []).length > 0;
                    const montado = esPeri ? peri.montado : montadoPorComida[k];
                    const objetivoFila = esPeri ? peri.objetivo : reparto?.comidas?.[k];
                    const nombre = esPeri ? k : nombreComida(k, esUnica);
                    return (
                        <div key={k} data-testid={`comida-hoy-${k}`}
                            className={`surface p-3.5 sm:p-4 flex items-center gap-3 transition-opacity ${marcada ? 'opacity-55' : ''}`}>
                            {/* La casilla. Persistencia: ver el comentario de cabecera. */}
                            <button onClick={() => marcar(k)} role="checkbox" aria-checked={marcada}
                                aria-label={`${nombre}: ${marcada ? 'ya marcado' : 'marcar como tomado'}`}
                                data-testid={`marcar-${k}`} className="flex-shrink-0 p-1 -m-1">
                                {marcada
                                    ? <CheckCircle2 className="w-6 h-6 text-ok" />
                                    : <Circle className="w-6 h-6 text-muted-foreground" />}
                            </button>
                            <button onClick={esPeri ? () => irAlPeri(k) : irANutricion}
                                className="flex-1 min-w-0 flex items-center gap-3 text-left group">
                                <div className="min-w-0 flex-1">
                                    <p className={`font-bold text-sm text-foreground flex items-center gap-1.5 ${marcada ? 'line-through' : ''}`}>
                                        {esPeri && <Zap className="w-3.5 h-3.5 text-brand flex-shrink-0" />}
                                        {nombre}
                                    </p>
                                    {/* Sin `truncate`: en 390 px «Sin hacer · objetivo 47 · 72 · 12»
                                        puede no caber en una línea. Que salte de línea. */}
                                    <p className="text-sm text-muted-foreground font-data">
                                        {tieneAlimentos
                                            ? lineaMacros(montado, esPeri)
                                            : objetivoFila
                                                ? (esPeri ? lineaMacros(objetivoFila, true)
                                                    : `Sin hacer · objetivo ${lineaMacros(objetivoFila)}`)
                                                : 'Sin hacer'}
                                    </p>
                                </div>
                                <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors flex-shrink-0" />
                            </button>
                        </div>
                    );
                })}
            </section>

            {/* «EXTRAS DEL DÍA», debajo de las comidas y del peri: lo comido fuera de la
                dieta. Su lista y ya: no entran en ninguna de las cuatro cuentas de arriba. */}
            <ExtrasDelDia api={api} fecha={fecha} extras={extrasDia} origen="inicio"
                onAnadido={(e) => setExtrasDia((prev) => [...prev, e])}
                onQuitado={(id) => setExtrasDia((prev) => prev.filter((x) => x.id !== id))} />
        </>
    );
};

export default TuDietaHoy;
