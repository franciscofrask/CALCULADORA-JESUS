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
    ChevronLeft, ChevronRight, Plus, Trash2, 
    Minus, Save, Copy, Check, ChevronDown, ChevronUp,
    Search, X, Zap, Wrench, RefreshCw, ArrowUpRight, Calendar
} from 'lucide-react';
import PreferencesSetup, { PREFERENCE_CATEGORIES } from '../components/nutrition/PreferencesSetup';

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

// Category filter chips - Categorías completas para buscador general
const CATEGORY_CHIPS = [
    { label: 'Todas', value: '', emoji: '🍽️' },
    { label: 'Huevos', value: '1', emoji: '🥚' },
    { label: 'Carnes', value: '2', emoji: '🥩' },
    { label: 'Pescados', value: '3', emoji: '🐟' },
    { label: 'Prot. polvo', value: '4', emoji: '💪' },
    { label: 'Lácteos', value: '5', emoji: '🥛' },
    { label: 'Soja', value: '6', emoji: '🫘' },
    { label: 'Cereales', value: '7', emoji: '🌾' },
    { label: 'Panes', value: '8', emoji: '🍞' },
    { label: 'Tubérculos', value: '9', emoji: '🥔' },
    { label: 'Legumbres', value: '10', emoji: '🫘' },
    { label: 'Frutas', value: '11', emoji: '🍎' },
    { label: 'Verduras', value: '13', emoji: '🥦' },
    { label: 'Salsas', value: '16', emoji: '🥫' },
    { label: 'Grasas', value: '17', emoji: '🫒' },
    { label: 'Intraentreno', value: '18', emoji: '⚡' },
    { label: 'Bebidas', value: '19', emoji: '☕' },
    { label: 'Arroces', value: '21', emoji: '🍚' },
    { label: 'Pasta', value: '22', emoji: '🍝' },
    { label: 'Beb. vegetales', value: '24', emoji: '🥤' },
    { label: 'Sustitutivos', value: '27', emoji: '🥤' },
    { label: 'Prot. vegetal', value: '28', emoji: '🌱' },
    { label: 'Barritas prot.', value: '29', emoji: '🍫' },
    { label: 'Bollería', value: '31', emoji: '🥐' },
    { label: 'Pizza/Lasaña', value: '32', emoji: '🍕' },
    { label: 'Chocolate', value: '34', emoji: '🍫' },
    { label: 'Helados', value: '35', emoji: '🍦' },
    { label: 'Postres', value: '36', emoji: '🍮' },
    { label: 'Cacao/Azúcar', value: '37', emoji: '🍯' },
    { label: 'Aperitivos', value: '38', emoji: '🍟' },
    { label: 'Cocina española', value: '39', emoji: '🥘' },
    { label: 'Aminoácidos', value: '41', emoji: '⚡' },
    { label: 'Barritas energ.', value: '47', emoji: '🍫' },
    { label: 'Sopas', value: '48', emoji: '🍲' },
    { label: 'Comida rápida', value: '49', emoji: '🍔' },
    { label: 'Comida asiática', value: '50', emoji: '🍜' },
    { label: 'Comida prep.', value: '53', emoji: '📦' },
];

// Momento entreno options
const MOMENTO_OPTIONS = [
    { value: 0, label: 'En ayunas' },
    { value: 1, label: 'Después de Comida 1' },
    { value: 2, label: 'Después de Comida 2' },
    { value: 3, label: 'Después de Comida 3' },
];

// Periworkout options
const PERI_OPTIONS = [
    { value: 'intra_post', label: 'Intra + Post' },
    { value: 'solo_post', label: 'Solo Post' },
    { value: 'solo_intra', label: 'Solo Intra' },
    { value: 'sin_peri', label: 'Sin periworkout' },
];

