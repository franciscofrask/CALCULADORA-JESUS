import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useOnboarding } from '../context/OnboardingContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import {
    Copy, FileDown, SlidersHorizontal, Star, Check, AlertCircle
} from 'lucide-react';
import BrandArrow from '../components/BrandArrow';
import PreferencesSetup, { PREFERENCE_CATEGORIES } from '../components/nutrition/PreferencesSetup';
import NutritionIntro from '../components/nutrition/NutritionIntro';
import PrimeraDieta from '../components/nutrition/PrimeraDieta';
import BuildMealModal from '../components/nutrition/BuildMealModal';
import RepeatMealModal from '../components/nutrition/RepeatMealModal';
import CopyDietModal from '../components/nutrition/CopyDietModal';
import FavoritesModal from '../components/nutrition/FavoritesModal';
import DayHeader from '../components/nutrition/DayHeader';
import MealCard, { MealSelectorItem, MealTab } from '../components/nutrition/MealCard';
import { VistaComidasSelector, leerVista, guardarVista } from '../components/nutrition/VistaComidas';
import { ModoMacrosSelector, AvisoMacrosReales, leerModoMacros, guardarModoMacros } from '../components/nutrition/ModoMacros';
import { SearchFoodModal } from '../components/nutrition/SearchFoodModal';
import LibraryMenusModal from '../components/nutrition/LibraryMenusModal';
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

