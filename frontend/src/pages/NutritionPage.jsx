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
    Search, X, Zap, Wrench, RotateCcw, ArrowRight, ArrowUpRight, Calendar
} from 'lucide-react';

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

// Category filter chips
const CATEGORY_CHIPS = [
    { label: 'Todas', value: '', emoji: '🍽️' },
    { label: 'Carnes', value: '2', emoji: '🥩' },
    { label: 'Pescados', value: '3', emoji: '🐟' },
    { label: 'Huevos', value: '1', emoji: '🥚' },
    { label: 'Lácteos', value: '5', emoji: '🥛' },
    { label: 'Cereales', value: '7', emoji: '🌾' },
    { label: 'Arroces', value: '21', emoji: '🍚' },
    { label: 'Pasta', value: '22', emoji: '🍝' },
    { label: 'Verduras', value: '13', emoji: '🥦' },
    { label: 'Fruta', value: '11', emoji: '🍎' },
    { label: 'Grasas', value: '17', emoji: '🫒' },
];

const NutritionPage = () => {
    const { token } = useAuth();
    
    // Date & Config state
    const [currentDate, setCurrentDate] = useState(new Date().toISOString().split('T')[0]);
    const [tipoDia, setTipoDia] = useState('entrenamiento');
    const [numComidas, setNumComidas] = useState(4);
    const [momentoEntreno, setMomentoEntreno] = useState(1);
    const [opcionPeri, setOpcionPeri] = useState('intra_post');
    const [configOpen, setConfigOpen] = useState(false);
    
    // Data state
    const [distribution, setDistribution] = useState(null);
    const [mealsData, setMealsData] = useState({});
    const [expandedMeals, setExpandedMeals] = useState({ C1: true });
    const [loading, setLoading] = useState(true);
    
    // Modal states
    const [addFoodModal, setAddFoodModal] = useState({ open: false, mealKey: null });
    const [menuOptionsModal, setMenuOptionsModal] = useState({ open: false, mealKey: null });
    const [copyModalOpen, setCopyModalOpen] = useState(false);
    const [copyDate, setCopyDate] = useState('');
    
    // Search state
    const [searchQuery, setSearchQuery] = useState('');
    const [searchCategory, setSearchCategory] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [searchLoading, setSearchLoading] = useState(false);
    
    // Menu options
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

    // Load saved diet
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
        if (!loading) loadDistribution();
    }, [tipoDia, numComidas, momentoEntreno, opcionPeri]); // eslint-disable-line

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

    // Meal order
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
        if (served.P > target.P + margin || served.H > target.H + margin || served.G > target.G + margin) return 'sobra';
        return 'falta';
    };

    // Food operations
    const handleAddFood = async (food) => {
        const mealKey = addFoodModal.mealKey;
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
        const newQuantity = Math.max(5, food.cantidad_g + delta);
        try {
            const result = await api('/api/calculator/macros-efectivos', {
                method: 'POST',
                body: JSON.stringify({ alimento_id: food.alimento_id, cantidad_g: newQuantity, es_vegano: false })
            });
            foods[foodIndex] = { ...food, cantidad_g: newQuantity, macros_efectivos: result.efectivos, macros_brutos: result.brutos, que_cuenta: result.que_cuenta };
            setMealsData(prev => ({ ...prev, [mealKey]: { alimentos: foods } }));
        } catch (err) { console.error('Error updating quantity:', err); }
    };

    const removeFood = (mealKey, foodIndex) => {
        setMealsData(prev => ({
            ...prev,
            [mealKey]: { alimentos: (prev[mealKey]?.alimentos || []).filter((_, i) => i !== foodIndex) }
        }));
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
                    macros_snapshot: distribution?.resumen
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
    const dayKcal = dayMacros.P * 4 + dayMacros.H * 4 + dayMacros.G * 9;

    // Macro Circle Component
    const MacroCircle = ({ value, target, label, color }) => {
        const pct = target > 0 ? Math.min((value / target) * 100, 100) : 0;
        const colors = {
            protein: { ring: '#FFDA61', bg: '#FFDA61' },
            carbs: { ring: '#4CAF50', bg: '#4CAF50' },
            fat: { ring: '#66BB6A', bg: '#66BB6A' }
        };
        const c = colors[color] || colors.protein;
        
        return (
            <div className="flex flex-col items-center">
                <div className="relative w-20 h-20">
                    <svg className="w-20 h-20 transform -rotate-90">
                        <circle cx="40" cy="40" r="34" fill="white" stroke="#E5E7EB" strokeWidth="6" />
                        <circle 
                            cx="40" cy="40" r="34" 
                            fill="none" 
                            stroke={c.ring} 
                            strokeWidth="6"
                            strokeDasharray={`${pct * 2.136} 213.6`}
                            strokeLinecap="round"
                            className="transition-all duration-500"
                        />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-xs text-gray-500">{label}</span>
                        <span className="text-lg font-bold text-gray-800">{target.toFixed(0)} g</span>
                    </div>
                </div>
                <span className="text-xs text-gray-500 mt-1">{value.toFixed(0)}/{target.toFixed(0)}</span>
            </div>
        );
    };

    // Meal info
    const mealInfo = {
        C1: { name: 'Comida 1', emoji: '🌅' },
        C2: { name: 'Comida 2', emoji: '☀️' },
        C3: { name: numComidas === 3 ? 'Comida 3' : 'Comida 3', emoji: numComidas === 3 ? '🌙' : '🌤️' },
        C4: { name: 'Comida 4', emoji: '🌙' },
        Intra: { name: 'Intra-entreno', emoji: '⚡' },
        Post: { name: 'Post-entreno', emoji: '💪' }
    };

    // Meal Card
    const MealCard = ({ mealKey }) => {
        const isExpanded = expandedMeals[mealKey];
        const target = getMealTarget(mealKey);
        const served = calculateMealMacros(mealKey);
        const status = getMealStatus(mealKey);
        const foods = mealsData[mealKey]?.alimentos || [];
        const isPeri = mealKey === 'Intra' || mealKey === 'Post';
        const info = mealInfo[mealKey];

        const statusConfig = {
            cuadrada: { label: 'Cuadrado', bg: 'bg-carbs-green', text: 'text-white' },
            falta: { label: 'Faltan', bg: 'bg-protein-yellow', text: 'text-gray-800' },
            sobra: { label: 'Sobran', bg: 'bg-fat-red', text: 'text-white' }
        };

        const getMacroStatus = (macro, value, targetVal) => {
            const diff = Math.abs(value - targetVal);
            if (diff <= 4) return 'cuadrada';
            if (value > targetVal + 4) return 'sobra';
            return 'falta';
        };

        return (
            <Card className={`bg-white shadow-md rounded-2xl overflow-hidden transition-all duration-200 ${isPeri ? 'border-l-4 border-l-brand-orange' : ''}`}>
                <button 
                    className="w-full text-left p-4 flex items-center justify-between"
                    onClick={() => setExpandedMeals(prev => ({ ...prev, [mealKey]: !isExpanded }))}
                    data-testid={`meal-card-${mealKey}`}
                >
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">{info.emoji}</span>
                        <div>
                            <h3 className="font-bold text-gray-900">{info.name}</h3>
                            <p className="text-xs text-gray-500">Macros para la comida</p>
                        </div>
                    </div>
                    {isExpanded ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
                </button>

                {isExpanded && (
                    <CardContent className="pt-0 px-4 pb-4">
                        {/* Macro badges */}
                        <div className="space-y-2 mb-4">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <span className="text-lg">🥩</span>
                                    <span className="text-sm text-gray-700">Proteínas:</span>
                                    <span className="text-sm font-semibold">{served.P.toFixed(1)} de {target.P.toFixed(1)} g</span>
                                </div>
                                {foods.length > 0 && (
                                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusConfig[getMacroStatus('P', served.P, target.P)].bg} ${statusConfig[getMacroStatus('P', served.P, target.P)].text}`}>
                                        {statusConfig[getMacroStatus('P', served.P, target.P)].label}
                                    </span>
                                )}
                            </div>
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <span className="text-lg">🍞</span>
                                    <span className="text-sm text-gray-700">Hidratos:</span>
                                    <span className="text-sm font-semibold">{served.H.toFixed(1)} de {target.H.toFixed(1)} g</span>
                                </div>
                                {foods.length > 0 && (
                                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusConfig[getMacroStatus('H', served.H, target.H)].bg} ${statusConfig[getMacroStatus('H', served.H, target.H)].text}`}>
                                        {statusConfig[getMacroStatus('H', served.H, target.H)].label}
                                    </span>
                                )}
                            </div>
                            {!isPeri && (
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <span className="text-lg">🫒</span>
                                        <span className="text-sm text-gray-700">Grasas:</span>
                                        <span className="text-sm font-semibold">{served.G.toFixed(1)} de {target.G.toFixed(1)} g</span>
                                    </div>
                                    {foods.length > 0 && (
                                        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusConfig[getMacroStatus('G', served.G, target.G)].bg} ${statusConfig[getMacroStatus('G', served.G, target.G)].text}`}>
                                            {statusConfig[getMacroStatus('G', served.G, target.G)].label}
                                        </span>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Empty state */}
                        {foods.length === 0 && !isPeri && (
                            <div className="space-y-2">
                                <Button 
                                    className="w-full h-12 bg-brand-orange hover:bg-brand-orange-dark text-white font-bold rounded-full shadow-lg shadow-brand-orange/30"
                                    onClick={() => loadMenuOptions(mealKey)}
                                    data-testid={`menu-options-${mealKey}`}
                                >
                                    <Zap className="w-5 h-5 mr-2" /> ELIGE TU MENÚ
                                </Button>
                                <div className="grid grid-cols-2 gap-2">
                                    <Button 
                                        variant="outline" 
                                        className="h-10 rounded-full border-gray-300"
                                        onClick={() => { setAddFoodModal({ open: true, mealKey }); setSearchQuery(''); setSearchCategory(''); }}
                                    >
                                        <Wrench className="w-4 h-4 mr-1" /> Construirlo
                                    </Button>
                                    <Button 
                                        variant="ghost" 
                                        className="h-10 rounded-full text-gray-600"
                                        onClick={() => { setAddFoodModal({ open: true, mealKey }); setSearchQuery(''); setSearchCategory(''); }}
                                    >
                                        <Search className="w-4 h-4 mr-1" /> Buscar
                                    </Button>
                                </div>
                            </div>
                        )}

                        {/* Empty state for peri */}
                        {foods.length === 0 && isPeri && (
                            <Button 
                                variant="outline" 
                                className="w-full h-10 rounded-full border-dashed border-brand-orange text-brand-orange"
                                onClick={() => { setAddFoodModal({ open: true, mealKey }); setSearchQuery(''); setSearchCategory(''); }}
                            >
                                <Search className="w-4 h-4 mr-1" /> Buscar alimento peri
                            </Button>
                        )}

                        {/* Foods list */}
                        {foods.length > 0 && (
                            <>
                                <div className="border-t border-gray-100 pt-3 mb-3">
                                    <p className="text-xs text-gray-500 mb-2">Ingredientes</p>
                                    <div className="space-y-2">
                                        {foods.map((food, idx) => (
                                            <div 
                                                key={idx} 
                                                className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0"
                                            >
                                                <div className="flex items-center gap-2 flex-1 min-w-0">
                                                    <span className="text-lg">{getFoodEmoji(food.categorias)}</span>
                                                    <span className="text-sm text-gray-800 truncate">{food.nombre}</span>
                                                </div>
                                                <div className="flex items-center gap-1">
                                                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => updateFoodQuantity(mealKey, idx, -10)}>
                                                        <Minus className="w-3 h-3" />
                                                    </Button>
                                                    <span className="text-sm font-bold w-14 text-center">{food.cantidad_g}g</span>
                                                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => updateFoodQuantity(mealKey, idx, 10)}>
                                                        <Plus className="w-3 h-3" />
                                                    </Button>
                                                    <Button variant="ghost" size="icon" className="h-7 w-7 text-fat-red hover:text-red-700" onClick={() => removeFood(mealKey, idx)}>
                                                        <Trash2 className="w-3 h-3" />
                                                    </Button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                                <Button 
                                    variant="ghost" 
                                    className="w-full text-brand-orange hover:text-brand-orange-dark"
                                    onClick={() => { setAddFoodModal({ open: true, mealKey }); setSearchQuery(''); setSearchCategory(''); }}
                                >
                                    <Plus className="w-4 h-4 mr-1" /> Añadir ingrediente
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
            <div className="min-h-screen bg-bg-page flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-orange border-t-transparent" />
                    <p className="text-gray-500 text-sm">Cargando...</p>
                </div>
            </div>
        );
    }

    return (
        <div 
            className="min-h-screen pb-24 relative"
            style={{
                backgroundImage: `url('/gohan-light.png')`,
                backgroundSize: 'contain',
                backgroundPosition: 'center',
                backgroundRepeat: 'no-repeat',
                backgroundAttachment: 'fixed'
            }}
            data-testid="nutrition-page"
        >
            {/* Background overlay */}
            <div className="absolute inset-0 bg-bg-page/[0.95]" />
            
            {/* Content */}
            <div className="relative z-10">
                {/* Header */}
                <div className="bg-bg-dark sticky top-0 z-20">
                    <div className="max-w-lg mx-auto px-4 py-3">
                        <div className="flex items-center justify-between">
                            <Logo12EN12 />
                            <span className="text-gray-400 text-sm">Nutrición</span>
                        </div>
                    </div>
                </div>

                <div className="max-w-lg mx-auto px-4 py-4">
                    {/* Date & Day type */}
                    <Card className="bg-white shadow-md rounded-2xl mb-4">
                        <CardContent className="p-4">
                            {/* Date selector */}
                            <div className="flex items-center justify-between mb-4">
                                <Button variant="ghost" size="icon" onClick={() => changeDate(-1)}>
                                    <ChevronLeft className="w-5 h-5" />
                                </Button>
                                <div className="flex items-center gap-2">
                                    <Calendar className="w-4 h-4 text-brand-orange" />
                                    <span className="font-bold text-gray-900">{formatDate(currentDate)}</span>
                                </div>
                                <Button variant="ghost" size="icon" onClick={() => changeDate(1)}>
                                    <ChevronRight className="w-5 h-5" />
                                </Button>
                            </div>
                            
                            {/* Day type toggle */}
                            <div className="flex gap-2 mb-4">
                                <button 
                                    className={`flex-1 py-2 px-3 rounded-full text-sm font-semibold transition-all ${
                                        tipoDia === 'entrenamiento' 
                                            ? 'bg-brand-orange text-white shadow-md' 
                                            : 'bg-gray-100 text-gray-600'
                                    }`}
                                    onClick={() => setTipoDia('entrenamiento')}
                                >
                                    Día de entrenamiento
                                </button>
                                <button 
                                    className={`flex-1 py-2 px-3 rounded-full text-sm font-semibold transition-all ${
                                        tipoDia === 'descanso' 
                                            ? 'bg-gray-800 text-white shadow-md' 
                                            : 'bg-gray-100 text-gray-600'
                                    }`}
                                    onClick={() => setTipoDia('descanso')}
                                >
                                    Día de descanso
                                </button>
                            </div>

                            {/* Macro circles */}
                            <div className="flex justify-around">
                                <MacroCircle value={dayMacros.P} target={dayTarget.P_total || 1} label="Proteínas" color="protein" />
                                <MacroCircle value={dayMacros.H} target={dayTarget.H_total || 1} label="Hidratos" color="carbs" />
                                <MacroCircle value={dayMacros.G} target={dayTarget.G_total || 1} label="Grasas" color="fat" />
                            </div>
                        </CardContent>
                    </Card>

                    {/* Config */}
                    {tipoDia === 'entrenamiento' && (
                        <Collapsible open={configOpen} onOpenChange={setConfigOpen} className="mb-4">
                            <CollapsibleTrigger asChild>
                                <Button variant="ghost" className="w-full justify-between text-gray-500">
                                    <span className="flex items-center gap-2"><Settings className="w-4 h-4" /> Configuración</span>
                                    {configOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                </Button>
                            </CollapsibleTrigger>
                            <CollapsibleContent>
                                <Card className="mt-2 bg-white rounded-2xl shadow-md">
                                    <CardContent className="p-4 space-y-4">
                                        <div>
                                            <label className="text-sm font-semibold text-gray-700 mb-2 block">¿Cuándo entrenas?</label>
                                            <div className="flex flex-wrap gap-2">
                                                {[{ value: 0, label: 'Ayunas' }, { value: 1, label: 'Después C1' }, { value: 2, label: 'Después C2' }, ...(numComidas === 4 ? [{ value: 3, label: 'Después C3' }] : [])].map(opt => (
                                                    <Button 
                                                        key={opt.value}
                                                        variant={momentoEntreno === opt.value ? 'default' : 'outline'}
                                                        size="sm"
                                                        onClick={() => setMomentoEntreno(opt.value)}
                                                        className={`rounded-full ${momentoEntreno === opt.value ? 'bg-brand-orange hover:bg-brand-orange-dark' : ''}`}
                                                    >
                                                        {opt.label}
                                                    </Button>
                                                ))}
                                            </div>
                                        </div>
                                        <div>
                                            <label className="text-sm font-semibold text-gray-700 mb-2 block">Periworkout</label>
                                            <div className="flex flex-wrap gap-2">
                                                {[{ value: 'intra_post', label: 'Intra+Post' }, { value: 'solo_post', label: 'Solo Post' }, { value: 'solo_intra', label: 'Solo Intra' }, { value: 'sin_peri', label: 'Sin peri' }].map(opt => (
                                                    <Button 
                                                        key={opt.value}
                                                        variant={opcionPeri === opt.value ? 'default' : 'outline'}
                                                        size="sm"
                                                        onClick={() => setOpcionPeri(opt.value)}
                                                        className={`rounded-full ${opcionPeri === opt.value ? 'bg-brand-orange hover:bg-brand-orange-dark' : ''}`}
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
                        {getMealOrder().map(mealKey => <MealCard key={mealKey} mealKey={mealKey} />)}
                    </div>

                    {/* Action buttons */}
                    <div className="flex gap-2">
                        <Button 
                            className="flex-1 h-12 bg-black hover:bg-gray-900 text-white rounded-full font-bold"
                            onClick={saveDiet}
                        >
                            <Save className="w-5 h-5 mr-2" /> Guardar día
                        </Button>
                        <Button variant="outline" className="h-12 w-12 rounded-full" onClick={() => setCopyModalOpen(true)}>
                            <Copy className="w-5 h-5" />
                        </Button>
                    </div>
                </div>
            </div>

            {/* Search Modal */}
            <Dialog open={addFoodModal.open} onOpenChange={(open) => !open && setAddFoodModal({ open: false, mealKey: null })}>
                <DialogContent className="max-w-lg max-h-[90vh] flex flex-col p-0 gap-0">
                    <DialogHeader className="bg-bg-dark p-4">
                        <DialogTitle className="text-white flex items-center justify-between">
                            <span>Buscador de alimentos</span>
                            <span className="text-brand-orange text-sm">{addFoodModal.mealKey}</span>
                        </DialogTitle>
                        <DialogDescription className="sr-only">Busca alimentos</DialogDescription>
                    </DialogHeader>
                    
                    <div className="p-4 bg-white">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                            <Input 
                                placeholder="Escribe un alimento"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-10 h-12 rounded-xl bg-gray-100 border-0"
                                data-testid="search-food-input"
                            />
                        </div>
                    </div>
                    
                    <ScrollArea className="w-full whitespace-nowrap border-b bg-white">
                        <div className="flex gap-2 p-4 pt-0">
                            {CATEGORY_CHIPS.map(chip => (
                                <button 
                                    key={chip.value}
                                    onClick={() => setSearchCategory(chip.value)}
                                    className={`flex-shrink-0 px-3 py-2 rounded-full text-sm font-medium transition-all ${
                                        searchCategory === chip.value 
                                            ? 'bg-brand-orange text-white' 
                                            : 'bg-gray-800 text-white'
                                    }`}
                                >
                                    {chip.emoji} {chip.label}
                                </button>
                            ))}
                        </div>
                    </ScrollArea>
                    
                    <ScrollArea className="flex-1 bg-gray-50">
                        {searchLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <div className="animate-spin rounded-full h-8 w-8 border-4 border-brand-orange border-t-transparent" />
                            </div>
                        ) : searchResults.length === 0 ? (
                            <div className="text-center py-12">
                                <span className="text-4xl mb-3 block">🔍</span>
                                <p className="text-gray-500">Busca un alimento</p>
                            </div>
                        ) : (
                            <div className="p-4 space-y-2">
                                {searchResults.map(food => (
                                    <button
                                        key={food.id}
                                        className="w-full text-left p-4 bg-white rounded-xl shadow-sm hover:shadow-md transition-all"
                                        onClick={() => handleAddFood(food)}
                                    >
                                        <div className="flex items-start gap-3">
                                            <span className="text-2xl">{getFoodEmoji(food.categorias)}</span>
                                            <div className="flex-1">
                                                <p className="font-semibold text-gray-900">{food.nombre}</p>
                                                <p className="text-xs text-gray-500">{food.racion}g / 1 ración</p>
                                                <div className="flex gap-2 mt-2">
                                                    <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-carbs-green text-white">{food.proteinas}g proteínas</span>
                                                    <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-fat-red text-white">{food.grasas}g grasas</span>
                                                </div>
                                            </div>
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
                <DialogContent className="max-w-lg max-h-[90vh] flex flex-col p-0 gap-0">
                    <DialogHeader className="bg-bg-dark p-4">
                        <DialogTitle className="text-white">Elige tu menú</DialogTitle>
                        <DialogDescription className="text-gray-400">
                            {menuOptionsModal.mealKey && mealInfo[menuOptionsModal.mealKey]?.name}
                        </DialogDescription>
                    </DialogHeader>
                    
                    <ScrollArea className="flex-1 bg-gray-50">
                        {menuOptionsLoading ? (
                            <div className="flex flex-col items-center justify-center py-16">
                                <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-orange border-t-transparent mb-4" />
                                <p className="text-gray-500">Calculando opciones...</p>
                            </div>
                        ) : menuOptions.length === 0 ? (
                            <div className="text-center py-16">
                                <span className="text-4xl mb-3 block">🤷</span>
                                <p className="text-gray-500">No hay opciones disponibles</p>
                            </div>
                        ) : (
                            <div className="p-4 space-y-4">
                                {menuOptions.map((option, index) => {
                                    const letra = ['A', 'B', 'C'][index];
                                    return (
                                        <button
                                            key={option.plantilla_id}
                                            className="w-full text-left p-4 bg-white rounded-2xl shadow-md hover:shadow-lg transition-all"
                                            onClick={() => applyMenuOption(option)}
                                            data-testid={`menu-option-${letra}`}
                                        >
                                            <div className="flex items-start gap-4">
                                                <div className="w-12 h-12 rounded-full bg-brand-orange flex items-center justify-center text-white text-xl font-bold">
                                                    {letra}
                                                </div>
                                                <div className="flex-1">
                                                    <div className="flex items-center justify-between mb-2">
                                                        <h3 className="font-bold text-gray-900">{option.nombre}</h3>
                                                        {option.cuadrada && (
                                                            <span className="bg-carbs-green text-white text-xs px-2 py-0.5 rounded-full flex items-center gap-1">
                                                                <Check className="w-3 h-3" /> Cuadrada
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="space-y-1 mb-3">
                                                        {option.items.map((item, i) => (
                                                            <div key={i} className="flex justify-between text-sm">
                                                                <span className="text-gray-700">{item.nombre}</span>
                                                                <span className="text-gray-500 font-mono">{item.cantidad_g}g</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                    <div className="flex gap-2">
                                                        <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-carbs-green text-white">{option.macros_totales?.P?.toFixed(0)}P</span>
                                                        <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-500 text-white">{option.macros_totales?.H?.toFixed(0)}H</span>
                                                        <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-brand-orange text-white">{option.macros_totales?.G?.toFixed(0)}G</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </ScrollArea>
                </DialogContent>
            </Dialog>

            {/* Copy Modal */}
            <Dialog open={copyModalOpen} onOpenChange={setCopyModalOpen}>
                <DialogContent className="max-w-sm rounded-2xl">
                    <DialogHeader>
                        <DialogTitle>Copiar dieta</DialogTitle>
                        <DialogDescription className="sr-only">Copia esta dieta a otro día</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <p className="text-sm text-gray-600">Copiar dieta del <span className="font-semibold">{formatDate(currentDate)}</span> a:</p>
                        <Input type="date" value={copyDate} onChange={(e) => setCopyDate(e.target.value)} min={new Date().toISOString().split('T')[0]} className="h-12 rounded-xl" />
                        <div className="flex gap-2">
                            <Button variant="outline" className="flex-1 h-12 rounded-full" onClick={() => setCopyModalOpen(false)}>Cancelar</Button>
                            <Button className="flex-1 h-12 rounded-full bg-black hover:bg-gray-900" onClick={copyDiet}>Copiar</Button>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default NutritionPage;
