import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useOnboarding } from '../context/OnboardingContext';
import { leer as leerLocal, escribir as escribirLocal, borrar as borrarLocal } from '../lib/almacenLocal';
import { excesos, textoExceso, margenDe, MARGEN } from '../lib/exceso';
import { num1 } from '../lib/numeros';
import { leerCantidad, avisoRazonable, TOPE_GRAMOS, AVISO_TOPE, AVISO_NO_ES_NUMERO, AVISO_NEGATIVO } from '../lib/cantidades';
import { useConfirm } from '../components/ui/confirm';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { hoyLocal } from '../lib/horaEspana';
import {
    Copy, FileDown, SlidersHorizontal, Star, Check, AlertCircle, AlertTriangle, Settings, UserCheck
} from 'lucide-react';
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
import LibraryMenusModal from '../components/nutrition/LibraryMenusModal';
import DietCalendar from '../components/nutrition/DietCalendar';
import DiaVacio from '../components/nutrition/DiaVacio';
import ExtrasDelDia from '../components/nutrition/ExtrasDelDia';
import { cabeceras } from '../lib/cabeceras';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// LOS DOS AVISOS DE BIENVENIDA DE NUTRICION, APAGADOS (Francisco, 11-08-2026).
//
// Al entrar por primera vez salian encadenados «Tu primera dieta» (PrimeraDieta) y el tutorial
// de la pantalla (NutritionIntro), y tapaban justo lo que la persona venia a hacer. Es lo
// mismo que ya senalo Jesus el 11-08 con la captura de Nutricion: la unica que consiguio hacer
// fue la de la bienvenida, porque no dejaba ver nada detras.
//
// Un solo interruptor, y el codigo se queda entero: volver a encenderlo es poner true.
// Ojo, no confundir con el gate de PREFERENCIAS (showPreferencesSetup), que es otra cosa y
// sigue vivo: ese recoge los gustos, que el sugeridor usa de verdad.
const BIENVENIDA_NUTRICION = false;

// Peri options: intra_post/solo_post (Calma) + solo_intra/sin_peri (custom). Normalize stored
// values, defaulting unknown to intra_post.
const PERI_VALUES = ['intra_post', 'solo_post', 'solo_intra', 'sin_peri'];
const normPeri = (v) => (PERI_VALUES.includes(v) ? v : 'intra_post');
// El momento del entreno solo puede ser 0-3 (en ayunas / tras C1 / tras C2 / tras C3), pero
// 5.400 dias migrados de Calma traen un 5: el backend ya lo corrige a 1 al calcular, y aqui
// se hace lo mismo al LEER, porque con un 5 el peri se pintaba al final del dia, el resumen
// salia con un hueco («4 comidas ·  · intra + post») y el selector de horario en blanco.
const normMomento = (v) => (Number.isInteger(v) && v >= 0 && v <= 3 ? v : 1);

// Cuándo se guardó el día, en corto. Aparte del `formatDate` de la pantalla porque aquel dice
// «Hoy» para la fecha de hoy, y «te lo montó Francisco el Hoy» no se puede leer.
const fechaDeEdicion = (iso) => {
    const d = new Date(iso);
    return isNaN(d) ? '' : d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
};

// Aquí había otra copia del logo, con las letras en blanco fijo. No la pintaba nadie: esta
// pantalla no lleva logo. Fuera (14-08-2026).

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

// La fecha de hoy con la que viajan las dietas (AAAA-MM-DD): EL RELOJ DEL CLIENTE
// (bloque F, 23-08, decisión de Francisco). Estuvo clavada a España para cuadrar con el
// servidor, pero eso le abría a un cliente en América el día de mañana. Ahora el servidor
// acepta la fecha del cliente en todos los caminos del día vivido (checkins, entreno,
// semana, montar-día), así que la cuenta única es la del navegador; España queda para
// los plazos y ventanas, que ya van con su «(h España)». Para quien vive aquí no cambia
// nada. OJO: nunca `toISOString()` -- ese es el día UTC, la trampa de siempre.
const hoyISO = () => hoyLocal();

