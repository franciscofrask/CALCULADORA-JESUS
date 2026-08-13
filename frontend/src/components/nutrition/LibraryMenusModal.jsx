/**
 * LibraryMenusModal - "Elige tu menú": UNA sola lista con todo lo que se puede elegir.
 *
 * Hasta el 13-08-2026 esto eran dos pestañas, Biblioteca y Recetario, y Francisco pidió
 * juntarlas: «unifica el recetario con la biblioteca, que ya no estén separados». Para
 * quien elige la comida son lo mismo -- menús que puede meterse en el plato --, y la
 * diferencia era nuestra, no suya:
 *
 * 1. Recetas del recetario ELM (`menu_templates`): no traen cantidades cerradas, así que
 *    al elegir una el motor la cuadra a tus macros (POST /calculator/menu-apply). Traen
 *    foto y nombre de plato.
 * 2. Menús reales (`meal_library`, 266k comidas de clientes ya cuadradas con el método):
 *    vienen con las cantidades puestas y se vuelcan tal cual. Filosofía (nota 2026-07-16):
 *    cercanía, no exactitud.
 *
 * Esa diferencia sigue existiendo por dentro -- cada tarjeta hace lo suyo al pulsarla --,
 * pero ya no se le pide al cliente que elija primero de qué cajón quiere sacar la comida.
 *
 * EL ORDEN: primero las recetas, después los menús reales. No es capricho ni es alfabético:
 * las recetas son material terminado de Jesús (con su foto y su enlace) y los menús reales
 * son comidas de relleno sacadas de dietas. Ordenar los dos juntos por lo bien que encajan
 * habría sido mejor, y se midió: cuadrar las 159 recetas contra un objetivo cuesta 52 s,
 * así que no se puede hacer mientras el cliente espera. Los menús reales sí llegan ya
 * ordenados por cercanía, porque eso lo hace el servidor.
 *
 * Y LA CARGA VA EN PARALELO. Antes la biblioteca solo se pedía al entrar en su pestaña y
 * podía tardar más de 30 segundos (Jesús se quedó mirándola). Ahora se pide al abrir, a la
 * vez que el recetario: la lista se puede usar desde el primer segundo con las recetas, y
 * los menús reales se suman abajo cuando llegan.
 */
import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Input } from '../ui/input';
import { Search, X, Check } from 'lucide-react';
import { BIBLIOTECA_DE_CLIENTES } from '../../lib/menuFuentes';

const normalizar = (s) => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

const MACRO_STYLE = {
    P: 'text-red-500',
    H: 'text-blue-500',
    G: 'text-yellow-500',
};

const MACRO_NOMBRE = {
    P: 'proteína',
    H: 'hidratos',
    G: 'grasa',
};

// A partir de esta desviación (g por macro) la receta NO se vuelca sin que el usuario
// lo vea: se le enseña de cuánto se pasa y decide. Mismo umbral laxo que usa el motor
// (MARGEN_MENU_RELAX en backend/meal_templates.py). El recetario va en best_effort, o sea
// que el backend nunca rechaza la receta elegida; este es el único freno que hay.
const MARGEN_AVISO = 12;

// Macros que se salen del margen al cuadrar la receta, con su diferencia en gramos
// (positiva = te pasas, negativa = te falta).
const desviosFuera = (totales, objetivo) => ['P', 'H', 'G']
    .map(m => ({ m, diff: Math.round(((totales?.[m] || 0) - (objetivo?.[m] || 0)) * 10) / 10 }))
    .filter(d => Math.abs(d.diff) > MARGEN_AVISO);

// Momentos del recetario (campo `momento` de menu_templates) -> etiqueta del chip
const MOMENTO_LABEL = {
    desayuno: 'Desayunos',
    comida: 'Comidas',
    merienda: 'Meriendas',
    cena: 'Cenas',
};

