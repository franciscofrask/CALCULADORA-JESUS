import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../components/ui/collapsible';
import { toast } from 'sonner';
import { 
    ChevronLeft, ChevronRight, Settings, Plus, Trash2, 
    Minus, Save, Copy, Check, ChevronDown, ChevronUp,
    Search, X, Zap, Wrench, RotateCcw, ArrowRight
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Emoji icons for food categories
const FOOD_EMOJIS = {
    '2': '🍗', // Carnes
    '3': '🐟', // Pescados
    '1': '🥚', // Huevos
    '5': '🥛', // Lácteos
    '4': '💪', // Proteína polvo
    '7': '🌾', // Cereales
    '8': '🍞', // Panes
    '21': '🍚', // Arroces
    '22': '🍝', // Pasta
    '9': '🥔', // Tubérculos
    '10': '🫘', // Legumbres
    '11': '🍎', // Fruta
    '13': '🥦', // Verduras
    '17': '🫒', // Grasas
    '17.2': '🥜', // Frutos secos
    '16': '🥫', // Salsas
    '24': '🥤', // Bebidas
    'default': '🍽️'
};

// Get emoji for food based on category
const getFoodEmoji = (categorias) => {
    if (!categorias) return FOOD_EMOJIS.default;
    const mainCat = categorias.split(' | ')[0]?.split('.')[0];
    return FOOD_EMOJIS[mainCat] || FOOD_EMOJIS.default;
};

// Category chips for search
const CATEGORY_CHIPS = [
    { label: 'Todas', value: '', emoji: '🍽️' },
    { label: 'Carnes', value: '2', emoji: '🍗' },
    { label: 'Pescados', value: '3', emoji: '🐟' },
    { label: 'Huevos', value: '1', emoji: '🥚' },
    { label: 'Lácteos', value: '5', emoji: '🥛' },
    { label: 'Proteína', value: '4', emoji: '💪' },
    { label: 'Cereales', value: '7', emoji: '🌾' },
    { label: 'Arroces', value: '21', emoji: '🍚' },
    { label: 'Pasta', value: '22', emoji: '🍝' },
    { label: 'Tubérculos', value: '9', emoji: '🥔' },
    { label: 'Verduras', value: '13', emoji: '🥦' },
    { label: 'Fruta', value: '11', emoji: '🍎' },
    { label: 'Grasas', value: '17', emoji: '🫒' },
    { label: 'F. Secos', value: '17.2', emoji: '🥜' },
];

// Builder steps for "Construirlo yo"
const BUILDER_STEPS = [
    { id: 'proteina', label: 'Elige tu proteína', emoji: '🍗', categories: ['2', '3', '1', '4', '5'] },
    { id: 'carbohidrato', label: 'Elige acompañamiento', emoji: '🍚', categories: ['7', '8', '21', '22', '9', '10', '11'] },
    { id: 'verdura', label: '¿Verduras?', emoji: '🥦', categories: ['13'], optional: true },
    { id: 'grasa', label: 'Ajustar grasas', emoji: '🫒', categories: ['17', '17.2'], optional: true }
];

const NutritionPage = () => {
    const { token } = useAuth();
    
    // Date state
    const [currentDate, setCurrentDate] = useState(new Date().toISOString().split('T')[0]);
    
    // Config state
    const [tipoDia, setTipoDia] = useState('entrenamiento');
    const [numComidas, setNumComidas] = useState(4);
    const [momentoEntreno, setMomentoEntreno] = useState(1);
    const [opcionPeri, setOpcionPeri] = useState('intra_post');
    const [configOpen, setConfigOpen] = useState(false);
    
    // Distribution from backend
    const [distribution, setDistribution] = useState(null);
    
    // Meals data
    const [mealsData, setMealsData] = useState({});
    
    // UI state
    const [expandedMeals, setExpandedMeals] = useState({ C1: true });
    const [loading, setLoading] = useState(true);
    
    // Modal states
    const [addFoodModal, setAddFoodModal] = useState({ open: false, mealKey: null });
    const [menuOptionsModal, setMenuOptionsModal] = useState({ open: false, mealKey: null });
    const [builderModal, setBuilderModal] = useState({ open: false, mealKey: null, step: 0, foods: [] });
    const [copyModalOpen, setCopyModalOpen] = useState(false);
    const [copyDate, setCopyDate] = useState('');
    
    // Search state
    const [searchQuery, setSearchQuery] = useState('');
    const [searchCategory, setSearchCategory] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [searchLoading, setSearchLoading] = useState(false);
    
    // Menu options state
    const [menuOptions, setMenuOptions] = useState([]);
    const [menuOptionsLoading, setMenuOptionsLoading] = useState(false);

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

    // Load distribution from backend
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
            toast.error('Error cargando distribución');
        }
    }, [api, tipoDia, numComidas, momentoEntreno, opcionPeri]);

    // Load saved diet for date
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
                                    return {
                                        ...food,
                                        macros_efectivos: result.efectivos,
                                        macros_brutos: result.brutos,
                                        que_cuenta: result.que_cuenta
                                    };
                                } catch {
                                    return food;
                                }
                            })
                        );
                        updatedMeals[mealKey] = { alimentos: updatedFoods };
                    } else {
                        updatedMeals[mealKey] = mealData;
                    }
                }
                setMealsData(updatedMeals);
            } else {
                setMealsData({});
            }
        } catch (err) {
            console.error('Error loading diet:', err);
            setMealsData({});
        }
    }, [api]);

    // Initial load
    useEffect(() => {
        const init = async () => {
            setLoading(true);
            await loadDiet(currentDate);
            await loadDistribution();
            setLoading(false);
        };
        init();
    }, [currentDate]); // eslint-disable-line

    // Reload distribution when config changes
    useEffect(() => {
        if (!loading) {
            loadDistribution();
        }
    }, [tipoDia, numComidas, momentoEntreno, opcionPeri]); // eslint-disable-line

    // Search foods with debounce
    useEffect(() => {
        if (!addFoodModal.open && !builderModal.open) return;
        
        const timer = setTimeout(async () => {
            setSearchLoading(true);
            try {
                const params = new URLSearchParams();
                if (searchQuery) params.set('q', searchQuery);
                if (searchCategory) params.set('category', searchCategory);
                
                // For periworkout, filter categories
                const mealKey = addFoodModal.mealKey || builderModal.mealKey;
                if (mealKey === 'Intra' || mealKey === 'Post') {
                    params.set('tipo_comida', mealKey.toLowerCase());
                }
                
                params.set('limit', '30');
                const result = await api(`/api/calculator/search?${params}`);
                setSearchResults(result.alimentos || []);
            } catch (err) {
                console.error('Search error:', err);
            }
            setSearchLoading(false);
        }, 300);
        
        return () => clearTimeout(timer);
    }, [searchQuery, searchCategory, addFoodModal.open, builderModal.open, addFoodModal.mealKey, builderModal.mealKey, api]);

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
        
        if (dateOnly.getTime() === today.getTime()) {
            return 'Hoy';
        }
        return d.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' });
    };

    // Get meal order based on momento_entreno
    const getMealOrder = () => {
        const baseMeals = numComidas === 3 ? ['C1', 'C2', 'C3'] : ['C1', 'C2', 'C3', 'C4'];
        
        if (tipoDia === 'descanso') return baseMeals;
        
        const periMeals = [];
        if (opcionPeri === 'intra_post') {
            periMeals.push('Intra', 'Post');
        } else if (opcionPeri === 'solo_post') {
            periMeals.push('Post');
        } else if (opcionPeri === 'solo_intra') {
            periMeals.push('Intra');
        }
        
        if (periMeals.length === 0) return baseMeals;
        
        const result = [...baseMeals];
        const insertIndex = momentoEntreno;
        result.splice(insertIndex, 0, ...periMeals);
        
        return result;
    };

    // Calculate macros
    const calculateMealMacros = (mealKey) => {
        const foods = mealsData[mealKey]?.alimentos || [];
        return foods.reduce((total, f) => ({
            P: total.P + (f.macros_efectivos?.P || 0),
            H: total.H + (f.macros_efectivos?.H || 0),
            G: total.G + (f.macros_efectivos?.G || 0)
        }), { P: 0, H: 0, G: 0 });
    };

    const calculateDayMacros = () => {
        const mealOrder = getMealOrder();
        return mealOrder.reduce((total, key) => {
            const mealMacros = calculateMealMacros(key);
            return {
                P: total.P + mealMacros.P,
                H: total.H + mealMacros.H,
                G: total.G + mealMacros.G
            };
        }, { P: 0, H: 0, G: 0 });
    };

    const getMealTarget = (mealKey) => {
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
        const margin = 4;
        
        const pOk = Math.abs(target.P - served.P) <= margin;
        const hOk = Math.abs(target.H - served.H) <= margin;
        const gOk = mealKey === 'Intra' || mealKey === 'Post' || Math.abs(target.G - served.G) <= margin;
        
        if (pOk && hOk && gOk) return 'cuadrada';
        if (served.P > target.P + margin || served.H > target.H + margin || served.G > target.G + margin) {
            return 'sobra';
        }
        return 'falta';
    };

    // Food operations
    const handleAddFood = async (food) => {
        const mealKey = addFoodModal.mealKey || builderModal.mealKey;
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
            
            const newFood = {
                alimento_id: food.id,
                nombre: food.nombre,
                cantidad_g: result.cantidad_g,
                macros_efectivos: result.macros_efectivos,
                macros_brutos: result.macros_brutos,
                que_cuenta: result.que_cuenta,
                categorias: food.categorias
            };
            
            if (builderModal.open) {
                // Add to builder foods
                setBuilderModal(prev => ({
                    ...prev,
                    foods: [...prev.foods, newFood]
                }));
                // Also add to meal
                setMealsData(prev => ({
                    ...prev,
                    [mealKey]: {
                        alimentos: [...(prev[mealKey]?.alimentos || []), newFood]
                    }
                }));
                toast.success(`${food.nombre} añadido`);
            } else {
                setMealsData(prev => ({
                    ...prev,
                    [mealKey]: {
                        alimentos: [...(prev[mealKey]?.alimentos || []), newFood]
                    }
                }));
                setAddFoodModal({ open: false, mealKey: null });
                setSearchQuery('');
                setSearchCategory('');
                toast.success(`${food.nombre} añadido`);
            }
        } catch (err) {
            toast.error('Error añadiendo alimento');
        }
    };

    const updateFoodQuantity = async (mealKey, foodIndex, delta) => {
        const foods = [...(mealsData[mealKey]?.alimentos || [])];
        const food = foods[foodIndex];
        const newQuantity = Math.max(5, food.cantidad_g + delta);
        
        try {
            const result = await api('/api/calculator/macros-efectivos', {
                method: 'POST',
                body: JSON.stringify({
                    alimento_id: food.alimento_id,
                    cantidad_g: newQuantity,
                    es_vegano: false
                })
            });
            
            foods[foodIndex] = {
                ...food,
                cantidad_g: newQuantity,
                macros_efectivos: result.efectivos,
                macros_brutos: result.brutos,
                que_cuenta: result.que_cuenta
            };
            
            setMealsData(prev => ({
                ...prev,
                [mealKey]: { alimentos: foods }
            }));
        } catch (err) {
            console.error('Error updating quantity:', err);
        }
    };

    const removeFood = (mealKey, foodIndex) => {
        setMealsData(prev => ({
            ...prev,
            [mealKey]: {
                alimentos: (prev[mealKey]?.alimentos || []).filter((_, i) => i !== foodIndex)
            }
        }));
    };

    // Menu options
    const loadMenuOptions = async (mealKey) => {
        const target = getMealTarget(mealKey);
        const momentoMap = {
            'C1': 'desayuno',
            'C2': 'comida',
            'C3': numComidas === 3 ? 'cena' : 'merienda',
            'C4': 'cena'
        };
        const momento = momentoMap[mealKey] || 'comida';
        
        setMenuOptionsLoading(true);
        setMenuOptionsModal({ open: true, mealKey });
        
        try {
            const result = await api('/api/calculator/menu-options', {
                method: 'POST',
                body: JSON.stringify({
                    momento,
                    macros_objetivo: { P: target.P, H: target.H, G: target.G },
                    es_vegano: false,
                    excluir_proteinas: []
                })
            });
            setMenuOptions(result.opciones || []);
        } catch (err) {
            console.error('Error loading menu options:', err);
            toast.error('Error cargando opciones');
            setMenuOptions([]);
        }
        setMenuOptionsLoading(false);
    };

    const applyMenuOption = async (option) => {
        const mealKey = menuOptionsModal.mealKey;
        
        try {
            const foods = option.items.map(item => ({
                alimento_id: item.alimento_id,
                nombre: item.nombre,
                cantidad_g: item.cantidad_g,
                macros_efectivos: item.macros_efectivos,
                macros_brutos: item.macros_efectivos,
                que_cuenta: { P: true, H: true, G: true }
            }));
            
            setMealsData(prev => ({
                ...prev,
                [mealKey]: { alimentos: foods }
            }));
            
            setMenuOptionsModal({ open: false, mealKey: null });
            toast.success(`Menú "${option.nombre}" aplicado`);
        } catch (err) {
            toast.error('Error aplicando menú');
        }
    };

    // Save & copy
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
                    macros_snapshot: distribution?.resumen
                })
            });
            toast.success('Dieta guardada');
        } catch (err) {
            toast.error('Error guardando dieta');
        }
    };

    const copyDiet = async () => {
        if (!copyDate) {
            toast.error('Selecciona una fecha');
            return;
        }
        try {
            await api('/api/diets/copy', {
                method: 'POST',
                body: JSON.stringify({
                    fecha_origen: currentDate,
                    fecha_destino: copyDate
                })
            });
            toast.success(`Copiada a ${formatDate(copyDate)}`);
            setCopyModalOpen(false);
            setCopyDate('');
        } catch (err) {
            toast.error('Error copiando dieta');
        }
    };

    // Builder functions
    const openBuilder = (mealKey) => {
        setBuilderModal({ open: true, mealKey, step: 0, foods: [] });
        setSearchQuery('');
        setSearchCategory(BUILDER_STEPS[0].categories[0]);
    };

    const nextBuilderStep = () => {
        const nextStep = builderModal.step + 1;
        if (nextStep >= BUILDER_STEPS.length) {
            // Finish builder
            setBuilderModal({ open: false, mealKey: null, step: 0, foods: [] });
            setSearchQuery('');
            setSearchCategory('');
            toast.success('Comida construida');
        } else {
            setBuilderModal(prev => ({ ...prev, step: nextStep }));
            setSearchCategory(BUILDER_STEPS[nextStep].categories[0]);
        }
    };

    // Day totals
    const dayMacros = calculateDayMacros();
    const dayTarget = distribution?.resumen || { P_total: 0, H_total: 0, G_total: 0, kcal_total: 0 };
    const dayKcal = dayMacros.P * 4 + dayMacros.H * 4 + dayMacros.G * 9;
    const isDayComplete = Math.abs(dayMacros.P - dayTarget.P_total) <= 4 && 
                          Math.abs(dayMacros.H - dayTarget.H_total) <= 4 && 
                          Math.abs(dayMacros.G - dayTarget.G_total) <= 4;

    // Circular progress component
    const CircularProgress = ({ value, max, color, label, size = 60 }) => {
        const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
        const radius = (size - 8) / 2;
        const circumference = 2 * Math.PI * radius;
        const offset = circumference - (pct / 100) * circumference;
        
        return (
            <div className="flex flex-col items-center">
                <div className="relative" style={{ width: size, height: size }}>
                    <svg className="transform -rotate-90" width={size} height={size}>
                        <circle
                            cx={size / 2}
                            cy={size / 2}
                            r={radius}
                            fill="none"
                            stroke="#E5E7EB"
                            strokeWidth="6"
                        />
                        <circle
                            cx={size / 2}
                            cy={size / 2}
                            r={radius}
                            fill="none"
                            stroke={color}
                            strokeWidth="6"
                            strokeDasharray={circumference}
                            strokeDashoffset={offset}
                            strokeLinecap="round"
                            className="transition-all duration-500"
                        />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-sm font-bold font-mono" style={{ color }}>{value.toFixed(0)}</span>
                    </div>
                </div>
                <span className="text-xs text-gray-500 mt-1">{label}</span>
            </div>
        );
    };

    // Progress bar component
    const ProgressBar = ({ value, max, color, label }) => {
        const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
        const isOver = value > max;
        return (
            <div className="flex items-center gap-2 mb-1.5">
                <span className="text-xs font-semibold w-4 font-mono" style={{ color }}>{label}</span>
                <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div 
                        className="h-full rounded-full transition-all duration-300" 
                        style={{ width: `${pct}%`, backgroundColor: isOver ? '#EF4444' : color }} 
                    />
                </div>
                <span className="text-xs text-gray-500 w-16 text-right font-mono">
                    {value.toFixed(0)}/{max.toFixed(0)}
                </span>
            </div>
        );
    };

    // Meal names with emojis
    const mealInfo = {
        C1: { name: 'Comida 1', subtitle: 'Desayuno', emoji: '🌅' },
        C2: { name: 'Comida 2', subtitle: 'Almuerzo', emoji: '☀️' },
        C3: { name: numComidas === 3 ? 'Comida 3' : 'Comida 3', subtitle: numComidas === 3 ? 'Cena' : 'Merienda', emoji: numComidas === 3 ? '🌙' : '🌤️' },
        C4: { name: 'Comida 4', subtitle: 'Cena', emoji: '🌙' },
        Intra: { name: 'Intra-entreno', subtitle: 'Durante', emoji: '⚡' },
        Post: { name: 'Post-entreno', subtitle: 'Después', emoji: '💪' }
    };

    // Meal Card Component
    const MealCard = ({ mealKey }) => {
        const isExpanded = expandedMeals[mealKey];
        const target = getMealTarget(mealKey);
        const served = calculateMealMacros(mealKey);
        const status = getMealStatus(mealKey);
        const foods = mealsData[mealKey]?.alimentos || [];
        const isPeri = mealKey === 'Intra' || mealKey === 'Post';
        const info = mealInfo[mealKey];

        const statusConfig = {
            cuadrada: { icon: '✅', text: 'Cuadrada', bg: 'bg-green-100 text-green-700' },
            falta: { icon: '⚠️', text: 'Faltan macros', bg: 'bg-yellow-100 text-yellow-700' },
            sobra: { icon: '❌', text: 'Sobran macros', bg: 'bg-red-100 text-red-700' }
        };

        return (
            <Card className={`bg-white shadow-sm rounded-xl overflow-hidden transition-all duration-200 ${isPeri ? 'border-l-4 border-l-[#FF671F]' : ''}`}>
                {/* Header */}
                <button 
                    className="w-full text-left"
                    onClick={() => setExpandedMeals(prev => ({ ...prev, [mealKey]: !isExpanded }))}
                    data-testid={`meal-card-${mealKey}`}
                >
                    <div className="p-4 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <span className="text-2xl">{info.emoji}</span>
                            <div>
                                <h3 className="font-bold text-[#1A1A1A] tracking-tight">{info.name}</h3>
                                <p className="text-xs text-[#666666]">
                                    {target.P.toFixed(0)}P | {target.H.toFixed(0)}H {!isPeri && `| ${target.G.toFixed(0)}G`}
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            {foods.length > 0 && (
                                <span className={`px-2 py-1 rounded-lg text-xs font-medium ${statusConfig[status].bg}`}>
                                    {statusConfig[status].icon} {statusConfig[status].text}
                                </span>
                            )}
                            {isExpanded ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
                        </div>
                    </div>
                </button>

                {/* Expanded content */}
                {isExpanded && (
                    <CardContent className="pt-0 px-4 pb-4">
                        {/* Progress bars */}
                        <div className="mb-4 bg-[#F5F5F5] rounded-lg p-3">
                            <ProgressBar value={served.P} max={target.P} color="#4CAF50" label="P" />
                            <ProgressBar value={served.H} max={target.H} color="#2196F3" label="H" />
                            {!isPeri && <ProgressBar value={served.G} max={target.G} color="#FF5722" label="G" />}
                        </div>

                        {/* Empty state with action buttons */}
                        {foods.length === 0 && !isPeri && (
                            <div className="space-y-2">
                                <Button 
                                    className="w-full h-12 bg-[#FF671F] hover:bg-[#E55A1B] text-white font-semibold rounded-xl transition-all"
                                    onClick={() => loadMenuOptions(mealKey)}
                                    data-testid={`menu-options-${mealKey}`}
                                >
                                    <Zap className="w-5 h-5 mr-2" /> ELIGE TU MENÚ
                                </Button>
                                <div className="grid grid-cols-2 gap-2">
                                    <Button 
                                        variant="outline" 
                                        className="h-10 rounded-xl border-gray-200"
                                        onClick={() => openBuilder(mealKey)}
                                        data-testid={`builder-${mealKey}`}
                                    >
                                        <Wrench className="w-4 h-4 mr-1.5" /> Construirlo
                                    </Button>
                                    <Button 
                                        variant="outline" 
                                        className="h-10 rounded-xl border-gray-200"
                                        onClick={() => {
                                            setAddFoodModal({ open: true, mealKey });
                                            setSearchQuery('');
                                            setSearchCategory('');
                                        }}
                                        data-testid={`search-${mealKey}`}
                                    >
                                        <Search className="w-4 h-4 mr-1.5" /> Buscar
                                    </Button>
                                </div>
                            </div>
                        )}

                        {/* Empty state for periworkout */}
                        {foods.length === 0 && isPeri && (
                            <Button 
                                variant="outline" 
                                className="w-full h-10 rounded-xl border-dashed border-[#FF671F] text-[#FF671F]"
                                onClick={() => {
                                    setAddFoodModal({ open: true, mealKey });
                                    setSearchQuery('');
                                    setSearchCategory('');
                                }}
                            >
                                <Search className="w-4 h-4 mr-1.5" /> Buscar alimento peri
                            </Button>
                        )}

                        {/* Foods list */}
                        {foods.length > 0 && (
                            <>
                                <div className="space-y-2 mb-3">
                                    {foods.map((food, idx) => (
                                        <div 
                                            key={idx} 
                                            className="flex items-center gap-3 bg-[#F5F5F5] rounded-xl p-3 transition-all hover:bg-gray-100"
                                        >
                                            <span className="text-xl">{getFoodEmoji(food.categorias)}</span>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium text-[#1A1A1A] truncate">{food.nombre}</p>
                                                <div className="flex gap-2 text-xs font-mono">
                                                    <span className="text-[#4CAF50]">{(food.macros_efectivos?.P ?? 0).toFixed(0)}P</span>
                                                    <span className="text-[#2196F3]">{(food.macros_efectivos?.H ?? 0).toFixed(0)}H</span>
                                                    <span className="text-[#FF5722]">{(food.macros_efectivos?.G ?? 0).toFixed(0)}G</span>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-1">
                                                <Button 
                                                    variant="ghost" 
                                                    size="icon" 
                                                    className="h-8 w-8 rounded-lg"
                                                    onClick={() => updateFoodQuantity(mealKey, idx, -10)}
                                                >
                                                    <Minus className="w-4 h-4" />
                                                </Button>
                                                <span className="text-sm font-bold font-mono w-14 text-center">{food.cantidad_g}g</span>
                                                <Button 
                                                    variant="ghost" 
                                                    size="icon" 
                                                    className="h-8 w-8 rounded-lg"
                                                    onClick={() => updateFoodQuantity(mealKey, idx, 10)}
                                                >
                                                    <Plus className="w-4 h-4" />
                                                </Button>
                                                <Button 
                                                    variant="ghost" 
                                                    size="icon" 
                                                    className="h-8 w-8 rounded-lg text-red-500 hover:text-red-700 hover:bg-red-50"
                                                    onClick={() => removeFood(mealKey, idx)}
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                                
                                {/* Add more button */}
                                <Button 
                                    variant="outline" 
                                    className="w-full rounded-xl border-dashed"
                                    onClick={() => {
                                        setAddFoodModal({ open: true, mealKey });
                                        setSearchQuery('');
                                        setSearchCategory('');
                                    }}
                                >
                                    <Plus className="w-4 h-4 mr-1" /> Añadir alimento
                                </Button>
                            </>
                        )}
                    </CardContent>
                )}
            </Card>
        );
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-[#F5F5F5] flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="animate-spin rounded-full h-10 w-10 border-4 border-[#FF671F] border-t-transparent" />
                    <p className="text-[#666666] text-sm">Cargando...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#F5F5F5] pb-24" data-testid="nutrition-page">
            {/* Header */}
            <div className="bg-white shadow-sm sticky top-0 z-10">
                <div className="max-w-lg mx-auto px-4 py-4">
                    {/* Date navigation */}
                    <div className="flex items-center justify-between mb-4">
                        <Button variant="ghost" size="icon" className="rounded-xl" onClick={() => changeDate(-1)}>
                            <ChevronLeft className="w-5 h-5" />
                        </Button>
                        <div className="flex items-center gap-2">
                            <span className="text-xl font-bold text-[#1A1A1A] tracking-tight">{formatDate(currentDate)}</span>
                        </div>
                        <Button variant="ghost" size="icon" className="rounded-xl" onClick={() => changeDate(1)}>
                            <ChevronRight className="w-5 h-5" />
                        </Button>
                    </div>
                    
                    {/* Day type toggle */}
                    <div className="flex justify-center p-1 bg-[#F5F5F5] rounded-xl mb-4">
                        <button 
                            className={`flex-1 py-2.5 px-4 rounded-lg font-semibold text-sm transition-all ${
                                tipoDia === 'entrenamiento' 
                                    ? 'bg-[#FF671F] text-white shadow-sm' 
                                    : 'text-[#666666]'
                            }`}
                            onClick={() => setTipoDia('entrenamiento')}
                            data-testid="btn-entrenamiento"
                        >
                            DÍA DE ENTRENO
                        </button>
                        <button 
                            className={`flex-1 py-2.5 px-4 rounded-lg font-semibold text-sm transition-all ${
                                tipoDia === 'descanso' 
                                    ? 'bg-gray-700 text-white shadow-sm' 
                                    : 'text-[#666666]'
                            }`}
                            onClick={() => setTipoDia('descanso')}
                            data-testid="btn-descanso"
                        >
                            DÍA DE DESCANSO
                        </button>
                    </div>

                    {/* Day summary with circular progress */}
                    <div className={`rounded-xl p-4 transition-all ${isDayComplete ? 'bg-green-50 ring-2 ring-green-200' : 'bg-white'}`}>
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                                {isDayComplete && <span className="text-xl">🎉</span>}
                                <span className="font-bold text-[#1A1A1A]">
                                    {isDayComplete ? '¡Día completo!' : 'Resumen del día'}
                                </span>
                            </div>
                            <span className="text-sm font-mono text-[#666666]">
                                {dayKcal.toFixed(0)} / {dayTarget.kcal_total?.toFixed(0) || 0} kcal
                            </span>
                        </div>
                        <div className="flex justify-around">
                            <CircularProgress value={dayMacros.P} max={dayTarget.P_total || 1} color="#4CAF50" label={`/${dayTarget.P_total?.toFixed(0) || 0}P`} />
                            <CircularProgress value={dayMacros.H} max={dayTarget.H_total || 1} color="#2196F3" label={`/${dayTarget.H_total?.toFixed(0) || 0}H`} />
                            <CircularProgress value={dayMacros.G} max={dayTarget.G_total || 1} color="#FF5722" label={`/${dayTarget.G_total?.toFixed(0) || 0}G`} />
                        </div>
                    </div>
                </div>
            </div>

            <div className="max-w-lg mx-auto px-4 py-4">
                {/* Configuration */}
                {tipoDia === 'entrenamiento' && (
                    <Collapsible open={configOpen} onOpenChange={setConfigOpen} className="mb-4">
                        <CollapsibleTrigger asChild>
                            <Button variant="ghost" className="w-full justify-between text-[#666666] rounded-xl">
                                <span className="flex items-center gap-2">
                                    <Settings className="w-4 h-4" />
                                    Configuración
                                </span>
                                {configOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                            </Button>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                            <Card className="mt-2 bg-white rounded-xl shadow-sm">
                                <CardContent className="p-4 space-y-4">
                                    <div>
                                        <label className="text-sm font-semibold text-[#1A1A1A] mb-2 block">Comidas</label>
                                        <div className="flex gap-2">
                                            {[3, 4].map(n => (
                                                <Button 
                                                    key={n}
                                                    variant={numComidas === n ? 'default' : 'outline'}
                                                    size="sm"
                                                    onClick={() => setNumComidas(n)}
                                                    className={`rounded-lg ${numComidas === n ? 'bg-[#FF671F] hover:bg-[#E55A1B]' : ''}`}
                                                >
                                                    {n} comidas
                                                </Button>
                                            ))}
                                        </div>
                                    </div>
                                    
                                    <div>
                                        <label className="text-sm font-semibold text-[#1A1A1A] mb-2 block">Entrenas después de</label>
                                        <div className="flex flex-wrap gap-2">
                                            {[
                                                { value: 0, label: 'Ayunas' },
                                                { value: 1, label: 'C1' },
                                                { value: 2, label: 'C2' },
                                                ...(numComidas === 4 ? [{ value: 3, label: 'C3' }] : [])
                                            ].map(opt => (
                                                <Button 
                                                    key={opt.value}
                                                    variant={momentoEntreno === opt.value ? 'default' : 'outline'}
                                                    size="sm"
                                                    onClick={() => setMomentoEntreno(opt.value)}
                                                    className={`rounded-lg ${momentoEntreno === opt.value ? 'bg-[#FF671F] hover:bg-[#E55A1B]' : ''}`}
                                                >
                                                    {opt.label}
                                                </Button>
                                            ))}
                                        </div>
                                    </div>
                                    
                                    <div>
                                        <label className="text-sm font-semibold text-[#1A1A1A] mb-2 block">Periworkout</label>
                                        <div className="flex flex-wrap gap-2">
                                            {[
                                                { value: 'intra_post', label: 'Intra+Post' },
                                                { value: 'solo_post', label: 'Solo Post' },
                                                { value: 'solo_intra', label: 'Solo Intra' },
                                                { value: 'sin_peri', label: 'Sin peri' }
                                            ].map(opt => (
                                                <Button 
                                                    key={opt.value}
                                                    variant={opcionPeri === opt.value ? 'default' : 'outline'}
                                                    size="sm"
                                                    onClick={() => setOpcionPeri(opt.value)}
                                                    className={`rounded-lg ${opcionPeri === opt.value ? 'bg-[#FF671F] hover:bg-[#E55A1B]' : ''}`}
                                                >
                                                    {opt.label}
                                                </Button>
                                            ))}
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </CollapsibleContent>
                    </Collapsible>
                )}

                {/* Meals */}
                <div className="space-y-3 mb-4">
                    {getMealOrder().map(mealKey => (
                        <MealCard key={mealKey} mealKey={mealKey} />
                    ))}
                </div>

                {/* Action buttons */}
                <div className="flex gap-2">
                    <Button 
                        className="flex-1 h-12 bg-[#FF671F] hover:bg-[#E55A1B] rounded-xl font-semibold"
                        onClick={saveDiet}
                        data-testid="save-diet-btn"
                    >
                        <Save className="w-5 h-5 mr-2" /> Guardar día
                    </Button>
                    <Button 
                        variant="outline" 
                        className="h-12 w-12 rounded-xl"
                        onClick={() => setCopyModalOpen(true)}
                        data-testid="copy-diet-btn"
                    >
                        <Copy className="w-5 h-5" />
                    </Button>
                </div>
            </div>

            {/* Search Food Modal */}
            <Dialog open={addFoodModal.open} onOpenChange={(open) => !open && setAddFoodModal({ open: false, mealKey: null })}>
                <DialogContent className="max-w-lg max-h-[90vh] flex flex-col p-0 gap-0 rounded-t-3xl">
                    <DialogHeader className="p-4 border-b">
                        <DialogTitle className="flex items-center gap-2">
                            <Search className="w-5 h-5 text-[#FF671F]" />
                            Buscar alimento
                        </DialogTitle>
                        <DialogDescription className="sr-only">Busca alimentos para añadir</DialogDescription>
                    </DialogHeader>
                    
                    <div className="p-4 border-b">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                            <Input 
                                placeholder="Buscar alimento..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-10 pr-10 h-12 rounded-xl bg-[#F5F5F5] border-0"
                                data-testid="search-food-input"
                            />
                            {searchQuery && (
                                <button className="absolute right-3 top-1/2 -translate-y-1/2" onClick={() => setSearchQuery('')}>
                                    <X className="w-5 h-5 text-gray-400" />
                                </button>
                            )}
                        </div>
                    </div>
                    
                    {/* Category chips */}
                    <ScrollArea className="w-full whitespace-nowrap border-b">
                        <div className="flex gap-2 p-4">
                            {CATEGORY_CHIPS.map(chip => (
                                <button 
                                    key={chip.value}
                                    onClick={() => setSearchCategory(chip.value)}
                                    className={`flex-shrink-0 px-3 py-2 rounded-xl text-sm font-medium transition-all ${
                                        searchCategory === chip.value 
                                            ? 'bg-[#FF671F] text-white' 
                                            : 'bg-[#F5F5F5] text-[#666666]'
                                    }`}
                                >
                                    {chip.emoji} {chip.label}
                                </button>
                            ))}
                        </div>
                    </ScrollArea>
                    
                    {/* Results */}
                    <ScrollArea className="flex-1">
                        {searchLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <div className="animate-spin rounded-full h-8 w-8 border-4 border-[#FF671F] border-t-transparent" />
                            </div>
                        ) : searchResults.length === 0 ? (
                            <div className="text-center py-12">
                                <span className="text-4xl mb-3 block">🔍</span>
                                <p className="text-[#666666]">{searchQuery || searchCategory ? 'Sin resultados' : 'Busca un alimento'}</p>
                            </div>
                        ) : (
                            <div className="p-4 space-y-2">
                                {searchResults.map(food => (
                                    <button
                                        key={food.id}
                                        className="w-full text-left p-4 bg-[#F5F5F5] hover:bg-gray-100 rounded-xl transition-all"
                                        onClick={() => handleAddFood(food)}
                                        data-testid={`food-result-${food.id}`}
                                    >
                                        <div className="flex items-center gap-3">
                                            <span className="text-2xl">{getFoodEmoji(food.categorias)}</span>
                                            <div className="flex-1">
                                                <p className="font-semibold text-[#1A1A1A]">{food.nombre}</p>
                                                <div className="flex gap-2 text-xs font-mono mt-1">
                                                    <span className="text-[#4CAF50]">{food.proteinas}P</span>
                                                    <span className="text-[#2196F3]">{food.hidratos}H</span>
                                                    <span className="text-[#FF5722]">{food.grasas}G</span>
                                                    <span className="text-gray-400">({food.racion}g)</span>
                                                </div>
                                            </div>
                                            <ArrowRight className="w-5 h-5 text-gray-300" />
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )}
                    </ScrollArea>
                </DialogContent>
            </Dialog>

            {/* Menu Options Modal */}
            <Dialog open={menuOptionsModal.open} onOpenChange={(open) => !open && setMenuOptionsModal({ open: false, mealKey: null })}>
                <DialogContent className="max-w-lg max-h-[90vh] flex flex-col p-0 gap-0 rounded-t-3xl">
                    <DialogHeader className="p-4 border-b">
                        <DialogTitle className="flex items-center gap-2">
                            <Zap className="w-5 h-5 text-[#FF671F]" />
                            Elige tu menú
                        </DialogTitle>
                        <DialogDescription>
                            {menuOptionsModal.mealKey && `Para ${mealInfo[menuOptionsModal.mealKey]?.name}`}
                        </DialogDescription>
                    </DialogHeader>
                    
                    <ScrollArea className="flex-1">
                        {menuOptionsLoading ? (
                            <div className="flex flex-col items-center justify-center py-16">
                                <div className="animate-spin rounded-full h-10 w-10 border-4 border-[#FF671F] border-t-transparent mb-4" />
                                <p className="text-[#666666]">Calculando opciones...</p>
                            </div>
                        ) : menuOptions.length === 0 ? (
                            <div className="text-center py-16">
                                <span className="text-4xl mb-3 block">🤷</span>
                                <p className="text-[#666666]">No hay opciones disponibles</p>
                            </div>
                        ) : (
                            <div className="p-4 space-y-4">
                                {menuOptions.map((option, index) => {
                                    const letra = ['A', 'B', 'C'][index] || String.fromCharCode(65 + index);
                                    const bgStyles = [
                                        'bg-gradient-to-br from-orange-50 to-amber-50 border-orange-200 hover:border-orange-400',
                                        'bg-gradient-to-br from-blue-50 to-cyan-50 border-blue-200 hover:border-blue-400',
                                        'bg-gradient-to-br from-green-50 to-emerald-50 border-green-200 hover:border-green-400'
                                    ];
                                    const badgeBg = ['bg-[#FF671F]', 'bg-blue-500', 'bg-green-500'];
                                    
                                    return (
                                        <button
                                            key={option.plantilla_id}
                                            className={`w-full text-left p-4 rounded-2xl border-2 transition-all hover:shadow-lg active:scale-[0.98] ${bgStyles[index % 3]}`}
                                            onClick={() => applyMenuOption(option)}
                                            data-testid={`menu-option-${letra}`}
                                        >
                                            <div className="flex items-start justify-between mb-3">
                                                <div className="flex items-center gap-3">
                                                    <span className={`${badgeBg[index % 3]} text-white text-lg font-bold w-10 h-10 rounded-xl flex items-center justify-center shadow-sm`}>
                                                        {letra}
                                                    </span>
                                                    <h3 className="font-bold text-[#1A1A1A]">{option.nombre}</h3>
                                                </div>
                                                {option.cuadrada && (
                                                    <span className="bg-green-100 text-green-700 text-xs px-2.5 py-1 rounded-lg font-semibold flex items-center gap-1">
                                                        <Check className="w-3 h-3" /> Cuadrada
                                                    </span>
                                                )}
                                            </div>
                                            
                                            <div className="space-y-2 mb-4">
                                                {option.items.map((item, i) => (
                                                    <div key={i} className="flex justify-between text-sm">
                                                        <span className="text-[#1A1A1A]">{item.nombre}</span>
                                                        <span className="text-[#666666] font-mono">{item.cantidad_g}g</span>
                                                    </div>
                                                ))}
                                            </div>
                                            
                                            <div className="flex items-center gap-3 pt-3 border-t border-gray-200">
                                                <span className="text-[#4CAF50] font-bold font-mono">{option.macros_totales?.P?.toFixed(0) || 0}P</span>
                                                <span className="text-[#2196F3] font-bold font-mono">{option.macros_totales?.H?.toFixed(0) || 0}H</span>
                                                <span className="text-[#FF5722] font-bold font-mono">{option.macros_totales?.G?.toFixed(0) || 0}G</span>
                                                <span className="text-[#666666] ml-auto">{option.macros_totales?.kcal?.toFixed(0) || 0} kcal</span>
                                            </div>
                                            
                                            <div className="mt-3 py-2 bg-white/50 rounded-xl text-center">
                                                <span className="text-sm font-semibold text-[#FF671F]">Aplicar menú {letra}</span>
                                            </div>
                                        </button>
                                    );
                                })}
                                
                                {/* Build your own option */}
                                <button
                                    className="w-full p-4 rounded-2xl border-2 border-dashed border-gray-300 hover:border-gray-400 transition-all text-center"
                                    onClick={() => {
                                        setMenuOptionsModal({ open: false, mealKey: null });
                                        openBuilder(menuOptionsModal.mealKey);
                                    }}
                                >
                                    <span className="text-2xl mb-2 block">🛠️</span>
                                    <p className="text-[#666666] font-medium">Ninguno me convence</p>
                                    <p className="text-sm text-[#FF671F]">Construirlo yo →</p>
                                </button>
                            </div>
                        )}
                    </ScrollArea>
                </DialogContent>
            </Dialog>

            {/* Builder Modal */}
            <Dialog open={builderModal.open} onOpenChange={(open) => !open && setBuilderModal({ open: false, mealKey: null, step: 0, foods: [] })}>
                <DialogContent className="max-w-lg max-h-[90vh] flex flex-col p-0 gap-0 rounded-t-3xl">
                    <DialogHeader className="p-4 border-b">
                        <DialogTitle className="flex items-center gap-2">
                            <Wrench className="w-5 h-5 text-[#FF671F]" />
                            Construir comida
                        </DialogTitle>
                        <DialogDescription>
                            {builderModal.mealKey && mealInfo[builderModal.mealKey]?.name}
                        </DialogDescription>
                    </DialogHeader>
                    
                    {/* Step indicator */}
                    <div className="p-4 border-b">
                        <div className="flex items-center justify-between mb-2">
                            {BUILDER_STEPS.map((step, idx) => (
                                <div key={step.id} className="flex items-center">
                                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all ${
                                        idx < builderModal.step 
                                            ? 'bg-green-500 text-white' 
                                            : idx === builderModal.step 
                                                ? 'bg-[#FF671F] text-white' 
                                                : 'bg-gray-200 text-gray-500'
                                    }`}>
                                        {idx < builderModal.step ? '✓' : step.emoji}
                                    </div>
                                    {idx < BUILDER_STEPS.length - 1 && (
                                        <div className={`w-8 h-1 mx-1 rounded ${idx < builderModal.step ? 'bg-green-500' : 'bg-gray-200'}`} />
                                    )}
                                </div>
                            ))}
                        </div>
                        <p className="text-center font-semibold text-[#1A1A1A]">
                            {BUILDER_STEPS[builderModal.step]?.label}
                        </p>
                        
                        {/* Progress hint */}
                        {builderModal.mealKey && (
                            <div className="mt-3 text-xs text-center text-[#666666]">
                                {(() => {
                                    const remaining = getMealRemaining(builderModal.mealKey);
                                    const target = getMealTarget(builderModal.mealKey);
                                    const pPct = target.P > 0 ? Math.round(((target.P - remaining.P) / target.P) * 100) : 0;
                                    return pPct >= 80 
                                        ? `✅ Ya tienes el ${pPct}% de proteína cubierta`
                                        : `Te falta ${remaining.P.toFixed(0)}P | ${remaining.H.toFixed(0)}H | ${remaining.G.toFixed(0)}G`;
                                })()}
                            </div>
                        )}
                    </div>
                    
                    {/* Search in builder */}
                    <div className="p-4 border-b">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                            <Input 
                                placeholder={`Buscar ${BUILDER_STEPS[builderModal.step]?.label?.toLowerCase() || 'alimento'}...`}
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-10 h-12 rounded-xl bg-[#F5F5F5] border-0"
                            />
                        </div>
                    </div>
                    
                    {/* Category chips for current step */}
                    <ScrollArea className="w-full whitespace-nowrap border-b">
                        <div className="flex gap-2 p-4">
                            {CATEGORY_CHIPS
                                .filter(c => !BUILDER_STEPS[builderModal.step]?.categories || 
                                            BUILDER_STEPS[builderModal.step]?.categories.some(cat => c.value.startsWith(cat) || c.value === ''))
                                .map(chip => (
                                    <button 
                                        key={chip.value}
                                        onClick={() => setSearchCategory(chip.value)}
                                        className={`flex-shrink-0 px-3 py-2 rounded-xl text-sm font-medium transition-all ${
                                            searchCategory === chip.value 
                                                ? 'bg-[#FF671F] text-white' 
                                                : 'bg-[#F5F5F5] text-[#666666]'
                                        }`}
                                    >
                                        {chip.emoji} {chip.label}
                                    </button>
                                ))}
                        </div>
                    </ScrollArea>
                    
                    {/* Results */}
                    <ScrollArea className="flex-1">
                        {searchLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <div className="animate-spin rounded-full h-8 w-8 border-4 border-[#FF671F] border-t-transparent" />
                            </div>
                        ) : (
                            <div className="p-4 space-y-2">
                                {searchResults.map(food => (
                                    <button
                                        key={food.id}
                                        className="w-full text-left p-4 bg-[#F5F5F5] hover:bg-gray-100 rounded-xl transition-all"
                                        onClick={() => handleAddFood(food)}
                                    >
                                        <div className="flex items-center gap-3">
                                            <span className="text-2xl">{getFoodEmoji(food.categorias)}</span>
                                            <div className="flex-1">
                                                <p className="font-semibold text-[#1A1A1A]">{food.nombre}</p>
                                                <div className="flex gap-2 text-xs font-mono mt-1">
                                                    <span className="text-[#4CAF50]">{food.proteinas}P</span>
                                                    <span className="text-[#2196F3]">{food.hidratos}H</span>
                                                    <span className="text-[#FF5722]">{food.grasas}G</span>
                                                </div>
                                            </div>
                                            <Plus className="w-5 h-5 text-[#FF671F]" />
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )}
                    </ScrollArea>
                    
                    {/* Builder actions */}
                    <div className="p-4 border-t flex gap-2">
                        <Button 
                            variant="outline" 
                            className="flex-1 h-12 rounded-xl"
                            onClick={() => setBuilderModal({ open: false, mealKey: null, step: 0, foods: [] })}
                        >
                            Cancelar
                        </Button>
                        <Button 
                            className="flex-1 h-12 rounded-xl bg-[#FF671F] hover:bg-[#E55A1B]"
                            onClick={nextBuilderStep}
                        >
                            {builderModal.step === BUILDER_STEPS.length - 1 ? 'Terminar' : 'Siguiente →'}
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>

            {/* Copy Modal */}
            <Dialog open={copyModalOpen} onOpenChange={setCopyModalOpen}>
                <DialogContent className="max-w-sm rounded-2xl">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <RotateCcw className="w-5 h-5 text-[#FF671F]" />
                            Copiar dieta
                        </DialogTitle>
                        <DialogDescription className="sr-only">Copia esta dieta a otro día</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <p className="text-sm text-[#666666]">
                            Copiar dieta del <span className="font-semibold">{formatDate(currentDate)}</span> a:
                        </p>
                        <Input 
                            type="date"
                            value={copyDate}
                            onChange={(e) => setCopyDate(e.target.value)}
                            min={new Date().toISOString().split('T')[0]}
                            className="h-12 rounded-xl"
                        />
                        <div className="flex gap-2">
                            <Button variant="outline" className="flex-1 h-12 rounded-xl" onClick={() => setCopyModalOpen(false)}>
                                Cancelar
                            </Button>
                            <Button className="flex-1 h-12 rounded-xl bg-[#FF671F] hover:bg-[#E55A1B]" onClick={copyDiet}>
                                Copiar
                            </Button>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default NutritionPage;
