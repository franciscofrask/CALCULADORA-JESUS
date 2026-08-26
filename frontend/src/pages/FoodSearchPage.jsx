import React, { useState, useEffect, useMemo } from 'react';
import { Search, X, Plus, ChevronDown, ChevronUp } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { descripcionCategoria, CATEGORIA_NOMBRES } from '../components/nutrition/calmaCategorias';
import SuggestFoodModal from '../components/nutrition/SuggestFoodModal';
import { useEsTelefono } from '../lib/esTelefono';
import { num1 } from '../lib/numeros';
// La búsqueda por nombre (filtro + relevancia, portada de Calma) vive en lib para que la
// use también el panel de «Añadir ingrediente» de Nutrición: era el mismo catálogo con dos
// buscadores distintos, y el de montar la dieta era el roto (Jesús, 15-08).
import { matchWord, matchAll, relevancia } from '../lib/busquedaAlimentos';

// Calma $() token match: token === code OR token starts with `${code}.<digit>`.
const tokenMatchesCode = (token, code) =>
    token === code ||
    (token.startsWith(code + '.') && token.length > code.length + 1 && /\d/.test(token[code.length + 1]));

const foodCats = (food) => String(food.categorias || '').split('|').map(t => t.trim()).filter(Boolean);

// Redondeo Calma d(n,1), y escrito como se escribe en español: «53,1» y no «53.1». Esta
// pantalla se había quedado fuera del arreglo de la coma decimal del 15-08 (lib/numeros),
// y encima el propio Jesús escribe «4,8 H · 53,1 G» en el punto 143.
const r1 = (n) => num1(n);

// ── Filtro de categorías (réplica de Calma ListadoAlimentos) ────────────────
const inAny = (f, codes) => codes.some(c => foodCats(f).some(t => tokenMatchesCode(t, c)));
const nameSome = (nombre, words) => words.some(w => matchWord(nombre, w));
const nameAll = (nombre, words) => words.every(w => matchWord(nombre, w));
const AHU_T = (f) => inAny(f, ['3.7', 'AHU']) || matchWord(f.nombre || '', 'ahumad');

// preparaciones con .test() propio; el resto usan match de token (default `c`).
const PREP_TESTS = {
    GEN: f => !f.url,
    FRE: f => inAny(f, ['FRE', '1.2.1', '2.2.1', '2.3.1', '2.4.1', '3.1', '3.9.1', '11.1', '13.1']),
    CGE: f => inAny(f, ['CGE', '2.2.4', '2.3.4', '2.4.4', '3.4', '3.9.4', '10.1.4', '11.4', '13.4']) || nameSome(f.nombre || '', ['congelad', 'helad']),
    AHU: AHU_T,
    LAT: f => nameSome(f.nombre || '', [' lata', 'conserva']) || inAny(f, ['2.2.8', '2.3.8', '2.4.8', '3.8', '3.9.8', '10.1.8', '11.8', '13.8']),
    POL: f => nameSome(f.nombre || '', ['polvo', 'harina']) || inAny(f, ['POL', '4', '7.1.2.6', '16.5', '18.3', '27']) || nameAll(f.nombre || '', ['crema', 'arroz']),
    PRE: f => inAny(f, ['PRE', '2.2.2', '2.3.2', '2.4.2', '3.2', '3.9.2', '11.5', '17.9.2']),
    YCO: f => inAny(f, ['YCO', '2.1', '2.2.3', '2.3.3', '2.4.3', '3.3', '3.9.3', '13.2', '17.9.3', '39']),
    UNI: f => !!f.unidades,
    YA: f => inAny(f, ['YA', '2.1', '4', '11.5']) || AHU_T(f),
};
const esPrepCode = (code) => /^[a-zA-Z]+$/.test(code);
// match de una categoría escogida: si es preparación usa su test, si no token-match.
const catMatch = (f, code) => (esPrepCode(code) && PREP_TESTS[code]) ? PREP_TESTS[code](f) : inAny(f, [code]);

// todasLasCategorias: lista completa ordenada como Calma (no-preparaciones por
// descripción de la categoría suprema, preparaciones al final), con sangría en subcategorías.
const supremeCode = (code) => (code.includes('.') ? code.slice(0, code.indexOf('.')) : code);
const TODAS_CATEGORIAS = (() => {
    const arr = [...CATEGORIA_NOMBRES.keys()].map(clave => ({
        clave,
        valor: CATEGORIA_NOMBRES.get(clave),
        sup: descripcionCategoria(supremeCode(clave)) || '',
        esSuprema: !clave.includes('.'),
        esPrep: esPrepCode(clave),
    }));
    arr.sort((a, b) =>
        a.esPrep && !b.esPrep ? 1 : !a.esPrep && b.esPrep ? -1 : a.sup.localeCompare(b.sup));
    return arr;
})();

