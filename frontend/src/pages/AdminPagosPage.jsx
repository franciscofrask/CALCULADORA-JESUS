/**
 * EL HISTORIAL DE COBROS, SOLO PARA EL ADMINISTRADOR.
 *
 * Francisco, 13-08-2026: «algo que quiero es un log de pagos en la app que solo pueda
 * verlo un administrador».
 *
 * Ojo con lo que es y lo que no: esto NO es la facturación viva (de cobrar hoy se encarga
 * Stripe, y eso está en Planes). Esto es lo que cada cliente ha pagado desde 2019, que
 * estaba repartido entre las facturas de Holded, los pedidos de ThriveCart y los eventos
 * de Stripe, y que hasta ahora no se veía en ninguna parte de la app.
 *
 * POR QUÉ SOLO EL ADMIN. Desde el 21-07 los entrenadores ven y gestionan a todos los
 * clientes, así que casi todo el panel está abierto a los dos roles. Lo que alguien ha
 * pagado no es información de entrenamiento, es del negocio: va con el mismo candado que
 * la pestaña de Usuarios, y el backend lo comprueba otra vez por su cuenta.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Receipt, Search, X, Loader2, TrendingUp } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { conceptoDeCobro, prettyToken } from '../lib/labels';

const ORIGENES = [
    { id: '', nombre: 'Todos' },
    { id: 'holded', nombre: 'Holded' },
    { id: 'thrivecart', nombre: 'ThriveCart' },
    { id: 'stripe', nombre: 'Stripe' },
];

// El nombre de un origen tal y como se escribe («thrivecart» -> «ThriveCart»).
const nombreOrigen = (id) => (ORIGENES.find((o) => o.id === id) || {}).nombre || id;

// El color dice de dónde viene el cobro sin tener que leerlo. Tres orígenes, tres tonos
// del mismo sitio de la paleta: no compiten con el naranja de la marca.
const COLOR_ORIGEN = {
    holded: 'bg-sky-500/10 text-sky-600 dark:text-sky-400',
    thrivecart: 'bg-violet-500/10 text-violet-600 dark:text-violet-400',
    stripe: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
};

const euros = (n, moneda = 'EUR') => {
    const v = Number(n || 0);
    try {
        return v.toLocaleString('es-ES', { style: 'currency', currency: moneda || 'EUR' });
    } catch {
        return `${v.toFixed(2)} ${moneda || 'EUR'}`;
    }
};

const fecha = (f) => {
    if (!f) return '-';
    const d = new Date(f);
    return Number.isNaN(d.getTime()) ? String(f).slice(0, 10)
        : d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' });
};

const AdminPagosPage = () => {
    const { api } = useAuth();
    const [resumen, setResumen] = useState(null);
    const [datos, setDatos] = useState(null);
    const [cargando, setCargando] = useState(true);
    const [error, setError] = useState('');

    const [busqueda, setBusqueda] = useState('');
    const [origen, setOrigen] = useState('');
    const [desde, setDesde] = useState('');
    const [hasta, setHasta] = useState('');
    const [pagina, setPagina] = useState(1);

    // Lo que se escribe no dispara una consulta por tecla: se espera a que pare. Sin esto,
    // teclear un correo de 20 letras son 20 consultas a una colección de miles de cobros.
    const [filtroEmail, setFiltroEmail] = useState('');
    useEffect(() => {
        const t = setTimeout(() => { setFiltroEmail(busqueda.trim()); setPagina(1); }, 350);
        return () => clearTimeout(t);
    }, [busqueda]);

    useEffect(() => {
        let vivo = true;
        api.get('/admin/pagos/resumen')
            .then((r) => { if (vivo) setResumen(r.data); })
            .catch(() => { /* el resumen es un extra: si falla, la lista manda */ });
        return () => { vivo = false; };
    }, [api]);

    const cargar = useCallback(async () => {
        setCargando(true);
        setError('');
        try {
            const params = { pagina };
            if (filtroEmail) params.email = filtroEmail;
            if (origen) params.origen = origen;
            if (desde) params.desde = desde;
            if (hasta) params.hasta = hasta;
            const r = await api.get('/admin/pagos', { params });
            setDatos(r.data);
        } catch (e) {
            // Al usuario no se le enseña una traza ni el detalle del backend: frase humana
            // aquí y el detalle a la consola, que es donde sirve.
            console.error('[pagos] no se pudo cargar el historial', e);
            setError('No hemos podido cargar el historial de cobros. Vuelve a intentarlo.');
        } finally {
            setCargando(false);
        }
    }, [api, pagina, filtroEmail, origen, desde, hasta]);

    useEffect(() => { cargar(); }, [cargar]);

    const hayFiltro = filtroEmail || origen || desde || hasta;
    const limpiar = () => {
        setBusqueda(''); setFiltroEmail(''); setOrigen(''); setDesde(''); setHasta(''); setPagina(1);
    };

    const totalFiltrado = useMemo(() => {
        if (!datos?.sumas?.length) return null;
        return datos.sumas.map((s) => euros(s.total, s.moneda)).join(' · ');
    }, [datos]);

    return (
        <div className="space-y-6">
            <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                    {/* BLANCO, NO `text-foreground`. Esta pantalla era la única del panel
                        escrita con las fichas del tema, y `AdminLayout` fija el fondo
                        oscuro a mano: en modo claro el título salía en negro sobre negro y
                        NO SE VEÍA (QA del 15-08 en producción). El resto del panel usa
                        `text-white` para lo que va directo sobre ese fondo; lo que vive
                        dentro de una tarjeta `surface` sí puede seguir con el tema. */}
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Receipt className="w-6 h-6 text-brand" /> Historial de cobros
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Lo que ha pagado cada cliente, de Holded, ThriveCart y Stripe. Solo lo ves tú.
                    </p>
                </div>
            </div>

            {/* Las cuatro cifras de arriba. Si todavía no se ha importado el histórico, la
                pantalla lo dice en vez de enseñar ceros sin explicación. */}
            {resumen && !resumen.hay_datos && (
                <div className="surface p-5 border-l-4 border-amber-500">
                    <p className="text-sm text-foreground font-semibold">Todavía no hay histórico importado</p>
                    <p className="text-sm text-muted-foreground mt-1">
                        Los cobros de Holded, ThriveCart y Stripe aún no se han traído a la app.
                    </p>
                </div>
            )}

            {resumen?.hay_datos && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="surface p-4">
                        <p className="caption">Cobros</p>
                        <p className="text-2xl font-bold text-foreground font-data mt-1">{resumen.total}</p>
                    </div>
                    <div className="surface p-4">
                        <p className="caption">Clientes</p>
                        <p className="text-2xl font-bold text-foreground font-data mt-1">{resumen.clientes}</p>
                    </div>
                    <div className="surface p-4">
                        <p className="caption">Último cobro</p>
                        <p className="text-lg font-semibold text-foreground mt-1">{fecha(resumen.ultimo_cobro)}</p>
                    </div>
                    <div className="surface p-4">
                        <p className="caption">Total facturado</p>
                        <p className="text-2xl font-bold text-brand font-data mt-1">
                            {euros(resumen.por_origen.reduce((s, o) => s + (o.importe || 0), 0))}
                        </p>
                    </div>
                </div>
            )}

            {/* QUÉ NO SE ESTÁ CONTANDO, dicho en voz alta.
                Holded no es una pasarela: es la facturación, así que cada cobro de Stripe
                o ThriveCart aparece además como factura. Contándolo todo salían 416.196 €
                cuando el dinero que entró de verdad son 332.022. Un panel que esconde
                filas sin explicarlo obliga a fiarse; diciendo cuántas y por qué, se puede
                comprobar. */}
            {resumen?.hay_datos && (resumen.fuera?.copias > 0 || resumen.fuera?.eventos_sin_dinero > 0) && (
                <p className="text-xs text-muted-foreground" data-testid="pagos-excluidos">
                    {/* AL REVÉS DE COMO ESTABA. Decía «que Holded factura» y justo debajo
                        enseñaba «HOLDED (353)»: los de Holded son los que SÍ se cuentan, y
                        lo que se deja fuera es la fila de la pasarela, que es el mismo
                        dinero por el otro camino. Que las dos cifras fueran 353 lo hacía
                        peor (QA del 15-08). Los nombres vienen del backend para que la
                        frase no se quede vieja si cambian las pasarelas. */}
                    No se cuentan {resumen.fuera.copias} cobros
                    {resumen.fuera.origenes?.length
                        ? ` de ${resumen.fuera.origenes.map(nombreOrigen).join(' y ')}`
                        : ''} que Holded ya factura (el mismo dinero por dos caminos)
                    {resumen.fuera.eventos_sin_dinero > 0 && `, ni ${resumen.fuera.eventos_sin_dinero} avisos sin cobro (cancelaciones, pausas y pagos fallidos)`}.
                </p>
            )}

            {resumen?.hay_datos && resumen.por_origen?.length > 0 && (
                <div className="surface p-4">
                    <p className="caption mb-3 flex items-center gap-1.5">
                        <TrendingUp className="w-3.5 h-3.5" /> Por origen
                    </p>
                    <div className="flex flex-wrap gap-3">
                        {resumen.por_origen.map((o) => (
                            <div key={o.origen} className="flex items-center gap-2">
                                <span className={`text-[11px] px-2 py-0.5 rounded-md font-semibold uppercase tracking-wide ${COLOR_ORIGEN[o.origen] || 'bg-muted text-muted-foreground'}`}>
                                    {o.origen}
                                </span>
                                <span className="text-sm text-foreground font-data">{euros(o.importe)}</span>
                                <span className="text-xs text-muted-foreground">({o.n})</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Filtros */}
            <div className="surface p-4 flex flex-wrap items-end gap-3">
                <div className="flex-1 min-w-[220px]">
                    <label className="caption block mb-1.5" htmlFor="pagos-buscar">Cliente</label>
                    <div className="relative">
                        <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                        <input id="pagos-buscar" type="text" value={busqueda} data-testid="pagos-buscar"
                            onChange={(e) => setBusqueda(e.target.value)}
                            placeholder="Correo del cliente"
                            className="w-full bg-muted border border-border rounded-lg pl-9 pr-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand/40" />
                    </div>
                </div>
                <div>
                    <label className="caption block mb-1.5" htmlFor="pagos-origen">Origen</label>
                    <select id="pagos-origen" value={origen} data-testid="pagos-origen"
                        onChange={(e) => { setOrigen(e.target.value); setPagina(1); }}
                        className="bg-muted border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-brand/40">
                        {ORIGENES.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}
                    </select>
                </div>
                <div>
                    <label className="caption block mb-1.5" htmlFor="pagos-desde">Desde</label>
                    <input id="pagos-desde" type="date" value={desde}
                        onChange={(e) => { setDesde(e.target.value); setPagina(1); }}
                        className="bg-muted border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-brand/40" />
                </div>
                <div>
                    <label className="caption block mb-1.5" htmlFor="pagos-hasta">Hasta</label>
                    <input id="pagos-hasta" type="date" value={hasta}
                        onChange={(e) => { setHasta(e.target.value); setPagina(1); }}
                        className="bg-muted border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-brand/40" />
                </div>
                {hayFiltro && (
                    <button onClick={limpiar} data-testid="pagos-limpiar"
                        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground px-3 py-2">
                        <X className="w-4 h-4" /> Quitar filtros
                    </button>
                )}
            </div>

            {/* El total de LO FILTRADO, que es lo que se mira de verdad al buscar un cliente */}
            {datos && totalFiltrado && (
                <p className="text-sm text-muted-foreground" data-testid="pagos-total">
                    {/* Igual que el título: va directo sobre el fondo del panel. */}
                    <span className="text-white font-semibold">{datos.total}</span>
                    {datos.total === 1 ? ' cobro' : ' cobros'}
                    {hayFiltro ? ' con estos filtros' : ''} · <span className="text-brand font-semibold font-data">{totalFiltrado}</span>
                </p>
            )}

            {error && (
                <div className="surface p-5 border-l-4 border-red-500">
                    <p className="text-sm text-foreground">{error}</p>
                </div>
            )}

            {/* La tabla se desplaza sola en horizontal: el móvil no puede empujar la página */}
            <div className="surface overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-border">
                                <th className="text-left px-4 py-3 caption">Fecha</th>
                                <th className="text-left px-4 py-3 caption">Cliente</th>
                                <th className="text-left px-4 py-3 caption">Concepto</th>
                                <th className="text-left px-4 py-3 caption">Origen</th>
                                <th className="text-right px-4 py-3 caption">Importe</th>
                            </tr>
                        </thead>
                        <tbody data-testid="pagos-tabla">
                            {cargando && (
                                <tr><td colSpan={5} className="px-4 py-10 text-center text-muted-foreground">
                                    <Loader2 className="w-5 h-5 animate-spin inline" />
                                </td></tr>
                            )}
                            {!cargando && !datos?.pagos?.length && (
                                <tr><td colSpan={5} className="px-4 py-10 text-center text-muted-foreground">
                                    {hayFiltro ? 'Ningún cobro con estos filtros' : 'Todavía no hay cobros registrados'}
                                </td></tr>
                            )}
                            {!cargando && datos?.pagos?.map((p) => (
                                <tr key={p.id || `${p.referencia}-${p.fecha}`} className="border-b border-border last:border-0 hover:bg-muted/40">
                                    <td className="px-4 py-3 text-muted-foreground whitespace-nowrap font-data">{fecha(p.fecha)}</td>
                                    <td className="px-4 py-3">
                                        <p className="text-foreground font-medium">{p.nombre || '-'}</p>
                                        <p className="text-xs text-muted-foreground">{p.email}</p>
                                    </td>
                                    {/* El concepto llega de la pasarela y en inglés: «1 x El Lunes
                                        Empiezo (at €81.07 / month)» (#64 del 15-08). Se traduce al
                                        pintarlo; el dato guardado no se toca, que es el que cuadra
                                        con Stripe si hay que reclamar algo. */}
                                    <td className="px-4 py-3 text-muted-foreground">
                                        {conceptoDeCobro(p.concepto || p.sku)}
                                        {p.tipo && p.tipo !== 'pago' && (
                                            <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 uppercase tracking-wide font-semibold">
                                                {prettyToken(p.tipo)}
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className={`text-[11px] px-2 py-0.5 rounded-md font-semibold uppercase tracking-wide ${COLOR_ORIGEN[p.origen] || 'bg-muted text-muted-foreground'}`}>
                                            {p.origen || '?'}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-right font-data font-semibold text-foreground whitespace-nowrap">
                                        {euros(p.importe, p.moneda)}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {datos && datos.paginas > 1 && (
                <div className="flex items-center justify-between">
                    <button disabled={pagina <= 1} onClick={() => setPagina((p) => p - 1)}
                        className="px-4 py-2 text-sm rounded-lg border border-border text-foreground disabled:opacity-40 disabled:cursor-not-allowed hover:bg-muted">
                        Anteriores
                    </button>
                    <span className="text-sm text-muted-foreground font-data">
                        {pagina} de {datos.paginas}
                    </span>
                    <button disabled={pagina >= datos.paginas} onClick={() => setPagina((p) => p + 1)}
                        className="px-4 py-2 text-sm rounded-lg border border-border text-foreground disabled:opacity-40 disabled:cursor-not-allowed hover:bg-muted">
                        Siguientes
                    </button>
                </div>
            )}
        </div>
    );
};

export default AdminPagosPage;
