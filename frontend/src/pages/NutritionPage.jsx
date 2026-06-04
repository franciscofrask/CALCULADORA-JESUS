import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { 
    ChevronLeft, ChevronRight,
    Save, Copy, ArrowUpRight, Calendar, FileDown
} from 'lucide-react';
import PreferencesSetup, { PREFERENCE_CATEGORIES } from '../components/nutrition/PreferencesSetup';
import BuildMealModal from '../components/nutrition/BuildMealModal';
import RepeatMealModal from '../components/nutrition/RepeatMealModal';
import CopyDietModal from '../components/nutrition/CopyDietModal';
import DaySummary from '../components/nutrition/DaySummary';
import ConfigSection from '../components/nutrition/ConfigSection';
import MealCard from '../components/nutrition/MealCard';
import { SearchFoodModal, MenuOptionsModal } from '../components/nutrition/SearchFoodModal';
import DietCalendar from '../components/nutrition/DietCalendar';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// 12EN12 Logo Component
const Logo12EN12 = () => (
    <div className="flex items-center text-xl font-bold tracking-tight">
        <span className="text-white">12EN12</span>
        <ArrowUpRight className="text-brand-orange w-5 h-5 -ml-0.5" strokeWidth={3} />
    </div>
);

// Food emojis for categories
const FOOD_EMOJIS = {
    '2': '🥩', '3': '🐟', '1': '🥚', '5': '🥛', '4': '💪',
    '7': '🌾', '8': '🍞', '21': '🍚', '22': '🍝', '9': '🥔',
    '10': '🫘', '11': '🍎', '13': '🥦', '17': '🫒', '17.2': '🥜',
    '16': '🥫', '24': '🥤', 'default': '🍽️'
};

const getFoodEmoji = (categorias) => {
    if (!categorias) return FOOD_EMOJIS.default;
    const mainCat = categorias.split(' | ')[0]?.split('.')[0];
    return FOOD_EMOJIS[mainCat] || FOOD_EMOJIS.default;
};


// Categories for Build Meal Modal - Step 1 (Proteínas) - Con prefixes para foods-sorted
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

