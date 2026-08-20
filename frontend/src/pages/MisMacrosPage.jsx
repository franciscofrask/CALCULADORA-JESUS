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
import { SlidersHorizontal, Loader2, Quote, TrendingUp } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { MACRO } from './ClientDashboard';
import HistorialDeMacros, { ultimoAjusteLegible } from '../components/HistorialDeMacros';

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

const MisMacrosPage = ({ onAjustar }) => {
    const { api } = useAuth();
    const navigate = useNavigate();
    const [datos, setDatos] = useState(null);
    const [cargando, setCargando] = useState(true);

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
                        movió la última vez, en una frase que se lee. Desde el 19-08 esta
                        pantalla es SOLO de quien se los calcula él («es su herramienta»):
                        nada de «te los ajustamos nosotros». */}
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
                {/* Su herramienta: el ajuste está a un clic, no escondido. */}
                {onAjustar && (
                    <button type="button" onClick={onAjustar} data-testid="ajustar-mis-macros"
                        className="px-4 py-2 rounded-full bg-brand text-white text-sm font-bold hover:opacity-90">
                        Ajustar mis macros
                    </button>
                )}
            </header>

            {cargando ? (
                <div className="flex justify-center py-16"><Loader2 className="w-7 h-7 animate-spin text-muted-foreground" /></div>
            ) : (
                <>
                    {/* ── HOY ── */}
                    <section className="surface p-5 space-y-3" data-testid="mis-macros-hoy">
                        <div className="flex items-baseline justify-between gap-2 flex-wrap">
                            <p className="caption">
                                Hoy{entrenaHoy ? ' · Entreno' : descansaHoy ? ' · Descanso' : ''}
                            </p>
                            {vigente?.fecha && (
                                <p className="text-xs text-muted-foreground" data-testid="mis-macros-vigentes-desde">
                                    Vigentes desde el {fechaLarga(vigente.fecha)}
                                </p>
                            )}
                        </div>

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
                                {vigente.peri && <BloqueLinea label="Perientreno (intra + post)" macros={vigente.peri} conGrasa={false} />}
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