// La fecha de hoy en el formato con el que viajan las dietas (AAAA-MM-DD), en hora local y
// no en UTC: con `toISOString()` el que entra de madrugada veria el dia anterior.
const hoyISO = () => {
    const n = new Date();
    return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`;
};

const NutritionPage = () => {
    const { token } = useAuth();
    const navigate = useNavigate();
    const { notify } = useOnboarding();

    // Preferences state - for checking if user has configured preferences
    const [showPreferencesSetup, setShowPreferencesSetup] = useState(false);
    const [userPreferences, setUserPreferences] = useState([]);
    const [avoidedCategories, setAvoidedCategories] = useState([]);
    const [avoidedKeywords, setAvoidedKeywords] = useState([]);
    const [preferencesLoading, setPreferencesLoading] = useState(true);
    // La configuracion del dia (comidas / horario / peri) va plegada: se resume en una
    // linea de texto y solo se despliega cuando de verdad se quiere cambiar algo.
    const [configExpanded, setConfigExpanded] = useState(false);

    // Como quiere ver las comidas del dia (lista y detalle, pestañas o todo seguido).
    // Se recuerda de un dia para otro; ver components/nutrition/VistaComidas.jsx.
    const [vistaComidas, setVistaComidas] = useState(leerVista);
    const cambiarVistaComidas = useCallback((v) => { guardarVista(v); setVistaComidas(v); }, []);

    // Macros del metodo o de la etiqueta. SOLO cambia lo que se enseña: el conteo, el
    // reparto y el estado de cada comida siguen saliendo de calculateMealMacros.
    const [modoMacros, setModoMacros] = useState(leerModoMacros);
    const cambiarModoMacros = useCallback((v) => { guardarModoMacros(v); setModoMacros(v); }, []);

    // Intro guiado de primera visita (una sola vez por dispositivo)
    const [showIntro, setShowIntro] = useState(() => localStorage.getItem('nutrition-intro-seen') !== '1');
    const dismissIntro = useCallback(() => {
        localStorage.setItem('nutrition-intro-seen', '1');
        setShowIntro(false);
    }, []);

    // Paso 4 del doc: la primera vez que viene a por su dieta se le piden los gustos (que es
    // cuando sirven de algo) y se le enseña como esta repartido su dia. Va antes que el tutorial:
    // primero se configura lo suyo, y despues se le explica la pantalla.
    const [primeraDieta, setPrimeraDieta] = useState(
        () => localStorage.getItem('primera-dieta-hecha') !== '1');
    const cerrarPrimeraDieta = useCallback(() => {
        localStorage.setItem('primera-dieta-hecha', '1');
        setPrimeraDieta(false);
    }, []);

    // Date & Config state
    const [currentDate, setCurrentDate] = useState(hoyISO);
    const [tipoDia, setTipoDia] = useState('entrenamiento');
    const [numComidas, setNumComidas] = useState(4);
    const [momentoEntreno, setMomentoEntreno] = useState(1);
    const [opcionPeri, setOpcionPeri] = useState('intra_post');

    // Favorites state (alimentos favoritos; UI oculta via FOOD_FAVORITES_UI, se conserva la logica)
    const [favorites, setFavorites] = useState(new Set());

    // Data state
    const [distribution, setDistribution] = useState(null);
    // Motivo por el que no hay reparto (p.ej. "No tienes macros asignados"): sin él,
    // los objetivos por comida se pintaban a 0 sin explicación.
    const [distribError, setDistribError] = useState(null);
    const [distribTargetsOverlay, setDistribTargetsOverlay] = useState(null);
    // La calibración del día la hace el backend; si esa llamada falla, los macros que quedan
    // en pantalla son los del conteo por alimento suelto, SIN el acumulado del día. Antes se
    // fallaba en silencio y esos números se guardaban y salían en el PDF como buenos.
    const [calibracionFallida, setCalibracionFallida] = useState(false);
    // Sube al pulsar "Reintentar": el efecto de calibración se dispara con la firma del día,
    // que al reintentar es la misma, así que hace falta algo que sí cambie.
    const [calibracionIntento, setCalibracionIntento] = useState(0);
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
            // El PDF se genera en el servidor a partir de la dieta GUARDADA, no de lo que hay en
            // pantalla. Sin esto, montar el dia y pulsar PDF sin salir antes de la pantalla daba
            // siempre "No hay dieta guardada para este dia" (404).
            await flushGuardado();
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

    // Load distribution - accepts optional overrides to avoid stale closure on init
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
            setDistribError(null);
        } catch (err) {
            // Sin reparto TODOS los objetivos por comida quedan a 0 ("todo sobra" y el
            // autoajuste peta): en vez de silenciarlo, se guarda para avisar en pantalla.
            console.error('Error loading distribution:', err);
            setDistribError(err.message || 'Error de red');
        }
    }, [api, tipoDia, numComidas, momentoEntreno, opcionPeri, currentDate]);

    // Load saved diet - returns { targets, config } where config has the diet's day values
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
                return { targets: diet.distribution_targets || null, config: dietConfig, ok: true, comidas: updatedMeals };
            } else {
                setMealsData({});
                setVolcadoMeal(null);
                return { targets: null, config: null, ok: true, comidas: {} };
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
    // diet never loaded (or failed to load) - preventing accidental deletion on a race.
    const autoSaveRef = useRef({});
    const loadedDateRef = useRef(null);
    // Estado del guardado que se muestra al usuario. Antes el auto-guardado era mudo: si fallaba,
    // seguias montando el dia creyendo que estaba a salvo y lo perdias al recargar.
    const [guardadoEstado, setGuardadoEstado] = useState('idle'); // idle | guardando | guardado | error
    // Un dia que llego con alimentos y se queda vacio SI se borra (el usuario los quito). Un dia
    // que nunca los tuvo no borra nada: asi un fallo de carga no puede convertirse en un DELETE.
    const teniaAlimentosRef = useRef(false);

    const [cargaFallida, setCargaFallida] = useState(false);
    const [reintentoCarga, setReintentoCarga] = useState(0);

    // ── Copia local del dia (red de seguridad) ───────────────────────────────
    // El dia se copia en el navegador en cuanto lo tocas. Si el servidor no responde, ni la
    // pantalla se queda vacia ni se pierde nada: se recupera de aqui y se sube solo cuando el
    // servidor vuelve. La copia se borra en cuanto el guardado remoto confirma.
    const claveLocal = (date) => `nutrition_dia_${date}`;

    const guardarCopiaLocal = (date, snap) => {
        try {
            if (hayAlimentos(snap)) localStorage.setItem(claveLocal(date), JSON.stringify(snap));
        } catch (e) { /* almacenamiento lleno o bloqueado: no es critico */ }
    };
    const leerCopiaLocal = (date) => {
        try {
            const s = localStorage.getItem(claveLocal(date));
            return s ? JSON.parse(s) : null;
        } catch (e) { return null; }
    };
    const borrarCopiaLocal = (date) => {
        try { localStorage.removeItem(claveLocal(date)); } catch (e) {}
    };

    const hayAlimentos = (snap) =>
        Object.values(snap?.comidas || {}).some(m => (m?.alimentos || []).length > 0);

    // Cuando se puede escribir en el servidor: con el dia cargado (caso normal) o, si la carga
    // fallo, en cuanto haya alimentos en pantalla. Perder lo que acabas de montar es mucho peor
    // que guardar un dia que quiza no cargo del todo; y borrar nunca se permite en ese estado.
    const puedeGuardar = (snap, date) =>
        loadedDateRef.current === date || hayAlimentos(snap);

    const autoSaveDiet = useCallback(async (date, snap) => {
        if (!date || !snap) return;
        const hasFood = hayAlimentos(snap);
        // Lo primero, la copia local: es instantanea y no puede fallar por red. A partir de aqui,
        // pase lo que pase con el servidor, el dia ya no se pierde.
        guardarCopiaLocal(date, snap);
        setGuardadoEstado('guardando');
        try {
            if (hasFood) {
                await api('/api/diets', { method: 'POST', body: JSON.stringify({ fecha: date, ...snap }) });
                teniaAlimentosRef.current = true;
            } else if (teniaAlimentosRef.current) {
                await api(`/api/diets/${date}`, { method: 'DELETE' }).catch(() => {}); // 404 = nothing to delete
                teniaAlimentosRef.current = false;
            }
            borrarCopiaLocal(date);   // confirmado en el servidor: la copia ya no hace falta
            setGuardadoEstado('guardado');
            return true;
        } catch (e) {
            setGuardadoEstado('error'); // la copia local sigue ahi y el reenvio la subira
            return false;
        }
    }, [api]); // eslint-disable-line react-hooks/exhaustive-deps

    // Guardado mientras trabajas (no solo al salir de la pantalla). Sin esto, el dia vivia unicamente
    // en memoria: el PDF no encontraba nada que exportar y una recarga podia llegar antes que el
    // guardado de despedida y dejar la pantalla en blanco.
    const guardadoTimerRef = useRef(null);
    const flushGuardado = useCallback(async () => {
        if (guardadoTimerRef.current) {
            clearTimeout(guardadoTimerRef.current);
            guardadoTimerRef.current = null;
        }
        if (!puedeGuardar(autoSaveRef.current, currentDate)) return;
        await autoSaveDiet(currentDate, autoSaveRef.current);
    }, [autoSaveDiet, currentDate]); // eslint-disable-line react-hooks/exhaustive-deps

    // Reintentar a mano nunca puede costarte lo que tienes en pantalla: si hay comida montada,
    // primero se sube y solo despues se vuelve a pedir el dia al servidor. Si la subida falla,
    // no se recarga nada (recargar pisaria tu trabajo con lo que haya en el servidor).
    const reintentarCarga = useCallback(async () => {
        const snap = autoSaveRef.current;
        if (hayAlimentos(snap)) {
            const subido = await autoSaveDiet(currentDate, snap);
            if (!subido) {
                toast.error('Seguimos sin conexión. Tu día está guardado en este dispositivo');
                return;
            }
        }
        setReintentoCarga(n => n + 1);
    }, [autoSaveDiet, currentDate]); // eslint-disable-line react-hooks/exhaustive-deps

    // Reenvio automatico: mientras quede una copia local sin confirmar, se reintenta sola cada 8 s.
    // Asi un corte de red se arregla solo en cuanto vuelve, sin que tengas que hacer nada.
    useEffect(() => {
        if (guardadoEstado !== 'error' || !currentDate) return;
        const t = setInterval(() => {
            const pendiente = leerCopiaLocal(currentDate);
            if (!pendiente) { clearInterval(t); return; }
            autoSaveDiet(currentDate, autoSaveRef.current);
        }, 8000);
        return () => clearInterval(t);
    }, [guardadoEstado, currentDate, autoSaveDiet]); // eslint-disable-line react-hooks/exhaustive-deps

    // Al abrir, HOY. Antes se restauraba sin más la última fecha que se hubiera mirado, así
    // que quien echaba un vistazo al día de mañana y se salía, al volver se encontraba la
    // pantalla abierta en mañana; y quien entraba al día siguiente aterrizaba en la fecha de
    // ayer. La app tiene que abrir en el día de hoy (punto 22 del doc del 07-08).
    //
    // Lo único que se conserva es lo útil de aquello: si recargas la página en el mismo día
    // en el que estabas trabajando, vuelves al día que tenías abierto en vez de perderlo. Por
    // eso se guarda también CUÁNDO se guardó, y la fecha solo se restaura si se guardó hoy y
    // no es futura.
    useEffect(() => {
        const stored = localStorage.getItem('nutrition_last_date');
        const guardadoEn = localStorage.getItem('nutrition_last_date_guardado');
        if (stored && guardadoEn === hoyISO() && stored <= hoyISO()) {
            setCurrentDate(stored);
            return;
        }
        setCurrentDate(hoyISO());
    }, []);

    // Se guarda la fecha vista y el día en que se vio, para lo de arriba.
    useEffect(() => {
        if (!currentDate) return;
        localStorage.setItem('nutrition_last_date', currentDate);
        localStorage.setItem('nutrition_last_date_guardado', hoyISO());
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

            // Reintento automatico antes de molestar al usuario: un microcorte de red no deberia
            // costarle un aviso ni, mucho menos, el dia. Tres intentos con esperas crecientes.
            let carga = await loadDiet(currentDate);
            for (let intento = 1; !carga.ok && intento <= 2; intento++) {
                await new Promise(r => setTimeout(r, intento * 1200));
                carga = await loadDiet(currentDate);
            }
            const { targets, config: dietConfig, ok, comidas: dietComidas } = carga;
            if (targets) setDistribTargetsOverlay(targets);

            // If diet has its own config, use that (overrides profile defaults for this day)
            const finalOverrides = dietConfig || cfgOverrides;
            await loadDistribution(finalOverrides);
            setLoading(false);
            // Only enable auto-save for this date once it has loaded successfully.
            if (ok) {
                loadedDateRef.current = currentDate;
                // Lo que traia el dia al abrirlo decide si un dia vacio puede borrarse (ver autoSaveDiet).
                teniaAlimentosRef.current = hayAlimentos({ comidas: dietComidas || {} });
                setGuardadoEstado('idle');
                setCargaFallida(false);
            } else {
                // La carga fallo (red, backend caido, sesion caducada). Antes esto dejaba la pantalla
                // muda PARA SIEMPRE en esa fecha: seguias montando el dia y no se guardaba por ningun
                // camino, sin un solo aviso. Ahora se avisa, y lo que montes se guarda igualmente
                // (ver puedeGuardar); lo unico que queda prohibido es BORRAR, porque el dia vacio que
                // se ve en pantalla no es de fiar.
                setCargaFallida(true);
                teniaAlimentosRef.current = false;
                // Sin esto, el "Guardado" del dia que acabas de dejar tapaba el aviso de esta fecha.
                setGuardadoEstado('idle');
                // Si el dia tenia copia local sin subir, se recupera: no ves la pantalla en blanco
                // ni pierdes lo que montaste la ultima vez que el servidor no respondio.
                const copia = leerCopiaLocal(currentDate);
                if (copia && hayAlimentos(copia)) {
                    setMealsData(copia.comidas || {});
                    if (copia.tipo_dia) setTipoDia(copia.tipo_dia);
                    if (copia.num_comidas) setNumComidas(copia.num_comidas);
                    if (copia.momento_entreno != null) setMomentoEntreno(copia.momento_entreno);
                    if (copia.opcion_peri) setOpcionPeri(normPeri(copia.opcion_peri));
                    setVolcadoMeal(copia.comida_volcada || null);
                    setGuardadoEstado('error');   // hay algo pendiente de subir: arranca el reenvio
                    toast.info('Sin conexion con el servidor: hemos recuperado tu día de la copia local');
                }
            }
        };
        init();
    }, [currentDate, reintentoCarga]); // eslint-disable-line

    // Auto-save the date being LEFT (cleanup runs on date change and on unmount) - mirrors
    // Calma's `watch fecha` + `unmounted` -> autoGuardadoEnFecha. Guarded by loadedDateRef so
    // a not-yet-loaded date is never persisted/deleted. autoSaveDiet is kept in a ref so the
    // effect depends ONLY on currentDate (not on autoSaveDiet/api identity) - otherwise an
    // unstable `api` would re-fire the cleanup on every render and save constantly.
    const autoSaveDietRef = useRef(autoSaveDiet);
    autoSaveDietRef.current = autoSaveDiet;
    useEffect(() => {
        const dateLeaving = currentDate;
        return () => {
            if (loadedDateRef.current === dateLeaving || hayAlimentos(autoSaveRef.current)) {
                autoSaveDietRef.current(dateLeaving, autoSaveRef.current);
            }
        };
    }, [currentDate]); // eslint-disable-line react-hooks/exhaustive-deps

    // A browser REFRESH/close does NOT run React cleanup, so the unmount auto-save never fires
    // and the day looked "lost". Save synchronously via keepalive fetch (it survives unload and
    // carries the auth header). Only saves a non-empty day, and nunca borra.
    //
    // Tres eventos, no uno: `beforeunload` no es fiable en movil (iOS puede matar la pestana sin
    // dispararlo nunca), asi que se escucha tambien `pagehide` y el paso a segundo plano, que es
    // lo que si ocurre cuando cambias de aplicacion. Guardar de mas es inofensivo: es un upsert.
    useEffect(() => {
        const handler = () => {
            if (loading) return;
            const snap = autoSaveRef.current;
            if (!hayAlimentos(snap)) return;
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
        const alOcultarse = () => { if (document.visibilityState === 'hidden') handler(); };
        window.addEventListener('beforeunload', handler);
        window.addEventListener('pagehide', handler);
        document.addEventListener('visibilitychange', alOcultarse);
        return () => {
            window.removeEventListener('beforeunload', handler);
            window.removeEventListener('pagehide', handler);
            document.removeEventListener('visibilitychange', alOcultarse);
        };
    }, [currentDate, loading]);

    // Guardado con retardo: cada cambio reinicia el contador y se guarda cuando paras de tocar.
    // 1,5 s es suficiente para no disparar una peticion por cada gramo que ajustas.
    useEffect(() => {
        if (loading || !puedeGuardar(autoSaveRef.current, currentDate)) return;
        if (guardadoTimerRef.current) clearTimeout(guardadoTimerRef.current);
        guardadoTimerRef.current = setTimeout(() => {
            autoSaveDiet(currentDate, autoSaveRef.current);
        }, 1500);
        return () => {
            if (guardadoTimerRef.current) clearTimeout(guardadoTimerRef.current);
        };
    }, [mealsData, tipoDia, numComidas, momentoEntreno, opcionPeri, volcadoMeal,
        currentDate, loading]); // eslint-disable-line react-hooks/exhaustive-deps

    // Reload distribution when config changes
    useEffect(() => {
        if (!loading) loadDistribution();
    }, [tipoDia, numComidas, momentoEntreno, opcionPeri]); // eslint-disable-line

    // Objetivo por comida guardado (distribTargetsOverlay) OBSOLETO: se congela al crear la
    // dieta, pero si los macros asignados al cliente cambian después, la distribución
    // recalculada (`distribution`) ya no coincide. Sin esto, la comida seguía mostrando el
    // objetivo viejo ("cuadrada") mientras la cabecera del día usaba el nuevo ("te pasas") -
    // en comida única eso dejaba 225/240 en la comida y 180/180 en el día. Al detectar el
    // desfase descartamos el overlay: la comida pasa a usar el objetivo de HOY (coinciden) y
    // el autoguardado deja de re-persistir el valor viejo. Se ignora en modo volcado (sus
    // objetivos viven en volcadoMeal, no en el overlay).
    useEffect(() => {
        if (!distribTargetsOverlay || !distribution || volcadoMeal) return;
        const TOL = 3; // holgura por redondeos; un cambio real de macros es >= 5 g
        const stale = Object.entries(distribTargetsOverlay).some(([k, t]) => {
            const f = distribution.comidas?.[k] || distribution.periworkout?.[k];
            if (!f) return true; // la comida ya no existe en la distribución de hoy
            return Math.abs((t.P || 0) - (f.P || 0)) > TOL ||
                   Math.abs((t.H || 0) - (f.H || 0)) > TOL ||
                   Math.abs((t.G || 0) - (f.G || 0)) > TOL;
        });
        if (stale) setDistribTargetsOverlay(null);
    }, [distribTargetsOverlay, distribution, volcadoMeal]);

    // Wrappers for user-initiated config changes - persist to profile (cross-device)
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
        if (dateStr === hoyISO()) return 'Hoy';
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
        // macros - but ONLY over the REGULAR comidas budget; peri (intra/post) is excluded from
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

    // ── Calibración progresiva (proteína vegetal por acumulado del DÍA) ─────────
    // Spec 17-07-2026: tras CUALQUIER cambio de composición (añadir, quitar, editar
    // cantidades, aplicar menú, repetir, cuadrar...), el backend recalcula los macros
    // de TODO el día con los acumulados de cereales+panes y frutos secos en orden
    // cronológico. Editar una comida solo cambia esa y las posteriores (las
    // anteriores no dependen de ella). La firma solo mira ids+cantidades, así que
    // cuando vuelven los macros recalibrados la firma no cambia y no hay bucle.
    const calibracionSig = JSON.stringify(getMealOrder().map(k => [k,
        (mealsData[k]?.alimentos || []).map(a => [a.alimento_id ?? null, a.cantidad_g ?? 0])]));
    useEffect(() => {
        const order = getMealOrder();
        if (!order.some(k => (mealsData[k]?.alimentos || []).length > 0)) return;
        let cancelado = false;
        const pedirCalibracion = () => api('/api/calculator/calibrar-dia', {
            method: 'POST',
            body: JSON.stringify({
                meal_order: order,
                comidas: Object.fromEntries(order.map(k => [k,
                    (mealsData[k]?.alimentos || []).map(a => ({
                        alimento_id: a.alimento_id ?? null,
                        cantidad_g: a.cantidad_g ?? 0,
                    }))])),
            })
        });
        const timer = setTimeout(async () => {
            try {
                // Un reintento: la mayoría de los fallos aquí son un corte de red de un
                // segundo, y perder la calibración cambia los macros que se ven y se guardan.
                let res;
                try {
                    res = await pedirCalibracion();
                } catch {
                    if (cancelado) return;
                    res = await pedirCalibracion();
                }
                if (cancelado || !res?.comidas) return;
                setCalibracionFallida(false);
                setMealsData(prev => {
                    const next = { ...prev };
                    for (const k of order) {
                        if (!prev[k]) continue;
                        const resp = res.comidas[k] || [];
                        next[k] = {
                            ...prev[k],
                            alimentos: (prev[k].alimentos || []).map((a, i) => {
                                const r = resp[i];
                                if (!r || !r.macros_efectivos) return a; // alimento desconocido: se conserva
                                return {
                                    ...a,
                                    macros_efectivos: r.macros_efectivos,
                                    macros_brutos: r.macros_brutos || a.macros_brutos,
                                    que_cuenta: r.que_cuenta || a.que_cuenta,
                                };
                            }),
                        };
                    }
                    return next;
                });
            } catch (e) {
                // Se conservan los macros previos, pero SIN calibrar: hay que decirlo, porque
                // el día se guarda con estos números y son los que salen en el PDF.
                if (!cancelado) setCalibracionFallida(true);
            }
        }, 300);
        return () => { cancelado = true; clearTimeout(timer); };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [calibracionSig, calibracionIntento]);

    // Get quantity increment based on food category
    // REGLA: Para alimentos con unidades, incrementar por 1 unidad (= racion gramos)
    // Para alimentos sin unidades, incrementar por categoría
    const getQuantityIncrement = (food) => {
        const cat = food.categorias?.split(' | ')[0]?.split('.')[0] || '';
        const subCat = food.categorias?.split(' | ')[0] || '';
        // Alimentos con unidades: incrementar 1 unidad = lo que pesa una unidad
        if (esPorUnidad(food)) return pesoUnidad(food);
        
        // Verduras (cat 13): ±50g
        if (cat === '13') return 50;
        
        // Bebidas vegetales (cat 24): ±50g
        if (cat === '24') return 50;
        
        // Salsas zero (cat 16.1): ±5g
        if (subCat.startsWith('16.1')) return 5;
        
        // TODO lo demás: ±1g
        return 1;
    };

    // ¿Este alimento se cuenta por unidades (huevos, piezas de fruta, lonchas)?
    // Segun por donde haya entrado, el campo se llama de tres maneras distintas:
    // `unidades` (catalogo y handleAddFood), `por_unidad` (algunos menus) y `unidad`
    // ('unidades' | 'g', que es lo que se guarda en la dieta). Mirar solo uno dejaba
    // huevos moviendose de gramo en gramo.
    const esPorUnidad = (food) =>
        Boolean(food && (food.por_unidad ?? food.unidades ?? (food.unidad === 'unidades')));

    // Lo que pesa una unidad. Nunca 0: dividir por el peso es como se pasa a unidades.
    const pesoUnidad = (food) => (food?.peso_unidad || food?.racion || 100) || 100;

    // Format quantity for display: "2 ud" for unit foods, "120g" for gram foods
    const formatFoodQuantity = (food) => {
        if (!food) return '0g';
        const qty = food.cantidad_g || 0;
        const isPorUnidad = esPorUnidad(food);
        const unitWeight = pesoUnidad(food);
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
            toast.error(`${food.nombre} ya está en esta comida - ajusta su cantidad directamente.`);
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

            // Por debajo de su cantidad mínima el alimento se descarta, no entra a cero. Sin
            // esto, la comida acababa con líneas tipo "Queso Havarti · 0 ud": el backend
            // devolvía 0 para decir "no cabe" y aquí ese 0, al no tener macros, se tomaba por
            // un alimento libre y se colaba igual.
            if (result.cabe === false || !(result.cantidad_g > 0)) {
                const min = result.cantidad_minima_g;
                toast.error(min
                    ? `${food.nombre} no cabe: lo mínimo son ${min} g y no queda hueco.`
                    : `${food.nombre} no cabe en esta comida.`);
                return;
            }

            // Free foods (all zeros: konjac, salsas zero, verduras libres) always pass
            const ef = result.macros_efectivos || {};
            const isFreeFood = !ef.P && !ef.H && !ef.G;
            if (!isFreeFood) {
                const mealStatus = getMealStatus(mealKey);
                if (mealStatus === 'cuadrada' || mealStatus === 'sobra') {
                    toast.error('Esta comida ya está completa - no hay espacio para más alimentos.');
                    return;
                }
                const target = getMealTarget(mealKey);
                const served = calculateMealMacros(mealKey);
                const margin = 0;
                if ((ef.P > 0 && served.P + ef.P > target.P + margin) ||
                    (ef.H > 0 && served.H + ef.H > target.H + margin) ||
                    (ef.G > 0 && served.G + ef.G > target.G + margin)) {
                    toast.error(`${food.nombre} no cabe - superaría los macros de esta comida.`);
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
                unidades: food.unidades || false,
                url: food.url || null,   // para que el enlace salga ya, sin esperar a recargar el dia
            };
            setMealsData(prev => ({
                ...prev,
                [mealKey]: { alimentos: [...(prev[mealKey]?.alimentos || []), newFood] }
            }));
            setAddFoodModal({ open: false, mealKey: null });
            setSearchQuery('');
            setSearchCategory('');
            toast.success(`${food.nombre} añadido`);
            notify('nutrition-add-food'); // auto-avanza el tour si está en ese paso
        } catch (err) {
            toast.error('Error añadiendo alimento');
        }
    };

    /**
     * Cambia la cantidad de un alimento y reajusta sus macros, sin llamar al servidor.
     *
     * Calma lo hace igual (K() = macros POST-REGLA x cantidad) y sin await, para que
     * pulsar -/+ rapido no deje `cantidad_g` desincronizada de los macros.
     *
     * La clave es "post-regla". Antes esto escalaba los campos crudos del catalogo
     * (`food.proteinas`...), que son los de la ETIQUETA: al tocar -/+ en un pan se le
     * colaban 6,8 g de proteina y 1,4 g de grasa que el metodo no cuenta, y el dia
     * pasaba a contar de mas hasta que el servidor recalculaba. Peor aun: como al
     * guardar un alimento no se guardan esos campos crudos, en los dias normales
     * `food.proteinas` ni existe y los macros se iban a 0.
     *
     * Ahora se escalan los `macros_efectivos` que ya tiene el alimento, que salieron
     * del motor con las reglas aplicadas. Es EQUIVALENTE a recalcular porque los
     * macros del metodo son lineales con la cantidad: las reglas (que() y el 25%)
     * deciden que cuenta y cuanto por 100 g / racion, no dependen de cuanto pongas.
     *
     * La calibracion progresiva del dia (cereales/panes y frutos secos por acumulado)
     * SI depende del resto del dia, pero de eso ya se encarga el recalculo del
     * servidor que se dispara tras cada cambio; esto es solo el eco inmediato.
     */
    const scaleFood = (food, newQty) => {
        const qtyPrevia = food.cantidad_g || 0;
        const ef = food.macros_efectivos;
        const r1 = (x) => Math.round((x || 0) * 10) / 10;

        if (qtyPrevia > 0 && ef && typeof ef.P === 'number') {
            const factor = newQty / qtyPrevia;
            return {
                ...food,
                cantidad_g: newQty,
                macros_efectivos: { P: r1(ef.P * factor), H: r1(ef.H * factor), G: r1(ef.G * factor) },
            };
        }

        // Sin cantidad previa (o sin macros ya calculados) no hay proporcion que aplicar.
        // Se deja la cantidad y se conservan los macros que hubiera: el recalculo del
        // servidor los pondra bien. Inventarlos con los crudos es lo que fallaba antes.
        return { ...food, cantidad_g: newQty };
    };

    // Lo minimo que tiene sentido de un alimento: de los que van por unidades, una
    // unidad entera (medio huevo no se pone en una dieta); del resto, 1 g.
    const cantidadMinima = (food) => (esPorUnidad(food) ? pesoUnidad(food) : 1);

    /**
     * Cambia la cantidad de un alimento, y lo QUITA si baja de su minimo.
     *
     * Antes el suelo era `Math.max(1, ...)`: 1 gramo. En un alimento por unidades eso
     * dejaba "0 ud" en pantalla -- un huevo que ni esta ni deja de estar -- pero
     * seguia contando su gramo en los macros de la comida. Bajar del minimo es decir
     * "quitalo", asi que se quita.
     */
    const updateFoodQuantity = (mealKey, foodIndex, delta) => {
        setMealsData(prev => {
            const foods = [...(prev[mealKey]?.alimentos || [])];
            const food = foods[foodIndex];
            if (!food) return prev;
            const increment = delta !== null ? delta : getQuantityIncrement(food);
            const bruta = (food.cantidad_g || 0) + increment;
            const minimo = cantidadMinima(food);
            if (bruta < minimo) {
                return { ...prev, [mealKey]: { alimentos: foods.filter((_, i) => i !== foodIndex) } };
            }
            foods[foodIndex] = scaleFood(food, bruta);
            return { ...prev, [mealKey]: { alimentos: foods } };
        });
    };

    /**
     * Cantidad escrita a mano. En los alimentos por unidades se escriben UNIDADES,
     * que es como los piensa el usuario ("2 huevos", no "126 g de huevo"); aqui se
     * pasan a gramos, que es como se guardan. Acepta medias unidades.
     */
    const updateFoodQuantityDirect = (mealKey, foodIndex, valor) => {
        setMealsData(prev => {
            const foods = [...(prev[mealKey]?.alimentos || [])];
            const food = foods[foodIndex];
            if (!food) return prev;
            const escrito = parseFloat(String(valor).replace(',', '.'));
            const porUnidad = esPorUnidad(food);
            const gramos = Number.isFinite(escrito)
                ? (porUnidad ? escrito * pesoUnidad(food) : escrito)
                : 0;
            if (gramos < cantidadMinima(food)) {
                return { ...prev, [mealKey]: { alimentos: foods.filter((_, i) => i !== foodIndex) } };
            }
            foods[foodIndex] = scaleFood(food, Math.round(gramos));
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

    // Reordenar ingrediente hacia arriba - replica Calma Dieta.subir = mover(e, -1):
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

    // Vaciar sin el confirm del navegador: ese dialogo bloquea la pestaña entera y no
    // pega con el resto de la app. Se vacia directamente y se ofrece deshacer, que en
    // movil es mas comodo y sigue siendo reversible.
    const clearMeal = (mealKey) => {
        const previo = mealsData[mealKey];
        const nombre = mealInfo[mealKey]?.name || 'La comida';
        setMealsData(prev => ({ ...prev, [mealKey]: { alimentos: [] } }));
        toast.success(`${nombre} vaciada`, {
            duration: 8000,
            action: {
                label: 'Deshacer',
                onClick: () => setMealsData(prev => ({ ...prev, [mealKey]: previo })),
            },
        });
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

    // "Sugiéreme un menú": modal con dos pestañas. Biblioteca REAL (db.meal_library,
    // 266k comidas de clientes ya cuadradas con el método): menús por CERCANÍA al
    // objetivo de la comida, que se vuelcan tal cual (o ajustados con sus palancas).
    // Recetario (menu_templates, recetas ELM): la receta se cuadra a los macros al
    // elegirla (menu-apply). El modal carga sus propios datos; aquí solo se abre y
    // se vuelca lo que devuelve, que en ambos casos viene con la misma forma.
    const loadMenuOptions = (mealKey) => {
        setMenuOptionsModal({ open: true, mealKey });
    };

    const applyLibraryMenu = (menu) => {
        const mealKey = menuOptionsModal.mealKey;
        // Los items ya vienen del backend con las cantidades AJUSTADAS por las
        // palancas del menú y sus macros calculados: aquí solo se vuelcan.
        const foods = menu.items.map(item => ({
            alimento_id: item.alimento_id,
            nombre: item.nombre,
            cantidad_g: item.cantidad_g,
            macros_efectivos: item.macros_efectivos,
            macros_brutos: item.macros_brutos,
            que_cuenta: item.que_cuenta,
            categorias: item.categorias,
            racion: item.racion,
            unidades: item.unidades,
            url: item.url || null,   // para que el enlace salga ya, sin esperar a recargar el dia
        }));
        setMealsData(prev => ({ ...prev, [mealKey]: { alimentos: foods } }));
        setMenuOptionsModal({ open: false, mealKey: null });
        if (menu.origen === 'recetario') {
            // Pestaña Recetario: el backend ya ha cuadrado la receta a los macros
            toast.success(menu.clavado
                ? `${menu.nombre}: clava tu objetivo`
                : menu.cuadrada
                    ? `${menu.nombre}, cuadrada a tu objetivo`
                    : `${menu.nombre} añadida, ajusta a mano lo que falte`);
            return;
        }
        toast.success(menu.clavado
            ? 'Menú añadido: clava tu objetivo'
            : (menu.cuadrada || menu.ajustado)
                ? 'Menú añadido, ajustado a tu objetivo'
                : 'Menú añadido tal cual (menú real, cercano a tu objetivo)');
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

    const applyDietFavorite = async (fav, { adaptar = false } = {}) => {
        // Aplica la favorita RE-AJUSTANDO sus cantidades a los macros de HOY (no arrastra los
        // objetivos guardados): reusa /refit-diet, que redimensiona cada alimento con la lógica
        // CALMA sin pasarse y respetando el mínimo. No auto-guarda; el día se guarda después.
        // Modo adaptar (entreno<->descanso): se mantiene el tipo de día ACTUAL y las comidas
        // que no existen en él (p.ej. el peri en descanso) se quitan con aviso.
        const cfg = adaptar ? {
            tipoDia,                                    // el del día, no el de la favorita
            numComidas: fav.num_comidas || 4,           // las claves C1..Cn deben casar
            momentoEntreno,
            opcionPeri,
        } : {
            tipoDia: fav.tipo_dia || 'entrenamiento',
            numComidas: fav.num_comidas || 4,
            momentoEntreno: fav.momento_entreno ?? 1,
            opcionPeri: normPeri(fav.opcion_peri),
        };
        if (!adaptar) setTipoDia(cfg.tipoDia);
        setNumComidas(cfg.numComidas);
        setMomentoEntreno(cfg.momentoEntreno);
        setOpcionPeri(cfg.opcionPeri);
        setVolcadoMeal(null);
        setDistribTargetsOverlay(null);   // usar los macros de HOY, no los objetivos guardados
        setFavoritesModalOpen(false);
        try {
            const res = await api('/api/calculator/refit-diet', {
                method: 'POST',
                body: JSON.stringify({
                    fecha: currentDate,
                    tipo_dia: cfg.tipoDia,
                    num_comidas: (fav.num_comidas === 3) ? 4 : cfg.numComidas,
                    momento_entreno: cfg.momentoEntreno,
                    opcion_peri: cfg.opcionPeri,
                    comidas: fav.comidas || {},
                    descartar_sin_objetivo: adaptar,
                }),
            });
            setMealsData(res.comidas || {});
            if (res.distribution) setDistribution(res.distribution);

            const excluidos = res.excluidos || [];
            const periQuitado = excluidos.filter(e => e.motivo === 'sin_objetivo_en_dia');
            const noCaben = excluidos.filter(e => e.motivo !== 'sin_objetivo_en_dia');
            const etiquetaDia = cfg.tipoDia === 'descanso' ? 'descanso' : 'entreno';

            if (adaptar && periQuitado.length) {
                toast.warning(`Aplicada "${fav.name}" adaptada a tu día de ${etiquetaDia}. El intra/post se ha quitado porque hoy no hay periworkout.`);
            } else if (adaptar) {
                toast.success(`Aplicada "${fav.name}" adaptada a tu día de ${etiquetaDia}`);
            } else if (!noCaben.length) {
                toast.success(`Aplicada "${fav.name}" y ajustada a tus macros`);
            }
            if (noCaben.length) toast.warning(`${noCaben.length} alimento(s) no cabían ni al mínimo y se quitaron.`);

            // Descanso -> entreno: la favorita no trae peri; avisar de que queda vacío.
            const trae = (k) => ((fav.comidas?.[k]?.alimentos) || []).length > 0;
            if (adaptar && cfg.tipoDia === 'entrenamiento' && cfg.opcionPeri !== 'sin_peri' && !trae('Intra') && !trae('Post')) {
                toast.info('El peri ha quedado vacío: añádelo con "Sugiéreme un menú".');
            }
        } catch (err) {
            toast.error('Error al aplicar la favorita');
        }
    };

    // Cuadrar una comida a demanda: re-ajusta sus alimentos a los macros de HOY, sin pasarse y
    // respetando el mínimo de cada uno (reusa /refit-diet solo para esa comida).
    const cuadrarComida = async (mealKey) => {
        try {
            const res = await api('/api/calculator/refit-diet', {
                method: 'POST',
                body: JSON.stringify({
                    fecha: currentDate,
                    tipo_dia: tipoDia, num_comidas: numComidas,
                    momento_entreno: momentoEntreno, opcion_peri: opcionPeri,
                    comidas: { [mealKey]: mealsData[mealKey] || { alimentos: [] } },
                }),
            });
            const refit = res.comidas?.[mealKey];
            if (!refit) { toast.error('No se pudo cuadrar la comida'); return; }
            setMealsData(prev => ({ ...prev, [mealKey]: refit }));
            setDistribTargetsOverlay(null);   // pasa a mostrar los macros de hoy
            const nEx = res.excluidos?.length || 0;
            if (nEx) toast.warning(`Comida cuadrada. ${nEx} alimento(s) no cabían ni al mínimo y se quitaron.`);
            else toast.success('Comida cuadrada a tus macros');
        } catch { toast.error('No se pudo cuadrar la comida'); }
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
        toast.success(`Macros volcados en ${mealInfo[mealKey]?.name} - las demás comidas quedan bloqueadas`);
    };

    const handleEliminarVolcado = () => {
        setVolcadoMeal(null);
        persistVolcado(null);
        toast.info('Volcado eliminado - reparto normal restaurado');
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

    // ===== SIN REPARTO DE MACROS (bug 0·0·0) =====
    // Sin distribución, cada comida tendría objetivo 0P·0H·0G: "todo sobra" y el
    // autoajuste excluye todo. Mejor una pantalla clara con el porqué y la salida.
    if (!distribution && distribError) {
        const sinMacros = distribError === 'No tienes macros asignados';
        return (
            <div className="min-h-[60vh] flex items-center justify-center px-4">
                <div className="surface p-6 max-w-md w-full text-center" data-testid="distrib-error">
                    <span className="text-4xl mb-3 block">🎯</span>
                    <h2 className="font-heading font-bold text-2xl text-foreground mb-2">
                        {sinMacros ? 'Aún no tienes macros asignados' : 'No se pudo cargar el reparto del día'}
                    </h2>
                    <p className="text-sm text-muted-foreground mb-5">
                        {sinMacros
                            ? 'Sin macros no podemos repartir objetivos entre tus comidas. Calcúlalos en un minuto con la calculadora, o pídeselos a tu entrenador.'
                            : `Sin el reparto, las comidas no tienen objetivo. Inténtalo de nuevo. (${distribError})`}
                    </p>
                    <div className="flex flex-col gap-2">
                        {sinMacros ? (
                            <button className="btn-brand w-full py-2.5" data-testid="distrib-error-cta"
                                onClick={() => navigate('/dashboard/macro-calculator')}>
                                Calcular mis macros
                            </button>
                        ) : (
                            <button className="btn-brand w-full py-2.5" onClick={() => loadDistribution()}>
                                Reintentar
                            </button>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    // ===== MAIN RENDER =====
    const mealCardProps = {
        mealInfo, mealsData, expandedMeals, setExpandedMeals, getMealTarget, calculateMealMacros,
        getMealStatus, loadMenuOptions, setBuildMealModal, openRepeatModal, removeFood, moveFoodUp,
        updateFoodQuantity, updateFoodQuantityDirect, editingQuantity, setEditingQuantity,
        getQuantityIncrement, clearMeal, getFoodEmoji, formatFoodQuantity, setMealMode,
        modoMacros, esPorUnidad, pesoUnidad,
    };
    const renderMealCard = (mealKey, forceExpanded, denso = false) => (
        <MealCard
            key={mealKey + (forceExpanded ? '-d' : '-m')}
            forceExpanded={forceExpanded}
            denso={denso}
            mealKey={mealKey}
            {...mealCardProps}
            isLocked={isMealLocked(mealKey)}
            canVolcar={mealKey === volcarTargetMeal}
            onVolcar={handleVolcarToMeal}
            onCuadrar={cuadrarComida}
            mealMode={mealsData[mealKey]?.modo === 'manual' ? 'manual' : 'auto'}
        />
    );

    // Aviso de guardado. Solo aparece cuando hay algo que contar: mientras guarda, cuando acaba
    // y, sobre todo, si ha fallado (antes fallaba en silencio y el dia se perdia sin avisar).
    const renderEstadoGuardado = () => {
        // Manda sobre el resto: si el día no está calibrado, los macros que se ven no son los
        // buenos, y decir "Guardado" tan tranquilo sería peor que no decir nada.
        if (calibracionFallida) {
            return (
                <button onClick={() => { setCalibracionFallida(false); setCalibracionIntento(n => n + 1); }}
                    title="Los macros no incluyen el acumulado del día. Toca para volver a intentarlo."
                    data-testid="calibracion-error"
                    className="flex items-center gap-1.5 text-xs font-semibold text-amber-500 hover:underline">
                    <AlertCircle className="w-3.5 h-3.5" /> Macros sin calibrar. Reintentar
                </button>
            );
        }
        if (cargaFallida && guardadoEstado !== 'guardado') {
            return (
                <button onClick={reintentarCarga} title="Vuelve a pedir el día al servidor"
                    className="flex items-center gap-1.5 text-xs font-semibold text-amber-500 hover:underline">
                    <AlertCircle className="w-3.5 h-3.5" /> Sin conexión con el servidor. Reintentar
                </button>
            );
        }
        if (guardadoEstado === 'idle') return null;
        if (guardadoEstado === 'error') {
            return (
                <button onClick={flushGuardado}
                    className="flex items-center gap-1.5 text-xs font-semibold text-red-400 hover:underline">
                    <AlertCircle className="w-3.5 h-3.5" /> No se ha podido guardar. Reintentar
                </button>
            );
        }
        return (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                {guardadoEstado === 'guardando'
                    ? <><div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" /> Guardando...</>
                    : <><Check className="w-3.5 h-3.5 text-green-500" /> Guardado</>}
            </span>
        );
    };

    const renderActions = (suffix = '') => (
        <div className="surface p-3 grid grid-cols-3 gap-2">
            <button onClick={exportPdf} disabled={exportingPdf} data-testid={`export-pdf-btn${suffix}`} className="btn-outline-brand w-full flex items-center justify-center gap-2 text-sm py-2.5">
                {exportingPdf ? <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" /> : <FileDown className="w-4 h-4" />} PDF
            </button>
            <button onClick={() => setCopyModalOpen(true)} className="btn-outline-brand w-full flex items-center justify-center gap-2 text-sm py-2.5">
                <Copy className="w-4 h-4" /> Copiar
            </button>
            <button onClick={() => { loadDietFavorites(); setFavoritesModalOpen(true); }} data-testid={`favorites-btn${suffix}`} className="btn-outline-brand w-full flex items-center justify-center gap-2 text-sm py-2.5">
                <Star className="w-4 h-4" /> Favoritas
            </button>
        </div>
    );

    return (
        <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1400px] mx-auto pb-24 lg:pb-10 animate-fade-in" data-testid="nutrition-page">
            {/* Primero los gustos (el gate de preferencias, mas arriba), luego como esta repartido
                su dia, y solo despues el tutorial de la pantalla. */}
            {primeraDieta ? (
                <PrimeraDieta
                    momentoEntreno={momentoEntreno}
                    numComidas={numComidas}
                    // La configuración del día está siempre a la vista en esta misma pantalla, así
                    // que "cambiarla" es cerrar esto (y el tutorial) para que la vea sin estorbos.
                    onIrAConfig={() => { cerrarPrimeraDieta(); dismissIntro(); }}
                    onListo={cerrarPrimeraDieta}
                />
            ) : showIntro && <NutritionIntro onClose={dismissIntro} />}
            <header className="flex items-center justify-between gap-4 mb-4">
                <div>
                    <p className="caption text-brand mb-1">Plan nutricional</p>
                    <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none">Nutrición</h1>
                    <div className="mt-1 h-4">{renderEstadoGuardado()}</div>
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
                    <button onClick={() => { loadDietFavorites(); setFavoritesModalOpen(true); }} data-testid="open-favorites-btn"
                        className="inline-flex items-center gap-2 surface px-3.5 py-2 text-sm font-semibold text-muted-foreground hover:text-brand transition-colors" title="Dietas favoritas">
                        <Star size={16} /> <span className="hidden sm:inline">Favoritas</span>
                    </button>
                    <button onClick={() => setShowPreferencesSetup(true)} data-testid="open-preferences-btn"
                        className="inline-flex items-center gap-2 surface px-3.5 py-2 text-sm font-semibold text-muted-foreground hover:text-brand transition-colors" title="Preferencias alimentarias">
                        <SlidersHorizontal size={16} /> <span className="hidden sm:inline">Preferencias</span>
                    </button>
                </div>
            </header>

            {/* Cabecera del día: fecha, tipo de día, configuración resumida y macros */}
                <DayHeader
                    currentDate={currentDate}
                    formatDate={formatDate}
                    changeDate={changeDate}
                    setCalendarOpen={setCalendarOpen}
                    handleSetTipoDia={handleSetTipoDia}
                    numComidas={numComidas}
                    setNumComidas={handleSetNumComidas}
                    momentoEntreno={momentoEntreno}
                    setMomentoEntreno={handleSetMomentoEntreno}
                    opcionPeri={opcionPeri}
                    setOpcionPeri={handleSetOpcionPeri}
                    singleMeal={singleMeal}
                    configExpanded={configExpanded}
                    setConfigExpanded={setConfigExpanded}
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
                    mealOrder={getMealOrder()}
                    mealInfo={mealInfo}
                    calculateMealMacros={calculateMealMacros}
                    getMealStatus={getMealStatus}
                    getDayStatus={getDayStatus}
                />

                <div className="border-t border-border my-6" />

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

                    {/* Cabecera de sección: el título y, a la derecha, cómo quiere verlas.
                        El switch de macros vive aquí porque solo cambia lo que pone en
                        la lista de ingredientes; ni los totales ni el reparto se mueven. */}
                    <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 mb-2.5">
                        <p className="caption">Comidas del día</p>
                        <div className="flex items-center gap-3">
                            <ModoMacrosSelector modo={modoMacros} onCambiar={cambiarModoMacros} />
                            <VistaComidasSelector vista={vistaComidas} onCambiar={cambiarVistaComidas} />
                        </div>
                    </div>
                    {modoMacros === 'reales' && <div className="mb-3"><AvisoMacrosReales /></div>}

                    {vistaComidas === 'actual' && (
                        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 xl:gap-8 items-start">
                            {/* Selector de comidas (columna) - desktop lg+ */}
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
                    )}

                    {/* Pestañas: las comidas arriba y la abierta a todo el ancho. Las pestañas
                        se desplazan en horizontal cuando no caben (móvil, o día con peri). */}
                    {vistaComidas === 'pestanas' && (
                        <div className="space-y-4">
                            <div className="overflow-x-auto border-b border-border" role="tablist" data-testid="meal-tabs">
                                <div className="flex gap-1 min-w-min">
                                    {getMealOrder().map(mealKey => (
                                        <MealTab
                                            key={mealKey}
                                            mealKey={mealKey}
                                            mealInfo={mealInfo}
                                            getMealStatus={getMealStatus}
                                            isLocked={isMealLocked(mealKey)}
                                            selected={selectedMeal === mealKey}
                                            onSelect={() => setSelectedMeal(mealKey)}
                                        />
                                    ))}
                                </div>
                            </div>
                            <div data-testid="meal-detail">
                                {getMealOrder().includes(selectedMeal) && renderMealCard(selectedMeal, true)}
                            </div>
                            <div className="sm:hidden">{renderActions('-mobile')}</div>
                        </div>
                    )}

                    {/* Todo seguido: el día entero abierto, como la dieta de Calma. Sin
                        seleccionar nada, se edita cualquier comida donde está. */}
                    {vistaComidas === 'continua' && (
                        <div className="space-y-4" data-testid="meals-continua">
                            {getMealOrder().map(mealKey => (
                                <div key={mealKey}>{renderMealCard(mealKey, true, true)}</div>
                            ))}
                            <div className="sm:hidden">{renderActions('-mobile')}</div>
                        </div>
                    )}
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

            {/* "Sugiéreme un menú": biblioteca REAL por cercanía, sin reescalar */}
            <LibraryMenusModal
                open={menuOptionsModal.open}
                mealKey={menuOptionsModal.mealKey}
                onClose={() => setMenuOptionsModal({ open: false, mealKey: null })}
                mealInfo={mealInfo}
                target={menuOptionsModal.mealKey ? getMealTarget(menuOptionsModal.mealKey) : null}
                api={api}
                dayConfig={{
                    fecha: currentDate,
                    tipo_dia: tipoDia,
                    num_comidas: numComidas,
                    momento_entreno: momentoEntreno,
                    opcion_peri: opcionPeri,
                }}
                onApply={applyLibraryMenu}
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
                tipoDia={tipoDia}
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
