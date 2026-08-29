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
 * EL ORDEN: NI UNAS NI OTROS PRIMERO (Francisco, 19-08: «siempre salen primero las recetas
 * y no quiero eso»). Hasta hoy se pintaban las 159 recetas y detrás los menús reales, así
 * que para ver un menú de la gente había que bajar toda la lista. Ahora las dos poblaciones
 * se van alternando en proporción a lo que hay de cada una -- si hay 20 recetas y 100 menús,
 * sale una receta cada cinco menús --, cada una en su propio orden: los menús reales por
 * cercanía a tu objetivo (eso lo hace el servidor) y las recetas como vienen del catálogo.
 *
 * No se mezclan ordenando los dos juntos por lo bien que encajan, que habría sido lo ideal:
 * se midió y cuadrar las 159 recetas contra un objetivo cuesta 52 s, así que no se puede
 * hacer mientras el cliente espera. Alternar no inventa una precisión que no tenemos.
 *
 * Y SE PUEDE FILTRAR, que no es lo mismo que separar: «Recetas» es un chip más, al lado de
 * los momentos del día, y se queda solo con ellas igual que «Cenas» se queda con las cenas.
 * Por defecto no está puesto y sale todo junto.
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
import { num1 } from '../../lib/numeros';

const normalizar = (s) => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

// Tono oscuro en claro y claro en oscuro: los 500 sobre blanco se quedan por debajo de
// 3:1 y a este tamaño no se leen (QA del 15-08 en producción).
const MACRO_STYLE = {
    P: 'text-red-700 dark:text-red-400',
    H: 'text-blue-700 dark:text-blue-400',
    G: 'text-yellow-700 dark:text-yellow-400',
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
                    {num1(macros?.[m])}
                </span>
                <span className="block text-[9px] font-bold text-muted-foreground mt-0.5">{m}</span>
            </div>
        ))}
    </div>
);

