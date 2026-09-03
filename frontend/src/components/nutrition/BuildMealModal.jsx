/**
 * BuildMealModal - Modal para construir comidas paso a paso
 * Extraído de NutritionPage.jsx para mejor mantenibilidad
 */
import React, { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { toast } from 'sonner';
import { Search, X, Plus, Minus, Star, ChevronUp } from 'lucide-react';
import { seExcede } from '../../lib/exceso';
import { SUELO_DE_LA_COMIDA } from '../../lib/estadoDelMacro';
import { num1, numMedio } from '../../lib/numeros';
import { leerCantidad, avisoRazonable, TOPE_GRAMOS, AVISO_TOPE, AVISO_NEGATIVO } from '../../lib/cantidades';
import { FOOD_FAVORITES_UI } from './SearchFoodModal';
import SinResultados from './SinResultados';
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
    faTrowelBricks, faCandyCane, faIceCream, faSmog, faUtensils, faMartiniGlassCitrus,
} from '@fortawesome/free-solid-svg-icons';

// Calma config T.macros.margenValido: peri (intra/post) meals have NO grasas objetivo, but
// macrosRestantes adds this fat slack so a little incidental fat is allowed/sized for. Fat
// budget = (target.G - served.G) + MARGEN_VALIDO, used by the engine to size AND order. Must
// match backend calma_suggest.MARGEN_VALIDO. Verified vs the Calma bundle 2026-06-14.
const MARGEN_VALIDO = 4;

const FREQUENT_CATEGORY = {
    id: '__frequent__',
    value: '__frequent__',
    label: 'Alimentos frecuentes',
    short: 'Frecuentes',
    icon: faStopwatch20,
};

// Nombre corto que se ve dentro de la pill. Los nombres de Calma son frases enteras
// ("Cacao en polvo y azúcares de todo tipo, chucherías y miel") y con trece categorías
// en 390 px no cabe ninguna: el largo se queda en el tooltip y en el aria-label.
// Abreviaturas coherentes con los chips del buscador de alimentos ("Prot. polvo",
// "Beb. vegetales"). Clave = id de la categoría, compartido entre pasos.
const NOMBRE_CORTO = {
    __frequent__: 'Frecuentes',
    // Proteínas
    huevos: 'Huevos',
    embutidos: 'Embutidos',
    aves: 'Aves',
    vacuno: 'Vacuno',
    cerdo: 'Cerdo',
    otras_carnes: 'Otras carnes',
    carnes_blancas: 'Carnes blancas',
    carnes_rojas: 'Carnes rojas',
    casqueria: 'Casquería',
    pescados: 'Pescados',
    lacteos: 'Lácteos',
    proteina: 'Prot. polvo',
    proteina_polvo: 'Prot. polvo',
    proteina_vegetal: 'Prot. vegetal',
    legumbres: 'Legumbres',
    // Hidratos y acompañamientos
    arroces: 'Arroces',
    panes: 'Panes',
    pan: 'Panes',
    cereales: 'Cereales',
    pasta: 'Pasta',
    tuberculos: 'Tubérculos',
    fruta: 'Fruta',
    verduras: 'Verduras',
    cremas_arroz: 'Cremas y tortas',
    sustitutivos: 'Sustitutivos',
    sopas: 'Sopas y caldos',
    cocina_esp: 'Cocina española',
    pizza: 'Pizza y lasaña',
    comida_rapida: 'Comida rápida',
    aperitivos: 'Aperitivos',
    // Bebidas
    beb_vegetales: 'Beb. vegetales',
    bebidas: 'Refrescos y café',
    isotonicas: 'Isotónicas',
    aminoacidos: 'Aminoácidos',
    // Dulces
    cremas: 'Bollería',
    bolleria: 'Bollería',
    chocolates: 'Chocolates',
    barritas: 'Barritas',
    helados: 'Helados',
    postres: 'Postres',
    cacao: 'Cacao y azúcar',
    azucar: 'Cacao y azúcar',
    // Grasas y otros
    grasas_buenas: 'Grasas buenas',
    grasas_todo: 'Otras grasas',
    grasas: 'Otras grasas',
    salsas: 'Salsas',
    superalimentos: 'Superalimentos',
};

const conNombreCorto = (cats) => cats.map(c => ({
    ...c,
    short: c.short || NOMBRE_CORTO[c.id] || c.label,
}));
import CategoryRail from './CategoryRail';
import { PREFERENCE_CATEGORIES } from './PreferencesSetup';

// Categories - Step 1 (Proteínas) - EXACT Calma T.categorias.categoriasProteinas order:
// ["1","2.1","2.2","2.3","2.4","45","3","5","30","28","10"] (single-code chips).
const PROTEIN_CATEGORIES = [
    { id: 'huevos',           value: 'huevos',           label: 'Huevos y derivados',                    emoji: '🥚', icon: faEgg,           prefixes: ['1'] },
    { id: 'embutidos',        value: 'embutidos',        label: 'Embutidos',                             emoji: '🥓', icon: faBacon,         prefixes: ['2.1'] },
    { id: 'aves',             value: 'aves',             label: 'Aves',                                  emoji: '🍗', icon: faDove,          prefixes: ['2.2'] },
    { id: 'vacuno',           value: 'vacuno',           label: 'Vacuno o buey',                         emoji: '🥩', icon: faCow,           prefixes: ['2.3'] },
    { id: 'cerdo',            value: 'cerdo',            label: 'Cerdo',                                 emoji: '🐷', icon: faPiggyBank,     prefixes: ['2.4'] },
    { id: 'otras_carnes',     value: 'otras_carnes',     label: 'Otras carnes',                          emoji: '🍖', icon: faDrumstickBite, prefixes: ['45'] },
    { id: 'pescados',         value: 'pescados',         label: 'Pescados y mariscos',                   emoji: '🐟', icon: faFish,          prefixes: ['3'] },
    { id: 'lacteos',          value: 'lacteos',          label: 'Lácteos y derivados',                   emoji: '🧀', icon: faCheese,        prefixes: ['5'] },
    { id: 'proteina_polvo',   value: 'proteina_polvo',   label: 'Proteína en polvo y barritas proteicas', emoji: '🥤', icon: faJar,          prefixes: ['30'] },
    { id: 'proteina_vegetal', value: 'proteina_vegetal', label: 'Proteína vegetal',                      emoji: '🌱', icon: faJarWheat,      prefixes: ['28'] },
    { id: 'legumbres',        value: 'legumbres',        label: 'Legumbres',                             emoji: '🫘', icon: faSeedling,      prefixes: ['10'] },
];

// Categories - Step 2 (Acompañamientos) - EXACT Calma T.categorias.categoriasHidratos order:
// ["21","8","7","22","9","11","13","10","5","24","19","27","32","43","44","37","38","39","16","17"].
const SIDE_CATEGORIES = [
    { id: 'arroces',       value: 'arroces',       label: 'Arroces y derivados',                                      emoji: '🍚', icon: faBowlRice,          prefixes: ['21'] },
    { id: 'panes',         value: 'panes',         label: 'Panes y tortillas de trigo',                               emoji: '🍞', icon: faBreadSlice,        prefixes: ['8'] },
    { id: 'cereales',      value: 'cereales',      label: 'Cereales (excepto arroz)',                                 emoji: '🌾', icon: faPlateWheat,        prefixes: ['7'] },
    { id: 'pasta',         value: 'pasta',         label: 'Pasta, quinoa y derivados',                                emoji: '🍝', icon: faBowlFood,          prefixes: ['22'] },
    { id: 'tuberculos',    value: 'tuberculos',    label: 'Tubérculos y derivados',                                   emoji: '🥔', icon: faCarrot,            prefixes: ['9'] },
    { id: 'fruta',         value: 'fruta',         label: 'Fruta, zumo, potitos y mermeladas',                        emoji: '🍎', icon: faAppleWhole,        prefixes: ['11'] },
    { id: 'verduras',      value: 'verduras',      label: 'Verduras y hortalizas',                                    emoji: '🥬', icon: faLeaf,              prefixes: ['13'] },
    { id: 'legumbres',     value: 'legumbres',     label: 'Legumbres',                                                emoji: '🫘', icon: faSeedling,          prefixes: ['10'] },
    { id: 'lacteos',       value: 'lacteos',       label: 'Lácteos y derivados',                                      emoji: '🧀', icon: faCheese,            prefixes: ['5'] },
    { id: 'beb_vegetales', value: 'beb_vegetales', label: 'Bebidas vegetales',                                        emoji: '🥛', icon: faBottleWater,      prefixes: ['24'] },
    { id: 'bebidas',       value: 'bebidas',       label: 'Bebidas energéticas, refrescos y cafés',                   emoji: '🥤', icon: faBolt,              prefixes: ['19'] },
    { id: 'sustitutivos',  value: 'sustitutivos',  label: 'Sustitutivos de comidas',                                  emoji: '🥤', icon: faBlender,           prefixes: ['27'] },
    { id: 'pizza',         value: 'pizza',         label: 'Pizza, lasaña, empanadas y empanadillas',                  emoji: '🍕', icon: faPizzaSlice,        prefixes: ['32'] },
    { id: 'cremas',        value: 'cremas',        label: 'Bollería, galletas, barritas energéticas, chocolate y chocolatinas', emoji: '🍫', icon: faCookie, prefixes: ['43'] },
    { id: 'helados',       value: 'helados',       label: 'Helados y postres',                                        emoji: '🍨', icon: faIceCream,          prefixes: ['44'] },
    { id: 'cacao',         value: 'cacao',         label: 'Cacao en polvo y azúcares de todo tipo, chucherías y miel', emoji: '🍯', icon: faCandyCane,        prefixes: ['37'] },
    { id: 'aperitivos',    value: 'aperitivos',    label: 'Aperitivos',                                               emoji: '🥨', icon: faMartiniGlassCitrus, prefixes: ['38'] },
    { id: 'cocina_esp',    value: 'cocina_esp',    label: 'Cocina tradicional española',                              emoji: '🥘', icon: faUtensils,         prefixes: ['39'] },
    { id: 'salsas',        value: 'salsas',        label: 'Salsas, siropes y konjac',                                 emoji: '🥫', icon: faPepperHot,         prefixes: ['16'] },
    { id: 'grasas',        value: 'grasas',        label: 'Alimentos ricos en grasas de todo tipo',                   emoji: '🫒', icon: faBottleDroplet,     prefixes: ['17'] },
];

