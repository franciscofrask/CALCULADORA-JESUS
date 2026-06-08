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
import { Search, X, Plus, Minus, ArrowLeft, Star } from 'lucide-react';
import { PREFERENCE_CATEGORIES } from './PreferencesSetup';

// Categories for Build Meal Modal - Step 1 (Proteínas)
const PROTEIN_CATEGORIES = [
    { id: 'huevos', label: 'Huevos', emoji: '🥚', prefixes: ['1.2'] },
    { id: 'claras', label: 'Claras', emoji: '🍳', prefixes: ['1.1'] },
    { id: 'embutidos', label: 'Embutidos', emoji: '🥓', prefixes: ['2.1'] },
    { id: 'aves', label: 'Aves', emoji: '🍗', prefixes: ['2.2'] },
    { id: 'vacuno', label: 'Vacuno', emoji: '🥩', prefixes: ['2.3'] },
    { id: 'cerdo', label: 'Cerdo', emoji: '🐷', prefixes: ['2.4'] },
    { id: 'otras_carnes', label: 'Otras carnes', emoji: '🍖', prefixes: ['2.5', '2.6', '2.7', '40', '45'] },
    { id: 'pescados', label: 'Pescados', emoji: '🐟', prefixes: ['3'] },
    { id: 'lacteos', label: 'Lácteos', emoji: '🧀', prefixes: ['5'] },
    { id: 'proteina_polvo', label: 'Proteína', emoji: '🥤', prefixes: ['4'] },
    { id: 'legumbres', label: 'Legumbres', emoji: '🫘', prefixes: ['10'] },
    { id: 'vegetal', label: 'Vegetal', emoji: '🌱', prefixes: ['28', '6'] },
];

// Categories for Build Meal Modal - Step 2 (Acompañamientos)
const SIDE_CATEGORIES = [
    { id: 'arroces', label: 'Arroces', emoji: '🍚', prefixes: ['21'] },
    { id: 'panes', label: 'Panes', emoji: '🍞', prefixes: ['8'] },
    { id: 'cereales', label: 'Cereales', emoji: '🌾', prefixes: ['7'] },
    { id: 'pasta', label: 'Pasta', emoji: '🍝', prefixes: ['22'] },
    { id: 'tuberculos', label: 'Tubérculos', emoji: '🥔', prefixes: ['9'] },
    { id: 'fruta', label: 'Fruta', emoji: '🍎', prefixes: ['11'] },
    { id: 'verduras', label: 'Verduras', emoji: '🥬', prefixes: ['13'] },
    { id: 'legumbres', label: 'Legumbres', emoji: '🫘', prefixes: ['10'] },
    { id: 'lacteos', label: 'Lácteos', emoji: '🧀', prefixes: ['5'] },
    { id: 'bebidas', label: 'Bebidas', emoji: '🥤', prefixes: ['19', '24'] },
    { id: 'comida_prep', label: 'Comida prep.', emoji: '🍕', prefixes: ['32', '39', '49', '50', '51', '53'] },
    { id: 'dulces', label: 'Dulces', emoji: '🍫', prefixes: ['31', '34', '35', '36', '37', '43', '44', '47'] },
    { id: 'salsas', label: 'Salsas', emoji: '🥫', prefixes: ['16'] },
    { id: 'grasas', label: 'Grasas', emoji: '🫒', prefixes: ['17', '42'] },
    { id: 'sopas', label: 'Sopas', emoji: '🍲', prefixes: ['48'] },
];

// INTRA categories - only aminoacids and isotonic
const INTRA_CATEGORIES = [
    { id: 'aminoacidos', label: 'Aminoácidos', emoji: '⚡', prefixes: ['41'] },
    { id: 'isotonicas', label: 'Isotónicas', emoji: '💧', prefixes: ['18.1'] },
];

// POST Step 1 categories - protein powders
const POST_PROTEIN_CATEGORIES = [
    { id: 'whey', label: 'Whey', emoji: '💪', prefixes: ['4.1'] },
    { id: 'caseina', label: 'Caseína', emoji: '🥛', prefixes: ['4.2'] },
    { id: 'vegetal', label: 'Vegetal', emoji: '🌱', prefixes: ['4.3'] },
    { id: 'batido', label: 'Batido', emoji: '🥤', prefixes: ['5.4'] },
];

