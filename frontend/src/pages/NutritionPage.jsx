import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../components/ui/collapsible';
import { toast } from 'sonner';
import { 
    ChevronLeft, ChevronRight, Calendar, Settings, Plus, Trash2, 
    Minus, Save, Copy, Check, AlertTriangle, ChevronDown, ChevronUp,
    Search, X
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Category chips mapping
const CATEGORY_CHIPS = [
    { label: 'Todas', value: '' },
    { label: 'Carnes', value: '2' },
    { label: 'Pescados', value: '3' },
    { label: 'Huevos', value: '1' },
    { label: 'Lácteos', value: '5' },
    { label: 'Proteína', value: '4' },
    { label: 'Cereales', value: '7' },
    { label: 'Panes', value: '8' },
    { label: 'Arroces', value: '21' },
    { label: 'Pasta', value: '22' },
    { label: 'Tubérculos', value: '9' },
    { label: 'Legumbres', value: '10' },
    { label: 'Fruta', value: '11' },
    { label: 'Verduras', value: '13' },
    { label: 'Grasas', value: '17' },
    { label: 'F. Secos', value: '17.2' },
    { label: 'Salsas', value: '16' },
    { label: 'Bebidas', value: '24' },
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
    
    // Meals data - alimentos añadidos por el usuario
    const [mealsData, setMealsData] = useState({});
    
    // UI state
    const [expandedMeals, setExpandedMeals] = useState({ C1: true });
    const [addFoodModal, setAddFoodModal] = useState({ open: false, mealKey: null });
    const [searchQuery, setSearchQuery] = useState('');
    const [searchCategory, setSearchCategory] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [searchLoading, setSearchLoading] = useState(false);
    const [copyModalOpen, setCopyModalOpen] = useState(false);
    const [copyDate, setCopyDate] = useState('');
    const [loading, setLoading] = useState(true);

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
            toast.error('Error cargando distribución de macros');
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
                
                // Recalculate macros for existing foods
                const updatedMeals = {};
                for (const [mealKey, mealData] of Object.entries(diet.comidas || {})) {
                    if (mealData.alimentos && mealData.alimentos.length > 0) {
                        const updatedFoods = await Promise.all(
                            mealData.alimentos.map(async (food) => {
                                // If food already has macros_efectivos, use them
                                if (food.macros_efectivos && food.macros_efectivos.P !== undefined) {
                                    return food;
                                }
                                // Otherwise recalculate
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
                // Reset meals for new day
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
        if (!addFoodModal.open) return;
        
        const timer = setTimeout(async () => {
            setSearchLoading(true);
            try {
                const params = new URLSearchParams();
                if (searchQuery) params.set('q', searchQuery);
                if (searchCategory) params.set('category', searchCategory);
                params.set('limit', '30');
                
                const result = await api(`/api/calculator/search?${params}`);
                setSearchResults(result.alimentos || []);
            } catch (err) {
                console.error('Search error:', err);
            }
            setSearchLoading(false);
        }, 300);
        
        return () => clearTimeout(timer);
    }, [searchQuery, searchCategory, addFoodModal.open, api]);

    // Navigation
    const changeDate = (days) => {
        const d = new Date(currentDate);
        d.setDate(d.getDate() + days);
        setCurrentDate(d.toISOString().split('T')[0]);
    };

    const formatDate = (dateStr) => {
        const d = new Date(dateStr);
        return d.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' });
    };

    // Get meal order based on momento_entreno
    const getMealOrder = () => {
        const baseMeals = numComidas === 3 ? ['C1', 'C2', 'C3'] : ['C1', 'C2', 'C3', 'C4'];
        
        if (tipoDia === 'descanso') return baseMeals;
        
        // Determine which peri meals to show
        const periMeals = [];
        if (opcionPeri === 'intra_post') {
            periMeals.push('Intra', 'Post');
        } else if (opcionPeri === 'solo_post') {
            periMeals.push('Post');
        } else if (opcionPeri === 'solo_intra') {
            periMeals.push('Intra');
        }
        
        if (periMeals.length === 0) return baseMeals;
        
        // Insert peri meals at correct position
        const result = [...baseMeals];
        const insertIndex = momentoEntreno; // 0=before C1, 1=after C1, etc.
        result.splice(insertIndex, 0, ...periMeals);
        
        return result;
    };

    // Calculate macros served for a meal
    const calculateMealMacros = (mealKey) => {
        const foods = mealsData[mealKey]?.alimentos || [];
        return foods.reduce((total, f) => ({
            P: total.P + (f.macros_efectivos?.P || 0),
            H: total.H + (f.macros_efectivos?.H || 0),
            G: total.G + (f.macros_efectivos?.G || 0)
        }), { P: 0, H: 0, G: 0 });
    };

    // Calculate total day macros
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

    // Get target macros for a meal
    const getMealTarget = (mealKey) => {
        if (!distribution) return { P: 0, H: 0, G: 0 };
        
        if (mealKey === 'Intra' || mealKey === 'Post') {
            return distribution.periworkout?.[mealKey] || { P: 0, H: 0, G: 0 };
        }
        return distribution.comidas?.[mealKey] || { P: 0, H: 0, G: 0 };
    };

    // Get remaining macros for a meal
    const getMealRemaining = (mealKey) => {
        const target = getMealTarget(mealKey);
        const served = calculateMealMacros(mealKey);
        return {
            P: Math.max(0, target.P - served.P),
            H: Math.max(0, target.H - served.H),
            G: Math.max(0, target.G - served.G)
        };
    };

    // Check meal status
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

    // Add food to meal
    const handleAddFood = async (food) => {
        const mealKey = addFoodModal.mealKey;
        const remaining = getMealRemaining(mealKey);
        
        try {
            // Get adjusted quantity from backend
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
                que_cuenta: result.que_cuenta
            };
            
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
        } catch (err) {
            toast.error('Error añadiendo alimento');
        }
    };

    // Update food quantity
    const updateFoodQuantity = async (mealKey, foodIndex, delta) => {
        const foods = [...(mealsData[mealKey]?.alimentos || [])];
        const food = foods[foodIndex];
        const newQuantity = Math.max(5, food.cantidad_g + delta);
        
        try {
            // Recalculate macros for new quantity
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

    // Remove food from meal
    const removeFood = (mealKey, foodIndex) => {
        setMealsData(prev => ({
            ...prev,
            [mealKey]: {
                alimentos: (prev[mealKey]?.alimentos || []).filter((_, i) => i !== foodIndex)
            }
        }));
    };

    // Save diet
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
            toast.success(`Dieta guardada para ${formatDate(currentDate)}`);
        } catch (err) {
            toast.error('Error guardando dieta');
        }
    };

    // Copy diet
    const copyDiet = async () => {
        if (!copyDate) {
            toast.error('Selecciona una fecha destino');
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
            toast.success(`Dieta copiada a ${formatDate(copyDate)}`);
            setCopyModalOpen(false);
            setCopyDate('');
        } catch (err) {
            toast.error('Error copiando dieta');
        }
    };

    // Progress bar component
    const ProgressBar = ({ value, max, color, label }) => {
        const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
        const isOver = value > max;
        return (
            <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-medium w-6" style={{ color }}>{label}</span>
                <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                        className="h-full rounded-full transition-all" 
                        style={{ 
                            width: `${pct}%`, 
                            backgroundColor: isOver ? '#EF4444' : color 
                        }} 
                    />
                </div>
                <span className="text-xs text-gray-600 w-20 text-right">
                    {value.toFixed(0)}/{max.toFixed(0)}g
                </span>
            </div>
        );
    };

    // Meal card component
    const MealCard = ({ mealKey }) => {
        const isExpanded = expandedMeals[mealKey];
        const target = getMealTarget(mealKey);
        const served = calculateMealMacros(mealKey);
        const status = getMealStatus(mealKey);
        const foods = mealsData[mealKey]?.alimentos || [];
        const isPeri = mealKey === 'Intra' || mealKey === 'Post';
        
        const mealNames = {
            C1: 'Comida 1', C2: 'Comida 2', C3: 'Comida 3', C4: 'Comida 4',
            Intra: 'Intra-entreno', Post: 'Post-entreno'
        };
        
        const statusColors = {
            cuadrada: 'bg-green-100 text-green-800',
            falta: 'bg-yellow-100 text-yellow-800',
            sobra: 'bg-red-100 text-red-800'
        };
        
        const statusIcons = {
            cuadrada: <Check className="w-3 h-3" />,
            falta: <AlertTriangle className="w-3 h-3" />,
            sobra: <AlertTriangle className="w-3 h-3" />
        };

        return (
            <Card className="mb-2 bg-white shadow-sm border border-gray-200">
                <button 
                    className="w-full"
                    onClick={() => setExpandedMeals(prev => ({ ...prev, [mealKey]: !isExpanded }))}
                >
                    <div className={`flex items-center justify-between p-3 border-l-4 ${foods.length > 0 ? 'border-l-orange-500' : 'border-l-gray-300'}`}>
                        <div className="flex items-center gap-2">
                            {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
                            <span className="font-semibold text-gray-800">{mealNames[mealKey]}</span>
                            <span className="text-xs text-gray-500">
                                {target.P.toFixed(0)}P | {target.H.toFixed(0)}H {!isPeri && `| ${target.G.toFixed(0)}G`}
                            </span>
                        </div>
                        {foods.length > 0 && (
                            <span className={`px-2 py-0.5 rounded-full text-xs flex items-center gap-1 ${statusColors[status]}`}>
                                {statusIcons[status]}
                                {status === 'cuadrada' ? 'OK' : status}
                            </span>
                        )}
                    </div>
                </button>
                
                {isExpanded && (
                    <CardContent className="pt-0 pb-3 px-3">
                        {/* Progress bars */}
                        <div className="mb-3">
                            <ProgressBar value={served.P} max={target.P} color="#4CAF50" label="P" />
                            <ProgressBar value={served.H} max={target.H} color="#2196F3" label="H" />
                            {!isPeri && <ProgressBar value={served.G} max={target.G} color="#FF5722" label="G" />}
                        </div>
                        
                        {/* Foods list */}
                        {foods.length === 0 ? (
                            <p className="text-sm text-gray-400 text-center py-2">Sin alimentos</p>
                        ) : (
                            <div className="space-y-2 mb-3">
                                {foods.map((food, idx) => (
                                    <div key={idx} className="flex items-center justify-between bg-gray-50 rounded-lg p-2">
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-gray-800 truncate">{food.nombre}</p>
                                            <p className="text-xs text-gray-500">
                                                <span className="text-green-600">{(food.macros_efectivos?.P ?? 0).toFixed(0)}P</span>
                                                {' | '}
                                                <span className="text-blue-600">{(food.macros_efectivos?.H ?? 0).toFixed(0)}H</span>
                                                {' | '}
                                                <span className="text-orange-600">{(food.macros_efectivos?.G ?? 0).toFixed(0)}G</span>
                                            </p>
                                        </div>
                                        <div className="flex items-center gap-1 ml-2">
                                            <Button 
                                                variant="ghost" 
                                                size="icon" 
                                                className="h-7 w-7"
                                                onClick={() => updateFoodQuantity(mealKey, idx, -10)}
                                            >
                                                <Minus className="w-3 h-3" />
                                            </Button>
                                            <span className="text-sm font-medium w-12 text-center">{food.cantidad_g}g</span>
                                            <Button 
                                                variant="ghost" 
                                                size="icon" 
                                                className="h-7 w-7"
                                                onClick={() => updateFoodQuantity(mealKey, idx, 10)}
                                            >
                                                <Plus className="w-3 h-3" />
                                            </Button>
                                            <Button 
                                                variant="ghost" 
                                                size="icon" 
                                                className="h-7 w-7 text-red-500 hover:text-red-700"
                                                onClick={() => removeFood(mealKey, idx)}
                                            >
                                                <Trash2 className="w-3 h-3" />
                                            </Button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                        
                        {/* Add food button */}
                        <Button 
                            variant="outline" 
                            className="w-full border-dashed"
                            onClick={() => setAddFoodModal({ open: true, mealKey })}
                        >
                            <Plus className="w-4 h-4 mr-1" /> Añadir alimento
                        </Button>
                    </CardContent>
                )}
            </Card>
        );
    };

    // Calculate totals
    const dayMacros = calculateDayMacros();
    const dayTarget = distribution?.resumen || { P_total: 0, H_total: 0, G_total: 0, kcal_total: 0 };
    const dayKcal = dayMacros.P * 4 + dayMacros.H * 4 + dayMacros.G * 9;

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 pb-20" data-testid="nutrition-page">
            {/* Header */}
            <div className="bg-white shadow-sm sticky top-0 z-10">
                <div className="max-w-lg mx-auto px-4 py-3">
                    {/* Date navigation */}
                    <div className="flex items-center justify-between mb-3">
                        <Button variant="ghost" size="icon" onClick={() => changeDate(-1)}>
                            <ChevronLeft className="w-5 h-5" />
                        </Button>
                        <div className="flex items-center gap-2">
                            <Calendar className="w-4 h-4 text-gray-500" />
                            <span className="font-semibold text-gray-800">{formatDate(currentDate)}</span>
                        </div>
                        <Button variant="ghost" size="icon" onClick={() => changeDate(1)}>
                            <ChevronRight className="w-5 h-5" />
                        </Button>
                    </div>
                    
                    {/* Day type toggle */}
                    <div className="flex justify-center gap-2 mb-2">
                        <Button 
                            variant={tipoDia === 'entrenamiento' ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => setTipoDia('entrenamiento')}
                            className={tipoDia === 'entrenamiento' ? 'bg-orange-500 hover:bg-orange-600' : ''}
                            data-testid="btn-entrenamiento"
                        >
                            Entreno
                        </Button>
                        <Button 
                            variant={tipoDia === 'descanso' ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => setTipoDia('descanso')}
                            className={tipoDia === 'descanso' ? 'bg-gray-600 hover:bg-gray-700' : ''}
                            data-testid="btn-descanso"
                        >
                            Descanso
                        </Button>
                    </div>
                </div>
            </div>

            <div className="max-w-lg mx-auto px-4 py-4">
                {/* Configuration section */}
                {tipoDia === 'entrenamiento' && (
                    <Collapsible open={configOpen} onOpenChange={setConfigOpen} className="mb-4">
                        <CollapsibleTrigger asChild>
                            <Button variant="ghost" className="w-full justify-between text-gray-600">
                                <span className="flex items-center gap-2">
                                    <Settings className="w-4 h-4" />
                                    Configuración
                                </span>
                                {configOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                            </Button>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                            <Card className="mt-2 bg-white">
                                <CardContent className="p-4 space-y-4">
                                    {/* Number of meals */}
                                    <div>
                                        <label className="text-sm font-medium text-gray-700 mb-2 block">Comidas</label>
                                        <div className="flex gap-2">
                                            {[3, 4].map(n => (
                                                <Button 
                                                    key={n}
                                                    variant={numComidas === n ? 'default' : 'outline'}
                                                    size="sm"
                                                    onClick={() => setNumComidas(n)}
                                                    className={numComidas === n ? 'bg-orange-500 hover:bg-orange-600' : ''}
                                                >
                                                    {n} comidas
                                                </Button>
                                            ))}
                                        </div>
                                    </div>
                                    
                                    {/* Training moment */}
                                    <div>
                                        <label className="text-sm font-medium text-gray-700 mb-2 block">Entrenas después de</label>
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
                                                    className={momentoEntreno === opt.value ? 'bg-orange-500 hover:bg-orange-600' : ''}
                                                >
                                                    {opt.label}
                                                </Button>
                                            ))}
                                        </div>
                                    </div>
                                    
                                    {/* Periworkout */}
                                    <div>
                                        <label className="text-sm font-medium text-gray-700 mb-2 block">Periworkout</label>
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
                                                    className={opcionPeri === opt.value ? 'bg-orange-500 hover:bg-orange-600' : ''}
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

                {/* Day summary */}
                <Card className={`mb-4 ${
                    Math.abs(dayMacros.P - dayTarget.P_total) <= 4 && 
                    Math.abs(dayMacros.H - dayTarget.H_total) <= 4 && 
                    Math.abs(dayMacros.G - dayTarget.G_total) <= 4 
                        ? 'bg-green-50 border-green-200' 
                        : 'bg-white'
                }`}>
                    <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-3">
                            <h2 className="font-semibold text-gray-800">
                                {tipoDia === 'entrenamiento' ? 'Día de Entreno' : 'Día de Descanso'}
                            </h2>
                            <span className="text-sm text-gray-500">
                                {dayKcal.toFixed(0)} / {dayTarget.kcal_total?.toFixed(0) || 0} kcal
                            </span>
                        </div>
                        <div className="grid grid-cols-3 gap-4">
                            <div className="text-center">
                                <div className="text-2xl font-bold text-green-600">{dayMacros.P.toFixed(0)}</div>
                                <div className="text-xs text-gray-500">/ {dayTarget.P_total?.toFixed(0) || 0}g P</div>
                            </div>
                            <div className="text-center">
                                <div className="text-2xl font-bold text-blue-600">{dayMacros.H.toFixed(0)}</div>
                                <div className="text-xs text-gray-500">/ {dayTarget.H_total?.toFixed(0) || 0}g H</div>
                            </div>
                            <div className="text-center">
                                <div className="text-2xl font-bold text-orange-600">{dayMacros.G.toFixed(0)}</div>
                                <div className="text-xs text-gray-500">/ {dayTarget.G_total?.toFixed(0) || 0}g G</div>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Meals accordion */}
                <div className="space-y-2 mb-4">
                    {getMealOrder().map(mealKey => (
                        <MealCard key={mealKey} mealKey={mealKey} />
                    ))}
                </div>

                {/* Action buttons */}
                <div className="flex gap-2">
                    <Button 
                        className="flex-1 bg-orange-500 hover:bg-orange-600"
                        onClick={saveDiet}
                        data-testid="save-diet-btn"
                    >
                        <Save className="w-4 h-4 mr-2" /> Guardar día
                    </Button>
                    <Button 
                        variant="outline" 
                        onClick={() => setCopyModalOpen(true)}
                        data-testid="copy-diet-btn"
                    >
                        <Copy className="w-4 h-4" />
                    </Button>
                </div>
            </div>

            {/* Add food modal */}
            <Dialog open={addFoodModal.open} onOpenChange={(open) => !open && setAddFoodModal({ open: false, mealKey: null })}>
                <DialogContent className="max-w-lg max-h-[90vh] flex flex-col">
                    <DialogHeader>
                        <DialogTitle>Añadir alimento</DialogTitle>
                        <DialogDescription className="sr-only">Busca y selecciona alimentos para añadir a tu comida</DialogDescription>
                    </DialogHeader>
                    
                    {/* Search input */}
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <Input 
                            placeholder="Buscar alimento..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-10 pr-10"
                            data-testid="search-food-input"
                        />
                        {searchQuery && (
                            <button 
                                className="absolute right-3 top-1/2 -translate-y-1/2"
                                onClick={() => setSearchQuery('')}
                            >
                                <X className="w-4 h-4 text-gray-400" />
                            </button>
                        )}
                    </div>
                    
                    {/* Category chips */}
                    <ScrollArea className="w-full whitespace-nowrap pb-2">
                        <div className="flex gap-2 px-1">
                            {CATEGORY_CHIPS.map(chip => (
                                <Button 
                                    key={chip.value}
                                    variant={searchCategory === chip.value ? 'default' : 'outline'}
                                    size="sm"
                                    onClick={() => setSearchCategory(chip.value)}
                                    className={`flex-shrink-0 ${searchCategory === chip.value ? 'bg-orange-500 hover:bg-orange-600' : ''}`}
                                >
                                    {chip.label}
                                </Button>
                            ))}
                        </div>
                    </ScrollArea>
                    
                    {/* Results */}
                    <ScrollArea className="flex-1 -mx-6 px-6">
                        {searchLoading ? (
                            <div className="flex items-center justify-center py-8">
                                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-orange-500" />
                            </div>
                        ) : searchResults.length === 0 ? (
                            <p className="text-center text-gray-400 py-8">
                                {searchQuery || searchCategory ? 'Sin resultados' : 'Busca un alimento'}
                            </p>
                        ) : (
                            <div className="space-y-2 py-2">
                                {searchResults.map(food => (
                                    <button
                                        key={food.id}
                                        className="w-full text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
                                        onClick={() => handleAddFood(food)}
                                        data-testid={`food-result-${food.id}`}
                                    >
                                        <p className="font-medium text-gray-800 text-sm">{food.nombre}</p>
                                        <p className="text-xs text-gray-500">
                                            <span className="text-green-600">{food.proteinas}P</span>
                                            {' | '}
                                            <span className="text-blue-600">{food.hidratos}H</span>
                                            {' | '}
                                            <span className="text-orange-600">{food.grasas}G</span>
                                            <span className="text-gray-400 ml-2">({food.racion}g)</span>
                                        </p>
                                    </button>
                                ))}
                            </div>
                        )}
                    </ScrollArea>
                </DialogContent>
            </Dialog>

            {/* Copy diet modal */}
            <Dialog open={copyModalOpen} onOpenChange={setCopyModalOpen}>
                <DialogContent className="max-w-sm">
                    <DialogHeader>
                        <DialogTitle>Copiar dieta</DialogTitle>
                        <DialogDescription className="sr-only">Selecciona una fecha destino para copiar la dieta actual</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <p className="text-sm text-gray-600">
                            Copiar dieta del {formatDate(currentDate)} a:
                        </p>
                        <Input 
                            type="date"
                            value={copyDate}
                            onChange={(e) => setCopyDate(e.target.value)}
                            min={new Date().toISOString().split('T')[0]}
                        />
                        <div className="flex gap-2">
                            <Button variant="outline" className="flex-1" onClick={() => setCopyModalOpen(false)}>
                                Cancelar
                            </Button>
                            <Button className="flex-1 bg-orange-500 hover:bg-orange-600" onClick={copyDiet}>
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