// Step 3 - fat sources
const FAT_CATEGORIES = [
    { id: 'grasas_buenas', value: 'grasas_buenas', label: 'Grasas de buena calidad', icon: faBottleDroplet, prefixes: ['42'] },
    { id: 'grasas_todo',   value: 'grasas_todo',   label: 'Grasas',                  icon: faOilCan,        prefixes: ['17'] },
    { id: 'lacteos',       value: 'lacteos',       label: 'Lácteos',                 icon: faCheese,        prefixes: ['5'] },
    { id: 'huevos',        value: 'huevos',        label: 'Huevos',                  icon: faEgg,           prefixes: ['1'] },
];

// INTRA categories - Calma categoriasIntraentreno: ["18","41"] (chips hidden, pre-active)
const INTRA_CATEGORIES = [
    { id: 'isotonicas',  value: 'isotonicas',  label: 'Intraentrenamiento',       emoji: '💧', icon: faBottleWater, prefixes: ['18'] },
    { id: 'aminoacidos', value: 'aminoacidos', label: 'Aminoacidos para entrenar', emoji: '⚡', icon: faTrowelBricks, prefixes: ['41'] },
];

// POST categories - single list, Calma categoriasPostentreno order:
// ["4","5","46","7","8","11","27","24","19","37","36","16"]
const POST_CATEGORIES = [
    { id: 'proteina',      value: 'proteina',      label: 'Proteínas en polvo',                                        emoji: '💪', icon: faJar,        prefixes: ['4'] },
    { id: 'lacteos',       value: 'lacteos',       label: 'Lácteos y derivados',                                       emoji: '🧀', icon: faCheese,     prefixes: ['5'] },
    { id: 'cremas_arroz',  value: 'cremas_arroz',  label: 'Cremas y tortas de arroz',                                  emoji: '🍚', icon: faBowlRice,   prefixes: ['46'] },
    { id: 'cereales',      value: 'cereales',      label: 'Cereales (excepto arroz)',                                  emoji: '🌾', icon: faPlateWheat, prefixes: ['7'] },
    { id: 'pan',           value: 'pan',           label: 'Panes y tortillas de trigo',                                emoji: '🍞', icon: faBreadSlice, prefixes: ['8'] },
    { id: 'fruta',         value: 'fruta',         label: 'Fruta, zumo, potitos y mermeladas',                         emoji: '🍎', icon: faAppleWhole, prefixes: ['11'] },
    { id: 'sustitutivos',  value: 'sustitutivos',  label: 'Sustitutivos de comidas',                                   emoji: '🥤', icon: faBlender,    prefixes: ['27'] },
    { id: 'beb_vegetales', value: 'beb_vegetales', label: 'Bebidas vegetales',                                         emoji: '🥛', icon: faBottleWater, prefixes: ['24'] },
    { id: 'bebidas',       value: 'bebidas',       label: 'Bebidas energéticas, refrescos y cafés',                    emoji: '⚡', icon: faBolt,       prefixes: ['19'] },
    { id: 'azucar',        value: 'azucar',        label: 'Cacao en polvo y azúcares de todo tipo, chucherías y miel', emoji: '🍯', icon: faCandyCane,  prefixes: ['37'] },
    { id: 'postres',       value: 'postres',       label: 'Postres',                                                   emoji: '🍮', icon: faIceCream,   prefixes: ['36'] },
    { id: 'salsas',        value: 'salsas',        label: 'Salsas, siropes y konjac',                                  emoji: '🥫', icon: faPepperHot,  prefixes: ['16'] },
];