const MacroTrio = ({ macros, size = 'lg' }) => (
    <div className="flex items-start gap-3">
        {['P', 'H', 'G'].map(m => (
            <div key={m} className="text-center leading-none">
                <span className={`font-black ${size === 'lg' ? 'text-xl' : 'text-sm'} ${MACRO_STYLE[m]}`}>
                    {Math.round((macros?.[m] || 0) * 10) / 10}
                </span>
                <span className="block text-[9px] font-bold text-muted-foreground mt-0.5">{m}</span>
            </div>
        ))}
    </div>
);

const LibraryMenusModal = ({ open, mealKey, onClose, mealInfo, target, api, dayConfig, onApply }) => {
    const [margen, setMargen] = React.useState(5);
    const [orden, setOrden] = React.useState('cuadrado');
    const [verReales, setVerReales] = React.useState(false);
    const [textFilter, setTextFilter] = React.useState('');
    const [menus, setMenus] = React.useState([]);
    const [sinCosechar, setSinCosechar] = React.useState(false);
    const [total, setTotal] = React.useState(0);
    const [objetivo, setObjetivo] = React.useState(null);
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState(null);
    const [applying, setApplying] = React.useState(false);

    // Pestaña "Recetario": catálogo de recetas ELM (se carga la primera vez que se abre)
    const [recetario, setRecetario] = React.useState(null);
    const [recetarioMomentos, setRecetarioMomentos] = React.useState([]);
    const [recetarioLoading, setRecetarioLoading] = React.useState(false);
    const [recetarioError, setRecetarioError] = React.useState(null);
    const [momento, setMomento] = React.useState('todos');
    const [aplicandoId, setAplicandoId] = React.useState(null);
    // Receta ya cuadrada pero lejos del objetivo, esperando el OK del usuario
    const [confirmacion, setConfirmacion] = React.useState(null);

    React.useEffect(() => {
        if (open) {
            setTextFilter('');
            setVerReales(false);
            setError(null);
            setRecetarioError(null);
            setMomento('todos');
            setConfirmacion(null);
        }
    }, [open, mealKey]);

    React.useEffect(() => {
        if (!open || !mealKey || !BIBLIOTECA_DE_CLIENTES) return;
        let cancelado = false;
        const cargar = async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await api('/api/calculator/library-menus', {
                    method: 'POST',
                    body: JSON.stringify({
                        mealKey,
                        // El objetivo lo define la calculadora; si aún no hay reparto
                        // (0/0/0), el backend reparte el día con la config actual.
                        macros_objetivo: target ? { P: target.P, H: target.H, G: target.G } : {},
                        margen,
                        orden,
                        // Suficiente para que el slider del margen se note: con 40 se
                        // llegaba al tope enseguida y ampliar el margen no cambiaba
                        // nada de lo que se veía.
                        limit: 120,
                        ...(dayConfig || {}),
                    }),
                });
                if (cancelado) return;
                setMenus(res.menus || []);
                setTotal(res.total || 0);
                setObjetivo(res.objetivo || null);
                // El servidor sabe distinguir «no hay ninguno que te cuadre» de «la base no
                // está cosechada» y lo dice en `filtros.sin_cosechar` (punto 10.3). Aquí no
                // se leía, así que el cero salía con el mismo texto en los dos casos y el
                // cliente subía el margen sin que eso pudiera arreglar nada.
                setSinCosechar(!!res.filtros?.sin_cosechar);
            } catch (err) {
                if (!cancelado) {
                    setMenus([]);
                    setTotal(0);
                    setError('No se pudieron cargar los menús de la biblioteca.');
                }
            }
            if (!cancelado) setLoading(false);
        };
        cargar();
        return () => { cancelado = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, mealKey, margen, orden]);

    // El catálogo del recetario no depende de la comida ni del objetivo: se pide una sola
    // vez, al abrir. Ya no espera a que nadie entre en una pestaña -- no hay pestañas --,
    // así que llega a la vez que la biblioteca y es lo primero que se puede leer.
    React.useEffect(() => {
        if (!open || recetario !== null || recetarioLoading) return;
        let cancelado = false;
        const cargar = async () => {
            setRecetarioLoading(true);
            setRecetarioError(null);
            try {
                const res = await api('/api/calculator/menu-catalog');
                if (cancelado) return;
                setRecetario(res.menus || []);
                setRecetarioMomentos(res.momentos || []);
            } catch (err) {
                if (!cancelado) setRecetarioError('No se pudo cargar el recetario.');
            }
            if (!cancelado) setRecetarioLoading(false);
        };
        cargar();
        return () => { cancelado = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open]);

    const filtrados = textFilter.trim()
        ? menus.filter(menu => menu.items.some(it => normalizar(it.nombre).includes(normalizar(textFilter))))
        : menus;

    const obj = objetivo || target || { P: 0, H: 0, G: 0 };

    const recetasFiltradas = (recetario || []).filter(receta => {
        if (momento !== 'todos' && !(receta.momentos || []).includes(momento)) return false;
        const q = normalizar(textFilter.trim());
        if (!q) return true;
        return normalizar(receta.nombre).includes(q)
            || (receta.alimentos || []).some(a => normalizar(a).includes(q));
    });

    const aplicar = async (menu) => {
        if (applying) return;
        setApplying(true);
        try { await onApply(menu); } finally { setApplying(false); }
    };

    // Recetario: la receta no trae cantidades cerradas, las cuadra el backend a tus
    // macros al elegirla; lo que devuelve ya viene listo para volcar en la comida.
    // Si aun cuadrada se queda a más de MARGEN_AVISO de tu objetivo, NO se vuelca:
    // primero se enseña de cuánto se pasa y el usuario decide (vídeo de Jesús 04-08:
    // "para mí es poco visual, yo no me di cuenta y me preparo esta receta").
    const aplicarReceta = async (receta) => {
        if (aplicandoId) return;
        setAplicandoId(receta.id);
        setRecetarioError(null);
        try {
            const res = await api('/api/calculator/menu-apply', {
                method: 'POST',
                body: JSON.stringify({
                    plantilla_id: receta.id,
                    mealKey,
                    macros_objetivo: (obj.P || obj.H || obj.G) ? { P: obj.P, H: obj.H, G: obj.G } : {},
                    ...(dayConfig || {}),
                }),
            });
            const menu = { ...res, nombre: res.nombre || receta.nombre, origen: 'recetario' };
            const fuera = desviosFuera(res.macros_totales, res.macros_objetivo || obj);
            if (fuera.length) {
                setConfirmacion({ menu, fuera });
                return;
            }
            await onApply(menu);
        } catch (err) {
            setRecetarioError('No se pudo montar esa receta con tus macros. Prueba con otra.');
        } finally {
            setAplicandoId(null);
        }
    };

    const confirmarReceta = async () => {
        if (!confirmacion) return;
        const { menu } = confirmacion;
        setConfirmacion(null);
        await onApply(menu);
    };

    const chips = ['todos', ...recetarioMomentos];

    return (
        <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="max-w-lg max-h-[90vh] flex flex-col p-0 gap-0 overflow-hidden [&>button]:hidden">
                <DialogHeader className="bg-bg-dark p-4 flex-shrink-0">
                    <div className="flex items-center justify-between">
                        <DialogTitle className="text-white">Elige tu menú</DialogTitle>
                        <button onClick={onClose} className="w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors">
                            <X className="w-5 h-5 text-white" />
                        </button>
                    </div>
                    {/* En el teléfono la cabecera queda con el título y poco más: fuera
                        «Comida 1 - menús reales que ya cuadran con tu objetivo» y fuera «Tu
                        objetivo P·H·G». Ahí ya está eligiendo, y todos los menús de la lista
                        cuadran con ese objetivo -- por eso están en la lista. En escritorio
                        se quedan las dos líneas, como estaban. */}
                    <DialogDescription className="hidden lg:block text-muted-foreground">
                        {mealKey && (mealInfo?.[mealKey]?.name || mealKey)}
                        {' - recetas y menús que cuadran con tu objetivo'}
                    </DialogDescription>
                    <div className="hidden lg:flex items-center gap-2 mt-1">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-white/60">Tu objetivo</span>
                        <span className="text-sm font-black text-white">
                            <span className="text-red-400">{Math.round(obj.P)}P</span>
                            {' · '}<span className="text-blue-400">{Math.round(obj.H)}H</span>
                            {' · '}<span className="text-yellow-400">{Math.round(obj.G)}G</span>
                        </span>
                    </div>
                </DialogHeader>

                {/* UNOS SOLOS CONTROLES PARA TODA LA LISTA. El buscador filtra las dos
                    cosas a la vez (por nombre de receta o por alimento) y los chips de
                    momento acotan las recetas; los menús reales ya vienen del momento de
                    esta comida, que lo decide el servidor con `mealKey`. */}
                <div className="px-4 pt-3 pb-3 border-b bg-card flex-shrink-0 space-y-2.5">
                    <div className="flex items-center gap-1.5 flex-wrap">
                        {chips.map(m => (
                            <button key={m}
                                className={`px-2.5 py-1 text-xs font-bold rounded-full border transition-colors ${momento === m ? 'bg-brand text-white border-brand' : 'bg-muted text-muted-foreground border-border'}`}
                                onClick={() => setMomento(m)} data-testid={`recetario-momento-${m}`}>
                                {m === 'todos' ? 'Todas' : (MOMENTO_LABEL[m] || m)}
                            </button>
                        ))}
                    </div>
                    <div className="relative">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                        <Input value={textFilter} onChange={(e) => setTextFilter(e.target.value)}
                            placeholder="Buscar receta o alimento (pollo, avena...)"
                            className="pl-8 h-9 text-sm" data-testid="recetario-filter" />
                    </div>
                    {/* Las palancas de los menús reales: solo tienen sentido sobre ellos, y
                        por eso van detrás y en pequeño. En el teléfono no salen -- ahí se
                        está eligiendo comida, no afinando una búsqueda -- salvo el margen,
                        que es el que de verdad cambia cuántos hay. */}
                    {BIBLIOTECA_DE_CLIENTES && (
                        <div className="flex items-center justify-between gap-3 flex-wrap pt-0.5">
                            <div className="flex items-center gap-2">
                                <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Margen ±{margen} g</span>
                                <input type="range" min="2" max="10" step="1" value={margen}
                                    onChange={(e) => setMargen(Number(e.target.value))}
                                    className="w-24 accent-orange-500" data-testid="library-margen" />
                            </div>
                            <div className="hidden lg:inline-flex rounded-lg bg-muted p-0.5 border border-border">
                                <button className={`px-2.5 py-1 text-xs font-bold rounded-md transition-colors ${orden === 'cuadrado' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setOrden('cuadrado')} data-testid="library-orden-cuadrado">Más cuadrado</button>
                                <button className={`px-2.5 py-1 text-xs font-bold rounded-md transition-colors ${orden === 'usado' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setOrden('usado')} data-testid="library-orden-usado">Lo que más gente monta</button>
                            </div>
                            <div className="hidden lg:inline-flex rounded-lg bg-muted p-0.5 border border-border">
                                <button className={`px-2.5 py-1 text-xs font-bold rounded-md transition-colors ${!verReales ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setVerReales(false)} data-testid="library-ver-metodo">Método</button>
                                <button className={`px-2.5 py-1 text-xs font-bold rounded-md transition-colors ${verReales ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setVerReales(true)} data-testid="library-ver-reales">Reales</button>
                            </div>
                        </div>
                    )}
                </div>

                <div className="flex-1 min-h-0 overflow-y-auto bg-muted">
                    {confirmacion ? (
                        <div className="p-6" data-testid="recetario-confirmar-desvio">
                                <span className="text-4xl mb-3 block text-center">⚠️</span>
                                <p className="font-bold text-foreground text-center leading-snug mb-1">
                                    {confirmacion.menu.nombre}
                                </p>
                                <p className="text-sm text-muted-foreground text-center mb-4">
                                    Cuadrada a tus macros, esta receta se te va del objetivo de esta comida:
                                </p>
                                <div className="space-y-1.5 mb-4">
                                    {confirmacion.fuera.map(({ m, diff }) => (
                                        <p key={m} className={`text-center text-sm font-black ${MACRO_STYLE[m]}`}>
                                            {diff > 0
                                                ? `Te sobran ${diff} g de ${MACRO_NOMBRE[m]}`
                                                : `Te faltan ${Math.abs(diff)} g de ${MACRO_NOMBRE[m]}`}
                                        </p>
                                    ))}
                                </div>
                                <div className="flex items-start justify-center gap-6 bg-muted/50 rounded-2xl py-3 mb-5">
                                    <div className="text-center">
                                        <span className="block text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-1">Tu objetivo</span>
                                        <MacroTrio macros={confirmacion.menu.macros_objetivo || obj} size="sm" />
                                    </div>
                                    <div className="text-center">
                                        <span className="block text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-1">La receta</span>
                                        <MacroTrio macros={confirmacion.menu.macros_totales} size="sm" />
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <button onClick={() => setConfirmacion(null)}
                                        className="flex-1 py-3 rounded-xl bg-muted text-foreground font-bold text-sm hover:bg-muted/70 transition-colors"
                                        data-testid="recetario-elegir-otra">
                                        Elegir otra
                                    </button>
                                    <button onClick={confirmarReceta}
                                        className="flex-1 py-3 rounded-xl bg-brand-orange text-white font-bold text-sm hover:opacity-90 transition-opacity"
                                        data-testid="recetario-meter-igual">
                                        Meterla igual
                                    </button>
                                </div>
                                <p className="text-[11px] text-muted-foreground text-center mt-3">
                                    Si la metes igual, tendrás que ajustar las cantidades a mano.
                                </p>
                            </div>
                    ) : recetarioLoading && !(recetario || []).length ? (
                        <div className="flex flex-col items-center justify-center py-16">
                            <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-orange border-t-transparent mb-4" />
                            <p className="text-muted-foreground">Cargando los menús...</p>
                        </div>
                    ) : (recetasFiltradas.length + filtrados.length) === 0 && !loading ? (
                        /* Vacío de verdad: no hay ni recetas ni menús que enseñar. Se
                           distingue el porqué, que no es lo mismo «no hay nada con esa
                           palabra» que «la biblioteca no está preparada» (punto 10.3). */
                        <div className="text-center py-14 px-6" data-testid={sinCosechar ? 'biblioteca-sin-cosechar' : undefined}>
                            <span className="text-4xl mb-3 block">{textFilter.trim() ? '🔍' : '🍽️'}</span>
                            <p className="font-semibold text-foreground mb-1.5">
                                {textFilter.trim()
                                    ? `Nada con "${textFilter.trim()}"`
                                    : 'No hay menús para esta comida'}
                            </p>
                            <p className="text-sm text-muted-foreground">
                                {textFilter.trim()
                                    ? 'Prueba con otro alimento, otro momento del día, o borra el filtro.'
                                    : 'Sube el margen o monta la comida con "Lo hago yo".'}
                            </p>
                            {(error || recetarioError) && (
                                <p className="text-xs text-amber-500 font-medium mt-3">{error || recetarioError}</p>
                            )}
                        </div>
                    ) : (
                        <div className="p-4 space-y-3">
                            {/* UN SOLO RECUENTO PARA LAS DOS COSAS. Antes cada pestaña
                                contaba lo suyo, y el cliente no tenía forma de saber
                                cuántas opciones tenía en total. */}
                            <p className="text-xs text-muted-foreground" data-testid="menus-recuento">
                                <span className="font-bold text-foreground">{recetasFiltradas.length + filtrados.length}</span>
                                {' '}para elegir
                                {recetasFiltradas.length > 0 && filtrados.length > 0
                                    ? ` · ${recetasFiltradas.length} recetas y ${filtrados.length} menús ya cuadrados`
                                    : ''}
                                {loading ? ' · buscando más...' : ''}
                            </p>
                            {(error || recetarioError) && (
                                <p className="text-xs text-amber-500 font-medium">{error || recetarioError}</p>
                            )}

                            {recetasFiltradas.map((receta, index) => (
                                    <button key={receta.id}
                                        className="w-full text-left bg-card rounded-2xl shadow-md hover:shadow-lg hover:ring-1 hover:ring-brand-orange/40 transition-all disabled:opacity-60 overflow-hidden"
                                        onClick={() => aplicarReceta(receta)} disabled={!!aplicandoId}
                                        data-testid={`recetario-menu-${index}`}>
                                        {/* La foto de la receta. Si no hay, la tarjeta va sin ella y sin
                                            hueco: nada de imagen genérica ni de plato de relleno. Los menús
                                            que salgan de los PDFs y de la cosecha no van a tener. */}
                                        {receta.foto && (
                                            <img src={receta.foto} alt="" loading="lazy"
                                                className="w-full h-36 object-cover bg-muted"
                                                onError={(e) => { e.currentTarget.style.display = 'none'; }} />
                                        )}
                                        <div className="p-4">
                                        <div className="flex items-start justify-between gap-2 mb-1">
                                            <h3 className="font-bold text-foreground text-lg lg:text-sm leading-snug">{receta.nombre}</h3>
                                            <div className="flex items-center gap-1 flex-shrink-0">
                                                {/* Sin proteína no cubre una comida entera (el «Turrón Crunch
                                                    de Cacao» son frutos secos y chocolate). Se dice AQUÍ, antes
                                                    de elegirla: si no, se la lleva el aviso de «te faltan 30 g
                                                    de proteína» sin saber por qué. Sigue estando y se puede
                                                    elegir; lo que no hace es proponerse sola. */}
                                                {receta.completa === false && (
                                                    <span className="text-[10px] font-semibold uppercase tracking-wide bg-brand-orange/15 text-brand-orange px-2 py-0.5 rounded-full">
                                                        complemento
                                                    </span>
                                                )}
                                                {(receta.momentos || []).map(m => (
                                                    <span key={m} className="text-[10px] font-semibold uppercase tracking-wide bg-muted text-muted-foreground px-2 py-0.5 rounded-full">{m}</span>
                                                ))}
                                            </div>
                                        </div>
                                        {/* Los alimentos de la receta, igual que en la
                                            biblioteca: es lo que se lee para elegir. Van
                                            justificados porque aquí sí es un párrafo -- los
                                            alimentos van seguidos separados por puntos -- y
                                            en un ancho de móvil el borde derecho en zigzag es
                                            lo que hace que un bloque de texto se lea peor. */}
                                        <p className="text-[17px] lg:text-xs text-foreground/70 lg:text-muted-foreground leading-relaxed text-justify lg:text-left hyphens-auto">
                                            {(receta.alimentos || []).join(' · ')}
                                        </p>
                                        <p className="text-[11px] text-brand-orange font-semibold mt-1.5 flex items-center gap-1">
                                            {aplicandoId === receta.id ? (
                                                <>
                                                    <span className="animate-spin rounded-full h-3 w-3 border-2 border-brand-orange border-t-transparent" />
                                                    Cuadrando a tus macros...
                                                </>
                                            ) : (
                                                <><Check className="w-3 h-3" /> Se cuadra a tus macros al elegirla</>
                                            )}
                                        </p>
                                        </div>
                                    </button>
                                ))}

                            {filtrados.map((menu, index) => (
                                    <button key={menu.biblioteca_id}
                                        className="w-full text-left p-4 bg-card rounded-2xl shadow-md hover:shadow-lg hover:ring-1 hover:ring-brand-orange/40 transition-all disabled:opacity-60"
                                        onClick={() => aplicar(menu)} disabled={applying}
                                        data-testid={`library-menu-${index}`}>
                                        <div className="flex items-center justify-between gap-2 mb-2">
                                            <MacroTrio macros={verReales ? menu.macros_reales : menu.macros_metodo} />
                                            <div className="flex items-center gap-1.5">
                                                {verReales && (
                                                    <span className="text-[10px] font-semibold uppercase tracking-wide bg-muted text-muted-foreground px-2 py-0.5 rounded-full">etiqueta</span>
                                                )}
                                                {menu.ajustado && (
                                                    <span className="text-[10px] font-bold uppercase tracking-wide bg-brand-orange/15 text-brand-orange px-2 py-0.5 rounded-full">Ajustado a ti</span>
                                                )}
                                                {menu.clavado ? (
                                                    <span className="text-[10px] font-bold uppercase tracking-wide bg-emerald-500/15 text-emerald-600 px-2 py-0.5 rounded-full">Clavado</span>
                                                ) : menu.cuadrada && (
                                                    <span className="text-[10px] font-bold uppercase tracking-wide bg-emerald-500/15 text-emerald-600 px-2 py-0.5 rounded-full">Cuadrado</span>
                                                )}
                                            </div>
                                        </div>
                                        {/* Los alimentos, en tamaño de lectura. Iban a 12 px, y
                                            son LO ÚNICO que se lee para decidir: los macros ya
                                            cuadran en todos los de la lista, así que entre un
                                            menú y otro lo que elige el cliente es la comida.
                                            Las cantidades a 15 y el nombre a 15. */}
                                        <ul className="space-y-2 lg:space-y-1">
                                            {menu.items.map((it, i) => (
                                                // LAS CANTIDADES, TODAS EMPEZANDO EN LA MISMA
                                                // LÍNEA. Estaban alineadas a la derecha, así
                                                // que «1 ud», «150 g» y «2 cucharadas»
                                                // arrancaban cada una en un sitio distinto y
                                                // la columna se leía en zigzag. Alineadas a la
                                                // izquierda y en la tipografía de datos, que
                                                // tiene todas las cifras del mismo ancho, las
                                                // dos columnas quedan a plomo.
                                                // `min-w` y no `w`: con la columna fija en 72 px,
                                                // un «1 ud» dejaba un hueco enorme hasta el
                                                // nombre. Así la columna solo reserva lo justo
                                                // para que los casos normales queden a plomo, y
                                                // una cantidad larga empuja el nombre en vez de
                                                // abrir un claro en todas las demás filas.
                                                <li key={i} className="flex items-baseline gap-2 lg:gap-2.5 text-[17px] lg:text-xs">
                                                    <span className="font-data font-bold text-brand-orange whitespace-nowrap min-w-[46px] lg:min-w-0 lg:w-12 lg:text-right flex-shrink-0">{it.cantidad_display}</span>
                                                    <span className="text-foreground leading-snug">{it.nombre}</span>
                                                </li>
                                            ))}
                                        </ul>
                                        <div className="flex items-center justify-between mt-2.5">
                                            {/* Se dice cuánta GENTE lo ha montado, no cuántas veces:
                                                que a una persona le guste y lo repita treinta veces no
                                                dice nada, y que lo monten treinta personas sí. Si aún
                                                no lo ha montado nadie aquí, no se dice nada -- mejor
                                                callar que enseñar un cero. */}
                                            <p className="text-[11px] text-muted-foreground">
                                                {menu.de_jesus
                                                    ? <>De los menús de Jesús · <span className="font-bold">{menu.menu_elm?.nombre}</span></>
                                                    : menu.personas > 1
                                                        ? <><span className="font-bold">{menu.personas}</span> personas lo han montado</>
                                                        : menu.personas === 1
                                                            ? 'Lo ha montado alguien más'
                                                            : menu.origen === 'variante' ? 'Variante de un menú real' : ''}
                                            </p>
                                            <p className="text-[11px] text-brand-orange font-semibold flex items-center gap-1">
                                                <Check className="w-3 h-3" /> {menu.ajustado ? 'Añadir ajustado a ti' : 'Añadir tal cual'}
                                            </p>
                                        </div>
                                    </button>
                                ))}

                            {/* La biblioteca llega después que las recetas y puede tardar:
                                se dice al pie, sin tapar lo que ya se puede elegir. */}
                            {loading && (
                                <div className="flex items-center justify-center gap-2 py-4 text-muted-foreground">
                                    <span className="animate-spin rounded-full h-4 w-4 border-2 border-brand-orange border-t-transparent" />
                                    <span className="text-xs">Buscando más menús que te cuadren...</span>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default LibraryMenusModal;
