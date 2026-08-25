import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Search, Dumbbell, ChevronRight, Users, Upload, Star } from 'lucide-react';
import { PlanBadge } from './ClientDashboard';
import EditorDeRutina from '../components/EditorDeRutina';

/**
 * LA BIBLIOTECA DE RUTINAS DEL EQUIPO (17-08-2026).
 *
 * «Deberíamos agregar la opción de crear rutinas en el panel de rutinas, y cuando vas a la
 * ficha poder elegir también de las creadas por entrenadores, poder editarlas y borrarlas»
 * (Francisco).
 *
 * Las rutinas que escribe Jesús cada mes viven en Drive y se mandan por fuera de la app.
 * Aquí se escriben una vez y se le asignan a quien haga falta desde su ficha. Borrar una de
 * la biblioteca NO deja a nadie sin rutina: al asignarla se copia.
 */
const BibliotecaDeRutinas = ({ api }) => {
    const [rutinas, setRutinas] = useState(null);
    const [editando, setEditando] = useState(null);   // null = cerrado; {} = nueva

    const cargar = React.useCallback(() => {
        api.get('/admin/routines/biblioteca')
            .then(r => setRutinas(r.data?.rutinas || []))
            .catch(() => toast.error('No hemos podido cargar las rutinas guardadas.'));
    }, [api]);

    useEffect(() => { cargar(); }, [cargar]);

    const borrar = (r) => {
        api.delete(`/admin/routines/biblioteca/${r.id}`)
            .then(() => { toast.success(`«${r.nombre}» quitada de la biblioteca`); cargar(); })
            .catch(() => toast.error('No hemos podido borrarla. Inténtalo de nuevo.'));
    };

    // CUÁL ES LA RUTINA DEL MES (24-08). Faltaba el concepto: la app la vende por 57 € en
    // tres sitios y en la base no había forma de saber cuál es la de este mes, así que el
    // que la compraba solo generaba un aviso para que alguien se la mandara a mano. La que
    // se marque aquí es la que se le pone sola a quien la pague.
    const marcarDelMes = (r) => {
        api.post(`/admin/routines/biblioteca/${r.id}/del-mes`, { del_mes: !r.del_mes })
            .then(() => {
                toast.success(r.del_mes ? `«${r.nombre}» ya no es la del mes`
                                        : `«${r.nombre}» es la rutina del mes`);
                cargar();
            })
            .catch(() => toast.error('No hemos podido marcarla. Inténtalo de nuevo.'));
    };

    return (
        <>
            <Card className="bg-[#111] border-[#222]">
                <CardContent className="p-4 space-y-3">
                    <div className="flex items-center gap-3 flex-wrap">
                        <Dumbbell className="w-5 h-5 text-[#FF671F] shrink-0" />
                        <div className="min-w-0 flex-1">
                            <p className="text-white text-sm font-semibold">Rutinas guardadas</p>
                            <p className="text-white/40 text-xs">
                                Escríbelas una vez y asígnalas desde la ficha de cualquier cliente.
                            </p>
                        </div>
                        <button onClick={() => setEditando({})} data-testid="nueva-rutina"
                            className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-sm font-semibold px-4 py-2 rounded-lg">
                            Rutina nueva
                        </button>
                    </div>

                    {rutinas === null ? (
                        <p className="text-white/30 text-sm py-2">Cargando…</p>
                    ) : rutinas.length === 0 ? (
                        <p className="text-white/30 text-sm py-2">
                            Todavía no hay ninguna. La primera que escribas se podrá asignar a todos los que la necesiten.
                        </p>
                    ) : (
                        <div className="space-y-2">
                            {rutinas.map(r => (
                                <div key={r.id} className={`flex items-center justify-between gap-3 p-3 bg-[#0A0A0A] rounded-lg border ${r.del_mes ? 'border-[#FF671F]/50' : 'border-[#222]'}`}>
                                    <div className="min-w-0">
                                        <p className="text-white text-sm">
                                            {r.nombre}
                                            {r.del_mes && (
                                                <span className="ml-2 text-[9px] uppercase font-bold tracking-wide text-[#FF671F] bg-[#FF671F]/15 px-1.5 py-0.5 rounded">
                                                    la del mes
                                                </span>
                                            )}
                                        </p>
                                        <p className="text-white/40 text-xs">
                                            {r.dias_de_entreno} {r.dias_de_entreno === 1 ? 'día' : 'días'} · {r.ejercicios} ejercicios
                                            {r.objetivo ? ` · ${r.objetivo}` : ''}{r.nivel ? ` · ${r.nivel}` : ''}
                                            {r.updated_by ? ` · la escribió ${r.updated_by}` : ''}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-3 shrink-0">
                                        <button onClick={() => marcarDelMes(r)} data-testid={`del-mes-${r.id}`}
                                            title="La que se le entrega sola a quien compre la rutina del mes"
                                            className={`inline-flex items-center gap-1 text-xs font-semibold ${r.del_mes ? 'text-[#FF671F]' : 'text-white/40 hover:text-white'}`}>
                                            <Star className={`w-3.5 h-3.5 ${r.del_mes ? 'fill-[#FF671F]' : ''}`} />
                                            {r.del_mes ? 'Es la del mes' : 'La del mes'}
                                        </button>
                                        <button onClick={() => setEditando(r)}
                                            className="text-white/50 hover:text-white text-xs font-semibold">Editar</button>
                                        <button onClick={() => borrar(r)}
                                            className="text-white/30 hover:text-red-400 text-xs">Borrar</button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {editando && (
                <EditorDeRutina api={api} rutina={editando.id ? editando : null}
                    onCerrar={() => setEditando(null)}
                    onGuardada={() => { setEditando(null); cargar(); }} />
            )}
        </>
    );
};

/**
 * PONERLES RUTINA A VARIOS A LA VEZ (punto 6 del documento del 17-08).
 *
 * «164 clientes tienen la rutina incluida en su plan y ninguno la tiene puesta. La vía
 * existe -- ficha → Entreno → Generar rutina con IA -- pero uno a uno, 164 veces, no es
 * viable.»
 *
 * Se hace por grupos, que es lo que pide el documento: quien comparte objetivo, días,
 * nivel y material puede compartir rutina, así que se genera UNA por grupo.
 *
 * Y lo primero que enseña es lo que NO se puede hacer. Medido en producción el 17-08: de
 * los 163 sin rutina, 159 no tienen puesto cuántos días entrenan y 91 no tienen objetivo.
 * Con eso no hay rutina que valga, y el botón no puede fingir que sí. Antes de asignar
 * nada se ve a cuántos les falta qué.
 */
const PonerlesRutinaAVarios = ({ api, onHecho }) => {
    const [datos, setDatos] = useState(null);
    const [cargando, setCargando] = useState(false);
    const [trabajando, setTrabajando] = useState(false);
    const [abierto, setAbierto] = useState(false);

    const mirar = () => {
        setCargando(true);
        setAbierto(true);
        api.get('/admin/routines/pendientes-por-grupo')
            .then(r => setDatos(r.data))
            .catch(() => toast.error('No hemos podido agrupar a los clientes. Inténtalo de nuevo.'))
            .finally(() => setCargando(false));
    };

    const asignar = (grupos) => {
        setTrabajando(true);
        api.post('/admin/routines/asignar-en-bloque', { grupos })
            .then(r => {
                const n = r.data?.asignadas || 0;
                toast.success(n === 1 ? 'Rutina puesta a 1 cliente' : `Rutinas puestas a ${n} clientes`);
                mirar();
                onHecho?.();
            })
            .catch(() => toast.error('No hemos podido asignar las rutinas. Inténtalo de nuevo.'))
            .finally(() => setTrabajando(false));
    };

    if (!abierto) {
        return (
            <Card className="bg-[#111] border-[#222]">
                <CardContent className="p-4 flex items-center gap-3 flex-wrap">
                    <Users className="w-5 h-5 text-[#FF671F] shrink-0" />
                    <div className="min-w-0 flex-1">
                        <p className="text-white text-sm font-semibold">Ponerles rutina a varios a la vez</p>
                        <p className="text-white/40 text-xs">
                            Agrupa a los que están sin rutina por objetivo, días y material, y genera una para cada grupo.
                        </p>
                    </div>
                    <button onClick={mirar} data-testid="ver-grupos-rutina"
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white text-sm font-semibold px-4 py-2 rounded-lg">
                        Ver los grupos
                    </button>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="bg-[#111] border-[#222]">
            <CardContent className="p-4 space-y-3">
                <div className="flex items-center gap-3">
                    <Users className="w-5 h-5 text-[#FF671F] shrink-0" />
                    <p className="text-white text-sm font-semibold flex-1">Ponerles rutina a varios a la vez</p>
                    <button onClick={() => setAbierto(false)} className="text-white/40 hover:text-white text-xs">cerrar</button>
                </div>

                {cargando && <p className="text-white/40 text-sm py-3">Agrupando…</p>}

                {!cargando && datos && (
                    <>
                        {/* Primero, a quién NO se le puede poner y por qué. */}
                        {datos.les_faltan_datos > 0 && (
                            <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-3">
                                <p className="text-white text-sm">
                                    {/* Decía «falta saber lo básico de su entrenamiento» cuando los días
                                        de entreno todavía bloqueaban. Ya no: son cuatro para todos y se
                                        rellenan solos, así que lo único que puede faltar es el objetivo,
                                        y eso no es «lo básico de su entrenamiento». */}
                                    A <b className="text-yellow-400">{datos.les_faltan_datos}</b> no se les puede
                                    generar todavía: falta un dato de su ficha.
                                </p>
                                <p className="text-white/50 text-xs mt-1">
                                    {datos.que_les_falta?.map(q => `${q.a_cuantos} sin ${q.dato}`).join(' · ')}
                                    {' '}· Se rellena en su ficha, o preguntándoselo.
                                </p>
                            </div>
                        )}

                        {datos.se_les_puede_poner_ya === 0 ? (
                            <p className="text-white/40 text-sm">
                                Ahora mismo no hay nadie a quien se le pueda poner una rutina con lo que sabemos de él.
                            </p>
                        ) : (
                            <>
                                <p className="text-white/60 text-sm">
                                    A <b className="text-white">{datos.se_les_puede_poner_ya}</b> sí, y hacen falta{' '}
                                    <b className="text-white">{datos.rutinas_que_harian_falta}</b>{' '}
                                    {datos.rutinas_que_harian_falta === 1 ? 'rutina' : 'rutinas'}.
                                </p>
                                <div className="space-y-2">
                                    {datos.grupos?.map(g => (
                                        <div key={g.id} className="flex items-center justify-between gap-3 p-3 bg-[#0A0A0A] rounded-lg border border-[#222]">
                                            <div className="min-w-0">
                                                <p className="text-white text-sm">{g.nombre || 'sin clasificar'}</p>
                                                <p className="text-white/40 text-xs">
                                                    {g.cuantos} {g.cuantos === 1 ? 'cliente' : 'clientes'}
                                                    {' · '}{g.clientes?.slice(0, 3).map(c => c.nombre).join(', ')}
                                                    {g.cuantos > 3 ? '…' : ''}
                                                </p>
                                            </div>
                                            <button disabled={trabajando} onClick={() => asignar([g.id])}
                                                className="shrink-0 text-xs font-semibold px-3 py-1.5 rounded-lg border border-[#FF671F] text-[#FF671F] hover:bg-[#FF671F] hover:text-white disabled:opacity-40 transition-colors">
                                                Ponérsela
                                            </button>
                                        </div>
                                    ))}
                                </div>
                                <button disabled={trabajando} onClick={() => asignar('todos')}
                                    data-testid="asignar-todos-los-grupos"
                                    className="w-full bg-[#FF671F] hover:bg-[#FF671F]/90 disabled:opacity-40 text-white text-sm font-semibold px-4 py-2 rounded-lg">
                                    {trabajando ? 'Generando y asignando…' : `Ponérsela a los ${datos.se_les_puede_poner_ya}`}
                                </button>
                            </>
                        )}
                    </>
                )}
            </CardContent>
        </Card>
    );
};

/**
 * LA MISMA RUTINA A VARIOS DE GOLPE (Jesús, 24-08).
 *
 * «La del mes solo a los que se le incluyen, la personalizada se le da una personalizada,
 * debemos agregar eso.» En producción hay 59 clientes con plan de rutina PERSONALIZADA y 58
 * sin ninguna rutina puesta. Subir el PDF de uno en uno desde su ficha son 58 vueltas de
 * ficha, subir, volver; la entrega mensual de agosto hubo que hacerla por un script suelto
 * porque esto no existía.
 *
 * Se marcan los clientes en la tabla de abajo y se sube UN archivo para todos. No pisa nada:
 * como la subida de la ficha, guarda una entrega más y el cliente ve la última.
 */
/**
 * LA RUTINA DEL MES: SE DEJA EN UN SITIO Y LE SALE A QUIEN LE TOQUE.
 *
 * Es como lo hace Jenny y como pidió Francisco el 25-08: dos archivos, el de hombre y el de
 * mujer, y ya está. Nadie selecciona clientes ni reparte nada.
 *
 * Lo de antes era subirla en dos tandas marcando gente a mano y sabiéndose de memoria quién
 * era hombre y quién mujer. Resultado medido: de los 56 que la llevan incluida, 26 no la
 * tenían, y 25 de ellos eran de ELM, el plan cuyo entregable principal es justo esa rutina.
 *
 * La cuenta de «le llega a N» va al lado del archivo a propósito: subir el PDF y que llegue
 * a cero personas es el fallo que no se ve.
 */
const HuecoDelMes = ({ api, sexo, hueco, onHecho }) => {
    const [subiendo, setSubiendo] = useState(false);
    const pdf = hueco?.pdf;
    const etiqueta = sexo === 'hombre' ? 'Hombre' : 'Mujer';

    const subir = async (e) => {
        const archivo = e.target.files?.[0];
        e.target.value = '';
        if (!archivo) return;
        setSubiendo(true);
        try {
            const fd = new FormData();
            fd.append('file', archivo);
            fd.append('sexo', sexo);
            const r = await api.post('/admin/routines/pdf-del-mes', fd);
            const n = r.data?.llega_a ?? 0;
            toast.success(n === 1 ? `Ya la ve 1 cliente (${etiqueta.toLowerCase()})`
                                  : `Ya la ven ${n} clientes (${etiqueta.toLowerCase()})`);
            onHecho?.();
        } catch (err) {
            toast.error(err?.response?.data?.detail || 'No hemos podido subir la rutina.');
        } finally {
            setSubiendo(false);
        }
    };

    return (
        <div className={`flex-1 min-w-0 rounded-lg border p-3 ${pdf ? 'border-[#333] bg-[#0A0A0A]' : 'border-dashed border-[#444] bg-transparent'}`}
            data-testid={`hueco-del-mes-${sexo}`}>
            <div className="flex items-center justify-between gap-2 mb-1">
                <p className="text-white text-sm font-semibold">{etiqueta}</p>
                <span className="text-[10px] text-white/40">
                    le llega a {hueco?.llega_a ?? 0}
                </span>
            </div>
            {pdf ? (
                <>
                    <p className="text-white/70 text-xs truncate" title={pdf.filename}>{pdf.filename}</p>
                    <p className="text-[10px] text-white/30 mb-2">
                        {pdf.nombre ? `${pdf.nombre} · ` : ''}
                        {pdf.uploaded_at ? new Date(pdf.uploaded_at).toLocaleDateString('es-ES') : ''}
                    </p>
                </>
            ) : (
                <p className="text-white/30 text-xs mb-2">Todavía no hay ninguna</p>
            )}
            <div className="flex items-center gap-2">
                <label className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg cursor-pointer
                    ${subiendo ? 'bg-[#FF671F]/40 text-white/70' : 'bg-[#FF671F] hover:bg-[#FF671F]/90 text-white'}`}>
                    <Upload className="w-3.5 h-3.5" />
                    {subiendo ? 'Subiendo…' : (pdf ? 'Cambiarla' : 'Subirla')}
                    <input type="file" accept="application/pdf" className="hidden" disabled={subiendo}
                        onChange={subir} data-testid={`input-del-mes-${sexo}`} />
                </label>
                {pdf && (
                    <button onClick={() => window.open(`${api.defaults.baseURL}/admin/routines/pdf-del-mes?sexo=${sexo}`, '_blank')}
                        className="text-xs text-white/40 hover:text-white">verla</button>
                )}
            </div>
        </div>
    );
};

const LaRutinaDelMes = ({ api, onHecho }) => {
    const [info, setInfo] = useState(null);

    const cargar = useCallback(async () => {
        try {
            const r = await api.get('/admin/routines/pdf-del-mes/info');
            setInfo(r.data || null);
        } catch { setInfo(null); }
    }, [api]);
    useEffect(() => { cargar(); }, [cargar]);

    const huecos = info?.huecos || {};
    return (
        <Card className="bg-[#111] border-[#222]" data-testid="la-rutina-del-mes">
            <CardContent className="p-4 space-y-3">
                <div>
                    <p className="text-white font-semibold text-sm">La rutina del mes</p>
                    <p className="text-white/40 text-xs">
                        Déjala aquí y le sale sola a quien la lleve en su plan. No hay que
                        elegir clientes: a cada uno se le da la de su sexo.
                    </p>
                </div>
                <div className="flex flex-col sm:flex-row gap-3">
                    <HuecoDelMes api={api} sexo="hombre" hueco={huecos.hombre}
                        onHecho={() => { cargar(); onHecho?.(); }} />
                    <HuecoDelMes api={api} sexo="mujer" hueco={huecos.mujer}
                        onHecho={() => { cargar(); onHecho?.(); }} />
                </div>
                <p className="text-[10px] text-white/30">
                    Si a alguien le has subido una rutina suya, esa manda: la del mes no la pisa.
                    Bronze y Mantenimiento no la ven, porque la compran aparte.
                </p>
            </CardContent>
        </Card>
    );
};

const SubirPdfAVarios = ({ api, ids, onHecho, onLimpiar }) => {
    const [reparto, setReparto] = useState('');
    const [semanas, setSemanas] = useState('');
    const [subiendo, setSubiendo] = useState(false);

    const subir = async (e) => {
        const archivo = e.target.files?.[0];
        e.target.value = '';               // para poder subir el mismo archivo dos veces
        if (!archivo) return;
        setSubiendo(true);
        try {
            const fd = new FormData();
            fd.append('file', archivo);
            fd.append('clientes', ids.join(','));
            if (reparto.trim()) fd.append('reparto', reparto.trim());
            if (semanas.trim()) fd.append('semanas', semanas.trim());
            const r = await api.post('/admin/routines/pdf-en-bloque', fd);
            const n = r.data?.subidas || 0;
            toast.success(n === 1 ? 'Rutina subida a 1 cliente' : `Rutina subida a ${n} clientes`);
            onHecho?.();
        } catch (err) {
            toast.error(err?.response?.data?.detail || 'No hemos podido subir la rutina. Inténtalo de nuevo.');
        } finally {
            setSubiendo(false);
        }
    };

    return (
        <Card className="bg-[#111] border-[#FF671F]/40" data-testid="subir-pdf-en-bloque">
            <CardContent className="p-4 space-y-3">
                <div className="flex items-center gap-3 flex-wrap">
                    <Upload className="w-5 h-5 text-[#FF671F] shrink-0" />
                    <p className="text-white text-sm font-semibold flex-1 min-w-0">
                        {ids.length} {ids.length === 1 ? 'cliente elegido' : 'clientes elegidos'}
                    </p>
                    <button onClick={onLimpiar} className="text-white/40 hover:text-white text-xs">quitar la selección</button>
                </div>
                {/* 130px y no 92: con la caja estrecha el «Semanas» sale cortado. */}
                <div className="grid grid-cols-1 sm:grid-cols-[1fr_130px] gap-2">
                    <Input value={reparto} onChange={e => setReparto(e.target.value)}
                        placeholder="Reparto: Empuje, Tirón, Pierna, Empuje"
                        className="bg-[#0A0A0A] border-[#333] text-white text-xs" data-testid="bloque-reparto" />
                    <Input type="number" min="1" max="52" value={semanas} onChange={e => setSemanas(e.target.value)}
                        placeholder="Semanas" className="bg-[#0A0A0A] border-[#333] text-white text-xs"
                        data-testid="bloque-semanas" />
                </div>
                <p className="text-[10px] text-white/30">
                    El reparto y las semanas se le ponen a todos: es la misma rutina. Los días de la
                    semana los eligió cada cliente en su alta.
                </p>
                <label className={`inline-flex items-center gap-2 text-sm font-semibold px-4 py-2 rounded-lg cursor-pointer
                    ${subiendo ? 'bg-[#FF671F]/40 text-white/70' : 'bg-[#FF671F] hover:bg-[#FF671F]/90 text-white'}`}>
                    <Upload className="w-4 h-4" />
                    {subiendo ? 'Subiendo…' : `Subirles el PDF a los ${ids.length}`}
                    <input type="file" accept="application/pdf" className="hidden" disabled={subiendo}
                        onChange={subir} data-testid="input-pdf-en-bloque" />
                </label>
            </CardContent>
        </Card>
    );
};

// Vista general de rutinas: quien tiene su rutina puesta (estructurada o en PDF) y quien no.
// La rutina se genera y se asigna dentro de la ficha del cliente (pestaña Entreno); editarle
// un ejercicio a un cliente concreto todavía no se puede desde ninguna pantalla.
const AdminRoutinesPage = () => {
    const { api, planCatalog } = useAuth();
    const navigate = useNavigate();
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [onlyMissing, setOnlyMissing] = useState(false);
    // «La del mes solo a los que se le incluyen, la personalizada se le da una
    // personalizada» (Jesús, 24-08). Son DOS entregas distintas y dos listas distintas: a
    // los de «del mes» se les sube el MISMO PDF de este mes de golpe, y a los de
    // personalizada, el suyo. Por eso hay un filtro para cada una y no uno solo: sin el de
    // «del mes» había que fiarse del ojo para no colarle a un personalizado la del montón.
    const [soloPersonalizadas, setSoloPersonalizadas] = useState(false);
    const [soloDelMes, setSoloDelMes] = useState(false);
    const [elegidos, setElegidos] = useState(() => new Set());

    const recargar = React.useCallback(() => {
        setLoading(true);
        api.get('/admin/routines/overview')
            .then(r => setRows(r.data || []))
            .catch(() => toast.error('No hemos podido cargar las rutinas. Inténtalo de nuevo.'))
            .finally(() => setLoading(false));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => { recargar(); }, [recargar]);

    // A QUIÉN SE LE PROMETIÓ UNA RUTINA.
    //
    // «Con 240 de 240 en rojo, la pantalla no ayuda a priorizar. Yo la ordenaría por plan:
    // los que pagan rutina primero, que son los únicos a los que se les prometió» (Jesús,
    // 11-08). El catálogo ya lo sabe: `habilitaciones.rutina` vale "ninguna" en los planes
    // que no la incluyen. Con 240 filas iguales, esto es la diferencia entre una lista y
    // una tarea.
    // «OPCIONAL» NO ES «INCLUIDA» (24-08). Esto contaba como prometida la rutina de
    // cualquier plan cuyo modo no fuera «ninguna», y «opcional» quiere decir justo lo
    // contrario: no se la lleva, se la puede comprar. Con los datos de hoy eran 43
    // personas de más -- Bronze y Reto 12en12 -- metidas en «la tienen incluida en su plan
    // y todavía no la tienen puesta», o sea 43 tareas que no existen. El doc de Jesús trae
    // ese número inflado (165) porque lo copió de esta pantalla.
    const modoRutina = (plan) => planCatalog?.[plan]?.habilitaciones?.rutina || 'ninguna';
    const laLlevaEnSuPlan = (plan) => {
        const r = modoRutina(plan);
        return Boolean(r) && r !== 'ninguna' && r !== 'opcional';
    };
    const esPersonalizada = (plan) => modoRutina(plan) === 'personalizada';
    const esDelMes = (plan) => modoRutina(plan) === 'del_mes';

    const filtered = rows.filter(r =>
        (!onlyMissing || !r.has_routine) &&
        (!soloPersonalizadas || esPersonalizada(r.plan)) &&
        (!soloDelMes || esDelMes(r.plan)) &&
        (!search || r.name?.toLowerCase().includes(search.toLowerCase()) || r.email?.toLowerCase().includes(search.toLowerCase()))
    ).sort((a, b) => {
        const pa = laLlevaEnSuPlan(a.plan), pb = laLlevaEnSuPlan(b.plan);
        if (pa !== pb) return pa ? -1 : 1;
        // Dentro de cada grupo, el que aún no la tiene primero: es el que hay que atender.
        if (a.has_routine !== b.has_routine) return a.has_routine ? 1 : -1;
        return (a.name || '').localeCompare(b.name || '', 'es');
    });
    const withRoutine = rows.filter(r => r.has_routine).length;
    const laLlevanSinRutina = rows.filter(r => laLlevaEnSuPlan(r.plan) && !r.has_routine).length;
    const personalizadasPendientes = rows.filter(r => esPersonalizada(r.plan) && !r.has_routine);
    const delMesPendientes = rows.filter(r => esDelMes(r.plan) && !r.has_routine);

    // La selección se guarda por id y no por fila: al recargar la tabla las filas son otras.
    const alternar = (id) => setElegidos(previos => {
        const s = new Set(previos);
        if (s.has(id)) s.delete(id); else s.add(id);
        return s;
    });
    const elegirLosDeLaLista = () => setElegidos(new Set(filtered.map(r => r.client_id)));
    const todosElegidos = filtered.length > 0 && filtered.every(r => elegidos.has(r.client_id));

    // Cada columna se enseña solo si tiene algo que decir: «o se rellenan o se quitan».
    // Los DÍAS solo los tiene la rutina estructurada (un PDF no se puede abrir por dentro),
    // así que colgarla de `withRoutine` -- que desde el 24-08 cuenta también los PDF --
    // dejaba esa columna entera a guiones en una casa que entregue todo en PDF. La FECHA la
    // tienen las dos, y la del PDF es la que dice si esa rutina es de este mes o de marzo.
    const hayDias = rows.some(r => r.routine_created_at);
    const hayFechas = hayDias || rows.some(r => r.pdf_uploaded_at);
    const columnas = 5 + (hayDias ? 1 : 0) + (hayFechas ? 1 : 0);

    if (loading) return <div className="p-6 bg-[#0A0A0A] min-h-screen"><div className="animate-pulse space-y-4"><div className="h-8 bg-[#222] rounded w-1/4" /><div className="h-96 bg-[#111] rounded-xl" /></div></div>;

    return (
        <div className="p-4 md:p-6 space-y-5 animate-fade-in bg-[#0A0A0A] min-h-screen" data-testid="admin-routines-page">
            <div>
                <h1 className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: 'Barlow Condensed' }}>RUTINAS</h1>
                <p className="text-white/40 text-sm">
                    {/* «Con rutina puesta» y no «activa»: desde el 24-08 cuenta también la
                        entregada en PDF, que es la vía de entrega real (bloque 11, 19-08). */}
                    {withRoutine} de {rows.length} clientes con rutina puesta
                    {rows.length - withRoutine > 0 && <span className="text-yellow-400"> · {rows.length - withRoutine} sin rutina</span>}
                </p>
                {/* El número que de verdad es una tarea: a los demás no se les prometió. */}
                {laLlevanSinRutina > 0 && (
                    <p className="text-white/60 text-sm mt-1" data-testid="rutinas-prometidas">
                        <span className="text-[#FF671F] font-semibold">{laLlevanSinRutina}</span>
                        {' '}de ellos la tienen incluida en su plan y todavía no la tienen puesta. Van primero en la lista.
                    </p>
                )}
                {personalizadasPendientes.length > 0 && (
                    <p className="text-white/60 text-sm mt-1" data-testid="rutinas-personalizadas-pendientes">
                        <span className="text-[#FF671F] font-semibold">{personalizadasPendientes.length}</span>
                        {' '}esperan una rutina PERSONALIZADA: la suya, no la del mes.
                        <button onClick={() => { setSoloPersonalizadas(true); setSoloDelMes(false); setOnlyMissing(true); }}
                            data-testid="ver-personalizadas-pendientes"
                            className="ml-2 text-[#FF671F] hover:underline">verlos</button>
                    </p>
                )}
                {/* YA NO HAY QUE SUBÍRSELA A NADIE (25-08). Esta línea decía «a estos se
                    les sube el mismo PDF a todos» y era verdad hasta hoy: había que
                    marcarlos y subir en dos tandas. Desde que la del mes se deja en su
                    caja, les llega sola, así que la lista de abajo cuenta a los que no
                    tienen NINGÚN PDF suyo, que no es lo mismo que estar sin rutina. */}
                {delMesPendientes.length > 0 && (
                    <p className="text-white/60 text-sm mt-1" data-testid="rutinas-del-mes-pendientes">
                        <span className="text-[#FF671F] font-semibold">{delMesPendientes.length}</span>
                        {' '}llevan LA DEL MES en su plan: les llega sola en cuanto esté aquí abajo.
                        <button onClick={() => { setSoloDelMes(true); setSoloPersonalizadas(false); setOnlyMissing(true); }}
                            data-testid="ver-del-mes-pendientes"
                            className="ml-2 text-[#FF671F] hover:underline">verlos</button>
                    </p>
                )}
            </div>

            <LaRutinaDelMes api={api} onHecho={recargar} />

            <BibliotecaDeRutinas api={api} />

            <PonerlesRutinaAVarios api={api} onHecho={recargar} />

            {elegidos.size > 0 && (
                <SubirPdfAVarios api={api} ids={[...elegidos]}
                    onLimpiar={() => setElegidos(new Set())}
                    onHecho={() => { setElegidos(new Set()); recargar(); }} />
            )}

            <div className="flex flex-col md:flex-row gap-3">
                <div className="relative flex-1 max-w-sm">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                    <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar cliente..." className="pl-9 bg-[#111] border-[#222] text-white" data-testid="routines-search" />
                </div>
                <button onClick={() => setOnlyMissing(v => !v)}
                    className={`px-4 py-2 rounded-lg text-sm font-semibold border transition-colors ${onlyMissing ? 'bg-[#FF671F] text-white border-[#FF671F]' : 'bg-[#111] text-white/60 border-[#222] hover:text-white'}`}
                    data-testid="only-missing-toggle">
                    Solo sin rutina
                </button>
                {/* Excluyentes: un plan no puede ser «del mes» y «personalizada» a la vez, y
                    con los dos puestos la tabla se quedaba vacía sin explicar por qué. */}
                <button onClick={() => { setSoloPersonalizadas(v => !v); setSoloDelMes(false); }}
                    className={`px-4 py-2 rounded-lg text-sm font-semibold border transition-colors ${soloPersonalizadas ? 'bg-[#FF671F] text-white border-[#FF671F]' : 'bg-[#111] text-white/60 border-[#222] hover:text-white'}`}
                    data-testid="only-personalizada-toggle">
                    Solo personalizada
                </button>
                <button onClick={() => { setSoloDelMes(v => !v); setSoloPersonalizadas(false); }}
                    className={`px-4 py-2 rounded-lg text-sm font-semibold border transition-colors ${soloDelMes ? 'bg-[#FF671F] text-white border-[#FF671F]' : 'bg-[#111] text-white/60 border-[#222] hover:text-white'}`}
                    data-testid="only-del-mes-toggle">
                    Solo la del mes
                </button>
                {filtered.length > 0 && (
                    <button onClick={() => (todosElegidos ? setElegidos(new Set()) : elegirLosDeLaLista())}
                        className="px-4 py-2 rounded-lg text-sm font-semibold border bg-[#111] text-white/60 border-[#222] hover:text-white transition-colors"
                        data-testid="elegir-los-de-la-lista">
                        {todosElegidos ? 'Quitar la selección' : `Elegir los ${filtered.length} de la lista`}
                    </button>
                )}
            </div>

            <Card className="bg-[#111] border-[#222]">
                <CardContent className="p-0">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-white/40 text-xs uppercase border-b border-[#222]">
                                    <th className="pl-4 pr-1 py-3 w-8">
                                        <input type="checkbox" checked={todosElegidos} data-testid="elegir-todos"
                                            onChange={() => (todosElegidos ? setElegidos(new Set()) : elegirLosDeLaLista())}
                                            className="accent-[#FF671F] w-4 h-4 align-middle" />
                                    </th>
                                    <th className="px-4 py-3">Cliente</th>
                                    <th className="px-4 py-3 hidden sm:table-cell">Plan</th>
                                    <th className="px-4 py-3">Rutina</th>
                                    {hayDias && <th className="px-4 py-3 hidden md:table-cell">Días de entreno</th>}
                                    {hayFechas && <th className="px-4 py-3 hidden lg:table-cell">Generada</th>}
                                    <th className="px-4 py-3 text-right"></th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map(r => (
                                    <tr key={r.client_id} className="border-b border-[#1a1a1a] cursor-pointer hover:bg-white/5"
                                        onClick={() => navigate(`/admin/clients/${r.client_id}`)} data-testid={`routine-row-${r.client_id}`}>
                                        {/* La casilla no abre la ficha: sin el stopPropagation, marcar
                                            a alguien te saca de la pantalla y pierdes la selección. */}
                                        <td className="pl-4 pr-1 py-3" onClick={e => e.stopPropagation()}>
                                            <input type="checkbox" checked={elegidos.has(r.client_id)}
                                                onChange={() => alternar(r.client_id)}
                                                data-testid={`elegir-${r.client_id}`}
                                                className="accent-[#FF671F] w-4 h-4 align-middle" />
                                        </td>
                                        <td className="px-4 py-3">
                                            <p className="text-white font-medium">{r.name || '-'}</p>
                                            <p className="text-white/40 text-xs">{r.email}</p>
                                        </td>
                                        <td className="px-4 py-3 hidden sm:table-cell">
                                            <PlanBadge plan={r.plan} />
                                            {laLlevaEnSuPlan(r.plan) && (
                                                <span className="ml-2 text-[9px] uppercase font-bold tracking-wide text-[#FF671F] bg-[#FF671F]/15 px-1.5 py-0.5 rounded">
                                                    {esPersonalizada(r.plan) ? 'personalizada' : esDelMes(r.plan) ? 'la del mes' : 'la lleva'}
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3">
                                            {/* «En PDF» no es lo mismo que «Activa»: la entregada en PDF no
                                                se puede abrir por dentro desde aquí, pero está puesta y no
                                                es trabajo pendiente. */}
                                            {r.routine_created_at
                                                ? <Badge className="bg-green-500/15 text-green-500 border-0">Activa</Badge>
                                                : r.tiene_pdf
                                                    ? <Badge className="bg-green-500/15 text-green-500 border-0">En PDF</Badge>
                                                    : <Badge className={`border-0 ${laLlevaEnSuPlan(r.plan) ? 'bg-red-500/15 text-red-400' : 'bg-white/5 text-white/40'}`}>
                                                        Sin rutina
                                                    </Badge>}
                                        </td>
                                        {hayDias && <td className="px-4 py-3 text-white/60 hidden md:table-cell">{r.training_days ? `${r.training_days} días` : '-'}</td>}
                                        {hayFechas && (
                                            <td className="px-4 py-3 text-white/40 text-xs hidden lg:table-cell">
                                                {r.routine_created_at || r.pdf_uploaded_at
                                                    ? new Date(r.routine_created_at || r.pdf_uploaded_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })
                                                    : '-'}
                                            </td>
                                        )}
                                        <td className="px-4 py-3 text-right"><ChevronRight className="w-4 h-4 text-white/30 inline" /></td>
                                    </tr>
                                ))}
                                {filtered.length === 0 && (
                                    <tr><td colSpan={columnas} className="px-4 py-10 text-center text-white/30">
                                        <Dumbbell className="w-8 h-8 mx-auto mb-2 text-white/15" />
                                        {/* Con el filtro de personalizada puesto, «todos los
                                            clientes tienen rutina» es falso: son los de ese
                                            filtro, y decirlo mal deja pensando que no queda
                                            trabajo cuando sí queda. */}
                                        {!onlyMissing ? 'Sin clientes'
                                            : soloPersonalizadas ? 'Todos los de rutina personalizada tienen la suya'
                                                : soloDelMes ? 'Todos los de la rutina del mes ya la tienen'
                                                    : 'Todos los clientes tienen rutina'}
                                    </td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
            {/* Decía «se genera y EDITA en la ficha» y la ficha no la edita: la pinta. Para
                cambiarle un ejercicio a alguien hay que volver a generarla o asignarle otra
                plantilla. Mientras no exista el editor por cliente, aquí no se promete. */}
            <p className="text-white/25 text-xs">La rutina se genera y se asigna desde la ficha del cliente, pestaña Entreno.</p>
        </div>
    );
};

export default AdminRoutinesPage;
