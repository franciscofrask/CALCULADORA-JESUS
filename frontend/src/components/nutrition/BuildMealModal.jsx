/**
 * BuildMealModal - Modal para construir comidas paso a paso
 * Extraído de NutritionPage.jsx para mejor mantenibilidad
 */
import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { ScrollArea } from '../ui/scroll-area';
import { toast } from 'sonner';
import { Search, X, Plus, Minus, Star } from 'lucide-react';
import {
    faStopwatch20,
    faEgg, faBacon, faBurger, faDove, faCow, faPiggyBank, faDrumstickBite,
    faFish, faCheese, faJar, faJarWheat, faSeedling, faBowlRice,
    faBreadSlice, faPlateWheat, faBowlFood, faCarrot, faAppleWhole,
    faLeaf, faBottleWater, faBolt, faBlender, faPizzaSlice, faCookie,
    faPepperHot, faBottleDroplet, faOilCan,
    faCircleInfo, faDroplet, faCookieBite, faScaleBalanced,
    faSquareCheck, faWheatAwnCircleExclamation, faSnowflake, faRing,
    faThumbsUp, faClock, faFireBurner, faMedal,
    faMugHot, faTrowelBricks, faCandyCane, faIceCream, faSmog,
} from '@fortawesome/free-solid-svg-icons';

const FREQUENT_CATEGORY = {
    id: '__frequent__',
    value: '__frequent__',
    label: 'Alimentos frecuentes',
    icon: faStopwatch20,
};
import CategoryRail from './CategoryRail';
import { PREFERENCE_CATEGORIES } from './PreferencesSetup';

// Categories - Step 1 (Proteínas)
const PROTEIN_CATEGORIES = [
    { id: 'huevos',         value: 'huevos',         label: 'Huevos y derivados', emoji: '🥚', icon: faEgg,         prefixes: ['1'] },
    { id: 'embutidos',      value: 'embutidos',      label: 'Embutidos',        emoji: '🥓', icon: faBacon,         prefixes: ['2.1'] },
    { id: 'aves',           value: 'aves',           label: 'Aves',             emoji: '🍗', icon: faDove,          prefixes: ['2.2'] },
    { id: 'vacuno',         value: 'vacuno',         label: 'Vacuno',           emoji: '🥩', icon: faCow,           prefixes: ['2.3'] },
    { id: 'cerdo',          value: 'cerdo',          label: 'Cerdo',            emoji: '🐷', icon: faPiggyBank,     prefixes: ['2.4'] },
    { id: 'otras_carnes',   value: 'otras_carnes',   label: 'Otras carnes',     emoji: '🍖', icon: faDrumstickBite, prefixes: ['2.6', '2.7', '45'] },
    { id: 'pescados',       value: 'pescados',       label: 'Pescados',         emoji: '🐟', icon: faFish,          prefixes: ['3'] },
    { id: 'lacteos',        value: 'lacteos',        label: 'Lácteos',          emoji: '🧀', icon: faCheese,        prefixes: ['5'] },
    { id: 'proteina_polvo', value: 'proteina_polvo', label: 'Proteína',         emoji: '🥤', icon: faJar,           prefixes: ['30'] },
    { id: 'vegetal',        value: 'vegetal',        label: 'Proteína vegetal', emoji: '🌱', icon: faJarWheat,      prefixes: ['28', '6'] },
    { id: 'legumbres',      value: 'legumbres',      label: 'Legumbres',        emoji: '🫘', icon: faSeedling,      prefixes: ['10'] },
];

// Categories - Step 2 (Acompañamientos)
const SIDE_CATEGORIES = [
    { id: 'arroces',     value: 'arroces',     label: 'Arroces',      emoji: '🍚', icon: faBowlRice,      prefixes: ['21'] },
    { id: 'panes',       value: 'panes',       label: 'Panes',        emoji: '🍞', icon: faBreadSlice,    prefixes: ['8'] },
    { id: 'cereales',    value: 'cereales',    label: 'Cereales',     emoji: '🌾', icon: faPlateWheat,    prefixes: ['7'] },
    { id: 'pasta',       value: 'pasta',       label: 'Pasta',        emoji: '🍝', icon: faBowlFood,      prefixes: ['22'] },
    { id: 'tuberculos',  value: 'tuberculos',  label: 'Tubérculos',   emoji: '🥔', icon: faCarrot,        prefixes: ['9'] },
    { id: 'fruta',       value: 'fruta',       label: 'Fruta',        emoji: '🍎', icon: faAppleWhole,    prefixes: ['11'] },
    { id: 'verduras',    value: 'verduras',    label: 'Verduras',     emoji: '🥬', icon: faLeaf,          prefixes: ['13'] },
    { id: 'legumbres',   value: 'legumbres',   label: 'Legumbres',    emoji: '🫘', icon: faSeedling,      prefixes: ['10'] },
    { id: 'lacteos',     value: 'lacteos',     label: 'Lácteos',      emoji: '🧀', icon: faCheese,        prefixes: ['5'] },
    { id: 'bebidas',     value: 'bebidas',     label: 'Bebidas',      emoji: '🥤', icon: faBolt,          prefixes: ['19', '24'] },
    { id: 'comida_prep', value: 'comida_prep', label: 'Comida prep.', emoji: '🍕', icon: faPizzaSlice,    prefixes: ['32', '39', '49', '50', '51', '53'] },
    { id: 'dulces',      value: 'dulces',      label: 'Dulces',       emoji: '🍫', icon: faCookie,        prefixes: ['29', '30', '31', '34', '35', '36', '37', '43', '44', '47'] },
    { id: 'salsas',      value: 'salsas',      label: 'Salsas',       emoji: '🥫', icon: faPepperHot,     prefixes: ['16'] },
    { id: 'grasas',      value: 'grasas',      label: 'Grasas',       emoji: '🫒', icon: faBottleDroplet, prefixes: ['17'] },
    { id: 'sopas',       value: 'sopas',       label: 'Sopas',        emoji: '🍲', icon: faMugHot,        prefixes: ['48'] },
];

