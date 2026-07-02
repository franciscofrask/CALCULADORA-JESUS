import React, { useState, useEffect } from 'react';
import { Button } from '../ui/button';
import { toast } from 'sonner';
import { Settings, Check, X, Plus, Ban } from 'lucide-react';
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

// Obligatoria: siempre marcada, no se puede desmarcar.
export const OBLIGATORY_PREFERENCES = ['grasas_buenas'];

// Pre-marcadas para clientes nuevos (todas desmarcables salvo las obligatorias).
export const DEFAULT_PREFERENCES = ['grasas_buenas', 'verduras', 'embutidos', 'lacteos', 'salsas'];

const withObligatory = (ids) => {
    const s = new Set(ids);
    OBLIGATORY_PREFERENCES.forEach(id => s.add(id));
    return s;
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
    const [activeTab, setActiveTab] = useState('like');
    const [selected, setSelected] = useState(
        withObligatory(isEditMode || initialPreferences.length ? initialPreferences : DEFAULT_PREFERENCES)
    );
    const [avoidedCats, setAvoidedCats] = useState(new Set(initialAvoidedCategories));
    const [avoidedKeywords, setAvoidedKeywords] = useState(initialAvoidedKeywords);
    const [keywordInput, setKeywordInput] = useState('');
    const [saving, setSaving] = useState(false);

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
        if (OBLIGATORY_PREFERENCES.includes(id)) return; // obligatoria, no se desmarca
        setSelected(prev => {
            const s = new Set(prev);
            s.has(id) ? s.delete(id) : s.add(id);
            return s;
        });
    };

    const toggleAvoidedCat = (id) => {
        setAvoidedCats(prev => {
            const s = new Set(prev);
            s.has(id) ? s.delete(id) : s.add(id);
            return s;
        });
    };

    const addKeyword = () => {
        const kw = keywordInput.trim().toLowerCase();
        if (!kw) return;
        if (avoidedKeywords.includes(kw)) {
            toast.error(`"${kw}" ya está en la lista`);
            return;
        }
        setAvoidedKeywords(prev => [...prev, kw]);
        setKeywordInput('');
    };

    const removeKeyword = (kw) => {
        setAvoidedKeywords(prev => prev.filter(k => k !== kw));
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

    const CategoryCheckbox = ({ cat, checked, onToggle, colorClass, locked = false }) => (
        <label
            key={cat.id}
            className={`flex items-center gap-3 p-3 rounded-lg transition-all ${locked ? 'cursor-default' : 'cursor-pointer'} ${
                checked
                    ? `${colorClass} border`
                    : 'bg-muted border border-transparent hover:bg-muted'
            }`}
            onClick={() => !locked && onToggle(cat.id)}
        >
            <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all flex-shrink-0 ${
                checked ? `${colorClass.includes('orange') ? 'bg-brand-orange border-brand-orange' : 'bg-red-500 border-red-500'}` : 'border-border'
            }`}>
                {checked && <Check className="w-3 h-3 text-white" />}
            </div>
            <span className={`text-sm flex-1 ${checked ? 'text-foreground font-medium' : 'text-foreground'}`}>
                {cat.label}
            </span>
            {locked && <span className="text-xs text-muted-foreground flex-shrink-0">Obligatorio</span>}
        </label>
    );

    return (
        <div className="min-h-screen bg-bg-dark flex items-center justify-center p-4">
            <div className="bg-card rounded-2xl shadow-xl max-w-md w-full max-h-[90vh] flex flex-col">
                {/* Header */}
                <div className="p-6 border-b flex-shrink-0">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="w-10 h-10 rounded-full bg-brand-orange/10 flex items-center justify-center">
                            <Settings className="w-5 h-5 text-brand-orange" />
                        </div>
                        <h1 className="text-xl font-bold text-foreground flex-1">
                            {isEditMode ? 'Editar preferencias' : 'Configura tus preferencias'}
                        </h1>
                        {isEditMode && onCancel && (
                            <button onClick={onCancel} className="text-muted-foreground hover:text-muted-foreground transition-colors">
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

                    {/* Tabs */}
                    <div className="flex gap-2 mt-3">
                        <button
                            onClick={() => setActiveTab('like')}
                            className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all ${
                                activeTab === 'like'
                                    ? 'bg-brand-orange text-white'
                                    : 'bg-muted text-muted-foreground hover:bg-muted'
                            }`}
                        >
                            Me gusta
                        </button>
                        <button
                            onClick={() => setActiveTab('avoid')}
                            className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-1 ${
                                activeTab === 'avoid'
                                    ? 'bg-red-500 text-white'
                                    : 'bg-muted text-muted-foreground hover:bg-muted'
                            }`}
                        >
                            <Ban className="w-3 h-3" />
                            Evitar
                            {(avoidedCats.size > 0 || avoidedKeywords.length > 0) && (
                                <span className={`ml-1 text-xs px-1.5 py-0.5 rounded-full ${
                                    activeTab === 'avoid' ? 'bg-white/30' : 'bg-red-100 text-red-600'
                                }`}>
                                    {avoidedCats.size + avoidedKeywords.length}
                                </span>
                            )}
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-4">
                    {activeTab === 'like' && (
                        <>
                            <div className="flex items-center justify-between mb-3">
                                <p className="text-muted-foreground text-sm flex-1 pr-2">
                                    La calculadora te sugerirá estos alimentos en los últimos toques de cada comida.
                                </p>
                                <button
                                    type="button"
                                    onClick={() => setSelected(selected.size === PREFERENCE_CATEGORIES.length ? withObligatory([]) : new Set(PREFERENCE_CATEGORIES.map(c => c.id)))}
                                    className="text-xs font-semibold text-brand-orange hover:underline whitespace-nowrap flex-shrink-0"
                                    data-testid="select-all-like"
                                >
                                    {selected.size === PREFERENCE_CATEGORIES.length ? 'Quitar todos' : 'Seleccionar todos'}
                                </button>
                            </div>
                            <div className="space-y-1">
                                {PREFERENCE_CATEGORIES.map(cat => (
                                    <CategoryCheckbox
                                        key={cat.id}
                                        cat={cat}
                                        checked={selected.has(cat.id)}
                                        onToggle={toggleCategory}
                                        locked={OBLIGATORY_PREFERENCES.includes(cat.id)}
                                        colorClass="bg-brand-orange/10 border-brand-orange"
                                    />
                                ))}
                            </div>
                        </>
                    )}

                    {activeTab === 'avoid' && (
                        <>
                            <p className="text-muted-foreground text-sm mb-3">
                                Estos alimentos nunca aparecerán en ninguna sugerencia - alergias, intolerancias o simplemente lo que no te gusta.
                            </p>

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
                                        className="flex-1 border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-300"
                                    />
                                    <button
                                        onClick={addKeyword}
                                        className="bg-red-500 text-white rounded-lg px-3 py-2 hover:bg-red-600 transition-colors"
                                    >
                                        <Plus className="w-4 h-4" />
                                    </button>
                                </div>
                                {avoidedKeywords.length > 0 && (
                                    <div className="flex flex-wrap gap-2">
                                        {avoidedKeywords.map(kw => (
                                            <span
                                                key={kw}
                                                className="flex items-center gap-1 bg-red-50 border border-red-200 text-red-700 text-xs px-2 py-1 rounded-full"
                                            >
                                                {kw}
                                                <button onClick={() => removeKeyword(kw)} className="hover:text-red-900">
                                                    <X className="w-3 h-3" />
                                                </button>
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* Category section */}
                            <div className="flex items-center justify-between mb-2">
                                <p className="text-xs font-semibold text-muted-foreground uppercase">Por categoría</p>
                                <button
                                    type="button"
                                    onClick={() => setAvoidedCats(avoidedCats.size === PREFERENCE_CATEGORIES.length ? new Set() : new Set(PREFERENCE_CATEGORIES.map(c => c.id)))}
                                    className="text-xs font-semibold text-red-500 hover:underline whitespace-nowrap"
                                    data-testid="select-all-avoid"
                                >
                                    {avoidedCats.size === PREFERENCE_CATEGORIES.length ? 'Quitar todos' : 'Seleccionar todos'}
                                </button>
                            </div>
                            <div className="space-y-1">
                                {PREFERENCE_CATEGORIES.map(cat => (
                                    <CategoryCheckbox
                                        key={cat.id}
                                        cat={cat}
                                        checked={avoidedCats.has(cat.id)}
                                        onToggle={toggleAvoidedCat}
                                        colorClass="bg-red-50 border-red-400"
                                    />
                                ))}
                            </div>
                        </>
                    )}
                </div>

                {/* Footer */}
                <div className="p-4 border-t flex-shrink-0 bg-muted">
                    {activeTab === 'like' && (
                        <p className={`text-sm mb-3 ${selected.size < 3 ? 'text-red-500' : 'text-muted-foreground'}`}>
                            {selected.size < 3
                                ? `Selecciona al menos 3 categorías (${selected.size}/3)`
                                : `${selected.size} categorías seleccionadas`
                            }
                        </p>
                    )}
                    {activeTab === 'avoid' && (
                        <p className="text-sm mb-3 text-muted-foreground">
                            {avoidedCats.size + avoidedKeywords.length === 0
                                ? 'Sin restricciones configuradas'
                                : `${avoidedCats.size} categorías + ${avoidedKeywords.length} palabras clave bloqueadas`
                            }
                        </p>
                    )}
                    <Button
                        onClick={handleSave}
                        disabled={selected.size < 3 || saving}
                        className="w-full h-12 rounded-full bg-brand-orange hover:bg-orange-600 text-white font-bold disabled:opacity-50"
                        data-testid="save-preferences-btn"
                    >
                        {saving ? 'Guardando...' : 'GUARDAR PREFERENCIAS'}
                    </Button>
                </div>
            </div>
        </div>
    );
};

export default PreferencesSetup;