// POST Step 2 categories - fast carbs
const POST_CARB_CATEGORIES = [
    { id: 'fruta', label: 'Fruta', emoji: '🍎', prefixes: ['11'] },
    { id: 'crema_arroz', label: 'C. Arroz', emoji: '🍚', prefixes: ['21.3'] },
    { id: 'cereales', label: 'Cereales', emoji: '🌾', prefixes: ['7.1'] },
    { id: 'bebida', label: 'Bebida', emoji: '🥤', prefixes: ['24'] },
];

// Food emojis
const FOOD_EMOJIS = {
    '2': '🥩', '3': '🐟', '1': '🥚', '5': '🥛', '4': '💪',
    '7': '🌾', '8': '🍞', '21': '🍚', '22': '🍝', '9': '🥔',
    '10': '🫘', '11': '🍎', '13': '🥦', '17': '🫒', '17.2': '🥜',
    '16': '🥫', '24': '🥤', 'default': '🍽️'
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
    // Estados principales
    const [paso, setPaso] = useState(1);
    const [tempFoods, setTempFoods] = useState([]);
    
    // Estado de categoría seleccionada
    const [selectedCategory, setSelectedCategory] = useState(null);
    const [categoryFoods, setCategoryFoods] = useState([]);
    const [loadingFoods, setLoadingFoods] = useState(false);
    
    // Búsqueda
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [isSearching, setIsSearching] = useState(false);
    
    // Selected food for quantity adjustment
    const [selectedFood, setSelectedFood] = useState(null);
    const [adjustedQuantity, setAdjustedQuantity] = useState(0);
    const [adjustedMacros, setAdjustedMacros] = useState({ P: 0, H: 0, G: 0 });

    // Favorites
    const [favorites, setFavorites] = useState(new Set());

    // Categories with no available foods (when macros context active)
    const [emptyCategoryIds, setEmptyCategoryIds] = useState(new Set());

    // Mode-specific config
    const isIntraMode = mode === 'intra';
    const isPostMode = mode === 'post';
    const isPeriMode = isIntraMode || isPostMode;
    
    // Calculate served and remaining macros
    // existingServed = foods already in the meal before opening the modal
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

    // Load favorites on mount
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
    
    // Check if meal is "cuadrada"
    const isCuadrada = Math.abs(target.P - served.P) <= 4 && 
                       Math.abs(target.H - served.H) <= 4 && 
                       (isPeriMode || Math.abs(target.G - served.G) <= 4);

    // Check if a food should be blocked (adding it would push any macro over target + margin)
    const getBlockReason = (macrosEf) => {
        if (isPeriMode) return null;
        const margin = mealKey === 'Intra' ? 2 : 4;
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

    // Check block for a food item in the list
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
    
    // Emoji mapping for preferences
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
    
    // Determine categories based on mode and paso
    const getCurrentCategories = () => {
        if (isIntraMode) return INTRA_CATEGORIES;
        if (isPostMode) {
            return paso === 1 ? POST_PROTEIN_CATEGORIES : POST_CARB_CATEGORIES;
        }
        if (paso === 1) return PROTEIN_CATEGORIES;
        if (paso === 2) return SIDE_CATEGORIES;
        // Paso 3 - Últimos toques
        if (paso === 3) {
            let cats = [];
            if (userPreferences && userPreferences.length > 0) {
                cats = PREFERENCE_CATEGORIES
                    .filter(cat => userPreferences.includes(cat.id))
                    .map(cat => ({
                        ...cat,
                        emoji: preferenceEmojis[cat.id] || '🍽️'
                    }));
            } else {
                cats = [...SIDE_CATEGORIES];
            }
            
            // Always include good fats if fat is still needed
            const grasaRestante = Math.max(0, target.G - served.G);
            if (grasaRestante > 1) {
                const grasaCat = { id: 'grasas_buenas', label: 'Grasas de buena calidad', emoji: '🫒', prefixes: ['42'] };
                if (!cats.find(c => c.id === 'grasas_buenas')) {
                    cats.unshift(grasaCat);
                }
            }
            
            return cats;
        }
        return SIDE_CATEGORIES;
    };
    
    // Reset state when modal opens
    useEffect(() => {
        if (open && mealKey) {
            setPaso(1);
            setTempFoods([]);
            setSelectedCategory(null);
            setCategoryFoods([]);
            setSearchQuery('');
            setSearchResults([]);
            setIsSearching(false);
            setSelectedFood(null);
        }
    }, [open, mealKey, mode]);
    
    // Auto-advance paso based on macros
    useEffect(() => {
        if (tempFoods.length === 0) {
            if (paso !== 1) {
                setPaso(1);
                setSelectedCategory(null);
                setCategoryFoods([]);
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
            }
        } else if (pPct >= 80 && hPct < 80) {
            if (paso !== 2) {
                setPaso(2);
                setSelectedCategory(null);
                setCategoryFoods([]);
                toast.info('✅ Proteínas cubiertas. Elige el acompañamiento.');
            }
        } else if (pPct >= 80 && hPct >= 80) {
            if (paso !== 3) {
                setPaso(3);
                setSelectedCategory(null);
                setCategoryFoods([]);
                toast.info('✨ ¡Macros cubiertos! Últimos toques.');
            }
        }
    }, [served.P, served.H, target.P, target.H, tempFoods.length, paso, isIntraMode]);
    
    // Reload current category when remaining macros change (auto-quantity updates after adding a food)
    useEffect(() => {
        if (!open) return;
        let cancelled = false;
        if (selectedCategory) {
            const params = new URLSearchParams({ q: '', category: selectedCategory.prefixes[0], limit: '100' });
            if (target.P > 0) params.set('p_rest', remaining.P);
            if (target.H > 0) params.set('h_rest', remaining.H);
            if (target.G > 0) params.set('g_rest', remaining.G);
            api(`/api/calculator/search?${params}`).then(result => {
                if (!cancelled) setCategoryFoods(sortByFit(result.alimentos || []));
            }).catch(() => {});
        } else if (isSearching && searchQuery.length >= 2) {
            const params = new URLSearchParams({ q: searchQuery, limit: '50', ...getMacrosParams() });
            api(`/api/calculator/search?${params}`).then(result => {
                if (!cancelled) setSearchResults(sortByFit(result.alimentos || []));
            }).catch(() => {});
        }
        return () => { cancelled = true; };
    }, [remaining.P, remaining.H, remaining.G]); // eslint-disable-line

    // Pre-check which categories have available foods (hide empty ones)
    useEffect(() => {
        const hasMacros = target.P > 0 || target.H > 0 || target.G > 0;
        if (!open || !hasMacros) {
            setEmptyCategoryIds(new Set());
            return;
        }
        const cats = getCurrentCategories();
        const macroParams = {};
        if (target.P > 0) macroParams.p_rest = remaining.P;
        if (target.H > 0) macroParams.h_rest = remaining.H;
        if (target.G > 0) macroParams.g_rest = remaining.G;
        let cancelled = false;
        Promise.all(cats.map(async cat => {
            try {
                const params = new URLSearchParams({ q: '', category: cat.prefixes[0], limit: '1', ...macroParams });
                const result = await api(`/api/calculator/search?${params}`);
                return { id: cat.id, empty: (result.alimentos || []).length === 0 };
            } catch {
                return { id: cat.id, empty: false };
            }
        })).then(results => {
            if (!cancelled) setEmptyCategoryIds(new Set(results.filter(r => r.empty).map(r => r.id)));
        });
        return () => { cancelled = true; };
    }, [open, paso, remaining.P, remaining.H, remaining.G]); // eslint-disable-line

    // Build macros context params for search (so backend auto-calculates quantity + sorts by aporte)
    const getMacrosParams = () => {
        const params = {};
        if (target.P > 0) params.p_rest = remaining.P;
        if (target.H > 0) params.h_rest = remaining.H;
        if (target.G > 0) params.g_rest = remaining.G;
        return params;
    };

    // Sort foods by how well they fill the most-needed macro first
    const sortByFit = (foods) => {
        if (!foods.length) return foods;
        const pFilled = target.P > 0 ? served.P / target.P : 1;
        const hFilled = target.H > 0 ? served.H / target.H : 1;
        const gFilled = target.G > 0 ? served.G / target.G : 1;
        // Primary macro = least filled (most needed)
        const primary = pFilled <= hFilled && pFilled <= gFilled ? 'P'
            : hFilled <= pFilled && hFilled <= gFilled ? 'H' : 'G';
        const macroKey = { P: 'proteinas', H: 'hidratos', G: 'grasas' }[primary];
        return [...foods].sort((a, b) => {
            const getContrib = (food) => {
                if (food._macros_sugeridos) return food._macros_sugeridos[primary] || 0;
                const qty = food._cantidad_sugerida || food.racion || 100;
                return (food[macroKey] || 0) * qty / 100;
            };
            return getContrib(b) - getContrib(a);
        });
    };

    // Handle category click
    const handleCategoryClick = async (category) => {
        setSelectedCategory(category);
        setLoadingFoods(true);
        setCategoryFoods([]);

        try {
            const params = new URLSearchParams({
                q: '',
                category: category.prefixes[0],
                limit: '100',
                ...getMacrosParams()
            });
            const result = await api(`/api/calculator/search?${params}`);
            setCategoryFoods(sortByFit(result.alimentos || []));
        } catch (err) {
            console.error('Error cargando alimentos:', err);
            toast.error('Error cargando alimentos');
        } finally {
            setLoadingFoods(false);
        }
    };

    // Handle back to categories
    const handleBackToCategories = () => {
        setSelectedCategory(null);
        setCategoryFoods([]);
    };

    // Handle search
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
            setSearchResults(sortByFit(result.alimentos || []));
        } catch (err) {
            console.error('Error buscando:', err);
        } finally {
            setLoadingFoods(false);
        }
    };
    
    // Handle select food
    const handleSelectFood = async (food) => {
        try {
            const foodId = food.id || food._id;
            const alreadyInMeal = (mealsData[mealKey]?.alimentos || []).some(f => f.alimento_id === foodId);
            const alreadyInTemp = tempFoods.some(f => f.alimento_id === foodId);
            if (alreadyInMeal || alreadyInTemp) {
                toast.error(`${food.nombre} ya está en esta comida — ajusta su cantidad directamente.`);
                return;
            }

            // Usar cantidad calculada por el backend (ajustada a macros restantes) o la ración estándar
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
    
    // Handle food with quantity adjustment preview
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
    
    // Adjust quantity
    const handleAdjustQuantity = (delta) => {
        if (!selectedFood) return;
        const isPorUnidad = selectedFood.por_unidad ?? selectedFood.unidades;
        const unitWeight = selectedFood.peso_unidad || selectedFood.racion || 100;
        const step = isPorUnidad ? unitWeight : 10;
        const newQty = Math.max(step, adjustedQuantity + (delta * step));
        setAdjustedQuantity(newQty);
        
        const factor = newQty / 100;
        setAdjustedMacros({
            P: Math.round((selectedFood.proteinas || 0) * factor * 10) / 10,
            H: Math.round((selectedFood.hidratos || 0) * factor * 10) / 10,
            G: Math.round((selectedFood.grasas || 0) * factor * 10) / 10
        });
    };
    
    // Confirm add adjusted food
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
    
    // Remove food
    const handleRemoveFood = (index) => {
        setTempFoods(prev => prev.filter((_, i) => i !== index));
    };
    
    // Increase/decrease food quantity
    const handleFoodQuantityChange = (index, delta) => {
        if (delta > 0) {
            const food = tempFoods[index];
            const step = (food.por_unidad ?? food.unidades) ? (food.peso_unidad || food.racion || 100) : 10;
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
            const margin = mealKey === 'Intra' ? 2 : 4;
            if ((newMacros.P > 0 && otherServed.P + newMacros.P > target.P + margin) ||
                (newMacros.H > 0 && otherServed.H + newMacros.H > target.H + margin) ||
                (newMacros.G > 0 && otherServed.G + newMacros.G > target.G + margin)) {
                toast.error('No puedes aumentar más — superaría los macros objetivo.');
                return;
            }
        }
        setTempFoods(prev => prev.map((f, i) => {
            if (i !== index) return f;
            const step = (f.por_unidad ?? f.unidades) ? (f.peso_unidad || f.racion || 100) : 10;
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
    
    // Save and close
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
    
    // Get emoji for food
    const getEmoji = getFoodEmoji || getFoodEmojiLocal;
    
    // Get paso label
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
    const categories = hasMacrosContext
        ? allCategories.filter(cat => !emptyCategoryIds.has(cat.id))
        : allCategories;
    const displayFoods = isSearching ? searchResults : categoryFoods;

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
                    
                    {/* Content area */}
                    <ScrollArea className="flex-1">
                        <div className="p-3">
                            {/* Food preview for quantity adjustment */}
                            {selectedFood && (
                                <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 mb-3">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="font-medium text-black">{selectedFood.nombre}</span>
                                        <button onClick={() => setSelectedFood(null)} className="text-gray-400">
                                            <X className="w-4 h-4" />
                                        </button>
                                    </div>
                                    <div className="flex items-center justify-center gap-3 mb-2">
                                        <Button variant="outline" size="sm" onClick={() => handleAdjustQuantity(-1)}>
                                            <Minus className="w-4 h-4" />
                                        </Button>
                                        <span className="text-lg font-bold w-24 text-center">
                                            {(selectedFood.por_unidad ?? selectedFood.unidades) && (selectedFood.peso_unidad || selectedFood.racion) > 0
                                                ? `${Math.round((adjustedQuantity / (selectedFood.peso_unidad || selectedFood.racion)) * 2) / 2} ud`
                                                : `${adjustedQuantity}g`
                                            }
                                        </span>
                                        <Button variant="outline" size="sm" onClick={() => handleAdjustQuantity(1)}>
                                            <Plus className="w-4 h-4" />
                                        </Button>
                                    </div>
                                    <div className="text-xs text-gray-600 text-center mb-2">
                                        P={adjustedMacros.P}g · H={adjustedMacros.H}g · G={adjustedMacros.G}g
                                    </div>
                                    <Button onClick={handleConfirmAddFood} className="w-full bg-orange-500 hover:bg-orange-600">
                                        Añadir
                                    </Button>
                                </div>
                            )}
                            
                            {/* Categories or food list */}
                            {!isSearching && !selectedCategory ? (
                                <div className="grid grid-cols-3 gap-2">
                                    {categories.map(cat => (
                                        <button
                                            key={cat.id}
                                            onClick={() => handleCategoryClick(cat)}
                                            className="p-3 bg-gray-100 hover:bg-gray-200 rounded-lg text-center transition-colors"
                                        >
                                            <div className="text-2xl mb-1">{cat.emoji}</div>
                                            <div className="text-xs text-gray-700">{cat.label}</div>
                                        </button>
                                    ))}
                                </div>
                            ) : (
                                <>
                                    {selectedCategory && (
                                        <button
                                            onClick={handleBackToCategories}
                                            className="flex items-center gap-1 text-sm text-gray-500 mb-2 hover:text-gray-700"
                                        >
                                            <ArrowLeft className="w-4 h-4" />
                                            Volver a categorías
                                        </button>
                                    )}
                                    
                                    {loadingFoods ? (
                                        <div className="text-center py-8 text-gray-500">Cargando...</div>
                                    ) : displayFoods.length === 0 ? (
                                        <div className="text-center py-8 text-gray-500">
                                            {isSearching ? 'No se encontraron alimentos' : 'No hay alimentos en esta categoría'}
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
                                                            onClick={() => handleFoodPreview(food)}
                                                            className="flex-1 flex items-center gap-2 p-2 rounded-lg text-left transition-colors hover:bg-gray-100"
                                                            data-testid={`food-item-${food.id || idx}`}
                                                        >
                                                            <span className="text-lg">{getEmoji(food.categorias)}</span>
                                                            <div className="flex-1 min-w-0">
                                                                <div className="text-sm text-black truncate">{food.nombre}</div>
                                                                <div className="text-xs text-gray-500">
                                                                    {food._cantidad_sugerida ? `${(food.por_unidad ?? food.unidades) && (food.peso_unidad || food.racion) > 0 ? `${Math.round(food._cantidad_sugerida / (food.peso_unidad || food.racion) * 2) / 2} ud` : `${food._cantidad_sugerida}g`} → ` : ''}
                                                                    P={food._macros_sugeridos?.P || Math.round(food.proteinas)}g
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