const NutritionPage = () => {
    // `user` hace falta para separar por cliente lo que se guarda en el navegador (punto
    // 4.7): la copia local del día se guardaba solo con la fecha, así que en un ordenador
    // compartido el siguiente que entrara se encontraba la dieta del anterior.
    const { token, user } = useAuth();
    const uid = user?.id;
    const navigate = useNavigate();
    const { notify } = useOnboarding();
    // Para preguntar antes de hacer algo que no se puede deshacer (copiar sobre un día que
    // ya tiene dieta, borrar una favorita). El confirm del navegador bloquea la pestaña.
    const { confirm } = useConfirm();

    // Preferences state - for checking if user has configured preferences
    const [showPreferencesSetup, setShowPreferencesSetup] = useState(false);
    const [userPreferences, setUserPreferences] = useState([]);
    const [avoidedCategories, setAvoidedCategories] = useState([]);
    const [avoidedKeywords, setAvoidedKeywords] = useState([]);
    const [preferencesLoading, setPreferencesLoading] = useState(true);
    // La configuracion del dia (comidas / horario / peri) va plegada: se resume en una
    // linea de texto y solo se despliega cuando de verdad se quiere cambiar algo.
    const [configExpanded, setConfigExpanded] = useState(false);
    // La tuerca de «Comidas del día»: dentro van «Método/Reales» y cómo ver las comidas.
    const [ajustesVistaAbierto, setAjustesVistaAbierto] = useState(false);

    // Como quiere ver las comidas del dia (lista y detalle, pestañas o todo seguido).
    // Se recuerda de un dia para otro; ver components/nutrition/VistaComidas.jsx.
    const [vistaComidas, setVistaComidas] = useState(leerVista);
    const cambiarVistaComidas = useCallback((v) => { guardarVista(v); setVistaComidas(v); }, []);

    // Macros del metodo o de la etiqueta. SOLO cambia lo que se enseña: el conteo, el
    // reparto y el estado de cada comida siguen saliendo de calculateMealMacros.
    const [modoMacros, setModoMacros] = useState(leerModoMacros);
    const cambiarModoMacros = useCallback((v) => { guardarModoMacros(v); setModoMacros(v); }, []);

    // Intro guiado de primera visita. POR CLIENTE, no por dispositivo (punto 4.7): si un
    // cliente lo cierra en el ordenador de casa, el siguiente que entre ahí no debería
    // perderse el tutorial por algo que hizo otro.
    const [showIntro, setShowIntro] = useState(false);
    useEffect(() => {
        // APAGADO (Francisco, 11-08-2026): ver BIENVENIDA_NUTRICION arriba.
        if (!BIENVENIDA_NUTRICION) return;
        if (uid) setShowIntro(leerLocal('nutrition-intro-seen', uid) !== '1');
    }, [uid]);
    const dismissIntro = useCallback(() => {
        escribirLocal('nutrition-intro-seen', uid, '1');
        setShowIntro(false);
    }, [uid]);

    // Paso 4 del doc: la primera vez que viene a por su dieta se le piden los gustos (que es
    // cuando sirven de algo) y se le enseña como esta repartido su dia. Va antes que el tutorial:
    // primero se configura lo suyo, y despues se le explica la pantalla.
    const [primeraDieta, setPrimeraDieta] = useState(false);
    useEffect(() => {
        // APAGADO (Francisco, 11-08-2026): ver BIENVENIDA_NUTRICION arriba.
        if (!BIENVENIDA_NUTRICION) return;
        if (uid) setPrimeraDieta(leerLocal('primera-dieta-hecha', uid) !== '1');
    }, [uid]);
    const cerrarPrimeraDieta = useCallback(() => {
        escribirLocal('primera-dieta-hecha', uid, '1');
        setPrimeraDieta(false);
    }, [uid]);

    // Date & Config state
    //
    // La fecha arranca DE LA URL, no de hoy (QA 15-08). Con hoy de arranque habia una
    // carrera: el efecto que refleja la fecha en la URL corria con el valor inicial antes
    // de que el efecto que lee ?date= aterrizara su setState, reescribia ?date= a hoy, y
    // con el doble montaje de StrictMode la segunda pasada releia la URL ya machacada.
    // Resultado: ?date=2026-08-16 abria el 15, y recargar en un dia futuro lo perdia.
    const [currentDate, setCurrentDate] = useState(() => {
        const pedida = new URLSearchParams(window.location.search).get('date');
        return (pedida && /^\d{4}-\d{2}-\d{2}$/.test(pedida)) ? pedida : hoyISO();
    });
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
    // Lo que lleva el día de cada familia calibrada y en qué tramo va. Sale de la misma
    // llamada de calibración (que ya lo devolvía y se tiraba), y es lo que se le enseña al
    // cliente: «frutos secos hoy: 15 de 20 g». Jesús, 13-08: que se vea desde el primer
    // gramo, no cuando ya ha cruzado.
    const [acumFamilias, setAcumFamilias] = useState(null);
    // El último tramo por el que se avisó, para no repetir el aviso en cada tecla. Es un
    // ref y no un estado a propósito: cambiarlo no tiene que repintar nada.
    const tramoAvisado = useRef({ cereal_pan: null, fruto_seco: null });
    // Un solo recuadre automático por familia y día (doc 57, F3): el refit puede devolver
    // el acumulado al tramo anterior y sin este candado la app entraría en un vaivén de
    // recuadres. La clave lleva la fecha, así que se limpia sola al cambiar de día.
    const recuadresHechos = useRef(new Set());
    // Calma comidaConMacrosVolcadas: the meal key that absorbs the day's remaining macros.
    // When set, every OTHER meal is locked (target = its served = cuadrada). null = no volcado.
    const [volcadoMeal, setVolcadoMeal] = useState(null);
    const [mealsData, setMealsData] = useState({});
    // TODAS CERRADAS AL ENTRAR, EN EL TELÉFONO. Aquí se abría la Comida 1 sola, cada vez que
    // se recargaba o se volvía a la pantalla, y con ella se desplegaban su modo de cálculo,
    // su fila de macros y sus tres botones: unos 600 px antes de llegar a la Comida 2. Lo
    // primero que tiene que ver el cliente es el día entero, no una comida cualquiera
    // abierta por él. En escritorio se queda como estaba, con la primera abierta.
    const [expandedMeals, setExpandedMeals] = useState(
        () => (typeof window !== 'undefined' && window.innerWidth < 1024 ? {} : { C1: true }));
    const [selectedMeal, setSelectedMeal] = useState('C1');
    const [loading, setLoading] = useState(true);
    
    // Modal states
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
    
    // Menu options
    
    // Summary expanded state
    const [summaryExpanded, setSummaryExpanded] = useState(false);
    
    // ¿NADIE HA DICHO SI ESTE DÍA ES DE ENTRENO? (punto 4.17)
    //
    // La app abre todos los días en «Entreno», y eso no es un valor por defecto cualquiera:
    // en el cliente que miró Jesús son 60 g de hidratos y 45 de perientreno de más un domingo.
    //
    // Y no es un despiste de alguno. Medido en producción el 09-08 sobre las 14.027 dietas
    // guardadas: **14.025 dicen «entrenamiento» y 2 dicen «descanso»**. Prácticamente nadie
    // lo marca nunca, así que casi todo el mundo come de día de entreno todos los días.
    //
    // Tampoco se puede deducir: `training_days` lo tienen 4 clientes de 174 y además es un
    // número (cuántos días, no cuáles), `nivel1.dias_entreno` lo tiene 1, y clientes activos
    // con rutina hay 0. No existe el dato en ninguna parte.
    //
    // Lo que sí se puede arreglar hoy es que el supuesto deje de ser invisible: si el día no
    // lo ha marcado nadie, se dice y se le pide que elija. Cuál debe ser la regla automática
    // es una decisión de Jesús, y con 2 de 14.027 delante se toma mejor.
    const [diaSinMarcar, setDiaSinMarcar] = useState(false);

    // EL DÍA VACÍO (doc 21-08, tarea 6.1). Cuando el día no tiene ninguna comida con
    // alimentos, en lugar de la parrilla sale una pregunta con tres salidas (DiaVacio).
    // «Crear el día» guarda aquí LA FECHA para la que se pidió la parrilla: así al
    // cambiar de día la pregunta vuelve, y si el cliente vacía un día que estaba
    // montando no se le echa de la parrilla a mitad de faena.
    const [diaEnCreacion, setDiaEnCreacion] = useState(null);
    // La lista de días recientes es la misma que usa el modal de repetir comida
    // (recentDiets, /diets/recent); esto solo marca que la está cargando el día vacío.
    const [cargandoRecientes, setCargandoRecientes] = useState(false);

    // Calendar state
    const [calendarOpen, setCalendarOpen] = useState(false);
    
    // PDF export state
    const [exportingPdf, setExportingPdf] = useState(false);

    // API helper
    //
    // LAS CABECERAS SALEN DE `lib/cabeceras`, NO DE AQUÍ (punto 2 del 17-08). Esto ponía el
    // token a mano y se dejaba `X-Actuar-Como`, así que cuando el entrenador entraba en la
    // calculadora de un cliente TODA esta pantalla trabajaba como el entrenador: el reparto
    // devolvía los macros del admin, la dieta que se cargaba era la del admin y lo que se
    // guardaba se guardaba encima de su propio día. Con el cartel naranja de «Estás en la
    // cuenta de Cliente Demo» arriba.
    const api = useCallback(async (endpoint, options = {}) => {
        const res = await fetch(`${API_URL}${endpoint}`, {
            ...options,
            headers: cabeceras(token, {
                'Content-Type': 'application/json',
                ...options.headers
            })
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
            // El mensaje de la excepción va a la consola, no a la cara del cliente.
            console.error('[PDF de la dieta]', err);
            toast.error('No hemos podido generar el PDF. Inténtalo de nuevo.');
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

    // QUIÉN MONTÓ ESTE DÍA (punto 4.11). El servidor lo guarda con la dieta desde que el
    // entrenador puede entrar en la calculadora de un cliente, y no se enseñaba en ninguna
    // pantalla. Jesús lo pidió con estas palabras: «si el entrenador le monta una dieta el
    // martes y el cliente la cambia el miércoles, los dos tienen que poder verlo».
    //
    // Al cliente solo se le dice cuando lo montó SU ENTRENADOR: que un día suyo lo montara él
    // no es una noticia, y una línea en todos los días acabaría siendo invisible justo el día
    // que dice algo.
    const [loMontoSuCoach, setLoMontoSuCoach] = useState(null);

    // La versión del día con la que trabaja esta pestaña (ver `loadDiet`).
    const versionDiaRef = useRef(null);
    const loadDietRef = useRef(null);

    // Extras del día (bloque 6.3): lo comido fuera del plan. Cuentan en Llevas del
    // Inicio y no tocan la Dieta; aquí solo se pintan y se editan.
    const [extrasDia, setExtrasDia] = useState([]);

    // Load saved diet - returns { targets, config } where config has the diet's day values
    const loadDiet = useCallback(async (date) => {
        try {
            const diet = await api(`/api/diets/${date}`);
            // CON QUÉ VERSIÓN DEL DÍA EMPEZAMOS. Viaja en cada guardado para que el
            // servidor sepa si esta pantalla va con una copia vieja: con el mismo día
            // abierto en dos sitios, el segundo en guardar devolvía su versión de antes y
            // borraba lo del otro sin que nadie se enterara (16-08-2026).
            versionDiaRef.current = diet?.updated_at || null;
            // Los Extras del día viajan con el documento (bloque 6.3 del doc 21-08):
            // se refrescan aquí para que el bloque de debajo de las comidas diga la verdad
            // también al cambiar de fecha o recargar tras un guardado.
            setExtrasDia(diet.extras || []);
            if (diet.exists) {
                const dietConfig = {
                    tipoDia: diet.tipo_dia || 'entrenamiento',
                    numComidas: diet.num_comidas || 4,
                    momentoEntreno: normMomento(diet.momento_entreno ?? 1),  // ?? not || so 0 (en ayunas) persiste
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
                setLoMontoSuCoach(diet.editado_como === 'entrenador'
                    ? { por: diet.editado_por, cuando: diet.updated_at } : null);
                // Este día ya lo configuró alguien: su tipo es una decisión, no un supuesto.
                setDiaSinMarcar(false);
                console.log('[loadDiet] distribution_targets:', diet.distribution_targets);
                return { targets: diet.distribution_targets || null, config: dietConfig, ok: true, comidas: updatedMeals };
            } else {
                setMealsData({});
                setVolcadoMeal(null);
                setLoMontoSuCoach(null);
                // NADIE HA DICHO SI ESTE DÍA ENTRENA (punto 4.17). Se sigue abriendo en
                // «Entreno» porque hay que abrir en algo, pero se dice.
                setDiaSinMarcar(true);
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
    // LA COPIA VA CON EL NOMBRE DEL CLIENTE DENTRO (punto 4.7). Antes la clave era solo la
    // fecha, así que en un ordenador compartido el segundo que entrara se encontraba el día
    // del primero -- y al guardarlo, se lo metía en su propia dieta. Sin cliente no se
    // guarda nada: mejor perder la red de seguridad que dejarla donde la vea otro.
    const claveLocal = (date) => `nutrition_dia_${date}`;

    const guardarCopiaLocal = (date, snap) => {
        if (!uid || !hayAlimentos(snap)) return;
        escribirLocal(claveLocal(date), uid, JSON.stringify(snap));
    };
    const leerCopiaLocal = (date) => {
        const s = leerLocal(claveLocal(date), uid);
        try { return s ? JSON.parse(s) : null; } catch (e) { return null; }
    };
    const borrarCopiaLocal = (date) => borrarLocal(claveLocal(date), uid);

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
                const res = await api('/api/diets', {
                    method: 'POST',
                    body: JSON.stringify({ fecha: date, ...snap,
                                           base_updated_at: versionDiaRef.current }),
                });
                // La versión con la que seguimos trabajando es la que acaba de escribir el
                // servidor; sin esto, el siguiente autoguardado chocaría contra sí mismo.
                if (res?.updated_at) versionDiaRef.current = res.updated_at;
                if ((res?.conflictos || []).length) {
                    // Esa comida la tocaron en otro sitio después de que cargáramos: se ha
                    // respetado la de allí y aquí se recarga para no seguir con una copia
                    // vieja que la volvería a pisar en el siguiente guardado.
                    setGuardadoEstado('guardado');
                    await loadDietRef.current?.(date);
                    return true;
                }
                teniaAlimentosRef.current = true;
                // A partir de este guardado el día lleva su firma, no la de su entrenador: el
                // aviso tiene que irse o estaría diciendo que lo montó otro.
                setLoMontoSuCoach(null);
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
    // eso se guarda también CUÁNDO se guardó, y la fecha solo se restaura si se guardó hoy.
    // El futuro TAMBIÉN se restaura: quien está dejando montado el día de mañana y recarga
    // (o el chat lo manda a mañana) tiene que seguir en mañana, no rebotar a hoy con el chat
    // y la pestaña cada uno en un día (ronda 1 del 15-08). El punto 22 queda protegido por
    // el sello del día: al entrar MAÑANA, lo guardado ayer ya no restaura y se abre en hoy.
    // Y la fecha también va por cliente (punto 4.7): era la otra mitad de lo mismo. Sin el
    // id dentro, el cliente B abría Nutrición en el día que estaba mirando el cliente A, que
    // es justo por donde empezaba el problema.
    //
    // Y ANTES QUE NADA, ?date=AAAA-MM-DD SI VIENE EN LA URL (punto 4.14). No funcionaba, y
    // con 991 días de dietas migradas por cliente es la única forma de mandar un enlace a un
    // día concreto -- o de que el entrenador abra el que quiere mirar sin ir pasando flechas.
    // Manda sobre lo guardado: si alguien pide un día por la URL, es ese y no otro.
    useEffect(() => {
        const pedida = new URLSearchParams(window.location.search).get('date');
        if (pedida && /^\d{4}-\d{2}-\d{2}$/.test(pedida)) {
            setCurrentDate(pedida);
            return;
        }
        if (!uid) return;
        const stored = leerLocal('nutrition_last_date', uid);
        const guardadoEn = leerLocal('nutrition_last_date_guardado', uid);
        if (stored && guardadoEn === hoyISO()) {
            setCurrentDate(stored);
            return;
        }
        setCurrentDate(hoyISO());
    }, [uid]);

    // ?comida=Intra|Post|C1..C4: aterrizar CON ESA COMIDA elegida. Es el remate del
    // P32 del 23-08: pinchar el bloque del peri en Inicio te dejaba en la cocina con
    // la Comida 1 delante, como si el peri no fuera contigo.
    useEffect(() => {
        const comida = new URLSearchParams(window.location.search).get('comida');
        if (comida && /^(C[1-4]|Intra|Post)$/.test(comida)) {
            setSelectedMeal(comida);
            setExpandedMeals(prev => ({ ...prev, [comida]: true }));
        }
    }, []);

    // Se guarda la fecha vista y el día en que se vio, para lo de arriba. Y se refleja en la
    // URL, para que copiar la barra de direcciones lleve al día que estás mirando: se cambia
    // sin recargar ni apilar historial, así que el botón de atrás sigue haciendo lo suyo.
    useEffect(() => {
        if (!currentDate || !uid) return;
        escribirLocal('nutrition_last_date', uid, currentDate);
        escribirLocal('nutrition_last_date_guardado', uid, hoyISO());
        try {
            const url = new URL(window.location.href);
            if (url.searchParams.get('date') !== currentDate) {
                url.searchParams.set('date', currentDate);
                window.history.replaceState(null, '', url.toString());
            }
        } catch (e) { /* si el navegador no deja tocar la URL, no pasa nada */ }
    }, [currentDate, uid]);

    // Initial load
    useEffect(() => {
        const init = async () => {
            setLoading(true);
            setDistribTargetsOverlay(null);

            // Load persisted diet config FIRST to avoid stale-closure distribution call
            let cfgOverrides = {};
            try {
                const cfg = await api('/api/user/diet-config');
                const me = normMomento(cfg.momento_entreno ?? 1);
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
                    if (copia.momento_entreno != null) setMomentoEntreno(normMomento(copia.momento_entreno));
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
    // `loadDiet` se declara más arriba pero el autoguardado necesita llamarla cuando otra
    // pantalla ha tocado el día; por el ref no hay que reordenar medio fichero.
    loadDietRef.current = loadDiet;
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
                    // CON SU VERSIÓN DEL DÍA, COMO TODOS LOS DEMÁS (16-08-2026, en prod).
                    // Este guardado de despedida era el único que no la mandaba, y resultó
                    // ser justo el que más daño hace: al salir de la pantalla escribía la
                    // copia más vieja que hay, sin candado ninguno. Medido con la cuenta de
                    // Francisco: el asistente pasaba el día a 3 comidas, y bastaba con
                    // recargar Nutrición para que volvieran las 4 con la Comida 4 entera.
                    // Aquí no se puede atender la respuesta -- la pestaña se está yendo --,
                    // pero con la versión el servidor ya sabe qué parte suya está vieja.
                    body: JSON.stringify({ fecha: currentDate, ...snap,
                                           base_updated_at: versionDiaRef.current }),
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

    // Al caer en el día vacío se cargan sus dos listas: cuántas dietas guardadas tiene
    // (para «Ver las N») y sus días recientes montados (para «Repetir un día»). Solo
    // cuando la pantalla de día vacío va a verse; cargar dos veces no rompe nada.
    useEffect(() => {
        if (loading || cargaFallida || diaEnCreacion === currentDate) return;
        const vacio = !Object.values(mealsData || {}).some(m => (m?.alimentos || []).length > 0);
        if (!vacio) return;
        loadDietFavorites();
        setCargandoRecientes(true);
        loadRecentDiets().finally(() => setCargandoRecientes(false));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [loading, currentDate, mealsData, cargaFallida, diaEnCreacion]);

    // Objetivo por comida guardado (distribTargetsOverlay) OBSOLETO: se congela al crear la
    // dieta, pero si los macros asignados al cliente cambian después, la distribución
    // recalculada (`distribution`) ya no coincide. Sin esto, la comida seguía mostrando el
    // objetivo viejo ("cuadrada") mientras la cabecera del día usaba el nuevo ("te pasas") -
    // en comida única eso dejaba 225/240 en la comida y 180/180 en el día. Al detectar el
    // desfase descartamos el overlay: la comida pasa a usar el objetivo de HOY (coinciden) y
    // el autoguardado deja de re-persistir el valor viejo. Se ignora en modo volcado (sus
    // objetivos viven en volcadoMeal, no en el overlay).
    //
    // PERO NO SE JUZGA A MITAD DE LA CARGA (17-08-2026). Al abrir un día que el asistente
    // dejó en 3 comidas, esta pantalla arranca con las 4 del perfil: su distribución dice
    // 47,5 para la Comida 1, el objetivo guardado dice 63,3, la diferencia pasa de la
    // tolerancia y el overlay se tira ENTERO. Cuando llega la configuración del día ya no
    // hay overlay que usar, así que la comida sale con el número que calcula esta pantalla
    // (63,5) y el chat sigue diciendo el suyo (63,3): dos cifras para lo mismo, y el «faltan
    // 9,3 g» de al lado calculado sobre la otra. Mientras la distribución no sea la de ESTE
    // día -- misma cantidad de comidas que el objetivo guardado -- aquí no se decide nada.
    useEffect(() => {
        if (!distribTargetsOverlay || !distribution || volcadoMeal || loading) return;
        const enDistribucion = Object.keys(distribution.comidas || {}).length
            + Object.keys(distribution.periworkout || {}).length;
        if (enDistribucion !== Object.keys(distribTargetsOverlay).length) return;
        const TOL = 3; // holgura por redondeos; un cambio real de macros es >= 5 g
        const stale = Object.entries(distribTargetsOverlay).some(([k, t]) => {
            const f = distribution.comidas?.[k] || distribution.periworkout?.[k];
            if (!f) return true; // la comida ya no existe en la distribución de hoy
            return Math.abs((t.P || 0) - (f.P || 0)) > TOL ||
                   Math.abs((t.H || 0) - (f.H || 0)) > TOL ||
                   Math.abs((t.G || 0) - (f.G || 0)) > TOL;
        });
        if (stale) setDistribTargetsOverlay(null);
    }, [distribTargetsOverlay, distribution, volcadoMeal, loading]);

    // Wrappers for user-initiated config changes - persist to profile (cross-device)
    // En cuanto elige, el día deja de estar sin marcar: lo ha dicho él (punto 4.17).
    const handleSetTipoDia = (v) => { setTipoDia(v); setDiaSinMarcar(false); };
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
        // CON EL AÑO SI NO ES ESTE (QA 15-08). Se podía acabar montando la dieta en enero
        // de 2020 y la cabecera solo decía «Mié, 1 Ene»: nada en pantalla te sacaba del
        // error. El año solo aparece cuando hace falta, para no ensuciar el día a día.
        const esteAno = new Date().getFullYear();
        return local.toLocaleDateString('es-ES', {
            weekday: 'short', day: 'numeric', month: 'short',
            ...(y !== esteAno ? { year: 'numeric' } : {}),
        });
    };

    // Un día fuera de temporada no tiene plan: los macros que se pintan son los de hoy
    // proyectados, y eso hay que decirlo. Sesenta días es margen de sobra para repasar
    // atrás y planificar adelante sin que salte el aviso.
    const diasDesdeHoy = (() => {
        const [y, m, d] = (currentDate || hoyISO()).split('-').map(Number);
        return Math.round((new Date(y, m - 1, d) - new Date(new Date().setHours(0, 0, 0, 0))) / 86400000);
    })();
    const fechaFueraDePlan = Math.abs(diasDesdeHoy) > 60;

    // Meal order based on config
    // Calma esModoSinRepartoDeMacrosPorComidas (coach-set quiereRepartoDeComidas=false):
    // a single comida holds the whole day's macros; peri (intra/post) stays separate.
    // num_comidas=1 ES comida unica aunque la bandera no venga: un dia guardado por el
    // chat como bloque unico se pintaba con cuatro comidas, tres de ellas fantasma a
    // 0/0/0 (QA 15-08 ronda 3, B3-04).
    const singleMeal = distribution?.config?.single_meal === true || numComidas === 1;

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
        // a 0.2 g overshoot as "sobra".) El número no se escribe aquí: vive en `lib/exceso`.
        const margin = MARGEN;
        const isPeriMeal = mealKey === 'Intra' || mealKey === 'Post';
        // EL MARGEN, PROPORCIONAL A LO QUE SE PIDE (13-08). Los 4 g fijos daban por
        // «cuadrado» un intra con 5 de 9 g de proteína, porque 4 sobre 9 es el 44 %. En una
        // comida normal no cambia nada; ver `margenDe` en lib/exceso.
        const mP = margenDe(target.P);
        const mH = margenDe(target.H);
        const mG = margenDe(target.G);
        // La proteína, cubierta basta (ver `getDayStatus`): pasarse no es un fallo, así que
        // tampoco puede dejar la comida en «te falta».
        const pOk = served.P - target.P > -mP;
        const hOk = Math.abs(target.H - served.H) < mH;
        const gOk = isPeriMeal || Math.abs(target.G - served.G) < mG;
        if (pOk && hOk && gOk) return 'cuadrada';
        // PASARSE DE PROTEÍNA NO ES PASARSE (Jesús, 13-08). El criterio vive en
        // `lib/exceso`; aquí antes se contaba también `served.P - target.P`, y con eso una
        // comida bien montada salía en rojo por hacer lo que se le pedía.
        if (excesos(served, target, { margen: margin, esPeri: isPeriMeal }).length) return 'sobra';
        return 'falta';
    };

    // LO QUE YA ESTÁ HECHO SE ABRE SOLO; LO QUE FALTA, NO.
    //
    // Jesús pedía que la fila dijera lo que hay dentro y no solo el estado: «lo que decide a
    // las nueve de la noche es qué comí, no en qué estado está la fila». Se probó metiendo los
    // alimentos en la propia fila y quedaban cortados, así que Francisco lo mandó quitar.
    // Esto lo resuelve por el otro lado: si la comida está cuadrada, se despliega y se leen
    // sus alimentos enteros, con sus cantidades y sin cortar nada.
    //
    // Solo al cargar el día, y una vez: después mandan los dedos del cliente. Si abre o cierra
    // algo, se respeta hasta que cambie de día. Por eso la marca lleva la fecha.
    const diaYaDesplegado = useRef(null);
    useEffect(() => {
        if (diaYaDesplegado.current === currentDate) return;
        if (!Object.keys(mealsData || {}).length) return;      // aún no ha llegado la dieta
        const hechas = getMealOrder().filter(k => getMealStatus(k) === 'cuadrada');
        diaYaDesplegado.current = currentDate;
        if (!hechas.length) return;
        setExpandedMeals(previo => ({ ...previo, ...Object.fromEntries(hechas.map(k => [k, true])) }));
        // eslint-disable-next-line react-hooks/exhaustive-deps -- se dispara al cambiar el día
        // o al llegar sus datos; meter las funciones de cálculo lo relanzaría en cada render.
    }, [currentDate, mealsData]);

    // Familias que se calibran, con sus tramos y cómo se llaman para el cliente. Los
    // gramos son los de la spec (17-07) y los mismos que aplica el backend.
    const FAMILIAS_CALIBRADAS = {
        fruto_seco: { etiqueta: 'frutos secos', tramos: [20, 40], campo: 'acum_fs' },
        cereal_pan: { etiqueta: 'cereales y pan', tramos: [50, 100], campo: 'acum_cp' },
    };

    /** Guarda lo que lleva el día de cada familia y avisa UNA vez al cruzar cada tramo.
     *
     * Jesús, 13-08: «un aviso una sola vez al cruzar cada tramo, sin preguntar nada». Es
     * informativo: se dice lo que acaba de pasar (a partir de ahí su proteína cuenta) y se
     * sigue. El tramo avisado se recuerda para no repetirlo mientras el día siga ahí, y
     * baja solo si el cliente quita gramos y vuelve al tramo anterior. */
    const anotarCalibracion = (pcts) => {
        if (!pcts) return;
        const una = Object.values(pcts)[0];       // el tramo es del día: todas las comidas igual
        if (!una) return;
        setAcumFamilias({
            fruto_seco: { gramos: una.acum_fs ?? 0, pct: una.pct_fs ?? 0 },
            cereal_pan: { gramos: una.acum_cp ?? 0, pct: una.pct_cp ?? 0 },
        });
        for (const [bloque, cfg] of Object.entries(FAMILIAS_CALIBRADAS)) {
            const g = (bloque === 'fruto_seco' ? una.acum_fs : una.acum_cp) ?? 0;
            const tramo = g > cfg.tramos[1] ? 2 : g > cfg.tramos[0] ? 1 : 0;
            const previo = tramoAvisado.current[bloque];
            // EL CARTEL SE VA SOLO, TIENE ASPA Y DEJA DE ESTAR CUANDO DEJA DE SER VERDAD
            // (Jesús, 15-08, fallo 37): «se quedó minutos en pantalla, siguió visible después
            // de borrar el alimento que lo provocó, y llegó a tapar el título de un panel».
            // El id fijo por familia es lo que permite retirarlo al bajar de tramo -- y de
            // paso evita que se apilen dos avisos de lo mismo.
            const idAviso = `umbral-${bloque}`;
            if (previo !== null && tramo > previo) {
                toast.info(tramo === 2
                    ? `Has pasado de ${cfg.tramos[1]} g de ${cfg.etiqueta} hoy: su proteína ya te cuenta entera`
                    : `Has pasado de ${cfg.tramos[0]} g de ${cfg.etiqueta} hoy: su proteína empieza a contarte a la mitad`,
                    { id: idAviso, duration: 7000, closeButton: true });
                // Y LAS COMIDAS YA MONTADAS SE RECUADRAN SOLAS (doc 57, F3): al cruzar el
                // tramo, la proteína de esa familia cambia de cuenta en TODAS las comidas
                // del día, también en las que ya estaban cuadradas. Antes se quedaban con
                // «sobran X g» sin que el cliente hubiera tocado nada. Solo las comidas en
                // modo Automático (Manual es «lo dejo como lo pongas») y solo una vez por
                // familia y día (ver recuadresHechos).
                const guard = `${bloque}:${currentDate}`;
                if (!recuadresHechos.current.has(guard)) {
                    const afectadas = getMealOrder().filter(k =>
                        !['Intra', 'Post'].includes(k)
                        && (mealsData[k]?.modo !== 'manual')
                        && (mealsData[k]?.alimentos || []).some(a => a.bloque === bloque));
                    if (afectadas.length) {
                        recuadresHechos.current.add(guard);
                        afectadas.forEach(k => cuadrarComida(k, { silencioso: true }));
                        toast.info(afectadas.length === 1
                            ? `Hemos recuadrado una comida que ya tenías creada: con el cambio de ${cfg.etiqueta} había que ajustar sus cantidades.`
                            : `Hemos recuadrado ${afectadas.length} comidas que ya tenías creadas: con el cambio de ${cfg.etiqueta} había que ajustar sus cantidades.`,
                            { id: `recuadre-${bloque}`, duration: 8000, closeButton: true });
                    }
                }
            } else if (previo !== null && tramo < previo) {
                toast.dismiss(idAviso);
            }
            tramoAvisado.current[bloque] = tramo;
        }
    };

    // ── Calibración progresiva (proteína vegetal por TOTAL del DÍA) ─────────────
    // Spec 17-07-2026, con la corrección de Jesús del 13-08: tras CUALQUIER cambio de
    // composición (añadir, quitar, editar cantidades, aplicar menú, repetir, cuadrar...),
    // el backend recalcula los macros de TODO el día. El tramo lo decide el total del día
    // de cada familia, así que es el mismo para todas las comidas y editar una comida
    // puede cambiar cualquier otra. La firma solo mira ids+cantidades, así que cuando
    // vuelven los macros recalibrados la firma no cambia y no hay bucle.
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
                anotarCalibracion(res.pcts);
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
                                    // De qué familia calibrada es (o null): lo necesita el
                                    // contador de la línea para saber qué cuenta enseñar.
                                    bloque: r.bloque ?? null,
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

    // Cómo se escribe la cantidad: «2 ud» los de unidades, «120 g» los de peso. La
    // equivalencia de la unidad («2 ud (53 g)») la pone quien lo pinta, que es el que sabe
    // el sitio que tiene -- ver `IngredientRow` en MealCard.
    const formatFoodQuantity = (food) => {
        if (!food) return '0 g';
        const qty = food.cantidad_g || 0;
        const isPorUnidad = esPorUnidad(food);
        const unitWeight = pesoUnidad(food);
        if (isPorUnidad && unitWeight > 0) {
            return `${num1(Math.round((qty / unitWeight) * 2) / 2)} ud`;
        }
        return `${num1(Math.round(qty))} g`;
    };

    // Food operations
    // Aquí vivía handleAddFood, que solo lo llamaba ese buscador. Lo que hacía -- resolver
    // las unidades del alimento y añadirlo a la comida -- lo hace hoy BuildMealModal.

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
            // El tope de 2000 g también con el «+»: verduras y bebidas suben de 50 en 50 y un
            // alimento por unidades, de una unidad entera (Jesús, 15-08, fallo 28).
            if (bruta > TOPE_GRAMOS) {
                toast.warning(AVISO_TOPE, { id: 'tope-cantidad' });
                return prev;
            }
            // Y el tope RAZONABLE de ese alimento, que es otro (16-08): a golpe de «+» se
            // llegaba a 1.000 g de leche de almendras sin que nadie dijera nada. Se avisa y
            // se pone igual, como hace el asistente.
            const aviso = avisoRazonable(food, bruta, {
                porUnidad: esPorUnidad(food), pesoUnidad: pesoUnidad(food),
            });
            if (aviso) toast.warning(aviso, { id: 'tope-razonable' });
            foods[foodIndex] = scaleFood(food, bruta);
            return { ...prev, [mealKey]: { alimentos: foods } };
        });
    };

    /**
     * Cantidad escrita a mano. En los alimentos por unidades se escriben UNIDADES,
     * que es como los piensa el usuario ("2 huevos", no "126 g de huevo"); aqui se
     * pasan a gramos, que es como se guardan. Acepta medias unidades.
     *
     * LO QUE NO SE ENTIENDE NO BORRA NADA (Jesús, 15-08, fallo 4). Escribir «-50» o «abc»
     * eliminaba el ingrediente de la comida: el texto no era un número, el número salía 0 y
     * el 0 estaba por debajo del mínimo, que significa «quítalo». Un guion puesto sin querer
     * y el alimento desaparecía sin decir nada y sin forma de recuperarlo. Ahora se rechaza
     * el valor y se queda el que había. Bajar de verdad del mínimo (escribir 0) sí lo quita,
     * porque es lo que se está pidiendo, pero se puede deshacer.
     */
    const updateFoodQuantityDirect = (mealKey, foodIndex, valor) => {
        const food = (mealsData[mealKey]?.alimentos || [])[foodIndex];
        setEditingQuantity({ mealKey: null, foodIndex: null });
        if (!food) return;

        const lectura = leerCantidad(valor, {
            porUnidad: esPorUnidad(food),
            pesoUnidad: pesoUnidad(food),
            minimo: cantidadMinima(food),
            alimento: food,
        });

        if (lectura.estado === 'no_es_numero') { toast.error(AVISO_NO_ES_NUMERO); return; }
        if (lectura.estado === 'negativo') { toast.error(AVISO_NEGATIVO); return; }

        if (lectura.estado === 'por_debajo_del_minimo') {
            const previo = mealsData[mealKey];
            setMealsData(prev => ({
                ...prev,
                [mealKey]: { ...prev[mealKey], alimentos: (prev[mealKey]?.alimentos || []).filter((_, i) => i !== foodIndex) },
            }));
            toast.success(`${food.nombre} fuera de la comida`, {
                duration: 8000,
                action: { label: 'Deshacer', onClick: () => setMealsData(prev => ({ ...prev, [mealKey]: previo })) },
            });
            return;
        }

        if (lectura.estado === 'pasa_del_tope') toast.warning(AVISO_TOPE);
        // Dentro del tope duro y aun así demasiado para una comida (un litro de leche): se
        // dice y se pone, que es como se comporta el asistente.
        if (lectura.aviso) toast.warning(lectura.aviso, { id: 'tope-razonable' });
        setMealsData(prev => {
            const foods = [...(prev[mealKey]?.alimentos || [])];
            if (!foods[foodIndex]) return prev;
            foods[foodIndex] = scaleFood(foods[foodIndex], Math.round(lectura.gramos));
            return { ...prev, [mealKey]: { ...prev[mealKey], alimentos: foods } };
        });
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
            // `para`: el día abierto. El servidor solo ofrece comidas que se puedan
            // cuadrar con los macros de ESE día (caso 27; punto 14 del 23-08).
            const result = await api(`/api/diets/recent?limit=14&para=${currentDate}`);
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

    // EL DÍA VIENE POR PARÁMETRO, NO POR ESTADO (punto 4.3).
    //
    // Antes el modal hacía `setSelectedDietForRepeat(dia); copyMealFromDay(comida)` en la
    // misma línea, y `setState` de React es asíncrono: esta función se ejecutaba en el mismo
    // tick y leía el valor ANTERIOR del estado. De ahí las dos caras del fallo que reportó
    // Jesús, que son la misma:
    //
    //   - la primera vez el estado valía null -> "No hay alimentos en esa comida";
    //   - la segunda valía el día que había elegido en el intento anterior -> pedía el 3 de
    //     mayo y le copiaba el 17, y el aviso decía "Copiada Comida 1 del lun, 17 may".
    //
    // La vista previa nunca fallaba porque la pinta el modal con su propia selección, que sí
    // es la buena. No era una clave distinta: era el mismo dato leído un tick antes.
    const copyMealFromDay = async (sourceMealKey, dietElegida) => {
        const targetMealKey = repeatMealModal.mealKey;
        const sourceDiet = dietElegida || selectedDietForRepeat;

        if (!sourceDiet || !sourceDiet.comidas || !sourceDiet.comidas[sourceMealKey]) {
            toast.error('No hay alimentos en esa comida');
            return;
        }
        
        const sourceAlimentos = sourceDiet.comidas[sourceMealKey].alimentos || [];
        if (sourceAlimentos.length === 0) {
            toast.error('Esa comida está vacía');
            return;
        }
        
        // CUADRAR CON EL MISMO MOTOR QUE EL RECETARIO (punto 4.9).
        //
        // Aquí se escalaban las cantidades por el RATIO DE PROTEÍNA y ya: la proteína caía
        // cerca del objetivo y los hidratos y la grasa donde salieran. Con 30 P · 20 H · 10 G,
        // la prueba de Jesús dio 34,2 / 30,0 / 3,2 y la comida en rojo.
        //
        // Es decir: ni copiaba tal cual -- cambiaba las cantidades -- ni cuadraba. Lo peor de
        // las dos cosas. Y por el recetario sí cuadra, sin que nada dijera que los dos
        // caminos hacen cosas distintas. Ahora los dos llaman al mismo sitio.
        let scaledFoods = null;
        try {
            const r = await api('/api/calculator/cuadrar-comida', {
                method: 'POST',
                body: JSON.stringify({
                    items: sourceAlimentos.map(a => ({
                        alimento_id: a.alimento_id, cantidad_g: a.cantidad_g, nombre: a.nombre,
                    })),
                    mealKey: targetMealKey,
                    fecha: currentDate,
                    tipo_dia: tipoDia,
                    num_comidas: numComidas,
                    momento_entreno: momentoEntreno,
                    opcion_peri: opcionPeri,
                }),
            });
            scaledFoods = (r.items || []).length ? r.items : null;
            // Si el motor tuvo que AÑADIR alimentos para poder cuadrar (la comida
            // copiada no tenía fuente de algún macro), se dice: son suyos ahora,
            // pero no los eligió él (punto 14 del 23-08, caso 28).
            const anadidos = (r.items || []).filter(i => i.anadido_para_cuadrar);
            if (anadidos.length) {
                toast.info(anadidos.length === 1
                    ? `Hemos añadido ${anadidos[0].nombre} para poder cuadrarla con tus macros de hoy.`
                    : `Hemos añadido ${anadidos.map(i => i.nombre).join(' y ')} para poder cuadrarla con tus macros de hoy.`);
            }
        } catch (err) {
            console.error('cuadrar-comida falló; se escala por proteína:', err);
        }

        // Si el servidor no responde se usa el escalado de antes. Es peor que cuadrar, pero
        // mucho mejor que dejar al cliente sin poder repetir su día.
        if (!scaledFoods) {
        const targetMacros = getMealTarget(targetMealKey);
        const sourceMacros = sourceAlimentos.reduce((acc, a) => ({
            P: acc.P + (a.macros_efectivos?.P || 0),
            H: acc.H + (a.macros_efectivos?.H || 0),
            G: acc.G + (a.macros_efectivos?.G || 0)
        }), { P: 0, H: 0, G: 0 });
        const scaleFactor = sourceMacros.P > 0 ? targetMacros.P / sourceMacros.P : 1;
        scaledFoods = [];
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
        }

        setMealsData(prev => ({
            ...prev,
            [targetMealKey]: { alimentos: scaledFoods }
        }));

        setRepeatMealModal({ open: false, mealKey: null });
        setSelectedDietForRepeat(null);
        toast.success(`Copiada ${mealInfo[sourceMealKey]?.name || sourceMealKey} del ${formatDate(sourceDiet.fecha)}, cuadrada a tu objetivo`);
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
            const res = await api('/api/diets', {
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
                    base_updated_at: versionDiaRef.current,
                })
            });
            // La versión con la que seguimos trabajando es la que acaba de escribir el
            // servidor, igual que en el autoguardado: sin esto, guardar a mano dejaba la
            // referencia vieja y el siguiente guardado automático chocaba consigo mismo.
            if (res?.updated_at) versionDiaRef.current = res.updated_at;
            // Alguna comida se tocó por otro lado mientras esta pantalla la tenía abierta:
            // esa se ha respetado, y aquí se recarga para enseñar lo que hay de verdad.
            const chocaron = res?.conflictos || [];
            if (chocaron.length) {
                // `_dia` no es una comida: es el reparto del día (cuántas comidas, entreno o
                // descanso, peri). Nombrarlo por su clave sería enseñarle jerga al cliente.
                const nombres = chocaron
                    .map(k => (k === '_dia' ? 'El reparto del día' : (mealInfo[k]?.name || k)))
                    .join(' y ');
                toast(`${nombres} se había cambiado en otro sitio, así que dejé lo más `
                    + `reciente. Te lo recargo.`, { icon: '🔄' });
                await loadDiet(currentDate);
                return;
            }
            toast.success('Dieta guardada');
        } catch (err) { toast.error('Error guardando dieta'); }
    };

    /**
     * Copiar el día a otra fecha.
     *
     * Jesús, 15-08 (fallo 31): copió una dieta a otro día «sin un solo mensaje. Ni "copiado
     * a...", ni aviso de que ese día ya tenía algo, ni deshacer». Copiar PISA la dieta del
     * destino, así que antes se pregunta -- y se dice si allí había algo --, y al terminar
     * se dice qué se ha hecho y dónde.
     */
    const copyDiet = async () => {
        if (!copyDate) { toast.error('Selecciona una fecha'); return; }
        try {
            const sourceDiet = await api(`/api/diets/${currentDate}`);
            if (!sourceDiet || !sourceDiet.exists) {
                toast.error('No hay dieta guardada para hoy');
                return;
            }

            // Qué hay en el destino. Si no se puede mirar, se pregunta igual: mejor una
            // confirmación de más que pisar una dieta en silencio.
            let destino = null;
            try { destino = await api(`/api/diets/${copyDate}`); }
            catch (err) { console.error('[copiar dieta] no se pudo mirar el destino', err); }
            const destinoConDieta = Boolean(destino?.exists)
                && Object.values(destino.comidas || {}).some(c => (c?.alimentos || []).length > 0);
            const cuando = formatDate(copyDate);

            const adelante = await confirm({
                title: destinoConDieta ? `El ${cuando.toLowerCase()} ya tiene dieta` : `Copiar al ${cuando.toLowerCase()}`,
                description: destinoConDieta
                    ? 'Si sigues, la dieta de ese día se sustituye por esta. Eso no se puede deshacer.'
                    : 'Se copia este día entero: sus comidas, sus cantidades y su tipo de día.',
                confirmLabel: destinoConDieta ? 'Sustituirla' : 'Copiar',
                danger: destinoConDieta,
            });
            if (!adelante) return;

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
            toast.success(destinoConDieta
                ? `Dieta copiada al ${cuando.toLowerCase()}, sustituyendo la que había`
                : `Dieta copiada al ${cuando.toLowerCase()}`);
            setCopyModalOpen(false);
            setCopyDate('');
        } catch (err) {
            console.error('[copiar dieta]', err);
            toast.error('No hemos podido copiar la dieta. Inténtalo de nuevo.');
        }
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
            // La confirmación dice DÓNDE vive lo guardado (doc 21-08): «Favorita
            // guardada» a secas no decía dónde volver a encontrarla. El último tramo
            // nombra el tipo de día CONTRARIO al guardado, que es cuando de verdad se
            // recuadra al aplicarla.
            toast.success('Guardada · Ya es una de tus dietas', {
                description: 'La tienes en Una de mis dietas cuando montes cualquier día. '
                    + `Se recuadrará sola si la pones en un día de ${tipoDia === 'descanso' ? 'entreno' : 'descanso'}.`,
                duration: 8000,
            });
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

            // Si la composición de la favorita no da para cubrir alguna comida, se dice y
            // se ofrece el Cuadrar aquí mismo (doc 57, F5): antes solo quedaba el hueco en
            // rojo y el cliente tenía que descubrir el botón comida por comida. El peri va
            // aparte a propósito (ahí no hay Cuadrar desde el 08-08).
            const cortas = Object.entries(res.desfases || {})
                .filter(([k, d]) => !['Intra', 'Post'].includes(k)
                    && d && ['P', 'H', 'G'].some(m => (d[m] || 0) < -4))
                .map(([k]) => k);
            const avisoCorta = {
                duration: 9000,
                action: { label: 'Cuadrar ahora', onClick: () => cortas.forEach(k => cuadrarComida(k)) },
            };
            const seQuedaCorta = cortas.length === 1
                ? 'una comida se queda corta de macros'
                : `${cortas.length} comidas se quedan cortas de macros`;

            if (adaptar && periQuitado.length) {
                toast.warning(`Aplicada "${fav.name}" adaptada a tu día de ${etiquetaDia}. El intra/post se ha quitado porque hoy no hay periworkout.`);
            } else if (adaptar && cortas.length) {
                toast.warning(`Aplicada "${fav.name}" adaptada a tu día de ${etiquetaDia}, pero ${seQuedaCorta}.`, avisoCorta);
            } else if (adaptar) {
                toast.success(`Aplicada "${fav.name}" adaptada a tu día de ${etiquetaDia}`);
            } else if (!noCaben.length && cortas.length) {
                toast.warning(`Aplicada "${fav.name}", pero ${seQuedaCorta}.`, avisoCorta);
            } else if (!noCaben.length) {
                toast.success(`Aplicada "${fav.name}" y ajustada a tus macros`);
            }
            // Singular y plural de verdad, no «alimento(s)» (Jesús, 15-08, fallo 42).
            if (noCaben.length) {
                toast.warning(noCaben.length === 1
                    ? 'Un alimento no cabía ni al mínimo y se ha quitado.'
                    : `${noCaben.length} alimentos no cabían ni al mínimo y se han quitado.`);
            }

            // Descanso -> entreno: la favorita no trae peri; avisar de que queda vacío.
            const trae = (k) => ((fav.comidas?.[k]?.alimentos) || []).length > 0;
            if (adaptar && cfg.tipoDia === 'entrenamiento' && cfg.opcionPeri !== 'sin_peri' && !trae('Intra') && !trae('Post')) {
                toast.info('El peri ha quedado vacío: añádelo con "Sugiéreme un menú".');
            }
        } catch (err) {
            toast.error('Error al aplicar la favorita');
        }
    };

    // Repetir un día reciente entero sobre el día abierto (pantalla de día vacío, doc
    // 21-08). El mecanismo es EL MISMO que aplicar una favorita: applyDietFavorite ->
    // /calculator/refit-diet, que recuadra cada alimento a los macros de HOY, con sus
    // avisos de comidas cortas y su «Cuadrar ahora» (doc 57). Si el tipo de día no
    // coincide («Se adapta»), va en modo adaptar: se queda el tipo del día abierto y el
    // peri que no exista aquí se quita con aviso.
    //
    // /diets/recent no trae momento_entreno ni opcion_peri, así que antes se pide el
    // día completo: sin eso, repetir un día «que encaja» le cambiaría el horario del
    // entreno y el peri por los valores por defecto.
    const repetirDiaReciente = async (diaReciente) => {
        try {
            const full = await api(`/api/diets/${diaReciente.fecha}`);
            if (!full?.exists) {
                toast.error('Ese día ya no está guardado');
                return;
            }
            const comoFavorita = {
                name: formatDate(diaReciente.fecha),
                tipo_dia: full.tipo_dia || 'entrenamiento',
                num_comidas: full.num_comidas || 4,
                momento_entreno: normMomento(full.momento_entreno ?? 1),
                opcion_peri: normPeri(full.opcion_peri),
                comidas: full.comidas || {},
            };
            await applyDietFavorite(comoFavorita, {
                adaptar: comoFavorita.tipo_dia !== tipoDia,
            });
        } catch (err) {
            console.error('[repetir día]', err);
            toast.error('No hemos podido repetir ese día. Inténtalo de nuevo.');
        }
    };

    // Cuadrar una comida a demanda: re-ajusta sus alimentos a los macros de HOY, sin pasarse y
    // respetando el mínimo de cada uno (reusa /refit-diet solo para esa comida).
    // `silencioso`: lo usa el recuadre automático al cruzar un umbral (doc 57, F3), que ya
    // pone su propio aviso; sin él saldrían dos carteles por el mismo gesto.
    const cuadrarComida = async (mealKey, { silencioso = false } = {}) => {
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
            if (!refit) { if (!silencioso) toast.error('No se pudo cuadrar la comida'); return; }
            setMealsData(prev => ({ ...prev, [mealKey]: refit }));
            setDistribTargetsOverlay(null);   // pasa a mostrar los macros de hoy
            // Tras el recuadre automático del cruce de umbral, los macros del refit vienen
            // SIN la calibración del día encima: se fuerza una pasada más para que lo que
            // se ve (y se guarda) quede asentado con la regla nueva de la familia.
            if (silencioso) setCalibracionIntento(n => n + 1);
            // Cuadrar ya no quita ingredientes (08-08-2026): reparte y, si no llega a
            // cuadrar del todo, lo dice. El aviso de antes ("no cabían ni al mínimo")
            // además no era cierto: sí cabían, lo que pasaba es que los macros se
            // agotaban antes de llegar a ellos.
            const nEx = res.excluidos?.length || 0;
            const d = res.desfases?.[mealKey];
            const falla = d && ['P', 'H', 'G'].filter(m => Math.abs(d[m]) > 4);
            const nombre = { P: 'proteína', H: 'hidratos', G: 'grasa' };
            // Cuando el redondeo a cantidades pesables mueve algo, se dice: los macros no
            // salen clavados y el cliente tiene derecho a saber por qué (Jesús, 15-08,
            // fallo 29: «5 g de aguacate es media cucharadita, nadie pesa eso»).
            const notaRedondeo = d?.redondeado
                // Reescrito por el punto 9 del 23-08 (y acortado por Francisco).
                ? ' Cantidades redondeadas para pesarlas fácil: los macros pueden variar unos gramos.'
                : '';
            if (silencioso) return;
            if (nEx) {
                toast.warning(`Comida cuadrada. ${nEx === 1 ? 'Un alimento ya no está' : `${nEx} alimentos ya no están`} en el catálogo y se quitó.`);
            } else if (falla?.length) {
                const texto = falla.map(m => {
                    const v = d[m];
                    return `${v > 0 ? 'sobran' : 'faltan'} ${num1(Math.abs(v))} g de ${nombre[m]}`;
                }).join(' y ');
                // Y se dice por dónde empezar, que es lo que hace útil el aviso. Quitar
                // lo decide el cliente: la app no toca lo que él ha puesto.
                const s = d.sugerencia;
                const comoArreglarlo = s?.que_hacer === 'quitar_o_bajar'
                    ? ` Para cuadrarlo tendrías que quitar o bajar ${s.alimento}, que pone ${num1(s.aporta)} g de ${nombre[s.macro]}.`
                    : s?.que_hacer === 'anadir'
                        ? ` Para cuadrarlo te falta añadir algo con ${nombre[s.macro]}.`
                        : '';
                toast.warning(
                    `No se puede cuadrar sin quitar nada: ${texto}.${comoArreglarlo} No se ha quitado ninguno.${notaRedondeo}`,
                    { duration: 9000 });
            } else {
                toast.success(`Comida cuadrada a tus macros.${notaRedondeo}`);
            }
        } catch { toast.error('No se pudo cuadrar la comida'); }
    };

    // La papelera preguntaba nada y borraba (Jesús, 15-08, fallo 33): un clic y la favorita
    // desaparecía, sin confirmar y sin deshacer. Es lo único de esta pantalla que no se
    // puede reconstruir desde el día, así que aquí sí se pregunta antes.
    const deleteDietFavorite = async (id) => {
        const fav = dietFavorites.find(f => f.id === id);
        const adelante = await confirm({
            title: `¿Borrar "${fav?.name || 'esta favorita'}"?`,
            description: 'La favorita se borra para siempre. Los días que montaste con ella no se tocan.',
            confirmLabel: 'Borrar',
            danger: true,
        });
        if (!adelante) return;
        try {
            await api(`/api/diets/favorites/${id}`, { method: 'DELETE' });
            setDietFavorites(prev => prev.filter(f => f.id !== id));
            toast.success('Favorita borrada');
        } catch (err) {
            console.error('[borrar favorita]', err);
            toast.error('No hemos podido borrar la favorita. Inténtalo de nuevo.');
        }
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
                    base_updated_at: versionDiaRef.current,
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
        toast.info('Volcado deshecho: cada comida vuelve a su objetivo.');
    };

    // RECUADRAR EL DÍA ENTERO (punto 26 del doc del 23-08): al cambiar los macros, los
    // días ya creados se quedaban en «TE PASAS» contra el objetivo nuevo y nadie le
    // ofrecía rehacerlos. El motor ya existía (refit-diet, el mismo de las favoritas):
    // reajusta cantidades sin pasarse y respetando el mínimo de cada alimento.
    const [recuadrando, setRecuadrando] = useState(false);
    const handleRecuadrarDia = async () => {
        setRecuadrando(true);
        try {
            const res = await api('/api/calculator/refit-diet', {
                method: 'POST',
                body: JSON.stringify({
                    fecha: currentDate, tipo_dia: tipoDia, num_comidas: numComidas,
                    momento_entreno: momentoEntreno, opcion_peri: opcionPeri,
                    comidas: mealsData,
                }),
            });
            setMealsData(res.comidas || {});
            const fuera = (res.excluidos || []).length;
            toast.success(fuera
                ? `Día recuadrado a tus macros. ${fuera === 1 ? 'Un alimento no cabía ni al mínimo y se quitó' : `${fuera} alimentos no cabían ni al mínimo y se quitaron`}.`
                : 'Día recuadrado a tus macros.');
        } catch (err) {
            console.error('[recuadrar dia]', err);
            toast.error('No hemos podido recuadrar el día. Inténtalo de nuevo.');
        } finally {
            setRecuadrando(false);
        }
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
        // EL DÍA SE JUZGA CON EL MISMO MARGEN QUE LAS COMIDAS: ±4 g (decisión de Francisco,
        // 16-08). Aquí había un 0 a pelo, así que un día con 234,8 de 235 de proteína se
        // guardaba como NO cuadrado mientras la cabecera, las tarjetas de comida, el cierre
        // del día y el reporte del mes lo daban por bueno. De ahí salían dos cuentas
        // distintas de «cuadraste N días» sobre los mismos datos: la del calendario de
        // Nutrición, que sale de este `is_cuadrado` guardado, y la del reporte.
        const margin = MARGEN;
        const pDiff = dayMacros.P - (dayTarget.P_total || 0);
        const hDiff = dayMacros.H - (dayTarget.H_total || 0);
        const gDiff = comidasG - (dayTarget.G_total || 0);  // peri grasas excluded from comidas G

        // Solo hidratos y grasa: pasarse de proteína no es un fallo (Jesús, 13-08). El día
        // entero se juzga con el mismo criterio que cada comida, en `lib/exceso`.
        if (excesos({ H: dayMacros.H, G: comidasG },
                    { H: dayTarget.H_total || 0, G: dayTarget.G_total || 0 },
                    { margen: margin }).length) return 'sobra';

        // La proteína cuenta como hecha en cuanto está CUBIERTA, no solo cuando se clava.
        // Es la otra cara de la decisión de Jesús: si pasarse de proteína no es un fallo,
        // tampoco puede dejar el día en «te falta» -- que es donde caía al quitarle el
        // rojo, y decirle que le falta algo a quien va sobrado es el mismo error al revés.
        const pOk = pDiff >= -margin;
        const hOk = Math.abs(hDiff) <= margin;
        const gOk = Math.abs(gDiff) <= margin;

        // Y NINGUNA COMIDA GENUINAMENTE DESCUADRADA (doc 57, F3): una comida corta de
        // hidratos y otra pasada se compensan en el total, y el día decía CUADRADO con un
        // «faltan» y un «sobran» a la vista. El criterio por comida es el de siempre
        // (getMealStatus, donde pasarse de proteína no es un fallo).
        const algunaComidaMal = getMealOrder().some(k =>
            (mealsData[k]?.alimentos || []).length > 0 && getMealStatus(k) !== 'cuadrada');

        if (pOk && hOk && gOk && !algunaComidaMal) return 'cuadrado';
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
        // Sin el «-entreno»: en 390 px salía «INTRA-ENT...» cortado (recorrido móvil
        // del 23-08) y el icono del rayo ya dice de qué va.
        Intra: { name: 'Intra', shortName: 'Intra', emoji: '⚡' },
        Post: { name: 'Post', shortName: 'Post', emoji: '💪' }
    };

    // ── El día vacío (doc 21-08, tarea 6.1) ──────────────────────────────────
    // «Vacío» es SOLO ninguna comida con alimentos: un día migrado con 1-2 comidas
    // montadas sigue yendo a la parrilla de siempre. Y si la carga falló, la pantalla
    // vacía sería mentira (el día puede existir en el servidor), así que tampoco.
    const diaVacio = !Object.values(mealsData || {}).some(m => (m?.alimentos || []).length > 0);
    const mostrarDiaVacio = diaVacio && !cargaFallida && diaEnCreacion !== currentDate;
    // Los días que se ofrecen repetir: montados de verdad y que no sean el día abierto.
    const recientesMontados = (recentDiets || []).filter(d =>
        d.fecha !== currentDate
        && Object.values(d.comidas || {}).some(m => (m?.alimentos || []).length > 0));
    // «Hoy · jueves, 21 de agosto», o el día que sea si no es hoy.
    const tituloDiaVacio = (() => {
        const [y, m, d] = (currentDate || hoyISO()).split('-').map(Number);
        const largo = new Date(y, m - 1, d).toLocaleDateString('es-ES', {
            weekday: 'long', day: 'numeric', month: 'long',
            ...(y !== new Date().getFullYear() ? { year: 'numeric' } : {}),
        });
        return currentDate === hoyISO() ? `Hoy · ${largo}` : largo.charAt(0).toUpperCase() + largo.slice(1);
    })();

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
                            /* Aquí se pegaba `distribError` entre paréntesis, que es el mensaje
                               de la excepción: «Request failed with status code 500», «Network
                               Error». Al cliente no le dice nada y no puede hacer nada con ello.
                               Sigue yendo entero a la consola, que es donde sirve. */
                            : 'Sin el reparto, las comidas no tienen objetivo. Inténtalo de nuevo en un momento.'}
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
        // Lo que lleva el día de cada familia calibrada, para el contador de la línea del
        // alimento (`ContadorFamilia`). Va en los props comunes porque el contador es el
        // mismo en todas las comidas: el tramo lo decide el día entero.
        acumFamilias,
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
            // En el intra y el post no hay botón «Cuadrar» (Francisco, 08-08-2026):
            // el peri se monta con «Construir» y con el sugeridor, y ahí el botón no
            // pinta nada. Sin `onCuadrar`, MealCard no lo dibuja.
            //
            // El backend SÍ sabe cuadrar el peri, y eso se queda: `refit-diet` es lo
            // que ajusta una dieta favorita al aplicarla y al pasarla de entreno a
            // descanso, y hasta el 08-08 el peri de esas favoritas se copiaba tal cual,
            // sin ajustar a los macros del día. Quitar el botón es una decisión de
            // pantalla; que el peri se ajuste al aplicar una favorita no lo es.
            onCuadrar={['Intra', 'Post'].includes(mealKey) ? undefined : cuadrarComida}
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
                    // UNA BIENVENIDA, NO DOS ENCADENADAS.
                    // Al cerrar esta aparecía el tutorial de la pantalla: dos pantallas completas
                    // antes de ver la primera dieta, contando lo mismo por partes. Ahora cerrar
                    // esta da por visto también aquel.
                    // No se pierde: el tutorial sigue entero en «Repetir recorrido guiado», en Mi
                    // perfil. Es el argumento de Jesús (11-08): como se puede volver a ver, no
                    // hace falta contarlo todo la primera vez, con la dieta esperando detrás.
                    onListo={() => { cerrarPrimeraDieta(); dismissIntro(); }}
                />
            ) : showIntro && <NutritionIntro onClose={dismissIntro} />}
            <header className="flex items-center justify-between gap-4 mb-4">
                <div className="min-w-0">
                    {/* EL TÍTULO «NUTRICIÓN» NO SALE EN EL TELÉFONO: en la barra de abajo ya
                        está marcada «Nutrición» en naranja, así que a 48 px lo dice por
                        tercera vez. En escritorio se queda, que ahí no hay barra inferior.
                        «Plan nutricional» y el estado de guardado se quedan siempre. */}
                    <p className="caption text-brand mb-1">Plan nutricional</p>
                    <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground leading-none hidden lg:block">Nutrición</h1>
                    <div className="mt-1 h-4">{renderEstadoGuardado()}</div>
                    {/* Este día se lo montó su entrenador (punto 4.11). */}
                    {loMontoSuCoach && (
                        <p className="mt-1 text-xs text-brand font-semibold flex items-center gap-1.5"
                            data-testid="dieta-la-monto-el-coach">
                            <UserCheck className="w-3.5 h-3.5" />
                            Este día te lo montó {loMontoSuCoach.por || 'tu entrenador'}
                            {loMontoSuCoach.cuando ? ` el ${fechaDeEdicion(loMontoSuCoach.cuando)}` : ''}
                        </p>
                    )}
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
                    {/* LA TUERCA, ARRIBA CON LAS DEMÁS. Dentro van «Método/Reales» y cómo ver
                        las comidas: dos conmutadores que estaban a la vista y permanentes
                        justo encima de las comidas -- que es lo que se viene a ver -- y que
                        se tocan de higos a brevas. Uno cambia solo lo que pone en la lista de
                        ingredientes; el otro es una preferencia que se elige una vez. */}
                    <button onClick={() => setAjustesVistaAbierto(v => !v)} data-testid="toggle-ajustes-vista"
                        className={`lg:hidden inline-flex items-center gap-2 px-3.5 py-2 text-sm font-semibold transition-colors ${ajustesVistaAbierto ? 'rounded-2xl bg-brand text-white' : 'surface text-muted-foreground hover:text-brand'}`}
                        title="Cómo ver las comidas y qué macros mostrar">
                        <Settings size={16} />
                    </button>
                </div>
            </header>

            {ajustesVistaAbierto && (
                <div className="lg:hidden surface p-4 mb-4 space-y-4" data-testid="ajustes-vista">
                    <div>
                        <p className="caption mb-1.5">Qué macros se muestran</p>
                        <ModoMacrosSelector modo={modoMacros} onCambiar={cambiarModoMacros} />
                    </div>
                    <div>
                        <p className="caption mb-1.5">Cómo ver las comidas</p>
                        <VistaComidasSelector vista={vistaComidas} onCambiar={cambiarVistaComidas} />
                    </div>
                </div>
            )}

            {/* UN DIA MUY LEJOS DE HOY NO TIENE PLAN, Y SE DICE (QA 15-08). Se podia abrir
                el 1 de enero de 2020 y salia un dia entero con sus objetivos repartidos,
                como si el metodo hubiera estado ahi: eran los macros de hoy proyectados.
                Sin aviso, el cliente monta en una fecha que no le sirve de nada. */}
            {fechaFueraDePlan && (
                <div className="surface mb-4 flex items-start gap-2 border-l-4 border-amber-500 p-3 text-sm"
                    data-testid="aviso-fuera-de-plan">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-500" />
                    <span>
                        Este día queda {diasDesdeHoy < 0 ? 'muy atrás' : 'muy lejos'} de hoy y no tiene
                        un plan propio: los objetivos que ves son los de tus macros de ahora. Si querías
                        otro día, vuelve con la flecha o el calendario.
                    </span>
                </div>
            )}

            {/* Cabecera del día: fecha, tipo de día, configuración resumida y macros */}
                <DayHeader
                    currentDate={currentDate}
                    formatDate={formatDate}
                    changeDate={changeDate}
                    setCalendarOpen={setCalendarOpen}
                    handleSetTipoDia={handleSetTipoDia}
                    diaSinMarcar={diaSinMarcar}
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
                    datosDudosos={distribution?.datos_dudosos}
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

                {/* EL DÍA VACÍO EN LUGAR DE LA PARRILLA (doc 21-08, tarea 6.1): una
                    pregunta con tres salidas. Los macros del día siguen arriba, en la
                    cabecera, para que sepa a qué está montando. «Crear el día» abre la
                    parrilla de siempre; las otras dos salidas la rellenan y la parrilla
                    aparece sola en cuanto hay comida. */}
                {mostrarDiaVacio ? (
                <div className="mt-4 lg:mt-6">
                    <DiaVacio
                        titulo={tituloDiaVacio}
                        tipoDia={tipoDia}
                        numFavoritas={dietFavorites.length}
                        onCrear={() => setDiaEnCreacion(currentDate)}
                        onVerFavoritas={() => { loadDietFavorites(); setFavoritesModalOpen(true); }}
                        recientes={recientesMontados}
                        cargandoRecientes={cargandoRecientes}
                        onRepetir={repetirDiaReciente}
                        formatDate={formatDate}
                    />
                </div>
                ) : (
                <>
                {/* En el teléfono, sin la raya que separaba los macros del día de las
                    comidas: son la misma cosa contada dos veces -- lo que te queda arriba,
                    de dónde va a salir debajo -- y la raya las presentaba como dos secciones
                    ajenas. En escritorio se queda. */}
                <div className="my-4 lg:my-6 lg:border-t lg:border-border" />

                {/* ── Comidas: selector en columna + detalle ── */}
                <div data-testid="nutrition-meals">
                    {/* «TE PASAS» con salida (punto 26 del 23-08): si el día ya creado se
                        pasa del objetivo -- lo típico tras un cambio de macros --, se
                        ofrece recuadrarlo, no solo se le riñe. */}
                    {!activeVolcado && !loading && getDayStatus() === 'sobra'
                        && Object.values(mealsData).some(c => (c?.alimentos || []).length > 0) && (
                        <div className="surface p-4 mb-4 flex items-center justify-between gap-3 border-amber-500/30"
                            data-testid="banner-recuadrar">
                            <div className="min-w-0">
                                <p className="font-bold text-foreground">Este día se pasa de tus macros de ahora</p>
                                <p className="text-xs text-muted-foreground">Si tus macros han cambiado, podemos reajustar las cantidades sin quitarte nada.</p>
                            </div>
                            <button
                                className="shrink-0 rounded-xl font-bold text-sm px-4 py-2 border border-brand text-brand hover:bg-brand hover:text-white transition-colors disabled:opacity-50"
                                onClick={handleRecuadrarDia} disabled={recuadrando}
                                data-testid="boton-recuadrar-dia">
                                {recuadrando ? 'Recuadrando...' : 'Recuadrar el día'}
                            </button>
                        </div>
                    )}
                    {/* Volcado de macros banner (ancho completo) */}
                    {activeVolcado && (
                        /* Sin `truncate` (punto 12 del 23-08: se leía «Volcados en…»,
                           cortado) y con el botón en «Deshacer» (punto 10). */
                        <div className="surface p-4 mb-4 flex items-center justify-between gap-3 border-brand/30">
                            <div className="min-w-0">
                                <p className="font-bold text-foreground">Los macros que te quedaban están volcados en {mealInfo[activeVolcado]?.name}</p>
                                <p className="text-xs text-muted-foreground">Las demás comidas quedan bloqueadas hasta deshacerlo.</p>
                            </div>
                            <button
                                className="shrink-0 rounded-xl font-bold text-sm px-4 py-2 border border-brand text-brand hover:bg-brand hover:text-white transition-colors"
                                onClick={handleEliminarVolcado}
                            >
                                Deshacer volcado
                            </button>
                        </div>
                    )}

                    {/* Cabecera de sección: el título y, a la derecha, cómo quiere verlas.
                        El switch de macros vive aquí porque solo cambia lo que pone en
                        la lista de ingredientes; ni los totales ni el reparto se mueven. */}
                    {/* En el teléfono, sin «COMIDAS DEL DÍA» y sin los dos conmutadores:
                        debajo vienen las comidas con su nombre, y los conmutadores están en
                        la tuerca de arriba. En escritorio, la fila de siempre. */}
                    <div className="hidden lg:flex flex-wrap items-center justify-between gap-x-3 gap-y-2 mb-2.5">
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
                                {/* Las comidas, pegadas: es una lista que se va tachando, no
                                    cinco tarjetas sueltas. El aire entre ellas sumaba casi
                                    una pantalla de móvil sin decir nada. */}
                                <div className="lg:hidden space-y-1" data-testid="meals-accordion">
                                    {getMealOrder().map(mealKey => renderMealCard(mealKey, false))}
                                </div>

                                {/* Extras del día (bloque 6.3): debajo de las comidas y del
                                    peri. Cuentan en Llevas del Inicio y no tocan la Dieta.
                                    El componente habla axios (api.get/post/delete): se le
                                    adapta el fetch de esta página. */}
                                <ExtrasDelDia
                                    api={{
                                        get: (url, cfg) => api(`/api${url}?${new URLSearchParams(cfg?.params || {})}`).then((data) => ({ data })),
                                        post: (url, body) => api(`/api${url}`, { method: 'POST', body: JSON.stringify(body || {}) }).then((data) => ({ data })),
                                        delete: (url) => api(`/api${url}`, { method: 'DELETE' }).then((data) => ({ data })),
                                    }}
                                    fecha={currentDate}
                                    extras={extrasDia}
                                    onAnadido={(extra) => setExtrasDia((prev) => [...prev, extra])}
                                    onQuitado={(id) => setExtrasDia((prev) => prev.filter((e) => e.id !== id))}
                                />

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
                    {/* EN PANTALLA ANCHA, EN DOS COLUMNAS (Jesus, 12-08-2026: «aprovechar el
                        ancho para ver las cuatro comidas a la vez»). En una sola columna, un
                        dia de cuatro comidas son dos pantallas y media de scroll en un monitor
                        donde sobra la mitad del ancho. A partir de xl caben las cuatro sin
                        moverse; por debajo se queda como estaba, que es donde tiene sentido. */}
                    {vistaComidas === 'continua' && (
                        <div data-testid="meals-continua">
                            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 items-start">
                                {getMealOrder().map(mealKey => (
                                    <div key={mealKey} className="min-w-0">{renderMealCard(mealKey, true, true)}</div>
                                ))}
                            </div>
                            <div className="sm:hidden mt-4">{renderActions('-mobile')}</div>
                        </div>
                    )}
                </div>
                </>
                )}

            {/* AQUÍ SE MONTABA UN BUSCADOR DE ALIMENTOS QUE NADIE PODÍA ABRIR.
                `addFoodModal` se inicializaba cerrado y se cerraba en dos sitios, pero en toda
                la aplicación no había una sola línea que lo pusiera en abierto: estaba escrito,
                montado y muerto. Salió al hacer el catálogo de pantallas del 10-08, intentando
                retratarlo.
                No se le ha puesto una puerta porque lo que hacía ya existe y mejor: el modal
                «Lo hago yo» busca alimentos y los añade a la comida, con categorías y
                preparaciones. Un segundo camino a lo mismo solo añade ruido.
                Se va con él su `useEffect` de búsqueda y sus cuatro estados. El fichero
                SearchFoodModal.jsx SE QUEDA: de él salen `FOOD_FAVORITES_UI`, que usa
                BuildMealModal, y `FoodFilterBar`, que usa la ficha del cliente. */}

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
                /* El día viaja como argumento, no por el estado: leerlo del estado en el
                   mismo tick devolvía el del intento anterior (punto 4.3). */
                onCopyMeal={(sourceMealKey, sourceDiet) => copyMealFromDay(sourceMealKey, sourceDiet)}
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
                // Para no dejar guardar un día sin comidas como favorita.
                diaVacio={diaVacio}
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
