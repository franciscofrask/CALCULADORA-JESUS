import React, { useState, useEffect, useMemo } from 'react';
import { Search, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { descripcionCategoria, CATEGORIA_NOMBRES } from '../components/nutrition/calmaCategorias';
import SuggestFoodModal from '../components/nutrition/SuggestFoodModal';
import SinResultados from '../components/nutrition/SinResultados';
import { useEsTelefono } from '../lib/esTelefono';
import { num1 } from '../lib/numeros';
// La búsqueda por nombre (filtro + relevancia, portada de Calma) vive en lib para que la
// use también el panel de «Añadir ingrediente» de Nutrición: era el mismo catálogo con dos
// buscadores distintos, y el de montar la dieta era el roto (Jesús, 15-08).
import { matchWord, matchAll, relevancia } from '../lib/busquedaAlimentos';
import { esGenerico } from '../lib/generico';

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
    // GEN va por `lib/generico`, no por «no tiene enlace»: había seis alimentos de marca sin
    // enlace en producción y este filtro los daba por genéricos (29-08).
    GEN: esGenerico,
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

// SIN COLORES (punto 160 del 27-08). Aquí había una píldora por macro -- verde la proteína,
// azul los hidratos, rojo la grasa -- y eso rompía la regla de color de la app, que está
// escrita en la parte 4: «verde si ese macro ya está resuelto, naranja si te has pasado, sin
// color mientras vas por debajo». El color significa ESTADO, no tipo de macro, y aquí se
// estaba usando la misma paleta con dos significados distintos en la misma aplicación: el
// cliente aprende en Inicio que verde es «ya está», entra en Alimentos y ve verde en la
// proteína de los 3.211. Encima aparecía el azul, que no existe en el sistema.
// En el buscador no hay ningún estado que pintar -- es un catálogo, no su día --, así que los
// números van en el color del texto. Y de paso caben en una línea: en el móvil las píldoras
// partían «11 g grasa» a la línea siguiente.

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

// Lo mismo, para los que ya vienen en {P,H,G}: `macros_reales` y `necesitas`.
const linea_PHG = (m) => ['P', 'H', 'G']
    .filter((k) => Number(m?.[k] || 0) > 0)
    .map((k) => `${r1(m[k])} ${k}`)
    .join(' · ');

// POR CUÁNTO ES, Y VA LO PRIMERO (punto 146). «No es lo mismo por 100 g que por unidad, de
// 63 g que por unidad, de 125 g. Sin ese dato, los números de debajo no significan nada»:
// los 38,8 hidratos de la tarrina son de la tarrina entera, y quien los lea como por 100 g
// se equivoca en un 25%. Los mililitros son de los líquidos y los pone el servidor.
const porCuantoEs = (food) => (food.unidades
    ? `por unidad, de ${r1(food.racion)} g`
    : `por 100 ${food.es_liquido ? 'ml' : 'g'}`);

// UNA CATEGORÍA, NO CUATRO (punto 153). Salían las cuatro seguidas -- «Frutos secos sin
// grasas y/o azúcares añadidos | Listo para comer | Alimentos ricos en grasas de buena
// calidad | Frutos secos» -- y se comían dos líneas. Queda la primera, «que es la que
// manda»; las otras son ramas padre y etiquetas operativas.
//
// LA PRIMERA NUMÉRICA, no la primera a secas: en `categorias` las etiquetas transversales
// (YA, POL, SNA...) van mezcladas con los códigos, y medido contra producción hay 35 fichas
// de 3.219 donde la etiqueta va delante -- «Harina de espelta integral (Hacendado)» es
// `POL | 7.2.3` --, que con la regla ingenua saldrían clasificadas como «En polvo».
//
// Y no es decoración: la categoría explica las otras dos líneas. Las almendras cuentan grasa
// porque son frutos secos sin grasas añadidas, y su mínimo sale de lo mismo.
const esCodigoNumerico = (c) => /^\d/.test(c);
const categoriaQueManda = (food) => {
    const cats = foodCats(food);
    const clave = cats.find(esCodigoNumerico) || cats[0];
    return (clave && descripcionCategoria(clave)) || '';
};

/**
 * UN ALIMENTO, EN CUATRO LÍNEAS Y TODAS A LA IZQUIERDA (puntos 145 a 155 del 27-08).
 *
 *   [·] Almendras                                    GENÉRICO
 *       Frutos secos sin grasas y/o azúcares añadidos · por 100 g
 *       Te cuenta la grasa   53,1 G
 *       Desde 10 g · necesitas 5,3 G
 *
 * Antes los macros iban arrinconados en la esquina derecha, en un tercio del ancho, y en el
 * móvil ese tercio era la mitad de estrecho. Todo a la izquierda, como en CALMA.
 *
 * EL NOMBRE ABRE LA FICHA; LA WEB TIENE SU BOTÓN (punto 152). Hasta hoy el nombre subrayado
 * ERA el enlace, así que tocar el de una marca te sacaba de la aplicación a la web del
 * supermercado y tocar el de un genérico abría la ficha: el mismo gesto hacía dos cosas
 * distintas. Ahora el nombre siempre abre la ficha, la web va aparte y con su flecha, y el
 * nombre deja de ir subrayado (en veinte resultados eso era bastante ruido).
 * En la esquina, o `GENÉRICO` o `Ver web ↗`: poner las dos en una marca sobra, porque si hay
 * web es que es una marca.
 *
 * AL ABRIRLO, LOS REALES Y LA CALIBRACIÓN ENTERA (punto 154). Los macros reales bajan aquí
 * -- antes se comían un renglón en la lista, y en veinte resultados eso es una pantalla --
 * y con ellos los tres tramos, con el del cliente marcado. La categoría no se repite dentro:
 * ya salió arriba. Y ahora se puede abrir CUALQUIER alimento, no solo los que llevan punto.
 */
const FoodRow = ({ food }) => {
    const categoria = categoriaQueManda(food);
    const [abierto, setAbierto] = React.useState(false);
    const cal = food.calibracion;
    const reales = linea_PHG(food.macros_reales);
    const necesita = linea_PHG(food.necesitas);
    // «Come lo que quieras» / «Bebe lo que quieras» ocupa el sitio del número cuando no le
    // cuenta nada (punto 150). El verbo lo decide si se bebe: es lo que hace la maqueta con
    // la Coca-Cola Zero, y decirle «come» a un refresco se nota.
    const loQueQuieras = `${food.es_liquido ? 'Bebe' : 'Come'} lo que quieras`;
    return (
        <div className="bg-card border border-border rounded-lg p-3 shadow-sm" data-testid="alimento">
            {/* Línea 1 · el nombre, y al lado GENÉRICO o Ver web ↗ */}
            <div className="flex items-start justify-between gap-2">
                <button onClick={() => setAbierto((v) => !v)} data-testid={`abrir-${food.id}`}
                    aria-expanded={abierto}
                    className="min-w-0 flex items-start gap-1.5 text-left">
                    {/* EL PUNTO, Y NADA MÁS (punto 138). «Cero texto añadido por alimento. Y
                        el punto separa los que dependen de la cantidad de los que no — hoy
                        los tres se ven exactamente igual.»
                        EL MISMO PUNTO QUE EL DE LA LEYENDA (punto 155): arriba va de viñeta y
                        aquí pegado al nombre, y si no fueran idénticos no se entendería que
                        hablan de lo mismo. Si se toca uno, se tocan los dos. */}
                    {cal && <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand flex-shrink-0"
                        title="Te cuenta más proteína cuanta más cantidad comes en el día" />}
                    <span className="text-sm font-medium text-foreground break-words">{food.nombre}</span>
                </button>
                {food.url ? (
                    <a href={food.url} target="_blank" rel="noopener noreferrer"
                        data-testid={`ver-web-${food.id}`}
                        className="flex-shrink-0 text-xs font-semibold text-brand-orange whitespace-nowrap">
                        Ver web ↗
                    </a>
                ) : esGenerico(food) ? (
                    /* Y «GENÉRICO» solo si lo es. Esto lo ponía a todo lo que no tuviera web,
                       así que el «Chicharrón ibérico (7 Hermanos)» salía etiquetado como
                       genérico con la marca escrita al lado (29-08). Los de marca sin web no
                       llevan etiqueta: no hay web que ofrecer y genéricos no son. */
                    <span data-testid={`generico-${food.id}`}
                        className="flex-shrink-0 text-[10px] uppercase tracking-wider text-muted-foreground whitespace-nowrap">
                        Genérico
                    </span>
                ) : null}
            </div>

            {/* Línea 2 · la categoría que manda y por cuánto es */}
            <p className="text-xs text-muted-foreground mt-1" data-testid={`categoria-${food.id}`}>
                {[categoria, porCuantoEs(food)].filter(Boolean).join(' · ')}
            </p>

            {/* Línea 3 · qué te cuenta, y el número.
                La frase la arma el servidor comparando lo que el alimento TIENE con lo que de
                verdad le cuenta (`_que_te_cuenta`). Antes esto ponía «Necesita 9g proteínas /
                5.5g hidratos / 5.5g grasas para ser sugerido», que es el filtro del tercio
                dicho al revés y en lenguaje de programador, justo en la pantalla donde alguien
                viene a entender por qué la app le cuenta unas cosas y otras no (Jesús, 11-08). */}
            <p className="text-xs mt-1 flex flex-wrap items-baseline gap-x-2" data-testid={`cuenta-${food.id}`}>
                <span className="text-brand-orange">{food.que_te_cuenta}</span>
                <span className="text-foreground font-data">
                    {food.tiene_macros ? lineaDeMacros(food) : loQueQuieras}
                </span>
            </p>

            {/* Línea 4 · desde cuánto, y cuánto necesita.
                Los dos juntos porque separados no dicen nada: 10 g solo es un número y 5,3 G
                solo es otro (punto 148). Y en los que no cuentan nada el mínimo existe igual
                -- no se meten 10 g de lechuga -- pero no hay que comprobar si cabe: «siempre
                cabe», que en CALMA es «Siempre puede ser sugerido» (punto 150). */}
            {food.desde && (
                <p className="text-xs text-muted-foreground mt-1 font-data" data-testid={`desde-${food.id}`}>
                    Desde {food.desde} · {necesita ? `necesitas ${necesita}` : 'siempre cabe'}
                </p>
            )}

            {/* AL ABRIRLO: LOS REALES Y LA CALIBRACIÓN ENTERA (punto 154). */}
            {abierto && (
                <div className="mt-2 rounded-lg bg-muted/50 p-2.5 space-y-2" data-testid={`ficha-${food.id}`}>
                    {/* TENER MACROS Y CONTARLOS NO ES LO MISMO (punto 151). El kétchup zero
                        tiene 1,6 P · 5,4 H · 0,1 G y no le cuentan, así que sí lleva esta
                        fila; la lechuga no la lleva porque no tiene macros que enseñar. Es
                        donde mejor se ve para qué están las dos cifras. */}
                    {reales && (
                        <p className="text-xs text-muted-foreground font-data">
                            <span className="font-sans text-[10px] uppercase tracking-wider mr-1.5">Macros reales</span>
                            {reales}
                        </p>
                    )}
                    {cal && (
                        <div className="space-y-1">
                            <p className="text-[11px] text-muted-foreground">
                                Su proteína, según lo que lleves de <b className="text-foreground">{cal.familia}</b> en todo el día:
                            </p>
                            {[
                                { hasta: `hasta ${cal.tramos[0]} g`, que: 'nada' },
                                { hasta: `de ${cal.tramos[0]} a ${cal.tramos[1]} g`, que: 'la mitad' },
                                { hasta: `más de ${cal.tramos[1]} g`, que: 'toda' },
                            ].map((t) => (
                                <p key={t.hasta} className="text-xs flex items-center justify-between gap-3">
                                    <span className="text-muted-foreground">{t.hasta}</span>
                                    <span className="font-semibold text-foreground">{t.que}</span>
                                </p>
                            ))}
                        </div>
                    )}
                    {/* Un alimento sin reales y sin calibración se puede abrir igual -- el
                        gesto tiene que ser el mismo en los 3.211 -- y entonces esto dice lo
                        único que queda por decir. */}
                    {!reales && !cal && (
                        <p className="text-xs text-muted-foreground">
                            De este alimento te cuenta lo que pone arriba, comas la cantidad que comas.
                        </p>
                    )}
                </div>
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
        if (opcion === 'genericos') list = list.filter(esGenerico);          // ni enlace ni marca
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
                    {/* SE ENTRA Y SE ESCRIBE (punto 156 del 27-08). Antes de llegar al campo
                        de buscar había cinco párrafos y el botón de pedir, así que en el móvil
                        había que hacer scroll para poder escribir, que es a lo que se entra.
                        El orden es: campo · filtros · leyenda · resultados, y el enlace de
                        pedir al final de la lista. */}
                    <h1 className="text-xl font-bold text-foreground mb-3">Buscador de alimentos</h1>

                    <div className="relative mb-3">
                        <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                            type="text"
                            value={query}
                            onChange={e => setQuery(e.target.value)}
                            placeholder="Texto en el alimento"
                            data-testid="buscador-campo"
                            className="w-full bg-card text-foreground placeholder:text-muted-foreground border border-input rounded-lg pl-9 pr-9 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-orange/40"
                        />
                        {query && (
                            <button onClick={() => setQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-muted-foreground">
                                <X className="w-4 h-4" />
                            </button>
                        )}
                    </div>

                    {/* LOS TRES FILTROS, EN UNA FILA (punto 156). Eran seis líneas: la etiqueta
                        «Categoría» con su desplegable, la etiqueta «Opciones» con la suya y dos
                        redondeles. Ahora van juntos y sin etiquetas: el desplegable ya dice
                        «Todas las categorías» y los dos botones dicen lo que hacen.
                        La cascada se conserva -- se pueden encadenar varias categorías para
                        ajustar -- y los desplegables de más solo aparecen cuando ya hay una
                        escogida, que es cuando ocupan sitio por algo. */}
                    <div className="flex flex-wrap items-start gap-2">
                        {[...cats, ''].map((sel, idx) => {
                          const otras = cats.filter((_, i) => i !== idx);
                          const opciones = TODAS_CATEGORIAS.filter(c => !otras.includes(c.clave));
                          return (
                            <select
                                key={idx}
                                value={sel}
                                onChange={e => setCatAt(idx, e.target.value)}
                                data-testid={`filtro-categoria-${idx}`}
                                className="flex-1 min-w-[11rem] border border-input rounded-lg px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-brand-orange/40"
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
                        {/* «NO APORTAN MACROS», QUE ES COMO SE LLAMA EN CALMA (punto 150).
                            Se llamaba «Verduras libres» y dejaba fuera a la mitad de lo que
                            filtra: el Aquarius zero, la Coca-Cola Zero, la Fanta Zero, el
                            Powerade zero y el kétchup de Heinz no son verduras y salen aquí,
                            porque lo que tienen en común es que no cuentan, no que sean
                            verdura. */}
                        {/* Los dos van EN SU PROPIA CAJA para que compartan línea: sueltos en
                            el `flex-wrap` de fuera, el desplegable se lleva la primera fila
                            entera y cada botón caía en la suya, que son tres líneas otra vez.
                            Juntos caben de sobra en 390 px. */}
                        <div className="flex items-center gap-2">
                            {[['genericos', 'Sólo genéricos'], ['sinMacros', 'No aportan macros']].map(([id, texto]) => (
                                <button key={id} type="button" role="checkbox" aria-checked={opcion === id}
                                    data-testid={`filtro-${id}`}
                                    onClick={() => setOpcion(opcion === id ? '' : id)}
                                    className={`flex-shrink-0 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                                        opcion === id
                                            ? 'border-brand-orange bg-brand-orange text-white'
                                            : 'border-input bg-card text-muted-foreground hover:text-foreground'}`}>
                                    {texto}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* LA LEYENDA, EN DOS LÍNEAS (puntos 157 y 159).
                        Se caen los tramos -- «desde 20 g la mitad, desde 40 g toda» y los de
                        cereales y panes --: ahora viven dentro de cada alimento, al abrirlo,
                        con el tramo del cliente marcado, y arriba estaban repetidos y se
                        comían cuatro líneas. Queda lo que no está en ningún otro sitio: qué es
                        un genérico y qué significa el punto.

                        Y LA JERARQUÍA, DEL DERECHO (punto 159). La línea que menos dice -- la
                        de «busca entre todos los alimentos» -- iba más grande que las dos que
                        explican el método. Ahora es la pequeña.

                        LAS DOS PALABRAS EN NEGRITA, no una: `genéricos` y `marcas` son los dos
                        términos que se definen, y con una sola parecía que solo se definía uno.
                        Y el guion, que se había cambiado por dos puntos.

                        LO QUE DICE DE LAS MARCAS SE REESCRIBE. El punto 137 decía «llevan el
                        nombre subrayado en naranja y tocando el nombre vas a su web», y el
                        punto 152 quita las dos cosas: ya no hay subrayado y el nombre abre la
                        ficha. Mantener la frase sería describir algo que no pasa. */}
                    <p className="text-xs text-muted-foreground mt-3">
                        Busca entre todos los alimentos cargados en la calculadora.
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                        Los <b className="text-foreground">genéricos</b> son alimentos sin marca - pollo, arroz, almendras.
                        Las <b className="text-foreground">marcas</b> llevan <span className="text-brand-orange font-semibold">Ver web ↗</span>.
                    </p>
                    <p className="text-sm text-muted-foreground mt-1 flex items-start gap-1.5">
                        {/* El mismo punto que el de la lista (punto 155): mismo tamaño y mismo
                            color, o no se entiende que hablen de lo mismo. */}
                        <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand flex-shrink-0" />
                        <span>
                            Los que llevan punto te cuentan <b className="text-foreground">más proteína cuanta más cantidad comes en el día</b>. Ábrelos para ver desde cuánto.
                        </span>
                    </p>
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
                            {filtered.length === 0 && <SinResultados />}
                        </div>
                        {aLaVista < filtered.length && (
                            <button onClick={() => setDeMas(n => n + porTanda)} data-testid="ver-mas-alimentos"
                                className="w-full mt-3 py-3 rounded-xl border border-border text-sm font-bold text-muted-foreground hover:text-brand-orange hover:border-brand-orange/40 transition-colors">
                                Ver {Math.min(porTanda, filtered.length - aLaVista)} más
                            </button>
                        )}
                        {/* EL ENLACE DE PEDIR, AL FINAL DE LA LISTA (punto 158).
                            Estaba arriba del todo, en amarillo y a media pantalla de ancho,
                            antes incluso del texto que explica la pantalla: era lo primero que
                            se veía. Aquí abajo lo encuentra el que ha mirado los veinte
                            resultados y de verdad no está -- con 121 clientes, un botón así
                            arriba son solicitudes todos los días -- y ni siquiera hace falta
                            botón, basta el enlace. Ese amarillo, además, no era de la casa: no
                            aparece en ninguna otra pantalla. */}
                        <p className="text-sm text-muted-foreground text-center mt-6" data-testid="pedir-alimento">
                            ¿No encuentras alguno?{' '}
                            <button onClick={() => setSuggestOpen(true)}
                                className="font-semibold text-brand-orange underline underline-offset-2">
                                Solicitar alimento
                            </button>
                        </p>
                    </>
                )}
            </div>
            <SuggestFoodModal open={suggestOpen} onClose={() => setSuggestOpen(false)} />
        </div>
    );
};

export default FoodSearchPage;