// Categories for Build Meal Modal - Step 1 (Proteínas) - Con prefixes para foods-sorted
const PROTEIN_CATEGORIES = [
    { id: 'huevos', label: 'Huevos', emoji: '🥚', prefixes: ['1'] },
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

// ==================== BUILD MEAL MODAL COMPONENT ====================
// Reescrito según especificaciones: NO muestra alimentos hasta que se pinche una categoría
const BuildMealModal = ({ 
    open, mealKey, mode = 'normal', onClose, getMealTarget, mealInfo, api, tipoDia, mealsData, setMealsData, getFoodEmoji, userPreferences = []
}) => {
    // Estados principales
    const [paso, setPaso] = useState(1);
    const [tempFoods, setTempFoods] = useState([]);
    
    // Estado de categoría seleccionada - null = vista de botones de categoría
    const [selectedCategory, setSelectedCategory] = useState(null);
    const [categoryFoods, setCategoryFoods] = useState([]);
    const [loadingFoods, setLoadingFoods] = useState(false);
    
    // Búsqueda
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [isSearching, setIsSearching] = useState(false);
    
    // Selected food for quantity adjustment (BUG 4 fix)
    const [selectedFood, setSelectedFood] = useState(null);
    const [adjustedQuantity, setAdjustedQuantity] = useState(0);
    const [adjustedMacros, setAdjustedMacros] = useState({ P: 0, H: 0, G: 0 });
    
    // Mode-specific config
    const isIntraMode = mode === 'intra';
    const isPostMode = mode === 'post';
    const isPeriMode = isIntraMode || isPostMode;
    
    // Calculate served and remaining macros
    const target = mealKey ? getMealTarget(mealKey) : { P: 0, H: 0, G: 0 };
    const served = tempFoods.reduce((acc, f) => ({
        P: acc.P + (f.macros_efectivos?.P || 0),
        H: acc.H + (f.macros_efectivos?.H || 0),
        G: acc.G + (f.macros_efectivos?.G || 0)
    }), { P: 0, H: 0, G: 0 });
    const remaining = {
        P: Math.max(0, target.P - served.P),
        H: Math.max(0, target.H - served.H),
        G: Math.max(0, target.G - served.G)
    };
    
    // Check if meal is "cuadrada"
    const isCuadrada = Math.abs(target.P - served.P) <= 4 && 
                       Math.abs(target.H - served.H) <= 4 && 
                       (isPeriMode || Math.abs(target.G - served.G) <= 4);
    
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
        // Paso 3 - Últimos toques: use user preferences
        if (paso === 3 && userPreferences && userPreferences.length > 0) {
            return PREFERENCE_CATEGORIES
                .filter(cat => userPreferences.includes(cat.id))
                .map(cat => ({
                    ...cat,
                    emoji: preferenceEmojis[cat.id] || '🍽️'
                }));
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
    
    // Auto-advance paso based on macros (single useEffect)
    useEffect(() => {
        if (tempFoods.length === 0) {
            if (paso !== 1) {
                setPaso(1);
                setSelectedCategory(null);
                setCategoryFoods([]);
            }
            return;
        }
        
        if (isIntraMode) return; // Intra no tiene pasos
        
        const pPct = target.P > 0 ? (served.P / target.P) * 100 : 100;
        const hPct = target.H > 0 ? (served.H / target.H) * 100 : 100;
        
        if (pPct < 80) {
            // Proteínas NO llegan al 80% → SIEMPRE paso 1
            if (paso !== 1) {
                setPaso(1);
                setSelectedCategory(null);
                setCategoryFoods([]);
            }
        } else if (pPct >= 80 && hPct < 80) {
            // Proteínas OK pero hidratos no → paso 2
            if (paso !== 2) {
                setPaso(2);
                setSelectedCategory(null);
                setCategoryFoods([]);
                toast.info('✅ Proteínas cubiertas. Elige el acompañamiento.');
            }
        } else if (pPct >= 80 && hPct >= 80) {
            // Ambos OK → paso 3
            if (paso !== 3) {
                setPaso(3);
                setSelectedCategory(null);
                setCategoryFoods([]);
                toast.info('✨ ¡Macros cubiertos! Últimos toques.');
            }
        }
    }, [served.P, served.H, target.P, target.H, tempFoods.length, paso, isIntraMode]);
    
    // Handle category click - load foods from that category
    const handleCategoryClick = async (category) => {
        setSelectedCategory(category);
        setLoadingFoods(true);
        setCategoryFoods([]);
        
        try {
            const result = await api('/api/calculator/foods-sorted', {
                method: 'POST',
                body: JSON.stringify({
                    category_prefixes: category.prefixes,
                    macros_restantes: { P: remaining.P, H: remaining.H, G: remaining.G },
                    limit: 200
                })
            });
            setCategoryFoods(result.alimentos || []);
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
                limit: '50' 
            });
            
            // Add tipo_comida filter for intra/post modes
            if (isIntraMode) params.set('tipo_comida', 'intra');
            else if (isPostMode) params.set('tipo_comida', 'post');
            
            const result = await api(`/api/calculator/search?${params}`);
            setSearchResults(result.alimentos || []);
        } catch (err) {
            console.error('Error buscando:', err);
        } finally {
            setLoadingFoods(false);
        }
    };
    
    // Handle select food - add directly
    const handleSelectFood = async (food) => {
        if (tempFoods.length >= MAX_FOODS) {
            toast.warning(`Máximo ${MAX_FOODS} alimentos por comida`);
            return;
        }
        
        try {
            // Use pre-calculated values if available, otherwise calculate
            let quantity = food._cantidad_sugerida;
            let macrosEf = food._macros_sugeridos;
            
            if (!quantity || !macrosEf) {
                const result = await api('/api/calculator/adjust', {
                    method: 'POST',
                    body: JSON.stringify({
                        alimento_id: food.id || food._id,
                        macros_restantes: remaining,
                        es_vegano: false
                    })
                });
                quantity = result.cantidad_g;
                macrosEf = result.macros_efectivos;
            }
            
            // Check if exceeds macros
            const newServed = {
                P: served.P + (macrosEf?.P || 0),
                H: served.H + (macrosEf?.H || 0),
                G: served.G + (macrosEf?.G || 0)
            };
            
            const overP = newServed.P - target.P;
            const overH = newServed.H - target.H;
            const overG = newServed.G - target.G;
            
            if (overP > 4 || overH > 4 || (!isPeriMode && overG > 4)) {
                const overMacros = [];
                if (overP > 4) overMacros.push('P +' + Math.round(overP) + 'g');
                if (overH > 4) overMacros.push('H +' + Math.round(overH) + 'g');
                if (!isPeriMode && overG > 4) overMacros.push('G +' + Math.round(overG) + 'g');
                toast.warning('⚠️ Te pasarías de: ' + overMacros.join(' | '));
            }
            
            const newFood = {
                alimento_id: food.id || food._id,
                nombre: food.nombre,
                cantidad_g: quantity,
                macros_efectivos: macrosEf,
                categorias: food.categorias,
                racion: food.racion,
                url: food.url || food.enlace || null
            };
            
            setTempFoods(prev => [...prev, newFood]);
            toast.success(`${food.nombre.substring(0, 30)}... añadido`);
            
            // Return to categories
            setSelectedCategory(null);
            setCategoryFoods([]);
            setSearchQuery('');
            setSearchResults([]);
            setIsSearching(false);
        } catch (err) {
            toast.error('Error añadiendo alimento');
            console.error(err);
        }
    };
    
    // Handle remove food
    const handleRemoveFood = (index) => {
        setTempFoods(prev => prev.filter((_, i) => i !== index));
    };
    
    // Handle clear meal
    const handleClearMeal = () => {
        setTempFoods([]);
        setPaso(1);
        setSelectedCategory(null);
        setCategoryFoods([]);
        setSearchQuery('');
        setSearchResults([]);
        setIsSearching(false);
    };
    
    // Save and close
    const handleSaveAndClose = () => {
        if (tempFoods.length === 0) {
            onClose();
            return;
        }
        
        setMealsData(prev => ({
            ...prev,
            [mealKey]: { alimentos: tempFoods }
        }));
        
        toast.success('Comida guardada');
        onClose();
    };
    
    // Get modal title based on mode
    const getModalTitle = () => {
        if (isIntraMode) return 'INTRA-ENTRENO';
        if (isPostMode) return 'POST-ENTRENO';
        return 'LO HAGO YO';
    };
    
    // Get step title
    const getStepTitle = () => {
        if (isIntraMode) return 'Elige tus alimentos intra';
        if (paso === 1) return 'PASO 1: ELIGE TU PROTEÍNA';
        if (paso === 2) return 'PASO 2: ELIGE ACOMPAÑAMIENTO';
        return '✨ ÚLTIMOS TOQUES';
    };
    
    // Format macro value
    const formatMacro = (val) => {
        if (!val || val === 0) return null;
        return Math.round(val);
    };
    
    // BUG 4: Handle food click - show adjustment panel
    const handleFoodClick = (food) => {
        const qty = food._cantidad_sugerida || food._config?.defecto || 100;
        const config = food._config || { minimo: 10, incremento: 25 };
        
        // If quantity is 0, use minimum
        const finalQty = qty === 0 ? config.minimo : qty;
        
        setSelectedFood(food);
        setAdjustedQuantity(finalQty);
        setAdjustedMacros(food._macros_sugeridos || { P: 0, H: 0, G: 0 });
    };
    
    // BUG 4: Handle quantity change in adjustment panel
    const handleQuantityChange = (delta) => {
        if (!selectedFood) return;
        
        const config = selectedFood._config || { minimo: 10, incremento: 25 };
        const nombre = (selectedFood.nombre || "").toLowerCase();
        
        // BUG 7: Hamburguesas con incremento de 0.5 unidades
        let increment = config.incremento || 25;
        if (nombre.includes("hamburguesa")) {
            const racion = selectedFood.racion || 100;
            increment = Math.round(racion * 0.5); // 0.5 unidades
        }
        
        const newQty = Math.max(config.minimo || 10, adjustedQuantity + (delta * increment));
        setAdjustedQuantity(newQty);
        
        // Recalcular macros localmente
        const baseQty = selectedFood._cantidad_sugerida || 100;
        const baseMacros = selectedFood._macros_sugeridos || { P: 0, H: 0, G: 0 };
        if (baseQty > 0) {
            const ratio = newQty / baseQty;
            setAdjustedMacros({
                P: Math.round((baseMacros.P || 0) * ratio * 10) / 10,
                H: Math.round((baseMacros.H || 0) * ratio * 10) / 10,
                G: Math.round((baseMacros.G || 0) * ratio * 10) / 10
            });
        }
    };
    
    // BUG 4: Confirm add with adjusted quantity
    const handleConfirmAdd = () => {
        if (!selectedFood) return;
        
        // Verificar sobrepaso
        const newServed = {
            P: served.P + (adjustedMacros.P || 0),
            H: served.H + (adjustedMacros.H || 0),
            G: served.G + (adjustedMacros.G || 0)
        };
        
        if (newServed.P > target.P + 4 || newServed.H > target.H + 4 || (!isPeriMode && newServed.G > target.G + 4)) {
            const overParts = [];
            if (newServed.P > target.P + 4) overParts.push('P +' + Math.round(newServed.P - target.P) + 'g');
            if (newServed.H > target.H + 4) overParts.push('H +' + Math.round(newServed.H - target.H) + 'g');
            if (!isPeriMode && newServed.G > target.G + 4) overParts.push('G +' + Math.round(newServed.G - target.G) + 'g');
            toast.warning('⚠️ Te pasarías: ' + overParts.join(' | '));
        }
        
        const newFood = {
            alimento_id: selectedFood.id || selectedFood._id,
            nombre: selectedFood.nombre,
            cantidad_g: adjustedQuantity,
            macros_efectivos: adjustedMacros,
            categorias: selectedFood.categorias,
            url: selectedFood.url || selectedFood.enlace || null,
            _config: selectedFood._config || null
        };
        
        setTempFoods(prev => [...prev, newFood]);
        setSelectedFood(null);
        toast.success(`${selectedFood.nombre.substring(0, 30)}... añadido`);
        
        // Return to categories
        setSelectedCategory(null);
        setCategoryFoods([]);
    };
    
    // Food row component with adjustment panel (BUG 4)
    const FoodRow = ({ food }) => {
        const macros = food._macros_sugeridos || food.macros_efectivos || {};
        const quantity = food._formatted_qty || `${food._cantidad_sugerida || food.racion || 100}g`;
        const hasUrl = food.url || food.enlace;
        const isSelected = selectedFood && (selectedFood.id || selectedFood._id) === (food.id || food._id);
        
        const macroParts = [];
        if (macros.P > 0) macroParts.push(<span key="p" className="text-green-600">{formatMacro(macros.P)}P</span>);
        if (macros.H > 0) macroParts.push(<span key="h" className="text-blue-600">{formatMacro(macros.H)}H</span>);
        if (macros.G > 0) macroParts.push(<span key="g" className="text-orange-500">{formatMacro(macros.G)}G</span>);
        
        // If this food is selected, show adjustment panel
        if (isSelected) {
            const adjMacroParts = [];
            if (adjustedMacros.P > 0) adjMacroParts.push(<span key="p" className="text-green-600">{formatMacro(adjustedMacros.P)}P</span>);
            if (adjustedMacros.H > 0) adjMacroParts.push(<span key="h" className="text-blue-600">{formatMacro(adjustedMacros.H)}H</span>);
            if (adjustedMacros.G > 0) adjMacroParts.push(<span key="g" className="text-orange-500">{formatMacro(adjustedMacros.G)}G</span>);
            
            const wouldExceed = (served.P + adjustedMacros.P > target.P + 4) || 
                               (served.H + adjustedMacros.H > target.H + 4) || 
                               (!isPeriMode && served.G + adjustedMacros.G > target.G + 4);
            
            return (
                <div className={`p-4 rounded-xl border-2 ${isIntraMode ? 'border-yellow-400 bg-yellow-50' : isPostMode ? 'border-green-400 bg-green-50' : 'border-brand-orange bg-orange-50'}`}>
                    <div className="flex items-center gap-2 mb-3">
                        <span className="text-xl">{getFoodEmoji(food.categorias)}</span>
                        <p className="font-bold text-gray-900 truncate flex-1">{food.nombre}</p>
                    </div>
                    
                    {/* Quantity adjuster */}
                    <div className="flex items-center justify-center gap-3 mb-3">
                        <button
                            onClick={() => handleQuantityChange(-1)}
                            className="w-10 h-10 rounded-full bg-gray-200 hover:bg-gray-300 flex items-center justify-center font-bold text-xl"
                        >
                            −
                        </button>
                        <input
                            type="number"
                            value={adjustedQuantity}
                            onChange={(e) => {
                                const val = parseInt(e.target.value) || 0;
                                setAdjustedQuantity(val);
                                // Recalculate macros
                                const baseQty = selectedFood._cantidad_sugerida || 100;
                                const baseMacros = selectedFood._macros_sugeridos || { P: 0, H: 0, G: 0 };
                                if (baseQty > 0) {
                                    const ratio = val / baseQty;
                                    setAdjustedMacros({
                                        P: Math.round((baseMacros.P || 0) * ratio * 10) / 10,
                                        H: Math.round((baseMacros.H || 0) * ratio * 10) / 10,
                                        G: Math.round((baseMacros.G || 0) * ratio * 10) / 10
                                    });
                                }
                            }}
                            className="w-24 h-12 text-center text-2xl font-bold border-2 border-brand-orange rounded-lg bg-white"
                        />
                        <span className="text-lg font-medium text-gray-600">g</span>
                        <button
                            onClick={() => handleQuantityChange(1)}
                            className="w-10 h-10 rounded-full bg-gray-200 hover:bg-gray-300 flex items-center justify-center font-bold text-xl"
                        >
                            +
                        </button>
                    </div>
                    
                    {/* Macros display */}
                    <div className="text-center mb-3">
                        {adjMacroParts.length > 0 ? (
                            <p className="text-lg font-semibold">
                                {adjMacroParts.map((part, i) => (
                                    <span key={i}>
                                        {i > 0 && <span className="text-gray-300 mx-1">|</span>}
                                        {part}
                                    </span>
                                ))}
                            </p>
                        ) : (
                            <p className="text-gray-400">Sin macros efectivos</p>
                        )}
                    </div>
                    
                    {/* Warning if would exceed */}
                    {wouldExceed && (
                        <p className="text-center text-orange-600 text-sm mb-3">
                            ⚠️ Te pasarías de macros si añades este alimento
                        </p>
                    )}
                    
                    {/* Action buttons */}
                    <div className="flex gap-2">
                        <button
                            onClick={() => setSelectedFood(null)}
                            className="flex-1 py-2 px-4 rounded-full border border-gray-300 text-gray-600 hover:bg-gray-100"
                        >
                            Cancelar
                        </button>
                        <button
                            onClick={handleConfirmAdd}
                            className={`flex-1 py-2 px-4 rounded-full text-white font-bold ${
                                isIntraMode ? 'bg-yellow-500 hover:bg-yellow-600' :
                                isPostMode ? 'bg-green-500 hover:bg-green-600' :
                                'bg-brand-orange hover:bg-orange-600'
                            }`}
                        >
                            ✓ Añadir
                        </button>
                    </div>
                </div>
            );
        }
        
        // Normal row view
        return (
            <div 
                onClick={() => handleFoodClick(food)}
                className="flex items-center gap-2 p-3 rounded-lg hover:bg-gray-100 border border-gray-100 transition-colors cursor-pointer"
                data-testid={`food-row-${food.id || food._id}`}
            >
                <span className="text-xl flex-shrink-0">{getFoodEmoji(food.categorias)}</span>
                <div className="flex-1 min-w-0">
                    {hasUrl ? (
                        <a 
                            href={hasUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="font-medium text-[#FF5405] underline truncate block hover:text-orange-600"
                        >
                            {food.nombre}
                        </a>
                    ) : (
                        <p className="font-medium text-gray-900 truncate">{food.nombre}</p>
                    )}
                    <p className="text-sm text-gray-500">
                        <span className="font-medium">{quantity}</span>
                        {macroParts.length > 0 && ' · '}
                        {macroParts.map((part, i) => (
                            <span key={i}>
                                {i > 0 && <span className="text-gray-300"> | </span>}
                                {part}
                            </span>
                        ))}
                    </p>
                </div>
                <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                    isIntraMode ? 'bg-yellow-100 text-yellow-600' :
                    isPostMode ? 'bg-green-100 text-green-600' :
                    'bg-orange-100 text-brand-orange'
                }`}>
                    <Plus className="w-4 h-4" />
                </div>
            </div>
        );
    };
    
    if (!open || !mealKey) return null;
    
    const categories = getCurrentCategories();
    const displayList = isSearching ? searchResults : categoryFoods;
    
    return (
        <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="max-w-lg h-[95vh] max-h-[95vh] flex flex-col p-0 gap-0 overflow-hidden">
                {/* Header */}
                <div className={`p-4 flex-shrink-0 ${isIntraMode ? 'bg-yellow-600' : isPostMode ? 'bg-green-600' : 'bg-bg-dark'}`}>
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                            <button 
                                onClick={onClose}
                                className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center"
                            >
                                <X className="w-4 h-4 text-white" />
                            </button>
                            <DialogTitle className="text-white text-lg">{getModalTitle()}</DialogTitle>
                        </div>
                        {isIntraMode && <Zap className="w-6 h-6 text-white" />}
                    </div>
                    <DialogDescription className="sr-only">Constructor de comida</DialogDescription>
                    
                    {/* Meal info */}
                    <div className="text-white text-sm mb-2">
                        <span className="font-bold">{mealInfo[mealKey]?.name}:</span>{' '}
                        <span className="text-white/80">
                            {target.P.toFixed(0)}P | {target.H.toFixed(0)}H {!isPeriMode && `| ${target.G.toFixed(0)}G`}
                        </span>
                    </div>
                    <div className="text-white/90 text-sm font-semibold">
                        Te quedan: {remaining.P.toFixed(0)}P | {remaining.H.toFixed(0)}H {!isPeriMode && `| ${remaining.G.toFixed(0)}G`}
                    </div>
                    
                    {/* Progress bars */}
                    <div className="mt-3 space-y-1">
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-white/70 w-4">P</span>
                            <div className="flex-1 h-2 bg-white/20 rounded-full overflow-hidden">
                                <div className="h-full bg-green-400 transition-all" style={{ width: `${Math.min((served.P / target.P) * 100, 100)}%` }} />
                            </div>
                            <span className="text-xs text-white/70 w-12 text-right">{Math.round(served.P)}/{Math.round(target.P)}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-white/70 w-4">H</span>
                            <div className="flex-1 h-2 bg-white/20 rounded-full overflow-hidden">
                                <div className="h-full bg-blue-400 transition-all" style={{ width: `${Math.min((served.H / target.H) * 100, 100)}%` }} />
                            </div>
                            <span className="text-xs text-white/70 w-12 text-right">{Math.round(served.H)}/{Math.round(target.H)}</span>
                        </div>
                        {!isPeriMode && (
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-white/70 w-4">G</span>
                                <div className="flex-1 h-2 bg-white/20 rounded-full overflow-hidden">
                                    <div className="h-full bg-orange-400 transition-all" style={{ width: `${Math.min((served.G / target.G) * 100, 100)}%` }} />
                                </div>
                                <span className="text-xs text-white/70 w-12 text-right">{Math.round(served.G)}/{Math.round(target.G)}</span>
                            </div>
                        )}
                    </div>
                </div>
                
                {/* Ingredients added */}
                {tempFoods.length > 0 && (
                    <div className="bg-gray-100 px-4 py-3 flex-shrink-0 border-b">
                        <div className="flex justify-between items-center mb-2">
                            <p className="text-xs text-gray-500 font-semibold">EN ESTA COMIDA ({tempFoods.length}/{MAX_FOODS})</p>
                            <button 
                                onClick={handleClearMeal}
                                className="text-xs text-red-500 hover:text-red-700"
                            >
                                🗑️ Vaciar
                            </button>
                        </div>
                        <div className="space-y-1">
                            {tempFoods.map((food, idx) => (
                                <div key={idx} className="flex items-center justify-between bg-white rounded-lg px-3 py-2 text-sm">
                                    <div className="flex items-center gap-2 flex-1 min-w-0">
                                        <span>{getFoodEmoji(food.categorias)}</span>
                                        <span className="font-medium truncate">{food.nombre}</span>
                                        <span className="text-gray-500 flex-shrink-0">{food.cantidad_g}g</span>
                                    </div>
                                    <div className="flex items-center gap-2 flex-shrink-0">
                                        <span className="text-xs text-gray-500">
                                            {food.macros_efectivos?.P?.toFixed(0)}P|{food.macros_efectivos?.H?.toFixed(0)}H|{food.macros_efectivos?.G?.toFixed(0)}G
                                        </span>
                                        <button 
                                            onClick={() => handleRemoveFood(idx)}
                                            className="text-red-500 hover:text-red-700"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                
                {/* Cuadrada state */}
                {isCuadrada && tempFoods.length > 0 && (
                    <div className="bg-green-500 text-white text-center py-3 font-bold flex-shrink-0">
                        🎉 ¡COMIDA CUADRADA!
                    </div>
                )}
                
                {/* Main content */}
                <div className="flex-1 overflow-y-auto bg-white">
                    {/* Search bar - ALWAYS visible */}
                    <div className="px-4 py-3 border-b sticky top-0 bg-white z-10">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                            <Input
                                placeholder="🔍 Buscar alimento..."
                                value={searchQuery}
                                onChange={(e) => handleSearch(e.target.value)}
                                className="pl-9 h-10 rounded-lg bg-gray-100 border-0"
                                data-testid="search-food-input"
                            />
                            {searchQuery && (
                                <button 
                                    onClick={() => {
                                        setSearchQuery('');
                                        setSearchResults([]);
                                        setIsSearching(false);
                                    }}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                                >
                                    <X className="w-4 h-4" />
                                </button>
                            )}
                        </div>
                    </div>
                    
                    {/* Step title */}
                    <div className="px-4 py-3 border-b">
                        <h3 className="font-bold text-gray-900">{getStepTitle()}</h3>
                    </div>
                    
                    {/* Content based on state */}
                    {!isSearching && !selectedCategory && (
                        /* CATEGORY BUTTONS - Initial state, no foods shown */
                        <div className="px-4 py-4">
                            <div className="flex flex-wrap gap-2">
                                {categories.map(cat => (
                                    <button
                                        key={cat.id}
                                        onClick={() => handleCategoryClick(cat)}
                                        className={`px-4 py-2.5 rounded-full text-sm font-medium transition-all ${
                                            isIntraMode ? 'bg-yellow-100 hover:bg-yellow-200 text-yellow-800' :
                                            isPostMode ? 'bg-green-100 hover:bg-green-200 text-green-800' :
                                            'bg-gray-100 hover:bg-orange-100 hover:text-orange-600 text-gray-700'
                                        }`}
                                        data-testid={`category-${cat.id}`}
                                    >
                                        {cat.emoji} {cat.label}
                                    </button>
                                ))}
                            </div>
                            <p className="text-center text-gray-400 mt-8 text-sm">
                                Pincha una categoría para ver los alimentos
                            </p>
                        </div>
                    )}
                    
                    {!isSearching && selectedCategory && (
                        /* FOODS FROM SELECTED CATEGORY */
                        <div className="px-4 py-3">
                            <button 
                                onClick={handleBackToCategories}
                                className="text-brand-orange text-sm mb-3 flex items-center gap-1 hover:underline"
                                data-testid="back-to-categories"
                            >
                                ← Volver a categorías
                            </button>
                            
                            <p className="text-sm text-gray-500 mb-3">
                                {selectedCategory.emoji} <span className="font-medium">{selectedCategory.label}</span> · ordenados por mejor ajuste
                            </p>
                            
                            {loadingFoods && (
                                <div className="flex justify-center py-8">
                                    <div className={`animate-spin rounded-full h-8 w-8 border-4 ${
                                        isIntraMode ? 'border-yellow-500' : isPostMode ? 'border-green-500' : 'border-brand-orange'
                                    } border-t-transparent`} />
                                </div>
                            )}
                            
                            {!loadingFoods && categoryFoods.length === 0 && (
                                <p className="text-center py-8 text-gray-400">No hay alimentos en esta categoría</p>
                            )}
                            
                            {!loadingFoods && categoryFoods.length > 0 && (
                                <div className="space-y-1 max-h-[50vh] overflow-y-auto">
                                    {categoryFoods.map(food => (
                                        <FoodRow key={food.id || food._id} food={food} />
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                    
                    {isSearching && (
                        /* SEARCH RESULTS */
                        <div className="px-4 py-3">
                            <p className="text-sm text-gray-500 mb-3">
                                Resultados para "{searchQuery}"
                            </p>
                            
                            {loadingFoods && (
                                <div className="flex justify-center py-8">
                                    <div className="animate-spin rounded-full h-8 w-8 border-4 border-brand-orange border-t-transparent" />
                                </div>
                            )}
                            
                            {!loadingFoods && searchResults.length === 0 && (
                                <p className="text-center py-8 text-gray-400">No se encontraron resultados</p>
                            )}
                            
                            {!loadingFoods && searchResults.length > 0 && (
                                <div className="space-y-1 max-h-[50vh] overflow-y-auto">
                                    {searchResults.map(food => (
                                        <FoodRow key={food.id || food._id} food={food} />
                                    ))}
                                </div>
                            )}
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
    
    // Handle preferences saved
    const handlePreferencesSaved = (preferences) => {
        setUserPreferences(preferences);
        setShowPreferencesSetup(false);
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
    const getQuantityIncrement = (food) => {
        const cat = food.categorias?.split(' | ')[0]?.split('.')[0] || '';
        const subCat = food.categorias?.split(' | ')[0] || '';
        
        // Cat 2 (carnes), 3 (pescados): ±25g
        if (cat === '2' || cat === '3') return 25;
        // Cat 21 (arroz), 22 (pasta), 9 (patata): ±25g
        if (cat === '21' || cat === '22' || cat === '9') return 25;
        // Cat 8 (pan): ±10g
        if (cat === '8') return 10;
        // Cat 1 (huevos): ±55g (1 huevo)
        if (cat === '1') return 55;
        // Cat 17.2 (frutos secos): ±5g
        if (subCat.startsWith('17.2')) return 5;
        // Cat 17.1 (aceites): ±1g
        if (subCat.startsWith('17.1')) return 1;
        // Cat 11.1 (fruta fresca): usar racion/2 o ±50g
        if (subCat.startsWith('11.1') || subCat.startsWith('11.2')) {
            return Math.round((food.racion || 100) / 2);
        }
        // Cat 4 (proteína polvo): ±5g
        if (cat === '4') return 5;
        // Default: ±10g
        return 10;
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
                categorias: food.categorias,
                racion: food.racion
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
        try {
            const result = await api('/api/calculator/macros-efectivos', {
                method: 'POST',
                body: JSON.stringify({ alimento_id: food.alimento_id, cantidad_g: newQuantity, es_vegano: false })
            });
            foods[foodIndex] = { ...food, cantidad_g: newQuantity, macros_efectivos: result.efectivos, macros_brutos: result.brutos, que_cuenta: result.que_cuenta };
            setMealsData(prev => ({ ...prev, [mealKey]: { alimentos: foods } }));
        } catch (err) { console.error('Error updating quantity:', err); }
    };

    const updateFoodQuantityDirect = async (mealKey, foodIndex, newQuantity) => {
        const foods = [...(mealsData[mealKey]?.alimentos || [])];
        const food = foods[foodIndex];
        const quantity = Math.max(1, parseInt(newQuantity) || 1);
        try {
            const result = await api('/api/calculator/macros-efectivos', {
                method: 'POST',
                body: JSON.stringify({ alimento_id: food.alimento_id, cantidad_g: quantity, es_vegano: false })
            });
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
    const ProgressBar = ({ value, max, color, height = 6, showCheck = false }) => {
        const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
        const isOver = value > max + 4;
        const isOk = Math.abs(value - max) <= 4;
        const actualColor = isOver ? '#EF4444' : color;
        
        return (
            <div className="flex items-center gap-2 w-full">
                <div className={`flex-1 bg-gray-200 rounded-full overflow-hidden`} style={{ height }}>
                    <div 
                        className="h-full rounded-full transition-all duration-300"
                        style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: actualColor }}
                    />
                </div>
                {showCheck && isOk && value > 0 && <Check className="w-4 h-4 text-green-500 flex-shrink-0" />}
            </div>
        );
    };

    // Mini status dot for meals
    const getMealStatusDot = (mealKey) => {
        const status = getMealStatus(mealKey);
        if (status === 'empty') return { color: 'bg-gray-300', symbol: '⚪' };
        if (status === 'cuadrada') return { color: 'bg-green-500', symbol: '🟢' };
        if (status === 'sobra') return { color: 'bg-red-500', symbol: '🔴' };
        return { color: 'bg-yellow-500', symbol: '🟡' };
    };

    // ===== STICKY SUMMARY COMPONENT =====
    const DaySummary = () => {
        const dayStatus = getDayStatus();
        const mealOrder = getMealOrder();
        
        return (
            <div 
                className="sticky top-[52px] z-30 bg-white shadow-md border-b cursor-pointer"
                onClick={() => setSummaryExpanded(!summaryExpanded)}
                data-testid="day-summary"
            >
                <div className="max-w-lg mx-auto px-4 py-3">
                    {/* Title & Status Badge */}
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-bold text-gray-500 uppercase tracking-wide">
                            {tipoDia === 'entrenamiento' ? 'Día de Entrenamiento' : 'Día de Descanso'}
                        </span>
                        {dayStatus === 'cuadrado' && (
                            <span className="px-2 py-0.5 bg-green-500 text-white text-xs font-bold rounded-full">🟢 Cuadrado</span>
                        )}
                        {dayStatus === 'sobra' && (
                            <span className="px-2 py-0.5 bg-red-500 text-white text-xs font-bold rounded-full">🔴 Te pasas</span>
                        )}
                    </div>
                    
                    {/* Progress Bars */}
                    <div className="space-y-1.5">
                        <div className="flex items-center gap-2 text-xs">
                            <span className="w-4 text-center">🟢</span>
                            <span className="w-6 font-semibold">P:</span>
                            <div className="flex-1">
                                <ProgressBar value={dayMacros.P} max={dayTarget.P_total} color="#4CAF50" height={6} />
                            </div>
                            <span className={`w-20 text-right font-mono ${dayMacros.P > dayTarget.P_total + 4 ? 'text-red-500' : ''}`}>
                                {dayMacros.P.toFixed(0)}/{dayTarget.P_total?.toFixed(0) || 0}g
                            </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs">
                            <span className="w-4 text-center">🔵</span>
                            <span className="w-6 font-semibold">H:</span>
                            <div className="flex-1">
                                <ProgressBar value={dayMacros.H} max={dayTarget.H_total} color="#2196F3" height={6} />
                            </div>
                            <span className={`w-20 text-right font-mono ${dayMacros.H > dayTarget.H_total + 4 ? 'text-red-500' : ''}`}>
                                {dayMacros.H.toFixed(0)}/{dayTarget.H_total?.toFixed(0) || 0}g
                            </span>
                        </div>
                        <div className="flex items-center gap-2 text-xs">
                            <span className="w-4 text-center">🟠</span>
                            <span className="w-6 font-semibold">G:</span>
                            <div className="flex-1">
                                <ProgressBar value={dayMacros.G} max={dayTarget.G_total} color="#FFA500" height={6} />
                            </div>
                            <span className={`w-20 text-right font-mono ${dayMacros.G > dayTarget.G_total + 4 ? 'text-red-500' : ''}`}>
                                {dayMacros.G.toFixed(0)}/{dayTarget.G_total?.toFixed(0) || 0}g
                            </span>
                        </div>
                    </div>
                    
                    {/* Peri Line (only training days) */}
                    {tipoDia === 'entrenamiento' && opcionPeri !== 'sin_peri' && (
                        <div className="mt-2 pt-2 border-t border-gray-100 flex items-center justify-center text-xs text-gray-500">
                            <span>Peri: {servedPeriP.toFixed(0)}/{totalPeriP.toFixed(0)}P · {servedPeriH.toFixed(0)}/{totalPeriH.toFixed(0)}H</span>
                        </div>
                    )}
                    
                    {/* Mini meal status line */}
                    <div className="mt-2 flex items-center justify-center gap-1 text-xs">
                        {mealOrder.map((mealKey, idx) => (
                            <span key={mealKey} className="flex items-center">
                                {idx > 0 && <span className="text-gray-300 mx-1">|</span>}
                                <span className="text-gray-500">{mealInfo[mealKey].shortName}</span>
                                <span className="ml-0.5">{getMealStatusDot(mealKey).symbol}</span>
                            </span>
                        ))}
                    </div>
                    
                    {/* Expanded details */}
                    {summaryExpanded && (
                        <div className="mt-3 pt-3 border-t border-gray-200">
                            <table className="w-full text-xs">
                                <thead>
                                    <tr className="text-gray-500">
                                        <th className="text-left font-medium py-1"></th>
                                        <th className="text-right font-medium py-1 w-16">P</th>
                                        <th className="text-right font-medium py-1 w-16">H</th>
                                        <th className="text-right font-medium py-1 w-16">G</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {mealOrder.map(mealKey => {
                                        const served = calculateMealMacros(mealKey);
                                        const isPeri = mealKey === 'Intra' || mealKey === 'Post';
                                        return (
                                            <tr key={mealKey} className="border-t border-gray-100">
                                                <td className="py-1 text-gray-700">{mealInfo[mealKey].name}</td>
                                                <td className="text-right font-mono">{served.P.toFixed(0)}g</td>
                                                <td className="text-right font-mono">{served.H.toFixed(0)}g</td>
                                                <td className="text-right font-mono">{isPeri ? '-' : `${served.G.toFixed(0)}g`}</td>
                                            </tr>
                                        );
                                    })}
                                    <tr className="border-t-2 border-gray-300 font-bold">
                                        <td className="py-1">TOTAL</td>
                                        <td className="text-right font-mono">{dayMacros.P.toFixed(0)}g</td>
                                        <td className="text-right font-mono">{dayMacros.H.toFixed(0)}g</td>
                                        <td className="text-right font-mono">{dayMacros.G.toFixed(0)}g</td>
                                    </tr>
                                    <tr className="text-gray-500">
                                        <td className="py-1">OBJETIVO</td>
                                        <td className="text-right font-mono">{dayTarget.P_total?.toFixed(0) || 0}g</td>
                                        <td className="text-right font-mono">{dayTarget.H_total?.toFixed(0) || 0}g</td>
                                        <td className="text-right font-mono">{dayTarget.G_total?.toFixed(0) || 0}g</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    )}
                    
                    <div className="mt-2 flex justify-center">
                        {summaryExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                    </div>
                </div>
            </div>
        );
    };

    // ===== CONFIG SECTION COMPONENT =====
    const ConfigSection = () => {
        const momentoOptions = numComidas === 3 
            ? MOMENTO_OPTIONS.filter(o => o.value < 3) 
            : MOMENTO_OPTIONS;
        
        return (
            <div className="bg-gray-100 rounded-xl p-3 mb-4" data-testid="config-section">
                {/* Comidas selector */}
                <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-600 font-medium">Comidas:</span>
                        <div className="flex gap-1">
                            <button
                                onClick={() => {
                                    setNumComidas(3);
                                    if (momentoEntreno > 2) setMomentoEntreno(2);
                                }}
                                className={`w-8 h-8 rounded-full text-sm font-bold transition-all ${
                                    numComidas === 3 
                                        ? 'bg-brand-orange text-white shadow' 
                                        : 'bg-white text-gray-600 border border-gray-300'
                                }`}
                                data-testid="comidas-3-btn"
                            >
                                3
                            </button>
                            <button
                                onClick={() => setNumComidas(4)}
                                className={`w-8 h-8 rounded-full text-sm font-bold transition-all ${
                                    numComidas === 4 
                                        ? 'bg-brand-orange text-white shadow' 
                                        : 'bg-white text-gray-600 border border-gray-300'
                                }`}
                                data-testid="comidas-4-btn"
                            >
                                4
                            </button>
                        </div>
                    </div>
                    
                    {/* Momento entreno - only on training days */}
                    {tipoDia === 'entrenamiento' && (
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-600 font-medium">Entrenas:</span>
                            <select
                                value={momentoEntreno}
                                onChange={(e) => setMomentoEntreno(Number(e.target.value))}
                                className="text-xs bg-white border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-orange"
                                data-testid="momento-entreno-select"
                            >
                                {momentoOptions.map(opt => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                            </select>
                        </div>
                    )}
                    
                    {/* Peri option - only on training days */}
                    {tipoDia === 'entrenamiento' && (
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-600 font-medium">Peri:</span>
                            <select
                                value={opcionPeri}
                                onChange={(e) => setOpcionPeri(e.target.value)}
                                className="text-xs bg-white border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-orange"
                                data-testid="peri-select"
                            >
                                {PERI_OPTIONS.map(opt => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                            </select>
                        </div>
                    )}
                </div>
            </div>
        );
    };

    // ===== MEAL PROGRESS BARS COMPONENT =====
    const MealProgressBars = ({ mealKey }) => {
        const target = getMealTarget(mealKey);
        const served = calculateMealMacros(mealKey);
        const isPeri = mealKey === 'Intra' || mealKey === 'Post';
        const status = getMealStatus(mealKey);
        
        const getMacroDiff = (servedVal, targetVal) => {
            const diff = targetVal - servedVal;
            if (Math.abs(diff) <= 4) return { ok: true, diff: 0 };
            return { ok: false, diff };
        };
        
        const pDiff = getMacroDiff(served.P, target.P);
        const hDiff = getMacroDiff(served.H, target.H);
        const gDiff = !isPeri ? getMacroDiff(served.G, target.G) : { ok: true, diff: 0 };
        
        const pOver = served.P > target.P + 4;
        const hOver = served.H > target.H + 4;
        const gOver = !isPeri && served.G > target.G + 4;
        
        // Build status message
        let statusMessage = '';
        let statusColor = '';
        
        if (status === 'cuadrada') {
            statusMessage = '🟢 Cuadrada';
            statusColor = 'text-green-600';
        } else if (pOver || hOver || gOver) {
            const parts = [];
            if (pOver) parts.push(`${(served.P - target.P).toFixed(0)}g P`);
            if (hOver) parts.push(`${(served.H - target.H).toFixed(0)}g H`);
            if (gOver) parts.push(`${(served.G - target.G).toFixed(0)}g G`);
            statusMessage = `🔴 Sobran ${parts.join(', ')}`;
            statusColor = 'text-red-600';
        } else if (status === 'falta') {
            const parts = [];
            if (!pDiff.ok && pDiff.diff > 0) parts.push(`${pDiff.diff.toFixed(0)}g P`);
            if (!hDiff.ok && hDiff.diff > 0) parts.push(`${hDiff.diff.toFixed(0)}g H`);
            if (!gDiff.ok && gDiff.diff > 0) parts.push(`${gDiff.diff.toFixed(0)}g G`);
            if (parts.length > 0) {
                statusMessage = `🟡 Faltan ${parts.join(', ')}`;
                statusColor = 'text-yellow-600';
            }
        }
        
        return (
            <div className="bg-gray-50 rounded-lg p-3 mb-3" data-testid={`meal-progress-${mealKey}`}>
                {/* Protein bar */}
                <div className="flex items-center gap-2 mb-2">
                    <span className="w-5 text-center text-sm">🟢</span>
                    <span className="w-4 text-xs font-semibold text-gray-600">P</span>
                    <div className="flex-1">
                        <ProgressBar value={served.P} max={target.P} color="#4CAF50" height={8} showCheck />
                    </div>
                    <span className={`text-xs font-mono w-16 text-right ${pOver ? 'text-red-500 font-bold' : ''}`}>
                        {served.P.toFixed(0)}/{target.P.toFixed(0)}g
                    </span>
                </div>
                
                {/* Carbs bar */}
                <div className="flex items-center gap-2 mb-2">
                    <span className="w-5 text-center text-sm">🔵</span>
                    <span className="w-4 text-xs font-semibold text-gray-600">H</span>
                    <div className="flex-1">
                        <ProgressBar value={served.H} max={target.H} color="#2196F3" height={8} showCheck />
                    </div>
                    <span className={`text-xs font-mono w-16 text-right ${hOver ? 'text-red-500 font-bold' : ''}`}>
                        {served.H.toFixed(0)}/{target.H.toFixed(0)}g
                    </span>
                </div>
                
                {/* Fat bar (not for peri) */}
                {!isPeri && (
                    <div className="flex items-center gap-2 mb-2">
                        <span className="w-5 text-center text-sm">🟠</span>
                        <span className="w-4 text-xs font-semibold text-gray-600">G</span>
                        <div className="flex-1">
                            <ProgressBar value={served.G} max={target.G} color="#FFA500" height={8} showCheck />
                        </div>
                        <span className={`text-xs font-mono w-16 text-right ${gOver ? 'text-red-500 font-bold' : ''}`}>
                            {served.G.toFixed(0)}/{target.G.toFixed(0)}g
                        </span>
                    </div>
                )}
                
                {/* Status message */}
                {statusMessage && (
                    <div className={`text-xs font-semibold ${statusColor} mt-1`}>
                        {statusMessage}
                    </div>
                )}
            </div>
        );
    };

    // ===== MEAL CARD COMPONENT =====
    const MealCard = ({ mealKey }) => {
        const isExpanded = expandedMeals[mealKey];
        const target = getMealTarget(mealKey);
        const foods = mealsData[mealKey]?.alimentos || [];
        const isPeri = mealKey === 'Intra' || mealKey === 'Post';
        const info = mealInfo[mealKey];
        const status = getMealStatus(mealKey);
        const statusDot = getMealStatusDot(mealKey);

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
                            <div className="flex items-center gap-2">
                                <h3 className="font-bold text-gray-900">{info.name}</h3>
                                <span className="text-sm">{statusDot.symbol}</span>
                            </div>
                            <p className="text-xs text-gray-500">
                                {isPeri 
                                    ? `${target.P.toFixed(0)}P | ${target.H.toFixed(0)}H`
                                    : `${target.P.toFixed(0)}P | ${target.H.toFixed(0)}H | ${target.G.toFixed(0)}G`
                                }
                            </p>
                        </div>
                    </div>
                    {isExpanded ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
                </button>

                {isExpanded && (
                    <CardContent className="pt-0 px-4 pb-4">
                        {/* Progress bars */}
                        <MealProgressBars mealKey={mealKey} />

                        {/* Empty state */}
                        {foods.length === 0 && !isPeri && (
                            <div className="space-y-2">
                                <Button 
                                    className="w-full h-12 bg-brand-orange hover:bg-brand-orange-dark text-white font-bold rounded-full shadow-lg shadow-brand-orange/30"
                                    onClick={() => loadMenuOptions(mealKey)}
                                    data-testid={`menu-options-${mealKey}`}
                                >
                                    <Zap className="w-5 h-5 mr-2" /> SUGIÉREME UN MENÚ
                                </Button>
                                <div className="grid grid-cols-2 gap-2">
                                    <Button 
                                        variant="outline" 
                                        className="h-10 rounded-full border-gray-300"
                                        onClick={() => setBuildMealModal({ open: true, mealKey, mode: 'normal' })}
                                        data-testid={`build-meal-${mealKey}`}
                                    >
                                        <Wrench className="w-4 h-4 mr-1" /> Lo hago yo
                                    </Button>
                                    <Button 
                                        variant="outline" 
                                        className="h-10 rounded-full border-gray-300"
                                        onClick={() => openRepeatModal(mealKey)}
                                        data-testid={`repeat-meal-${mealKey}`}
                                    >
                                        <RefreshCw className="w-4 h-4 mr-1" /> Repetir
                                    </Button>
                                </div>
                            </div>
                        )}

                        {/* Empty state for INTRA */}
                        {foods.length === 0 && mealKey === 'Intra' && (
                            <Button 
                                className="w-full h-10 rounded-full bg-brand-orange/10 border border-brand-orange text-brand-orange hover:bg-brand-orange hover:text-white"
                                onClick={() => setBuildMealModal({ open: true, mealKey, mode: 'intra' })}
                            >
                                <Zap className="w-4 h-4 mr-1" /> Construir Intra
                            </Button>
                        )}

                        {/* Empty state for POST */}
                        {foods.length === 0 && mealKey === 'Post' && (
                            <Button 
                                className="w-full h-10 rounded-full bg-brand-orange/10 border border-brand-orange text-brand-orange hover:bg-brand-orange hover:text-white"
                                onClick={() => setBuildMealModal({ open: true, mealKey, mode: 'post' })}
                            >
                                <Zap className="w-4 h-4 mr-1" /> Construir Post
                            </Button>
                        )}

                        {/* Foods list */}
                        {foods.length > 0 && (
                            <>
                                <div className="border-t border-gray-100 pt-3 mb-3">
                                    <p className="text-xs text-gray-500 mb-2 font-semibold">── INGREDIENTES ──</p>
                                    <div className="space-y-3">
                                        {foods.map((food, idx) => {
                                            const macros = food.macros_efectivos || {};
                                            const increment = getQuantityIncrement(food);
                                            const isEditing = editingQuantity.mealKey === mealKey && editingQuantity.foodIndex === idx;
                                            const hasMacros = (macros.P || 0) > 0 || (macros.H || 0) > 0 || (macros.G || 0) > 0;
                                            
                                            return (
                                                <div 
                                                    key={idx} 
                                                    className="bg-gray-50 rounded-lg p-3"
                                                >
                                                    <div className="flex items-center justify-between mb-1">
                                                        <div className="flex items-center gap-2 flex-1 min-w-0">
                                                            <span className="text-xl">{getFoodEmoji(food.categorias)}</span>
                                                            <span className="text-sm font-semibold text-gray-800 truncate">{food.nombre}</span>
                                                        </div>
                                                        <Button 
                                                            variant="ghost" 
                                                            size="icon" 
                                                            className="h-7 w-7 text-gray-400 hover:text-red-500" 
                                                            onClick={() => removeFood(mealKey, idx)}
                                                        >
                                                            <Trash2 className="w-4 h-4" />
                                                        </Button>
                                                    </div>
                                                    
                                                    {/* Quantity controls */}
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center gap-1">
                                                            <Button 
                                                                variant="outline" 
                                                                size="icon" 
                                                                className="h-8 w-8 rounded-full"
                                                                onClick={() => updateFoodQuantity(mealKey, idx, -increment)}
                                                            >
                                                                <Minus className="w-3 h-3" />
                                                            </Button>
                                                            {isEditing ? (
                                                                <input
                                                                    type="number"
                                                                    defaultValue={food.cantidad_g}
                                                                    className="w-16 h-8 text-center text-sm font-bold border rounded-lg"
                                                                    autoFocus
                                                                    onBlur={(e) => updateFoodQuantityDirect(mealKey, idx, e.target.value)}
                                                                    onKeyDown={(e) => {
                                                                        if (e.key === 'Enter') updateFoodQuantityDirect(mealKey, idx, e.target.value);
                                                                        if (e.key === 'Escape') setEditingQuantity({ mealKey: null, foodIndex: null });
                                                                    }}
                                                                />
                                                            ) : (
                                                                <button 
                                                                    className="w-16 h-8 text-sm font-bold text-center bg-white border border-gray-200 rounded-lg hover:border-brand-orange"
                                                                    onClick={() => setEditingQuantity({ mealKey, foodIndex: idx })}
                                                                >
                                                                    {food.cantidad_g}g
                                                                </button>
                                                            )}
                                                            <Button 
                                                                variant="outline" 
                                                                size="icon" 
                                                                className="h-8 w-8 rounded-full"
                                                                onClick={() => updateFoodQuantity(mealKey, idx, increment)}
                                                            >
                                                                <Plus className="w-3 h-3" />
                                                            </Button>
                                                        </div>
                                                        
                                                        {/* Macros display */}
                                                        <div className="text-xs text-gray-500">
                                                            {hasMacros ? (
                                                                <span>
                                                                    ({(macros.P || 0).toFixed(0)}P | {(macros.H || 0).toFixed(0)}H | {(macros.G || 0).toFixed(0)}G)
                                                                </span>
                                                            ) : (
                                                                <span className="text-gray-400">(no aporta macros)</span>
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                                
                                {/* Add more button */}
                                {foods.length < (isPeri ? 3 : 5) ? (
                                    <Button 
                                        variant="ghost" 
                                        className="w-full text-brand-orange hover:text-brand-orange-dark"
                                        onClick={() => setBuildMealModal({ open: true, mealKey, startStep: 2 })}
                                    >
                                        <Plus className="w-4 h-4 mr-1" /> Añadir ingrediente
                                    </Button>
                                ) : (
                                    <p className="text-xs text-gray-400 text-center">Máximo {isPeri ? 3 : 5} alimentos alcanzado</p>
                                )}
                                
                                {/* Clear meal button */}
                                <button 
                                    className="w-full text-xs text-gray-400 hover:text-red-500 mt-2 py-1"
                                    onClick={() => clearMeal(mealKey)}
                                >
                                    🗑️ Vaciar comida
                                </button>
                            </>
                        )}
                    </CardContent>
                )}
            </Card>
        );
    };

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
                <DaySummary />

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
                            <div className="flex gap-2">
                                <button 
                                    className={`flex-1 py-2 px-3 rounded-full text-sm font-semibold transition-all ${
                                        tipoDia === 'entrenamiento' 
                                            ? 'bg-brand-orange text-white shadow-md' 
                                            : 'bg-gray-100 text-gray-600'
                                    }`}
                                    onClick={() => setTipoDia('entrenamiento')}
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
                                    onClick={() => setTipoDia('descanso')}
                                    data-testid="tipo-dia-descanso"
                                >
                                    Día de descanso
                                </button>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Config Section - always visible now */}
                    <ConfigSection />

                    {/* Meals */}
                    <div className="space-y-3 mb-4">
                        {getMealOrder().map(mealKey => <MealCard key={mealKey} mealKey={mealKey} />)}
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
                        <Button variant="outline" className="h-12 w-12 rounded-full" onClick={() => setCopyModalOpen(true)}>
                            <Copy className="w-5 h-5" />
                        </Button>
                    </div>
                </div>
            </div>

            {/* Search Modal */}
            <Dialog open={addFoodModal.open} onOpenChange={(open) => !open && setAddFoodModal({ open: false, mealKey: null })}>
                <DialogContent className="max-w-lg max-h-[90vh] flex flex-col p-0 gap-0 overflow-hidden">
                    <DialogHeader className="bg-bg-dark p-4 flex-shrink-0">
                        <div className="flex items-center justify-between">
                            <DialogTitle className="text-white flex items-center gap-2">
                                <span>Buscador de alimentos</span>
                                <span className="text-brand-orange text-sm">({addFoodModal.mealKey})</span>
                            </DialogTitle>
                            <button 
                                onClick={() => setAddFoodModal({ open: false, mealKey: null })}
                                className="w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
                            >
                                <X className="w-5 h-5 text-white" />
                            </button>
                        </div>
                        <DialogDescription className="sr-only">Busca alimentos para añadir a tu comida</DialogDescription>
                    </DialogHeader>
                    
                    {/* Search input */}
                    <div className="p-4 bg-white flex-shrink-0 border-b">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                            <Input 
                                placeholder="Escribe un alimento..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-10 h-12 rounded-xl bg-gray-100 border-0"
                                data-testid="search-food-input"
                            />
                        </div>
                    </div>
                    
                    {/* Category chips */}
                    <div className="flex-shrink-0 bg-white border-b">
                        <div className="flex gap-2 px-4 py-3 overflow-x-auto scrollbar-hide">
                            {CATEGORY_CHIPS.map(chip => (
                                <button 
                                    key={chip.value}
                                    onClick={() => setSearchCategory(chip.value)}
                                    className={`flex-shrink-0 inline-flex items-center px-4 py-2 rounded-full text-sm font-medium transition-all whitespace-nowrap ${
                                        searchCategory === chip.value 
                                            ? 'bg-brand-orange text-white shadow-md' 
                                            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                                    }`}
                                >
                                    <span className="mr-1">{chip.emoji}</span> {chip.label}
                                </button>
                            ))}
                        </div>
                    </div>
                    
                    {/* Results */}
                    <div className="flex-1 overflow-y-auto bg-gray-50">
                        {searchLoading ? (
                            <div className="flex items-center justify-center py-12">
                                <div className="animate-spin rounded-full h-8 w-8 border-4 border-brand-orange border-t-transparent" />
                            </div>
                        ) : searchResults.length === 0 ? (
                            <div className="text-center py-12">
                                <span className="text-4xl mb-3 block">🔍</span>
                                <p className="text-gray-500">{searchQuery ? 'No se encontraron resultados' : 'Escribe para buscar'}</p>
                            </div>
                        ) : (
                            <div className="p-4 space-y-2">
                                {searchResults.map(food => {
                                    const macrosEf = food.macros_efectivos || {};
                                    const pEf = macrosEf.P ?? food.proteinas ?? 0;
                                    const hEf = macrosEf.H ?? food.hidratos ?? 0;
                                    const gEf = macrosEf.G ?? food.grasas ?? 0;
                                    const racion = food.racion || 100;
                                    
                                    return (
                                        <button
                                            key={food.id}
                                            className="w-full text-left p-4 bg-white rounded-xl shadow-sm hover:shadow-md transition-all active:scale-[0.98]"
                                            onClick={() => handleAddFood(food)}
                                        >
                                            <div className="flex items-start gap-3">
                                                <span className="text-2xl">{getFoodEmoji(food.categorias)}</span>
                                                <div className="flex-1 min-w-0">
                                                    <p className="font-semibold text-gray-900 truncate">{food.nombre}</p>
                                                    <p className="text-xs text-gray-500">{racion}g / 1 ración</p>
                                                    <div className="flex flex-wrap gap-1 mt-2">
                                                        {pEf > 0 && (
                                                            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-protein-yellow text-gray-800">{pEf.toFixed(1)}g P</span>
                                                        )}
                                                        {hEf > 0 && (
                                                            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-carbs-green text-white">{hEf.toFixed(1)}g H</span>
                                                        )}
                                                        {gEf > 0 && (
                                                            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-fat-red text-white">{gEf.toFixed(1)}g G</span>
                                                        )}
                                                        {pEf === 0 && hEf === 0 && gEf === 0 && (
                                                            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-200 text-gray-600">Sin macros</span>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>
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

            {/* Build Meal Modal - "Lo hago yo" Constructor */}
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
            <Dialog open={repeatMealModal.open} onOpenChange={(open) => !open && setRepeatMealModal({ open: false, mealKey: null })}>
                <DialogContent className="max-w-md max-h-[85vh] flex flex-col p-0 gap-0 overflow-hidden">
                    <DialogHeader className="bg-bg-dark p-4 flex-shrink-0">
                        <DialogTitle className="text-white">Repetir de otro día</DialogTitle>
                        <DialogDescription className="text-gray-400">
                            Copiar a {repeatMealModal.mealKey && mealInfo[repeatMealModal.mealKey]?.name}
                        </DialogDescription>
                    </DialogHeader>
                    
                    <div className="flex-1 overflow-y-auto">
                        {!selectedDietForRepeat ? (
                            // Step 1: Select day
                            <div className="p-4">
                                {recentDiets.length === 0 ? (
                                    <div className="text-center py-8 text-gray-500">
                                        <RefreshCw className="w-8 h-8 mx-auto mb-3 animate-spin" />
                                        <p>Cargando días recientes...</p>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        {recentDiets.map(diet => (
                                            <button
                                                key={diet.fecha}
                                                className="w-full text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-xl transition-all"
                                                onClick={() => setSelectedDietForRepeat(diet)}
                                            >
                                                <div className="flex items-center justify-between">
                                                    <div>
                                                        <p className="font-semibold text-gray-900">{formatDate(diet.fecha)}</p>
                                                        <p className="text-xs text-gray-500">
                                                            {diet.tipo_dia === 'entrenamiento' ? '🟢 Entreno' : '⚪ Descanso'}, {diet.num_comidas} comidas
                                                        </p>
                                                    </div>
                                                    <ChevronRight className="w-5 h-5 text-gray-400" />
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ) : (
                            // Step 2: Select meal from day
                            <div className="p-4">
                                <button 
                                    className="flex items-center gap-2 text-sm text-gray-500 mb-4"
                                    onClick={() => setSelectedDietForRepeat(null)}
                                >
                                    <ChevronLeft className="w-4 h-4" /> Volver
                                </button>
                                
                                <h3 className="font-bold text-gray-900 mb-3">
                                    Comidas del {formatDate(selectedDietForRepeat.fecha)}
                                </h3>
                                
                                <div className="space-y-2">
                                    {Object.entries(selectedDietForRepeat.comidas_resumen || {}).map(([key, resumen]) => (
                                        <button
                                            key={key}
                                            className="w-full text-left p-3 bg-gray-50 hover:bg-brand-orange/10 rounded-xl transition-all border-2 border-transparent hover:border-brand-orange"
                                            onClick={() => copyMealFromDay(key)}
                                        >
                                            <div className="flex items-center justify-between">
                                                <div>
                                                    <p className="font-semibold text-gray-900">
                                                        {mealInfo[key]?.name || key}
                                                    </p>
                                                    <p className="text-xs text-gray-500 truncate max-w-[250px]">
                                                        {resumen}
                                                    </p>
                                                </div>
                                                <span className="text-brand-orange text-sm font-semibold">Copiar</span>
                                            </div>
                                        </button>
                                    ))}
                                    
                                    {Object.keys(selectedDietForRepeat.comidas_resumen || {}).length === 0 && (
                                        <p className="text-center text-gray-500 py-4">
                                            No hay comidas guardadas este día
                                        </p>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                    
                    <div className="flex-shrink-0 p-4 border-t">
                        <Button 
                            variant="outline" 
                            className="w-full rounded-full"
                            onClick={() => {
                                setRepeatMealModal({ open: false, mealKey: null });
                                setSelectedDietForRepeat(null);
                            }}
                        >
                            Cancelar
                        </Button>
                    </div>
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
