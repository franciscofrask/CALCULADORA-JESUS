import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { plural } from '../lib/labels';
import { Dumbbell, Moon, Utensils, ChevronRight, HelpCircle } from 'lucide-react';

// Mi semana (tarea 5.1 del rediseño, doc de Jesús del 21-08): los siete días de la
// semana actual, cada uno con su dieta y su entreno. Es la pantalla para programar la
// víspera: de aquí se salta a Nutrición en el día que toque (?date=, el mismo camino
// que ya usa NutritionPage).

// El servidor manda lunes a domingo en este orden; la etiqueta corta sale del índice,
// no de parsear la fecha con la zona del navegador.
const DIAS_CORTOS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

const diaDelMes = (fecha) => Number(String(fecha || '').slice(8, 10)) || '';

// Mismo marco que RoutinePage, y fuera del componente por lo mismo que allí: definido
// dentro, cada render crearía un componente nuevo y React remontaría la página.
const Wrap = ({ children }) => (
    <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1200px] mx-auto animate-fade-in" data-testid="mi-semana-page">{children}</div>
);

const FILTROS = [
    { id: 'todo', label: 'Todo' },
    { id: 'dieta', label: 'Dieta' },
    { id: 'entreno', label: 'Entreno' },
];

const MiSemanaPage = () => {
    const { api } = useAuth();
    const navigate = useNavigate();
    const [semana, setSemana] = useState(null);
    const [loading, setLoading] = useState(true);
    const [filtro, setFiltro] = useState('todo');

    useEffect(() => {
        // Con el «hoy» del RELOJ DEL CLIENTE (bloque F, 23-08): la pastilla «Hoy» y la
        // semana por defecto son suyas, no las de España.
        api.get(`/diets/semana?hoy_cliente=${new Date().toLocaleDateString('en-CA')}`)
            .then(r => setSemana(r.data))
            .catch(e => {
                console.error('Error cargando la semana:', e);
                toast.error('No hemos podido cargar tu semana. Inténtalo en un momento.');
            })
            .finally(() => setLoading(false));
    }, [api]);

    const irAlDia = (fecha) => navigate(`/dashboard/nutrition?date=${fecha}`);

    if (loading) {
        return <Wrap><div className="animate-pulse space-y-3 max-w-2xl">
            <div className="h-9 bg-muted rounded w-1/3" />
            <div className="h-5 bg-muted rounded w-2/3" />
            <div className="h-10 bg-muted rounded-xl w-56" />
            {[...Array(7)].map((_, i) => <div key={i} className="h-20 bg-muted rounded-2xl" />)}
        </div></Wrap>;
    }

    if (!semana) {
        return <Wrap>
            <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground mb-6" data-testid="mi-semana-heading">Mi semana</h1>
            <div className="surface p-10 text-center max-w-2xl">
                <p className="text-muted-foreground text-sm">No hemos podido cargar tu semana. Recarga la página para intentarlo otra vez.</p>
            </div>
        </Wrap>;
    }

    const r = semana.resumen || {};
    // «2 creadas · 1 empezada · 4 sin crear · 1 de 4 entrenos» (fuera «montar», punto 7
    // del 23-08; los campos del servidor conservan su nombre). El tramo de entrenos
    // solo dice «X de N» cuando el registro de sesiones existe; si no, «N entrenos» a
    // secas: un «0 de 4» que nadie ha contado sería mentira.
    // Y SI NO HAY NINGUNO PREVISTO, EL TRAMO NO SALE. Al que no lleva rutina con nosotros le
    // salía «0 entrenos», que no informa de nada y encima le sugiere que debería tener
    // alguno: ese 0 no es un entreno que se haya saltado, es que la semana no pinta ninguno.
    const entrenosTxt = !r.entrenos_total
        ? null
        : r.entrenos_hechos == null
            ? plural(r.entrenos_total, 'entreno')
            : `${r.entrenos_hechos} de ${plural(r.entrenos_total, 'entreno')}`;
    // Y EL TITULAR CUENTA LAS QUE CUADRAN, no solo las creadas (revisión del 2-09):
    // «7 creadas» con las siete sin cuadrar es el mismo problema que el verde de las filas.
    // Se cuenta aquí, sobre los días que ya llegan, para no pedirle otro número al servidor.
    const cuadradas = (semana.dias || []).filter(d => d.estado === 'montada' && d.is_cuadrado).length;
    const creadas = r.montadas || 0;
    const contador = [
        creadas ? `${creadas} ${creadas === 1 ? 'creada' : 'creadas'}${
            creadas ? ` (${cuadradas} ${cuadradas === 1 ? 'cuadrada' : 'cuadradas'})` : ''}` : null,
        plural(r.empezadas || 0, 'empezada'),
        `${r.sin_montar || 0} sin crear`,
        entrenosTxt,
    ].filter(Boolean).join(' · ');

    return (
        <Wrap>
            <div className="max-w-2xl">
                {/* Cabecera */}
                <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none mb-2" data-testid="mi-semana-heading">Mi semana</h1>
                <p className="text-sm text-muted-foreground mb-4" data-testid="mi-semana-contador">{contador}</p>

                {/* Deslizador Todo / Dieta / Entreno */}
                <div className="inline-flex bg-muted rounded-xl p-1 gap-1 mb-5" role="tablist" data-testid="mi-semana-filtro">
                    {FILTROS.map(f => (
                        <button key={f.id} role="tab" aria-selected={filtro === f.id}
                            onClick={() => setFiltro(f.id)} data-testid={`filtro-${f.id}`}
                            className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-colors
                                ${filtro === f.id ? 'bg-brand text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}>
                            {f.label}
                        </button>
                    ))}
                </div>

                {/* Los siete días */}
                <div className="space-y-2.5" data-testid="mi-semana-dias">
                    {(semana.dias || []).map((dia, i) => (
                        <DiaCard key={dia.fecha} dia={dia} indice={i} filtro={filtro}
                            esHoy={dia.fecha === semana.hoy} onIr={() => irAlDia(dia.fecha)} />
                    ))}
                </div>
            </div>
        </Wrap>
    );
};

const DiaCard = ({ dia, indice, filtro, esHoy, onIr }) => {
    const descanso = dia.tipo_dia === 'descanso';
    // En «Entreno», los días de descanso se APAGAN en vez de desaparecer, para que la
    // semana no se descoloque (lo pide el doc tal cual).
    const apagado = filtro === 'entreno' && descanso;

    return (
        <div onClick={onIr} role="button" tabIndex={0}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onIr(); } }}
            data-testid={`dia-${dia.fecha}`}
            className={`surface p-3.5 sm:p-4 flex items-center gap-3 sm:gap-4 cursor-pointer transition-all
                hover:border-brand/40 ${esHoy ? 'border-brand/60' : ''} ${apagado ? 'opacity-40' : ''}`}>

            {/* Etiqueta del día: Lun 24 (+ pastilla Hoy) */}
            <div className="w-14 sm:w-16 flex-shrink-0 text-center">
                <p className={`text-[11px] font-bold uppercase tracking-wider ${esHoy ? 'text-brand' : 'text-muted-foreground'}`}>{DIAS_CORTOS[indice]}</p>
                <p className={`font-heading text-2xl font-bold leading-none ${esHoy ? 'text-brand' : 'text-foreground'}`}>{diaDelMes(dia.fecha)}</p>
                {esHoy && <span className="inline-block mt-1 text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-brand text-white" data-testid={`hoy-${dia.fecha}`}>Hoy</span>}
            </div>

            {/* Las dos líneas del día */}
            <div className="flex-1 min-w-0 space-y-1">
                {filtro !== 'entreno' && <LineaDieta dia={dia} />}
                {filtro !== 'dieta' && <LineaEntreno dia={dia} descanso={descanso} />}
            </div>

            {/* La acción: llevar a Nutrición en ese día */}
            <div className="flex-shrink-0 flex items-center gap-2">
                {filtro !== 'entreno' && dia.estado === 'empezada' && (
                    <span className="text-xs font-bold uppercase tracking-wider text-brand" data-testid={`accion-${dia.fecha}`}>Terminar</span>
                )}
                {filtro !== 'entreno' && dia.estado === 'sin_montar' && (
                    <span className="text-xs font-bold uppercase tracking-wider text-brand" data-testid={`accion-${dia.fecha}`}>Repetir</span>
                )}
                {/* El día completo también lleva rótulo (pedido 23-08), pero en gris:
                    el naranja queda para lo pendiente. */}
                {filtro !== 'entreno' && dia.estado === 'montada' && (
                    <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground" data-testid={`accion-${dia.fecha}`}>Ver día</span>
                )}
                <ChevronRight className="w-4 h-4 text-foreground/40" />
            </div>
        </div>
    );
};

