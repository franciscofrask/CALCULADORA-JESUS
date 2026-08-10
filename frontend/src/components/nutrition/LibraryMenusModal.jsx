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
    const [tab, setTab] = React.useState(BIBLIOTECA_DE_CLIENTES ? 'biblioteca' : 'recetario');
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
            setTab(BIBLIOTECA_DE_CLIENTES ? 'biblioteca' : 'recetario');
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
                    {/* Sin la línea de «Comida 1 - menús reales que ya cuadran con tu
                        objetivo»: el objetivo está justo debajo con sus tres números, y que
                        cuadran lo dice el contador de la lista. Era la tercera vez. */}
                    <div className="flex items-center gap-2 mt-1">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-white/60">Tu objetivo</span>
                        <span className="text-sm font-black text-white">
                            <span className="text-red-400">{Math.round(obj.P)}P</span>
                            {' · '}<span className="text-blue-400">{Math.round(obj.H)}H</span>
                            {' · '}<span className="text-yellow-400">{Math.round(obj.G)}G</span>
                        </span>
                    </div>
                </DialogHeader>

                {/* Pestañas: biblioteca real / recetario ELM. Con la biblioteca apagada
                    (06-08-2026) no hay dos fuentes que elegir: sobra la barra entera. */}
                {BIBLIOTECA_DE_CLIENTES && (
                    <div className="px-4 pt-3 pb-2 bg-card flex-shrink-0">
                        <div className="inline-flex w-full rounded-lg bg-muted p-0.5 border border-border">
                            <button className={`flex-1 px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${tab === 'biblioteca' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                onClick={() => setTab('biblioteca')} data-testid="menus-tab-biblioteca">Biblioteca</button>
                            <button className={`flex-1 px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${tab === 'recetario' ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                onClick={() => setTab('recetario')} data-testid="menus-tab-recetario">Recetario</button>
                        </div>
                    </div>
                )}

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
                                    onClick={() => setOrden('usado')} data-testid="library-orden-usado">Lo que más gente monta</button>
                            </div>
                            {/* El conmutador Método/Reales sale de aquí. Está eligiendo un
                                menú: lo que le importa es cuál coge, y los dos juegos de
                                números para el mismo plato en el momento de decidir son ruido.
                                `verReales` se queda en el componente -- las tarjetas siguen
                                sabiendo pintar los dos -- y el modo del día se elige en la
                                tuerca de Nutrición, que es donde vive esa preferencia. */}
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
                        ) : menus.length === 0 && sinCosechar ? (
                            /* El cero no es del margen: la biblioteca no está preparada
                               todavía (punto 10.3). Decirle que suba el margen sería
                               mandarle a mover una palanca que no puede cambiar nada. */
                            <div className="text-center py-14 px-6" data-testid="biblioteca-sin-cosechar">
                                <span className="text-4xl mb-3 block">🧰</span>
                                <p className="font-semibold text-foreground mb-1.5">La biblioteca todavía no está lista</p>
                                <p className="text-sm text-muted-foreground">
                                    No es tu objetivo ni el margen: los menús están sin preparar. Usa el{' '}
                                    <button className="font-semibold text-brand-orange underline" onClick={() => setTab('recetario')}>recetario</button>{' '}
                                    mientras tanto.
                                </p>
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
                                {/* Solo el recuento. Lo de «y aquí tienes los 120 que mejor te
                                    encajan» y «las cantidades vienen ajustadas a tu objetivo»
                                    se va: lo segundo ya se lee en cada tarjeta, que trae los
                                    gramos puestos.
                                    Queda apuntado que, cuando la lista se recorta, ya no se
                                    dice: se enseñan 120 de 207 sin avisar. */}
                                <p className="text-xs text-muted-foreground">
                                    Hay <span className="font-bold text-foreground">{total}</span> menús que cuadran (±{margen} g)
                                    {textFilter.trim() ? ` · ${filtrados.length} con "${textFilter.trim()}"` : ''}
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
                                        {/* Los alimentos, en tamaño de lectura. Iban a 12 px, y
                                            son LO ÚNICO que se lee para decidir: los macros ya
                                            cuadran en todos los de la lista, así que entre un
                                            menú y otro lo que elige el cliente es la comida.
                                            Las cantidades a 15 y el nombre a 15. */}
                                        <ul className="space-y-1.5">
                                            {menu.items.map((it, i) => (
                                                <li key={i} className="flex items-baseline gap-2.5 text-[15px]">
                                                    <span className="font-bold text-brand-orange whitespace-nowrap w-14 flex-shrink-0 text-right">{it.cantidad_display}</span>
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
                            </div>
                        )
                    ) : (
                        confirmacion ? (
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
                        ) : recetarioLoading ? (
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
                                            <h3 className="font-bold text-foreground text-base leading-snug">{receta.nombre}</h3>
                                            <div className="flex items-center gap-1 flex-shrink-0">
                                                {(receta.momentos || []).map(m => (
                                                    <span key={m} className="text-[10px] font-semibold uppercase tracking-wide bg-muted text-muted-foreground px-2 py-0.5 rounded-full">{m}</span>
                                                ))}
                                            </div>
                                        </div>
                                        {/* Los alimentos de la receta, igual que en la
                                            biblioteca: es lo que se lee para elegir. */}
                                        <p className="text-[15px] text-foreground/70 leading-relaxed">
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
                            </div>
                        )
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default LibraryMenusModal;