/**
 * CUÁNTOS SE PINTAN DE GOLPE.
 *
 * Medido: al entrar sin buscar nada, esta pantalla pintaba 300 de golpe y el documento
 * quedaba en **69.711 px, ochenta y dos pantallas de móvil**. Nadie recorre 300 alimentos
 * por orden alfabético con el pulgar, y mientras tanto el teléfono los tiene todos montados.
 *
 * Veinte y un botón para traer más. No se quita nada -- pulsando se llega hasta el final
 * de la lista -- y se dice cuántos hay, que es lo que evita que un recorte se lea como
 * «no hay más». Antes había un tope de 300 incluso pulsando y de ahí no se pasaba: con
 * 3.211 alimentos, «viendo 300» sin botón era un callejón (P39, doc 23-08). Fuera el tope.
 *
 * En el ordenador, cuarenta: caben dos columnas y la pantalla es más alta, así que el
 * primer golpe de vista da más sin volver a los 69.000 px. Esto era solo del teléfono
 * porque el encargo era no tocar el escritorio, y allí seguían los 300 de una vez
 * (Jesús, 11-08: *«el paginado del móvil funciona igual de bien aquí; con más ancho, 40»*).
 * El problema de fondo -- que se descargan todos -- es el mismo en los dos y sigue ahí.
 */
const CAP_TELEFONO = 20;
const CAP_ORDENADOR = 40;

// Calma EtiquetasMacros: badge por macro > 0 (P verde, H azul, G rojo), 1 decimal.
const MACRO_DEFS = [
    // Con unidad y en singular: «18 g proteína» y no «18 proteínas», que no es nada
    // (Jesús, 11-08).
    ['proteinas', 'g proteína', 'bg-green-100 text-green-700'],
    ['hidratos', 'g hidratos', 'bg-blue-100 text-blue-700'],
    ['grasas', 'g grasa', 'bg-red-100 text-red-700'],
];

// Los dos números de un alimento, con su nombre delante (puntos 142 y 143). «Cada alimento
// enseña sus dos números y dice cuál es cuál»: los macros del MÉTODO son lo que te cuenta a
// ti, ya con las reglas aplicadas, y los REALES lo que de verdad contiene. No se
// contradicen -- las almendras llevan 23 de proteína y de esos tres números el método te
// cuenta uno, los 53,1 de grasa --, pero hasta hoy la app enseñaba los dos sin decir cuál
// era cuál, y a uno lo llamaba «lo que pone la etiqueta» aunque fuera un genérico sin bote.
const LETRA = { proteinas: 'P', hidratos: 'H', grasas: 'G' };
const lineaDeMacros = (m) => ['proteinas', 'hidratos', 'grasas']
    .filter((k) => Number(m[k] || 0) > 0)
    .map((k) => `${r1(m[k])} ${LETRA[k]}`)
    .join(' · ');

