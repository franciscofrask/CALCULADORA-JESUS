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
    faEgg, faBacon, faDove, faCow, faPiggyBank, faDrumstickBite,
    faFish, faCheese, faJar, faJarWheat, faSeedling, faBowlRice,
    faBreadSlice, faPlateWheat, faBowlFood, faCarrot, faAppleWhole,
    faLeaf, faBottleWater, faBolt, faBlender, faPizzaSlice, faCookie,
    faUtensils, faPepperHot, faBottleDroplet, faOilCan,
    faCircleInfo, faDroplet, faCookieBite, faScaleBalanced,
    faSquareCheck, faWheatAwnCircleExclamation, faSnowflake, faRing,
    faThumbsUp, faClock, faFireBurner, faMedal,
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
    { id: 'otras_carnes',   value: 'otras_carnes',   label: 'Otras carnes',     emoji: '🍖', icon: faDrumstickBite, prefixes: ['2.5', '2.6', '2.7', '40', '45'] },
    { id: 'pescados',       value: 'pescados',       label: 'Pescados',         emoji: '🐟', icon: faFish,          prefixes: ['3'] },
    { id: 'lacteos',        value: 'lacteos',        label: 'Lácteos',          emoji: '🧀', icon: faCheese,        prefixes: ['5'] },
    { id: 'proteina_polvo', value: 'proteina_polvo', label: 'Proteína',         emoji: '🥤', icon: faJar,           prefixes: ['4'] },
    { id: 'legumbres',      value: 'legumbres',      label: 'Legumbres',        emoji: '🫘', icon: faSeedling,      prefixes: ['10'] },
    { id: 'vegetal',        value: 'vegetal',        label: 'Vegetal',          emoji: '🌱', icon: faJarWheat,      prefixes: ['28', '6'] },
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
    { id: 'dulces',      value: 'dulces',      label: 'Dulces',       emoji: '🍫', icon: faCookie,        prefixes: ['31', '34', '35', '36', '37', '43', '44', '47'] },
    { id: 'salsas',      value: 'salsas',      label: 'Salsas',       emoji: '🥫', icon: faPepperHot,     prefixes: ['16'] },
    { id: 'grasas',      value: 'grasas',      label: 'Grasas',       emoji: '🫒', icon: faBottleDroplet, prefixes: ['17', '42'] },
    { id: 'sopas',       value: 'sopas',       label: 'Sopas',        emoji: '🍲', icon: faUtensils,      prefixes: ['48'] },
];

// Step 3 - fat sources
const FAT_CATEGORIES = [
    { id: 'grasas_buenas', value: 'grasas_buenas', label: 'Grasas de buena calidad', icon: faBottleDroplet, prefixes: ['42'] },
    { id: 'grasas_todo',   value: 'grasas_todo',   label: 'Grasas',                  icon: faOilCan,        prefixes: ['17'] },
    { id: 'lacteos',       value: 'lacteos',       label: 'Lácteos',                 icon: faCheese,        prefixes: ['5'] },
    { id: 'huevos',        value: 'huevos',        label: 'Huevos',                  icon: faEgg,           prefixes: ['1'] },
];

// INTRA categories
const INTRA_CATEGORIES = [
    { id: 'aminoacidos', value: 'aminoacidos', label: 'Aminoácidos', emoji: '⚡', icon: faJar,         prefixes: ['41'] },
    { id: 'isotonicas',  value: 'isotonicas',  label: 'Isotónicas',  emoji: '💧', icon: faBottleWater, prefixes: ['18.1'] },
];

// POST Step 1 - protein powders
const POST_PROTEIN_CATEGORIES = [
    { id: 'whey',    value: 'whey',    label: 'Whey',    emoji: '💪', icon: faJar,        prefixes: ['4.1'] },
    { id: 'caseina', value: 'caseina', label: 'Caseína', emoji: '🥛', icon: faJar,        prefixes: ['4.2'] },
    { id: 'vegetal', value: 'vegetal', label: 'Vegetal', emoji: '🌱', icon: faJarWheat,   prefixes: ['4.3'] },
    { id: 'batido',  value: 'batido',  label: 'Batido',  emoji: '🥤', icon: faBlender,    prefixes: ['5.4'] },
];

