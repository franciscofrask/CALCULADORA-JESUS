import React, { useState, useEffect } from 'react';
import { Button } from '../ui/button';
import { useConfirm } from '../ui/confirm';
import { toast } from 'sonner';
import { Settings, Check, X, Plus, Ban, Lock } from 'lucide-react';
import {
    faBottleDroplet, faOilCan, faBowlRice, faDove,
    faDumbbell, faBolt, faBottleWater, faBlender,
    faMugHot, faDrumstickBite, faPiggyBank, faPlateWheat, faCookie,
    faUtensils, faBacon, faAppleWhole,
    faEgg, faCheese, faSeedling, faBone, faBreadSlice,
    faFish, faPizzaSlice, faJarWheat,
    faPepperHot, faBowlFood, faStar, faCarrot, faCow, faLeaf,
    faJar, faCubesStacked, faCandyCane, faMartiniGlassCitrus,
    faRecycle, faIceCream, faHotdog,
} from '@fortawesome/free-solid-svg-icons';

// MAPEO de categorías de preferencias con sus prefijos para filtrar
// Ordered by category code, matching Calma's `categoriasParaPreferencias`
// [1, 2.1, 2.2, 2.3, 2.4, 2.6, 2.7, 3, 5, 7, 8, 9, 10, 11, 13, 16, 17, 18.1, 19, 21, 22,
//  24, 28, 30, 31, 32, 34, 37, 38, 39, 40, 44, 47, 48, 49, 51], with grasas_buenas (42,
// a fixed preference) first. Calma's master category map and all filter lists are code-ordered.
export const PREFERENCE_CATEGORIES = [
    { id: 'grasas_buenas',    label: 'Alimentos ricos en grasas de buena calidad', prefixes: ['42'],            icon: faBottleDroplet },
    { id: 'huevos',           label: 'Huevos y derivados',                         prefixes: ['1'],             icon: faEgg },
    { id: 'embutidos',        label: 'Embutidos',                                  prefixes: ['2.1'],           icon: faBacon },
    { id: 'aves',             label: 'Aves',                                       prefixes: ['2.2'],           icon: faDove },
    { id: 'vacuno',           label: 'Vacuno o buey',                              prefixes: ['2.3'],           icon: faCow },
    { id: 'cerdo',            label: 'Cerdo',                                      prefixes: ['2.4'],           icon: faPiggyBank },
    { id: 'carnes_blancas',   label: 'Otras carnes blancas',                       prefixes: ['2.6'],           icon: faDrumstickBite },
    { id: 'carnes_rojas',     label: 'Otras carnes rojas',                         prefixes: ['2.7'],           icon: faBone },
    { id: 'pescados',         label: 'Pescados y mariscos',                        prefixes: ['3'],             icon: faFish },
    { id: 'lacteos',          label: 'Lácteos y derivados',                        prefixes: ['5'],             icon: faCheese },
    { id: 'cereales',         label: 'Cereales (excepto arroz)',                   prefixes: ['7'],             icon: faPlateWheat },
    { id: 'panes',            label: 'Panes y tortillas de trigo',                 prefixes: ['8'],             icon: faBreadSlice },
    { id: 'tuberculos',       label: 'Tubérculos y derivados',                     prefixes: ['9'],             icon: faCarrot },
    { id: 'legumbres',        label: 'Legumbres',                                  prefixes: ['10'],            icon: faSeedling },
    { id: 'fruta',            label: 'Fruta, zumo, potitos y mermeladas',          prefixes: ['11'],            icon: faAppleWhole },
    { id: 'verduras',         label: 'Verduras y hortalizas',                      prefixes: ['13'],            icon: faLeaf },
    { id: 'salsas',           label: 'Salsas, siropes y konjac',                   prefixes: ['16'],            icon: faPepperHot },
    { id: 'grasas_todo',      label: 'Alimentos ricos en grasas de todo tipo',     prefixes: ['17'],            icon: faOilCan },
    { id: 'isotonicas',       label: 'Bebidas isotónicas',                         prefixes: ['18.1'],          icon: faBottleWater },
    { id: 'bebidas',          label: 'Bebidas energéticas, refrescos y cafés',     prefixes: ['19'],            icon: faBolt },
    { id: 'arroces',          label: 'Arroces y derivados',                        prefixes: ['21'],            icon: faBowlRice },
    { id: 'pasta',            label: 'Pasta, quinoa y derivados',                  prefixes: ['22'],            icon: faBowlFood },
    { id: 'beb_vegetales',    label: 'Bebidas vegetales',                          prefixes: ['24'],            icon: faBlender },
    { id: 'proteina_vegetal', label: 'Proteína vegetal',                           prefixes: ['28'],            icon: faJarWheat },
    { id: 'proteina_polvo',   label: 'Proteína en polvo y barritas proteicas',     prefixes: ['4', '29', '30'], icon: faJar },
    { id: 'bolleria',         label: 'Bollería industrial y galletas',             prefixes: ['31'],            icon: faCookie },
    { id: 'pizza',            label: 'Pizza, lasaña, empanadas y empanadillas',    prefixes: ['32'],            icon: faPizzaSlice },
    { id: 'chocolates',       label: 'Chocolates y chocolatinas',                  prefixes: ['34'],            icon: faCubesStacked },
    { id: 'cacao',            label: 'Cacao en polvo y azúcares de todo tipo, chucherías y miel', prefixes: ['37'], icon: faCandyCane },
    { id: 'aperitivos',       label: 'Aperitivos',                                 prefixes: ['38'],            icon: faMartiniGlassCitrus },
    { id: 'cocina_esp',       label: 'Cocina tradicional española',                prefixes: ['39'],            icon: faUtensils },
    { id: 'casqueria',        label: 'Casquería',                                  prefixes: ['40'],            icon: faRecycle },
    { id: 'helados',          label: 'Helados y postres',                          prefixes: ['44'],            icon: faIceCream },
    { id: 'barritas',         label: 'Barritas energéticas',                       prefixes: ['47'],            icon: faDumbbell },
    { id: 'sopas',            label: 'Sopas y Caldos',                             prefixes: ['48'],            icon: faMugHot },
    { id: 'comida_rapida',    label: 'Comida rápida',                              prefixes: ['49'],            icon: faHotdog },
    { id: 'superalimentos',   label: 'Superalimentos',                             prefixes: ['51'],            icon: faStar },
];

