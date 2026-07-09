import React, { useState, useEffect, useMemo } from 'react';
import { Search, X, Plus } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { descripcionCategoria, CATEGORIA_NOMBRES } from '../components/nutrition/calmaCategorias';
import SuggestFoodModal from '../components/nutrition/SuggestFoodModal';

// Calma $() token match: token === code OR token starts with `${code}.<digit>`.
const tokenMatchesCode = (token, code) =>
    token === code ||
    (token.startsWith(code + '.') && token.length > code.length + 1 && /\d/.test(token[code.length + 1]));

const foodCats = (food) => String(food.categorias || '').split('|').map(t => t.trim()).filter(Boolean);

// redondeo Calma d(n,1)
const r1 = (n) => Math.round(Number(n || 0) * 10) / 10;

// ── Búsqueda y orden, portados de Calma (group-home-utils) ──────────────────
const norm = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase(); // h()
const lenOk = (e, r) => (r === '' ? true : !(!r || !e.length || ('' + r).length > e.length)); // H()
const inc = (e, r) => (lenOk(e, r) ? e.includes(r) : false); // L()
const matchWord = (e, r) => (lenOk(e, r) ? inc(norm(e), norm(r)) : false); // E()
const matchAll = (nombre, words) => words.every(w => matchWord(nombre, w)); // P(...,true)

// Ie(): puntuación de relevancia (mayor = mejor coincidencia con el nombre)
const relevancia = (nombre, words) => {
    let n = 0;
    const t = nombre.toUpperCase();
    const s = t.split(' ');
    const a = norm(nombre);
    const ia = s.map(norm);
    for (const f of words) {
        const l = f.toUpperCase();
        const p = norm(f);
        if (t === l) n += 5;
        if (a === p) n += 5;
        if (t.startsWith(l)) n += 4;
        if (a.startsWith(p)) n += 4;
        if (s.some(u => u === l)) n += 3;
        if (ia.some(u => u === p)) n += 2;
        if (s.some(u => u.startsWith(l))) n += 2;
        if (ia.some(u => u.startsWith(p))) n += 1;
        if (s.some(u => inc(u, l))) n += 1;
        if (ia.some(u => matchWord(u, p))) n += 1;
    }
    return n;
};

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

const RENDER_CAP = 300;

// Calma EtiquetasMacros: badge por macro > 0 (P verde, H azul, G rojo), 1 decimal.
const MACRO_DEFS = [
    ['proteinas', 'proteínas', 'bg-green-100 text-green-700'],
    ['hidratos', 'hidratos', 'bg-blue-100 text-blue-700'],
    ['grasas', 'grasas', 'bg-red-100 text-red-700'],
];

const FoodRow = ({ food }) => {
    const cats = foodCats(food).map(descripcionCategoria).filter(Boolean);
    return (
        <div className="bg-card border border-border rounded-lg p-3 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-1 sm:gap-3">
                <div className="min-w-0">
                    {food.url ? (
                        <a href={food.url} target="_blank" rel="noopener noreferrer"
                            className="text-sm font-medium text-[#FF671F] hover:underline break-words">
                            {food.nombre}
                        </a>
                    ) : (
                        <span className="text-sm font-medium text-foreground break-words">{food.nombre}</span>
                    )}
                </div>
                <div className="flex-shrink-0 sm:text-right">
                    {food.tiene_macros ? (
                        <>
                            <div className="flex flex-wrap gap-1 sm:justify-end">
                                {MACRO_DEFS.map(([k, label, cls]) =>
                                    Number(food[k] || 0) > 0 ? (
                                        <span key={k} className={`text-xs px-2 py-0.5 rounded-full font-medium tabular-nums ${cls}`}>
                                            {r1(food[k])} {label}
                                        </span>
                                    ) : null
                                )}
                            </div>
                            <p className="text-xs text-muted-foreground mt-1">
                                por cada {food.unidades ? `unidad de ${food.racion}g` : '100 gramos'}
                            </p>
                        </>
                    ) : (
                        <em className="text-xs text-muted-foreground">No aporta macros</em>
                    )}
                </div>
            </div>
            {cats.length > 0 && (
                <p className="text-xs text-muted-foreground mt-1">{cats.join(' | ')}</p>
            )}
            {food.cantidad_minima != null && (
                <p className="text-xs text-muted-foreground">cantidad mínima: {food.cantidad_minima}</p>
            )}
            {food.sugerencia && (
                <p className="text-xs text-brand-orange">{food.sugerencia}</p>
            )}
            {food.info_etiqueta && (
                <p className="text-xs text-muted-foreground">Información de etiqueta: {food.info_etiqueta}</p>
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

    return (
        <div className="min-h-screen bg-background p-4 md:p-6">
            <div className="max-w-3xl mx-auto">
                <div className="bg-card border border-border rounded-xl p-4 mb-4">
                    <div className="flex items-start justify-between gap-3 mb-1">
                        <h1 className="text-xl font-bold text-foreground">Buscador de alimentos</h1>
                        <button
                            onClick={() => setSuggestOpen(true)}
                            className="flex-shrink-0 inline-flex items-center gap-1.5 bg-brand-orange hover:bg-brand-orange/90 text-white text-sm font-medium rounded-lg px-3 py-2 transition-colors"
                        >
                            <Plus className="w-4 h-4" />
                            Sugerir alimento
                        </button>
                    </div>
                    <p className="text-muted-foreground text-sm mb-4">
                        Busca entre todos los alimentos cargados en la calculadora. Ordenados por coincidencia con el nombre.
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

                    {/* Categoría (cascada: añade más para afinar) */}
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
                                    {idx === 0 ? 'Todas las categorías' : (sel ? 'Quitar este filtro' : 'Añade otra categoría para afinar')}
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
                            No aportan macros
                        </label>
                    </div>
                </div>

                {loading ? (
                    <div className="flex justify-center py-16">
                        <div className="animate-spin w-8 h-8 border-2 border-brand-orange border-t-transparent rounded-full" />
                    </div>
                ) : (
                    <>
                        <div className="space-y-2">
                            {filtered.slice(0, RENDER_CAP).map((f, i) => (
                                <FoodRow key={f.id ?? i} food={f} />
                            ))}
                            {filtered.length === 0 && (
                                <p className="text-center text-muted-foreground text-sm py-12">Sin resultados</p>
                            )}
                        </div>
                    </>
                )}
            </div>
            <SuggestFoodModal open={suggestOpen} onClose={() => setSuggestOpen(false)} />
        </div>
    );
};

export default FoodSearchPage;