// POST Step 2 - fast carbs
const POST_CARB_CATEGORIES = [
    { id: 'fruta',       value: 'fruta',       label: 'Fruta',    emoji: '🍎', icon: faAppleWhole, prefixes: ['11'] },
    { id: 'crema_arroz', value: 'crema_arroz', label: 'C. Arroz', emoji: '🍚', icon: faBowlRice,   prefixes: ['21.3'] },
    { id: 'cereales',    value: 'cereales',    label: 'Cereales', emoji: '🌾', icon: faPlateWheat, prefixes: ['7.1'] },
    { id: 'bebida',      value: 'bebida',      label: 'Bebida',   emoji: '🥤', icon: faBottleWater, prefixes: ['24'] },
];

const PREPARATIONS = [
    { value: 'GEN', label: 'Genérico',                                 icon: faCircleInfo },
    { value: 'FRE', label: 'Frescos',                                  icon: faDroplet },
    { value: 'SNA', label: 'Snacks fáciles de transportar',            icon: faCookieBite },
    { value: 'UNI', label: 'Ya pesado',                                icon: faScaleBalanced },
    { value: 'YA',  label: 'Listo para comer',                         icon: faSquareCheck },
    { value: 'SGL', label: 'Etiquetado "Sin gluten"',                  icon: faWheatAwnCircleExclamation },
    { value: 'CGE', label: 'Congelados',                               icon: faSnowflake },
    { value: 'LAT', label: 'Conservas',                                icon: faRing },
    { value: 'PRE', label: 'Preparado',                                icon: faThumbsUp },
    { value: 'MIN', label: '1 minuto al micro y listo',                icon: faClock },
    { value: 'YCO', label: 'Ya cocinados',                             icon: faFireBurner },
    { value: 'PRO', label: 'Marca recomendada con descuento especial', icon: faMedal },
    { value: 'POL', label: 'En polvo',                                 icon: faJar },
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
    userPreferences = []
}) => {
    const [paso, setPaso] = useState(1);
    const [tempFoods, setTempFoods] = useState([]);

    const [selectedCategory, setSelectedCategory] = useState(null);
    const [categoryFoods, setCategoryFoods] = useState([]);
    const [loadingFoods, setLoadingFoods] = useState(false);

    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [isSearching, setIsSearching] = useState(false);

    const [selectedFood, setSelectedFood] = useState(null);
    const [adjustedQuantity, setAdjustedQuantity] = useState(0);
    const [adjustedMacros, setAdjustedMacros] = useState({ P: 0, H: 0, G: 0 });

    const [favorites, setFavorites] = useState(new Set());
    const [emptyCategoryIds, setEmptyCategoryIds] = useState(new Set());
    const [checkingCategories, setCheckingCategories] = useState(false);
    const lastCheckedRemaining = React.useRef(null);

    // Preparation filter
    const [selectedPreparation, setSelectedPreparation] = useState('');
    const [availablePreps, setAvailablePreps] = useState([]);

    const isIntraMode = mode === 'intra';
    const isPostMode = mode === 'post';
    const isPeriMode = isIntraMode || isPostMode;

    const target = mealKey ? getMealTarget(mealKey) : { P: 0, H: 0, G: 0 };
    const existingServed = (mealsData[mealKey]?.alimentos || []).reduce((acc, f) => ({
        P: acc.P + (f.macros_efectivos?.P || 0),
        H: acc.H + (f.macros_efectivos?.H || 0),
        G: acc.G + (f.macros_efectivos?.G || 0)
    }), { P: 0, H: 0, G: 0 });
    const served = tempFoods.reduce((acc, f) => ({
        P: acc.P + (f.macros_efectivos?.P || 0),
        H: acc.H + (f.macros_efectivos?.H || 0),
        G: acc.G + (f.macros_efectivos?.G || 0)
    }), { P: existingServed.P, H: existingServed.H, G: existingServed.G });
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

    const isCuadrada = Math.abs(target.P - served.P) <= 0 &&
                       Math.abs(target.H - served.H) <= 0 &&
                       (isPeriMode || Math.abs(target.G - served.G) <= 0);

    const getBlockReason = (macrosEf) => {
        if (isPeriMode) return null;
        const margin = 0;
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

    const getCurrentCategories = () => {
        let base = [];
        if (isIntraMode) {
            base = INTRA_CATEGORIES;
        } else if (isPostMode) {
            base = paso === 1 ? POST_PROTEIN_CATEGORIES : POST_CARB_CATEGORIES;
        } else if (paso === 1) {
            base = PROTEIN_CATEGORIES;
        } else if (paso === 2) {
            base = SIDE_CATEGORIES;
        } else if (paso === 3) {
            // Only fat-relevant and zero-macro categories at paso 3
            const FAT_IDS = new Set([
                'grasas_buenas', 'grasas_todo', 'lacteos', 'huevos',
                'aperitivos', 'chocolates', 'salsas', 'superalimentos',
            ]);
            let cats = [];
            if (userPreferences && userPreferences.length > 0) {
                cats = PREFERENCE_CATEGORIES
                    .filter(cat => userPreferences.includes(cat.id) && FAT_IDS.has(cat.id))
                    .map(cat => ({ ...cat, value: cat.id }));
            }
            // Always ensure fat base categories are present
            const ensurecat = (id, label, icon, prefixes) => {
                if (!cats.find(c => c.id === id))
                    cats.unshift({ id, value: id, label, icon, prefixes });
            };
            ensurecat('grasas_todo',   'Grasas',                  faOilCan,        ['17']);
            ensurecat('grasas_buenas', 'Grasas de buena calidad', faBottleDroplet, ['42']);
            base = cats;
        } else {
            base = SIDE_CATEGORIES;
        }
        return [FREQUENT_CATEGORY, ...base];
    };

    useEffect(() => {
        if (open && mealKey) {
            setTempFoods([]);
            setSelectedCategory(null);
            setCategoryFoods([]);
            setSearchQuery('');
            setSearchResults([]);
            setIsSearching(false);
            setSelectedFood(null);
            setSelectedPreparation('');
            setAvailablePreps([]);
            setEmptyCategoryIds(new Set());
            setCheckingCategories(false);

            // Determine correct starting paso based on already-saved foods in this meal
            if (!isIntraMode) {
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
                setSelectedCategory(null);
                setCategoryFoods([]);
                setSelectedPreparation('');
                setAvailablePreps([]);
            }
            return;
        }

        if (isIntraMode) return;

        const pPct = target.P > 0 ? (served.P / target.P) * 100 : 100;
        const hPct = target.H > 0 ? (served.H / target.H) * 100 : 100;

        if (pPct < 80) {
            if (paso !== 1) {
                setPaso(1);
                setSelectedCategory(null);
                setCategoryFoods([]);
                setSelectedPreparation('');
                setAvailablePreps([]);
            }
        } else if (pPct >= 80 && hPct < 80) {
            if (paso !== 2) {
                setPaso(2);
                setSelectedCategory(null);
                setCategoryFoods([]);
                setSelectedPreparation('');
                setAvailablePreps([]);
                toast.info('✅ Proteínas cubiertas. Elige el acompañamiento.');
            }
        } else if (pPct >= 80 && hPct >= 80) {
            if (paso !== 3) {
                setPaso(3);
                setSelectedCategory(null);
                setCategoryFoods([]);
                setSelectedPreparation('');
                setAvailablePreps([]);
                toast.info('✨ ¡Macros cubiertos! Últimos toques.');
            }
        }
    }, [served.P, served.H, target.P, target.H, tempFoods.length, paso, isIntraMode]);

    // Reload foods when macros change or preparation filter changes
    useEffect(() => {
        if (!open) return;
        let cancelled = false;
        if (selectedCategory) {
            const params = new URLSearchParams({ q: '', category: selectedCategory.prefixes[0], limit: '100' });
            if (target.P > 0) params.set('p_rest', remaining.P);
            if (target.H > 0) params.set('h_rest', remaining.H);
            if (target.G > 0) params.set('g_rest', remaining.G);
            if (selectedPreparation) params.set('tag', selectedPreparation);
            api(`/api/calculator/search?${params}`).then(result => {
                if (!cancelled) setCategoryFoods(result.alimentos || []);
            }).catch(() => {});
        } else if (isSearching && searchQuery.length >= 2) {
            const params = new URLSearchParams({ q: searchQuery, limit: '50', ...getMacrosParams() });
            api(`/api/calculator/search?${params}`).then(result => {
                if (!cancelled) setSearchResults(result.alimentos || []);
            }).catch(() => {});
        }
        return () => { cancelled = true; };
    }, [remaining.P, remaining.H, remaining.G, selectedPreparation]); // eslint-disable-line

    // Pre-check which categories have available foods
    useEffect(() => {
        const hasMacros = target.P > 0 || target.H > 0 || target.G > 0;
        if (!open || !hasMacros) {
            setEmptyCategoryIds(new Set());
            setCheckingCategories(false);
            return;
        }
        const cats = getCurrentCategories();
        // Only pass macros that are still needed (> 0) so the backend doesn't
        // exclude foods for "full" macros — categories should show if they have
        // any food that fits what's still missing
        const macroParams = {};
        if (target.P > 0 && remaining.P > 0) macroParams.p_rest = remaining.P;
        if (target.H > 0 && remaining.H > 0) macroParams.h_rest = remaining.H;
        if (target.G > 0 && remaining.G > 0) macroParams.g_rest = remaining.G;
        let cancelled = false;
        setCheckingCategories(true);
        lastCheckedRemaining.current = null; // invalidate until check completes
        // Exclude virtual categories (no backend prefix to check)
        const checkableCats = cats.filter(cat => cat.prefixes?.length > 0);
        const isGrasasPaso = paso === 3 && remaining.G > 0;
        Promise.all(checkableCats.map(async cat => {
            try {
                const limit = isGrasasPaso ? '10' : '1';
                const params = new URLSearchParams({ q: '', category: cat.prefixes[0], limit, ...macroParams });
                const result = await api(`/api/calculator/search?${params}`);
                const foods = result.alimentos || [];
                if (!isGrasasPaso) return { id: cat.id, empty: foods.length === 0 };
                // At paso 3: category useful only if it has foods with fat OR truly zero-macro foods
                const hasUseful = foods.some(f => {
                    const ms = f._macros_sugeridos || {};
                    const g = ms.G ?? 0;
                    const p = ms.P ?? 0;
                    const h = ms.H ?? 0;
                    return g > 0 || (p === 0 && h === 0 && g === 0);
                });
                return { id: cat.id, empty: !hasUseful };
            } catch {
                return { id: cat.id, empty: false };
            }
        })).then(results => {
            if (!cancelled) {
                setEmptyCategoryIds(new Set(results.filter(r => r.empty).map(r => r.id)));
                setCheckingCategories(false);
                lastCheckedRemaining.current = { P: remaining.P, H: remaining.H, G: remaining.G };
            }
        });
        return () => { cancelled = true; };
    }, [open, paso, remaining.P, remaining.H, remaining.G]); // eslint-disable-line

    const getMacrosParams = () => {
        const params = {};
        if (target.P > 0 && remaining.P > 0) params.p_rest = remaining.P;
        if (target.H > 0 && remaining.H > 0) params.h_rest = remaining.H;
        if (target.G > 0 && remaining.G > 0) params.g_rest = remaining.G;
        return params;
    };


    const handleCategoryClick = async (category) => {
        setSelectedCategory(category);
        setSelectedPreparation('');
        setLoadingFoods(true);
        setCategoryFoods([]);
        setAvailablePreps([]);

        try {
            if (category.id === '__frequent__') {
                const result = await api('/api/calculator/frequent-foods?limit=20');
                setCategoryFoods(result.alimentos || []);
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
        setSelectedPreparation('');
        setAvailablePreps([]);
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
            if (delta > 0) {
                const margin = 0;
                if ((ef.P > 0 && served.P + ef.P > target.P + margin) ||
                    (ef.H > 0 && served.H + ef.H > target.H + margin) ||
                    (ef.G > 0 && served.G + ef.G > target.G + margin)) {
                    toast.error('No puedes aumentar más — superaría los macros objetivo.');
                    return;
                }
            }
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
        if (delta > 0) {
            const food = tempFoods[index];
            const step = (food.por_unidad ?? food.unidades) ? (food.peso_unidad || food.racion || 100) : 1;
            const currentQty = food.cantidad_g || food.cantidad || 0;
            const newQty = Math.max(step, currentQty + step);
            const factor = newQty / 100;
            const newMacros = {
                P: Math.round((food.proteinas || 0) * factor * 10) / 10,
                H: Math.round((food.hidratos || 0) * factor * 10) / 10,
                G: Math.round((food.grasas || 0) * factor * 10) / 10
            };
            const otherServed = tempFoods.filter((_, i) => i !== index).reduce((acc, f) => ({
                P: acc.P + (f.macros_efectivos?.P || 0),
                H: acc.H + (f.macros_efectivos?.H || 0),
                G: acc.G + (f.macros_efectivos?.G || 0)
            }), { P: existingServed.P, H: existingServed.H, G: existingServed.G });
            const margin = 0;
            if ((newMacros.P > 0 && otherServed.P + newMacros.P > target.P + margin) ||
                (newMacros.H > 0 && otherServed.H + newMacros.H > target.H + margin) ||
                (newMacros.G > 0 && otherServed.G + newMacros.G > target.G + margin)) {
                toast.error('No puedes aumentar más — superaría los macros objetivo.');
                return;
            }
        }
        setTempFoods(prev => prev.map((f, i) => {
            if (i !== index) return f;
            const step = (f.por_unidad ?? f.unidades) ? (f.peso_unidad || f.racion || 100) : 1;
            const currentQty = f.cantidad_g || f.cantidad || 0;
            const newQty = Math.max(step, currentQty + (delta * step));
            const factor = newQty / 100;
            return {
                ...f,
                cantidad_g: newQty,
                macros_efectivos: {
                    P: Math.round((f.proteinas || 0) * factor * 10) / 10,
                    H: Math.round((f.hidratos || 0) * factor * 10) / 10,
                    G: Math.round((f.grasas || 0) * factor * 10) / 10
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
        if (isPostMode) {
            return paso === 1 ? 'Paso 1: Proteína' : 'Paso 2: Carbohidratos';
        }
        if (paso === 1) return 'Paso 1: Proteína';
        if (paso === 2) return 'Paso 2: Acompañamiento';
        return 'Paso 3: Últimos toques';
    };

    const allCategories = getCurrentCategories();
    const hasMacrosContext = remaining.P > 0 || remaining.H > 0 || remaining.G > 0;
    const lcr = lastCheckedRemaining.current;
    const isStaleCheck = !lcr || lcr.P !== remaining.P || lcr.H !== remaining.H || lcr.G !== remaining.G;
    const categories = hasMacrosContext
        ? allCategories.filter(cat => !emptyCategoryIds.has(cat.id))
        : allCategories;
    const displayFoods = isSearching ? searchResults : categoryFoods;

    // Preparations available for the selected category
    const availablePreparations = PREPARATIONS.filter(p => availablePreps.includes(p.value));

    return (
        <Dialog open={open} onOpenChange={() => onClose()}>
            <DialogContent className="max-w-md h-[90vh] p-0 flex flex-col bg-white">
                <DialogHeader className="flex-shrink-0 p-4 border-b">
                    <DialogTitle className="text-xl font-bold text-black">
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
                                    {served.P.toFixed(1)}/{target.P}g
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Hidratos</div>
                                <div className={`font-bold ${served.H > target.H ? 'text-red-500' : 'text-blue-500'}`}>
                                    {served.H.toFixed(1)}/{target.H}g
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Grasas</div>
                                <div className={`font-bold ${served.G > target.G ? 'text-red-500' : 'text-yellow-500'}`}>
                                    {served.G.toFixed(1)}/{target.G}g
                                </div>
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

                    {/* Category + Preparation Rails */}
                    {!isCuadrada && <div className="flex-shrink-0 px-3 pt-3 pb-2 border-b bg-white space-y-2">
                        {(checkingCategories || isStaleCheck) ? (
                            <div className="flex items-center gap-2 h-8">
                                <span className="text-xs font-bold text-gray-500">Categorías:</span>
                                <div className="flex gap-1.5">
                                    {[...Array(5)].map((_, i) => (
                                        <div key={i} className="w-8 h-8 rounded-full bg-gray-100 animate-pulse" />
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <CategoryRail
                                label="Categorías:"
                                categories={categories}
                                value={selectedCategory?.id || ''}
                                onChange={(val) => {
                                    if (!val) {
                                        handleBackToCategories();
                                    } else {
                                        const cat = categories.find(c => c.id === val);
                                        if (cat) handleCategoryClick(cat);
                                    }
                                }}
                                size="sm"
                            />
                        )}
                        {selectedCategory && availablePreparations.length > 0 && (
                            <CategoryRail
                                label="Preparación:"
                                categories={availablePreparations}
                                value={selectedPreparation}
                                onChange={setSelectedPreparation}
                                size="sm"
                            />
                        )}
                    </div>}

                    {/* Food list */}
                    <ScrollArea className="flex-1">
                        <div className="p-3">
                            {!isSearching && !selectedCategory ? (
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
                                                : selectedCategory?.id === '__frequent__'
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
                                                            <span className="text-lg">{getEmoji(food.categorias)}</span>
                                                            <div className="flex-1 min-w-0">
                                                                <div className="text-sm text-black truncate">{food.nombre}</div>
                                                                <div className="text-xs text-gray-500">
                                                                    {food._cantidad_sugerida ? `${(food.por_unidad ?? food.unidades) && (food.peso_unidad || food.racion) > 0 ? `${Math.round(food._cantidad_sugerida / (food.peso_unidad || food.racion) * 2) / 2} ud` : `${food._cantidad_sugerida}g`} → ` : ''}
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
                                                                        ].filter(Boolean).join(' ');
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
                                        <span>{getEmoji(food.categorias)}</span>
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
                                                    ? `${Math.round(((food.cantidad_g || food.cantidad || 0) / (food.peso_unidad || food.racion)) * 2) / 2} ud`
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