// Ordered to match Calma's `A.preparaciones`:
// [GEN, PRO, FRE, CGE, AHU, LAT, POL, PRE, HAM, SNA, MIN, YCO, UNI, YA, SGL]
const PREPARATIONS = [
    { value: 'GEN', label: 'Genérico',                                 short: 'Genérico',     icon: faCircleInfo },
    { value: 'PRO', label: 'Marca recomendada con descuento especial', short: 'Recomendada',  icon: faMedal },
    { value: 'FRE', label: 'Frescos',                                  short: 'Frescos',      icon: faDroplet },
    { value: 'CGE', label: 'Congelados',                               short: 'Congelados',   icon: faSnowflake },
    { value: 'AHU', label: 'Ahumados',                                 short: 'Ahumados',     icon: faSmog },
    { value: 'LAT', label: 'Conservas',                                short: 'Conservas',    icon: faRing },
    { value: 'POL', label: 'En Polvo',                                 short: 'En polvo',     icon: faJar },
    { value: 'PRE', label: 'Preparado',                                short: 'Preparado',    icon: faThumbsUp },
    { value: 'HAM', label: 'Carne picada y hamburguesas',              short: 'Carne picada', icon: faBurger },
    { value: 'SNA', label: 'Snacks fáciles de transportar',            short: 'Para llevar',  icon: faCookieBite },
    { value: 'MIN', label: '1 Minuto al micro y listo',                short: 'Al micro',     icon: faClock },
    { value: 'YCO', label: 'Ya cocinados',                             short: 'Ya cocinado',  icon: faFireBurner },
    { value: 'UNI', label: 'Ya pesado',                                short: 'Ya pesado',    icon: faScaleBalanced },
    { value: 'YA',  label: 'Listo para comer',                         short: 'Listo',        icon: faSquareCheck },
    { value: 'SGL', label: 'Sin gluten',                               short: 'Sin gluten',   icon: faWheatAwnCircleExclamation },
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
    setMealMode,
    getFoodEmoji,
    userPreferences = [],
    avoidedCategories = [],
    // Lo que el día lleva ya de cada familia calibrada. Sin esto esta ventana calculaba con
    // el motor de antes de la calibración y enseñaba números que cambiaban al guardar
    // (punto 135 del 26-08): ver `getDiaParams`.
    acumFamilias = null,
}) => {
    const [paso, setPaso] = useState(1);
    const [tempFoods, setTempFoods] = useState([]);
    const [addedOpen, setAddedOpen] = useState(false);  // collapsible "añadidos" bar (closed → list keeps space)
    const [qtyDraft, setQtyDraft] = useState({});  // buffer del input de cantidad por índice (permite teclear libre)

    const [selectedCategories, setSelectedCategories] = useState([]);
    const [categoryFoods, setCategoryFoods] = useState([]);
    const [loadingFoods, setLoadingFoods] = useState(false);

    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [isSearching, setIsSearching] = useState(false);
    // EL TURNO DE LA BÚSQUEDA. Cada tecla lanzaba su petición y ganaba la que llegase
    // ÚLTIMA, no la última escrita: al teclear «pechuga» la respuesta de «pe» -- que trae
    // medio catálogo y tarda más -- pisaba a la de «pechuga» y en pantalla quedaban Pepsi
    // Max y Pepitas. Ese era el fallo 3 de Jesús. Cada búsqueda coge número y solo se pinta
    // la que sigue siendo la actual.
    const turnoBusqueda = useRef(0);

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
    // Manual mode (per meal): no auto-quantity, no 80% progression, no suggestions, free
    // amount, foods alphabetical, no min-quantity block. Peri meals never use it.
    const isManual = !isPeriMode && !!mealKey && mealsData[mealKey]?.modo === 'manual';

    const target = mealKey ? getMealTarget(mealKey) : { P: 0, H: 0, G: 0 };
    // Calma's macroEnIngredientes sums UNROUNDED per-food contributions (raw post-regla
    // macros × quantity). The stored macros_efectivos are rounded to 1 decimal for display;
    // summing those loses ~0.05 g/food, enough to flip a floor() in the suggested quantity
    // (e.g. tikka H = 26.5×1.37 = 36.305 → remaining 10.495, not 10.5 → Tasty rice 13 g not
    // 14 g) and reorder the list. Rebuild the contribution from the raw fields, gated by
    // macros_efectivos so regla-25% zeroed macros stay zero; fall back to the rounded
    // efectivos when raw fields are absent (older saved diets).
    /**
     * LO QUE APORTA UN ALIMENTO DE LA VENTANA: LOS MACROS EFECTIVOS, Y NADA MÁS.
     *
     * Esto rehacía la cuenta desde los macros de la etiqueta (`f.proteinas * factor`) y sólo
     * usaba los efectivos como interruptor de encendido, para no perder decimales por el
     * redondeo. Con la calibración del día eso ya no vale: el crudo no sabe en qué tramo
     * está el día, así que reconstruirlo da otro número. Las almendras del punto 135 lo
     * enseñaban de las dos formas a la vez en la misma pantalla -- el resumen de abajo
     * decía «P 3» y la barra de arriba «40 g» sin servido --, porque el alimento llega del
     * servidor con la proteína ya puesta a cero por la regla de categoría y el crudo valía 0.
     *
     * Los efectivos vienen redondeados a la décima, que es exactamente lo que se escribe en
     * pantalla en todas partes. La precisión que se pierde no se ve; la contradicción sí.
     */
    const foodContrib = (f) => {
        const ef = f.macros_efectivos || {};
        return { P: ef.P || 0, H: ef.H || 0, G: ef.G || 0 };
    };
    const sumContrib = (list, acc) => list.reduce((a, f) => {
        const c = foodContrib(f);
        return { P: a.P + c.P, H: a.H + c.H, G: a.G + c.G };
    }, acc);
    // tempFoods se precarga con los alimentos ya guardados de la comida (ver efecto de apertura),
    // así que ya representa el TOTAL de la comida; no sumamos los existentes aparte (se duplicarían).
    const served = sumContrib(tempFoods, { P: 0, H: 0, G: 0 });
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
        if (open && FOOD_FAVORITES_UI) loadFavorites();
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
    const fmtHalf = numMedio;   // coma decimal, como todo lo que se ve en Nutrición

    // Calma "Macros para Comida X" per macro (margenValido = 4), r = target - served UNROUNDED:
    //   served > 0  -> num "served/target g" + status:
    //                  |r|<1 -> "cuadrado" | |r|<4 -> "cuadrado (+X,X)" |
    //                  r>=4 -> "faltan X.Xg" | r<=-4 -> "sobran X.Xg"
    //   served == 0 -> num "targetg" ONLY, NO status (e.g. "Hidratos: 30g"). The status appears
    //                  at the SAME moment Calma shows it: only once that macro has something served.
    const MARGEN_VALIDO = 4;
    const fmt1 = num1;
    // `key` (P/H/G) para el rojo: pasarse de proteína no es un fallo y no se pinta (Jesús,
    // 13-08). El «sobran X g» se sigue diciendo, en el color de siempre.
    const macroCell = (servedVal, tgtVal, key) => {
        if (!(servedVal > 0)) return { num: `${fmtHalf(tgtVal)} g`, status: null, over: false };
        const r = tgtVal - servedVal;
        let status, cls;
        // LOS COLORES, LEGIBLES EN CLARO. A 11 px sobre fondo blanco, `amber-500` da 2,15:1
        // y `red-500` 3,3:1: por debajo de lo que se lee sin forzar la vista (QA del 15-08).
        // En oscuro mandan los tonos claros, que ahí son los que contrastan.
        // LAS MISMAS PALABRAS QUE LA TARJETA. Y las palabras son las del 3-09 (Francisco,
        // revirtiendo la revisión del 2-09): «cuadrado» SOLO cuando está exacto (por debajo
        // de un gramo, `SUELO_DE_LA_COMIDA`); dentro del margen, «válido» con su desvío --
        // la letra del punto 78/11.1: «de 1 a 4, falte o sobre, es válido y sale en verde» --
        // y fuera, «faltan»/«sobran». Igual que `lib/estadoDelMacro`, para que el mismo
        // plato no se lea distinto según la ventana.
        //
        // El signo va del lado del cliente, no del cálculo: aquí `r` es lo que FALTA
        // (objetivo − servido), así que un `r` negativo es que se ha pasado y lleva el «+».
        if (Math.abs(r) < SUELO_DE_LA_COMIDA) { status = 'cuadrado'; cls = 'text-green-700 dark:text-green-400'; }
        // Inclusivo: «de 1 a 4» entra el 4 clavado (alineado el 3-09 con lib/estadoDelMacro).
        else if (Math.abs(r) <= MARGEN_VALIDO) { status = `válido (${r < 0 ? '+' : '−'}${fmt1(Math.abs(r))})`; cls = 'text-green-700 dark:text-green-400'; }
        // LO QUE FALTA VA EN BLANCO, no en rojo (2-09). Es la regla del punto 77 -- «sin color
        // mientras vas por debajo», porque ir corto no es un error, es que no has terminado --
        // y la lista del 196 lo deja por escrito: «faltan 11 de proteína, en blanco, que es un
        // número y va con su número». Este diálogo era el último sitio que lo pintaba de rojo,
        // y ademas se abre con la comida vacía: entrabas a montarla y te recibían tres avisos
        // rojos por no haber puesto nada todavía.
        else if (r > 0) { status = `faltan ${fmt1(r)} g`; cls = 'text-foreground'; }
        else {
            const enRojo = seExcede(key, servedVal, tgtVal, { esPeri: isPeriMode });
            status = `sobran ${fmt1(-r)} g`;
            cls = enRojo ? 'text-red-700 dark:text-red-400' : 'text-muted-foreground';
        }
        return { num: `${fmt1(servedVal)}/${fmtHalf(tgtVal)} g`, status, cls,
                 over: seExcede(key, servedVal, tgtVal, { esPeri: isPeriMode }) };
    };

    const isCuadrada = Math.abs(target.P - served.P) <= 0 &&
                       Math.abs(target.H - served.H) <= 0 &&
                       (isPeriMode || Math.abs(target.G - served.G) <= 0);

    // Calma: a meal that is already valida (within margenValido) has no remaining to fill, so
    // the engine returns no suggestions and you can't keep stuffing it. Block a food that would
    // overshoot the meal target by more than the 4 g margin.
    const getBlockReason = (macrosEf) => {
        if (isPeriMode) return null;
        const margin = 4;
        if (macrosEf.P > 0 && served.P + macrosEf.P > target.P + margin) {
            return 'No cabe - superaría la proteína objetivo de esta comida.';
        }
        if (macrosEf.H > 0 && served.H + macrosEf.H > target.H + margin) {
            return 'No cabe - superaría los hidratos objetivo de esta comida.';
        }
        if (macrosEf.G > 0 && served.G + macrosEf.G > target.G + margin) {
            return 'No cabe - superaría las grasas objetivo de esta comida.';
        }
        return null;
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
        if (isManual) {
            // Manual: no progression, so expose the WHOLE Calma category universe at once
            // (PREFERENCE_CATEGORIES = the 38 canonical category codes) for free browsing.
            // Order within a category is alphabetical.
            base = filterAvoided(PREFERENCE_CATEGORIES.map(cat => ({ ...cat, value: cat.id })));
            return conNombreCorto([FREQUENT_CATEGORY, ...base]);
        }
        if (isIntraMode) {
            base = INTRA_CATEGORIES;
        } else if (isPostMode) {
            // Calma: post is a single phase - all 12 categoriasPostentreno at once (no split).
            base = POST_CATEGORIES;
        } else if (paso === 1) {
            base = filterAvoided(PROTEIN_CATEGORIES);
        } else if (paso === 2) {
            base = filterAvoided(SIDE_CATEGORIES);
        } else if (paso === 3) {
            // Calma paso 3 (todos) = filtrosDePreferencias: the user's preferences shown in the
            // CANONICAL categoriasParaPreferencias order (the prefs form builds the Set by iterating
            // that fixed list, so [...preferencias] is code order, NOT click order). grasas_buenas
            // (42) is a "fija" -> always present. PREFERENCE_CATEGORIES already IS that canonical
            // order with grasas_buenas first, so just filter it (don't re-order by selection).
            const prefSet = new Set(userPreferences || []);
            base = filterAvoided(
                PREFERENCE_CATEGORIES
                    .filter(c => c.id === 'grasas_buenas' || prefSet.has(c.id))
                    .map(cat => ({ ...cat, value: cat.id }))
            );
        } else {
            base = SIDE_CATEGORIES;
        }
        return conNombreCorto([FREQUENT_CATEGORY, ...base]);
    };

    useEffect(() => {
        if (open && mealKey) {
            // Precargar los alimentos ya guardados de la comida, para que al reabrir el modal
            // se sigan viendo (y se puedan editar/quitar) en lugar de empezar vacío.
            const yaGuardados = (mealsData[mealKey]?.alimentos || []).map(f => ({ ...f }));
            setTempFoods(yaGuardados);
            // La barra de «añadidos» arranca CERRADA, aunque la comida ya tuviera alimentos.
            // Abierta se comía media ventana y solo dejaba ver el primer resultado del
            // buscador, así que el buscador parecía muerto (Jesús, 15-08, fallo 30). Cerrada
            // sigue diciendo cuántos hay y con qué macros; para verlos, se despliega.
            setAddedOpen(false);
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
                const pOk = !(t.P > 0) || (ex.P / t.P) > 0.8;   // Calma porcentajeSuficienteMacros, strict >
                const hOk = !(t.H > 0) || (ex.H / t.H) > 0.8;
                setPaso(!pOk ? 1 : (!hOk ? 2 : 3));
            } else {
                setPaso(1);
            }
        }
    }, [open, mealKey, mode]); // eslint-disable-line

    // Switching mode (manual<->auto) mid-modal resets the category selection so stale chips
    // don't linger. Skip the first run (ref starts equal) so intra's auto-selection survives mount.
    const prevManual = useRef(isManual);
    useEffect(() => {
        if (prevManual.current === isManual) return;
        prevManual.current = isManual;
        if (!open) return;
        setSelectedCategories([]);
        setCategoryFoods([]);
        setSelectedPreparations([]);
        setAvailablePreps([]);
    }, [isManual, open]);

    // Calma filtroParaAplicar is REACTIVE: the phase is recomputed from the current served macros
    // every change - NOT a one-way advance. So removing the food that supplied the carbs drops you
    // back from paso 3 to paso 2. haySuficientes = served/target > 0.8 (porcentajeSuficienteMacros,
    // STRICT >). target==0 -> that macro counts as sufficient (nothing to add there).
    useEffect(() => {
        if (!open) return;       // modal stays mounted while closed; don't react to day switches
        if (isPeriMode) return;  // peri (intra/post) is a single phase - no paso split
        if (isManual) return;    // manual: no 80% progression at all
        const pOk = !(target.P > 0) || (served.P / target.P) > 0.8;
        const hOk = !(target.H > 0) || (served.H / target.H) > 0.8;
        const newPaso = !pOk ? 1 : (!hOk ? 2 : 3);
        if (newPaso !== paso) {
            setPaso(newPaso);
            setSelectedCategories([]);
            setCategoryFoods([]);
            setSelectedPreparations([]);
            setAvailablePreps([]);
            if (newPaso > paso) {  // toast only when advancing
                if (newPaso === 2) toast.info('✅ Proteínas cubiertas. Elige el acompañamiento.');
                else if (newPaso === 3) toast.info('✨ ¡Macros cubiertos! Últimos toques.');
            }
        }
    }, [open, served.P, served.H, target.P, target.H, paso, isPeriMode, isManual]);

    // Calma: filtrosActivacionPorDefecto = false. In paso 3 (cuadrarMacros / "últimos
    // toques") the preference category chips are shown but start INACTIVE - the user
    // picks which to finish with. We previously auto-selected all of them, which was a
    // bug (every chip appeared selected and the whole catalog loaded). No pre-activation.

    // Reload foods when macros, categories or preparations change
    useEffect(() => {
        if (!open) return;
        let cancelled = false;
        const hasFrequent = selectedCategories.some(c => c.id === '__frequent__');
        if (hasFrequent) {
            setLoadingFoods(true);
            // Calma: frequent foods (top-20 by raw count) go through the SAME engine -
            // suggested quantity + macro rule + diferencia ordering, using the meal remaining.
            const params = new URLSearchParams({ frequent: 'true', limit: '20', ...getDiaParams() });
            const mp = getMacrosParams();
            Object.entries(mp).forEach(([k, v]) => params.set(k, v));
            api(`/api/calculator/search?${params}`).then(result => {
                if (!cancelled) { setCategoryFoods(result.alimentos || []); setAvailablePreps(result.available_preps || []); }
            }).catch(() => {}).finally(() => { if (!cancelled) setLoadingFoods(false); });
        } else if (selectedCategories.length > 0) {
            setLoadingFoods(true);
            const categoryParam = selectedCategories.flatMap(c => c.prefixes || []).filter(Boolean).join(',');
            const params = new URLSearchParams({ q: '', category: categoryParam, limit: '100', ...getDiaParams() });
            // Manual: send NO macro context, so the backend returns the plain category list
            // (no suggested quantity, no diferencia ordering). Frontend sorts it alphabetically.
            if (!isManual) {
                // Calma uses ONE unified remaining (full meal target minus added), all three macros,
                // every step. The "paso" only changes which CATEGORIES are shown, never the macro
                // constraints. Sending only P+G in paso 1 left H unconstrained -> Tortitas 4ud and an
                // order that ignored hidratos. Send all three, no tolerance.
                if (target.P > 0) params.set('p_rest', Math.max(0, remaining.P));
                if (target.H > 0) params.set('h_rest', Math.max(0, remaining.H));
                if (target.G > 0) params.set('g_rest', Math.max(0, remaining.G));
                // Calma prioridad fase (Dieta.js ordenarIngredientesPorMacro): once P AND H are >80%
                // of target (porcentajeSuficienteMacros) the sort switches to `cuadrarMacros` (good
                // fats) REGARDLESS of meal type; otherwise peri uses its own list. Peri meals always
                // add margenValido to the fat budget (g_rest), independent of the fase.
                const sufP = !(target.P > 0) || served.P / target.P > 0.8;
                const sufH = !(target.H > 0) || served.H / target.H > 0.8;
                if (isIntraMode || isPostMode) {
                    // peri = MEAL TYPE (post → cat-25 universe + grasas margin); sent always.
                    params.set('peri', isIntraMode ? 'intra' : 'post');
                    params.set('g_rest', target.G - served.G + MARGEN_VALIDO);
                }
                // cuadrar = prioridad FASE (good fats), once P&H >80% - independent of meal type.
                if (sufP && sufH || paso === 3) params.set('cuadrar', 'true');
            }
            if (selectedPreparations.length > 0) params.set('tag', selectedPreparations.join(','));
            api(`/api/calculator/search?${params}`).then(result => {
                if (!cancelled) {
                    setCategoryFoods(result.alimentos || []);
                    setAvailablePreps(result.available_preps || []);
                }
            }).catch(() => {}).finally(() => { if (!cancelled) setLoadingFoods(false); });
        }
        // AQUÍ SE RELANZABA LA BÚSQUEDA POR TEXTO cada vez que cambiaba lo que le queda a la
        // comida, con el hueco de macros dentro. Era la otra mitad del fallo 3: la lista de
        // resultados se reordenaba sola -- o se vaciaba -- sin que nadie hubiera tocado el
        // buscador. Lo que se ha escrito no depende de los macros, así que ya no se relanza.
        return () => { cancelled = true; };
    }, [remaining.P, remaining.H, remaining.G, selectedCategories, selectedPreparations, isManual]); // eslint-disable-line

    /**
     * LO QUE LLEVA EL DÍA DE CADA FAMILIA CALIBRADA, PARA QUE LOS NÚMEROS NO CAMBIEN AL
     * GUARDAR (punto 135 del 26-08).
     *
     * Jesús: «añades 100 g de almendras y la proteína no se mueve; al guardar, pasa a contar
     * los 23 g». Reproducido con 25 g: aquí ponía «P 0 · H 0 · G 13» y la comida guardada
     * decía «2,9 P». Esta ventana calculaba con el motor de Calma, que es el de antes de que
     * existiera la calibración progresiva; la comida, con la calibración.
     *
     * La cuenta tiene tres sumandos y hacen falta los tres, porque `tempFoods` arranca
     * PRECARGADO con lo que esta comida ya tenía guardado y el acumulado del día también lo
     * cuenta: sumarlos sin más lo contaba dos veces, y con 25 g de almendras guardadas el
     * tramo saltaba al lleno antes de tiempo. Se descuenta lo que la comida tenía y se suma
     * lo que tiene ahora, así valen igual añadir, quitar y cambiar la cantidad aquí dentro.
     *
     * El bloque de cada alimento lo dice el servidor, para no repetir aquí la clasificación
     * por categorías.
     */
    const getDiaParams = () => {
        const gramosDe = (lista, bloque) => (lista || [])
            .filter((f) => f.bloque === bloque)
            .reduce((s, f) => s + (Number(f.cantidad_g) || 0), 0);
        const guardados = mealsData[mealKey]?.alimentos || [];
        const delDia = (bloque, acum) => Math.max(0,
            (acum || 0) - gramosDe(guardados, bloque) + gramosDe(tempFoods, bloque));
        return {
            dia_cp: delDia('cereal_pan', acumFamilias?.cereal_pan?.gramos),
            dia_fs: delDia('fruto_seco', acumFamilias?.fruto_seco?.gramos),
        };
    };

    /**
     * LA VENTANA LE PREGUNTA AL MISMO MOTOR QUE LA COMIDA (punto 135, la parte de fondo).
     *
     * Aquí se calculaban los macros de tres maneras distintas -- el sugeridor al listar, la
     * regla de categoría al añadir y una regla de tres al cambiar la cantidad -- y ninguna
     * era la del día. Por eso los números cambiaban al guardar.
     *
     * En vez de repetir la calibración aquí, se le pide al servidor que calibre el día
     * ENTERO con esta comida tal y como está en la ventana. Es la misma llamada que ya usa
     * Nutrición, así que por definición da lo mismo que quedará guardado, y cierra de paso
     * los casos que el cálculo al añadir no puede ver: subir la cantidad hasta cruzar de
     * tramo, quitar un alimento y que los demás bajen, o que dos frutos secos se sumen.
     *
     * Con retardo, porque los botones de cantidad se pulsan seguidos. Y si el servidor
     * devuelve lo mismo que ya había, se conserva el array anterior: si se creara uno nuevo
     * cada vez, este mismo efecto se volvería a disparar y no pararía nunca.
     */
    useEffect(() => {
        if (!open || !mealKey || tempFoods.length === 0) return undefined;
        const t = setTimeout(async () => {
            try {
                const comidas = {};
                Object.entries(mealsData || {}).forEach(([k, v]) => {
                    comidas[k] = (v?.alimentos || []).map((f) => ({
                        alimento_id: f.alimento_id, cantidad_g: f.cantidad_g,
                    }));
                });
                comidas[mealKey] = tempFoods.map((f) => ({
                    alimento_id: f.alimento_id, cantidad_g: f.cantidad_g,
                }));
                const res = await api('/api/calculator/calibrar-dia', {
                    method: 'POST', body: JSON.stringify({ comidas }),
                });
                const fila = res?.comidas?.[mealKey] || [];
                setTempFoods((prev) => {
                    let cambio = false;
                    const next = prev.map((f, i) => {
                        const ef = fila[i]?.macros_efectivos;
                        if (!ef) return f;
                        const a = f.macros_efectivos || {};
                        const bloque = fila[i].bloque ?? null;
                        if (a.P === ef.P && a.H === ef.H && a.G === ef.G && (f.bloque ?? null) === bloque) return f;
                        cambio = true;
                        return { ...f, macros_efectivos: ef, bloque };
                    });
                    return cambio ? next : prev;
                });
            } catch (e) {
                // Si no llega, se quedan los macros estimados: el guardado los cuadra igual.
                console.error('[calibrar-dia en la ventana]', e);
            }
        }, 350);
        return () => clearTimeout(t);
    }, [tempFoods, open, mealKey]); // eslint-disable-line

    const getMacrosParams = () => {
        // Calma's manual builder uses ONE unified remaining (full meal target minus
        // added ingredients), all three macros, NO tolerance. The engine (calma_suggest)
        // computes quantity = floor(min(remaining/perUnit)) and orders by diferenciaDeMacros.
        const params = {};
        if (isManual) return params;   // manual: no suggestion/quantity context
        if (target.P > 0) params.p_rest = Math.max(0, remaining.P);
        if (target.H > 0) params.h_rest = Math.max(0, remaining.H);
        if (target.G > 0) params.g_rest = Math.max(0, remaining.G);
        // Calma prioridad fase: cuadrarMacros once P&H >80% of target (any meal); else peri uses
        // its own list. Peri meals always add margenValido to the fat budget (g_rest).
        const sufP = !(target.P > 0) || served.P / target.P > 0.8;
        const sufH = !(target.H > 0) || served.H / target.H > 0.8;
        if (isIntraMode || isPostMode) {
            params.peri = isIntraMode ? 'intra' : 'post';   // meal type: cat-25 universe + grasas margin
            params.g_rest = target.G - served.G + MARGEN_VALIDO;
        }
        if (sufP && sufH || paso === 3) params.cuadrar = 'true';   // prioridad fase (good fats)
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
                const params = new URLSearchParams({ frequent: 'true', limit: '20', ...getMacrosParams(), ...getDiaParams() });
                const result = await api(`/api/calculator/search?${params}`);
                setCategoryFoods(result.alimentos || []);
                setAvailablePreps(result.available_preps || []);
            } else {
                const params = new URLSearchParams({
                    q: '',
                    category: category.prefixes[0],
                    limit: '100',
                    ...getMacrosParams(),
                    ...getDiaParams(),
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

    /**
     * BUSCAR POR NOMBRE, COMO EN CALMA: ESTA LISTA TIENE QUE SALIR IGUAL QUE LA SUYA.
     *
     * Las tres cosas que hace el buscador de la Dieta de Calma, y las tres están aquí:
     *
     *  1. FILTRA por nombre: cada palabra escrita tiene que estar en el nombre
     *     (`Ye(nombre, texto.split(" "), true)`), sin buscar parecidos. Eso lo hace el
     *     servidor (`buscar_alimentos`) y es lo que cierra el fallo 3 de Jesús (15-08):
     *     buscando «pechuga» salen 58 pechugas y ninguna Pepsi, porque ninguna Pepsi lleva
     *     esa palabra. No hace falta nada más para que mande lo que ha escrito el cliente.
     *  2. PONE CANTIDAD con el hueco de macros de la comida (`ajustarCantidadIngrediente`).
     *     Sin el hueco el alimento entraba con su ración: buscando «leche de almendras»
     *     tapaba 1 g de los 10 g de grasa que faltaban (Francisco, 17-08). Por eso el hueco
     *     viaja con `solo_cantidad`: pone la cantidad y NO tira a nadie de la lista.
     *  3. ORDENA por diferencia de macros y desempata por nombre, y nada más. No puntúa el
     *     parecido con lo escrito: ese scoring (`Ie`) es del catálogo de «Alimentos», que es
     *     otra pantalla. Ordenar aquí por parecido partía la lista en bloques que Calma
     *     mezcla por encaje, y era la lista que no cuadraba con la suya (Francisco, 17-08).
     *
     * `peri` se mantiene porque no es un hueco de macros: dice de qué alimentos se compone
     * un intra o un post.
     */
    const handleSearch = async (query) => {
        setSearchQuery(query);
        const texto = query.trim();

        if (texto.length < 2) {
            turnoBusqueda.current += 1;   // invalida lo que estuviera en vuelo
            setIsSearching(false);
            setSearchResults([]);
            return;
        }

        setIsSearching(true);
        setLoadingFoods(true);
        const miTurno = ++turnoBusqueda.current;

        try {
            const macrosParams = getMacrosParams();
            const params = new URLSearchParams({ q: texto, limit: '200', ...macrosParams, ...getDiaParams() });
            // LOS CHIPS ENCENDIDOS TAMBIÉN FILTRAN AL ESCRIBIR (31-08-2026).
            //
            // Aquí se mandaba solo `q`. Los chips seguían pintados y encendidos, pero en
            // cuanto tecleabas dejaban de existir: un cliente puso «Genérico», buscó «pechuga
            // de pollo» y le salieron todas las marcas. Un filtro que se ve encendido y no
            // filtra es peor que no tenerlo, porque el cliente cree que la lista ya está
            // filtrada.
            const cats = selectedCategories.flatMap(c => c.prefixes || []).filter(Boolean);
            if (cats.length) params.set('category', cats.join(','));
            if (selectedPreparations.length) params.set('tag', selectedPreparations.join(','));
            if (Object.keys(macrosParams).length > 0) params.set('solo_cantidad', 'true');
            if (isIntraMode || isPostMode) params.set('peri', isIntraMode ? 'intra' : 'post');
            const result = await api(`/api/calculator/search?${params}`);
            if (miTurno !== turnoBusqueda.current) return;   // ya se ha escrito otra cosa
            // EL ORDEN VIENE DEL SERVIDOR Y ES EL DE CALMA (diferencia de macros). Reordenar
            // aquí por parecido con lo escrito -- el scoring `Ie`, que es el del catálogo de
            // Alimentos, no el de la Dieta -- dejaba una lista distinta a la de Calma.
            setSearchResults(result.alimentos || []);
        } catch (err) {
            console.error('Error buscando:', err);
            if (miTurno === turnoBusqueda.current) {
                toast.error('No hemos podido buscar ahora mismo. Inténtalo otra vez.');
            }
        } finally {
            if (miTurno === turnoBusqueda.current) setLoadingFoods(false);
        }
    };

    // Y SI TOCAS UN CHIP CON ALGO ESCRITO, SE VUELVE A BUSCAR (31-08-2026). La búsqueda solo
    // se lanza al teclear, así que sin esto encender «Genérico» con «pechuga de pollo» ya
    // escrito no cambiaba la lista: el chip se veía encendido y los resultados eran los de
    // antes. Mismo fallo por otra puerta.
    useEffect(() => {
        if (!open) return;
        const texto = (searchQuery || '').trim();
        if (texto.length < 2) return;
        handleSearch(searchQuery);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedCategories, selectedPreparations]);

    const handleSelectFood = async (food) => {
        try {
            const foodId = food.id || food._id;
            const alreadyInMeal = (mealsData[mealKey]?.alimentos || []).some(f => f.alimento_id === foodId);
            const alreadyInTemp = tempFoods.some(f => f.alimento_id === foodId);
            if (alreadyInMeal || alreadyInTemp) {
                toast.error(`${food.nombre} ya está en esta comida - ajusta su cantidad directamente.`);
                return;
            }

            const quantity = food._cantidad_sugerida || food.racion || 100;
            // En la comida MANUAL no hay hueco que cuadrar, así que el alimento no trae
            // macros calculados y se le piden al servidor: escalar aquí los campos crudos
            // contaría lo que dice la etiqueta y no lo que cuenta el método, y en los
            // alimentos por unidades lo multiplicaría además por la ración equivocada.
            let macrosEf;
            let bloque = food.bloque ?? null;
            if (food._macros_sugeridos && Object.keys(food._macros_sugeridos).length > 0) {
                macrosEf = { P: food._macros_sugeridos.P || 0, H: food._macros_sugeridos.H || 0, G: food._macros_sugeridos.G || 0 };
            } else {
                try {
                    const res = await api('/api/calculator/macros-efectivos', {
                        method: 'POST',
                        // Con lo que lleva el día: sin esto la comida manual enseñaba la
                        // proteína de unas almendras a cero y al guardar aparecía (punto 135).
                        body: JSON.stringify({ alimento_id: foodId, cantidad_g: quantity, es_vegano: false,
                                               ...getDiaParams() }),
                    });
                    const ef = res.efectivos || {};
                    macrosEf = { P: ef.P || 0, H: ef.H || 0, G: ef.G || 0 };
                    bloque = res.bloque ?? bloque;
                } catch (e) {
                    console.error('[macros-efectivos]', e);
                    const isUnit = food.por_unidad ?? food.unidades;
                    const factor = isUnit ? (quantity / (food.racion || 100)) : (quantity / 100);
                    macrosEf = {
                        P: Math.round((food.proteinas || 0) * factor * 10) / 10,
                        H: Math.round((food.hidratos || 0) * factor * 10) / 10,
                        G: Math.round((food.grasas || 0) * factor * 10) / 10,
                    };
                }
            }

            // LO QUE EL CLIENTE HA BUSCADO ENTRA (Jesús, 15-08, punto 2 de las mejoras: «que
            // lo que el cliente ha nombrado entre sí o sí»). El bloqueo de Calma -- no dejar
            // meter algo que se pase del objetivo -- se queda para las SUGERENCIAS, que es
            // donde tiene sentido: allí lo propone la app. Si lo ha escrito él, entra y se le
            // dice que se pasa, con la cantidad a mano para bajarla.
            const seVaDeMadre = isManual ? null : getBlockReason(macrosEf);
            if (seVaDeMadre) {
                if (!isSearching) { toast.error(seVaDeMadre); return; }
                toast.warning(`${food.nombre} entra, pero esta comida se pasa. Baja la cantidad si quieres cuadrarla.`);
            }

            // Cuadrar el macro puede pedir una cantidad que no se come: 10 g de grasa con
            // leche de almendras son casi 900 ml. Se pone -- es la cantidad que cuadra --
            // pero se avisa, igual que al teclearla a mano (Jesús, 16-08).
            const avisoTope = avisoRazonable(food, quantity, {
                porUnidad: Boolean(food.por_unidad ?? food.unidades),
                pesoUnidad: food.peso_unidad || food.racion || 0,
            });
            if (avisoTope) toast.warning(avisoTope, { id: 'tope-razonable' });

            const foodToAdd = {
                ...food,
                alimento_id: food.id || food._id,
                cantidad_g: quantity,
                por_unidad: food.por_unidad ?? food.unidades ?? false,
                peso_unidad: food.peso_unidad || food.racion || 100,
                racion: food.racion || 100,
                macros_efectivos: macrosEf,
                // La familia calibrada, para que el siguiente alimento que se busque cuente
                // ya estos gramos en el tramo del día (`getDiaParams`).
                bloque,
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
        if (newQty > TOPE_GRAMOS) { toast.warning(AVISO_TOPE, { id: 'tope-cantidad' }); return; }
        // Lo que cabe de ESTE alimento en una comida: se avisa y se deja seguir (16-08).
        const avisoTope = avisoRazonable(selectedFood, newQty, { porUnidad: isPorUnidad, pesoUnidad: unitWeight });
        if (avisoTope) toast.warning(avisoTope, { id: 'tope-razonable' });

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

    // Recalcula macros efectivos para una cantidad (en gramos) dada.
    /**
     * Al cambiar la cantidad, los macros se escalan y el servidor los confirma.
     *
     * Esto rehacía la cuenta desde los macros de la etiqueta (`f.proteinas * mult`), y esos
     * llegan del servidor ya puestos a cero por la regla de categoría: al pulsar «+» sobre
     * unos anacardos su proteína calibrada se iba a cero. Escalar lo que ya cuenta nunca
     * inventa un cero, y el efecto de abajo lo cuadra con el motor del día en cuanto
     * responde -- que es quien sabe si al subir la cantidad se ha cruzado de tramo.
     */
    const recalcFoodMacros = (f, newQty) => {
        const antes = Number(f.cantidad_g ?? f.cantidad ?? 0);
        const ef = f.macros_efectivos || {};
        const k = antes > 0 ? newQty / antes : 0;
        const e = (v) => Math.round((v || 0) * k * 10) / 10;
        return {
            ...f,
            cantidad_g: newQty,
            macros_efectivos: { P: e(ef.P), H: e(ef.H), G: e(ef.G) },
        };
    };

    const handleFoodQuantityChange = (index, delta) => {
        // Calma lets you freely increase/decrease an added food's quantity even past the
        // meal target - the macro bars just show over-target (red). No block.
        setTempFoods(prev => prev.map((f, i) => {
            if (i !== index) return f;
            const isUnit = f.por_unidad ?? f.unidades;
            const racion = f.racion || 100;
            const step = isUnit ? (f.peso_unidad || racion) : 1;
            const currentQty = f.cantidad_g || f.cantidad || 0;
            const newQty = Math.max(step, currentQty + (delta * step));
            // El tope por arriba también con los botones: llegar a 2000 g de 5 en 5 cuesta,
            // pero un alimento por unidades sube de 250 en 250 (fallo 28).
            if (newQty > TOPE_GRAMOS) {
                toast.warning(AVISO_TOPE, { id: 'tope-cantidad' });
                return f;
            }
            // Y el tope con sentido humano de ese alimento concreto (16-08): avisa, no corta.
            const aviso = avisoRazonable(f, newQty, { porUnidad: Boolean(isUnit), pesoUnidad: step });
            if (aviso) toast.warning(aviso, { id: 'tope-razonable' });
            return recalcFoodMacros(f, newQty);
        }));
    };

    /**
     * Cantidad absoluta tecleada. Para alimentos por unidad el valor es en UNIDADES
     * (se convierte a gramos con peso_unidad/racion); para granel, en gramos.
     *
     * Lo que no se entiende se rechaza y la cantidad se queda como estaba (fallo 4): antes
     * un «abc» o un «-50» la ponían a 0 g, con el alimento dentro de la comida sumando nada.
     */
    const handleFoodQuantitySet = (index, rawValue) => {
        const actual = tempFoods[index];
        if (!actual) return;
        const isUnit = Boolean(actual.por_unidad ?? actual.unidades);
        const peso = actual.peso_unidad || actual.racion || 100;
        const lectura = leerCantidad(rawValue, {
            porUnidad: isUnit,
            pesoUnidad: peso,
            minimo: isUnit ? peso : 1,
            alimento: actual,
        });
        if (lectura.estado === 'no_es_numero') {
            // Sin aviso mientras se escribe: el campo se queda vacío un instante al borrar
            // para teclear otra cifra, y un cartel por cada tecla sería insufrible. Se ignora
            // y la cantidad anterior sigue en pie.
            return;
        }
        if (lectura.estado === 'negativo') {
            toast.error(AVISO_NEGATIVO, { id: 'cantidad-negativa' });
            return;
        }
        if (lectura.estado === 'por_debajo_del_minimo') return;   // aún está escribiendo
        if (lectura.estado === 'pasa_del_tope') toast.warning(AVISO_TOPE, { id: 'tope-cantidad' });
        if (lectura.aviso) toast.warning(lectura.aviso, { id: 'tope-razonable' });
        setTempFoods(prev => prev.map((f, i) => (i === index ? recalcFoodMacros(f, lectura.gramos) : f)));
    };

    const handleSaveAndClose = () => {
        if (!mealKey || tempFoods.length === 0) return;

        // tempFoods ya incluye los alimentos que había en la comida (precargados al abrir) más los
        // nuevos, así que REEMPLAZAMOS la lista (no concatenamos, o se duplicarían los existentes).
        setMealsData(prev => ({
            ...prev,
            [mealKey]: {
                ...prev[mealKey],
                alimentos: [...tempFoods]
            }
        }));

        toast.success(`✅ Comida guardada (${tempFoods.length} ${tempFoods.length === 1 ? 'alimento' : 'alimentos'})`);
        onClose();
    };

    const getEmoji = getFoodEmoji || getFoodEmojiLocal;

    // Calma consejoParaEscogerAlimento: phase guidance text (not "Paso 1/2/3").
    const getPasoLabel = () => {
        // En el idioma del cliente, no del programa (Jesús, doc 21-08, apartado 14).
        if (isManual) return 'Modo manual - las cantidades las pones tú y lo compensas en el día';
        if (isIntraMode) return 'Alimentos Intra-entreno';
        if (isPostMode) return 'Alimentos Post-entreno';
        if (paso === 1) return 'Definiendo base de proteínas...';
        if (paso === 2) return 'Añade hidratos de carbono...';
        return 'Termina de cuadrar tus macros';
    };

    // Calma shows ALL category chips for the current phase (filtrosSinAlergias only removes
    // allergy categories); it NEVER hides a category because its foods don't fit the remaining.
    // Individual foods that overshoot are still excluded server-side (ajustarCantidad -> 0).
    // We mirror that: no emptiness-based chip hiding (was dropping most chips in paso 3, where
    // the remaining is tiny). filterAvoided() already applied the allergy removal upstream.
    const categories = getCurrentCategories();
    const rawFoods = isSearching ? searchResults : categoryFoods;
    // Manual: no suggestion ranking, so list alphabetically. Además, en manual ocultamos los
    // alimentos que ya están en la comida o ya añadidos en esta sesión del modal, para que no
    // vuelvan a aparecer en la lista (ya no se pueden volver a añadir, solo ajustar cantidad).
    const addedFoodIds = new Set([
        ...(mealsData[mealKey]?.alimentos || []).map(f => f.alimento_id),
        ...tempFoods.map(f => f.alimento_id),
    ]);
    // Buscando NO se reordena alfabéticamente ni en manual: el orden lo manda el parecido
    // con lo que se ha escrito, que es todo el arreglo del fallo 3.
    const displayFoods = isManual
        ? (isSearching
            ? rawFoods.filter(f => !addedFoodIds.has(f.id || f._id))
            : [...rawFoods]
                .filter(f => !addedFoodIds.has(f.id || f._id))
                .sort((a, b) => (a.nombre || '').localeCompare(b.nombre || '')))
        : rawFoods;

    // Preparations available for the selected category
    const availablePreparations = PREPARATIONS.filter(p => availablePreps.includes(p.value));

    return (
        <Dialog open={open} onOpenChange={() => onClose()}>
            <DialogContent className="max-w-2xl h-[90dvh] p-0 flex flex-col bg-card overflow-hidden">
                <DialogHeader className="flex-shrink-0 px-4 py-3 border-b">
                    {/* pr-8: deja hueco a la derecha para la cruz de cerrar (absolute right-4),
                        si no el switch Automático/Manual queda superpuesto a ella. */}
                    <div className="flex items-center justify-between gap-2 pr-8">
                        <DialogTitle className="text-lg font-bold text-foreground">
                            {mealInfo?.label || `Comida ${mealKey?.replace('C', '')}`}
                        </DialogTitle>
                        {!isPeriMode && setMealMode && (
                            <div className="inline-flex rounded-full bg-muted p-0.5 shrink-0">
                                <button
                                    type="button"
                                    className={`px-2.5 py-1 text-xs font-semibold rounded-full transition-colors ${!isManual ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground'}`}
                                    onClick={() => setMealMode(mealKey, 'auto')}
                                    data-testid="modal-mode-auto"
                                >
                                    Automático
                                </button>
                                <button
                                    type="button"
                                    className={`px-2.5 py-1 text-xs font-semibold rounded-full transition-colors ${isManual ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground'}`}
                                    onClick={() => setMealMode(mealKey, 'manual')}
                                    data-testid="modal-mode-manual"
                                >
                                    Manual
                                </button>
                            </div>
                        )}
                    </div>
                    <DialogDescription className="sr-only">
                        Construye tu comida paso a paso
                    </DialogDescription>
                </DialogHeader>

                {/* La lista de alimentos tiene altura mínima garantizada; si las secciones fijas
                    no caben (móvil o ventana baja), la columna entera hace scroll. */}
                <div className="flex-1 min-h-0 flex flex-col overflow-y-auto">
                    {/* Macros summary */}
                    <div className="flex-shrink-0 px-4 py-2.5 bg-muted border-b">
                        <div className="text-xs font-medium text-muted-foreground mb-1.5 leading-tight">{getPasoLabel()}</div>
                        {/* Peri (intra/post) carry only P+H - Calma shows no Grasas column for them. */}
                        <div className={`grid ${isPeriMode ? 'grid-cols-2' : 'grid-cols-3'} gap-2 text-center leading-tight`}>
                            {(() => { const c = macroCell(served.P, target.P, "P"); return (
                                <div>
                                    <div className="text-xs text-muted-foreground">Proteína</div>
                                    <div className={`text-lg font-bold ${c.over ? 'text-red-500' : 'text-orange-500'}`}>{c.num}</div>
                                    {c.status && <div className={`text-[10px] font-semibold ${c.cls}`}>{c.status}</div>}
                                </div>
                            ); })()}
                            {(() => { const c = macroCell(served.H, target.H, "H"); return (
                                <div>
                                    <div className="text-xs text-muted-foreground">Hidratos</div>
                                    <div className={`text-lg font-bold ${c.over ? 'text-red-500' : 'text-blue-500'}`}>{c.num}</div>
                                    {c.status && <div className={`text-[10px] font-semibold ${c.cls}`}>{c.status}</div>}
                                </div>
                            ); })()}
                            {!isPeriMode && (() => { const c = macroCell(served.G, target.G, "G"); return (
                                <div>
                                    <div className="text-xs text-muted-foreground">Grasas</div>
                                    <div className={`text-lg font-bold ${c.over ? 'text-red-500' : 'text-yellow-500'}`}>{c.num}</div>
                                    {c.status && <div className={`text-[10px] font-semibold ${c.cls}`}>{c.status}</div>}
                                </div>
                            ); })()}
                        </div>
                    </div>

                    {/* Search bar */}
                    <div className="flex-shrink-0 p-3 border-b">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground w-4 h-4" />
                            <Input
                                placeholder="Buscar alimento..."
                                value={searchQuery}
                                onChange={(e) => handleSearch(e.target.value)}
                                className="pl-10 pr-10"
                            />
                            {searchQuery && (
                                <button
                                    onClick={() => { setSearchQuery(''); setIsSearching(false); setSearchResults([]); }}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-muted-foreground"
                                >
                                    <X className="w-4 h-4" />
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Category + Preparation Rails - hidden for intra (Calma: chips hidden) */}
                    {(isManual || !isCuadrada) && !isIntraMode && <div className="flex-shrink-0 px-3 pt-3 pb-2 border-b bg-card space-y-2">
                        {/* Dos filas visibles y el resto tras "Mostrar más".
                            Las categorías son círculos con icono, y el nombre sale al pasar por
                            encima y SE QUEDA abierto en la que está marcada -- en un móvil no hay
                            ratón, así que sin eso no habría forma de saber qué es cada dibujo.
                            El 09-08 se cambiaron por pastillas con el nombre dentro y se quitó ese
                            comportamiento; Francisco pidió volver atrás el 11-08. Los campos
                            `short` que se añadieron para aquello siguen en las listas de abajo,
                            sin usarse. */}
                        <CategoryRail
                            label="Categorías"
                            categories={categories}
                            value={selectedCategories.map(c => c.id)}
                            onChange={handleCategoriesChange}
                            size="sm"
                            collapsible
                            maxRows={2}
                        />
                        {selectedCategories.length > 0 && availablePreparations.length > 0 && (
                            <CategoryRail
                                label="Preparación"
                                categories={availablePreparations}
                                value={selectedPreparations}
                                onChange={setSelectedPreparations}
                                size="sm"
                                collapsible
                                maxRows={2}
                            />
                        )}
                    </div>}

                    {/* Food list. Scroll NATIVO (no el ScrollArea de Radix): su viewport
                        envuelve el contenido en un div display:table que ignora el ancho del
                        padre y hacía crecer las filas hasta el nombre más largo (en móvil se
                        cortaban contra el borde). Con overflow nativo el ancho se limita al
                        contenedor y los nombres largos saltan de línea. */}
                    <div className="flex-1 min-h-[38vh] overflow-y-auto">
                        <div className="p-3">
                            {!isSearching && selectedCategories.length === 0 ? (
                                <div className="text-center py-10 text-muted-foreground text-sm">
                                    Selecciona una categoría arriba para ver los alimentos
                                </div>
                            ) : (
                                <>
                                    {loadingFoods ? (
                                        <div className="text-center py-8 text-muted-foreground">Cargando...</div>
                                    ) : displayFoods.length === 0 ? (
                                        /* BUSCANDO Y SIN NADA, EL MISMO TEXTO QUE EN ALIMENTOS
                                           (punto 144 del 27-08: «igual en los dos sitios»).
                                           Los otros dos vacíos NO son éste y se quedan como
                                           están: uno es no tener frecuentes todavía y el otro
                                           una categoría vacía, y ninguno de los dos es «no lo
                                           tenemos». */
                                        isSearching ? <SinResultados /> : (
                                        <div className="text-center py-8 text-muted-foreground">
                                            {selectedCategories.some(c => c.id === '__frequent__')
                                                ? 'Aún no tienes alimentos frecuentes - guarda algunas dietas primero'
                                                : 'No hay alimentos en esta categoría'}
                                        </div>
                                        )
                                    ) : (
                                        <div className="space-y-1">
                                            {/* DE DÓNDE SALE ESTA LISTA. Jesús, 15-08: «que lo que
                                                el cliente ha nombrado entre sí o sí, con las
                                                sugerencias aparte y marcadas como sugerencias».
                                                Buscando manda el texto; por categorías, lo que le
                                                falta a la comida -- y así se dice. */}
                                            <p className="text-[11px] text-muted-foreground mb-1.5" data-testid="origen-lista">
                                                {isSearching
                                                    ? <>Resultados de <span className="font-semibold text-foreground">«{searchQuery.trim()}»</span>{isManual ? '' : ', con la cantidad ya ajustada y el que mejor encaja primero'}</>
                                                    : isManual
                                                        ? 'Alimentos de la categoría, por orden alfabético'
                                                        : 'Sugerencias para lo que le falta a esta comida, con la cantidad ya ajustada'}
                                            </p>
                                            {displayFoods.map((food, idx) => {
                                                const isFav = favorites.has(String(food.id));
                                                return (
                                                    <div key={food.id || idx} className="flex items-center gap-1">
                                                        {FOOD_FAVORITES_UI && (
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); toggleFavorite(food.id); }}
                                                                className={`flex-shrink-0 p-1 rounded transition-colors ${isFav ? 'text-yellow-400' : 'text-muted-foreground hover:text-yellow-300'}`}
                                                                data-testid={`fav-toggle-${food.id}`}
                                                            >
                                                                <Star className="w-4 h-4" fill={isFav ? 'currentColor' : 'none'} />
                                                            </button>
                                                        )}
                                                        <button
                                                            onClick={() => handleSelectFood(food)}
                                                            className="flex-1 flex items-center gap-2 p-2 rounded-lg text-left transition-colors hover:bg-muted"
                                                            data-testid={`food-item-${food.id || idx}`}
                                                        >
                                                            <div className="flex-1 min-w-0">
                                                                <div className="text-sm text-foreground leading-snug break-words">
                                                                    {food.nombre}
                                                                    {food.is_promocionado && (
                                                                        <span className="ml-1.5 align-middle inline-block text-[9px] font-bold tracking-wide text-white bg-black rounded px-1 py-0.5">PROMOCIONADO</span>
                                                                    )}
                                                                </div>
                                                                <div className="text-xs text-muted-foreground">
                                                                    {food._cantidad_sugerida
                                                                        ? `${(food.por_unidad ?? food.unidades) && (food.peso_unidad || food.racion) > 0
                                                                            ? `${num1(Math.round(food._cantidad_sugerida / (food.peso_unidad || food.racion) * 2) / 2)} ud (${num1(food._cantidad_sugerida)} g/ml)`
                                                                            : `${num1(food._cantidad_sugerida)} g`} → `
                                                                        // Sin cantidad del motor (comida manual, sin objetivo que cuadrar):
                                                                        // se dice a cuánto equivale una unidad, que es lo que se añadirá.
                                                                        : (food.por_unidad ?? food.unidades) && (food.peso_unidad || food.racion) > 0
                                                                            ? `1 ud (${num1(food.peso_unidad || food.racion)} g/ml) → `
                                                                            : `${num1(food.racion || 100)} g → `}
                                                                    {(() => {
                                                                        // Sin cantidad sugerida (comida manual) se enseñan los macros
                                                                        // de UNA ración, que es lo que trae el catálogo ya pasado
                                                                        // por las reglas del método (`macros_efectivos`).
                                                                        const ms = food._macros_sugeridos || food.macros_efectivos;
                                                                        const qty = food._cantidad_sugerida || food.racion || 100;
                                                                        const fmt = num1;
                                                                        const p = ms?.P ?? (food.proteinas || 0) * qty / 100;
                                                                        const h = ms?.H ?? (food.hidratos || 0) * qty / 100;
                                                                        const g = ms?.G ?? (food.grasas || 0) * qty / 100;
                                                                        // Colores P/H/G consistentes con la cabecera del modal: P naranja, H azul, G amarillo.
                                                                        const parts = [
                                                                            // Tonos oscuros en claro: a este tamaño el amarillo 500 sobre
                                                                            // blanco queda en 1,97:1 y no se lee (QA del 15-08).
                                                                            p > 0 ? <span key="p" className="font-semibold text-orange-600 dark:text-orange-400">P={fmt(p)} g</span> : null,
                                                                            h > 0 ? <span key="h" className="font-semibold text-blue-700 dark:text-blue-400">H={fmt(h)} g</span> : null,
                                                                            g > 0 ? <span key="g" className="font-semibold text-yellow-700 dark:text-yellow-400">G={fmt(g)} g</span> : null,
                                                                        ].filter(Boolean);
                                                                        if (parts.length === 0) return 'No aporta macros';
                                                                        return parts.reduce((acc, el, i) => (i === 0 ? [el] : [...acc, ' ', el]), []);
                                                                    })()}
                                                                </div>
                                                            </div>
                                                            <Plus className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                                                        </button>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </div>

                </div>

                {/* Added foods - barra SIEMPRE visible, anclada fuera del scroll (encima del botón de guardar) */}
                {tempFoods.length > 0 && (() => {
                        const tot = tempFoods.reduce((a, f) => ({
                            P: a.P + (f.macros_efectivos?.P || 0),
                            H: a.H + (f.macros_efectivos?.H || 0),
                            G: a.G + (f.macros_efectivos?.G || 0),
                        }), { P: 0, H: 0, G: 0 });
                        const fmt = v => Math.round(v);
                        return (
                            <div className={`border-t bg-muted flex flex-col ${addedOpen ? 'min-h-0 max-h-52' : 'flex-shrink-0'}`}>
                                <button
                                    type="button"
                                    onClick={() => setAddedOpen(o => !o)}
                                    className="flex-shrink-0 w-full flex items-center justify-between px-3 py-2.5 text-sm font-medium text-foreground"
                                    data-testid="added-bar-toggle"
                                >
                                    <span className="flex items-center gap-2">
                                        <span className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-black text-white text-xs">{tempFoods.length}</span>
                                        <span>{tempFoods.length === 1 ? 'añadido' : 'añadidos'}</span>
                                        <span className="text-xs font-normal">· <span className="font-semibold text-orange-600 dark:text-orange-400">P {fmt(tot.P)}</span> · <span className="font-semibold text-blue-700 dark:text-blue-400">H {fmt(tot.H)}</span> · <span className="font-semibold text-yellow-700 dark:text-yellow-400">G {fmt(tot.G)}</span></span>
                                    </span>
                                    <span className="inline-flex items-center gap-1 rounded-full border border-brand/40 bg-brand/10 px-2.5 py-1 text-xs font-semibold text-brand flex-shrink-0">
                                        {addedOpen ? 'Ocultar' : 'Ver'}
                                        <ChevronUp className={`w-3.5 h-3.5 transition-transform ${addedOpen ? '' : 'rotate-180'}`} />
                                    </span>
                                </button>
                                {addedOpen && (
                                    <div className="flex-1 min-h-0 overflow-y-auto px-3 pb-3 space-y-1">
                                        {tempFoods.map((food, idx) => (
                                            <div key={idx} className="flex items-center gap-2 bg-card rounded p-2 text-sm">
                                                {/* El nombre entero en el title: recortado con
                                                    puntos suspensivos no hay forma de saber qué
                                                    es «Salmón ahumado (Ha…» (Jesús, fallo 44). */}
                                                <span className="flex-1 truncate text-foreground" title={food.nombre}>{food.nombre}</span>
                                                <div className="flex items-center gap-1">
                                                    <button
                                                        onClick={() => handleFoodQuantityChange(idx, -1)}
                                                        data-testid={`temp-menos-${idx}`}
                                                        className="w-6 h-6 flex items-center justify-center bg-muted rounded"
                                                    >
                                                        <Minus className="w-3 h-3" />
                                                    </button>
                                                    {(() => {
                                                        const isUnit = (food.por_unidad ?? food.unidades) && (food.peso_unidad || food.racion) > 0;
                                                        const grams = food.cantidad_g || food.cantidad || 0;
                                                        const display = isUnit
                                                            ? Math.round((grams / (food.peso_unidad || food.racion)) * 2) / 2
                                                            : grams;
                                                        const value = qtyDraft[idx] !== undefined ? qtyDraft[idx] : display;
                                                        return (
                                                            <span className="flex items-center gap-1">
                                                                {/* Con techo: el campo no tenía `max` y la flecha de arriba subía
                                                                    sin final. El techo es el tope duro, en la unidad del campo;
                                                                    el tope razonable del alimento avisa aparte. */}
                                                                <input
                                                                    type="number"
                                                                    min="0"
                                                                    max={isUnit
                                                                        ? Math.floor(TOPE_GRAMOS / (food.peso_unidad || food.racion || 100))
                                                                        : TOPE_GRAMOS}
                                                                    step={isUnit ? '0.5' : '1'}
                                                                    value={value}
                                                                    onChange={(e) => { setQtyDraft(d => ({ ...d, [idx]: e.target.value })); handleFoodQuantitySet(idx, e.target.value); }}
                                                                    onBlur={() => setQtyDraft(d => { const n = { ...d }; delete n[idx]; return n; })}
                                                                    onFocus={(e) => e.target.select()}
                                                                    className="w-12 text-center text-xs bg-muted rounded px-1 py-1 text-foreground focus:outline-none focus:ring-1 focus:ring-[#FF671F]"
                                                                />
                                                                {/* Los gramos de LO QUE HAY, no los de una unidad suelta: con medio
                                                                    plátano en el plato ponía «0,5 ud (100 g)» y quien lo lee entiende
                                                                    que medio plátano son 100 g (QA del 15-08 en producción). */}
                                                                <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                                                                    {isUnit ? `ud (${num1(grams)} g)` : 'g'}
                                                                </span>
                                                            </span>
                                                        );
                                                    })()}
                                                    <button
                                                        onClick={() => handleFoodQuantityChange(idx, 1)}
                                                        data-testid={`temp-mas-${idx}`}
                                                        className="w-6 h-6 flex items-center justify-center bg-muted rounded"
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
                                )}
                            </div>
                        );
                })()}

                {/* Footer */}
                <div className="flex-shrink-0 bg-card border-t p-4">
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
