import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import {
    ChevronLeft, ChevronRight,
    Copy, Calendar, FileDown, SlidersHorizontal
} from 'lucide-react';
import BrandArrow from '../components/BrandArrow';
import PreferencesSetup, { PREFERENCE_CATEGORIES } from '../components/nutrition/PreferencesSetup';
import BuildMealModal from '../components/nutrition/BuildMealModal';
import RepeatMealModal from '../components/nutrition/RepeatMealModal';
import CopyDietModal from '../components/nutrition/CopyDietModal';
import FavoritesModal from '../components/nutrition/FavoritesModal';
import DaySummary from '../components/nutrition/DaySummary';
import ConfigSection from '../components/nutrition/ConfigSection';
import MealCard, { MealSelectorItem } from '../components/nutrition/MealCard';
import { SearchFoodModal, MenuOptionsModal } from '../components/nutrition/SearchFoodModal';
import DietCalendar from '../components/nutrition/DietCalendar';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Peri options: intra_post/solo_post (Calma) + solo_intra/sin_peri (custom). Normalize stored
// values, defaulting unknown to intra_post.
const PERI_VALUES = ['intra_post', 'solo_post', 'solo_intra', 'sin_peri'];
const normPeri = (v) => (PERI_VALUES.includes(v) ? v : 'intra_post');