// Step 3 - fat sources
const FAT_CATEGORIES = [
    { id: 'grasas_buenas', value: 'grasas_buenas', label: 'Grasas de buena calidad', icon: faBottleDroplet, prefixes: ['42'] },
    { id: 'grasas_todo',   value: 'grasas_todo',   label: 'Grasas',                  icon: faOilCan,        prefixes: ['17'] },
    { id: 'lacteos',       value: 'lacteos',       label: 'Lácteos',                 icon: faCheese,        prefixes: ['5'] },
    { id: 'huevos',        value: 'huevos',        label: 'Huevos',                  icon: faEgg,           prefixes: ['1'] },
];

// INTRA categories — Calma categoriasIntraentreno: ["18","41"] (chips hidden, pre-active)
const INTRA_CATEGORIES = [
    { id: 'isotonicas',  value: 'isotonicas',  label: 'Isotónicas',  emoji: '💧', icon: faBottleWater, prefixes: ['18'] },
    { id: 'aminoacidos', value: 'aminoacidos', label: 'Aminoácidos', emoji: '⚡', icon: faTrowelBricks, prefixes: ['41'] },
];

// POST categories — single list, Calma categoriasPostentreno order:
// ["4","5","46","7","8","11","27","24","19","37","36","16"]
const POST_CATEGORIES = [
    { id: 'proteina',      value: 'proteina',      label: 'Proteína',          emoji: '💪', icon: faJar,        prefixes: ['4'] },
    { id: 'lacteos',       value: 'lacteos',       label: 'Lácteos',           emoji: '🧀', icon: faCheese,     prefixes: ['5'] },
    { id: 'cremas_arroz',  value: 'cremas_arroz',  label: 'Cremas de arroz',   emoji: '🍚', icon: faBowlRice,   prefixes: ['46'] },
    { id: 'cereales',      value: 'cereales',      label: 'Cereales',          emoji: '🌾', icon: faPlateWheat, prefixes: ['7'] },
    { id: 'pan',           value: 'pan',           label: 'Pan',               emoji: '🍞', icon: faBreadSlice, prefixes: ['8'] },
    { id: 'fruta',         value: 'fruta',         label: 'Fruta',             emoji: '🍎', icon: faAppleWhole, prefixes: ['11'] },
    { id: 'sustitutivos',  value: 'sustitutivos',  label: 'Sustitutivos',      emoji: '🥤', icon: faBlender,    prefixes: ['27'] },
    { id: 'beb_vegetales', value: 'beb_vegetales', label: 'Bebidas vegetales', emoji: '🥛', icon: faBottleWater, prefixes: ['24'] },
    { id: 'bebidas',       value: 'bebidas',       label: 'Bebidas',           emoji: '⚡', icon: faBolt,       prefixes: ['19'] },
    { id: 'azucar',        value: 'azucar',        label: 'Cacao/Azúcar',      emoji: '🍯', icon: faCandyCane,  prefixes: ['37'] },
    { id: 'postres',       value: 'postres',       label: 'Postres',           emoji: '🍮', icon: faIceCream,   prefixes: ['36'] },
    { id: 'salsas',        value: 'salsas',        label: 'Salsas',            emoji: '🥫', icon: faPepperHot,  prefixes: ['16'] },
];

// Ordered to match Calma's `A.preparaciones`:
// [GEN, PRO, FRE, CGE, AHU, LAT, POL, PRE, HAM, SNA, MIN, YCO, UNI, YA, SGL]
const PREPARATIONS = [
    { value: 'GEN', label: 'Genérico',                                 icon: faCircleInfo },
    { value: 'PRO', label: 'Marca recomendada con descuento especial', icon: faMedal },
    { value: 'FRE', label: 'Frescos',                                  icon: faDroplet },
    { value: 'CGE', label: 'Congelados',                               icon: faSnowflake },
    { value: 'AHU', label: 'Ahumados',                                 icon: faSmog },
    { value: 'LAT', label: 'Conservas',                                icon: faRing },
    { value: 'POL', label: 'En polvo',                                 icon: faJar },
    { value: 'PRE', label: 'Preparado',                                icon: faThumbsUp },
    { value: 'HAM', label: 'Hamburguesa / Carne picada',               icon: faBurger },
    { value: 'SNA', label: 'Snacks fáciles de transportar',            icon: faCookieBite },
    { value: 'MIN', label: '1 minuto al micro y listo',                icon: faClock },
    { value: 'YCO', label: 'Ya cocinados',                             icon: faFireBurner },
    { value: 'UNI', label: 'Ya pesado',                                icon: faScaleBalanced },
    { value: 'YA',  label: 'Listo para comer',                         icon: faSquareCheck },
    { value: 'SGL', label: 'Etiquetado "Sin gluten"',                  icon: faWheatAwnCircleExclamation },
];

// Food emojis
const FOOD_EMOJIS = {
    '2': '🥩', '3': '🐟', '1': '🥚', '5': '🥛', '4': '💪',
    '7': '🌾', '8': '🍞', '21': '🍚', '22': '🍝', '9': '🥔',
    '10': '🫘', '11': '🍎', '13': '🥦', '17': '🫒', '17.2': '🥜',
    '16': '🥫', '24': '🥤', '42': '🥑', '28': '🌱', '6': '🌿',
    '32': '🍕', '39': '🥘', '49': '🍔', '50': '🌮', '53': '🍱',
    'default': '🍽️'
};

const getFoodEmojiLocal = (categorias) => {
    if (!categorias) return FOOD_EMOJIS.default;
    const mainCat = categorias.split(' | ')[0]?.split('.')[0];
    return FOOD_EMOJIS[mainCat] || FOOD_EMOJIS.default;
};

