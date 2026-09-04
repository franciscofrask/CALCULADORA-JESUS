import React, { useEffect, useState } from 'react';
import { Search, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { num1 } from '../../lib/numeros';

/**
 * «EXTRAS DEL DÍA» (apartado 5 del doc del 21-08; rehecho con los puntos 27 a 31 del doc
 * del 24-08).
 *
 * Lo que el cliente se come FUERA de su dieta -- el cumpleaños, el picoteo -- no tenía
 * dónde apuntarse: o lo metía en una comida (y descuadraba el reparto) o no lo contaba
 * (y la app creía que iba perfecto).
 *
 * UN CAMPO DE TEXTO Y YA. Hasta el 24-08 esto eran cuatro pasos: botón, ventana, buscar en
 * el catálogo y gramos. Un extra es por definición lo que NO estaba en la dieta -- el
 * pincho del bar, la tarta del cumpleaños --, justo lo que no va a encontrar en el
 * catálogo, y si no lo encuentra no lo apunta. El dato lo confirmó: con esto vivo desde el
 * 21-08 y 198 clientes, en toda la base de producción había UN solo extra apuntado. Ahora
 * escribe «Dos cañas y un pincho de tortilla» y sigue con su día.
 *
 * NO TOCAN LA DIETA NI «LLEVAS» (punto 28). Antes se sumaban en Llevas y eso le encogía el
 * Falta: si se comía una tarta a media tarde, la app le decía que ya no se comiera la
 * comida 4. Eso es enseñarle a compensar. Van en su lista, aparte, y no mueven ni un
 * número de la dieta.
 *
 * El dato vive en el servidor (`extras` en el documento del día): POST /diets/{fecha}/extras
 * con `{texto}`, DELETE para quitarlo. El estado lo lleva el padre (TuDietaHoy o
 * NutritionPage), que avisa con `onAnadido` / `onQuitado`; aquí no se guarda copia propia.
 * Los extras viejos, los del catálogo, siguen llegando con macros y se pintan como antes.
 *
 * `origen` dice por dónde entró el extra (`inicio`, `nutricion` o `checkin`) y lo guarda el
 * servidor. Lo pone EL PADRE y no tiene valor por defecto a propósito: este bloque se monta
 * en dos sitios -- el Inicio y Nutrición --, y si se dejara fijo aquí lo apuntado desde
 * Nutrición se contaría como del Inicio. Un origen que no consta se arregla mirando; uno
 * falseado no se nota nunca.
 */

// Lo que cabe en un extra. El servidor corta en el mismo número (`_LARGO_MAX_EXTRA`), y
// aquí se avisa antes de que el campo deje de responder sin decir nada.
const LARGO_MAX = 300;

const lineaMacros = (m) => ['P', 'H', 'G']
    .filter((k) => (m?.[k] || 0) > 0)
    .map((k) => `${num1(m[k])}${k}`)
    .join(' · ');

// El detalle de los extras VIEJOS, los del catálogo: «126 g · 9,3P · 17H · 4,8G». Los
// nuevos son texto libre y no tienen ni cantidad ni macros que enseñar.
const detalleDelExtra = (e) => [
    e.cantidad_texto || (e.cantidad_g ? `${num1(e.cantidad_g)} g` : null),
    lineaMacros(e.macros) || null,
].filter(Boolean).join(' · ');

/**
 * `plegable`: el bloque nace cerrado y se abre con el «+» (maqueta de la parte 6, en
 * Nutrición). Ahí abajo es lo último de una pantalla larga y con la caja de escribir abierta
 * se lleva media pantalla para algo que la mayoría de los días no se usa: la frase se queda
 * -- que es lo que dice para qué sirve -- y el campo aparece cuando se va a escribir.
 *
 * SE PLIEGA EN LOS TRES SITIOS (Francisco, 2-09). Antes `plegable` venía en `false` y no lo
 * pasaba nadie, así que el buscador y la caja de escribir salían de entrada en Inicio, en
 * Nutrición y en el panel del día: media pantalla ocupada por un formulario para algo que la
 * mayoría de los días no se usa. Ahora el bloque nace cerrado en todas partes y lo abre el
 * «+», que es lo que él pidió: «tiene que ser un botón de más y ahí mostrar el buscador».
 *
 * Aquí había escrita la decisión contraria («en el Inicio NO se pliega, un toque de más entre
 * me he comido algo y apuntarlo es justo donde se pierde la gente»). La cambió él.
 *
 * LO APUNTADO SE VE SIEMPRE, esté abierto o cerrado: la lista es el registro y va fuera del
 * bloque que se pliega. Lo que se esconde es el formulario, no lo que ya se anotó. Por eso
 * `desplegado` es solo `abierto` y ya no se abre solo por tener extras: con algo apuntado se
 * abría entero otra vez y volvía el formulario a la pantalla.
 */
//: Los que se cuentan por piezas: ahí la cantidad son unidades y no gramos.
const esPorUnidad = (food) => Boolean(food?.por_unidad ?? food?.unidades);

const ExtrasDelDia = ({ api, fecha, extras = [], onAnadido, onQuitado, origen, plegable = true }) => {
    const [texto, setTexto] = useState('');
    const [guardando, setGuardando] = useState(false);
    const [quitando, setQuitando] = useState(null);
    const [abierto, setAbierto] = useState(!plegable);
    // ── El buscador, que vuelve (punto 1.2 del documento del 1-09) ───────────
    const [query, setQuery] = useState('');
    const [resultados, setResultados] = useState([]);
    const [buscando, setBuscando] = useState(false);
    const [elegido, setElegido] = useState(null);
    const [cantidad, setCantidad] = useState('');

    // Con su respiro de 300 ms, como el resto de buscadores de la casa.
    useEffect(() => {
        if (elegido) return undefined;
        const q = query.trim();
        if (q.length < 2) { setResultados([]); setBuscando(false); return undefined; }
        setBuscando(true);
        const t = setTimeout(() => {
            api.get('/calculator/search', { params: { q, limit: 30 } })
                .then((r) => { setResultados(r.data?.alimentos || []); setBuscando(false); })
                .catch((err) => {
                    console.error('[extras] no se pudo buscar en el catálogo', err);
                    setResultados([]); setBuscando(false);
                });
        }, 300);
        return () => clearTimeout(t);
    }, [query, elegido, api]);

    const soltarLaBusqueda = () => {
        setQuery(''); setResultados([]); setElegido(null); setCantidad('');
    };

    const elegir = (food) => {
        setElegido(food);
        // Un arranque razonable que el cliente corrige: 1 unidad, o 100 g.
        setCantidad(esPorUnidad(food) ? '1' : '100');
    };

    const apuntarDelCatalogo = async () => {
        const valor = parseFloat(String(cantidad).replace(',', '.'));
        if (!valor || valor <= 0) { toast.error('Dime cuánto ha sido.'); return; }
        if (guardando) return;
        setGuardando(true);
        try {
            const cuerpo = esPorUnidad(elegido)
                ? { alimento_id: elegido.id, unidades: valor }
                : { alimento_id: elegido.id, cantidad_g: valor };
            const r = await api.post(`/diets/${fecha}/extras`,
                origen ? { ...cuerpo, origen } : cuerpo);
            onAnadido?.(r.data.extra);
            soltarLaBusqueda();
        } catch (err) {
            console.error('[extras] no se pudo apuntar el extra', err);
            toast.error('No se pudo apuntar el extra. Prueba otra vez.');
        } finally {
            setGuardando(false);
        }
    };

    const apuntar = async () => {
        const limpio = texto.trim();
        if (!limpio || guardando) return;
        setGuardando(true);
        try {
            // Sin `origen` no se manda el campo: el servidor lo guarda vacío y se ve que
            // ese sitio todavía no lo dice, en vez de apuntarlo donde no fue.
            const r = await api.post(`/diets/${fecha}/extras`,
                origen ? { texto: limpio, origen } : { texto: limpio });
            onAnadido?.(r.data.extra);
            setTexto('');
        } catch (err) {
            console.error('[extras] no se pudo apuntar el extra', err);
            toast.error('No se pudo apuntar el extra. Prueba otra vez.');
        } finally {
            setGuardando(false);
        }
    };

    const quitar = async (extra) => {
        setQuitando(extra.id);
        try {
            await api.delete(`/diets/${fecha}/extras/${extra.id}`);
            onQuitado?.(extra.id);
        } catch (err) {
            console.error('[extras] no se pudo quitar el extra', err);
            toast.error('No se pudo quitar el extra. Prueba otra vez.');
        } finally {
            setQuitando(null);
        }
    };

    // Solo lo que él abre. La lista de lo apuntado se pinta igual, esté abierto o cerrado
    // (va fuera de este bloque), así que tener extras ya no tiene por qué sacar el formulario.
    const desplegado = abierto;

    // LO QUE LLEVA EN EXTRAS, SUMADO Y APARTE (1-09).
    //
    // Un extra buscado en el catálogo trae sus macros; uno escrito a mano no tiene de dónde
    // sacarlos. Aquí se suman los que los tienen, y se enseñan en su propia línea.
    //
    // APARTE, Y NO DENTRO DE «LLEVAS», a propósito. El documento del 1-09 pide que lo que se
    // busque cuente; el punto 28 del 24-08 pide que los extras no toquen la dieta, y su
    // motivo sigue siendo bueno: sumarlos al día encogía el «Falta» y la app acababa
    // diciéndole que se saltara una comida por haberse comido una tarta. Las dos cosas caben
    // si se separa CONTAR de DESCONTAR: el extra se mide, se ve y viaja al reporte, y lo que
    // te queda de tu dieta no se mueve.
    const enExtras = extras.reduce((acc, e) => ({
        P: acc.P + (e.macros?.P || 0),
        H: acc.H + (e.macros?.H || 0),
        G: acc.G + (e.macros?.G || 0),
    }), { P: 0, H: 0, G: 0 });
    const lineaDeExtras = lineaMacros(enExtras);

    return (
        <section className="space-y-3" data-testid="extras-del-dia">
            {/* El texto de Jesús, literal (punto 30). Se ve SIEMPRE, no solo con la lista
                vacía: es el rótulo del bloque, y con lista llena es cuando más falta hace
                que se entienda que esto es para lo de fuera de la dieta.
                «PREVISTO» (punto 175 del 27-08): decía «algo que no estaba en tu dieta», que
                se lee como una falta. Previsto quita la culpa -- no está prohibido, es que no
                entraba en el plan de hoy -- y así lo apunta en vez de callárselo.

                Este comentario llevaba aquí desde el 27-08 describiendo un cambio que NUNCA
                se hizo: la frase de abajo seguía siendo la vieja. Corregido el 2-09 con el
                texto entero que él escribió en el punto 175, que también cambia el final
                («en cuanto pase» en vez de «por pequeño que sea»). */}
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <p className="caption">Extras del día</p>
                    <p className="text-sm text-muted-foreground mt-1">
                        Si comes algo que no estaba previsto en tu dieta, ponlo aquí en cuanto pase.
                    </p>
                </div>
                {plegable && !desplegado && (
                    <button onClick={() => setAbierto(true)} data-testid="extras-abrir"
                        aria-label="Apuntar un extra del día"
                        className="flex-shrink-0 w-9 h-9 rounded-full border border-border text-brand text-xl font-bold leading-none flex items-center justify-center hover:border-brand/50 transition-colors">
                        +
                    </button>
                )}
            </div>

            {/* Lo apuntado, encima del campo (punto 29). */}
            {extras.map((e) => {
                const detalle = detalleDelExtra(e);
                return (
                    <div key={e.id} data-testid={`extra-${e.id}`}
                        className="surface p-3.5 sm:p-4 flex items-center gap-3">
                        <div className="min-w-0 flex-1">
                            <p className="font-bold text-sm text-foreground">{e.texto || e.nombre}</p>
                            {detalle && (
                                <p className="text-sm text-muted-foreground font-data">{detalle}</p>
                            )}
                        </div>
                        <button onClick={() => quitar(e)} disabled={quitando === e.id}
                            aria-label={`Quitar ${e.texto || e.nombre} de los extras`}
                            data-testid={`quitar-extra-${e.id}`}
                            className="flex-shrink-0 p-2 -m-1 text-muted-foreground hover:text-destructive transition-colors disabled:opacity-40">
                            <Trash2 className="w-5 h-5" />
                        </button>
                    </div>
                );
            })}

            {/* La suma de lo buscado, en su propia línea y con el «además» delante, que es lo
                que dice que va POR ENCIMA de la dieta y no dentro. Sale solo si hay algo que
                sumar: los extras escritos a mano no traen macros, y una línea a cero no
                informa de nada. */}
            {lineaDeExtras && (
                <p className="text-xs text-muted-foreground" data-testid="extras-suma">
                    Además de tu dieta, hoy llevas <span className="font-data text-foreground">{lineaDeExtras}</span> en extras.
                </p>
            )}

            <div className={`space-y-2 ${desplegado ? '' : 'hidden'}`}>
                {/* EL BUSCADOR DELANTE, LA CAJA DETRÁS (punto 1.2 del documento del 1-09).
                    El 24-08 se quitó el catálogo de aquí y quedó solo el texto libre, con un
                    motivo bueno: eran cuatro pasos para apuntar un pincho de tortilla, y en
                    toda la base había UN extra apuntado. Pero el texto libre no cuenta macros
                    -- no hay ficha de la que sacarlos --, así que quien se come algo que SÍ
                    está en el catálogo no tenía forma de que contara.
                    Vuelven los dos, en el orden del documento: primero buscarlo, y si no está,
                    escribirlo. Cada uno dice lo que hace en la frase de abajo. */}
                {!elegido && (
                    <div className="relative">
                        <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                        <Input value={query} onChange={(ev) => setQuery(ev.target.value)}
                            placeholder="Buscar el alimento…"
                            aria-label="Buscar el alimento en el catálogo"
                            className="pl-10 rounded-xl bg-muted border-0"
                            data-testid="extras-buscar" />
                    </div>
                )}

                {/* Los resultados, cortos: es una lista para reconocer lo que se ha comido,
                    no para elegir el mejor encaje de macros (eso es el buscador de la dieta). */}
                {!elegido && query.trim().length >= 2 && (
                    <div className="max-h-56 overflow-y-auto space-y-1" data-testid="extras-resultados">
                        {buscando && <p className="text-xs text-muted-foreground px-1">Buscando…</p>}
                        {!buscando && resultados.length === 0 && (
                            <p className="text-xs text-muted-foreground px-1">
                                Eso no está en el catálogo. Escríbelo aquí abajo.
                            </p>
                        )}
                        {resultados.map((food) => (
                            <button key={food.id} onClick={() => elegir(food)}
                                data-testid={`extras-elegir-${food.id}`}
                                className="w-full text-left rounded-lg border border-border px-3 py-2 hover:border-brand/50 transition-colors">
                                <span className="block text-sm text-foreground">{food.nombre}</span>
                                <span className="block text-xs text-muted-foreground">
                                    por {esPorUnidad(food) ? 'unidad' : '100 g'}
                                </span>
                            </button>
                        ))}
                    </div>
                )}

                {/* Elegido uno, lo único que falta es cuánto. */}
                {elegido && (
                    <div className="surface p-3 space-y-2" data-testid="extras-cuanto">
                        <p className="text-sm font-bold text-foreground">{elegido.nombre}</p>
                        <div className="flex items-center gap-2">
                            <Input type="number" inputMode="decimal" min="0"
                                step={esPorUnidad(elegido) ? '0.5' : '5'}
                                value={cantidad} onChange={(ev) => setCantidad(ev.target.value)}
                                aria-label={esPorUnidad(elegido) ? 'Cuántas unidades' : 'Cuántos gramos'}
                                className="rounded-xl bg-muted border-0"
                                data-testid="extras-cantidad" />
                            <span className="text-sm text-muted-foreground shrink-0">
                                {esPorUnidad(elegido) ? 'ud' : 'g'}
                            </span>
                        </div>
                        <div className="flex gap-2">
                            <button onClick={soltarLaBusqueda} data-testid="extras-otro"
                                className="flex-1 h-11 rounded-xl border border-border text-sm text-muted-foreground">
                                Buscar otro
                            </button>
                            <button onClick={apuntarDelCatalogo} disabled={guardando}
                                data-testid="extras-apuntar-catalogo"
                                className="flex-1 h-11 rounded-xl bg-brand text-white font-bold text-sm disabled:opacity-60">
                                {guardando ? 'Apuntando…' : 'Apuntarlo'}
                            </button>
                        </div>
                    </div>
                )}

                {/* FUERA «o si no está» (Francisco, 2-09), junto con el «a ojo» del campo y
                    la frase de qué cuenta y qué no. Eran tres explicaciones seguidas encima de
                    dos controles que se entienden solos: se busca, o se escribe. */}

                {/* LA CAJA DE ESCRIBIR A MANO VUELVE (Francisco, 5-09: «ese text area tiene que
                    volver»). El 2-09 salió entera («el textarea quítalo, no se va a usar») y
                    tres días después la pidió de vuelta: se restauró tal cual estaba, sin las
                    tres frases, que siguen fuera. Lo que se escribe aquí queda como registro
                    y no cuenta en los macros, igual que antes. */}
                {/* Tres filas porque en un móvil de 390 px el campo con dos se queda corto en
                    cuanto apunta la comida de un domingo entero. */}
                <Textarea rows={3} value={texto} maxLength={LARGO_MAX}
                    onChange={(ev) => setTexto(ev.target.value)}
                    /* Enter apunta; para partir la línea, Mayúsculas + Enter. Es una línea
                       de lo que se ha comido, no un texto largo. */
                    onKeyDown={(ev) => {
                        if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); apuntar(); }
                    }}
                    /* Sin `placeholder`: decía «Escríbelo a mano. En cuanto pase, con la
                       cantidad a ojo si no lo pesas», y sale (Francisco, 2-09). Lo que hay que
                       poner ahí ya lo dice el rótulo del bloque, arriba. */
                    /* El campo no tiene etiqueta encima (el rótulo es el del bloque), así que
                       el nombre para quien lo lee con voz sale de aquí. */
                    aria-label="Apunta un extra del día"
                    className="rounded-xl bg-muted border-0 resize-none"
                    /* `extras-` y no `extra-`: cada fila apuntada es `extra-{id}`, así que
                       un guión que busque `[data-testid^="extra-"]` para contar lo apuntado
                       se llevaría también el campo y la cuenta. */
                    data-testid="extras-campo" />
                {/* La cuenta sale al acercarse al tope. Sin ella el campo se queda mudo de
                    golpe -- deja de aceptar letras y no dice por qué --, y quien está
                    poniendo la comida del domingo entero se cree que se ha colgado. Es un
                    número a secas y no una frase a propósito: los textos que lee el cliente
                    los escribe Jesús, y éste no está en su documento. */}
                {texto.length >= LARGO_MAX - 50 && (
                    <p className="text-xs text-muted-foreground text-right font-data"
                        data-testid="extras-cuenta">
                        {texto.length} / {LARGO_MAX}
                    </p>
                )}
                {/* El botón sale en cuanto escribe: con el campo vacío no pinta nada. */}
                {texto.trim() && (
                    <button onClick={apuntar} disabled={guardando} data-testid="apuntar-extra"
                        className="w-full h-12 rounded-xl bg-brand text-white font-bold text-sm disabled:opacity-60 transition-opacity">
                        {guardando ? 'Apuntando...' : 'Apuntarlo'}
                    </button>
                )}

                {/* Aquí iba «Lo que pongas a mano no cuenta en tus macros, simplemente queda
                    el registro. Lo que busques, sí» (punto 1.2 del 1-09). FUERA por decisión
                    suya del 2-09. Lo que decía sigue siendo verdad y se sigue viendo donde
                    importa: la línea «Además de tu dieta, hoy llevas ... en extras» solo suma
                    lo buscado, porque lo escrito a mano no trae macros de ningún sitio. */}
            </div>
        </section>
    );
};

export default ExtrasDelDia;
