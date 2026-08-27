import React, { useState } from 'react';
import { Trash2 } from 'lucide-react';
import { toast } from 'sonner';
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
 * En el Inicio NO se pliega: allí es el sitio donde se apunta lo del día sobre la marcha, y
 * un toque de más entre «me he comido algo» y apuntarlo es justo donde se pierde la gente.
 * Con algo ya apuntado se abre solo: la lista tiene que verse sin buscarla.
 */
const ExtrasDelDia = ({ api, fecha, extras = [], onAnadido, onQuitado, origen, plegable = false }) => {
    const [texto, setTexto] = useState('');
    const [guardando, setGuardando] = useState(false);
    const [quitando, setQuitando] = useState(null);
    const [abierto, setAbierto] = useState(!plegable);

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

    // Con algo apuntado se abre solo: la lista no se esconde detrás de un botón.
    const desplegado = abierto || extras.length > 0;

    return (
        <section className="space-y-3" data-testid="extras-del-dia">
            {/* El texto de Jesús, literal (punto 30). Se ve SIEMPRE, no solo con la lista
                vacía: es el rótulo del bloque, y con lista llena es cuando más falta hace
                que se entienda que esto es para lo de fuera de la dieta.
                «PREVISTO» (punto 175 del 27-08): decía «algo que no estaba en tu dieta», que
                se lee como una falta. Previsto quita la culpa -- no está prohibido, es que no
                entraba en el plan de hoy -- y así lo apunta en vez de callárselo. */}
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

            <div className={`space-y-2 ${desplegado ? '' : 'hidden'}`}>
                {/* El «a ojo» va DENTRO del campo (punto 31), que es donde lo lee justo
                    cuando va a escribir, y no gasta una línea de la pantalla. Tres filas
                    porque en un móvil de 390 px el gris ocupa tres líneas y con dos se
                    cortaba justo la mitad que importa («pero ponlo todo»). */}
                <Textarea rows={3} value={texto} maxLength={LARGO_MAX}
                    onChange={(ev) => setTexto(ev.target.value)}
                    /* Enter apunta; para partir la línea, Mayúsculas + Enter. Es una línea
                       de lo que se ha comido, no un texto largo. */
                    onKeyDown={(ev) => {
                        if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); apuntar(); }
                    }}
                    placeholder="Con la cantidad aproximada a ojo si no lo pesas, pero ponlo todo."
                    /* El campo no tiene etiqueta encima (el rótulo es el del bloque), así que
                       el nombre para quien lo lee con voz sale de aquí. */
                    aria-label="Apunta un extra del día"
                    /* EL «A OJO» PESA MENOS QUE LA INSTRUCCIÓN (punto 176 del 27-08). Salía
                       casi del mismo tamaño que la frase de arriba y competían: aquélla dice
                       qué es esto, y ésta es ayuda de mientras escribe.
                       Se toca SOLO el `placeholder`, no el texto que teclea: en el móvil un
                       campo por debajo de 16 px hace que el navegador dé un salto de zoom al
                       entrar, y eso vale para lo que se escribe, no para lo que sugiere. */
                    className="rounded-xl bg-muted border-0 resize-none placeholder:text-xs"
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
            </div>
        </section>
    );
};

export default ExtrasDelDia;