// LOS DIEZ CAJONES del doc 19-08: las 37 categorías repartidas (más la fija de grasas
// buenas, que va en su cajón). «Se escribe una vez y no se vuelve a tocar»: los números
// del doc -- 9, 1, 5, 1, 2, 2, 4, 3, 7 y 3 -- salen solos de este reparto.
export const CAJONES = [
    { id: 'carnes',    nombre: 'Carnes, pescados y huevos', cats: ['huevos', 'embutidos', 'aves', 'vacuno', 'cerdo', 'carnes_blancas', 'carnes_rojas', 'pescados', 'casqueria'] },
    { id: 'lacteos',   nombre: 'Lácteos',                   cats: ['lacteos'] },
    { id: 'cereales',  nombre: 'Cereales, pan y tubérculos', cats: ['cereales', 'panes', 'tuberculos', 'arroces', 'pasta'] },
    { id: 'legumbres', nombre: 'Legumbres',                 cats: ['legumbres'] },
    { id: 'fruta',     nombre: 'Fruta y verdura',           cats: ['fruta', 'verduras'] },
    { id: 'grasas',    nombre: 'Grasas',                    cats: ['grasas_buenas', 'grasas_todo'] },
    { id: 'supl',      nombre: 'Suplementos',               cats: ['proteina_polvo', 'proteina_vegetal', 'barritas', 'superalimentos'] },
    { id: 'bebidas',   nombre: 'Bebidas',                   cats: ['isotonicas', 'bebidas', 'beb_vegetales'] },
    { id: 'caprichos', nombre: 'Caprichos',                 cats: ['bolleria', 'pizza', 'chocolates', 'cacao', 'aperitivos', 'helados', 'comida_rapida'] },
    { id: 'otros',     nombre: 'Otros',                     cats: ['salsas', 'cocina_esp', 'sopas'] },
];

// «Tres ejemplos debajo de cada una» (doc 19-08). Los seis que salen en el propio doc van
// tal cual; el resto, tres alimentos corrientes de esa categoría del catálogo.
export const EJEMPLOS = {
    grasas_buenas: 'aceite de oliva, nueces, aguacate…',
    huevos: 'huevos, claras…',
    embutidos: 'jamón serrano, pavo en lonchas, cecina…',
    aves: 'pollo, pavo, conejo…',
    vacuno: 'ternera, buey, hamburguesa de vacuno…',
    cerdo: 'lomo, solomillo, secreto…',
    carnes_blancas: 'conejo, codorniz…',
    carnes_rojas: 'cordero, caballo, potro…',
    pescados: 'merluza, salmón, gambas…',
    lacteos: 'leche, yogur, queso…',
    cereales: 'avena, cereales de desayuno, harinas…',
    panes: 'pan de barra, pan de molde, wraps…',
    tuberculos: 'patata, boniato, yuca…',
    legumbres: 'lentejas, garbanzos, alubias…',
    fruta: 'plátano, manzana, zumos…',
    verduras: 'brócoli, calabacín, ensaladas…',
    salsas: 'salsas zero, siropes, konjac…',
    grasas_todo: 'mantequilla, cremas de frutos secos, coco…',
    isotonicas: 'bebidas isotónicas con y sin azúcar…',
    bebidas: 'refrescos zero, café, bebidas energéticas…',
    arroces: 'arroz blanco, basmati, tortas de arroz…',
    pasta: 'macarrones, espaguetis, quinoa…',
    beb_vegetales: 'bebida de soja, de almendra, de avena…',
    proteina_vegetal: 'tofu, seitán, soja texturizada…',
    proteina_polvo: 'whey, caseína, barritas proteicas…',
    bolleria: 'galletas, bollos, magdalenas…',
    pizza: 'pizza, lasaña, empanadas…',
    chocolates: 'chocolate negro, chocolatinas…',
    cacao: 'cacao en polvo, azúcar, miel…',
    aperitivos: 'patatas fritas, encurtidos, palomitas…',
    cocina_esp: 'tortilla, cocido, paella…',
    casqueria: 'hígado, riñones, mollejas…',
    helados: 'helados, postres lácteos…',
    barritas: 'barritas energéticas y de cereales…',
    sopas: 'sopas, caldos, cremas…',
    comida_rapida: 'hamburguesas, kebab, nuggets…',
    superalimentos: 'chía, espirulina, levadura nutricional…',
};