const LibraryMenusModal = ({ open, mealKey, onClose, mealInfo, target, api, dayConfig, onApply }) => {
    const [margen, setMargen] = React.useState(5);
    const [orden, setOrden] = React.useState('cuadrado');
    // La procedencia, a la vista y con puerta (doc 57, F7; decision de Francisco 21-08:
    // opcion 3, «separar y etiquetar»). Los menus de la biblioteca los monta la gente y
    // pueden traer cualquier cosa que cuadre (el donut del recorrido de Juan); no se
    // filtran, pero cada tarjeta dice de donde viene y el cliente puede quedarse solo
    // con el recetario. La eleccion se recuerda.
    const [verDeOtros, setVerDeOtros] = React.useState(() => {
        try { return localStorage.getItem('menus_ver_de_otros') !== 'no'; } catch { return true; }
    });
    const cambiarVerDeOtros = (v) => {
        setVerDeOtros(v);
        try { localStorage.setItem('menus_ver_de_otros', v ? 'si' : 'no'); } catch { /* privado */ }
    };
    const [verReales, setVerReales] = React.useState(false);
    const [textFilter, setTextFilter] = React.useState('');
    const [menus, setMenus] = React.useState([]);
    const [sinCosechar, setSinCosechar] = React.useState(false);
    const [total, setTotal] = React.useState(0);
    const [objetivo, setObjetivo] = React.useState(null);
    // El momento del día de ESTA comida, tal y como lo calcula el servidor (`meal_moment`).
    const [momentoComida, setMomentoComida] = React.useState(null);
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
                        // EL CHIP TAMBIÉN ACOTA LOS MENÚS DE LA GENTE (Francisco, 29-08).
                        // Antes solo acotaba el recetario y aquí se pedía por la POSICIÓN de
                        // la comida, así que al filtrar por Meriendas salían las cenas de
                        // todo el mundo: con 4 comidas la 3 es merienda, con 3 es cena. El
                        // servidor filtra por `momentos`, que pone `_momentos_biblioteca.py`.
                        // Con «Todas» y con «Recetas» no se manda nada y sigue como estaba.
                        ...(momento !== 'todos' && momento !== 'recetas' ? { momento } : {}),
                        ...(dayConfig || {}),
                    }),
                });
                if (cancelado) return;
                setMenus(res.menus || []);
                setTotal(res.total || 0);
                setObjetivo(res.objetivo || null);
                setMomentoComida(res.momento_comida || null);
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
        // `momento` entra en las dependencias: cambiar de chip vuelve a pedir los menús,
        // que es lo que hace que el filtro se note en ellos y no solo en las recetas.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, mealKey, margen, orden, momento]);

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

    // Con el chip «Recetas» puesto, los menús de la gente no salen: es el propio filtro.
    const soloRecetas = momento === 'recetas';
    const filtrados = soloRecetas ? []
        : textFilter.trim()
            ? menus.filter(menu => normalizar(menu.nombre || '').includes(normalizar(textFilter))
                || menu.items.some(it => normalizar(it.nombre).includes(normalizar(textFilter))))
            : menus;

    const obj = objetivo || target || { P: 0, H: 0, G: 0 };

    // LAS RECETAS, SOLO EN SU CHIP, Y LAS DE ESTA COMIDA (Francisco, 29-08): «que recetas
    // solo se muestren con el filtro de recetas y que distinga la comida».
    //
    // Salían mezcladas con los menús de la gente en todos los chips, y con «Recetas» puesto
    // salía el recetario ENTERO -- desayunos incluidos -- porque ahí no se filtraba por
    // momento. Ahora: en cualquier otro chip no hay recetas, y en el suyo salen las del
    // momento que le toca a esta comida, que lo dice el servidor en `momento_comida` (con 4
    // comidas la 3 es merienda; con 3, cena). Si la receta no dice sus momentos, se enseña:
    // más vale ofrecerla que esconderla por un dato que falta.
    const recetasFiltradas = !soloRecetas ? [] : (recetario || []).filter(receta => {
        const momentos = receta.momentos || [];
        if (momentoComida && momentos.length && !momentos.includes(momentoComida)) return false;
        const q = normalizar(textFilter.trim());
        if (!q) return true;
        return normalizar(receta.nombre).includes(q)
            || (receta.alimentos || []).some(a => normalizar(a).includes(q));
    });

    // LA LISTA ÚNICA, ALTERNANDO. Cada elemento sabe de dónde viene y qué número hace
    // DENTRO DE SU POBLACIÓN: la tarjeta que se pinta es distinta y las pruebas buscan por
    // ese número (`recetario-menu-3`, `library-menu-3`), que no cambia al mezclarlas.
    //
    // El reparto es proporcional: en cada paso entra el que va más atrasado respecto a lo
    // que le toca. Así ninguna de las dos se queda para el final aunque haya diez veces más
    // de una que de otra, y el orden interno de cada una se respeta entero.
    const mostrados = React.useMemo(() => {
        const recetas = recetasFiltradas.map((dato, i) => ({ tipo: 'receta', dato, i }));
        const reales = (verDeOtros ? filtrados : []).map((dato, i) => ({ tipo: 'menu', dato, i }));
        const salida = [];
        let a = 0, b = 0;
        while (a < recetas.length || b < reales.length) {
            const avanceRecetas = recetas.length ? a / recetas.length : 1;
            const avanceReales = reales.length ? b / reales.length : 1;
            // En el empate gana el menú real (doc 57, F8): la lista debe abrir con una
            // tarjeta que ya trae los gramos y su etiqueta, no con la receta sin números.
            if (b >= reales.length || (a < recetas.length && avanceRecetas < avanceReales)) {
                salida.push(recetas[a++]);
            } else {
                salida.push(reales[b++]);
            }
        }
        return salida;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [recetasFiltradas, filtrados, verDeOtros]);

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
            setRecetarioError('No se pudo crear esa receta con tus macros. Prueba con otra.');
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

    // «Recetas» es un chip más, al lado de los momentos (Francisco, 19-08). No separa la
    // lista: solo se queda con las recetas, igual que «Cenas» se queda con las cenas.
    //
    // Está SIEMPRE, no solo cuando ya han llegado los menús de la gente. Si apareciera y
    // desapareciera según la carga, quien lo hubiera pulsado se quedaba con el filtro
    // puesto y sin el botón para quitarlo: la lista se le quedaba en recetas y parecía que
    // los menús habían desaparecido.
    const chips = ['todos', 'recetas', ...recetarioMomentos];

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

                {/* UNOS SOLOS CONTROLES PARA TODA LA LISTA. El buscador filtra las dos cosas
                    a la vez (por nombre de receta o por alimento) y los chips de momento
                    acotan LAS DOS: las recetas por su `momento`, y los menús de la gente por
                    `momentos`, que el servidor cruza con las dietas donde se montaron.
                    Hasta el 29-08 los chips solo acotaban las recetas y los menús venían por
                    la posición de la comida, así que al pedir Meriendas salían cenas. */}
                <div className="px-4 pt-3 pb-3 border-b bg-card flex-shrink-0 space-y-2.5">
                    <div className="flex items-center gap-1.5 flex-wrap">
                        {chips.map(m => (
                            <button key={m}
                                className={`px-2.5 py-1 text-xs font-bold rounded-full border transition-colors ${momento === m ? 'bg-brand text-white border-brand' : 'bg-muted text-muted-foreground border-border'}`}
                                onClick={() => setMomento(m)} data-testid={`recetario-momento-${m}`}>
                                {m === 'todos' ? 'Todas' : m === 'recetas' ? 'Recetas' : (MOMENTO_LABEL[m] || m)}
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
                            {/* La puerta de la procedencia (doc 57, F7): los menús de la
                                biblioteca los monta la gente, no el equipo, y quien no los
                                quiera ver se queda con el recetario a secas. */}
                            <div className="inline-flex rounded-lg bg-muted p-0.5 border border-border">
                                <button className={`px-2.5 py-1 text-xs font-bold rounded-md transition-colors ${verDeOtros ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => cambiarVerDeOtros(true)} data-testid="library-fuente-todo">Recetario y gente</button>
                                <button className={`px-2.5 py-1 text-xs font-bold rounded-md transition-colors ${!verDeOtros ? 'bg-brand text-white' : 'text-muted-foreground'}`}
                                    onClick={() => cambiarVerDeOtros(false)} data-testid="library-fuente-recetario">Solo recetario</button>
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
                                            {/* Con coma decimal, como el resto de Nutrición (fallo 43). */}
                                            {diff > 0
                                                ? `Te sobran ${num1(diff)} g de ${MACRO_NOMBRE[m]}`
                                                : `Te faltan ${num1(Math.abs(diff))} g de ${MACRO_NOMBRE[m]}`}
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
                    ) : mostrados.length === 0 && !loading ? (
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
                                <span className="font-bold text-foreground">{mostrados.length}</span>
                                {' '}para elegir
                                {recetasFiltradas.length > 0 && filtrados.length > 0
                                    ? ` · ${recetasFiltradas.length} recetas y ${filtrados.length} menús ya cuadrados`
                                    : ''}
                                {loading ? ' · buscando más...' : ''}
                            </p>
                            {(error || recetarioError) && (
                                <p className="text-xs text-amber-500 font-medium">{error || recetarioError}</p>
                            )}

                            {mostrados.map((fila) => {
                                const index = fila.i;
                                if (fila.tipo === 'receta') {
                                    const receta = fila.dato;
                                    return (
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
                                                {/* La procedencia, dicha (doc 57, F7). */}
                                                <span className="text-[10px] font-semibold uppercase tracking-wide bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 px-2 py-0.5 rounded-full">Del recetario</span>
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
                                    );
                                }
                                const menu = fila.dato;
                                return (
                                    <button key={menu.biblioteca_id}
                                        className="w-full text-left p-4 bg-card rounded-2xl shadow-md hover:shadow-lg hover:ring-1 hover:ring-brand-orange/40 transition-all disabled:opacity-60"
                                        onClick={() => aplicar(menu)} disabled={applying}
                                        data-testid={`library-menu-${index}`}>
                                        {/* El título que le haya puesto el equipo desde el
                                            panel. Casi ninguno lo tiene -- estos menús son
                                            la lista de lo que llevan --, así que solo se
                                            reserva sitio cuando existe. */}
                                        {menu.nombre && (
                                            <h3 className="font-bold text-foreground text-lg lg:text-sm leading-snug mb-1.5">{menu.nombre}</h3>
                                        )}
                                        <div className="flex items-center justify-between gap-2 mb-2">
                                            <MacroTrio macros={verReales ? menu.macros_reales : menu.macros_metodo} />
                                            <div className="flex items-center gap-1.5">
                                                {/* La procedencia, dicha (doc 57, F7): estos menús los monta
                                                    la gente, no el equipo, y el cliente tiene que saberlo
                                                    ANTES de fijarse en que los números cuadran. */}
                                                <span className="text-[10px] font-semibold uppercase tracking-wide bg-muted text-muted-foreground px-2 py-0.5 rounded-full">De otros usuarios</span>
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
                                                    {/* `lg:w-auto`: desde que la unidad lleva su
                                                        equivalencia al lado («2 ud (10 g)», fallo
                                                        46) el ancho fijo de 48 px se quedaba
                                                        corto y el texto se montaba sobre el
                                                        nombre. El `min-w` mantiene la columna a
                                                        plomo en los casos normales. */}
                                                    <span className="font-data font-bold text-brand-orange whitespace-nowrap min-w-[46px] lg:w-auto lg:min-w-[3rem] lg:text-right flex-shrink-0">{it.cantidad_display}</span>
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
                                                        ? <><span className="font-bold">{menu.personas}</span> personas lo han usado</>
                                                        : menu.personas === 1
                                                            ? 'Lo ha usado alguien más'
                                                            : menu.origen === 'variante' ? 'Variante de un menú real' : ''}
                                            </p>
                                            <p className="text-[11px] text-brand-orange font-semibold flex items-center gap-1">
                                                <Check className="w-3 h-3" /> {menu.ajustado ? 'Añadir ajustado a ti' : 'Añadir tal cual'}
                                            </p>
                                        </div>
                                    </button>
                                );
                            })}

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
