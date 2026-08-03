/**
 * LibraryMenusModal - "Elige tu menú", con dos pestañas:
 *
 * 1. Biblioteca: menús REALES (266k comidas de clientes ya cuadradas con el
 *    método). Filosofía (nota 2026-07-16): cercanía, no exactitud. El objetivo lo
 *    define la calculadora (reparto del día) y NO se puede editar aquí; el menú
 *    elegido se vuelca tal cual (o ajustado con las palancas del propio menú).
 * 2. Recetario: las recetas de la membresía ELM (menu_templates). Aquí no hay
 *    cantidades cerradas: al elegir una receta, el motor la cuadra a tus macros
 *    (POST /calculator/menu-apply).
 */
import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Input } from '../ui/input';
import { Search, X, Check } from 'lucide-react';

const normalizar = (s) => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

const MACRO_STYLE = {
    P: 'text-red-500',
    H: 'text-blue-500',
    G: 'text-yellow-500',
};

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
    const [tab, setTab] = React.useState('biblioteca');
    const [margen, setMargen] = React.useState(5);
    const [orden, setOrden] = React.useState('cuadrado');
    const [verReales, setVerReales] = React.useState(false);
    const [textFilter, setTextFilter] = React.useState('');
    const [menus, setMenus] = React.useState([]);
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

    React.useEffect(() => {
        if (open) {
            setTab('biblioteca');
            setTextFilter('');
            setVerReales(false);
            setError(null);
            setRecetarioError(null);
            setMomento('todos');
        }
    }, [open, mealKey]);

    React.useEffect(() => {
        if (!open || !mealKey) return;
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
                        limit: 40,
                        ...(dayConfig || {}),
                    }),
                });
                if (cancelado) return;
                setMenus(res.menus || []);
                setTotal(res.total || 0);
                setObjetivo(res.objetivo || null);
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

    // El catálogo del recetario no depende de la comida ni del objetivo: se pide
    // una sola vez, la primera vez que se entra en la pestaña.
    React.useEffect(() => {
        if (!open || tab !== 'recetario' || recetario !== null || recetarioLoading) return;
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
    }, [open, tab]);

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
            await onApply({ ...res, nombre: res.nombre || receta.nombre, origen: 'recetario' });
        } catch (err) {
            setRecetarioError('No se pudo montar esa receta con tus macros. Prueba con otra.');
        } finally {
            setAplicandoId(null);
        }
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
                    <DialogDescription className="text-muted-foreground">
                        {mealKey && (mealInfo?.[mealKey]?.name || mealKey)}
                        {tab === 'biblioteca'
                            ? ' - menús reales que ya cuadran con tu objetivo'
                            : ' - recetas del recetario, cuadradas a tu objetivo'}
                    </DialogDescription>
                    <div className="flex items-center gap-2 mt-1">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-white/60">Tu objetivo</span>
                        <span className="text-sm font-black text-white">
                            <span className="text-red-400">{Math.round(obj.P)}P</span>
                            {' · '}<span className="text-blue-400">{Math.round(obj.H)}H</span>
                            {' · '}<span className="text-yellow-400">{Math.round(obj.G)}G</span>
                        </span>
                    </div>
                </DialogHeader>

                {/* Pestañas: biblioteca real / recetario ELM */}
                <div className="px-4 pt-3 pb-2 bg-card flex-shrink-0">
                    <div className="inline-flex w-full rounded-lg bg-muted p-0.5 border border-border">
                        <button className={`flex-1 px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${tab === 'biblioteca' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                            onClick={() => setTab('biblioteca')} data-testid="menus-tab-biblioteca">Biblioteca</button>
                        <button className={`flex-1 px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${tab === 'recetario' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                            onClick={() => setTab('recetario')} data-testid="menus-tab-recetario">Recetario</button>
                    </div>
                </div>

                {tab === 'biblioteca' ? (
                    /* Controles de la biblioteca: margen, orden, método/reales */
                    <div className="px-4 pb-3 border-b bg-card flex-shrink-0 space-y-2.5">
                        <div className="flex items-center justify-between gap-3 flex-wrap">
                            <div className="flex items-center gap-2">
                                <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Margen ±{margen} g</span>
                                <input type="range" min="2" max="10" step="1" value={margen}
                                    onChange={(e) => setMargen(Number(e.target.value))}
                                    className="w-24 accent-orange-500" data-testid="library-margen" />
                            </div>
                            <div className="inline-flex rounded-lg bg-muted p-0.5 border border-border">
                                <button className={`px-2.5 py-1 text-xs font-bold rounded-md transition-colors ${orden === 'cuadrado' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setOrden('cuadrado')} data-testid="library-orden-cuadrado">Más cuadrado</button>
                                <button className={`px-2.5 py-1 text-xs font-bold rounded-md transition-colors ${orden === 'usado' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setOrden('usado')} data-testid="library-orden-usado">Más usado</button>
                            </div>
                            <div className="inline-flex rounded-lg bg-muted p-0.5 border border-border">
                                <button className={`px-2.5 py-1 text-xs font-bold rounded-md transition-colors ${!verReales ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setVerReales(false)} data-testid="library-ver-metodo">Método</button>
                                <button className={`px-2.5 py-1 text-xs font-bold rounded-md transition-colors ${verReales ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => setVerReales(true)} data-testid="library-ver-reales">Reales</button>
                            </div>
                        </div>
                        <div className="relative">
                            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                            <Input value={textFilter} onChange={(e) => setTextFilter(e.target.value)}
                                placeholder="Filtrar por alimento (avena, batido, arroz...)"
                                className="pl-8 h-9 text-sm" data-testid="library-food-filter" />
                        </div>
                    </div>
                ) : (
                    /* Controles del recetario: momento + buscador por receta o alimento */
                    <div className="px-4 pb-3 border-b bg-card flex-shrink-0 space-y-2.5">
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
                    </div>
                )}

                <div className="flex-1 min-h-0 overflow-y-auto bg-muted">
                    {tab === 'biblioteca' ? (
                        loading ? (
                            <div className="flex flex-col items-center justify-center py-16">
                                <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-orange border-t-transparent mb-4" />
                                <p className="text-muted-foreground">Buscando en la biblioteca...</p>
                            </div>
                        ) : error ? (
                            <div className="text-center py-14 px-6">
                                <span className="text-4xl mb-3 block">⚠️</span>
                                <p className="font-semibold text-foreground mb-1.5">{error}</p>
                                <p className="text-sm text-muted-foreground">Inténtalo de nuevo en unos segundos.</p>
                            </div>
                        ) : menus.length === 0 ? (
                            <div className="text-center py-14 px-6">
                                <span className="text-4xl mb-3 block">🍽️</span>
                                <p className="font-semibold text-foreground mb-1.5">No hay menús a ±{margen} g de tu objetivo</p>
                                <p className="text-sm text-muted-foreground">
                                    Sube el margen, mira el <button className="font-semibold text-brand-orange underline" onClick={() => setTab('recetario')}>recetario</button> o
                                    monta la comida con "Lo hago yo".
                                </p>
                            </div>
                        ) : filtrados.length === 0 ? (
                            <div className="text-center py-14 px-6">
                                <span className="text-4xl mb-3 block">🔍</span>
                                <p className="font-semibold text-foreground mb-1.5">Ningún menú lleva "{textFilter}"</p>
                                <p className="text-sm text-muted-foreground">Prueba con otro alimento o borra el filtro.</p>
                            </div>
                        ) : (
                            <div className="p-4 space-y-3">
                                <p className="text-xs text-muted-foreground">
                                    Hay <span className="font-bold text-foreground">{total}</span> menús que cuadran (±{margen} g)
                                    {textFilter.trim() ? ` · ${filtrados.length} con "${textFilter.trim()}"` : ''}. Las cantidades vienen ajustadas a tu objetivo.
                                </p>
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
                                        <ul className="space-y-1">
                                            {menu.items.map((it, i) => (
                                                <li key={i} className="flex items-baseline gap-2 text-xs">
                                                    <span className="font-bold text-brand-orange whitespace-nowrap w-12 flex-shrink-0 text-right">{it.cantidad_display}</span>
                                                    <span className="text-foreground leading-snug">{it.nombre}</span>
                                                </li>
                                            ))}
                                        </ul>
                                        <div className="flex items-center justify-between mt-2.5">
                                            <p className="text-[11px] text-muted-foreground">
                                                {menu.veces > 1 ? <>Usado <span className="font-bold">{menu.veces}</span> veces</> : 'Variante de un menú real'}
                                            </p>
                                            <p className="text-[11px] text-brand-orange font-semibold flex items-center gap-1">
                                                <Check className="w-3 h-3" /> {menu.ajustado ? 'Añadir ajustado a ti' : 'Añadir tal cual'}
                                            </p>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )
                    ) : (
                        recetarioLoading ? (
                            <div className="flex flex-col items-center justify-center py-16">
                                <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-orange border-t-transparent mb-4" />
                                <p className="text-muted-foreground">Cargando el recetario...</p>
                            </div>
                        ) : recetarioError && !(recetario || []).length ? (
                            <div className="text-center py-14 px-6">
                                <span className="text-4xl mb-3 block">⚠️</span>
                                <p className="font-semibold text-foreground mb-1.5">{recetarioError}</p>
                                <p className="text-sm text-muted-foreground">Inténtalo de nuevo en unos segundos.</p>
                            </div>
                        ) : recetasFiltradas.length === 0 ? (
                            <div className="text-center py-14 px-6">
                                <span className="text-4xl mb-3 block">🔍</span>
                                <p className="font-semibold text-foreground mb-1.5">
                                    {(recetario || []).length === 0
                                        ? 'No hay recetas en el recetario'
                                        : `Ninguna receta con "${textFilter.trim()}"`}
                                </p>
                                <p className="text-sm text-muted-foreground">Prueba con otro momento del día o borra el filtro.</p>
                            </div>
                        ) : (
                            <div className="p-4 space-y-3">
                                {recetarioError && (
                                    <p className="text-xs text-amber-500 font-medium">{recetarioError}</p>
                                )}
                                <p className="text-xs text-muted-foreground">
                                    <span className="font-bold text-foreground">{recetasFiltradas.length}</span> recetas del recetario.
                                    Al elegir una, las cantidades se cuadran a tu objetivo.
                                </p>
                                {recetasFiltradas.map((receta, index) => (
                                    <button key={receta.id}
                                        className="w-full text-left p-4 bg-card rounded-2xl shadow-md hover:shadow-lg hover:ring-1 hover:ring-brand-orange/40 transition-all disabled:opacity-60"
                                        onClick={() => aplicarReceta(receta)} disabled={!!aplicandoId}
                                        data-testid={`recetario-menu-${index}`}>
                                        <div className="flex items-start justify-between gap-2 mb-1">
                                            <h3 className="font-bold text-foreground text-sm leading-snug">{receta.nombre}</h3>
                                            <div className="flex items-center gap-1 flex-shrink-0">
                                                {(receta.momentos || []).map(m => (
                                                    <span key={m} className="text-[10px] font-semibold uppercase tracking-wide bg-muted text-muted-foreground px-2 py-0.5 rounded-full">{m}</span>
                                                ))}
                                            </div>
                                        </div>
                                        <p className="text-xs text-muted-foreground leading-relaxed">
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
                                    </button>
                                ))}
                            </div>
                        )
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default LibraryMenusModal;
