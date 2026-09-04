import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, CheckSquare, ChevronRight, Circle, Square, X, Zap } from 'lucide-react';
import { leer as leerLocal, escribir as escribirLocal } from '../../lib/almacenLocal';
import { MARGEN } from '../../lib/exceso';
import { num0, num1, numMedio } from '../../lib/numeros';
import { leerMacro, claseDelMacro, fondoDelMacro, llevaPunto } from '../../lib/estadoDelMacro';
import { suplementosPorComida } from '../../lib/suplementosDelDia';
import ExtrasDelDia from '../nutrition/ExtrasDelDia';

/**
 * «TU DIETA HOY» (doc de Jesús del 21-08, tarea 4.2; repintado con el del 23-08 y cerrado
 * con el artifact del 25-08, puntos 75 a 101): el deslizador de cuatro posiciones sobre los
 * tres números por macro -- el nombre con su punto encima, el número en blanco, la palabra
 * del estado debajo y la barra -- y, debajo, «Marca lo que te vayas comiendo» con las hechas
 * contraídas y una fila por toma, el intra y el post incluidos.
 *
 *  - Macros  · el objetivo del día CON el perientreno dentro. Es el mismo número que la
 *              cabecera de Nutrición: `resumen.P_total/H_total` del reparto vivo
 *              (`POST /calculator/distribute`) llevan el peri sumado, y `G_total` no lo
 *              lleva porque en el método la grasa del peri no cuenta. Aquí vive el
 *              interruptor que lo separa, y solo aquí.
 *  - Dieta   · la suma de lo montado: `servido_comidas` (lo cuenta el servidor, calibrado)
 *              más lo montado en el peri (P/H; la grasa del peri va fuera, como arriba).
 *  - Llevas  · la suma de lo MARCADO con su casilla, comidas y peri. Los Extras del día NO
 *              entran (punto 28 del doc del 24-08): ver abajo.
 *  - Falta   · Macros menos Llevas. PUEDE quedar en negativo y se dice tal cual («te pasas
 *              14»), en el naranja de pasarse y sin bronca: es un dato.
 *
 * QUÉ COLOR LLEVA CADA COSA NO SE DECIDE AQUÍ: la regla entera está en
 * lib/estadoDelMacro, y las cuatro pestañas le preguntan lo mismo.
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
    // Con «TU» (punto 91 del 25-08). Es su calculadora, no «la» calculadora: la diferencia
    // entre una herramienta que le han dado y una que es suya.
    dieta: 'Lo que tienes creado en tu calculadora',
    falta: 'Lo que te queda para cuadrar el día',
};

// EL CONTADOR DE «LLEVAS», CON EL PERI APARTE (punto 93). El perientreno no es una comida y
// no se suma al número de comidas: son sus palabras. Se dice al lado, que es donde no
// estorba y donde se entiende sin explicarlo.
const contarLoMarcado = (comidas, peris) => {
    const deComidas = comidas === 0 ? '' : (comidas === 1 ? '1 comida marcada' : `${comidas} comidas marcadas`);
    const losDos = peris.length === 2;
    const dePeri = peris.length === 0 ? ''
        : (losDos ? 'intra y post' : `el ${peris[0].toLowerCase()}`);
    if (!dePeri) return deComidas;
    // Sin ninguna comida marcada el peri se dice solo, y en mayúscula: «El intra».
    if (!deComidas) return dePeri.charAt(0).toUpperCase() + dePeri.slice(1);
    return losDos ? `${deComidas}, ${dePeri}` : `${deComidas} y ${dePeri}`;
};

// Suma de `macros_efectivos` de los alimentos de una comida guardada. Es el mismo campo
// que suma el Inicio viejo; cuando falta en filas antiguas, esa comida cuenta 0 y el
// total del día lo sigue diciendo el servidor (`servido_comidas`), que calibra de verdad.
const montadoDe = (comida) => (comida?.alimentos || []).reduce((acc, a) => {
    const m = a.macros_efectivos || {};
    return { P: acc.P + (m.P || 0), H: acc.H + (m.H || 0), G: acc.G + (m.G || 0) };
}, { P: 0, H: 0, G: 0 });

// REDONDOS Y CON LETRA (punto 173 del 27-08). El 25-08 (punto 98) se quitaron las letras
// porque el orden ya está escrito arriba, en los rótulos de los tres números. Mirando la
// app, Jesús lo revierte: «en el resto de la app llevan letra; aquí no, y es la misma
// pantalla». Manda la coherencia, así que «32P · 19H · 6G».
//
// LO MONTADO VA REDONDO Y EL OBJETIVO AL MEDIO GRAMO (punto 80 y su excepción del 29). El
// punto 80 es el de esta pantalla -- «ni un decimal en Inicio, ni arriba ni en las comidas» --
// y el 29 le pone una sola excepción: «lo único que lleva decimal es el objetivo de una
// comida cuando cae en medio gramo, y sólo entonces. Está contado en el 115».
//
// Y no es cosmética, es la misma cuenta que arregló el 115 en la ficha de la comida: con los
// objetivos escritos en entero, los seis del día suman 236 sobre un día de 235. Con el medio
// gramo puesto, la suma da el día exacto.
//
// Lo montado sigue redondo, que es lo que pedía el 98: «61P · 30,2H · 19,6G» queda «61 · 30
// · 20». Ahí el decimal no decide nada; en el objetivo sí, porque es contra lo que se resta.
const lineaMacros = (m, sinGrasa = false, n = num0) => [
    `${n(m.P || 0)}P`, `${n(m.H || 0)}H`, ...(sinGrasa ? [] : [`${n(m.G || 0)}G`]),
].join(' · ');

//: El objetivo de una comida, al medio gramo. `numMedio` no escribe «48,0»: los enteros
//  salen enteros y sólo el medio gramo trae coma.
const lineaObjetivo = (m, sinGrasa = false) => lineaMacros(m, sinGrasa, numMedio);

const nombreComida = (k, unica) => (unica ? 'Comida única' : `Comida ${k.slice(1)}`);

// El intra y el post, en el orden en que se toman: uno detrás del otro (punto 97).
const ORDEN_PERI = ['Intra', 'Post'];

const TuDietaHoy = ({ api, userId, fecha, dieta, objetivo, servido, navigate, suplementos }) => {
    // ABRE EN «DIETA» (Francisco, 2-09). Esto ha cambiado dos veces y conviene saberlo antes
    // de tocarlo otra vez:
    //
    //   Macros  ->  el punto 170 del 27-08
    //   Llevas  ->  «Todo lo validado antes del 1 de septiembre», 1.1, con su motivo: «Macros
    //               es el objetivo y no cambia en todo el día; Llevas es por dónde va hoy, que
    //               es lo que ha venido a mirar»
    //   Dieta   ->  Francisco, 2-09, que es lo que manda ahora
    //
    // Sin nada marcado, Llevas no sacaba tres ceros pelados sino «Todavía no has marcado
    // nada»; eso sigue estando y funciona igual cuando se entra a esa pestaña.
    //
    // Y DESDE EL 3-09 DEPENDE DEL DÍA (decisión de Francisco, que cierra las tres versiones
    // que había): «la app tiene que abrir en la pestaña de Llevas, pero si hay al menos una
    // comida guardada; si no, se abre en Dieta».
    //
    // Es la regla que tiene sentido de las dos puntas: con el día sin montar lo que toca es
    // montarlo, y para eso está Dieta; con el día ya montado lo que se viene a mirar es por
    // dónde vas, que es Llevas. Antes era un valor fijo y por eso hubo tres decisiones
    // seguidas: cada una acertaba en un caso y fallaba en el otro.
    //
    // `vistaFijada` guarda que el cliente ya ha tocado las pestañas: a partir de ahí manda
    // él y la regla no vuelve a moverle la vista debajo de los dedos cuando llegue el día.
    const [vista, setVista] = useState('dieta');
    const vistaFijada = useRef(false);
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

    // CON EL DÍA MONTADO SE ABRE EN LLEVAS; SIN MONTAR, EN DIETA (Francisco, 3-09).
    //
    // «Al menos una comida guardada» es una comida con alimentos dentro, no una marcada: lo
    // que decide es si hay dieta que seguir. El peri cuenta como comida, que también es una
    // toma del día.
    //
    // Solo mientras el cliente no haya tocado las pestañas. Si ya eligió una, mandar la vista
    // cuando llegue el día de otra petición sería moverle la pantalla debajo de los dedos.
    useEffect(() => {
        if (vistaFijada.current) return;
        const hayComidaGuardada = Object.values(comidasGuardadas)
            .some((c) => (c?.alimentos || []).length > 0);
        setVista(hayComidaGuardada ? 'llevas' : 'dieta');
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dieta, fecha]);

    // Al cambiar de día se vuelve a decidir sola: la elección era para el día que estaba
    // mirando, no para siempre.
    useEffect(() => { vistaFijada.current = false; }, [fecha]);

    const elegirVista = (cual) => { vistaFijada.current = true; setVista(cual); };

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

    // Los suplementos que le tocan con cada comida (punto 174). Ver `suplementosPorComida`.
    const supPorComida = useMemo(() => suplementosPorComida(suplementos, claves),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [suplementos, claves.join(',')]);

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

    // LA QUE TOCA AHORA (bloque 07 del doc «Cómo abre Inicio», 3-09).
    //
    // Su documento dice: «el Post lleva una barra naranja a la izquierda que no dice qué
    // significa» y «la marca del Post pasa a ser una palabra, Ahora, que se entiende sin
    // leyenda». O sea que NO es una marca nueva en cualquier fila: es LA MARCA QUE YA HAY
    // -- la del peri -- convertida en palabra cuando a esa toma le toca.
    //
    // Y «le toca» es secuencial (Francisco, 3-09): la primera SIN MARCAR en el orden del
    // día, que ya lo monta `filas` con el intra y el post en su sitio según el momento de
    // entreno. No hay reloj de por medio: se lee de lo que él ha ido marcando.
    //
    // Así que el chip sale en el intra o en el post cuando son los siguientes, y entonces
    // sustituyen su barra. Las demás filas no llevaban marca y siguen sin llevarla.
    //
    // Con el día entero marcado no toca ninguna, que es lo correcto.
    const siguienteSinMarcar = filas.find((f) => !marcadas[f.clave]) || null;
    const laDeAhora = siguienteSinMarcar?.esPeri ? siguienteSinMarcar.clave : null;
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
    // LA LÍNEA DE AVISO TAMBIÉN RESPETA EL MARGEN (punto 78). Se pintaba con `falta[k] < 0`,
    // o sea con cualquier gramo de más, y el margen de 4 no entraba: con 293 de hidratos
    // sobre 290, la tarjeta decía «3 · cuadrado» en verde y justo debajo «Te has pasado 3 g
    // de hidratos» en naranja. La misma tarjeta absolviendo y regañando por el mismo dato.
    // Manda el 78: «de 1 a 4, falte o sobre, es válido y sale en verde. No hace falta cuadrar
    // al gramo». Así que la línea la deciden las MISMAS reglas que el color, preguntándole a
    // `leerMacro`, y no una comparación aparte que nadie volvió a mirar.
    const pasadas = conPeri ? ['P', 'H', 'G'].filter((k) => leerMacro({
        vista: 'falta', hay: llevas[k], objetivo: conPeri[k],
    }).color === 'pasado') : [];

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

    // SI LA DIETA DEL DÍA NO LLEGA A SUS MACROS, QUE SE VEA (revisión del 2-09, y el aviso
    // entero con el doc «Cómo abre Inicio» del 3-09).
    //
    // EL MARGEN ES EL DE LA CASA. Aquí vivía un 5 a pelo mientras el resto de la app daba
    // un macro por bueno con 4 («de 1 a 4, falte o sobre, es válido», punto 11.1, plano en
    // todo desde el 3-09): con 4,5 de desvío el punto no salía y la comida sí decía que no
    // cuadraba. Ahora sale de `lib/exceso`, como en todas partes.
    const desvioDeLaDieta = conPeri && dieta?.exists
        ? { P: (totalDieta.P || 0) - (conPeri.P || 0),
            H: (totalDieta.H || 0) - (conPeri.H || 0),
            G: (totalDieta.G || 0) - (conPeri.G || 0) }
        : null;
    const fueraDeMargen = desvioDeLaDieta
        ? ['P', 'H', 'G'].filter((k) => Math.abs(desvioDeLaDieta[k]) > MARGEN) : [];
    const dietaNoCuadra = fueraDeMargen.length > 0;

    // LO QUE LE PASA A LA DIETA, DICHO COMO EN SU MAQUETA: «Te faltan 12 g de hidratos por
    // meter». Su documento solo dibuja el caso de faltar, pero el aviso salta igual cuando
    // el día creado SE PASA, y ahí «te faltan» sería mentira: se dice cada cosa por su
    // nombre y, si se dan las dos, las dos.
    //
    // EL NÚMERO SALE DE LOS NÚMEROS QUE ÉL LEE, no del desvío exacto (la regla del punto 80,
    // la misma que ya cumple `leerMacro`). Con 193,4 de 200,9 el desvío exacto redondea a 8
    // y debajo pone «faltan 7»: el aviso diría un número distinto del que tiene justo
    // debajo, que es exactamente lo que este aviso viene a evitar. Se resta lo pintado.
    const desvioQueSeVe = desvioDeLaDieta
        ? Object.fromEntries(['P', 'H', 'G'].map((k) =>
            [k, Math.round(totalDieta[k] || 0) - Math.round(conPeri[k] || 0)]))
        : null;
    const enPalabras = (claves) => claves
        .map((k) => `${num0(Math.abs(desvioQueSeVe[k]))} g de ${NOMBRE_LLANO[k]}`)
        .reduce((a, t, i, l) => (i === 0 ? t : i === l.length - 1 ? `${a} y ${t}` : `${a}, ${t}`), '');
    const loQueFalta = fueraDeMargen.filter((k) => desvioDeLaDieta[k] < 0);
    const loQueSobra = fueraDeMargen.filter((k) => desvioDeLaDieta[k] > 0);
    const avisoDeLaDieta = !dietaNoCuadra ? null
        : loQueFalta.length && loQueSobra.length
            ? `Te faltan ${enPalabras(loQueFalta)} por meter, y te pasas ${enPalabras(loQueSobra)}`
            : loQueFalta.length
                ? `Te faltan ${enPalabras(loQueFalta)} por meter`
                : `Te pasas ${enPalabras(loQueSobra)}`;

    // LA «×» LO QUITA POR HOY, NO PARA SIEMPRE (bloque 03 del doc): «mañana es otra dieta,
    // y si tampoco llega, vuelve». Por eso la marca lleva la fecha. Y el punto de la
    // pestaña NO se va con ella: la señal no desaparece, baja de volumen.
    const [avisoQuitado, setAvisoQuitado] = useState(false);
    useEffect(() => {
        setAvisoQuitado(leerLocal(`inicio-aviso-dieta-${fecha}`, userId) === '1');
    }, [fecha, userId]);
    const quitarAviso = () => {
        escribirLocal(`inicio-aviso-dieta-${fecha}`, userId, '1');
        setAvisoQuitado(true);
    };

    // «TERMINARLA», NO «VERLO» (bloque 03): «Verlo te enseña el problema; Terminarla te
    // lleva a arreglarlo». Y lleva a la comida donde falta, que es la primera del día cuyo
    // montaje no llega a su objetivo. Arreglar una dieta se hace en Nutrición: en Inicio
    // las filas son casillas para marcar lo comido, no la cocina. Si no se puede señalar
    // ninguna -- el día no tiene reparto todavía --, se va a Nutrición sin más.
    const comidaDondeFalta = useMemo(() => {
        const objetivos = reparto?.comidas || {};
        const corta = claves.find((k) => {
            const o = objetivos[k];
            const m = montadoPorComida[k];
            if (!o || !m) return false;
            return ['P', 'H', 'G'].some((x) => (o[x] || 0) - (m[x] || 0) > MARGEN);
        });
        return corta || null;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [claves.join(','), reparto, montadoPorComida]);

    // El contador de Llevas: las comidas por un lado y el peri por otro (punto 93).
    const contadorDeLlevas = contarLoMarcado(
        hechas.filter((f) => !f.esPeri).length,
        hechas.filter((f) => f.esPeri).map((f) => f.clave));

    // EL PIE DE FALTA CAMBIA CUANDO EL DÍA ESTÁ HECHO: los tres ceros en verde son el final
    // del día, y el pie lo dice en vez de seguir pidiendo lo que ya no queda.
    const diaCuadrado = Boolean(conPeri) && ['P', 'H', 'G'].every((k) => leerMacro({
        vista: 'falta', hay: llevas[k], objetivo: conPeri[k],
    }).color === 'ok');
    const pieDeFalta = diaCuadrado ? 'Día cuadrado. Mañana seguimos.' : PIE_DE_VISTA.falta;

    // CADA COMIDA ATERRIZA EN LA SUYA, no solo el peri.
    //
    // Esto nació en el P32 del 23-08 para el peri: «pinchar su tarjeta te dejaba en la cocina
    // con la Comida 1 delante, como si el peri no fuera contigo». Y se quedó ahí: las comidas
    // normales seguían yendo a Nutrición a secas, o sea a la Comida 1, dijeras la que dijeras.
    // Lo cazó Gonzalo probando en pantalla: «entran en el día, no entran en la comida».
    //
    // El destino ya sabía recibirlo (`?comida=C1..C4|Intra|Post` en NutritionPage); lo único
    // que faltaba era decirle cuál.
    const irALaComida = (clave) => navigate(`/dashboard/nutrition?comida=${clave}`);

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
                                onClick={() => elegirVista(v.id)} data-testid={`vista-${v.id}`}
                                /* `min-w-0` para que las 4 columnas sean de verdad iguales: sin él,
                                   la celda no baja del ancho de su texto y «Macros» ensancha su
                                   columna y su pastilla invadía la de «Dieta» en pantalla estrecha.
                                   Poco padding para que los labels quepan enteros sin cortarse. */
                                className={`min-w-0 px-1 py-1.5 rounded-lg text-xs sm:text-sm font-semibold text-center transition-colors
                                    ${vista === v.id ? 'bg-brand text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}>
                                {v.label}
                                {/* El punto avisa de que la dieta del día no llega a sus
                                    macros, sin sacarle de la pestaña en la que entra.

                                    EN ROJO, NO EN NARANJA (doc del 3-09, bloque 02): «que se
                                    vea a la primera; el naranja se pierde contra el fondo del
                                    selector». Y el rojo está FUERA de la regla de colores a
                                    propósito, como el aviso: verde es cuadrado, naranja es
                                    pasarse, sin color es ir por debajo, y que la dieta esté
                                    sin terminar no es ninguna de las tres.
                                    Sobre la pestaña encendida sigue yendo en blanco: ahí el
                                    fondo ya es el naranja de la casa y el rojo no se leería. */}
                                {v.id === 'dieta' && dietaNoCuadra && (
                                    <span data-testid="dieta-no-cuadra"
                                        className={`inline-block w-1.5 h-1.5 rounded-full ml-1 align-middle
                                            ${vista === v.id ? 'bg-white' : 'bg-red-500'}`} />
                                )}
                            </button>
                        ))}
                    </div>

                    {/* EL AVISO DE LA DIETA SIN TERMINAR, DENTRO DE DIETA (doc «Cómo abre
                        Inicio», 3-09, bloques 01 y 03).
                        Antes esto era una línea suelta encima de los números y en TODAS las
                        pestañas, y salió el 2-09 por chocar: en Llevas decía «faltan 12» y
                        justo debajo había un 107 que era otra cosa. Aquí no choca: ese 12 es
                        EL MISMO que se ve debajo, porque los dos miran lo creado contra el
                        objetivo.
                        El rojo es a propósito: la regla de colores dice verde cuadrado,
                        naranja pasarse y sin color ir por debajo, y esto no es ninguna de las
                        tres -- no es un estado de la dieta, es algo que está sin terminar.
                        Otro color, otra cosa. */}
                    {vista === 'dieta' && dietaNoCuadra && !avisoQuitado && (
                        /* EN DOS FILAS EN EL TELÉFONO. Su maqueta lo dibuja todo en una línea
                           porque nombra UN macro; con los tres fuera de sitio -- un día a
                           medio montar -- la frase se partía en cinco renglones de tres
                           palabras contra el botón. Aquí el texto se lleva su ancho y el
                           botón baja; a partir de `sm` vuelve a la línea de su maqueta. */
                        /* EL AIRE, QUE NO LO TENÍA (Francisco, 3-09, con la captura delante).
                           Iba pegado al selector, sin un solo píxel entre medias, y de lejos
                           se leía como una quinta pestaña en vez de como un aviso. Y la «×»
                           tocaba el borde de la tarjeta.
                           Ahora: separación arriba, más alto de caja, y las dos cosas que se
                           tocan -- el botón y la «×» -- agrupadas a la derecha con su hueco,
                           sin que ninguna llegue al filo. */
                        <div data-testid="aviso-dieta"
                            className="mt-3 mb-3 rounded-xl border border-red-500/50 bg-red-500/[0.13]
                                       px-3.5 py-3 flex flex-col sm:flex-row sm:items-center gap-2.5 sm:gap-3">
                            <div className="flex items-start gap-2.5 flex-1 min-w-0">
                                <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                                <p className="flex-1 min-w-0 text-sm text-foreground leading-snug">{avisoDeLaDieta}</p>
                                {/* La «×» con su hueco de dedo y con nombre, que un aspa a
                                    secas no se anuncia. En el teléfono va arriba, junto al
                                    texto: abajo quedaría lejos de lo que cierra. */}
                                <button onClick={quitarAviso} data-testid="cerrar-aviso-dieta"
                                    aria-label="Quitar el aviso por hoy" title="Quitar el aviso por hoy"
                                    className="flex-shrink-0 p-1.5 -mt-1 -mr-1 sm:hidden text-muted-foreground hover:text-foreground transition-colors">
                                    <X className="w-4 h-4" />
                                </button>
                            </div>
                            <div className="flex items-center gap-1.5 self-start sm:self-auto flex-shrink-0">
                                <button
                                    onClick={() => navigate(comidaDondeFalta
                                        ? `/dashboard/nutrition?comida=${comidaDondeFalta}`
                                        : '/dashboard/nutrition')}
                                    data-testid="terminar-dieta"
                                    className="rounded-full bg-red-500 hover:bg-red-600 text-white
                                               text-xs font-bold px-3.5 py-2 transition-colors">
                                    Terminarla
                                </button>
                                <button onClick={quitarAviso} data-testid="cerrar-aviso-dieta-ancho"
                                    aria-label="Quitar el aviso por hoy" title="Quitar el aviso por hoy"
                                    className="hidden sm:block p-1.5 rounded-lg text-muted-foreground
                                               hover:text-foreground hover:bg-red-500/10 transition-colors">
                                    <X className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    )}

                    {vista === 'llevas' && nadaMarcado ? (
                        /* Sin nada marcado, Llevas no es un 0 en rojo: se dice y ya está. */
                        <p className="text-center text-sm py-8" data-testid="llevas-vacio">
                            <span className="text-foreground font-semibold">Todavía no has marcado nada.</span>
                            <br />
                            {/* «Lo que VAYAS comiendo» (punto 94), no «lo que ya te has
                                comido»: lo de arriba mira atrás y esto mira al resto del día,
                                que es lo que le queda por hacer. */}
                            <span className="text-muted-foreground">Marca abajo lo que vayas comiendo.</span>
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
                                                {llevaPunto(lectura.color) && (
                                                    <span data-testid={`punto-${vista}-${k}`}
                                                        className={`w-1.5 h-1.5 rounded-full ${fondoDelMacro(lectura.color)}`} />
                                                )}
                                            </p>
                                            {/* 44 px, arriba y abajo (punto 172 del 27-08).
                                                Estaban a 34 en el móvil y 40 en el ordenador,
                                                y es en el móvil donde dice que se nota. El
                                                peso lo pone `.numero-grande`. */}
                                            <p className="numero-grande font-data leading-none text-[44px] mt-1.5 text-foreground">
                                                {impreso == null ? '·' : impreso}
                                            </p>
                                            {/* CONTRA QUÉ SE MIDE, y siempre (bloque 06 de su
                                                documento: «250 / de 250 / ya lo tienes»). Va
                                                en gris y por encima del estado: es la
                                                referencia, no el juicio. */}
                                            {lectura.referencia && (
                                                <p data-testid={`de-${vista}-${k}`}
                                                    className="text-xs mt-1 text-muted-foreground">
                                                    {lectura.referencia}
                                                </p>
                                            )}
                                            {lectura.palabra && (
                                                <p data-testid={`palabra-${vista}-${k}`}
                                                    className={`text-xs ${lectura.referencia ? '' : 'mt-1'} ${claseDelMacro(lectura.color)}`}>
                                                    {lectura.palabra}
                                                </p>
                                            )}
                                            {/* La barra, en las cuatro menos en Macros: allí no
                                                hay nada que recorrer. */}
                                            {lectura.barra && (
                                                <div className="h-1 rounded-full bg-muted mt-1.5 overflow-hidden">
                                                    <div data-testid={`barra-${vista}-${k}`}
                                                        className={`h-full rounded-full ${fondoDelMacro(lectura.barra.color)}`}
                                                        style={{ width: `${lectura.barra.largo}%` }} />
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                            {/* LA LÍNEA DE AVISO, que es donde vive el ÚNICO decimal de todo
                                el Inicio (punto 80): «el decimal exacto sólo aparece en la
                                línea de aviso: Te has pasado 13,7 g de hidratos».

                                Ojo con confundirla con la del punto 90, que es otra: aquella
                                era la línea de ARRIBA, la que iba encima de los números, y
                                esa sí se fue -- era el rótulo del perientreno, y lo sustituyó
                                el interruptor. Ésta va debajo y se queda. */}
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
                                /* Solo las comidas y el peri: los extras no se nombran aquí
                                   porque no entran en la cuenta, y verlos al lado del número
                                   sería volver a prometer que suman. */
                                <p className="text-xs text-muted-foreground text-center mt-3"
                                    data-testid="contador-llevas">
                                    {contadorDeLlevas}
                                </p>
                            ) : PIE_DE_VISTA[vista] ? (
                                <p className="text-xs text-muted-foreground text-center mt-3"
                                    data-testid={`pie-${vista}`}>
                                    {vista === 'falta' ? pieDeFalta : PIE_DE_VISTA[vista]}
                                </p>
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
                {/* SOBRE LA MARCHA, NO POR LA NOCHE (punto 171 del 27-08). Ponía «Marca lo
                    que ya te has comido», que mira al pasado, y dentro de la pestaña Llevas
                    ya pone «Marca abajo lo que vayas comiendo». Eran las dos mitades de la
                    misma pantalla diciendo cosas distintas. Manda la de dentro. */}
                <p className="caption">Marca lo que te vayas comiendo</p>

                {/* Las hechas, contraídas en una fila: la lista queda para lo que falta
                    por comer. El «Ver» las despliega (y ahí se pueden desmarcar). */}
                {hechas.length > 0 && (
                    <div className="surface p-3.5 sm:p-4 flex items-center justify-between gap-3"
                        data-testid="resumen-hechas">
                        {/* QUÉ LLEVAS, NO SOLO CUÁNTAS (bloque 07 del doc del 3-09): «3 hechas
                            151P · 107H · 49G». Ponía «3 hechas · ocultas», y para saber qué
                            llevaba había que pulsar «Ver». Los macros son los mismos que suma
                            la pestaña Llevas, así que la línea no puede decir otra cosa que
                            el número de arriba.
                            El «· ocultas» se va: lo dice ya el botón, que pone «Ver». */}
                        <p className="text-sm text-muted-foreground">
                            <span className="font-bold text-foreground">
                                {hechas.length === 1 ? '1 hecha' : `${hechas.length} hechas`}
                            </span>
                            {' '}{num0(llevas.P)}P · {num0(llevas.H)}H · {num0(llevas.G)}G
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
                        // EL BORDE NARANJA DEL PERI SE QUEDA EN EL CONTENEDOR. Esta fila era
                        // un solo botón y llevaba el `border-l-4` puesto en él; al partirla
                        // en dos para meter la casilla de marcar (punto 96), el borde se
                        // quedó dentro del trozo que se pulsa y dejó de verse. Es lo único
                        // que distingue de un vistazo el intra y el post de las comidas.
                        // LA TARJETA YA NO ES LA FILA: dentro van la fila (casilla, nombre,
                        // macros y flecha) y, debajo, la línea del suplemento, que lleva a otro
                        // sitio y necesita ser su propio botón (punto 190). Por eso el `flex`
                        // baja un nivel y aquí queda sólo la caja.
                        // Y LA MARCA DEL PERI SE VUELVE PALABRA CUANDO LE TOCA (bloque 07).
                        // La barra de la izquierda y el chip son LA MISMA marca en dos
                        // momentos, así que no se pintan a la vez: mientras no le toca, la
                        // barra; cuando le toca, el chip «Ahora» y el borde entero, que es
                        // como lo dibuja su maqueta. El chip va solapando el borde de arriba,
                        // y por eso la caja necesita `relative`.
                        <div key={k} data-testid={`comida-hoy-${k}`}
                            className={`surface p-3.5 sm:p-4 transition-opacity relative
                                ${esPeri && k !== laDeAhora ? 'border-l-4 border-l-brand' : ''}
                                ${k === laDeAhora ? 'border border-brand' : ''}
                                ${marcada ? 'opacity-55' : ''}`}>
                            {k === laDeAhora && (
                                <span data-testid={`ahora-${k}`}
                                    className="absolute -top-2 left-3 rounded-full bg-brand px-2 py-0.5
                                               text-[10px] font-bold uppercase tracking-wide text-white">
                                    Ahora
                                </span>
                            )}
                            <div className="flex items-center gap-3">
                            {/* La casilla. Persistencia: ver el comentario de cabecera. */}
                            <button onClick={() => marcar(k)} role="checkbox" aria-checked={marcada}
                                aria-label={`${nombre}: ${marcada ? 'ya marcado' : 'marcar como tomado'}`}
                                data-testid={`marcar-${k}`} className="flex-shrink-0 p-1 -m-1">
                                {marcada
                                    ? <CheckCircle2 className="w-6 h-6 text-ok" />
                                    : <Circle className="w-6 h-6 text-muted-foreground" />}
                            </button>
                            <button onClick={() => irALaComida(k)}
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
                                                ? (esPeri ? lineaObjetivo(objetivoFila, true)
                                                    : `Sin hacer · objetivo ${lineaObjetivo(objetivoFila)}`)
                                                : 'Sin hacer'}
                                    </p>
                                </div>
                                <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-brand transition-colors flex-shrink-0" />
                            </button>
                            </div>

                            {/* «+ Creatina» DEBAJO DE LOS MACROS (punto 174), Y SE PUEDE TOCAR
                                (punto 190 del 27-08). «Desde Inicio no se llega a Suplementos,
                                y es donde el cliente está cada día. Con el + Creatina debajo de
                                la comida 3 ya hay por dónde: tocando ahí.»

                                Por eso sale FUERA del botón de la fila y no dentro: la fila
                                lleva a Nutrición y esto lleva a Suplementos, y un botón dentro
                                de otro botón ni es HTML válido ni deja elegir destino.
                                El margen de la izquierda lo alinea con el texto de arriba, por
                                debajo de la casilla de marcar.

                                Sólo el nombre; la dosis vive en su pantalla. Y el intra y el
                                post no entran nunca: ver `suplementosPorComida`.

                                EN GRIS Y CON SU FLECHA (punto 202 del 28-08). Iba en el naranja
                                de la marca, que por la regla del 76 es correcto -- es el color de
                                lo que se toca --, pero lo gastaba en lo que menos corre: en una
                                lista donde también hay «sobran 6,5 de hidratos», lo primero que
                                se ve no puede ser la creatina. La › dice que lleva a otro sitio
                                sin gastar color. */}
                            {!esPeri && (supPorComida[k] || []).length > 0 && (
                                <button onClick={() => navigate('/dashboard/supplements')}
                                    data-testid={`suplementos-${k}`}
                                    className="mt-1 ml-9 flex items-center gap-1 text-sm text-muted-foreground text-left hover:text-foreground transition-colors">
                                    + {supPorComida[k].join(' · ')}
                                    <ChevronRight className="w-3.5 h-3.5 flex-shrink-0" />
                                </button>
                            )}
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
