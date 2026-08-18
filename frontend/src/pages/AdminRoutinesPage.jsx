import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Search, Dumbbell, ChevronRight, Users } from 'lucide-react';
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
                                <div key={r.id} className="flex items-center justify-between gap-3 p-3 bg-[#0A0A0A] rounded-lg border border-[#222]">
                                    <div className="min-w-0">
                                        <p className="text-white text-sm">{r.nombre}</p>
                                        <p className="text-white/40 text-xs">
                                            {r.dias_de_entreno} {r.dias_de_entreno === 1 ? 'día' : 'días'} · {r.ejercicios} ejercicios
                                            {r.objetivo ? ` · ${r.objetivo}` : ''}{r.nivel ? ` · ${r.nivel}` : ''}
                                            {r.updated_by ? ` · la escribió ${r.updated_by}` : ''}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-3 shrink-0">
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

// Vista general de rutinas: quien tiene rutina activa y quien no.
// La rutina se genera/edita dentro de la ficha del cliente (pestaña Entreno).
const AdminRoutinesPage = () => {
    const { api, planCatalog } = useAuth();
    const navigate = useNavigate();
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [onlyMissing, setOnlyMissing] = useState(false);

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
    const pagaRutina = (plan) => {
        const r = planCatalog?.[plan]?.habilitaciones?.rutina;
        return Boolean(r) && r !== 'ninguna';
    };

    const filtered = rows.filter(r =>
        (!onlyMissing || !r.has_routine) &&
        (!search || r.name?.toLowerCase().includes(search.toLowerCase()) || r.email?.toLowerCase().includes(search.toLowerCase()))
    ).sort((a, b) => {
        const pa = pagaRutina(a.plan), pb = pagaRutina(b.plan);
        if (pa !== pb) return pa ? -1 : 1;
        // Dentro de cada grupo, el que aún no la tiene primero: es el que hay que atender.
        if (a.has_routine !== b.has_routine) return a.has_routine ? 1 : -1;
        return (a.name || '').localeCompare(b.name || '', 'es');
    });
    const withRoutine = rows.filter(r => r.has_routine).length;
    const laPagan = rows.filter(r => pagaRutina(r.plan));
    const laPaganSinRutina = laPagan.filter(r => !r.has_routine).length;

    // Las dos columnas solo hablan de rutinas que existen. Si no hay ninguna, son dos
    // columnas de guiones: «o se rellenan o se quitan», y aquí se quitan solas en cuanto
    // no hay nada que enseñar, y vuelven cuando lo haya.
    const hayRutinas = withRoutine > 0;

    if (loading) return <div className="p-6 bg-[#0A0A0A] min-h-screen"><div className="animate-pulse space-y-4"><div className="h-8 bg-[#222] rounded w-1/4" /><div className="h-96 bg-[#111] rounded-xl" /></div></div>;

    return (
        <div className="p-4 md:p-6 space-y-5 animate-fade-in bg-[#0A0A0A] min-h-screen" data-testid="admin-routines-page">
            <div>
                <h1 className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: 'Barlow Condensed' }}>RUTINAS</h1>
                <p className="text-white/40 text-sm">
                    {withRoutine} de {rows.length} clientes con rutina activa
                    {rows.length - withRoutine > 0 && <span className="text-yellow-400"> · {rows.length - withRoutine} sin rutina</span>}
                </p>
                {/* El número que de verdad es una tarea: a los demás no se les prometió. */}
                {laPaganSinRutina > 0 && (
                    <p className="text-white/60 text-sm mt-1" data-testid="rutinas-prometidas">
                        <span className="text-[#FF671F] font-semibold">{laPaganSinRutina}</span>
                        {' '}de ellos la tienen incluida en su plan y todavía no la tienen puesta. Van primero en la lista.
                    </p>
                )}
            </div>

            <BibliotecaDeRutinas api={api} />

            <PonerlesRutinaAVarios api={api} onHecho={recargar} />

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
            </div>

            <Card className="bg-[#111] border-[#222]">
                <CardContent className="p-0">
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-left text-white/40 text-xs uppercase border-b border-[#222]">
                                    <th className="px-4 py-3">Cliente</th>
                                    <th className="px-4 py-3 hidden sm:table-cell">Plan</th>
                                    <th className="px-4 py-3">Rutina</th>
                                    {hayRutinas && <th className="px-4 py-3 hidden md:table-cell">Días de entreno</th>}
                                    {hayRutinas && <th className="px-4 py-3 hidden lg:table-cell">Generada</th>}
                                    <th className="px-4 py-3 text-right"></th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map(r => (
                                    <tr key={r.client_id} className="border-b border-[#1a1a1a] cursor-pointer hover:bg-white/5"
                                        onClick={() => navigate(`/admin/clients/${r.client_id}`)} data-testid={`routine-row-${r.client_id}`}>
                                        <td className="px-4 py-3">
                                            <p className="text-white font-medium">{r.name || '-'}</p>
                                            <p className="text-white/40 text-xs">{r.email}</p>
                                        </td>
                                        <td className="px-4 py-3 hidden sm:table-cell">
                                            <PlanBadge plan={r.plan} />
                                            {pagaRutina(r.plan) && (
                                                <span className="ml-2 text-[9px] uppercase font-bold tracking-wide text-[#FF671F] bg-[#FF671F]/15 px-1.5 py-0.5 rounded">
                                                    la paga
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3">
                                            {r.has_routine
                                                ? <Badge className="bg-green-500/15 text-green-500 border-0">Activa</Badge>
                                                : <Badge className={`border-0 ${pagaRutina(r.plan) ? 'bg-red-500/15 text-red-400' : 'bg-white/5 text-white/40'}`}>
                                                    Sin rutina
                                                </Badge>}
                                        </td>
                                        {hayRutinas && <td className="px-4 py-3 text-white/60 hidden md:table-cell">{r.has_routine ? `${r.training_days} días` : '-'}</td>}
                                        {hayRutinas && (
                                            <td className="px-4 py-3 text-white/40 text-xs hidden lg:table-cell">
                                                {r.routine_created_at ? new Date(r.routine_created_at).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' }) : '-'}
                                            </td>
                                        )}
                                        <td className="px-4 py-3 text-right"><ChevronRight className="w-4 h-4 text-white/30 inline" /></td>
                                    </tr>
                                ))}
                                {filtered.length === 0 && (
                                    <tr><td colSpan={hayRutinas ? 6 : 4} className="px-4 py-10 text-center text-white/30">
                                        <Dumbbell className="w-8 h-8 mx-auto mb-2 text-white/15" />
                                        {onlyMissing ? 'Todos los clientes tienen rutina' : 'Sin clientes'}
                                    </td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
            <p className="text-white/25 text-xs">La rutina se genera y edita dentro de la ficha del cliente, pestaña Entreno.</p>
        </div>
    );
};

export default AdminRoutinesPage;
