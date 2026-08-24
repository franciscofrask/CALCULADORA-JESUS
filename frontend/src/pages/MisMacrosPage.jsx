/**
 * «MIS MACROS» (punto 6.2 de la revisión del 09-08).
 *
 * La pantalla del cliente al que los macros se los lleva su entrenador. Sustituye a «Ajustar
 * macros» en esos planes: sin quiz, sin calculadora y sin botón de guardar, porque no hay nada
 * que él pueda tocar. Lo que hasta hoy veía era la calculadora capada -- los mismos campos
 * editables, pero sin el botón --, que es la peor de las dos cosas: parece que puedes escribir
 * y no sirve de nada.
 *
 * Los cuatro bloques del documento, y qué aporta cada uno:
 *
 *   HOY            sus números vigentes, con la fecha desde la que aplican.
 *   FEEDBACK       lo que le escribió su entrenador EN ESTE ajuste. La app ya obliga a
 *                  escribirlo en cada cambio y hasta ahora se perdía en el listado de
 *                  novedades; pegado a sus macros es lo que hoy se manda por audio.
 *   TU HISTÓRICO   la escalera de los ajustes anteriores, con lo que cambió marcado en color.
 *                  Es la misma marca que lee el entrenador en su panel, calculada al guardar
 *                  (`cambios`, punto 31), así que los dos ven señalado lo mismo.
 *
 * Quién ve el histórico lo decide el servidor a partir de su plan (TABLA 20): el plan
 * personalizado sí, el plan sin ajuste no. Aquí solo se pinta lo que llega.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SlidersHorizontal, Loader2, Quote, TrendingUp, ClipboardCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { MACRO } from './ClientDashboard';
import HistorialDeMacros, { ultimoAjusteLegible } from '../components/HistorialDeMacros';
import { fraseDeLoQueFalta } from '../lib/datosDudosos';
import { PERI_OPTIONS } from '../components/nutrition/ConfigSection';

const fechaLarga = (iso) => {
    if (!iso) return '';
    return new Date(iso + 'T12:00:00').toLocaleDateString('es-ES', {
        day: 'numeric', month: 'long', year: 'numeric',
    });
};

// Los tres macros de un bloque, en el orden de siempre.
const CAMPOS = [
    { key: 'proteina', corto: 'P', label: 'Proteína', color: MACRO.protein },
    { key: 'hidratos', corto: 'H', label: 'Hidratos', color: MACRO.carbs },
    { key: 'grasa', corto: 'G', label: 'Grasas', color: MACRO.fat },
];

const numero = (v) => (v === null || v === undefined ? '-' : v);

// El bloque grande de la tarjeta de hoy: un macro por columna, con su nombre entero.
const BloqueGrande = ({ macros }) => (
    <div className="grid grid-cols-3 gap-3">
        {CAMPOS.map(c => (
            <div key={c.key}>
                <p className="text-[11px] font-bold uppercase tracking-wider mb-0.5" style={{ color: c.color }}>{c.label}</p>
                <p className="font-data text-2xl font-bold text-foreground leading-none">
                    {numero(macros?.[c.key])}<span className="text-sm font-normal text-muted-foreground ml-0.5">g</span>
                </p>
            </div>
        ))}
    </div>
);

// Los dos bloques pequeños (perientreno y descanso): una línea cada uno.
const BloqueLinea = ({ label, macros, conGrasa = true, destacado = false }) => {
    const campos = conGrasa ? CAMPOS : CAMPOS.slice(0, 2);
    return (
        <div className={`flex items-baseline justify-between gap-3 py-1.5 ${destacado ? 'font-semibold' : ''}`}>
            <span className={`text-sm ${destacado ? 'text-foreground' : 'text-muted-foreground'}`}>{label}</span>
            <span className="font-data text-sm text-foreground whitespace-nowrap">
                {campos.map((c, i) => (
                    <React.Fragment key={c.key}>
                        {i > 0 && <span className="text-muted-foreground mx-1">·</span>}
                        {numero(macros?.[c.key])}<span className="text-[11px] ml-0.5" style={{ color: c.color }}>{c.corto}</span>
                    </React.Fragment>
                ))}
            </span>
        </div>
    );
};

// La tabla del histórico vive en components/HistorialDeMacros, compartida con Evolución.

// EL RÓTULO DEL PERI, CON EL MODO QUE TIENE PUESTO EL CLIENTE (punto 50 del doc 24-08).
//
// Aquí ponía «Perientreno (intra + post)» escrito a fuego, sin mirar su configuración:
// Montalvo tiene «solo post» guardado en su ficha y en sus diez dietas de agosto, así que
// Nutrición le decía «solo post» y esta pantalla «intra + post» el mismo día. Los gramos
// no se tocan, solo el nombre.
//
// Las etiquetas son las del desplegable donde él lo elige (PERI_OPTIONS de ConfigSection),
// que es la misma lista que usa la línea de configuración de Nutrición: así la misma cosa
// se llama igual en las dos pantallas. Ojo, que hay OTRA lista `PERI_OPTIONS` en
// components/nutrition/constants.js, con «Sin periworkout» y sin que la importe nadie:
// renombrar ahí no cambia ni esta pantalla ni Nutrición.
export const rotuloDelPeri = (opcionPeri) => {
    // «Sin perientreno» no es un matiz del rótulo, es lo contrario: ahí el bloque se
    // queda en «Perientreno» a secas. Y sin saber su modo tampoco se inventa uno: mejor
    // no decirlo que decir el que no es, que es justo lo que pasaba. Sin modo se está
    // solo mientras carga o si la consulta falla: al que no ha elegido nunca, el
    // servidor le contesta `intra_post`, el mismo que da por bueno Nutrición.
    if (!opcionPeri || opcionPeri === 'sin_peri') return 'Perientreno';
    const etiqueta = PERI_OPTIONS.find(o => o.value === opcionPeri)?.label;
    return etiqueta ? `Perientreno (${etiqueta.toLowerCase()})` : 'Perientreno';
};

// De dónde sale ese modo. NO de `profile`: el modelo con el que el servidor sirve
// /clients/profile (ClientProfile) no lleva `diet_opcion_peri`, así que en el front
// siempre llegaba undefined. Se pide a /user/diet-config, que es de donde ya lo sacan
// Inicio (TuDietaHoy) y el chat cuando el día no está montado.
//
// El de la FICHA, que es su última elección: Nutrición lo guarda ahí cada vez que toca el
// desplegable. Un día concreto puede tener guardado otro (el que había cuando se montó) y
// eso es lo que enseña Nutrición en ESE día; aquí no se habla de un día, se habla de sus
// macros, así que manda lo que el cliente lleva puesto.
export const useOpcionPeri = () => {
    const { api } = useAuth();
    const [opcionPeri, setOpcionPeri] = useState(null);
    useEffect(() => {
        let vivo = true;
        api.get('/user/diet-config')
            .then(r => { if (vivo) setOpcionPeri(r.data?.opcion_peri || null); })
            // Sin esto la pantalla se pinta igual, con el rótulo corto: el porqué, a la consola.
            .catch(e => console.error('No se pudo leer la configuración del perientreno', e));
        return () => { vivo = false; };
    }, [api]);
    return opcionPeri;
};

const MisMacrosPage = ({ onAjustar }) => {
    const { api, profile } = useAuth();
    const navigate = useNavigate();
    const [datos, setDatos] = useState(null);
    const [cargando, setCargando] = useState(true);
    // Datos del perfil faltantes o imposibles (tarea 1.4): lo calcula el servidor al leer
    // el perfil. Con la lista llena, los números se rotulan «Provisionales» y se empuja a
    // la pantalla de completar datos que ya existe (?completar=1), que solo rellena huecos.
    const datosDudosos = profile?.datos_dudosos || [];
    // La ventana del botón Revisar: {abierta, se_abre, motivo}, del servidor (tarea 7.3).
    const ventana = profile?.ventana_revision;
    // Su perientreno, para rotular el bloque con el que de verdad lleva (punto 50, 24-08).
    const opcionPeri = useOpcionPeri();

    useEffect(() => {
        let vivo = true;
        api.get('/macros/historial')
            .then(res => { if (vivo) setDatos(res.data); })
            .catch(() => { if (vivo) setDatos(null); })
            .finally(() => { if (vivo) setCargando(false); });
        return () => { vivo = false; };
    }, [api]);

    const vigente = datos?.vigente;
    const entradas = datos?.entradas || [];
    const entrenaHoy = datos?.tipo_dia_hoy === 'entrenamiento';
    const descansaHoy = datos?.tipo_dia_hoy === 'descanso';
    // «Último ajuste: −20 g de hidratos en entreno...» (la cabecera del doc 19-08).
    const ultimoAjuste = ultimoAjusteLegible(entradas);

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[900px] mx-auto space-y-6 animate-fade-in">
            <header className="flex items-start gap-3 flex-wrap">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-brand/10">
                    <SlidersHorizontal className="w-6 h-6 text-brand" />
                </div>
                <div className="flex-1 min-w-[220px]">
                    <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none" data-testid="macros-heading">
                        Mis macros
                    </h1>
                    {/* LA CABECERA DEL DOC 19-08: la última revisión y la próxima, y qué se
                        movió la última vez, en una frase que se lee. Desde la tarea 7.3
                        del 21-08 la pantalla vuelve a ser DE TODOS los planes: el de
                        autogestión con sus botones y el de coach en solo lectura (sin
                        `onAjustar`, con el Revisar según su ciclo). */}
                    {(datos?.ultima_revision || datos?.proxima_revision) && (
                        <p className="text-sm text-muted-foreground mt-1" data-testid="macros-revisiones">
                            {datos?.ultima_revision && `Última revisión: ${fechaLarga(datos.ultima_revision)}`}
                            {datos?.ultima_revision && datos?.proxima_revision && ' · '}
                            {datos?.proxima_revision && `Próxima: ${fechaLarga(datos.proxima_revision)}`}
                        </p>
                    )}
                    {ultimoAjuste && (
                        <p className="text-sm text-muted-foreground" data-testid="macros-ultimo-ajuste">
                            Último ajuste: {ultimoAjuste}
                        </p>
                    )}
                </div>
                {/* Los otros dos bloques de la tarea 7.3, como botones de cabecera:
                    CAMBIARLOS TÚ (solo autogestión: `onAjustar` llega únicamente cuando
                    macros_ajustables.puede lo permite) y el botón REVISAR de abajo. */}
                <div className="flex flex-col items-end gap-2">
                    {onAjustar && (
                        <button type="button" onClick={onAjustar} data-testid="ajustar-mis-macros"
                            className="px-4 py-2 rounded-full bg-brand text-white text-sm font-bold hover:opacity-90">
                            Ajustar mis macros
                        </button>
                    )}
                    {/* EL BOTÓN REVISAR (tarea 7.3): el cuestionario de ajuste se enciende
                        cuando toca -- una vez al mes en autogestión, en su semana de ciclo
                        con coach -- y se apaga cuando no. Lo decide el servidor
                        (ventana_revision, core/ventana_revision.py). Apagado se queda
                        VISIBLE en gris y dice cuándo se abre: un botón gris informa, uno
                        que no está no. El cliente no pide nada: la app le abre la ventana. */}
                    {ventana && (ventana.abierta ? (
                        <button type="button" data-testid="boton-revisar"
                            onClick={() => navigate('/questionnaire?ajustar=1')}
                            className="px-4 py-2 rounded-full border border-brand text-brand text-sm font-bold hover:bg-brand/10 inline-flex items-center gap-2">
                            <ClipboardCheck className="w-4 h-4" /> Revisar mis macros
                        </button>
                    ) : (
                        <div className="text-right">
                            <button type="button" disabled data-testid="boton-revisar"
                                className="px-4 py-2 rounded-full border border-border bg-muted text-muted-foreground text-sm font-bold cursor-not-allowed inline-flex items-center gap-2">
                                <ClipboardCheck className="w-4 h-4" /> Revisar mis macros
                            </button>
                            <p className="text-[11px] text-muted-foreground mt-1" data-testid="revisar-cuando">
                                {ventana.se_abre
                                    ? `Se abre el ${fechaLarga(ventana.se_abre)}`
                                    : ventana.motivo}
                            </p>
                        </div>
                    ))}
                </div>
            </header>

            {cargando ? (
                <div className="flex justify-center py-16"><Loader2 className="w-7 h-7 animate-spin text-muted-foreground" /></div>
            ) : (
                <>
                    {/* ── HOY ── */}
                    <section className="surface p-5 space-y-3" data-testid="mis-macros-hoy">
                        <div className="flex items-baseline justify-between gap-2 flex-wrap">
                            <p className="caption flex items-center gap-2">
                                Hoy{entrenaHoy ? ' · Entreno' : descansaHoy ? ' · Descanso' : ''}
                                {/* Rótulo discreto, no un aviso: los números siguen siendo
                                    los suyos, solo que se calcularon con huecos en el perfil. */}
                                {datosDudosos.length > 0 && (
                                    <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-bold uppercase tracking-wide"
                                        data-testid="rotulo-provisionales">
                                        Provisionales
                                    </span>
                                )}
                            </p>
                            {vigente?.fecha && (
                                <p className="text-xs text-muted-foreground" data-testid="mis-macros-vigentes-desde">
                                    Vigentes desde el {fechaLarga(vigente.fecha)}
                                </p>
                            )}
                        </div>
                        {datosDudosos.length > 0 && (
                            <p className="text-xs text-amber-600 dark:text-amber-400 -mt-1" data-testid="macros-provisionales">
                                {fraseDeLoQueFalta(datosDudosos)}{' '}
                                <button type="button" onClick={() => navigate('/questionnaire?completar=1')}
                                    className="underline font-semibold">
                                    Completar mis datos
                                </button>
                            </p>
                        )}

                        {vigente ? (<>
                            {/* El bloque grande es el del día que le toca hoy si lo sabemos, y el de
                                entreno si no: es el que se mira más veces. */}
                            <BloqueGrande macros={descansaHoy ? vigente.descanso : vigente.entreno} />
                            <p className="text-[11px] text-muted-foreground -mt-1">
                                {descansaHoy ? 'Día de descanso' : 'Día de entrenamiento'}
                            </p>
                            <div className="border-t border-border pt-1">
                                {/* El perientreno solo si lo tiene: una línea de guiones no dice
                                    «no llevas intra», dice «esto está roto». */}
                                {vigente.peri && <BloqueLinea label={rotuloDelPeri(opcionPeri)} macros={vigente.peri} conGrasa={false} />}
                                <BloqueLinea label={descansaHoy ? 'Día de entrenamiento' : 'Día de descanso'}
                                    macros={descansaHoy ? vigente.entreno : vigente.descanso} />
                            </div>
                        </>) : (
                            <p className="text-sm text-muted-foreground">
                                Todavía no tienes ningún ajuste guardado. En cuanto te pongamos
                                los primeros, los verás aquí.
                            </p>
                        )}
                    </section>

                    {/* ── LO QUE TE DIJO TU ENTRENADOR EN ESTE AJUSTE ──
                        Solo si lo escribió: un recuadro vacío con ese título le diría que su
                        entrenador no le dijo nada, y lo que pasa es que no todos los ajustes
                        llevan mensaje. */}
                    {vigente?.feedback && (
                        <section className="surface p-5 border-l-4 border-l-brand" data-testid="mis-macros-feedback">
                            <p className="caption mb-2 flex items-center gap-2">
                                <Quote className="w-3.5 h-3.5" /> Lo que te dijimos en este ajuste
                            </p>
                            <p className="text-foreground leading-relaxed">«{vigente.feedback}»</p>
                        </section>
                    )}

                    {/* ── TU HISTÓRICO ── El componente compartido con Evolución: la misma
                        tabla se pinta aquí para quien tiene la pestaña, y en Seguimiento
                        para quien no (doc 19-08). */}
                    <HistorialDeMacros entradas={entradas} />

                    {/* LA CURVA DE PESO VIVE EN SEGUIMIENTO, Y SOLO AHÍ (punto 4 del 17-08).
                        «El peso no es un macro y ya vive en Evolución.»

                        Estaba en las dos pantallas y llegaron a decir lo contrario: «Ahora
                        77,1 kg · +2,1» aquí y «Ahora 50 kg · −25» allí, del mismo cliente el
                        mismo día. Se arreglaron las fuentes -- las dos leen ya la misma serie
                        saneada, punto por punto -- pero mientras la gráfica esté duplicada,
                        el día que alguien toque una de las dos volvemos a esto: de hecho, ya
                        arregladas seguían discrepando en cuántos pesajes enseñaba cada una, y
                        no se vio hasta que Francisco preguntó si de verdad coincidían.

                        Una sola gráfica no puede contradecirse consigo misma. */}

                    {/* «VER MI EVOLUCIÓN» (doc 19-08): el botón sustituye a la gráfica de
                        peso, que se quitó. El peso no es un macro y ya vive en Evolución. */}
                    <button type="button" data-testid="ver-mi-evolucion"
                        onClick={() => navigate('/dashboard/reports?abrir=evolucion')}
                        className="w-full sm:w-auto px-5 py-2.5 rounded-full border border-brand text-brand text-sm font-bold hover:bg-brand/10 inline-flex items-center gap-2">
                        <TrendingUp className="w-4 h-4" /> Ver mi evolución
                    </button>

                    {/* El «si crees que hay que moverlos, dínoslo por el chat» murió con la
                        versión para planes con entrenador (doc 19-08): al personalizado ya no
                        se le invita a mover nada, y esta pantalla ya no la ve. */}
                </>
            )}
        </div>
    );
};

export default MisMacrosPage;