const LineaDieta = ({ dia }) => {
    const m = dia.macros || {};
    return (
        <div className="flex items-center gap-2 text-sm" data-testid={`dieta-${dia.fecha}`}>
            <Utensils className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
            {dia.estado === 'montada' && (
                /* «creada» delante y sin `truncate` en ella: a 390 px la línea se cortaba
                   justo ahí y el día se quedaba en «99 · 82 · 32 · ...» (recorrido móvil
                   del 23-08).

                   Y LOS NÚMEROS TAMPOCO SE CORTAN (28-08). Llevaban `truncate`, y en el
                   teléfono no caben: medida la fila, son 354 px de los que el rótulo «Ver
                   día» se lleva 86 y el cuadrito del día 63, así que a los tres números les
                   quedaban 52 px para los 108 que ocupan. Resultado en pantalla: «Creada ·
                   118 …», que es justo el dato por el que se entra a mirar. Ahora, cuando no
                   caben, bajan enteros a la línea de abajo: la fila crece unos píxeles en el
                   móvil y no se pierde nada. */
                /* CREADA NO ES CUADRADA (revisión del 2-09).
                   Las siete filas decían «Creada» en verde, así que el día que se queda a
                   128 g de hidratos se leía igual que el que cuadra, y el verde le decía
                   que iba bien. El calendario de Nutrición ya distingue las dos cosas con
                   `is_cuadrado`; aquí se usa esa misma señal y no una nueva.

                   EL NARANJA DE «SIN CUADRAR» SE QUEDA, Y ESTÁ SIN DECIDIR (2-09). Choca con
                   dos cosas a la vez y no se puede arreglar solo aquí: con el punto 77
                   («naranja sólo para lo que se pasa»; un día a medias no es un error), y con
                   la propia fila, donde el número de la proteína ya va en naranja porque en
                   esta pantalla los macros llevan su color (P naranja · H azul · G amarillo).
                   Pero la leyenda del calendario de Nutrición (`DietCalendar`) pinta «Sin
                   cuadrar» con ese mismo naranja, así que cambiarlo aquí y no allí deja las
                   dos pantallas diciendo lo mismo de dos formas. Es una decisión de diseño de
                   las dos a la vez, no un arreglo de una. */
                <span className="font-data text-foreground flex items-baseline gap-1 flex-wrap min-w-0">
                    {/* `null` es «no hay con qué juzgarlo» (un cliente sin macros puestos):
                        ahí se dice «Creada» a secas y sin color, que es lo único cierto.
                        Antes cualquier cosa que no fuera `true` se leía «Sin cuadrar». */}
                    <span className={`font-semibold flex-shrink-0 ${
                        dia.is_cuadrado === true ? 'text-emerald-400'
                            : dia.is_cuadrado === false ? 'text-orange-400' : 'text-muted-foreground'}`}
                        data-testid={`estado-dieta-${dia.fecha}`}>
                        {dia.is_cuadrado === true ? 'Cuadrada'
                            : dia.is_cuadrado === false ? 'Sin cuadrar' : 'Creada'}
                    </span>
                    <span className="text-muted-foreground">·</span>
                    <span className="whitespace-nowrap">
                        <span className="text-orange-400 font-semibold">{Math.round(m.P || 0)}</span>
                        <span className="text-muted-foreground"> · </span>
                        <span className="text-blue-400 font-semibold">{Math.round(m.H || 0)}</span>
                        <span className="text-muted-foreground"> · </span>
                        <span className="text-yellow-400 font-semibold">{Math.round(m.G || 0)}</span>
                    </span>
                </span>
            )}
            {dia.estado === 'empezada' && (
                <span className="text-foreground">{dia.n_comidas_con_alimentos} de {plural(dia.n_comidas_total, 'comida')}</span>
            )}
            {dia.estado === 'sin_montar' && (
                <span className="text-muted-foreground">Sin crear</span>
            )}
        </div>
    );
};

const LineaEntreno = ({ dia, descanso }) => {
    const e = dia.entreno || {};
    return (
        <div className="flex items-center gap-2 text-sm" data-testid={`entreno-${dia.fecha}`}>
            {descanso ? (
                <>
                    <Moon className="w-3.5 h-3.5 text-violet-400 flex-shrink-0" />
                    <span className="text-muted-foreground">Descanso</span>
                </>
            ) : dia.tipo_dia === 'entrenamiento' ? (
                <>
                    <Dumbbell className="w-3.5 h-3.5 text-brand flex-shrink-0" />
                    <span className="text-foreground truncate">{e.nombre || 'Entreno'}</span>
                    {/* Preparado para el registro de sesiones: cuando el servidor sepa si
                        el entreno se hizo, aquí se dice; con null no se inventa nada. */}
                    {e.hecho === true && <span className="text-xs text-emerald-400 font-semibold">hecho</span>}
                    {e.hecho === false && <span className="text-xs text-muted-foreground">pendiente</span>}
                </>
            ) : (
                <>
                    <HelpCircle className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                    <span className="text-muted-foreground">Por decidir</span>
                </>
            )}
        </div>
    );
};

export default MiSemanaPage;