// Obligatoria: siempre marcada, no se puede desmarcar.
export const OBLIGATORY_PREFERENCES = ['grasas_buenas'];

// Pre-marcadas para clientes nuevos (todas desmarcables salvo las obligatorias).
export const DEFAULT_PREFERENCES = ['grasas_buenas', 'verduras', 'embutidos', 'lacteos', 'salsas'];

const withObligatory = (ids) => {
    const s = new Set(ids);
    OBLIGATORY_PREFERENCES.forEach(id => s.add(id));
    return s;
};

// A nivel de módulo a propósito (mismo repaso del 13-08 que el marco de RecuperarPage):
// definida dentro de PreferencesSetup, cada render creaba una función nueva y React
// desmontaba y volvía a montar las treinta filas de categorías enteras. Pasaba con cada
// tecla del campo de palabras clave. Aquí no se perdía el foco porque ese campo es hermano
// de la lista, no descendiente, pero tiraba y rehacía todo ese DOM por pulsación.
// Todo lo que necesita entra por props, así que sube sin tocar nada más.
const CategoryCheckbox = ({ cat, checked, onToggle, colorClass, locked = false }) => (
    <label
        className={`flex items-center gap-3 p-3 rounded-lg transition-all ${locked ? 'cursor-default' : 'cursor-pointer'} ${
            checked
                ? `${colorClass} border`
                : 'bg-muted border border-transparent hover:bg-muted'
        }`}
        // Las obligatorias también avisan al pulsarlas: antes no pasaba nada de nada y no
        // había forma de saber por qué (Jesús, 15-08, fallo 40). El aviso lo da `onToggle`.
        onClick={() => onToggle(cat.id)}
    >
        {/* La casilla marcada siempre en el naranja de la casa (doc 23-08, P22): antes la
            pestaña de evitar la pintaba en rojo y la de preferidos en el #FFA500 legacy,
            que en pantalla se lee amarillo. La app es naranja: brand y punto. */}
        <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all flex-shrink-0 ${
            checked ? 'bg-brand border-brand' : 'border-border'
        }`}>
            {checked && <Check className="w-3 h-3 text-white" />}
        </div>
        <span className={`text-sm flex-1 min-w-0 ${checked ? 'text-foreground font-medium' : 'text-foreground'}`}>
            {cat.label}
            {/* «Tres ejemplos debajo de cada una» (doc 19-08). */}
            {EJEMPLOS[cat.id] && (
                <span className="block text-xs text-muted-foreground font-normal">{EJEMPLOS[cat.id]}</span>
            )}
        </span>
        {/* La fija de grasas dice lo que hace, no «obligatorio» a secas (doc 19-08). */}
        {locked && <span className="text-xs text-muted-foreground flex-shrink-0">Se ofrecen siempre</span>}
    </label>
);

// LAS ALERGIAS DEL ALTA, con lo que bloquea cada una. Es el espejo exacto de
// `_preferencias_del_basico` del backend: lactosa total quita los lácteos, la celiaquía
// quita panes, pasta, bollería y cereales, y lo escrito en «otra» va por palabras. Las
// parciales (tolera algo, sensibilidad) no bloquean nada: van con candado informativo.
export const alergiasDelAlta = (perfil) => {
    const alergias = perfil?.alergias || [];
    const lista = Array.isArray(alergias) ? alergias : [];
    const fuera = [];
    if (lista.includes('lactosa')) {
        const total = (perfil?.lactosa || '') === 'total';
        fuera.push({
            clave: 'lactosa', nombre: 'Lactosa',
            nota: total ? 'total: nada de lácteos' : 'tolero el yogur y el queso curado',
            bloquea: total ? ['lacteos'] : [], palabras: [],
            aviso: '¿Seguro? A partir de ahora podemos ponerte lácteos.',
        });
    }
    if (lista.includes('gluten')) {
        const celiaca = (perfil?.gluten || '') === 'celiaquia';
        fuera.push({
            clave: 'gluten', nombre: 'Gluten',
            nota: celiaca ? 'celiaquía: nada de gluten' : 'sensibilidad, tolero pequeñas cantidades',
            bloquea: celiaca ? ['panes', 'pasta', 'bolleria', 'cereales'] : [], palabras: [],
            aviso: '¿Seguro? A partir de ahora podemos ponerte gluten.',
        });
    }
    const otra = (perfil?.alergia_otra || '').trim();
    if (lista.includes('otra') && otra) {
        // El mismo troceo que el backend: comas, puntos y comas o « y », y fuera lo corto.
        const palabras = otra.split(/[,;]| y /).map(t => t.trim().toLowerCase()).filter(t => t.length > 2);
        for (const p of palabras) {
            fuera.push({
                clave: `otra:${p}`, nombre: p.charAt(0).toUpperCase() + p.slice(1),
                nota: 'alergia o intolerancia', bloquea: [], palabras: [p],
                aviso: `¿Seguro? A partir de ahora podemos ponerte ${p}.`,
            });
        }
    }
    return fuera;
};

const PreferencesSetup = ({
    api,
    initialPreferences = [],
    initialAvoidedCategories = [],
    initialAvoidedKeywords = [],
    onSave,
    onCancel,
    isEditMode = false
}) => {
    // La pestaña de EVITAR va primero cuando se entra a revisar («Esto es lo que nos
    // dijiste al darte de alta. Confírmalo o cámbialo», doc 19-08); en el alta se acaba de
    // contestar y se empieza por los preferidos.
    const [activeTab, setActiveTab] = useState(isEditMode ? 'avoid' : 'like');
    const [selected, setSelected] = useState(
        withObligatory(isEditMode || initialPreferences.length ? initialPreferences : DEFAULT_PREFERENCES)
    );
    const [avoidedCats, setAvoidedCats] = useState(new Set(initialAvoidedCategories));
    const [avoidedKeywords, setAvoidedKeywords] = useState(initialAvoidedKeywords);
    const [keywordInput, setKeywordInput] = useState('');
    const [saving, setSaving] = useState(false);
    const { confirm } = useConfirm();
    // El perfil, para pintar las alergias del alta con su candado (solo al revisar).
    const [perfil, setPerfil] = useState(null);
    // «Con lo que has marcado podemos cuadrarte...»: la respuesta del motor, en vivo.
    // `null` mientras responde o si la llamada falla: sin respuesta la franja no se
    // pinta y el Guardar no se apaga, porque un fallo de red no puede dejar a nadie
    // sin guardar sus preferencias.
    const [cuadra, setCuadra] = useState(null);

    useEffect(() => {
        if (!isEditMode) return;
        api('/api/clients/profile').then(setPerfil).catch(() => {});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isEditMode]);

    // LA FRANJA DE LOS 20 g (doc 23-08, P20): ¿con lo marcado se pueden cuadrar 20 g de
    // proteína y 20 g de hidratos? Se le pregunta al MOTOR de sugerencias, no a una
    // tabla aparte: el endpoint del doc 19-08 recorta el catálogo a las categorías
    // marcadas como preferidas (las grasas buenas van siempre, por eso la grasa no se
    // comprueba) y simula sugerir hasta llegar a los 20 g de cada macro. La
    // comprobación es EN VIVO, a cada marca, con un respiro de medio segundo para no
    // bombardear al motor mientras se marca en cadena.
    useEffect(() => {
        const t = setTimeout(() => {
            api('/api/calculator/preferencias/cuadra', {
                method: 'POST',
                body: JSON.stringify({ marcadas: Array.from(selected) }),
            }).then(setCuadra).catch(() => setCuadra(null));
        }, 500);
        return () => clearTimeout(t);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selected]);
    const noCuadra = !!cuadra && (!cuadra.proteina || !cuadra.hidratos);

    // Las alergias del alta y su estado ACTUAL: una está «puesta» si lo que bloquea sigue
    // en las listas de evitar. Quitarla avisa y no bloquea (doc 19-08).
    const alergias = alergiasDelAlta(perfil);
    const alergiaPuesta = (a) =>
        (a.bloquea.length || a.palabras.length)
            ? (a.bloquea.every(c => avoidedCats.has(c)) && a.palabras.every(p => avoidedKeywords.includes(p)))
            : true;
    const toggleAlergia = async (a) => {
        if (!a.bloquea.length && !a.palabras.length) return;   // informativa: nada que soltar
        if (alergiaPuesta(a)) {
            const seguro = await confirm({
                title: '¿Seguro?',
                description: a.aviso,
                confirmLabel: 'Sí, quitarla',
                cancelLabel: 'Dejarla como está',
                danger: true,
            });
            if (!seguro) return;
            setAvoidedCats(prev => { const s = new Set(prev); a.bloquea.forEach(c => s.delete(c)); return s; });
            setAvoidedKeywords(prev => prev.filter(p => !a.palabras.includes(p)));
        } else {
            setAvoidedCats(prev => { const s = new Set(prev); a.bloquea.forEach(c => s.add(c)); return s; });
            setAvoidedKeywords(prev => [...prev, ...a.palabras.filter(p => !prev.includes(p))]);
        }
    };
    // Lo derivado de una alergia vive arriba con su candado: en la lista de «lo que
    // dijiste que no querías» no se repite.
    const catsDeAlergia = new Set(alergias.flatMap(a => a.bloquea));
    const palabrasDeAlergia = new Set(alergias.flatMap(a => a.palabras));

    useEffect(() => {
        setSelected(withObligatory(isEditMode || initialPreferences.length ? initialPreferences : DEFAULT_PREFERENCES));
    }, [initialPreferences, isEditMode]);

    useEffect(() => {
        setAvoidedCats(new Set(initialAvoidedCategories));
    }, [initialAvoidedCategories]);

    useEffect(() => {
        setAvoidedKeywords(initialAvoidedKeywords);
    }, [initialAvoidedKeywords]);

    const toggleCategory = (id) => {
        if (OBLIGATORY_PREFERENCES.includes(id)) {
            // Antes esto era un `return` mudo: se pulsaba y no pasaba nada, sin decir por qué
            // (Jesús, 15-08, fallo 40).
            toast.info('Las grasas de buena calidad van siempre: el método las necesita en todas las comidas.');
            return;
        }
        setSelected(prev => {
            const s = new Set(prev);
            s.has(id) ? s.delete(id) : s.add(id);
            return s;
        });
        // LO MISMO NO PUEDE ESTAR EN LAS DOS LISTAS (Jesús, 15-08, fallo 34): «Huevos y
        // derivados» quedó marcado en «Me gusta» y en «Evitar» a la vez, y nada decía cuál
        // ganaba. Marcarlo aquí lo saca de la otra, y se dice.
        if (!selected.has(id) && avoidedCats.has(id)) {
            setAvoidedCats(prev => { const s = new Set(prev); s.delete(id); return s; });
            toast.info('Lo hemos quitado de "Evitar": no puede gustarte y evitarse a la vez.');
        }
    };

    const toggleAvoidedCat = (id) => {
        if (OBLIGATORY_PREFERENCES.includes(id) && !avoidedCats.has(id)) {
            toast.info('Las grasas de buena calidad no se pueden evitar: el método las necesita.');
            return;
        }
        setAvoidedCats(prev => {
            const s = new Set(prev);
            s.has(id) ? s.delete(id) : s.add(id);
            return s;
        });
        if (!avoidedCats.has(id) && selected.has(id)) {
            setSelected(prev => { const s = new Set(prev); s.delete(id); return s; });
            toast.info('Lo hemos quitado de "Me gusta": no puede gustarte y evitarse a la vez.');
        }
    };

    /**
     * Añade una palabra a evitar, y avisa si no bloquea nada.
     *
     * Jesús, 15-08 (fallo 39): metió «zzzz» y la app lo aceptó tan contenta, dando a
     * entender que a partir de ahí algo quedaba bloqueado. Se comprueba contra el catálogo
     * -- el mismo buscador de alimentos -- y, si no casa con nada, se dice; la palabra se
     * guarda igualmente, porque mañana puede entrar un alimento que sí case.
     */
    const addKeyword = async () => {
        const kw = keywordInput.trim().toLowerCase();
        if (!kw) return;
        if (avoidedKeywords.includes(kw)) {
            toast.error(`"${kw}" ya está en la lista`);
            return;
        }
        setAvoidedKeywords(prev => [...prev, kw]);
        setKeywordInput('');
        try {
            const res = await api(`/api/calculator/search?q=${encodeURIComponent(kw)}&limit=1`);
            if (!(res?.alimentos || []).length) {
                toast.warning(`"${kw}" no coincide con ningún alimento del catálogo: guardada, pero hoy no bloquea nada.`);
            }
        } catch (err) {
            // Si no se puede comprobar, no se dice nada: la palabra ya está guardada y
            // asustar con un error de red no ayuda a nadie.
            console.error('[palabra a evitar] no se pudo comprobar contra el catálogo', err);
        }
    };

    const removeKeyword = (kw) => {
        setAvoidedKeywords(prev => prev.filter(k => k !== kw));
    };

    /**
     * Cerrar sin guardar, avisando de lo que se pierde.
     *
     * Jesús, 15-08 (fallo 41): «correcto que no guarde, pero debería decir que se van a
     * perder los cambios». Si no se ha tocado nada se cierra sin preguntar: un diálogo por
     * abrir y cerrar una pantalla es peor que no tenerlo.
     */
    const mismoConjunto = (a, b) => a.size === b.size && [...a].every(x => b.has(x));
    const hayCambiosSinGuardar = () => {
        const base = withObligatory(isEditMode || initialPreferences.length ? initialPreferences : DEFAULT_PREFERENCES);
        if (!mismoConjunto(selected, base)) return true;
        if (!mismoConjunto(avoidedCats, new Set(initialAvoidedCategories))) return true;
        return avoidedKeywords.length !== initialAvoidedKeywords.length
            || avoidedKeywords.some(kw => !initialAvoidedKeywords.includes(kw));
    };

    const handleCancel = async () => {
        if (hayCambiosSinGuardar()) {
            const salir = await confirm({
                title: 'Tienes cambios sin guardar',
                description: 'Si cierras ahora, tus preferencias se quedan como estaban.',
                confirmLabel: 'Cerrar sin guardar',
                cancelLabel: 'Seguir editando',
                danger: true,
            });
            if (!salir) return;
        }
        onCancel();
    };

    const handleSave = async () => {
        if (selected.size < 3) {
            setActiveTab('like');
            toast.error('Selecciona al menos 3 categorías en "Me gusta"');
            return;
        }

        setSaving(true);
        try {
            const preferences = Array.from(selected);
            const avoided_categories = Array.from(avoidedCats);
            await api('/api/user/preferences', {
                method: 'POST',
                body: JSON.stringify({
                    food_preferences: preferences,
                    avoided_categories,
                    avoided_keywords: avoidedKeywords,
                })
            });
            toast.success('Preferencias guardadas');
            onSave(preferences, avoided_categories, avoidedKeywords);
        } catch (err) {
            toast.error('Error guardando preferencias');
            console.error(err);
        } finally {
            setSaving(false);
        }
    };

    // EL PIE NO PUEDE QUEDAR DEBAJO DE LA BARRA DE NAVEGACIÓN.
    // La ventana se centra a 90vh, así que en un móvil de 844 px su borde inferior cae a unos
    // 42 px del fondo, y la barra fija de abajo mide 64: la cuenta de categorías y el botón de
    // guardar quedaban tapados. Con treinta categorías y scroll dentro, si el botón se tapa
    // nadie guarda y la pantalla entera deja de servir. Lo vio Jesús el 11-08.
    // En escritorio no hay barra y todo se queda igual.
    return (
        <div className="min-h-screen bg-bg-dark flex items-center justify-center p-4 pb-24 lg:pb-4">
            <div className="bg-card rounded-2xl shadow-xl max-w-md w-full max-h-[85vh] lg:max-h-[90vh] flex flex-col">
                {/* Header */}
                <div className="p-6 border-b flex-shrink-0">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="w-10 h-10 rounded-full bg-brand/10 flex items-center justify-center">
                            <Settings className="w-5 h-5 text-brand" />
                        </div>
                        {/* «Preferencias de alimentos», no «Editar preferencias» (doc 23-08,
                            P17): la pantalla dice de qué van las preferencias. */}
                        <h1 className="text-xl font-bold text-foreground flex-1">
                            {isEditMode ? 'Preferencias de alimentos' : 'Configura tus preferencias'}
                        </h1>
                        {isEditMode && onCancel && (
                            <button onClick={handleCancel} aria-label="Cerrar preferencias"
                                className="text-muted-foreground hover:text-muted-foreground transition-colors">
                                <X size={20} />
                            </button>
                        )}
                    </div>

                    {!isEditMode && (
                        <p className="text-muted-foreground text-sm" data-testid="preferences-intro">
                            Un último paso antes de empezar. Esto le dice a la calculadora qué
                            alimentos sugerirte. Ya dejamos algunos marcados: puedes ajustarlos o
                            guardar directamente y cambiarlos cuando quieras.
                        </p>
                    )}

                    {/* LAS DOS PESTAÑAS DEL DOC 19-08, y en su orden: primero confirmar lo
                        que dijo al alta, luego los preferidos. */}
                    <div className="flex gap-2 mt-3">
                        <button
                            onClick={() => setActiveTab('avoid')}
                            data-testid="tab-evitar"
                            className={`flex-1 py-2 px-2 rounded-lg text-[13px] font-medium transition-all flex items-center justify-center gap-1 ${
                                activeTab === 'avoid'
                                    ? 'bg-brand text-white'
                                    : 'bg-muted text-muted-foreground hover:bg-muted'
                            }`}
                        >
                            <Ban className="w-3 h-3 flex-shrink-0" />
                            Alimentos a evitar
                            {(avoidedCats.size > 0 || avoidedKeywords.length > 0) && (
                                <span className={`ml-1 text-xs px-1.5 py-0.5 rounded-full ${
                                    activeTab === 'avoid' ? 'bg-white/30' : 'bg-brand/10 text-brand'
                                }`}>
                                    {avoidedCats.size + avoidedKeywords.length}
                                </span>
                            )}
                        </button>
                        <button
                            onClick={() => setActiveTab('like')}
                            data-testid="tab-preferidos"
                            className={`flex-1 py-2 px-2 rounded-lg text-[13px] font-medium transition-all ${
                                activeTab === 'like'
                                    ? 'bg-brand text-white'
                                    : 'bg-muted text-muted-foreground hover:bg-muted'
                            }`}
                        >
                            Mis alimentos preferidos
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-4">
                    {activeTab === 'like' && (
                        <>
                            {/* El texto del doc 19-08, literal. */}
                            <p className="text-muted-foreground text-sm mb-3">
                                Te los sugeriremos cuando te falten macros para terminar de cuadrar
                                una comida, y son los que usamos para crearte los menús.
                            </p>
                            {/* LOS DIEZ CAJONES, cada uno con su número y su Todas · Ninguna.
                                Aquí solo se marcan categorías: no hay buscador de alimentos a
                                propósito (doc 19-08: «lo fino está en la otra pestaña»). */}
                            <div className="space-y-4">
                                {CAJONES.map(cajon => {
                                    const cats = cajon.cats.map(id => PREFERENCE_CATEGORIES.find(c => c.id === id)).filter(Boolean);
                                    const marcables = cats.filter(c => !OBLIGATORY_PREFERENCES.includes(c.id));
                                    return (
                                        <div key={cajon.id} data-testid={`cajon-${cajon.id}`}>
                                            <div className="flex items-center justify-between mb-1">
                                                <p className="text-xs font-bold text-muted-foreground uppercase tracking-wide">
                                                    {cajon.nombre} · {cats.length}
                                                </p>
                                                {marcables.length > 1 && (
                                                    <span className="text-xs whitespace-nowrap">
                                                        <button type="button" className="font-semibold text-brand hover:underline"
                                                            onClick={() => setSelected(prev => { const s = new Set(prev); marcables.forEach(c => s.add(c.id)); return s; })}>
                                                            Todas
                                                        </button>
                                                        <span className="text-muted-foreground"> · </span>
                                                        <button type="button" className="font-semibold text-muted-foreground hover:underline"
                                                            onClick={() => setSelected(prev => { const s = new Set(prev); marcables.forEach(c => s.delete(c.id)); return s; })}>
                                                            Ninguna
                                                        </button>
                                                    </span>
                                                )}
                                            </div>
                                            <div className="space-y-1">
                                                {cats.map(cat => (
                                                    <CategoryCheckbox
                                                        key={cat.id}
                                                        cat={cat}
                                                        checked={selected.has(cat.id)}
                                                        onToggle={toggleCategory}
                                                        locked={OBLIGATORY_PREFERENCES.includes(cat.id)}
                                                        colorClass="bg-brand/10 border-brand"
                                                    />
                                                ))}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </>
                    )}

                    {activeTab === 'avoid' && (
                        <>
                            <p className="text-muted-foreground text-sm mb-3">
                                {isEditMode
                                    ? 'Esto es lo que nos dijiste al darte de alta. Confírmalo o cámbialo.'
                                    : 'Estos alimentos nunca aparecerán en ninguna sugerencia - alergias, intolerancias o simplemente lo que no te gusta.'}
                            </p>

                            {/* TUS ALERGIAS E INTOLERANCIAS (doc 19-08): las del alta, con
                                candado. Quitar una avisa («¿Seguro? A partir de ahora podemos
                                ponerte lácteos.»), no bloquea. Las parciales no quitan nada:
                                el candado ahí es informativo. */}
                            {alergias.length > 0 && (
                                <div className="mb-4" data-testid="alergias-del-alta">
                                    <p className="text-xs font-semibold text-muted-foreground uppercase mb-2">Tus alergias e intolerancias</p>
                                    <div className="space-y-1">
                                        {alergias.map(a => {
                                            const bloquea = a.bloquea.length > 0 || a.palabras.length > 0;
                                            const puesta = alergiaPuesta(a);
                                            return (
                                                <div key={a.clave}
                                                    onClick={() => toggleAlergia(a)}
                                                    data-testid={`alergia-${a.clave}`}
                                                    className={`flex items-center gap-3 p-3 rounded-lg border ${bloquea ? 'cursor-pointer' : 'cursor-default'} ${
                                                        puesta && bloquea ? 'bg-brand/10 border-brand' : 'bg-muted border-transparent'
                                                    }`}>
                                                    <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 ${
                                                        puesta && bloquea ? 'bg-brand border-brand' : 'border-border'
                                                    }`}>
                                                        {puesta && bloquea && <Check className="w-3 h-3 text-white" />}
                                                    </div>
                                                    <span className="text-sm flex-1 min-w-0 text-foreground font-medium">
                                                        {a.nombre}
                                                        <span className="block text-xs text-muted-foreground font-normal">{a.nota}</span>
                                                    </span>
                                                    <Lock className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}

                            {isEditMode && (
                                <p className="text-xs font-semibold text-muted-foreground uppercase mb-2 mt-4">Lo que dijiste que no querías</p>
                            )}

                            {/* Keyword section */}
                            <div className="mb-4">
                                <p className="text-xs font-semibold text-muted-foreground uppercase mb-2">Por palabra clave</p>
                                <div className="flex gap-2 mb-2">
                                    <input
                                        type="text"
                                        value={keywordInput}
                                        onChange={e => setKeywordInput(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && addKeyword()}
                                        placeholder='Ej: "cerdo", "trigo", "pan"...'
                                        className="flex-1 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand/40"
                                    />
                                    <button
                                        onClick={addKeyword}
                                        className="bg-brand text-white rounded-lg px-3 py-2 hover:bg-brand-dark transition-colors"
                                    >
                                        <Plus className="w-4 h-4" />
                                    </button>
                                </div>
                                {avoidedKeywords.length > 0 && (
                                    <div className="flex flex-wrap gap-2">
                                        {/* Las palabras que vienen de una alergia viven arriba
                                            con su candado: aquí solo lo demás. */}
                                        {avoidedKeywords.filter(kw => !palabrasDeAlergia.has(kw)).map(kw => (
                                            <span
                                                key={kw}
                                                className="flex items-center gap-1 bg-brand/10 border border-brand/40 text-brand text-xs px-2 py-1 rounded-full"
                                            >
                                                {kw}
                                                <button onClick={() => removeKeyword(kw)} className="hover:text-brand-dark">
                                                    <X className="w-3 h-3" />
                                                </button>
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* «O quitar grupos enteros» (doc 19-08): la lista completa de
                                categorías, sin las que ya bloquea una alergia (esas van
                                arriba con su candado). */}
                            <div className="flex items-center justify-between mb-2">
                                <p className="text-xs font-semibold text-muted-foreground uppercase">O quitar grupos enteros</p>
                                <button
                                    type="button"
                                    onClick={() => setAvoidedCats(avoidedCats.size === PREFERENCE_CATEGORIES.length ? new Set() : new Set(PREFERENCE_CATEGORIES.map(c => c.id)))}
                                    className="text-xs font-semibold text-brand hover:underline whitespace-nowrap"
                                    data-testid="select-all-avoid"
                                >
                                    {avoidedCats.size === PREFERENCE_CATEGORIES.length ? 'Quitar todos' : 'Seleccionar todos'}
                                </button>
                            </div>
                            {/* Con opacidad (`/10`) y no un tinte fijo (`bg-red-50` en su día):
                                en modo oscuro el tinte clarito con la letra blanca encima dejaba
                                la categoría marcada SIN TEXTO. Visto al probar el fallo 34. */}
                            <div className="space-y-1">
                                {PREFERENCE_CATEGORIES.filter(cat => !catsDeAlergia.has(cat.id)).map(cat => (
                                    <CategoryCheckbox
                                        key={cat.id}
                                        cat={cat}
                                        checked={avoidedCats.has(cat.id)}
                                        onToggle={toggleAvoidedCat}
                                        colorClass="bg-brand/10 border-brand"
                                    />
                                ))}
                            </div>
                        </>
                    )}

                    {/* AQUÍ NO VA NADA MÁS (doc 23-08, P16): los tres selectores de «Cómo
                        quieres tu día» que vivían debajo de las categorías se fueron con su
                        Guardar propio. Esas preguntas pasan al cuestionario, y el día suelto
                        ya se cambia en la configuración del día de Nutrición. */}
                </div>

                {/* Footer */}
                <div className="p-4 border-t flex-shrink-0 bg-muted">
                    {/* LA FRANJA DE LOS 20 g (doc 23-08, P20): donde antes ponía «No estás
                        evitando nada» va la respuesta en vivo del motor: si con lo marcado
                        se cuadran 20 g de proteína y 20 g de hidratos. Se pinta en las dos
                        pestañas porque el Guardar es uno y se apaga si no llega: el porqué
                        tiene que estar al lado del botón apagado. */}
                    {cuadra && (
                        <div className="mb-3" data-testid="cuadra-en-vivo">
                            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide mb-1">
                                Con lo que has marcado podemos cuadrarte
                            </p>
                            <div className="flex gap-4 text-sm">
                                <span className={cuadra.proteina ? 'text-green-600 dark:text-green-400' : 'text-red-500'}>
                                    {cuadra.proteina ? '✓' : '✗'} 20 g de proteína
                                </span>
                                <span className={cuadra.hidratos ? 'text-green-600 dark:text-green-400' : 'text-red-500'}>
                                    {cuadra.hidratos ? '✓' : '✗'} 20 g de hidratos
                                </span>
                            </div>
                            {noCuadra && (
                                <p className="text-xs text-red-500 mt-1">
                                    Con lo que has marcado no podemos cuadrarte{' '}
                                    {[!cuadra.proteina && '20 g de proteína', !cuadra.hidratos && '20 g de hidratos']
                                        .filter(Boolean).join(' ni ')}. Marca alguna categoría más en "Mis alimentos preferidos" para poder guardar.
                                </p>
                            )}
                        </div>
                    )}
                    {activeTab === 'like' && selected.size < 3 && (
                        <p className="text-sm mb-3 text-red-500">
                            Selecciona al menos 3 categorías ({selected.size}/3)
                        </p>
                    )}
                    {/* UN solo Guardar, «Guardar» a secas y en el naranja de la casa (doc
                        23-08, P18, P19 y P22): fuera el contador, que además contaba las
                        categorías de la otra pestaña. Apagado si lo excluido no deja
                        cuadrar los 20 g (P20). */}
                    <Button
                        onClick={handleSave}
                        disabled={selected.size < 3 || saving || noCuadra}
                        className="w-full h-12 rounded-full bg-brand hover:bg-brand-dark text-white font-bold disabled:opacity-50"
                        data-testid="save-preferences-btn"
                    >
                        {saving ? 'Guardando...' : 'Guardar'}
                    </Button>
                </div>
            </div>
        </div>
    );
};

export default PreferencesSetup;