// 12EN12 Logo Component
const Logo12EN12 = () => (
    <div className="flex items-center text-xl font-bold tracking-tight">
        <span className="text-white">12EN12</span>
        <BrandArrow className="text-brand-orange h-[1em] w-[1em] -ml-0.5" />
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
    { id: 'vegetal', label: 'Proteína vegetal', emoji: '🌱', prefixes: ['28', '6'] },
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
    const [avoidedCategories, setAvoidedCategories] = useState([]);
    const [avoidedKeywords, setAvoidedKeywords] = useState([]);
    const [preferencesLoading, setPreferencesLoading] = useState(true);
    
    // Date & Config state
    const [currentDate, setCurrentDate] = useState(() => {
        const n = new Date();
        return `${n.getFullYear()}-${String(n.getMonth()+1).padStart(2,'0')}-${String(n.getDate()).padStart(2,'0')}`;
    });
    const [tipoDia, setTipoDia] = useState('entrenamiento');
    const [numComidas, setNumComidas] = useState(4);
    const [momentoEntreno, setMomentoEntreno] = useState(1);
    const [opcionPeri, setOpcionPeri] = useState('intra_post');

    // Favorites state
    const [favorites, setFavorites] = useState(new Set());
    
    // Data state
    const [distribution, setDistribution] = useState(null);
    const [distribTargetsOverlay, setDistribTargetsOverlay] = useState(null);
    // Calma comidaConMacrosVolcadas: the meal key that absorbs the day's remaining macros.
    // When set, every OTHER meal is locked (target = its served = cuadrada). null = no volcado.
    const [volcadoMeal, setVolcadoMeal] = useState(null);
    const [mealsData, setMealsData] = useState({});
    const [expandedMeals, setExpandedMeals] = useState({ C1: true });
    const [selectedMeal, setSelectedMeal] = useState('C1');
    const [loading, setLoading] = useState(true);
    
    // Modal states
    const [addFoodModal, setAddFoodModal] = useState({ open: false, mealKey: null });
    const [menuOptionsModal, setMenuOptionsModal] = useState({ open: false, mealKey: null });
    const [copyModalOpen, setCopyModalOpen] = useState(false);
    const [favoritesModalOpen, setFavoritesModalOpen] = useState(false);
    const [dietFavorites, setDietFavorites] = useState([]);
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
                    setAvoidedCategories(res.avoided_categories || []);
                    setAvoidedKeywords(res.avoided_keywords || []);
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
    const handlePreferencesSaved = (preferences, avoidedCats, avoidedKws) => {
        setUserPreferences(preferences);
        setAvoidedCategories(avoidedCats || []);
        setAvoidedKeywords(avoidedKws || []);
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

    // Load distribution — accepts optional overrides to avoid stale closure on init
    const loadDistribution = useCallback(async (overrides = {}) => {
        try {
            const result = await api('/api/calculator/distribute', {
                method: 'POST',
                body: JSON.stringify({
                    fecha: currentDate, // date-versioned macros: backend resolves the version effective on this date
                    tipo_dia: overrides.tipoDia ?? tipoDia,
                    num_comidas: overrides.numComidas ?? numComidas,
                    momento_entreno: overrides.momentoEntreno ?? momentoEntreno,
                    opcion_peri: overrides.opcionPeri ?? opcionPeri,
                    single_meal: (overrides.numComidas ?? numComidas) === 1, // el cliente manda
                })
            });
            setDistribution(result);
        } catch (err) {
            console.error('Error loading distribution:', err);
        }
    }, [api, tipoDia, numComidas, momentoEntreno, opcionPeri, currentDate]);

    // Load saved diet — returns { targets, config } where config has the diet's day values
    const loadDiet = useCallback(async (date) => {
        try {
            const diet = await api(`/api/diets/${date}`);
            if (diet.exists) {
                const dietConfig = {
                    tipoDia: diet.tipo_dia || 'entrenamiento',
                    numComidas: diet.num_comidas || 4,
                    momentoEntreno: diet.momento_entreno ?? 1,  // ?? not || so 0 (en ayunas) persiste
                    opcionPeri: normPeri(diet.opcion_peri),
                };
                setTipoDia(dietConfig.tipoDia);
                setNumComidas(dietConfig.numComidas);
                setMomentoEntreno(dietConfig.momentoEntreno);
                setOpcionPeri(dietConfig.opcionPeri);

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
                        updatedMeals[mealKey] = { ...mealData, alimentos: updatedFoods };
                    } else {
                        updatedMeals[mealKey] = mealData;
                    }
                }
                setMealsData(updatedMeals);
                setVolcadoMeal(diet.comida_volcada || null);
                console.log('[loadDiet] distribution_targets:', diet.distribution_targets);
                return { targets: diet.distribution_targets || null, config: dietConfig, ok: true };
            } else {
                setMealsData({});
                setVolcadoMeal(null);
                return { targets: null, config: null, ok: true };
            }
        } catch (err) {
            console.error('Error loading diet:', err);
            setMealsData({});
            // ok:false -> the load FAILED (not "no diet"); auto-save must not treat the empty
            // in-memory state as authoritative and delete a diet that may exist on the server.
            return { targets: null, config: null, ok: false };
        }
    }, [api]);

    // ── Auto-guardado (Calma autoGuardadoEnFecha) ────────────────────────────
    // Calma auto-saves the diet you are LEAVING when the date changes and on page unmount
    // (no per-keystroke save). An empty day is deleted (borrarDieta). autoSaveRef holds the
    // latest savable snapshot; loadedDateRef guards against saving/deleting a date whose
    // diet never loaded (or failed to load) — preventing accidental deletion on a race.
    const autoSaveRef = useRef({});
    const loadedDateRef = useRef(null);

    const autoSaveDiet = useCallback(async (date, snap) => {
        if (!date || !snap) return;
        const hasFood = Object.values(snap.comidas || {}).some(m => (m?.alimentos || []).length > 0);
        try {
            if (hasFood) {
                await api('/api/diets', { method: 'POST', body: JSON.stringify({ fecha: date, ...snap }) });
            } else {
                await api(`/api/diets/${date}`, { method: 'DELETE' }).catch(() => {}); // 404 = nothing to delete
            }
        } catch (e) { /* silent: auto-save must never interrupt the user */ }
    }, [api]);

    // On mount: restore the last viewed date (so a reload returns to the day you were on, not
    // today), else the local date. Persisted below on every date change.
    useEffect(() => {
        const stored = localStorage.getItem('nutrition_last_date');
        if (stored) { setCurrentDate(stored); return; }
        const n = new Date();
        setCurrentDate(`${n.getFullYear()}-${String(n.getMonth()+1).padStart(2,'0')}-${String(n.getDate()).padStart(2,'0')}`);
    }, []);

    // Persist the viewed date so a refresh returns to it.
    useEffect(() => {
        if (currentDate) localStorage.setItem('nutrition_last_date', currentDate);
    }, [currentDate]);

    // Initial load
    useEffect(() => {
        const init = async () => {
            setLoading(true);
            setDistribTargetsOverlay(null);

            // Load persisted diet config FIRST to avoid stale-closure distribution call
            let cfgOverrides = {};
            try {
                const cfg = await api('/api/user/diet-config');
                const me = cfg.momento_entreno ?? 1;
                const nc = cfg.num_comidas ?? 4;
                const op = normPeri(cfg.opcion_peri);
                setMomentoEntreno(me);
                setNumComidas(nc);
                setOpcionPeri(op);
                cfgOverrides = { momentoEntreno: me, numComidas: nc, opcionPeri: op };
            } catch (e) {}

            const { targets, config: dietConfig, ok } = await loadDiet(currentDate);
            if (targets) setDistribTargetsOverlay(targets);

            // If diet has its own config, use that (overrides profile defaults for this day)
            const finalOverrides = dietConfig || cfgOverrides;
            await loadDistribution(finalOverrides);
            setLoading(false);
            // Only enable auto-save for this date once it has loaded successfully.
            if (ok) loadedDateRef.current = currentDate;
        };
        init();
    }, [currentDate]); // eslint-disable-line

    // Auto-save the date being LEFT (cleanup runs on date change and on unmount) — mirrors
    // Calma's `watch fecha` + `unmounted` -> autoGuardadoEnFecha. Guarded by loadedDateRef so
    // a not-yet-loaded date is never persisted/deleted. autoSaveDiet is kept in a ref so the
    // effect depends ONLY on currentDate (not on autoSaveDiet/api identity) — otherwise an
    // unstable `api` would re-fire the cleanup on every render and save constantly.
    const autoSaveDietRef = useRef(autoSaveDiet);
    autoSaveDietRef.current = autoSaveDiet;
    useEffect(() => {
        const dateLeaving = currentDate;
        return () => {
            if (loadedDateRef.current === dateLeaving) {
                autoSaveDietRef.current(dateLeaving, autoSaveRef.current);
            }
        };
    }, [currentDate]);

    // A browser REFRESH/close does NOT run React cleanup, so the unmount auto-save never fires
    // and the day looked "lost". Save synchronously on `beforeunload` via keepalive fetch (it
    // survives unload and carries the auth header). Only saves a loaded, non-empty day.
    useEffect(() => {
        const handler = () => {
            if (loading || loadedDateRef.current !== currentDate) return;
            const snap = autoSaveRef.current;
            const hasFood = Object.values(snap.comidas || {}).some(m => (m?.alimentos || []).length > 0);
            if (!hasFood) return;
            try {
                const token = localStorage.getItem('token');
                fetch(`${process.env.REACT_APP_BACKEND_URL}/api/diets`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
                    body: JSON.stringify({ fecha: currentDate, ...snap }),
                    keepalive: true,
                });
            } catch (e) { /* best effort */ }
        };
        window.addEventListener('beforeunload', handler);
        return () => window.removeEventListener('beforeunload', handler);
    }, [currentDate, loading]);

    // Reload distribution when config changes
    useEffect(() => {
        if (!loading) loadDistribution();
    }, [tipoDia, numComidas, momentoEntreno, opcionPeri]); // eslint-disable-line

    // Wrappers for user-initiated config changes — persist to profile (cross-device)
    const handleSetTipoDia = (v) => { setTipoDia(v); };
    const handleSetMomentoEntreno = (v) => {
        setMomentoEntreno(v);
        api('/api/user/diet-config', { method: 'PATCH', body: JSON.stringify({ momento_entreno: v }) }).catch(() => {});
    };
    const handleSetOpcionPeri = (v) => {
        setOpcionPeri(v);
        api('/api/user/diet-config', { method: 'PATCH', body: JSON.stringify({ opcion_peri: v }) }).catch(() => {});
    };
    const handleSetNumComidas = (v) => {
        setNumComidas(v);
        api('/api/user/diet-config', { method: 'PATCH', body: JSON.stringify({ num_comidas: v }) }).catch(() => {});
    };

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
        const d = new Date(currentDate + 'T12:00:00');
        d.setDate(d.getDate() + days);
        const n = d;
        setCurrentDate(`${n.getFullYear()}-${String(n.getMonth()+1).padStart(2,'0')}-${String(n.getDate()).padStart(2,'0')}`);
    };

    const formatDate = (dateStr) => {
        const n = new Date();
        const todayStr = `${n.getFullYear()}-${String(n.getMonth()+1).padStart(2,'0')}-${String(n.getDate()).padStart(2,'0')}`;
        if (dateStr === todayStr) return 'Hoy';
        const [y, m, d] = dateStr.split('-').map(Number);
        const local = new Date(y, m - 1, d);
        return local.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short' });
    };

    // Meal order based on config
    // Calma esModoSinRepartoDeMacrosPorComidas (coach-set quiereRepartoDeComidas=false):
    // a single comida holds the whole day's macros; peri (intra/post) stays separate.
    const singleMeal = distribution?.config?.single_meal === true;

    const getMealOrder = () => {
        const baseMeals = singleMeal ? ['C1'] : (numComidas === 3 ? ['C1', 'C2', 'C3'] : ['C1', 'C2', 'C3', 'C4']);
        if (tipoDia === 'descanso') return baseMeals;
        const periMeals = opcionPeri === 'intra_post' ? ['Intra', 'Post'] :
                         opcionPeri === 'solo_post' ? ['Post'] :
                         opcionPeri === 'solo_intra' ? ['Intra'] : [];
        if (periMeals.length === 0) return baseMeals;
        const result = [...baseMeals];
        // single mode: peri after the one comida; otherwise spliced at the training moment.
        result.splice(singleMeal ? baseMeals.length : momentoEntreno, 0, ...periMeals);
        return result;
    };

    // Mantener la comida seleccionada (vista master-detail) válida al cambiar la config
    useEffect(() => {
        const order = getMealOrder();
        if (!order.includes(selectedMeal)) setSelectedMeal(order[0]);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [numComidas, tipoDia, opcionPeri, momentoEntreno, singleMeal]);

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

    // Guard: only honor the volcado if its meal still exists in the current layout (e.g. the
    // user dropped from 4 to 3 meals after volcando to C4 → ignore, don't lock everything).
    const activeVolcado = (volcadoMeal && getMealOrder().includes(volcadoMeal)) ? volcadoMeal : null;

    const getMealTarget = (mealKey) => {
        // Volcado (Calma comidaConMacrosVolcadas): the chosen meal absorbs the day's remaining
        // macros — but ONLY over the REGULAR comidas budget; peri (intra/post) is excluded from
        // the volcado (Calma's "Macros para las comidas" = 190/130/60 ≠ day total incl. peri).
        if (activeVolcado) {
            const isPeriMeal = mealKey === 'Intra' || mealKey === 'Post';
            if (mealKey === activeVolcado) {
                const regulars = getMealOrder().filter(k => !['Intra', 'Post'].includes(k));
                const dist = distribution?.comidas || {};
                const budget = regulars.reduce((acc, k) => {
                    const t = dist[k] || {};
                    return { P: acc.P + (t.P || 0), H: acc.H + (t.H || 0), G: acc.G + (t.G || 0) };
                }, { P: 0, H: 0, G: 0 });
                const otherServed = regulars.filter(k => k !== activeVolcado).reduce((acc, k) => {
                    const m = calculateMealMacros(k);
                    return { P: acc.P + m.P, H: acc.H + m.H, G: acc.G + m.G };
                }, { P: 0, H: 0, G: 0 });
                const r1 = (v) => Math.max(0, Math.round(v * 10) / 10);
                return { P: r1(budget.P - otherServed.P), H: r1(budget.H - otherServed.H), G: r1(budget.G - otherServed.G) };
            }
            // Peri keeps its normal peri target (just locked from editing); other regular meals
            // are locked to their served macros (cuadrada).
            if (isPeriMeal) return distribution?.periworkout?.[mealKey] || { P: 0, H: 0, G: 0 };
            return calculateMealMacros(mealKey);
        }

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
        // Calma margenValido = 4: a macro is OK while |target - served| < 4. "Sobra" only when
        // a macro genuinely overshoots by >= 4; "falta" otherwise. (margin 0 wrongly flagged
        // a 0.2 g overshoot as "sobra".)
        const margin = 4;
        const isPeriMeal = mealKey === 'Intra' || mealKey === 'Post';
        const pOk = Math.abs(target.P - served.P) < margin;
        const hOk = Math.abs(target.H - served.H) < margin;
        const gOk = isPeriMeal || Math.abs(target.G - served.G) < margin;
        if (pOk && hOk && gOk) return 'cuadrada';
        if (served.P - target.P >= margin || served.H - target.H >= margin ||
            (!isPeriMeal && served.G - target.G >= margin)) return 'sobra';
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
        const isPorUnidad = food.por_unidad ?? food.unidades;
        const unitWeight = food.peso_unidad || food.racion || 100;
        if (isPorUnidad && unitWeight > 0) {
            const units = qty / unitWeight;
            const rounded = Math.round(units * 2) / 2;
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
                const margin = 0;
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

    // Calma computes a food's macros synchronously on the client (K() = raw post-regla
    // macros × quantity), never per-keystroke server calls. We do the same: scale the
    // stored raw fields locally. This is race-free (no await between read and write) — the
    // old version read mealsData from the render closure and awaited an API call, so rapid
    // clicks overwrote each other and left cantidad_g out of sync with macros_efectivos
    // (the "suma de a poco" lag). Calma also lets you set ANY quantity past the target
    // (bars just go red); no block.
    const scaleFood = (food, newQty) => {
        const isUnit = food.por_unidad ?? food.unidades;
        const racion = food.racion || 100;
        // unidades: raw fields are per-unit -> scale by units (qty/racion). granel: per-100g.
        const mult = isUnit ? (racion ? newQty / racion : 0) : newQty / 100;
        const m = (k) => Math.round((food[k] || 0) * mult * 10) / 10;
        return { ...food, cantidad_g: newQty, macros_efectivos: { P: m('proteinas'), H: m('hidratos'), G: m('grasas') } };
    };

    const updateFoodQuantity = (mealKey, foodIndex, delta) => {
        setMealsData(prev => {
            const foods = [...(prev[mealKey]?.alimentos || [])];
            const food = foods[foodIndex];
            if (!food) return prev;
            const increment = delta !== null ? delta : getQuantityIncrement(food);
            const newQuantity = Math.max(1, (food.cantidad_g || 0) + (delta !== null ? delta : increment));
            foods[foodIndex] = scaleFood(food, newQuantity);
            return { ...prev, [mealKey]: { alimentos: foods } };
        });
    };

    const updateFoodQuantityDirect = (mealKey, foodIndex, newQuantity) => {
        const quantity = Math.max(1, parseInt(newQuantity) || 1);
        setMealsData(prev => {
            const foods = [...(prev[mealKey]?.alimentos || [])];
            const food = foods[foodIndex];
            if (!food) return prev;
            foods[foodIndex] = scaleFood(food, quantity);
            return { ...prev, [mealKey]: { alimentos: foods } };
        });
        setEditingQuantity({ mealKey: null, foodIndex: null });
    };

    const removeFood = (mealKey, foodIndex) => {
        setMealsData(prev => ({
            ...prev,
            [mealKey]: { alimentos: (prev[mealKey]?.alimentos || []).filter((_, i) => i !== foodIndex) }
        }));
    };

    // Reordenar ingrediente hacia arriba — replica Calma Dieta.subir = mover(e, -1):
    // saca el elemento en i-1 y lo reinserta en i (swap adyacente con el anterior).
    const moveFoodUp = (mealKey, foodIndex) => {
        if (foodIndex <= 0) return;
        setMealsData(prev => {
            const foods = [...(prev[mealKey]?.alimentos || [])];
            const n = foods.splice(foodIndex - 1, 1);
            foods.splice(foodIndex, 0, n[0]);
            return { ...prev, [mealKey]: { ...prev[mealKey], alimentos: foods } };
        });
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
                    is_cuadrado: getDayStatus() === 'cuadrado',
                    comida_volcada: volcadoMeal,
                })
            });
            toast.success('Dieta guardada');
        } catch (err) { toast.error('Error guardando dieta'); }
    };

    const copyDiet = async () => {
        if (!copyDate) { toast.error('Selecciona una fecha'); return; }
        try {
            const sourceDiet = await api(`/api/diets/${currentDate}`);
            if (!sourceDiet || !sourceDiet.exists) {
                toast.error('No hay dieta guardada para hoy');
                return;
            }
            await api('/api/diets', {
                method: 'POST',
                body: JSON.stringify({
                    fecha: copyDate,
                    tipo_dia: sourceDiet.tipo_dia,
                    num_comidas: sourceDiet.num_comidas,
                    momento_entreno: sourceDiet.momento_entreno,
                    opcion_peri: sourceDiet.opcion_peri,
                    comidas: sourceDiet.comidas,
                    macros_snapshot: sourceDiet.macros_snapshot,
                    distribution_targets: sourceDiet.distribution_targets,
                    is_cuadrado: sourceDiet.is_cuadrado,
                })
            });
            toast.success(`Copiada a ${formatDate(copyDate)}`);
            setCopyModalOpen(false);
            setCopyDate('');
        } catch (err) { toast.error(err.message || 'Error copiando dieta'); }
    };

    // ── Dietas favoritas (Calma guardarFavorita / favoritas) ──────────────────
    const loadDietFavorites = async () => {
        try {
            const res = await api('/api/diets/favorites');
            setDietFavorites(res.favorites || []);
        } catch (err) { setDietFavorites([]); }
    };

    const saveDietFavorite = async (name) => {
        try {
            await api('/api/diets/favorites', {
                method: 'POST',
                body: JSON.stringify({
                    name,
                    tipo_dia: tipoDia, num_comidas: numComidas,
                    momento_entreno: momentoEntreno, opcion_peri: opcionPeri,
                    comidas: mealsData, macros_snapshot: distribution?.resumen,
                    distribution_targets: distribTargetsOverlay || null,
                })
            });
            toast.success('Favorita guardada');
            loadDietFavorites();
        } catch (err) { toast.error('Error guardando favorita'); }
    };

    const applyDietFavorite = (fav) => {
        // Load the favorite's meals + config into the current day (does NOT auto-save; the
        // user saves/auto-saves the day after). Foods keep their stored macros_efectivos + raw.
        setTipoDia(fav.tipo_dia || 'entrenamiento');
        setNumComidas(fav.num_comidas || 4);
        setMomentoEntreno(fav.momento_entreno ?? 1);
        setOpcionPeri(normPeri(fav.opcion_peri));
        setMealsData(fav.comidas || {});
        setDistribTargetsOverlay(fav.distribution_targets || null);
        setVolcadoMeal(null);
        setFavoritesModalOpen(false);
        toast.success(`Aplicada: ${fav.name}`);
        loadDistribution({
            tipoDia: fav.tipo_dia || 'entrenamiento',
            numComidas: (fav.num_comidas === 3) ? 4 : (fav.num_comidas || 4),
            momentoEntreno: fav.momento_entreno ?? 1,
            opcionPeri: normPeri(fav.opcion_peri),
        });
    };

    const deleteDietFavorite = async (id) => {
        try {
            await api(`/api/diets/favorites/${id}`, { method: 'DELETE' });
            setDietFavorites(prev => prev.filter(f => f.id !== id));
        } catch (err) { toast.error('Error eliminando favorita'); }
    };

    // Day summary
    // Per-meal builder mode (manual | auto). Default auto. Switching never touches the
    // already-loaded foods (spread prev[mealKey]); autosave persists `modo` inside comidas.
    const setMealMode = (mealKey, modo) => {
        setMealsData(prev => ({
            ...prev,
            [mealKey]: { alimentos: [], ...(prev[mealKey] || {}), modo },
        }));
    };

    const dayMacros = calculateDayMacros();
    const dayTarget = distribution?.resumen || { P_total: 0, H_total: 0, G_total: 0, kcal_total: 0 };
    // Peri (intra/post) grasas do NOT count toward the comidas budget. Calma: peri objetivo has
    // no grasas key, so resumen.G_total = sum(comidas.G) only (backend macro_distribution sums
    // peri P/H but NOT G). dayMacros.G however includes peri served grasas → subtract them so the
    // comidas G served stays consistent with the comidas-only G_total. (P/H need no subtraction:
    // their _total budgets already include peri.)
    const servedPeriG = (calculateMealMacros('Intra').G || 0) + (calculateMealMacros('Post').G || 0);
    const comidasG = dayMacros.G - servedPeriG;
    const remainingDay = {
        P: Math.max(0, Math.round((dayTarget.P_total || 0) - dayMacros.P)),
        H: Math.max(0, Math.round((dayTarget.H_total || 0) - dayMacros.H)),
        G: Math.max(0, Math.round((dayTarget.G_total || 0) - comidasG)),
    };

    // Calma volcarMacros(t): meal `t` absorbs the day's remaining macros (target computed in
    // getMealTarget), every OTHER meal is locked. Locking lives in `volcadoMeal` state, not in
    // an overlay, so removing the volcado restores the normal per-meal targets exactly.
    const isMealLocked = (mealKey) => activeVolcado != null && mealKey !== activeVolcado;

    const persistVolcado = async (meal) => {
        try {
            await api('/api/diets', {
                method: 'POST',
                body: JSON.stringify({
                    fecha: currentDate,
                    tipo_dia: tipoDia, num_comidas: numComidas,
                    momento_entreno: momentoEntreno, opcion_peri: opcionPeri,
                    comidas: mealsData, macros_snapshot: distribution?.resumen,
                    distribution_targets: distribTargetsOverlay || null,
                    is_cuadrado: getDayStatus() === 'cuadrado',
                    comida_volcada: meal,
                })
            });
        } catch (err) { /* silent: volcado state is already applied in the UI */ }
    };

    const handleVolcarToMeal = (mealKey) => {
        if (['Intra', 'Post'].includes(mealKey)) return;
        setVolcadoMeal(mealKey);
        persistVolcado(mealKey);
        toast.success(`Macros volcados en ${mealInfo[mealKey]?.name} — las demás comidas quedan bloqueadas`);
    };

    const handleEliminarVolcado = () => {
        setVolcadoMeal(null);
        persistVolcado(null);
        toast.info('Volcado eliminado — reparto normal restaurado');
    };
    const dayKcal = dayMacros.P * 4 + dayMacros.H * 4 + comidasG * 9;  // peri grasas excluded (match G_total)
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
        const margin = 0;
        const pDiff = dayMacros.P - (dayTarget.P_total || 0);
        const hDiff = dayMacros.H - (dayTarget.H_total || 0);
        const gDiff = comidasG - (dayTarget.G_total || 0);  // peri grasas excluded from comidas G

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

    // Latest savable snapshot for auto-save (read in the [currentDate] cleanup). Mirrors the
    // manual saveDiet payload. Updated every render so the cleanup sees the data of the date
    // being left (state hasn't reloaded the new date yet when the cleanup fires).
    autoSaveRef.current = {
        tipo_dia: tipoDia,
        num_comidas: numComidas,
        momento_entreno: momentoEntreno,
        opcion_peri: opcionPeri,
        comidas: mealsData,
        macros_snapshot: distribution?.resumen,
        distribution_targets: distribTargetsOverlay || null,
        is_cuadrado: getDayStatus() === 'cuadrado',
        comida_volcada: volcadoMeal,
    };

    // Calma macrosParaVolcar(e): the volcar action is offered on meal `e` ONLY when `e` is the
    // SINGLE regular meal still not cuadrada and no volcado is active (comidasNoValidas.length
    // == 1 && comidasNoValidas[0] == e && !comidaConMacrosVolcadas). Peri meals don't count.
    const volcarTargetMeal = (() => {
        if (activeVolcado || singleMeal) return null; // Calma: volcar disabled in single-meal mode
        const regulars = getMealOrder().filter(k => !['Intra', 'Post'].includes(k));
        const noValidas = regulars.filter(k => getMealStatus(k) !== 'cuadrada');
        return noValidas.length === 1 ? noValidas[0] : null;
    })();

    // Meal info
    const mealInfo = {
        C1: { name: singleMeal ? 'Comida única' : 'Comida 1', shortName: 'C1', emoji: singleMeal ? '🍽️' : '🌅' },
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
            <div className="min-h-[60vh] flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand border-t-transparent" />
                    <p className="text-muted-foreground text-sm">Cargando...</p>
                </div>
            </div>
        );
    }

    // ===== SHOW PREFERENCES SETUP IF NEEDED =====
    if (preferencesLoading) {
        return (
            <div className="min-h-[60vh] flex items-center justify-center">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-brand border-t-transparent" />
            </div>
        );
    }
    
    if (showPreferencesSetup) {
        return (
            <PreferencesSetup
                api={api}
                initialPreferences={userPreferences}
                initialAvoidedCategories={avoidedCategories}
                initialAvoidedKeywords={avoidedKeywords}
                onSave={handlePreferencesSaved}
                onCancel={userPreferences.length > 0 ? () => setShowPreferencesSetup(false) : undefined}
                isEditMode={userPreferences.length > 0}
            />
        );
    }

    // ===== MAIN RENDER =====
    const mealCardProps = {
        mealInfo, mealsData, expandedMeals, setExpandedMeals, getMealTarget, calculateMealMacros,
        getMealStatus, loadMenuOptions, setBuildMealModal, openRepeatModal, removeFood, moveFoodUp,
        updateFoodQuantity, updateFoodQuantityDirect, editingQuantity, setEditingQuantity,
        getQuantityIncrement, clearMeal, getFoodEmoji, formatFoodQuantity, setMealMode,
    };
    const renderMealCard = (mealKey, forceExpanded) => (
        <MealCard
            key={mealKey + (forceExpanded ? '-d' : '-m')}
            forceExpanded={forceExpanded}
            mealKey={mealKey}
            {...mealCardProps}
            isLocked={isMealLocked(mealKey)}
            canVolcar={mealKey === volcarTargetMeal}
            onVolcar={handleVolcarToMeal}
            mealMode={mealsData[mealKey]?.modo === 'manual' ? 'manual' : 'auto'}
        />
    );

    const renderActions = (suffix = '') => (
        <div className="surface p-3 grid grid-cols-2 gap-2">
            <button onClick={exportPdf} disabled={exportingPdf} data-testid={`export-pdf-btn${suffix}`} className="btn-outline-brand w-full flex items-center justify-center gap-2 text-sm py-2.5">
                {exportingPdf ? <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" /> : <FileDown className="w-4 h-4" />} PDF
            </button>
            <button onClick={() => setCopyModalOpen(true)} className="btn-outline-brand w-full flex items-center justify-center gap-2 text-sm py-2.5">
                <Copy className="w-4 h-4" /> Copiar
            </button>
        </div>
    );

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1400px] mx-auto pb-24 lg:pb-10 animate-fade-in" data-testid="nutrition-page">
            <header className="flex items-center justify-between gap-4 mb-4">
                <div>
                    <p className="caption text-brand mb-1">Plan nutricional</p>
                    <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none">Nutrición</h1>
                </div>
                <div className="flex items-center gap-2">
                    <button onClick={exportPdf} disabled={exportingPdf} data-testid="export-pdf-btn"
                        className="hidden sm:inline-flex items-center gap-2 surface px-3.5 py-2 text-sm font-semibold text-muted-foreground hover:text-brand transition-colors" title="Exportar a PDF">
                        {exportingPdf ? <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" /> : <FileDown size={16} />} PDF
                    </button>
                    <button onClick={() => setCopyModalOpen(true)}
                        className="hidden sm:inline-flex items-center gap-2 surface px-3.5 py-2 text-sm font-semibold text-muted-foreground hover:text-brand transition-colors" title="Copiar dieta a otro día">
                        <Copy size={16} /> Copiar
                    </button>
                    <button onClick={() => setShowPreferencesSetup(true)} data-testid="open-preferences-btn"
                        className="inline-flex items-center gap-2 surface px-3.5 py-2 text-sm font-semibold text-muted-foreground hover:text-brand transition-colors" title="Preferencias alimentarias">
                        <SlidersHorizontal size={16} /> <span className="hidden sm:inline">Preferencias</span>
                    </button>
                </div>
            </header>

            {/* Resumen del día */}
                <DaySummary
                    tipoDia={tipoDia}
                    summaryExpanded={summaryExpanded}
                    setSummaryExpanded={setSummaryExpanded}
                    dayMacros={dayMacros}
                    dayTarget={dayTarget}
                    servedPeriP={servedPeriP}
                    servedPeriH={servedPeriH}
                    servedPeriG={servedPeriG}
                    totalPeriP={totalPeriP}
                    totalPeriH={totalPeriH}
                    opcionPeri={opcionPeri}
                    mealOrder={getMealOrder()}
                    mealInfo={mealInfo}
                    calculateMealMacros={calculateMealMacros}
                    getMealStatus={getMealStatus}
                    getDayStatus={getDayStatus}
                />

                {/* ── Controles del día (2 tarjetas compactas: Día unificado + Configuración) ── */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-5 items-stretch mt-6 mb-6" data-testid="nutrition-controls">
                    {/* Tarjeta Día: navegación de fecha + tipo de día unificados */}
                    <div className="surface p-4 sm:p-5 lg:col-span-5 flex flex-col gap-3.5">
                        <div className="flex items-center justify-between gap-3">
                            <button onClick={() => changeDate(-1)} aria-label="Día anterior" className="w-9 h-9 rounded-full flex items-center justify-center text-muted-foreground hover:text-brand hover:bg-brand/10 transition-colors flex-shrink-0">
                                <ChevronLeft className="w-5 h-5" />
                            </button>
                            <button onClick={() => setCalendarOpen(true)} data-testid="open-calendar-btn" className="flex items-center justify-center gap-2.5 flex-1 min-w-0 h-10 rounded-xl hover:bg-muted/60 transition-colors">
                                <Calendar className="w-5 h-5 text-brand flex-shrink-0" />
                                <span className="font-heading font-bold text-xl text-foreground capitalize truncate">{formatDate(currentDate)}</span>
                            </button>
                            <button onClick={() => changeDate(1)} aria-label="Día siguiente" className="w-9 h-9 rounded-full flex items-center justify-center text-muted-foreground hover:text-brand hover:bg-brand/10 transition-colors flex-shrink-0">
                                <ChevronRight className="w-5 h-5" />
                            </button>
                        </div>
                        <div className="grid grid-cols-2 gap-2.5 flex-1">
                            <button
                                className={`h-full min-h-[48px] px-3 rounded-2xl text-sm font-bold transition-all ${tipoDia === 'entrenamiento' ? 'bg-brand text-white shadow-sm' : 'bg-muted text-muted-foreground hover:text-foreground'}`}
                                onClick={() => handleSetTipoDia('entrenamiento')}
                                data-testid="tipo-dia-entrenamiento"
                            >
                                <span className="sm:hidden">Entreno</span>
                                <span className="hidden sm:inline">Día de entrenamiento</span>
                            </button>
                            <button
                                className={`h-full min-h-[48px] px-3 rounded-2xl text-sm font-bold transition-all ${tipoDia === 'descanso' ? 'bg-brand text-white shadow-sm' : 'bg-muted text-muted-foreground hover:text-foreground'}`}
                                onClick={() => handleSetTipoDia('descanso')}
                                data-testid="tipo-dia-descanso"
                            >
                                <span className="sm:hidden">Descanso</span>
                                <span className="hidden sm:inline">Día de descanso</span>
                            </button>
                        </div>
                    </div>

                    {/* Tarjeta Configuración (3 selects en una línea) */}
                    <div className="surface p-4 sm:p-5 lg:col-span-7 flex flex-col justify-center">
                        <div className="flex flex-col sm:flex-row sm:items-end gap-4 sm:gap-5">
                            <ConfigSection
                                inline
                                tipoDia={tipoDia}
                                momentoEntreno={momentoEntreno}
                                setMomentoEntreno={handleSetMomentoEntreno}
                                opcionPeri={opcionPeri}
                                setOpcionPeri={handleSetOpcionPeri}
                                numComidas={numComidas}
                                setNumComidas={handleSetNumComidas}
                                singleMeal={singleMeal}
                            />
                        </div>
                    </div>
                </div>

                {/* ── Comidas: selector en columna + detalle ── */}
                <div data-testid="nutrition-meals">
                    {/* Volcado de macros banner (ancho completo) */}
                    {activeVolcado && (
                        <div className="surface p-4 mb-4 flex items-center justify-between gap-3 border-brand/30">
                            <div className="min-w-0">
                                <p className="font-bold text-foreground truncate">Macros volcados en {mealInfo[activeVolcado]?.name}</p>
                                <p className="text-xs text-muted-foreground">Las demás comidas quedan bloqueadas hasta quitarlo.</p>
                            </div>
                            <button
                                className="shrink-0 rounded-xl font-bold text-sm px-4 py-2 border border-brand text-brand hover:bg-brand hover:text-white transition-colors"
                                onClick={handleEliminarVolcado}
                            >
                                Quitar volcado
                            </button>
                        </div>
                    )}

                    {/* Cabecera de sección (desktop): alinea selector y detalle a la misma altura */}
                    <p className="hidden lg:block caption mb-2.5">Comidas del día</p>

                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 xl:gap-8 items-start">
                        {/* Selector de comidas (columna) — desktop lg+ */}
                        <aside className="hidden lg:block lg:col-span-4 xl:col-span-3 lg:sticky lg:top-6 self-start space-y-2" data-testid="meal-selector">
                            {getMealOrder().map(mealKey => (
                                <MealSelectorItem
                                    key={mealKey}
                                    mealKey={mealKey}
                                    mealInfo={mealInfo}
                                    getMealTarget={getMealTarget}
                                    calculateMealMacros={calculateMealMacros}
                                    getMealStatus={getMealStatus}
                                    isLocked={isMealLocked(mealKey)}
                                    selected={selectedMeal === mealKey}
                                    onSelect={() => setSelectedMeal(mealKey)}
                                />
                            ))}
                        </aside>

                        {/* Detalle (desktop) + acordeón (móvil) */}
                        <main className="lg:col-span-8 xl:col-span-9 min-w-0 space-y-5">
                            {/* Desktop: detalle de la comida seleccionada */}
                            <div className="hidden lg:block" data-testid="meal-detail">
                                {getMealOrder().includes(selectedMeal) && renderMealCard(selectedMeal, true)}
                            </div>

                            {/* Móvil/tablet (<lg): acordeón de comidas en una sola columna */}
                            <div className="lg:hidden space-y-3" data-testid="meals-accordion">
                                {getMealOrder().map(mealKey => renderMealCard(mealKey, false))}
                            </div>

                            {/* Acciones (móvil <sm: tras las comidas; en sm+ van en la tarjeta de config) */}
                            <div className="sm:hidden">
                                {renderActions('-mobile')}
                            </div>
                        </main>
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
                setMealMode={setMealMode}
                getFoodEmoji={getFoodEmoji}
                userPreferences={userPreferences}
                avoidedCategories={avoidedCategories}
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

            {/* Dietas favoritas */}
            <FavoritesModal
                open={favoritesModalOpen}
                onClose={() => setFavoritesModalOpen(false)}
                favorites={dietFavorites}
                onSave={saveDietFavorite}
                onApply={applyDietFavorite}
                onDelete={deleteDietFavorite}
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
