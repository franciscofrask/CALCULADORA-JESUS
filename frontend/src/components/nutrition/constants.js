/**
 * Constantes y utilidades para la página de Nutrición
 */

export const API_URL = process.env.REACT_APP_BACKEND_URL;

// Food emojis for categories
export const FOOD_EMOJIS = {
    '2': '🥩', '3': '🐟', '1': '🥚', '5': '🥛', '4': '💪',
    '7': '🌾', '8': '🍞', '21': '🍚', '22': '🍝', '9': '🥔',
    '10': '🫘', '11': '🍎', '13': '🥦', '17': '🫒', '17.2': '🥜',
    '16': '🥫', '24': '🥤', 'default': '🍽️'
};

export const getFoodEmoji = (categorias) => {
    if (!categorias) return FOOD_EMOJIS.default;
    const mainCat = categorias.split(' | ')[0]?.split('.')[0];
    return FOOD_EMOJIS[mainCat] || FOOD_EMOJIS.default;
};

// Category filter chips
export const CATEGORY_CHIPS = [
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
export const MOMENTO_OPTIONS = [
    { value: 0, label: 'En ayunas' },
    { value: 1, label: 'Tras Comida 1' },
    { value: 2, label: 'Tras Comida 2' },
    { value: 3, label: 'Tras Comida 3' },
];

// Periworkout options  
export const PERI_OPTIONS = [
    { value: 'intra_post', label: 'Intra + Post' },
    { value: 'solo_post', label: 'Solo Post' },
    { value: 'solo_intra', label: 'Solo Intra' },
    { value: 'sin_peri', label: 'Sin periworkout' },
];

// Categories for Build Meal Modal - Step 1 (Proteínas)
export const PROTEIN_CATEGORIES = [
    { id: 'huevos', label: 'Huevos', emoji: '🥚', prefixes: ['1.2'] },
    { id: 'carnes', label: 'Carnes', emoji: '🥩', prefixes: ['2'] },
    { id: 'pescados', label: 'Pescados', emoji: '🐟', prefixes: ['3'] },
    { id: 'mariscos', label: 'Mariscos', emoji: '🦐', prefixes: ['3.9'] },
    { id: 'lacteos', label: 'Lácteos', emoji: '🥛', prefixes: ['5'] },
    { id: 'embutidos', label: 'Embutidos', emoji: '🥓', prefixes: ['2.7'] },
    { id: 'proteina_polvo', label: 'Proteína en polvo', emoji: '💪', prefixes: ['4'] },
];

// Categories for Build Meal Modal - Step 2 (Acompañamientos)
export const ACCOMPANIMENT_CATEGORIES = [
    { id: 'cereales', label: 'Cereales', emoji: '🌾', prefixes: ['7'] },
    { id: 'panes', label: 'Panes', emoji: '🍞', prefixes: ['8'] },
    { id: 'tuberculos', label: 'Tubérculos', emoji: '🥔', prefixes: ['9'] },
    { id: 'legumbres', label: 'Legumbres', emoji: '🫘', prefixes: ['10'] },
    { id: 'frutas', label: 'Frutas', emoji: '🍎', prefixes: ['11'] },
    { id: 'verduras', label: 'Verduras', emoji: '🥦', prefixes: ['13'] },
    { id: 'arroces', label: 'Arroces', emoji: '🍚', prefixes: ['21'] },
    { id: 'pasta', label: 'Pasta', emoji: '🍝', prefixes: ['22'] },
    { id: 'grasas', label: 'Grasas', emoji: '🫒', prefixes: ['17'] },
    { id: 'salsas', label: 'Salsas', emoji: '🥫', prefixes: ['16'] },
];

// Intra-entreno categories
export const INTRA_CATEGORIES = [
    { id: 'aminoacidos', label: 'Aminoácidos', emoji: '⚡', prefixes: ['41'] },
    { id: 'intra', label: 'Bebidas intra', emoji: '🥤', prefixes: ['18.1.1'] },
    { id: 'geles', label: 'Geles energéticos', emoji: '🍯', prefixes: ['47'] },
    { id: 'fruta_desh', label: 'Fruta deshidratada', emoji: '🍇', prefixes: ['11.3'] },
];

// Post-entreno protein categories
export const POST_PROTEIN_CATEGORIES = [
    { id: 'whey', label: 'Whey Protein', emoji: '💪', prefixes: ['4.1', '4.2'] },
    { id: 'caseina', label: 'Caseína', emoji: '🥛', prefixes: ['4.3'] },
    { id: 'aislado', label: 'Aislado/Hidrolizado', emoji: '⚡', prefixes: ['4.2'] },
];

// Post-entreno accompaniment categories
export const POST_ACCOMPANIMENT_CATEGORIES = [
    { id: 'frutas', label: 'Frutas', emoji: '🍎', prefixes: ['11'] },
    { id: 'crema_arroz', label: 'Crema de arroz', emoji: '🍚', prefixes: ['7.2'] },
    { id: 'miel', label: 'Miel/Mermelada', emoji: '🍯', prefixes: ['37'] },
    { id: 'lacteos', label: 'Lácteos', emoji: '🥛', prefixes: ['5'] },
];

// Helper to check if food matches category prefixes
export const foodMatchesCategory = (food, category) => {
    if (!food?.categorias || !category?.prefixes) return false;
    return category.prefixes.some(prefix => 
        food.categorias.split(' | ').some(cat => cat.startsWith(prefix))
    );
};

// Calculate macros for a food at a given quantity
export const calculateFoodMacros = (food, quantity) => {
    if (!food) return { P: 0, H: 0, G: 0 };
    const factor = quantity / 100;
    return {
        P: Math.round((food.proteinas || 0) * factor * 10) / 10,
        H: Math.round((food.hidratos || 0) * factor * 10) / 10,
        G: Math.round((food.grasas || 0) * factor * 10) / 10
    };
};

// Format quantity display
export const formatQuantity = (cantidad, unidad) => {
    if (unidad === 'ud') {
        return `${cantidad} ud`;
    }
    return `${cantidad}g`;
};