const BuildMealModal = ({
    open,
    mealKey,
    mode = 'normal',
    onClose,
    getMealTarget,
    mealInfo,
    api,
    tipoDia,
    mealsData,
    setMealsData,
    getFoodEmoji,
    userPreferences = [],
    avoidedCategories = []
}) => {
    const [paso, setPaso] = useState(1);
    const [tempFoods, setTempFoods] = useState([]);

    const [selectedCategories, setSelectedCategories] = useState([]);
    const [categoryFoods, setCategoryFoods] = useState([]);
    const [loadingFoods, setLoadingFoods] = useState(false);

    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [isSearching, setIsSearching] = useState(false);

    const [selectedFood, setSelectedFood] = useState(null);
    const [adjustedQuantity, setAdjustedQuantity] = useState(0);
    const [adjustedMacros, setAdjustedMacros] = useState({ P: 0, H: 0, G: 0 });

    const [favorites, setFavorites] = useState(new Set());

    // Preparation filter
    const [selectedPreparations, setSelectedPreparations] = useState([]);
    const [availablePreps, setAvailablePreps] = useState([]);

    const isIntraMode = mode === 'intra';
    const isPostMode = mode === 'post';
    const isPeriMode = isIntraMode || isPostMode;

    const target = mealKey ? getMealTarget(mealKey) : { P: 0, H: 0, G: 0 };
    // Calma's macroEnIngredientes sums UNROUNDED per-food contributions (raw post-regla
    // macros × quantity). The stored macros_efectivos are rounded to 1 decimal for display;
    // summing those loses ~0.05 g/food, enough to flip a floor() in the suggested quantity
    // (e.g. tikka H = 26.5×1.37 = 36.305 → remaining 10.495, not 10.5 → Tasty rice 13 g not
    // 14 g) and reorder the list. Rebuild the contribution from the raw fields, gated by
    // macros_efectivos so regla-25% zeroed macros stay zero; fall back to the rounded
    // efectivos when raw fields are absent (older saved diets).
    const foodContrib = (f) => {
        const ef = f.macros_efectivos || {};
        const isUnit = f.por_unidad ?? f.unidades;
        const racion = f.racion || 100;
        const qty = f.cantidad_g ?? f.cantidad ?? 0;
        const factor = isUnit ? (racion ? qty / racion : 0) : qty / 100;
        const m = (rawKey, efVal) => {
            if (!(efVal > 0)) return 0;                       // zeroed by regla -> stays 0
            const raw = f[rawKey];
            return (raw != null && qty) ? raw * factor : (efVal || 0);  // unrounded if raw present
        };
        return { P: m('proteinas', ef.P), H: m('hidratos', ef.H), G: m('grasas', ef.G) };
    };
    const sumContrib = (list, acc) => list.reduce((a, f) => {
        const c = foodContrib(f);
        return { P: a.P + c.P, H: a.H + c.H, G: a.G + c.G };
    }, acc);
    const existingServed = sumContrib(mealsData[mealKey]?.alimentos || [], { P: 0, H: 0, G: 0 });
    const served = sumContrib(tempFoods, { ...existingServed });
    const remaining = {
        P: Math.max(0, target.P - served.P),
        H: Math.max(0, target.H - served.H),
        G: Math.max(0, target.G - served.G)
    };

    useEffect(() => {
        const loadFavorites = async () => {
            try {
                const res = await api('/api/favorites');
                setFavorites(new Set((res.favorites || []).map(String)));
            } catch (e) { /* ignore */ }
        };
        if (open) loadFavorites();
    }, [open]); // eslint-disable-line

    const toggleFavorite = async (foodId) => {
        const fid = Number(foodId);
        const isFav = favorites.has(String(foodId));
        try {
            if (isFav) {
                await api(`/api/favorites/${fid}`, { method: 'DELETE' });
                setFavorites(prev => { const s = new Set(prev); s.delete(String(foodId)); return s; });
            } else {
                await api(`/api/favorites/${fid}`, { method: 'POST' });
                setFavorites(prev => new Set(prev).add(String(foodId)));
            }
        } catch (e) { /* ignore */ }
    };

    // Calma rounds the per-meal target to the nearest 0.5 g FOR DISPLAY ONLY (stepRedondeo):
    // an internal H target of 46.8 shows as "47". The status math below stays UNROUNDED so
    // "Faltan 10.5g" = 46.8 - 36.3, matching Calma exactly.
    const fmtHalf = (x) => (Math.round((x || 0) * 2) / 2).toString();

    // Calma calcularIcono (margenValido = 4), per macro, using r = target - served (UNROUNDED):
    //   round(r)==0 -> Cuadrado (green check) | |r|<4 -> Válido (amber check) |
    //   else danger (red xmark): Faltan r (r>0) / Sobran |r| (r<0).
    const MARGEN_VALIDO = 4;
    const macroStatus = (s, tgt) => {
        if (!tgt) return null;
        const r = tgt - s;                       // remaining, unrounded (Calma: macros - enIngredientes)
        if (Math.round(r) === 0) return { label: 'Cuadrado', cls: 'text-green-600' };
        if (Math.abs(r) < MARGEN_VALIDO) return { label: 'Válido', cls: 'text-amber-500' };
        const g = Math.round(Math.abs(r) * 10) / 10;
        return r > 0
            ? { label: `Faltan ${g}g`, cls: 'text-red-500' }
            : { label: `Sobran ${g}g`, cls: 'text-red-500' };
    };

    const isCuadrada = Math.abs(target.P - served.P) <= 0 &&
                       Math.abs(target.H - served.H) <= 0 &&
                       (isPeriMode || Math.abs(target.G - served.G) <= 0);

    const getBlockReason = (macrosEf) => {
        if (isPeriMode) return null;
        // Calma's tolerance is margenValido = 4 g. Suggested foods are already capped (me)
        // to not overshoot the remaining, so a strict margin=0 only blocked them on rounding
        // (e.g. fill 0.6 g H that lands at 46.8000…1 > 46.8). Use 4 to match Calma.
        const margin = 4;
        if (macrosEf.P > 0 && served.P + macrosEf.P > target.P + margin) {
            return 'No cabe — superaría la proteína objetivo de esta comida.';
        }
        if (macrosEf.H > 0 && served.H + macrosEf.H > target.H + margin) {
            return 'No cabe — superaría los hidratos objetivo de esta comida.';
        }
        if (macrosEf.G > 0 && served.G + macrosEf.G > target.G + margin) {
            return 'No cabe — superaría las grasas objetivo de esta comida.';
        }
        return null;
    };

    const getFoodBlockReason = (food) => {
        const qty = food.racion || 100;
        const factor = qty / 100;
        const macrosEf = {
            P: Math.round((food.proteinas || 0) * factor * 10) / 10,
            H: Math.round((food.hidratos || 0) * factor * 10) / 10,
            G: Math.round((food.grasas || 0) * factor * 10) / 10,
        };
        return getBlockReason(macrosEf);
    };

    const preferenceEmojis = {
        grasas_buenas: '🥑', grasas_todo: '🫒', aperitivos: '🍟', arroces: '🍚',
        aves: '🍗', barritas: '🍫', bebidas: '☕', isotonicas: '⚡',
        beb_vegetales: '🥤', bolleria: '🥐', cacao: '🍯', casqueria: '🥩',
        cerdo: '🐷', cereales: '🌾', chocolates: '🍫', cocina_esp: '🥘',
        comida_rapida: '🍔', embutidos: '🥓', fruta: '🍎', helados: '🍦',
        huevos: '🥚', lacteos: '🧀', legumbres: '🫘', carnes_blancas: '🍖',
        carnes_rojas: '🥩', panes: '🍞', pasta: '🍝', pescados: '🐟',
        pizza: '🍕', proteina_polvo: '💪', proteina_vegetal: '🌱', salsas: '🥫',
        sopas: '🍲', superalimentos: '✨', tuberculos: '🥔', vacuno: '🥩', verduras: '🥬'
    };

    // Calma: filtrosSinAlergias removes chips whose category code is in user's avoid list
    // Chips whose id (or mapped preference id) is in avoidedCategories are hidden
    const CHIP_PREF_MAP = {
        'vegetal': ['proteina_vegetal'],
        'otras_carnes': ['carnes_blancas', 'carnes_rojas'],
    };
    const filterAvoided = (chips) => {
        if (!avoidedCategories || avoidedCategories.length === 0) return chips;
        const avoidSet = new Set(avoidedCategories);
        return chips.filter(chip => {
            const prefIds = CHIP_PREF_MAP[chip.id] || [chip.id];
            return !prefIds.some(id => avoidSet.has(id));
        });
    };

    const getCurrentCategories = () => {
        let base = [];
        if (isIntraMode) {
            base = INTRA_CATEGORIES;
        } else if (isPostMode) {
            // Calma: post is a single phase — all 12 categoriasPostentreno at once (no split).
            base = POST_CATEGORIES;
        } else if (paso === 1) {
            base = filterAvoided(PROTEIN_CATEGORIES);
        } else if (paso === 2) {
            base = filterAvoided(SIDE_CATEGORIES);
        } else if (paso === 3) {
            // Calma: paso 3 (todos) shows the user's preferences in their SAVED order
            // (filtrosDePreferencias = [...preferencias].map — Set insertion order), NOT code
            // order. Paso 1/2 use fixed lists (categoriasProteinas/Hidratos) so code order is
            // right there; paso 3 must follow the user's preference order.
            const byId = new Map(PREFERENCE_CATEGORIES.map(c => [c.id, c]));
            let cats = (userPreferences || [])
                .map(id => byId.get(id))
                .filter(Boolean)
                .map(cat => ({ ...cat, value: cat.id }));
            // grasas_buenas (42) is a fixed preference (Calma fija) — ensure it's present
            if (!cats.find(c => c.id === 'grasas_buenas'))
                cats.unshift({ id: 'grasas_buenas', value: 'grasas_buenas', label: 'Grasas de buena calidad', icon: faBottleDroplet, prefixes: ['42'] });
            base = cats;
        } else {
            base = SIDE_CATEGORIES;
        }
        return [FREQUENT_CATEGORY, ...base];
    };

    useEffect(() => {
        if (open && mealKey) {
            setTempFoods([]);
            // Calma: intra has its category chips hidden and pre-activated (c(e, true)),
            // so foods load immediately. Auto-select the intra categories on open.
            setSelectedCategories(isIntraMode ? INTRA_CATEGORIES.map(c => ({ ...c, value: c.id })) : []);
            setCategoryFoods([]);
            setSearchQuery('');
            setSearchResults([]);
            setIsSearching(false);
            setSelectedFood(null);
            setSelectedPreparations([]);
            setAvailablePreps([]);

            // Determine correct starting paso based on already-saved foods in this meal
            if (!isPeriMode) {
                const ex = (mealsData[mealKey]?.alimentos || []).reduce((acc, f) => ({
                    P: acc.P + (f.macros_efectivos?.P || 0),
                    H: acc.H + (f.macros_efectivos?.H || 0),
                }), { P: 0, H: 0 });
                const t = mealKey ? getMealTarget(mealKey) : { P: 0, H: 0 };
                const pPct = t.P > 0 ? (ex.P / t.P) * 100 : 100;
                const hPct = t.H > 0 ? (ex.H / t.H) * 100 : 100;
                if (pPct >= 80 && hPct >= 80) setPaso(3);
                else if (pPct >= 80) setPaso(2);
                else setPaso(1);
            } else {
                setPaso(1);
            }
        }
    }, [open, mealKey, mode]); // eslint-disable-line

    useEffect(() => {
        if (tempFoods.length === 0) {
            // Only reset to paso 1 if there are no existing saved foods either
            const hasExisting = (mealsData[mealKey]?.alimentos || []).length > 0;
            if (!hasExisting && paso !== 1) {
                setPaso(1);
                setSelectedCategories([]);
                setCategoryFoods([]);
                setSelectedPreparations([]);
                setAvailablePreps([]);
            }
            return;
        }

        if (isPeriMode) return;  // peri (intra/post) is a single phase — no paso split

        const pPct = target.P > 0 ? (served.P / target.P) * 100 : 100;
        const hPct = target.H > 0 ? (served.H / target.H) * 100 : 100;

        if (pPct < 80) {
            if (paso !== 1) {
                setPaso(1);
                setSelectedCategories([]);
                setCategoryFoods([]);
                setSelectedPreparations([]);
                setAvailablePreps([]);
            }
        } else if (pPct >= 80 && hPct < 80) {
            if (paso !== 2) {
                setPaso(2);
                setSelectedCategories([]);
                setCategoryFoods([]);
                setSelectedPreparations([]);
                setAvailablePreps([]);
                toast.info('✅ Proteínas cubiertas. Elige el acompañamiento.');
            }
        } else if (pPct >= 80 && hPct >= 80) {
            if (paso !== 3) {
                setPaso(3);
                setSelectedCategories([]);
                setCategoryFoods([]);
                setSelectedPreparations([]);
                setAvailablePreps([]);
                toast.info('✨ ¡Macros cubiertos! Últimos toques.');
            }
        }
    }, [served.P, served.H, target.P, target.H, tempFoods.length, paso, isIntraMode]);

    // Calma: filtrosActivacionPorDefecto = false. In paso 3 (cuadrarMacros / "últimos
    // toques") the preference category chips are shown but start INACTIVE — the user
    // picks which to finish with. We previously auto-selected all of them, which was a
    // bug (every chip appeared selected and the whole catalog loaded). No pre-activation.

    // Reload foods when macros, categories or preparations change
    useEffect(() => {
        if (!open) return;
        let cancelled = false;
        const hasFrequent = selectedCategories.some(c => c.id === '__frequent__');
        if (hasFrequent) {
            setLoadingFoods(true);
            // Calma: frequent foods (top-20 by raw count) go through the SAME engine —
            // suggested quantity + macro rule + diferencia ordering, using the meal remaining.
            const params = new URLSearchParams({ frequent: 'true', limit: '20' });
            const mp = getMacrosParams();
            Object.entries(mp).forEach(([k, v]) => params.set(k, v));
            api(`/api/calculator/search?${params}`).then(result => {
                if (!cancelled) { setCategoryFoods(result.alimentos || []); setAvailablePreps(result.available_preps || []); }
            }).catch(() => {}).finally(() => { if (!cancelled) setLoadingFoods(false); });
        } else if (selectedCategories.length > 0) {
            setLoadingFoods(true);
            const categoryParam = selectedCategories.flatMap(c => c.prefixes || []).filter(Boolean).join(',');
            const params = new URLSearchParams({ q: '', category: categoryParam, limit: '100' });
            // Calma uses ONE unified remaining (full meal target minus added), all three macros,
            // every step. The "paso" only changes which CATEGORIES are shown, never the macro
            // constraints. Sending only P+G in paso 1 left H unconstrained -> Tortitas 4ud and an
            // order that ignored hidratos. Send all three, no tolerance.
            if (target.P > 0) params.set('p_rest', Math.max(0, remaining.P));
            if (target.H > 0) params.set('h_rest', Math.max(0, remaining.H));
            if (target.G > 0) params.set('g_rest', Math.max(0, remaining.G));
            if (isIntraMode) params.set('peri', 'intra');
            else if (isPostMode) params.set('peri', 'post');
            else if (paso === 3) params.set('cuadrar', 'true');  // good-fat prioridad sort
            if (selectedPreparations.length > 0) params.set('tag', selectedPreparations.join(','));
            api(`/api/calculator/search?${params}`).then(result => {
                if (!cancelled) {
                    setCategoryFoods(result.alimentos || []);
                    setAvailablePreps(result.available_preps || []);
                }
            }).catch(() => {}).finally(() => { if (!cancelled) setLoadingFoods(false); });
        } else if (isSearching && searchQuery.length >= 2) {
            const params = new URLSearchParams({ q: searchQuery, limit: '50', ...getMacrosParams() });
            api(`/api/calculator/search?${params}`).then(result => {
                if (!cancelled) setSearchResults(result.alimentos || []);
            }).catch(() => {});
        }
        return () => { cancelled = true; };
    }, [remaining.P, remaining.H, remaining.G, selectedCategories, selectedPreparations]); // eslint-disable-line

    const getMacrosParams = () => {
        // Calma's manual builder uses ONE unified remaining (full meal target minus
        // added ingredients), all three macros, NO tolerance. The engine (calma_suggest)
        // computes quantity = floor(min(remaining/perUnit)) and orders by diferenciaDeMacros.
        const params = {};
        if (target.P > 0) params.p_rest = Math.max(0, remaining.P);
        if (target.H > 0) params.h_rest = Math.max(0, remaining.H);
        if (target.G > 0) params.g_rest = Math.max(0, remaining.G);
        // Peri meals use their own prioridad lists; paso 3 normal meal = cuadrarMacros.
        if (isIntraMode) params.peri = 'intra';
        else if (isPostMode) params.peri = 'post';
        else if (paso === 3) params.cuadrar = 'true';
        return params;
    };


    const handleCategoriesChange = (ids) => {
        setSelectedCategories(getCurrentCategories().filter(c => ids.includes(c.id)));
        setCategoryFoods([]);
        setSelectedPreparations([]);
    };

    const handleCategoryClick = async (category) => {
        setSelectedCategory(category);
        setSelectedPreparation('');
        setLoadingFoods(true);
        setCategoryFoods([]);
        setAvailablePreps([]);

        try {
            if (category.id === '__frequent__') {
                // Frequent foods through the same engine (quantity + macro rule + diferencia).
                const params = new URLSearchParams({ frequent: 'true', limit: '20', ...getMacrosParams() });
                const result = await api(`/api/calculator/search?${params}`);
                setCategoryFoods(result.alimentos || []);
                setAvailablePreps(result.available_preps || []);
            } else {
                const params = new URLSearchParams({
                    q: '',
                    category: category.prefixes[0],
                    limit: '100',
                    ...getMacrosParams()
                });
                const result = await api(`/api/calculator/search?${params}`);
                setCategoryFoods(result.alimentos || []);
                setAvailablePreps(result.available_preps || []);
            }
        } catch (err) {
            console.error('Error cargando alimentos:', err);
            toast.error('Error cargando alimentos');
        } finally {
            setLoadingFoods(false);
        }
    };

    const handleBackToCategories = () => {
        setSelectedCategory(null);
        setCategoryFoods([]);
    };

    const handleSearch = async (query) => {
        setSearchQuery(query);

        if (query.length < 2) {
            setIsSearching(false);
            setSearchResults([]);
            return;
        }

        setIsSearching(true);
        setLoadingFoods(true);

        try {
            const params = new URLSearchParams({
                q: query,
                limit: '50',
                ...getMacrosParams()
            });
            const result = await api(`/api/calculator/search?${params}`);
            setSearchResults(result.alimentos || []);
        } catch (err) {
            console.error('Error buscando:', err);
        } finally {
            setLoadingFoods(false);
        }
    };

    const handleSelectFood = async (food) => {
        try {
            const foodId = food.id || food._id;
            const alreadyInMeal = (mealsData[mealKey]?.alimentos || []).some(f => f.alimento_id === foodId);
            const alreadyInTemp = tempFoods.some(f => f.alimento_id === foodId);
            if (alreadyInMeal || alreadyInTemp) {
                toast.error(`${food.nombre} ya está en esta comida — ajusta su cantidad directamente.`);
                return;
            }

            const quantity = food._cantidad_sugerida || food.racion || 100;
            const macrosEf = food._macros_sugeridos && Object.keys(food._macros_sugeridos).length > 0
                ? { P: food._macros_sugeridos.P || 0, H: food._macros_sugeridos.H || 0, G: food._macros_sugeridos.G || 0 }
                : {
                    P: Math.round((food.proteinas || 0) * quantity / 100 * 10) / 10,
                    H: Math.round((food.hidratos || 0) * quantity / 100 * 10) / 10,
                    G: Math.round((food.grasas || 0) * quantity / 100 * 10) / 10
                };

            const blockReason = getBlockReason(macrosEf);
            if (blockReason) {
                toast.error(blockReason);
                return;
            }

            const foodToAdd = {
                ...food,
                alimento_id: food.id || food._id,
                cantidad_g: quantity,
                por_unidad: food.por_unidad ?? food.unidades ?? false,
                peso_unidad: food.peso_unidad || food.racion || 100,
                racion: food.racion || 100,
                macros_efectivos: macrosEf
            };

            setTempFoods(prev => [...prev, foodToAdd]);
            setSelectedFood(null);
            setSearchQuery('');
            setIsSearching(false);
            setSearchResults([]);

        } catch (err) {
            console.error('Error añadiendo alimento:', err);
            toast.error('Error al añadir alimento');
        }
    };

    const handleFoodPreview = (food) => {
        const qty = food._cantidad_sugerida || food.racion || 100;
        const macros = food._macros_sugeridos || {
            P: Math.round((food.proteinas || 0) * qty / 100 * 10) / 10,
            H: Math.round((food.hidratos || 0) * qty / 100 * 10) / 10,
            G: Math.round((food.grasas || 0) * qty / 100 * 10) / 10
        };
        setSelectedFood(food);
        setAdjustedQuantity(qty);
        setAdjustedMacros(macros);
    };

    const handleAdjustQuantity = async (delta) => {
        if (!selectedFood) return;
        const isPorUnidad = selectedFood.por_unidad ?? selectedFood.unidades;
        const unitWeight = selectedFood.peso_unidad || selectedFood.racion || 100;
        const step = isPorUnidad ? unitWeight : 1;
        const newQty = Math.max(step, adjustedQuantity + (delta * step));

        try {
            const result = await api('/api/calculator/macros-efectivos', {
                method: 'POST',
                body: JSON.stringify({ alimento_id: selectedFood.id || selectedFood._id, cantidad_g: newQty, es_vegano: false })
            });
            const ef = result.efectivos || {};
            // Calma: free to adjust past the target (bars show over-target). No block.
            setAdjustedQuantity(newQty);
            setAdjustedMacros({ P: ef.P || 0, H: ef.H || 0, G: ef.G || 0 });
        } catch {
            setAdjustedQuantity(newQty);
            const factor = newQty / 100;
            setAdjustedMacros({
                P: Math.round((selectedFood.proteinas || 0) * factor * 10) / 10,
                H: Math.round((selectedFood.hidratos || 0) * factor * 10) / 10,
                G: Math.round((selectedFood.grasas || 0) * factor * 10) / 10
            });
        }
    };

    const handleConfirmAddFood = () => {
        if (!selectedFood) return;

        const foodToAdd = {
            ...selectedFood,
            alimento_id: selectedFood.id || selectedFood._id,
            cantidad_g: adjustedQuantity,
            por_unidad: selectedFood.por_unidad ?? selectedFood.unidades ?? false,
            peso_unidad: selectedFood.peso_unidad || selectedFood.racion || 100,
            racion: selectedFood.racion || 100,
            macros_efectivos: adjustedMacros
        };

        setTempFoods(prev => [...prev, foodToAdd]);
        setSelectedFood(null);
        setSearchQuery('');
        setIsSearching(false);
        setSearchResults([]);
    };

    const handleRemoveFood = (index) => {
        setTempFoods(prev => prev.filter((_, i) => i !== index));
    };

    const handleFoodQuantityChange = (index, delta) => {
        // Calma lets you freely increase/decrease an added food's quantity even past the
        // meal target — the macro bars just show over-target (red). No block.
        setTempFoods(prev => prev.map((f, i) => {
            if (i !== index) return f;
            const isUnit = f.por_unidad ?? f.unidades;
            const racion = f.racion || 100;
            const step = isUnit ? (f.peso_unidad || racion) : 1;
            const currentQty = f.cantidad_g || f.cantidad || 0;
            const newQty = Math.max(step, currentQty + (delta * step));
            // For `unidades` foods the macro fields are PER UNIT, so scale by number of
            // units (newQty/racion), NOT by grams/100 (that's only for granel).
            const mult = isUnit ? (newQty / racion) : (newQty / 100);
            return {
                ...f,
                cantidad_g: newQty,
                macros_efectivos: {
                    P: Math.round((f.proteinas || 0) * mult * 10) / 10,
                    H: Math.round((f.hidratos || 0) * mult * 10) / 10,
                    G: Math.round((f.grasas || 0) * mult * 10) / 10
                }
            };
        }));
    };

    const handleSaveAndClose = () => {
        if (!mealKey || tempFoods.length === 0) return;

        setMealsData(prev => ({
            ...prev,
            [mealKey]: {
                ...prev[mealKey],
                alimentos: [...(prev[mealKey]?.alimentos || []), ...tempFoods]
            }
        }));

        toast.success(`✅ ${tempFoods.length} alimento(s) añadido(s)`);
        onClose();
    };

    const getEmoji = getFoodEmoji || getFoodEmojiLocal;

    const getPasoLabel = () => {
        if (isIntraMode) return 'Alimentos Intra-entreno';
        if (isPostMode) return 'Alimentos Post-entreno';
        if (paso === 1) return 'Paso 1: Proteína';
        if (paso === 2) return 'Paso 2: Acompañamiento';
        return 'Paso 3: Últimos toques';
    };

    // Calma shows ALL category chips for the current phase (filtrosSinAlergias only removes
    // allergy categories); it NEVER hides a category because its foods don't fit the remaining.
    // Individual foods that overshoot are still excluded server-side (ajustarCantidad -> 0).
    // We mirror that: no emptiness-based chip hiding (was dropping most chips in paso 3, where
    // the remaining is tiny). filterAvoided() already applied the allergy removal upstream.
    const categories = getCurrentCategories();
    const displayFoods = isSearching ? searchResults : categoryFoods;

    // Preparations available for the selected category
    const availablePreparations = PREPARATIONS.filter(p => availablePreps.includes(p.value));

    return (
        <Dialog open={open} onOpenChange={() => onClose()}>
            <DialogContent className="max-w-2xl h-[90vh] p-0 flex flex-col bg-white">
                <DialogHeader className="flex-shrink-0 px-4 py-3 border-b">
                    <DialogTitle className="text-lg font-bold text-black">
                        {mealInfo?.label || `Comida ${mealKey?.replace('C', '')}`}
                    </DialogTitle>
                    <DialogDescription className="sr-only">
                        Construye tu comida paso a paso
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 flex flex-col overflow-hidden">
                    {/* Macros summary */}
                    <div className="flex-shrink-0 p-4 bg-gray-50 border-b">
                        <div className="text-sm font-medium text-gray-600 mb-2">{getPasoLabel()}</div>
                        <div className="grid grid-cols-3 gap-2 text-center">
                            <div>
                                <div className="text-xs text-gray-500">Proteína</div>
                                <div className={`font-bold ${served.P > target.P ? 'text-red-500' : 'text-orange-500'}`}>
                                    {served.P.toFixed(1)}/{fmtHalf(target.P)}g
                                </div>
                                {(() => { const st = macroStatus(served.P, target.P); return st && <div className={`text-[10px] font-semibold ${st.cls}`}>{st.label}</div>; })()}
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Hidratos</div>
                                <div className={`font-bold ${served.H > target.H ? 'text-red-500' : 'text-blue-500'}`}>
                                    {served.H.toFixed(1)}/{fmtHalf(target.H)}g
                                </div>
                                {(() => { const st = macroStatus(served.H, target.H); return st && <div className={`text-[10px] font-semibold ${st.cls}`}>{st.label}</div>; })()}
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Grasas</div>
                                <div className={`font-bold ${served.G > target.G ? 'text-red-500' : 'text-yellow-500'}`}>
                                    {served.G.toFixed(1)}/{fmtHalf(target.G)}g
                                </div>
                                {!isPeriMode && (() => { const st = macroStatus(served.G, target.G); return st && <div className={`text-[10px] font-semibold ${st.cls}`}>{st.label}</div>; })()}
                            </div>
                        </div>
                    </div>

                    {/* Search bar */}
                    <div className="flex-shrink-0 p-3 border-b">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
                            <Input
                                placeholder="Buscar alimento..."
                                value={searchQuery}
                                onChange={(e) => handleSearch(e.target.value)}
                                className="pl-10 pr-10"
                            />
                            {searchQuery && (
                                <button
                                    onClick={() => { setSearchQuery(''); setIsSearching(false); setSearchResults([]); }}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                                >
                                    <X className="w-4 h-4" />
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Category + Preparation Rails — hidden for intra (Calma: chips hidden) */}
                    {!isCuadrada && !isIntraMode && <div className="flex-shrink-0 px-3 pt-3 pb-2 border-b bg-white space-y-2">
                        <CategoryRail
                            label="Categorías:"
                            categories={categories}
                            value={selectedCategories.map(c => c.id)}
                            onChange={handleCategoriesChange}
                            size="sm"
                        />
                        {selectedCategories.length > 0 && availablePreparations.length > 0 && (
                            <CategoryRail
                                label="Preparación:"
                                categories={availablePreparations}
                                value={selectedPreparations}
                                onChange={setSelectedPreparations}
                                size="sm"
                            />
                        )}
                    </div>}

                    {/* Food list */}
                    <ScrollArea className="flex-1">
                        <div className="p-3">
                            {!isSearching && selectedCategories.length === 0 ? (
                                <div className="text-center py-10 text-gray-400 text-sm">
                                    Selecciona una categoría arriba para ver los alimentos
                                </div>
                            ) : (
                                <>
                                    {loadingFoods ? (
                                        <div className="text-center py-8 text-gray-500">Cargando...</div>
                                    ) : displayFoods.length === 0 ? (
                                        <div className="text-center py-8 text-gray-500">
                                            {isSearching
                                                ? 'No se encontraron alimentos'
                                                : selectedCategories.some(c => c.id === '__frequent__')
                                                    ? 'Aún no tienes alimentos frecuentes — guarda algunas dietas primero'
                                                    : 'No hay alimentos en esta categoría'}
                                        </div>
                                    ) : (
                                        <div className="space-y-1">
                                            {displayFoods.map((food, idx) => {
                                                const isFav = favorites.has(String(food.id));
                                                return (
                                                    <div key={food.id || idx} className="flex items-center gap-1">
                                                        <button
                                                            onClick={(e) => { e.stopPropagation(); toggleFavorite(food.id); }}
                                                            className={`flex-shrink-0 p-1 rounded transition-colors ${isFav ? 'text-yellow-400' : 'text-gray-300 hover:text-yellow-300'}`}
                                                            data-testid={`fav-toggle-${food.id}`}
                                                        >
                                                            <Star className="w-4 h-4" fill={isFav ? 'currentColor' : 'none'} />
                                                        </button>
                                                        <button
                                                            onClick={() => handleSelectFood(food)}
                                                            className="flex-1 flex items-center gap-2 p-2 rounded-lg text-left transition-colors hover:bg-gray-100"
                                                            data-testid={`food-item-${food.id || idx}`}
                                                        >
                                                            <div className="flex-1 min-w-0">
                                                                <div className="text-sm text-black truncate">{food.nombre}</div>
                                                                <div className="text-xs text-gray-500">
                                                                    {food._cantidad_sugerida ? `${(food.por_unidad ?? food.unidades) && (food.peso_unidad || food.racion) > 0 ? `${Math.round(food._cantidad_sugerida / (food.peso_unidad || food.racion) * 2) / 2} ud (${food.peso_unidad || food.racion} g/ml)` : `${food._cantidad_sugerida}g`} → ` : ''}
                                                                    {(() => {
                                                                        const ms = food._macros_sugeridos;
                                                                        const qty = food._cantidad_sugerida || food.racion || 100;
                                                                        const fmt = v => { const r = Math.round(v * 10) / 10; return r % 1 === 0 ? String(r) : r.toFixed(1); };
                                                                        const p = ms?.P ?? (food.proteinas || 0) * qty / 100;
                                                                        const h = ms?.H ?? (food.hidratos || 0) * qty / 100;
                                                                        const g = ms?.G ?? (food.grasas || 0) * qty / 100;
                                                                        return [
                                                                            p > 0 ? `P=${fmt(p)}g` : null,
                                                                            h > 0 ? `H=${fmt(h)}g` : null,
                                                                            g > 0 ? `G=${fmt(g)}g` : null,
                                                                        ].filter(Boolean).join(' ') || 'No aporta macros';
                                                                    })()}
                                                                </div>
                                                            </div>
                                                            <Plus className="w-4 h-4 text-gray-400 flex-shrink-0" />
                                                        </button>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </ScrollArea>

                    {/* Added foods */}
                    {tempFoods.length > 0 && (
                        <div className="flex-shrink-0 border-t bg-gray-50 p-3 max-h-48 overflow-auto">
                            <div className="text-xs text-gray-500 mb-2">Alimentos añadidos ({tempFoods.length})</div>
                            <div className="space-y-1">
                                {tempFoods.map((food, idx) => (
                                    <div key={idx} className="flex items-center gap-2 bg-white rounded p-2 text-sm">
                                        <span className="flex-1 truncate text-black">{food.nombre}</span>
                                        <div className="flex items-center gap-1">
                                            <button
                                                onClick={() => handleFoodQuantityChange(idx, -1)}
                                                className="w-6 h-6 flex items-center justify-center bg-gray-200 rounded"
                                            >
                                                <Minus className="w-3 h-3" />
                                            </button>
                                            <span className="w-16 text-center text-xs">
                                                {(food.por_unidad ?? food.unidades) && (food.peso_unidad || food.racion) > 0
                                                    ? `${Math.round(((food.cantidad_g || food.cantidad || 0) / (food.peso_unidad || food.racion)) * 2) / 2} ud (${food.peso_unidad || food.racion} g/ml)`
                                                    : `${food.cantidad_g || food.cantidad || 0}g`
                                                }
                                            </span>
                                            <button
                                                onClick={() => handleFoodQuantityChange(idx, 1)}
                                                className="w-6 h-6 flex items-center justify-center bg-gray-200 rounded"
                                            >
                                                <Plus className="w-3 h-3" />
                                            </button>
                                            <button
                                                onClick={() => handleRemoveFood(idx)}
                                                className="w-6 h-6 flex items-center justify-center text-red-500"
                                            >
                                                <X className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="flex-shrink-0 bg-white border-t p-4">
                    {tempFoods.length > 0 ? (
                        <Button
                            onClick={handleSaveAndClose}
                            className={`w-full h-12 rounded-full font-bold ${
                                isCuadrada
                                    ? 'bg-green-500 hover:bg-green-600 text-white'
                                    : 'bg-black hover:bg-gray-900 text-white'
                            }`}
                            data-testid="save-build-meal"
                        >
                            {isCuadrada ? '🎉 GUARDAR COMIDA CUADRADA' : 'GUARDAR Y CERRAR'}
                        </Button>
                    ) : (
                        <Button
                            variant="outline"
                            onClick={onClose}
                            className="w-full h-12 rounded-full"
                        >
                            Cancelar
                        </Button>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default BuildMealModal;
