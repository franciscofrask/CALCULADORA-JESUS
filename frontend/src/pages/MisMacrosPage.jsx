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
 *   TU PESO        la gráfica de `GraficaDePeso`, la misma de Reportes y de la ficha.
 *
 * Quién ve el histórico lo decide el servidor a partir de su plan (TABLA 20): el plan
 * personalizado sí, el plan sin ajuste no. Aquí solo se pinta lo que llega.
 */
import React, { useEffect, useState } from 'react';
import { SlidersHorizontal, Loader2, Quote, TrendingUp } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import GraficaDePeso from '../components/GraficaDePeso';
import { MACRO } from './ClientDashboard';

const fechaLarga = (iso) => {
    if (!iso) return '';
    return new Date(iso + 'T12:00:00').toLocaleDateString('es-ES', {
        day: 'numeric', month: 'long', year: 'numeric',
    });
};

const fechaCorta = (iso) => {
    if (!iso) return '-';
    return new Date(iso + 'T12:00:00').toLocaleDateString('es-ES', {
        day: 'numeric', month: 'short', year: '2-digit',
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

// Las celdas de un bloque dentro de la tabla del histórico. EN COLOR LO QUE CAMBIÓ respecto al
// ajuste anterior, igual que lo ve el entrenador: nadie lee veinte filas de números, se lee la
// escalera. La marca viene calculada del servidor (`cambios`), que es la que se guardó al hacer
// el ajuste; sin ella -- entradas viejas y las importadas de Calma -- no se marca nada, porque
// compararla con la fila de al lado solo acierta si la tabla está entera y en orden.
const CeldasHistorico = ({ macros, cambios, conGrasa = true }) => {
    const campos = conGrasa ? CAMPOS : CAMPOS.slice(0, 2);
    return campos.map(c => {
        const cambio = !!cambios?.[c.key];
        return (
            <td key={c.key}
                className={`px-1.5 py-2 text-right font-data ${cambio ? 'text-red-600 dark:text-red-400 font-bold' : 'text-foreground/70'}`}>
                {numero(macros?.[c.key])}
            </td>
        );
    });
};

// Cuántos ajustes se enseñan de entrada. Con la revisión quincenal son los seis últimos meses,
// que es lo que alguien mira; los que vinieron de Calma llevan años y arrancaban con cuarenta
// filas de tabla antes de la gráfica. El resto está a un clic, no escondido.
const AJUSTES_A_LA_VISTA = 12;

const MisMacrosPage = () => {
    const { api, profile } = useAuth();
    const [datos, setDatos] = useState(null);
    const [cargando, setCargando] = useState(true);
    const [todoElHistorico, setTodoElHistorico] = useState(false);

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
    const visibles = todoElHistorico ? entradas : entradas.slice(0, AJUSTES_A_LA_VISTA);
    const entrenaHoy = datos?.tipo_dia_hoy === 'entrenamiento';
    const descansaHoy = datos?.tipo_dia_hoy === 'descanso';
    const nombreDelCoach = profile?.entrenador?.nombre;
    const porQueNo = profile?.macros_ajustables?.por_que_no;

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[900px] mx-auto space-y-6 animate-fade-in">
            <header className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-brand/10">
                    <SlidersHorizontal className="w-6 h-6 text-brand" />
                </div>
                <div>
                    <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none" data-testid="macros-heading">
                        Mis macros
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        {nombreDelCoach ? `Te los ajusta ${nombreDelCoach}` : 'Te los ajusta tu entrenador'}
                    </p>
                </div>
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
                                Todavía no tienes ningún ajuste guardado. En cuanto tu entrenador te ponga
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
                                <Quote className="w-3.5 h-3.5" /> Lo que te dijo tu entrenador en este ajuste
                            </p>
                            <p className="text-foreground leading-relaxed">«{vigente.feedback}»</p>
                        </section>
                    )}

                    {/* ── TU HISTÓRICO ──
                        Con una sola entrada no hay escalera que leer: la fila que saldría es la
                        misma que ya está arriba en «Hoy». */}
                    {datos?.con_historico && entradas.length > 1 && (
                        <section className="space-y-2" data-testid="mis-macros-historico">
                            <div className="flex items-baseline justify-between gap-2 flex-wrap">
                                <p className="caption">Tu histórico</p>
                                <p className="text-[11px] text-muted-foreground">En rojo, lo que cambió en cada ajuste</p>
                            </div>
                            <div className="surface p-2 overflow-x-auto">
                                <table className="w-full text-sm min-w-[520px]">
                                    <thead>
                                        <tr className="text-muted-foreground text-[10px] uppercase tracking-wider border-b border-border">
                                            <th rowSpan={2} className="px-2 py-1.5 text-left font-semibold">Fecha</th>
                                            <th rowSpan={2} className="px-2 py-1.5 text-right font-semibold">Peso</th>
                                            {/* Las cabeceras van sin color a propósito: en esta
                                                tabla el color significa UNA cosa -- esto cambió --,
                                                y tres bloques de colores al lado se lo comen. */}
                                            <th colSpan={3} className="px-1.5 py-1.5 text-center font-bold border-l border-border">Entreno</th>
                                            <th colSpan={2} className="px-1.5 py-1.5 text-center font-bold border-l border-border">Peri</th>
                                            <th colSpan={3} className="px-1.5 py-1.5 text-center font-bold border-l border-border">Descanso</th>
                                        </tr>
                                        <tr className="text-muted-foreground/70 text-[10px] uppercase border-b border-border">
                                            <th className="px-1.5 pb-1.5 text-right font-medium border-l border-border">P</th><th className="px-1.5 pb-1.5 text-right font-medium">H</th><th className="px-1.5 pb-1.5 text-right font-medium">G</th>
                                            <th className="px-1.5 pb-1.5 text-right font-medium border-l border-border">P</th><th className="px-1.5 pb-1.5 text-right font-medium">H</th>
                                            <th className="px-1.5 pb-1.5 text-right font-medium border-l border-border">P</th><th className="px-1.5 pb-1.5 text-right font-medium">H</th><th className="px-1.5 pb-1.5 text-right font-medium">G</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {visibles.map((h, i) => (
                                            <tr key={h.id || i} className="border-b border-border last:border-0">
                                                <td className="px-2 py-2 whitespace-nowrap font-data text-foreground">{fechaCorta(h.fecha)}</td>
                                                <td className="px-2 py-2 text-right whitespace-nowrap font-data text-foreground">
                                                    {h.peso != null ? `${h.peso} kg` : '-'}
                                                </td>
                                                <CeldasHistorico macros={h.entreno} cambios={h.cambios?.entreno} />
                                                <CeldasHistorico macros={h.peri} cambios={h.cambios?.perientreno} conGrasa={false} />
                                                <CeldasHistorico macros={h.descanso} cambios={h.cambios?.descanso} />
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                            {entradas.length > visibles.length && (
                                <button type="button" onClick={() => setTodoElHistorico(true)}
                                    className="text-xs font-semibold text-brand hover:underline"
                                    data-testid="mis-macros-ver-todo">
                                    Ver los {entradas.length} ajustes
                                </button>
                            )}
                        </section>
                    )}

                    {/* ── EVOLUCIÓN DE TU PESO ── */}
                    {(datos?.evolucion_peso || []).length > 1 && (
                        <section className="space-y-2">
                            <p className="caption flex items-center gap-2"><TrendingUp className="w-4 h-4" /> Evolución de tu peso</p>
                            <div className="surface p-4">
                                <GraficaDePeso puntos={datos.evolucion_peso} />
                            </div>
                        </section>
                    )}

                    {/* Por qué no puede tocarlos, con las palabras que decide el servidor. Va al
                        final: es la explicación de una pantalla que ya se entiende sola, no un
                        aviso que haya que leer antes de nada. */}
                    {porQueNo && (
                        <p className="text-xs text-muted-foreground" data-testid="macros-los-lleva-tu-coach">{porQueNo}</p>
                    )}
                </>
            )}
        </div>
    );
};

export default MisMacrosPage;