const FoodRow = ({ food }) => {
    const cats = foodCats(food).map(descripcionCategoria).filter(Boolean);
    const [abierto, setAbierto] = React.useState(false);
    const cal = food.calibracion;
    const reales = food.macros_reales
        ? lineaDeMacros({ proteinas: food.macros_reales.P, hidratos: food.macros_reales.H, grasas: food.macros_reales.G })
        : null;
    return (
        <div className="bg-card border border-border rounded-lg p-3 shadow-sm" data-testid="alimento">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-1 sm:gap-3">
                <div className="min-w-0 flex items-start gap-1.5">
                    {/* EL PUNTO, Y NADA MÁS (punto 138). «Cero texto añadido por alimento. Y
                        el punto separa los que dependen de la cantidad de los que no — hoy
                        los tres se ven exactamente igual.» */}
                    {cal && <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand flex-shrink-0"
                        title="Te cuenta más proteína cuanta más cantidad comes en el día" />}
                    <div className="min-w-0">
                        {food.url ? (
                            <a href={food.url} target="_blank" rel="noopener noreferrer"
                                className="text-sm font-medium text-[#FF671F] underline underline-offset-2 break-words">
                                {food.nombre}
                            </a>
                        ) : (
                            <span className="text-sm font-medium text-foreground break-words">{food.nombre}</span>
                        )}
                    </div>
                </div>
                <div className="flex-shrink-0 sm:text-right">
                    {food.tiene_macros ? (
                        <>
                            <div className="flex flex-wrap gap-1 sm:justify-end items-baseline">
                                <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Macros del método</span>
                                {MACRO_DEFS.map(([k, label, cls]) =>
                                    Number(food[k] || 0) > 0 ? (
                                        <span key={k} className={`text-xs px-2 py-0.5 rounded-full font-medium tabular-nums ${cls}`}>
                                            {r1(food[k])} {label}
                                        </span>
                                    ) : null
                                )}
                            </div>
                            {reales && (
                                <p className="text-xs text-muted-foreground mt-1 font-data">
                                    <span className="font-sans text-[10px] uppercase tracking-wider mr-1.5">Macros reales</span>
                                    {reales}
                                </p>
                            )}
                            <p className="text-xs text-muted-foreground mt-1">
                                por cada {food.unidades ? `unidad de ${food.racion}g` : '100 gramos'}
                            </p>
                        </>
                    ) : (
                        <em className="text-xs text-muted-foreground">Come lo que quieras</em>
                    )}
                </div>
            </div>
            {cats.length > 0 && (
                <p className="text-xs text-muted-foreground mt-1">{cats.join(' | ')}</p>
            )}
            {/* QUÉ TE CUENTA, EN VEZ DEL FILTRO DEL TERCIO AL REVÉS.
                Aquí ponía «Necesita 9g proteínas / 5.5g hidratos / 5.5g grasas para ser
                sugerido» y, debajo, «cantidad mínima: 50». Lo primero es el filtro dicho en
                lenguaje de programador; lo segundo, un dato interno sin unidad ni contexto.
                Y esta es justo la pantalla donde alguien viene a entender por qué la app le
                cuenta unas cosas y otras no: era la ocasión de explicar el método y se
                gastaba en jerga (Jesús, 11-08). La frase la arma el servidor comparando lo
                que dice la etiqueta con lo que de verdad cuenta.
                En los que llevan punto va acortada (punto 139): ver `_que_te_cuenta`. */}
            {food.que_te_cuenta && (
                <p className="text-xs text-brand-orange mt-1">{food.que_te_cuenta}</p>
            )}
            {/* AL ABRIRLO, LOS TRES TRAMOS (punto 140). «En la lista no hacen falta, con el
                punto basta»: aquí es donde se explica de qué depende esa proteína. Hasta hoy
                un alimento de la lista no se podía abrir. */}
            {cal && (
                <>
                    <button onClick={() => setAbierto((v) => !v)} data-testid={`tramos-${food.id}`}
                        className="mt-1.5 text-xs font-semibold text-brand flex items-center gap-1">
                        {abierto ? 'Ocultar' : 'Y su proteína, según lo que lleves en el día'}
                        {abierto ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                    {abierto && (
                        <div className="mt-1.5 rounded-lg bg-muted/50 p-2.5 space-y-1" data-testid={`tramos-abiertos-${food.id}`}>
                            <p className="text-[11px] text-muted-foreground">
                                Cuenta lo que lleves de <b className="text-foreground">{cal.familia}</b> en todo el día:
                            </p>
                            {[
                                { hasta: `hasta ${cal.tramos[0]} g`, que: 'nada' },
                                { hasta: `${cal.tramos[0]} a ${cal.tramos[1]} g`, que: 'la mitad' },
                                { hasta: `más de ${cal.tramos[1]} g`, que: 'toda' },
                            ].map((t) => (
                                <p key={t.hasta} className="text-xs flex items-center justify-between gap-3">
                                    <span className="text-muted-foreground">{t.hasta}</span>
                                    <span className="font-semibold text-foreground">{t.que}</span>
                                </p>
                            ))}
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

const FoodSearchPage = () => {
    const { api } = useAuth();
    const [foods, setFoods] = useState([]);
    const [loading, setLoading] = useState(true);
    const [query, setQuery] = useState('');
    const [cats, setCats] = useState([]);            // categoriasEscogidas (cascada)
    const [opcion, setOpcion] = useState('');        // '' | 'genericos' | 'sinMacros' (excluyentes)
    const [suggestOpen, setSuggestOpen] = useState(false);

    const setCatAt = (idx, value) => setCats(prev => {
        const next = [...prev];
        if (idx < prev.length) {
            if (value) next[idx] = value; else next.splice(idx, 1);
        } else if (value) next.push(value);
        return next;
    });

    useEffect(() => {
        let alive = true;
        (async () => {
            try {
                const res = await api.get('/calculator/foods-listado');
                if (alive) setFoods(res.data || []);
            } catch (e) {
                console.error('Error cargando alimentos', e);
            } finally {
                if (alive) setLoading(false);
            }
        })();
        return () => { alive = false; };
    }, [api]);

    // Cuántos se ven ahora mismo. `deMas` vuelve a cero en cuanto cambia lo buscado: al
    // afinar la búsqueda se empieza otra vez por arriba, no por donde se quedó la anterior.
    const enTelefono = useEsTelefono();
    const [deMas, setDeMas] = useState(0);
    useEffect(() => { setDeMas(0); }, [query, cats, opcion]);

    const filtered = useMemo(() => {
        let list = foods;
        if (opcion === 'genericos') list = list.filter(f => !f.url);        // GEN: sin enlace
        if (opcion === 'sinMacros') list = list.filter(f => !f.tiene_macros); // noAportaMacros
        if (cats.length > 0) {
            list = list.filter(f => cats.every(code => catMatch(f, code)));
        }
        const words = query.trim().split(/\s+/).filter(Boolean);
        if (words.length) {
            // texto: filtra (todas las palabras) y ordena por relevancia desc (Calma)
            return list
                .filter(f => matchAll(f.nombre || '', words))
                .sort((x, y) => relevancia(y.nombre || '', words) - relevancia(x.nombre || '', words));
        }
        // sin texto: orden alfabético por nombre (getTodosLosAlimentos)
        return [...list].sort((x, y) => (x.nombre || '').localeCompare(y.nombre || ''));
    }, [foods, query, cats, opcion]);

    const porTanda = enTelefono ? CAP_TELEFONO : CAP_ORDENADOR;
    const aLaVista = Math.min(porTanda + deMas, filtered.length);

    return (
        <div className="min-h-screen bg-background p-4 md:p-6">
            <div className="max-w-3xl mx-auto">
                <div className="bg-card border border-border rounded-xl p-4 mb-4">
                    {/* EL TÍTULO Y EL BOTÓN, UNO DEBAJO DE OTRO SI NO CABEN.
                        Iban en una fila con el botón `flex-shrink-0`, o sea que no encogía
                        nunca: en un móvil estrecho se salía 27 px de la pantalla y arrastraba
                        la página entera de lado. Con `flex-wrap` baja de línea en vez de
                        empujar, y el título puede encoger porque ya no tiene el ancho tomado. */}
                    <div className="flex items-start justify-between gap-3 mb-1 flex-wrap">
                        <h1 className="text-xl font-bold text-foreground min-w-0">Buscador de alimentos</h1>
                        <button
                            onClick={() => setSuggestOpen(true)}
                            className="flex-shrink-0 inline-flex items-center gap-1.5 bg-brand-orange hover:bg-brand-orange/90 text-white text-sm font-medium rounded-lg px-3 py-2 transition-colors"
                        >
                            <Plus className="w-4 h-4" />
                            Sugerir alimento
                        </button>
                    </div>
                    {/* TRES LÍNEAS ARRIBA, Y LA REGLA UNA SOLA VEZ (punto 137 del 26-08).

                        Sale «Ordenados por coincidencia con el nombre»: es verdad -- primero
                        los que empiezan igual y luego los que lo llevan dentro -- pero nadie
                        entra a buscar un alimento preguntándose con qué criterio se ordenan
                        los resultados. Ese sitio hace falta para explicar QUÉ ES UN GENÉRICO,
                        que es lo que hoy no se dice en ningún sitio. */}
                    <p className="text-muted-foreground text-sm mb-1">
                        Busca entre todos los alimentos cargados en la calculadora.
                    </p>
                    {/* El subrayado naranja distingue marca de genérico y nadie lo decía en
                        ningún sitio (P40, doc 23-08). Una línea, con el estilo puesto encima
                        para que se reconozca sin explicarlo dos veces. */}
                    <p className="text-xs text-muted-foreground mb-1">
                        Los <b className="text-foreground">genéricos</b> son alimentos sin marca: pollo, arroz, almendras.
                        Las marcas llevan el nombre <span className="text-[#FF671F] underline underline-offset-2">subrayado en naranja</span> y
                        tocando el nombre vas a su web.
                    </p>
                    {/* Y LA CALIBRACIÓN, AQUÍ Y NO EN CADA ALIMENTO. Era un párrafo por
                        alimento, y en uno de cada tres decía algo que solo es verdad si comes
                        poco. Arriba una vez, y abajo el punto. */}
                    <p className="text-xs text-muted-foreground mb-4 flex items-start gap-1.5">
                        <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand flex-shrink-0" />
                        <span>
                            Los que llevan punto te cuentan <b className="text-foreground">más proteína cuanta más cantidad comes en el día</b>.
                            Frutos secos y semillas: desde 20 g la mitad, desde 40 g toda.
                            Cereales y panes, juntos: desde 50 g la mitad, desde 100 g toda.
                        </span>
                    </p>

                    <div className="relative mb-3">
                        <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                            type="text"
                            value={query}
                            onChange={e => setQuery(e.target.value)}
                            placeholder="Texto en el alimento"
                            className="w-full bg-card text-foreground placeholder:text-muted-foreground border border-input rounded-lg pl-9 pr-9 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-orange/40"
                        />
                        {query && (
                            <button onClick={() => setQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-muted-foreground">
                                <X className="w-4 h-4" />
                            </button>
                        )}
                    </div>

                    {/* Categoría (cascada: añade más para ajustar) */}
                    <label className="block text-xs font-semibold text-muted-foreground mb-1">Categoría</label>
                    <div className="space-y-2">
                        {[...cats, ''].map((sel, idx) => {
                          const otras = cats.filter((_, i) => i !== idx);
                          const opciones = TODAS_CATEGORIAS.filter(c => !otras.includes(c.clave));
                          return (
                            <select
                                key={idx}
                                value={sel}
                                onChange={e => setCatAt(idx, e.target.value)}
                                className="w-full border border-input rounded-lg px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-brand-orange/40"
                            >
                                <option value="">
                                    {idx === 0 ? 'Todas las categorías' : (sel ? 'Quitar este filtro' : 'Añade otra categoría para ajustar')}
                                </option>
                                {opciones.map((c, i) => (
                                    <React.Fragment key={c.clave}>
                                    {c.esSuprema && i > 0 && <option disabled>&nbsp;</option>}
                                    <option value={c.clave}
                                        className={c.esSuprema ? 'font-bold text-foreground' : 'font-normal text-muted-foreground'}>
                                        {c.esSuprema ? c.valor : `  ${c.valor}`}
                                    </option>
                                    </React.Fragment>
                                ))}
                            </select>
                          );
                        })}
                    </div>

                    {/* Opciones */}
                    <label className="block text-xs font-semibold text-muted-foreground mt-3 mb-1">Opciones</label>
                    <div className="flex flex-col gap-1">
                        <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
                            <input type="radio" name="opcion" checked={opcion === 'genericos'} onChange={() => {}}
                                onClick={() => setOpcion(opcion === 'genericos' ? '' : 'genericos')}
                                className="appearance-none shrink-0 w-3.5 h-3.5 rounded-full border border-input bg-card checked:bg-brand-orange checked:border-brand-orange cursor-pointer" />
                            Mostrar sólo genéricos
                        </label>
                        <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
                            <input type="radio" name="opcion" checked={opcion === 'sinMacros'} onChange={() => {}}
                                onClick={() => setOpcion(opcion === 'sinMacros' ? '' : 'sinMacros')}
                                className="appearance-none shrink-0 w-3.5 h-3.5 rounded-full border border-input bg-card checked:bg-brand-orange checked:border-brand-orange cursor-pointer" />
                            Verduras libres
                        </label>
                    </div>
                </div>

                {loading ? (
                    <div className="flex justify-center py-16">
                        <div className="animate-spin w-8 h-8 border-2 border-brand-orange border-t-transparent rounded-full" />
                    </div>
                ) : (
                    <>
                        {/* Cuántos hay y cuántos se están viendo. Sin esta línea, cortar la
                            lista se lee como que no hay más. */}
                        {filtered.length > 0 && (
                            <p className="text-sm text-muted-foreground mb-2" data-testid="cuantos-alimentos">
                                <b className="text-foreground">{filtered.length}</b> alimento{filtered.length === 1 ? '' : 's'}
                                {aLaVista < filtered.length ? ` · viendo ${aLaVista}` : ''}
                            </p>
                        )}
                        <div className="space-y-2">
                            {filtered.slice(0, aLaVista).map((f, i) => (
                                <FoodRow key={f.id ?? i} food={f} />
                            ))}
                            {filtered.length === 0 && (
                                <p className="text-center text-muted-foreground text-sm py-12">Sin resultados</p>
                            )}
                        </div>
                        {aLaVista < filtered.length && (
                            <button onClick={() => setDeMas(n => n + porTanda)} data-testid="ver-mas-alimentos"
                                className="w-full mt-3 py-3 rounded-xl border border-border text-sm font-bold text-muted-foreground hover:text-brand-orange hover:border-brand-orange/40 transition-colors">
                                Ver {Math.min(porTanda, filtered.length - aLaVista)} más
                            </button>
                        )}
                    </>
                )}
            </div>
            <SuggestFoodModal open={suggestOpen} onClose={() => setSuggestOpen(false)} />
        </div>
    );
};

export default FoodSearchPage;