const NutritionPage = () => {
    const { token } = useAuth();
    
    // Preferences state - for checking if user has configured preferences
    const [showPreferencesSetup, setShowPreferencesSetup] = useState(false);
    const [userPreferences, setUserPreferences] = useState([]);
    const [preferencesLoading, setPreferencesLoading] = useState(true);
    
    // Date & Config state
    const [currentDate, setCurrentDate] = useState(new Date().toISOString().split('T')[0]);
    const [tipoDia, setTipoDia] = useState('entrenamiento');
    const [numComidas, setNumComidas] = useState(4);
    const [momentoEntreno, setMomentoEntreno] = useState(1);
    const [opcionPeri, setOpcionPeri] = useState('intra_post');

    // Favorites state
    const [favorites, setFavorites] = useState(new Set());
    
    // Data state
    const [distribution, setDistribution] = useState(null);
    const [distribTargetsOverlay, setDistribTargetsOverlay] = useState(null);
    const [mealsData, setMealsData] = useState({});
    const [expandedMeals, setExpandedMeals] = useState({ C1: true });
    const [loading, setLoading] = useState(true);
    
    // Modal states
    const [addFoodModal, setAddFoodModal] = useState({ open: false, mealKey: null });
    const [menuOptionsModal, setMenuOptionsModal] = useState({ open: false, mealKey: null });
    const [copyModalOpen, setCopyModalOpen] = useState(false);
    const [copyDate, setCopyDate] = useState('');
    const [buildMealModal, setBuildMealModal] = useState({ open: false, mealKey: null });
    const [repeatMealModal, setRepeatMealModal] = useState({ open: false, mealKey: null });
    const [recentDiets, setRecentDiets] = useState([]);
    const [selectedDietForRepeat, setSelectedDietForRepeat] = useState(null);
    const [editingQuantity, setEditingQuantity] = useState({ mealKey: null, foodIndex: null });
    
    // Search state
    const [searchQuery, setSearchQuery] = useState('');
    const [searchCategory, setSearchCategory] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [searchLoading, setSearchLoading] = useState(false);
    
    // Menu options
    const [menuOptions, setMenuOptions] = useState([]);
    const [menuOptionsLoading, setMenuOptionsLoading] = useState(false);
    
    // Summary expanded state
    const [summaryExpanded, setSummaryExpanded] = useState(false);
    
    // Calendar state
    const [calendarOpen, setCalendarOpen] = useState(false);
    
    // PDF export state
    const [exportingPdf, setExportingPdf] = useState(false);

    // API helper
    const api = useCallback(async (endpoint, options = {}) => {
        const res = await fetch(`${API_URL}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
                ...options.headers
            }
        });
        if (!res.ok) {
            const error = await res.json().catch(() => ({ detail: 'Error de red' }));
            throw new Error(error.detail || 'Error');
        }
        return res.json();
    }, [token]);
    
    // Check user preferences on load
    useEffect(() => {
        const checkPreferences = async () => {
            try {
                const res = await api('/api/user/preferences');
                if (!res.has_preferences) {
                    setShowPreferencesSetup(true);
                } else {
                    setUserPreferences(res.food_preferences);
                }
            } catch (err) {
                console.error('Error checking preferences:', err);
            } finally {
                setPreferencesLoading(false);
            }
        };
        checkPreferences();
    }, [api]);

    // Load favorites on mount
    useEffect(() => {
        const loadFavorites = async () => {
            try {
                const res = await api('/api/favorites');
                setFavorites(new Set((res.favorites || []).map(String)));
            } catch (e) { /* ignore */ }
        };
        loadFavorites();
    }, [api]);

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
    
    // Handle preferences saved
    const handlePreferencesSaved = (preferences) => {
        setUserPreferences(preferences);
        setShowPreferencesSetup(false);
    };

    // Auto-detect day type from routine
    useEffect(() => {
        const detectDayType = async () => {
            try {
                const routine = await api('/api/routines/current');
                if (routine && routine.days) {
                    const dateObj = new Date(currentDate + 'T12:00:00');
                    const dayName = dateObj.toLocaleDateString('es-ES', { weekday: 'long' }).toLowerCase();
                    const dayData = routine.days.find(d => d.day.toLowerCase() === dayName);
                    if (dayData) {
                        setTipoDia(dayData.is_rest ? 'descanso' : 'entrenamiento');
                    }
                }
            } catch (err) {
                // No routine assigned, keep default
            }
        };
        detectDayType();
    }, [currentDate]); // eslint-disable-line

    // Export diet to PDF
    const exportPdf = async () => {
        setExportingPdf(true);
        try {
            const res = await fetch(`${API_URL}/api/diets/${currentDate}/pdf`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || 'Error generando PDF');
            }
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `dieta_jg12_${currentDate}.pdf`;
            a.click();
            URL.revokeObjectURL(url);
            toast.success('PDF descargado');
        } catch (err) {
            toast.error(err.message || 'Error exportando PDF');
        }
        setExportingPdf(false);
    };

    // Load distribution
    const loadDistribution = useCallback(async () => {
        try {
            const result = await api('/api/calculator/distribute', {
                method: 'POST',
                body: JSON.stringify({
                    tipo_dia: tipoDia,
                    num_comidas: numComidas,
                    momento_entreno: momentoEntreno,
                    opcion_peri: opcionPeri
                })
            });
            setDistribution(result);
        } catch (err) {
            console.error('Error loading distribution:', err);
        }
    }, [api, tipoDia, numComidas, momentoEntreno, opcionPeri]);

    // Load saved diet — returns distribution_targets if they were saved
    const loadDiet = useCallback(async (date) => {
        try {
            const diet = await api(`/api/diets/${date}`);
            if (diet.exists) {
                setTipoDia(diet.tipo_dia || 'entrenamiento');
                setNumComidas(diet.num_comidas || 4);
                setMomentoEntreno(diet.momento_entreno || 1);
                setOpcionPeri(diet.opcion_peri || 'intra_post');

                const updatedMeals = {};
                for (const [mealKey, mealData] of Object.entries(diet.comidas || {})) {
                    if (mealData.alimentos && mealData.alimentos.length > 0) {
                        const updatedFoods = await Promise.all(
                            mealData.alimentos.map(async (food) => {
                                if (food.macros_efectivos && food.macros_efectivos.P !== undefined) {
                                    return food;
                                }
                                try {
                                    const result = await api('/api/calculator/macros-efectivos', {
                                        method: 'POST',
                                        body: JSON.stringify({
                                            alimento_id: food.alimento_id,
                                            cantidad_g: food.cantidad_g,
                                            es_vegano: false
                                        })
                                    });
                                    return { ...food, macros_efectivos: result.efectivos, macros_brutos: result.brutos, que_cuenta: result.que_cuenta };
                                } catch { return food; }
                            })
                        );
                        updatedMeals[mealKey] = { alimentos: updatedFoods };
                    } else {
                        updatedMeals[mealKey] = mealData;
                    }
                }
                setMealsData(updatedMeals);
                return diet.distribution_targets || null;
            } else {
                setMealsData({});
                return null;
            }
        } catch (err) {
            console.error('Error loading diet:', err);
            setMealsData({});
            return null;
        }
    }, [api]);

    // Initial load
    useEffect(() => {
        const init = async () => {
            setLoading(true);
            setDistribTargetsOverlay(null); // Reset before loading new date
            const savedTargets = await loadDiet(currentDate);
            if (savedTargets) {
                setDistribTargetsOverlay(savedTargets);
            }
            await loadDistribution();
            setLoading(false);
        };
        init();
    }, [currentDate]); // eslint-disable-line

    // Reload distribution when config changes
    useEffect(() => {
        if (!loading) loadDistribution();
    }, [tipoDia, numComidas, momentoEntreno, opcionPeri]); // eslint-disable-line

    // Wrappers for user-initiated config changes
    const handleSetTipoDia = (v) => { setTipoDia(v); };
    const handleSetNumComidas = (v) => { setNumComidas(v); };
    const handleSetMomentoEntreno = (v) => { setMomentoEntreno(v); };
    const handleSetOpcionPeri = (v) => { setOpcionPeri(v); };

    // Search foods
    useEffect(() => {
        if (!addFoodModal.open) return;
        const timer = setTimeout(async () => {
            setSearchLoading(true);
            try {
                const params = new URLSearchParams();
                if (searchQuery) params.set('q', searchQuery);
                if (searchCategory) params.set('category', searchCategory);
                const mealKey = addFoodModal.mealKey;
                if (mealKey === 'Intra' || mealKey === 'Post') {
                    params.set('tipo_comida', mealKey.toLowerCase());
                }
                params.set('limit', '30');
                const result = await api(`/api/calculator/search?${params}`);
                setSearchResults(result.alimentos || []);
            } catch (err) { console.error('Search error:', err); }
            setSearchLoading(false);
        }, 300);
        return () => clearTimeout(timer);
    }, [searchQuery, searchCategory, addFoodModal.open, addFoodModal.mealKey, api]);

    // Navigation
    const changeDate = (days) => {
        const d = new Date(currentDate);
        d.setDate(d.getDate() + days);
        setCurrentDate(d.toISOString().split('T')[0]);
    };

    const formatDate = (dateStr) => {
        const d = new Date(dateStr);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const dateOnly = new Date(d);
        dateOnly.setHours(0, 0, 0, 0);
        if (dateOnly.getTime() === today.getTime()) return 'Hoy';
        return d.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' });
    };

    // Meal order based on config
    const getMealOrder = () => {
        const baseMeals = numComidas === 3 ? ['C1', 'C2', 'C3'] : ['C1', 'C2', 'C3', 'C4'];
        if (tipoDia === 'descanso') return baseMeals;
        const periMeals = opcionPeri === 'intra_post' ? ['Intra', 'Post'] :
                         opcionPeri === 'solo_post' ? ['Post'] :
                         opcionPeri === 'solo_intra' ? ['Intra'] : [];
        if (periMeals.length === 0) return baseMeals;
        const result = [...baseMeals];
        result.splice(momentoEntreno, 0, ...periMeals);
        return result;
    };

    // Calculations
    const calculateMealMacros = (mealKey) => {
        const foods = mealsData[mealKey]?.alimentos || [];
        return foods.reduce((total, f) => ({
            P: total.P + (f.macros_efectivos?.P || 0),
            H: total.H + (f.macros_efectivos?.H || 0),
            G: total.G + (f.macros_efectivos?.G || 0)
        }), { P: 0, H: 0, G: 0 });
    };

    const calculateDayMacros = () => {
        return getMealOrder().reduce((total, key) => {
            const m = calculateMealMacros(key);
            return { P: total.P + m.P, H: total.H + m.H, G: total.G + m.G };
        }, { P: 0, H: 0, G: 0 });
    };

    const getMealTarget = (mealKey) => {
        // Volcado overlay takes absolute precedence
        if (distribTargetsOverlay?.[mealKey]) return distribTargetsOverlay[mealKey];
        
        if (!distribution) return { P: 0, H: 0, G: 0 };
        if (mealKey === 'Intra' || mealKey === 'Post') {
            return distribution.periworkout?.[mealKey] || { P: 0, H: 0, G: 0 };
        }
        return distribution.comidas?.[mealKey] || { P: 0, H: 0, G: 0 };
    };

    const getMealRemaining = (mealKey) => {
        const target = getMealTarget(mealKey);
        const served = calculateMealMacros(mealKey);
        return {
            P: Math.max(0, target.P - served.P),
            H: Math.max(0, target.H - served.H),
            G: Math.max(0, target.G - served.G)
        };
    };

    const getMealStatus = (mealKey) => {
        const target = getMealTarget(mealKey);
        const served = calculateMealMacros(mealKey);
        const foods = mealsData[mealKey]?.alimentos || [];
        if (foods.length === 0) return 'empty';
        const margin = 4;
        const pOk = Math.abs(target.P - served.P) <= margin;
        const hOk = Math.abs(target.H - served.H) <= margin;
        const gOk = mealKey === 'Intra' || mealKey === 'Post' || Math.abs(target.G - served.G) <= margin;
        if (pOk && hOk && gOk) return 'cuadrada';
        if (served.P > target.P + margin || served.H > target.H + margin || served.G > target.G + margin) return 'sobra';
        return 'falta';
    };

    // Get quantity increment based on food category
    // REGLA: Para alimentos con unidades, incrementar por 1 unidad (= racion gramos)
    // Para alimentos sin unidades, incrementar por categoría
    const getQuantityIncrement = (food) => {
        const cat = food.categorias?.split(' | ')[0]?.split('.')[0] || '';
        const subCat = food.categorias?.split(' | ')[0] || '';
        const racion = food.racion || 100;
        
        // Alimentos con unidades: incrementar 1 unidad = racion gramos
        if (food.unidades) return racion;
        
        // Verduras (cat 13): ±50g
        if (cat === '13') return 50;
        
        // Bebidas vegetales (cat 24): ±50g
        if (cat === '24') return 50;
        
        // Salsas zero (cat 16.1): ±5g
        if (subCat.startsWith('16.1')) return 5;
        
        // TODO lo demás: ±1g
        return 1;
    };

    // Format quantity for display: "2 ud" for unit foods, "120g" for gram foods
    const formatFoodQuantity = (food) => {
        if (!food) return '0g';
        const qty = food.cantidad_g || 0;
        const racion = food.racion || 100;
        if (food.unidades && racion > 0) {
            const units = qty / racion;
            const rounded = Math.round(units * 2) / 2; // round to 0.5
            return `${rounded % 1 === 0 ? rounded.toFixed(0) : rounded.toFixed(1)} ud`;
        }
        return `${Math.round(qty)}g`;
    };

    // Food operations
    const handleAddFood = async (food) => {
        const mealKey = addFoodModal.mealKey;
        const alreadyInMeal = (mealsData[mealKey]?.alimentos || []).some(f => f.alimento_id === food.id);
        if (alreadyInMeal) {
            toast.error(`${food.nombre} ya está en esta comida — ajusta su cantidad directamente.`);
            return;
        }
        const remaining = getMealRemaining(mealKey);
        try {
            const result = await api('/api/calculator/adjust', {
                method: 'POST',
                body: JSON.stringify({
                    alimento_id: food.id,
                    macros_restantes: remaining,
                    es_vegano: false
                })
            });

            // Free foods (all zeros: konjac, salsas zero, verduras libres) always pass
            const ef = result.macros_efectivos || {};
            const isFreeFood = !ef.P && !ef.H && !ef.G;
            if (!isFreeFood) {
                const mealStatus = getMealStatus(mealKey);
                if (mealStatus === 'cuadrada' || mealStatus === 'sobra') {
                    toast.error('Esta comida ya está completa — no hay espacio para más alimentos.');
                    return;
                }
                const target = getMealTarget(mealKey);
                const served = calculateMealMacros(mealKey);
                const margin = mealKey === 'Intra' ? 2 : 4;
                if ((ef.P > 0 && served.P + ef.P > target.P + margin) ||
                    (ef.H > 0 && served.H + ef.H > target.H + margin) ||
                    (ef.G > 0 && served.G + ef.G > target.G + margin)) {
                    toast.error(`${food.nombre} no cabe — superaría los macros de esta comida.`);
                    return;
                }
            }

            const newFood = {
                alimento_id: food.id,
                nombre: food.nombre,
                cantidad_g: result.cantidad_g,
                macros_efectivos: result.macros_efectivos,
                macros_brutos: result.macros_brutos,
                que_cuenta: result.que_cuenta,
                categorias: food.categorias,
                racion: food.racion,
                unidades: food.unidades || false
            };
            setMealsData(prev => ({
                ...prev,
                [mealKey]: { alimentos: [...(prev[mealKey]?.alimentos || []), newFood] }
            }));
            setAddFoodModal({ open: false, mealKey: null });
            setSearchQuery('');
            setSearchCategory('');
            toast.success(`${food.nombre} añadido`);
        } catch (err) {
            toast.error('Error añadiendo alimento');
        }
    };

    const updateFoodQuantity = async (mealKey, foodIndex, delta) => {
        const foods = [...(mealsData[mealKey]?.alimentos || [])];
        const food = foods[foodIndex];
        const increment = delta !== null ? delta : getQuantityIncrement(food);
        const newQuantity = Math.max(1, food.cantidad_g + (delta !== null ? delta : increment));
        const isIncreasing = newQuantity > food.cantidad_g;
        try {
            const result = await api('/api/calculator/macros-efectivos', {
                method: 'POST',
                body: JSON.stringify({ alimento_id: food.alimento_id, cantidad_g: newQuantity, es_vegano: false })
            });
            if (isIncreasing) {
                const target = getMealTarget(mealKey);
                const margin = mealKey === 'Intra' ? 2 : 4;
                const ef = result.efectivos || {};
                const otherP = foods.filter((_, i) => i !== foodIndex).reduce((s, f) => s + (f.macros_efectivos?.P || 0), 0);
                const otherH = foods.filter((_, i) => i !== foodIndex).reduce((s, f) => s + (f.macros_efectivos?.H || 0), 0);
                const otherG = foods.filter((_, i) => i !== foodIndex).reduce((s, f) => s + (f.macros_efectivos?.G || 0), 0);
                if ((ef.P > 0 && otherP + ef.P > target.P + margin) ||
                    (ef.H > 0 && otherH + ef.H > target.H + margin) ||
                    (ef.G > 0 && otherG + ef.G > target.G + margin)) {
                    toast.error('No puedes aumentar más — superaría los macros objetivo.');
                    return;
                }
            }
            foods[foodIndex] = { ...food, cantidad_g: newQuantity, macros_efectivos: result.efectivos, macros_brutos: result.brutos, que_cuenta: result.que_cuenta };
            setMealsData(prev => ({ ...prev, [mealKey]: { alimentos: foods } }));
        } catch (err) { console.error('Error updating quantity:', err); }
    };

    const updateFoodQuantityDirect = async (mealKey, foodIndex, newQuantity) => {
        const foods = [...(mealsData[mealKey]?.alimentos || [])];
        const food = foods[foodIndex];
        const quantity = Math.max(1, parseInt(newQuantity) || 1);
        const isIncreasing = quantity > food.cantidad_g;
        try {
            const result = await api('/api/calculator/macros-efectivos', {
                method: 'POST',
                body: JSON.stringify({ alimento_id: food.alimento_id, cantidad_g: quantity, es_vegano: false })
            });
            if (isIncreasing) {
                const target = getMealTarget(mealKey);
                const margin = mealKey === 'Intra' ? 2 : 4;
                const ef = result.efectivos || {};
                const otherP = foods.filter((_, i) => i !== foodIndex).reduce((s, f) => s + (f.macros_efectivos?.P || 0), 0);
                const otherH = foods.filter((_, i) => i !== foodIndex).reduce((s, f) => s + (f.macros_efectivos?.H || 0), 0);
                const otherG = foods.filter((_, i) => i !== foodIndex).reduce((s, f) => s + (f.macros_efectivos?.G || 0), 0);
                if ((ef.P > 0 && otherP + ef.P > target.P + margin) ||
                    (ef.H > 0 && otherH + ef.H > target.H + margin) ||
                    (ef.G > 0 && otherG + ef.G > target.G + margin)) {
                    toast.error('Cantidad demasiado alta — superaría los macros objetivo.');
                    setEditingQuantity({ mealKey: null, foodIndex: null });
                    return;
                }
            }
            foods[foodIndex] = { ...food, cantidad_g: quantity, macros_efectivos: result.efectivos, macros_brutos: result.brutos, que_cuenta: result.que_cuenta };
            setMealsData(prev => ({ ...prev, [mealKey]: { alimentos: foods } }));
        } catch (err) { console.error('Error updating quantity:', err); }
        setEditingQuantity({ mealKey: null, foodIndex: null });
    };

    const removeFood = (mealKey, foodIndex) => {
        setMealsData(prev => ({
            ...prev,
            [mealKey]: { alimentos: (prev[mealKey]?.alimentos || []).filter((_, i) => i !== foodIndex) }
        }));
    };

    const clearMeal = (mealKey) => {
        if (window.confirm(`¿Vaciar todos los ingredientes de ${mealInfo[mealKey].name}?`)) {
            setMealsData(prev => ({
                ...prev,
                [mealKey]: { alimentos: [] }
            }));
            toast.success('Comida vaciada');
        }
    };

    // Repeat from another day
    const loadRecentDiets = async () => {
        try {
            const result = await api('/api/diets/recent?limit=14');
            setRecentDiets(result.diets || []);
        } catch (err) {
            console.error('Error loading recent diets:', err);
            setRecentDiets([]);
        }
    };

    const openRepeatModal = async (mealKey) => {
        setRepeatMealModal({ open: true, mealKey });
        setSelectedDietForRepeat(null);
        await loadRecentDiets();
    };

    const copyMealFromDay = async (sourceMealKey) => {
        const targetMealKey = repeatMealModal.mealKey;
        const sourceDiet = selectedDietForRepeat;
        
        if (!sourceDiet || !sourceDiet.comidas || !sourceDiet.comidas[sourceMealKey]) {
            toast.error('No hay alimentos en esa comida');
            return;
        }
        
        const sourceAlimentos = sourceDiet.comidas[sourceMealKey].alimentos || [];
        if (sourceAlimentos.length === 0) {
            toast.error('Esa comida está vacía');
            return;
        }
        
        // Get target macros and source total macros
        const targetMacros = getMealTarget(targetMealKey);
        const sourceMacros = sourceAlimentos.reduce((acc, a) => ({
            P: acc.P + (a.macros_efectivos?.P || 0),
            H: acc.H + (a.macros_efectivos?.H || 0),
            G: acc.G + (a.macros_efectivos?.G || 0)
        }), { P: 0, H: 0, G: 0 });
        
        // Calculate scaling factor based on protein (primary macro)
        const scaleFactor = sourceMacros.P > 0 ? targetMacros.P / sourceMacros.P : 1;
        
        // Scale and recalculate each food
        const scaledFoods = [];
        for (const food of sourceAlimentos) {
            const scaledQuantity = Math.round(food.cantidad_g * scaleFactor);
            try {
                const result = await api('/api/calculator/macros-efectivos', {
                    method: 'POST',
                    body: JSON.stringify({
                        alimento_id: food.alimento_id,
                        cantidad_g: scaledQuantity,
                        es_vegano: false
                    })
                });
                scaledFoods.push({
                    ...food,
                    cantidad_g: scaledQuantity,
                    macros_efectivos: result.efectivos,
                    macros_brutos: result.brutos,
                    que_cuenta: result.que_cuenta
                });
            } catch (err) {
                // If recalc fails, use original scaled estimate
                scaledFoods.push({
                    ...food,
                    cantidad_g: scaledQuantity,
                    macros_efectivos: {
                        P: (food.macros_efectivos?.P || 0) * scaleFactor,
                        H: (food.macros_efectivos?.H || 0) * scaleFactor,
                        G: (food.macros_efectivos?.G || 0) * scaleFactor
                    }
                });
            }
        }
        
        setMealsData(prev => ({
            ...prev,
            [targetMealKey]: { alimentos: scaledFoods }
        }));
        
        setRepeatMealModal({ open: false, mealKey: null });
        setSelectedDietForRepeat(null);
        toast.success(`Copiada ${mealInfo[sourceMealKey]?.name || sourceMealKey} del ${formatDate(sourceDiet.fecha)}`);
    };

    // Menu options
    const loadMenuOptions = async (mealKey) => {
        const target = getMealTarget(mealKey);
        const momentoMap = { 'C1': 'desayuno', 'C2': 'comida', 'C3': numComidas === 3 ? 'cena' : 'merienda', 'C4': 'cena' };
        setMenuOptionsLoading(true);
        setMenuOptionsModal({ open: true, mealKey });
        try {
            const result = await api('/api/calculator/menu-options', {
                method: 'POST',
                body: JSON.stringify({
                    momento: momentoMap[mealKey] || 'comida',
                    macros_objetivo: { P: target.P, H: target.H, G: target.G },
                    es_vegano: false,
                    excluir_proteinas: []
                })
            });
            setMenuOptions(result.opciones || []);
        } catch (err) {
            toast.error('Error cargando opciones');
            setMenuOptions([]);
        }
        setMenuOptionsLoading(false);
    };

    const applyMenuOption = async (option) => {
        const mealKey = menuOptionsModal.mealKey;
        const foods = option.items.map(item => ({
            alimento_id: item.alimento_id,
            nombre: item.nombre,
            cantidad_g: item.cantidad_g,
            macros_efectivos: item.macros_efectivos,
            macros_brutos: item.macros_efectivos,
            que_cuenta: { P: true, H: true, G: true }
        }));
        setMealsData(prev => ({ ...prev, [mealKey]: { alimentos: foods } }));
        setMenuOptionsModal({ open: false, mealKey: null });
        toast.success(`Menú "${option.nombre}" aplicado`);
    };

    // Save & Copy
    const saveDiet = async () => {
        try {
            await api('/api/diets', {
                method: 'POST',
                body: JSON.stringify({
                    fecha: currentDate,
                    tipo_dia: tipoDia,
                    num_comidas: numComidas,
                    momento_entreno: momentoEntreno,
                    opcion_peri: opcionPeri,
                    comidas: mealsData,
                    macros_snapshot: distribution?.resumen,
                    distribution_targets: distribTargetsOverlay || null,
                    is_cuadrado: getDayStatus() === 'cuadrado'
                })
            });
            toast.success('Dieta guardada');
        } catch (err) { toast.error('Error guardando dieta'); }
    };

    const copyDiet = async () => {
        if (!copyDate) { toast.error('Selecciona una fecha'); return; }
        try {
            await api('/api/diets/copy', {
                method: 'POST',
                body: JSON.stringify({ fecha_origen: currentDate, fecha_destino: copyDate })
            });
            toast.success(`Copiada a ${formatDate(copyDate)}`);
            setCopyModalOpen(false);
            setCopyDate('');
        } catch (err) { toast.error('Error copiando dieta'); }
    };

    // Day summary
    const dayMacros = calculateDayMacros();
    const dayTarget = distribution?.resumen || { P_total: 0, H_total: 0, G_total: 0, kcal_total: 0 };
    const remainingDay = {
        P: Math.max(0, Math.round((dayTarget.P_total || 0) - dayMacros.P)),
        H: Math.max(0, Math.round((dayTarget.H_total || 0) - dayMacros.H)),
        G: Math.max(0, Math.round((dayTarget.G_total || 0) - dayMacros.G)),
    };

    const handleVolcarMacros = () => {
        const regularMeals = getMealOrder().filter(k => !['Intra', 'Post'].includes(k));
        const lastMeal = regularMeals[regularMeals.length - 1];
        if (!lastMeal) return;

        // Sum macros of ALL meals except the last one (including peri)
        const otherServed = getMealOrder()
            .filter(k => k !== lastMeal)
            .reduce((acc, k) => {
                const m = calculateMealMacros(k);
                return { P: acc.P + m.P, H: acc.H + m.H, G: acc.G + m.G };
            }, { P: 0, H: 0, G: 0 });

        const targetForLastMeal = {
            P: Math.max(0, Math.round((dayTarget.P_total || 0) - otherServed.P)),
            H: Math.max(0, Math.round((dayTarget.H_total || 0) - otherServed.H)),
            G: Math.max(0, Math.round((dayTarget.G_total || 0) - otherServed.G)),
        };

        setDistribTargetsOverlay(prev => ({ ...(prev || {}), [lastMeal]: targetForLastMeal }));
        toast.success(`Macros volcados a ${mealInfo[lastMeal]?.name}`);
    };
    const dayKcal = dayMacros.P * 4 + dayMacros.H * 4 + dayMacros.G * 9;
    const targetKcal = dayTarget.kcal_total || 0;
    
    // Periworkout totals from distribution
    const periTarget = distribution?.periworkout || {};
    const intraTarget = periTarget.Intra || { P: 0, H: 0 };
    const postTarget = periTarget.Post || { P: 0, H: 0 };
    const totalPeriP = intraTarget.P + postTarget.P;
    const totalPeriH = intraTarget.H + postTarget.H;
    const servedPeriP = (calculateMealMacros('Intra').P || 0) + (calculateMealMacros('Post').P || 0);
    const servedPeriH = (calculateMealMacros('Intra').H || 0) + (calculateMealMacros('Post').H || 0);

    // Day status calculation
    const getDayStatus = () => {
        const margin = 4;
        const pDiff = dayMacros.P - (dayTarget.P_total || 0);
        const hDiff = dayMacros.H - (dayTarget.H_total || 0);
        const gDiff = dayMacros.G - (dayTarget.G_total || 0);
        
        const pOver = pDiff > margin;
        const hOver = hDiff > margin;
        const gOver = gDiff > margin;
        
        if (pOver || hOver || gOver) return 'sobra';
        
        const pOk = Math.abs(pDiff) <= margin;
        const hOk = Math.abs(hDiff) <= margin;
        const gOk = Math.abs(gDiff) <= margin;
        
        if (pOk && hOk && gOk) return 'cuadrado';
        return 'falta';
    };

    // Meal info
    const mealInfo = {
        C1: { name: 'Comida 1', shortName: 'C1', emoji: '🌅' },
        C2: { name: 'Comida 2', shortName: 'C2', emoji: '☀️' },
        C3: { name: numComidas === 3 ? 'Comida 3' : 'Comida 3', shortName: 'C3', emoji: numComidas === 3 ? '🌙' : '🌤️' },
        C4: { name: 'Comida 4', shortName: 'C4', emoji: '🌙' },
        Intra: { name: 'Intra-entreno', shortName: 'Intra', emoji: '⚡' },
        Post: { name: 'Post-entreno', shortName: 'Post', emoji: '💪' }
    };

    // ===== COMPONENTS =====

    // Progress Bar Component
    // ===== LOADING STATE =====
    if (loading) {
        return (
            <div className="min-h-screen bg-bg-page flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-orange border-t-transparent" />
                    <p className="text-gray-500 text-sm">Cargando...</p>
                </div>
            </div>
        );
    }

    // ===== SHOW PREFERENCES SETUP IF NEEDED =====
    if (preferencesLoading) {
        return (
            <div className="min-h-screen bg-bg-dark flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-brand-orange border-t-transparent" />
            </div>
        );
    }
    
    if (showPreferencesSetup) {
        return (
            <PreferencesSetup 
                api={api}
                initialPreferences={userPreferences}
                onSave={handlePreferencesSaved}
                isEditMode={userPreferences.length > 0}
            />
        );
    }

    // ===== MAIN RENDER =====
    return (
        <div 
            className="min-h-screen pb-32 relative"
            style={{
                backgroundImage: `url('/gohan-light.png')`,
                backgroundSize: 'contain',
                backgroundPosition: 'center',
                backgroundRepeat: 'no-repeat',
                backgroundAttachment: 'fixed',
                opacity: 1
            }}
            data-testid="nutrition-page"
        >
            {/* Background overlay */}
            <div className="absolute inset-0 bg-bg-page/[0.97]" />
            
            {/* Content */}
            <div className="relative z-10">
                {/* Header */}
                <div className="bg-bg-dark sticky top-0 z-40">
                    <div className="max-w-lg mx-auto px-4 py-3">
                        <div className="flex items-center justify-between">
                            <Logo12EN12 />
                            <span className="text-gray-400 text-sm">Nutrición</span>
                        </div>
                    </div>
                </div>

                {/* Sticky Summary */}
                <DaySummary
                    tipoDia={tipoDia}
                    summaryExpanded={summaryExpanded}
                    setSummaryExpanded={setSummaryExpanded}
                    dayMacros={dayMacros}
                    dayTarget={dayTarget}
                    servedPeriP={servedPeriP}
                    servedPeriH={servedPeriH}
                    totalPeriP={totalPeriP}
                    totalPeriH={totalPeriH}
                    opcionPeri={opcionPeri}
                    mealOrder={getMealOrder()}
                    mealInfo={mealInfo}
                    calculateMealMacros={calculateMealMacros}
                    getMealStatus={getMealStatus}
                    getDayStatus={getDayStatus}
                />

                <div className="max-w-lg mx-auto px-4 py-4">
                    {/* Date & Day type */}
                    <Card className="bg-white shadow-md rounded-2xl mb-4">
                        <CardContent className="p-4">
                            {/* Date selector */}
                            <div className="flex items-center justify-between mb-4">
                                <Button variant="ghost" size="icon" onClick={() => changeDate(-1)}>
                                    <ChevronLeft className="w-5 h-5" />
                                </Button>
                                <button
                                    className="flex items-center gap-2 hover:text-brand-orange transition-colors"
                                    onClick={() => setCalendarOpen(true)}
                                    data-testid="open-calendar-btn"
                                >
                                    <Calendar className="w-4 h-4 text-brand-orange" />
                                    <span className="font-bold text-gray-900">{formatDate(currentDate)}</span>
                                </button>
                                <Button variant="ghost" size="icon" onClick={() => changeDate(1)}>
                                    <ChevronRight className="w-5 h-5" />
                                </Button>
                            </div>
                            
                            {/* Day type toggle */}
                            <div className="flex gap-2">
                                <button 
                                    className={`flex-1 py-2 px-3 rounded-full text-sm font-semibold transition-all ${
                                        tipoDia === 'entrenamiento' 
                                            ? 'bg-brand-orange text-white shadow-md' 
                                            : 'bg-gray-100 text-gray-600'
                                    }`}
                                    onClick={() => handleSetTipoDia('entrenamiento')}
                                    data-testid="tipo-dia-entrenamiento"
                                >
                                    Día de entrenamiento
                                </button>
                                <button
                                    className={`flex-1 py-2 px-3 rounded-full text-sm font-semibold transition-all ${
                                        tipoDia === 'descanso'
                                            ? 'bg-gray-800 text-white shadow-md'
                                            : 'bg-gray-100 text-gray-600'
                                    }`}
                                    onClick={() => handleSetTipoDia('descanso')}
                                    data-testid="tipo-dia-descanso"
                                >
                                    Día de descanso
                                </button>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Config Section */}
                    <ConfigSection
                        tipoDia={tipoDia}
                        numComidas={numComidas}
                        setNumComidas={handleSetNumComidas}
                        momentoEntreno={momentoEntreno}
                        setMomentoEntreno={handleSetMomentoEntreno}
                        opcionPeri={opcionPeri}
                        setOpcionPeri={handleSetOpcionPeri}
                    />

                    {/* Volcado de macros banner */}
                    {distribution && getDayStatus() === 'falta' && (remainingDay.P > 4 || remainingDay.H > 4 || remainingDay.G > 4) && (
                        <div className="bg-orange-50 border border-brand-orange/30 rounded-2xl p-4 mb-4 flex items-center justify-between gap-3">
                            <div>
                                <p className="text-xs font-bold text-brand-orange uppercase tracking-wider mb-1">Macros pendientes hoy</p>
                                <p className="text-sm text-gray-700">
                                    {remainingDay.P > 0 && <span className="font-bold text-blue-600">{remainingDay.P}g P </span>}
                                    {remainingDay.H > 0 && <span className="font-bold text-amber-500">{remainingDay.H}g H </span>}
                                    {remainingDay.G > 0 && <span className="font-bold text-red-500">{remainingDay.G}g G</span>}
                                </p>
                            </div>
                            <Button
                                size="sm"
                                className="bg-brand-orange hover:bg-brand-orange/90 text-white rounded-full font-bold shrink-0"
                                onClick={handleVolcarMacros}
                            >
                                Volcar a {mealInfo[getMealOrder().filter(k => !['Intra','Post'].includes(k)).slice(-1)[0]]?.name || 'última comida'}
                            </Button>
                        </div>
                    )}

                    {/* Meals */}
                    <div className="space-y-3 mb-4">
                        {getMealOrder().map(mealKey => (
                            <MealCard
                                key={mealKey}
                                mealKey={mealKey}
                                mealInfo={mealInfo}
                                mealsData={mealsData}
                                expandedMeals={expandedMeals}
                                setExpandedMeals={setExpandedMeals}
                                getMealTarget={getMealTarget}
                                calculateMealMacros={calculateMealMacros}
                                getMealStatus={getMealStatus}
                                loadMenuOptions={loadMenuOptions}
                                setBuildMealModal={setBuildMealModal}
                                openRepeatModal={openRepeatModal}
                                removeFood={removeFood}
                                updateFoodQuantity={updateFoodQuantity}
                                updateFoodQuantityDirect={updateFoodQuantityDirect}
                                editingQuantity={editingQuantity}
                                setEditingQuantity={setEditingQuantity}
                                getQuantityIncrement={getQuantityIncrement}
                                clearMeal={clearMeal}
                                getFoodEmoji={getFoodEmoji}
                                formatFoodQuantity={formatFoodQuantity}
                            />
                        ))}
                    </div>

                    {/* Action buttons */}
                    <div className="flex gap-2">
                        <Button 
                            className="flex-1 h-12 bg-black hover:bg-gray-900 text-white rounded-full font-bold"
                            onClick={saveDiet}
                            data-testid="save-diet-btn"
                        >
                            <Save className="w-5 h-5 mr-2" /> Guardar día
                        </Button>
                        <Button
                            variant="outline"
                            className="h-12 w-12 rounded-full"
                            onClick={exportPdf}
                            disabled={exportingPdf}
                            data-testid="export-pdf-btn"
                            title="Exportar PDF"
                        >
                            {exportingPdf
                                ? <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
                                : <FileDown className="w-5 h-5" />
                            }
                        </Button>
                        <Button variant="outline" className="h-12 w-12 rounded-full" onClick={() => setCopyModalOpen(true)}>
                            <Copy className="w-5 h-5" />
                        </Button>
                    </div>
                </div>
            </div>

            {/* Search Food Modal */}
            <SearchFoodModal
                open={addFoodModal.open}
                mealKey={addFoodModal.mealKey}
                onClose={() => setAddFoodModal({ open: false, mealKey: null })}
                searchQuery={searchQuery}
                setSearchQuery={setSearchQuery}
                searchCategory={searchCategory}
                setSearchCategory={setSearchCategory}
                searchLoading={searchLoading}
                searchResults={searchResults}
                onAddFood={handleAddFood}
                getFoodEmoji={getFoodEmoji}
                favorites={favorites}
                onToggleFavorite={toggleFavorite}
            />

            {/* Menu Options Modal */}
            <MenuOptionsModal
                open={menuOptionsModal.open}
                mealKey={menuOptionsModal.mealKey}
                onClose={() => setMenuOptionsModal({ open: false, mealKey: null })}
                mealInfo={mealInfo}
                menuOptionsLoading={menuOptionsLoading}
                menuOptions={menuOptions}
                onApplyOption={applyMenuOption}
            />

            {/* Build Meal Modal */}
            <BuildMealModal 
                open={buildMealModal.open}
                mealKey={buildMealModal.mealKey}
                mode={buildMealModal.mode || 'normal'}
                onClose={() => setBuildMealModal({ open: false, mealKey: null })}
                getMealTarget={getMealTarget}
                mealInfo={mealInfo}
                api={api}
                tipoDia={tipoDia}
                mealsData={mealsData}
                setMealsData={setMealsData}
                getFoodEmoji={getFoodEmoji}
                userPreferences={userPreferences}
            />

            {/* Repeat Meal Modal */}
            <RepeatMealModal
                open={repeatMealModal.open}
                mealKey={repeatMealModal.mealKey}
                onClose={() => {
                    setRepeatMealModal({ open: false, mealKey: null });
                    setSelectedDietForRepeat(null);
                }}
                recentDiets={recentDiets}
                mealInfo={mealInfo}
                formatDate={formatDate}
                onCopyMeal={(sourceMealKey, sourceDiet) => {
                    setSelectedDietForRepeat(sourceDiet);
                    copyMealFromDay(sourceMealKey);
                }}
            />

            {/* Copy Diet Modal */}
            <CopyDietModal
                open={copyModalOpen}
                onClose={() => setCopyModalOpen(false)}
                copyDate={copyDate}
                setCopyDate={setCopyDate}
                onCopy={copyDiet}
                currentDateFormatted={formatDate(currentDate)}
            />

            {/* Diet Calendar Modal */}
            <DietCalendar
                open={calendarOpen}
                onClose={() => setCalendarOpen(false)}
                onSelectDate={(date) => setCurrentDate(date)}
                api={api}
            />
        </div>
    );
};

export default NutritionPage;
