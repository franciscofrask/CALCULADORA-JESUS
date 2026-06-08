import React, { useState, useEffect } from 'react';
import { Button } from '../ui/button';
import { toast } from 'sonner';
import { Settings, Check, X, Plus, Ban } from 'lucide-react';

// MAPEO de categorías de preferencias con sus prefijos para filtrar
export const PREFERENCE_CATEGORIES = [
    { id: 'grasas_buenas', label: 'Alimentos ricos en grasas de buena calidad', prefixes: ['42'] },
    { id: 'grasas_todo', label: 'Alimentos ricos en grasas de todo tipo', prefixes: ['17'] },
    { id: 'aperitivos', label: 'Aperitivos', prefixes: ['38'] },
    { id: 'arroces', label: 'Arroces y derivados', prefixes: ['21'] },
    { id: 'aves', label: 'Aves', prefixes: ['2.2'] },
    { id: 'barritas', label: 'Barritas energéticas', prefixes: ['47'] },
    { id: 'bebidas', label: 'Bebidas energéticas, refrescos y cafés', prefixes: ['19'] },
    { id: 'isotonicas', label: 'Bebidas isotónicas', prefixes: ['18.1'] },
    { id: 'beb_vegetales', label: 'Bebidas vegetales', prefixes: ['24'] },
    { id: 'bolleria', label: 'Bollería industrial y galletas', prefixes: ['31'] },
    { id: 'cacao', label: 'Cacao en polvo, azúcares, chucherías y miel', prefixes: ['37'] },
    { id: 'casqueria', label: 'Casquería', prefixes: ['40'] },
    { id: 'cerdo', label: 'Cerdo', prefixes: ['2.4'] },
    { id: 'cereales', label: 'Cereales (excepto arroz)', prefixes: ['7'] },
    { id: 'chocolates', label: 'Chocolates y chocolatinas', prefixes: ['34'] },
    { id: 'cocina_esp', label: 'Cocina tradicional española', prefixes: ['39'] },
    { id: 'comida_rapida', label: 'Comida rápida', prefixes: ['49'] },
    { id: 'embutidos', label: 'Embutidos', prefixes: ['2.1'] },
    { id: 'fruta', label: 'Fruta y derivados', prefixes: ['11'] },
    { id: 'helados', label: 'Helados y postres', prefixes: ['35', '36'] },
    { id: 'huevos', label: 'Huevos y derivados', prefixes: ['1'] },
    { id: 'lacteos', label: 'Lácteos y derivados', prefixes: ['5'] },
    { id: 'legumbres', label: 'Legumbres', prefixes: ['10'] },
    { id: 'carnes_blancas', label: 'Otras carnes blancas', prefixes: ['2.5'] },
    { id: 'carnes_rojas', label: 'Otras carnes rojas', prefixes: ['2.6'] },
    { id: 'panes', label: 'Panes y tortillas de trigo', prefixes: ['8'] },
    { id: 'pasta', label: 'Pasta, quinoa y derivados', prefixes: ['22'] },
    { id: 'pescados', label: 'Pescados y mariscos', prefixes: ['3'] },
    { id: 'pizza', label: 'Pizza, lasaña, empanadas y empanadillas', prefixes: ['32'] },
    { id: 'proteina_polvo', label: 'Proteína en polvo y barritas proteicas', prefixes: ['4', '29', '30'] },
    { id: 'proteina_vegetal', label: 'Proteína vegetal', prefixes: ['28'] },
    { id: 'salsas', label: 'Salsas, siropes y konjac', prefixes: ['16'] },
    { id: 'sopas', label: 'Sopas y Caldos', prefixes: ['48'] },
    { id: 'superalimentos', label: 'Superalimentos', prefixes: ['52'] },
    { id: 'tuberculos', label: 'Tubérculos y derivados', prefixes: ['9'] },
    { id: 'vacuno', label: 'Vacuno o buey', prefixes: ['2.3'] },
    { id: 'verduras', label: 'Verduras y hortalizas', prefixes: ['13'] },
];

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
    const [selected, setSelected] = useState(new Set(initialPreferences));
    const [avoidedCats, setAvoidedCats] = useState(new Set(initialAvoidedCategories));
    const [avoidedKeywords, setAvoidedKeywords] = useState(initialAvoidedKeywords);
    const [keywordInput, setKeywordInput] = useState('');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        setSelected(new Set(initialPreferences));
    }, [initialPreferences]);

    useEffect(() => {
        setAvoidedCats(new Set(initialAvoidedCategories));
    }, [initialAvoidedCategories]);

    useEffect(() => {
        setAvoidedKeywords(initialAvoidedKeywords);
    }, [initialAvoidedKeywords]);

    const toggleCategory = (id) => {
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

    const CategoryCheckbox = ({ cat, checked, onToggle, colorClass }) => (
        <label
            key={cat.id}
            className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all ${
                checked
                    ? `${colorClass} border`
                    : 'bg-gray-50 border border-transparent hover:bg-gray-100'
            }`}
            onClick={() => onToggle(cat.id)}
        >
            <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all flex-shrink-0 ${
                checked ? `${colorClass.includes('orange') ? 'bg-brand-orange border-brand-orange' : 'bg-red-500 border-red-500'}` : 'border-gray-300'
            }`}>
                {checked && <Check className="w-3 h-3 text-white" />}
            </div>
            <span className={`text-sm ${checked ? 'text-gray-900 font-medium' : 'text-gray-700'}`}>
                {cat.label}
            </span>
        </label>
    );

    return (
        <div className="min-h-screen bg-bg-dark flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl shadow-xl max-w-md w-full max-h-[90vh] flex flex-col">
                {/* Header */}
                <div className="p-6 border-b flex-shrink-0">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="w-10 h-10 rounded-full bg-brand-orange/10 flex items-center justify-center">
                            <Settings className="w-5 h-5 text-brand-orange" />
                        </div>
                        <h1 className="text-xl font-bold text-gray-900 flex-1">
                            {isEditMode ? 'Editar preferencias' : 'Configura tus preferencias'}
                        </h1>
                        {isEditMode && onCancel && (
                            <button onClick={onCancel} className="text-gray-400 hover:text-gray-600 transition-colors">
                                <X size={20} />
                            </button>
                        )}
                    </div>

                    {/* Tabs */}
                    <div className="flex gap-2 mt-3">
                        <button
                            onClick={() => setActiveTab('like')}
                            className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all ${
                                activeTab === 'like'
                                    ? 'bg-brand-orange text-white'
                                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                            }`}
                        >
                            Me gusta
                        </button>
                        <button
                            onClick={() => setActiveTab('avoid')}
                            className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-1 ${
                                activeTab === 'avoid'
                                    ? 'bg-red-500 text-white'
                                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
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
                            <p className="text-gray-500 text-sm mb-3">
                                La calculadora te sugerirá estos alimentos en los últimos toques de cada comida.
                            </p>
                            <div className="space-y-1">
                                {PREFERENCE_CATEGORIES.map(cat => (
                                    <CategoryCheckbox
                                        key={cat.id}
                                        cat={cat}
                                        checked={selected.has(cat.id)}
                                        onToggle={toggleCategory}
                                        colorClass="bg-brand-orange/10 border-brand-orange"
                                    />
                                ))}
                            </div>
                        </>
                    )}

                    {activeTab === 'avoid' && (
                        <>
                            <p className="text-gray-500 text-sm mb-3">
                                Estos alimentos nunca aparecerán en ninguna sugerencia — alergias, intolerancias o simplemente lo que no te gusta.
                            </p>

                            {/* Keyword section */}
                            <div className="mb-4">
                                <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Por palabra clave</p>
                                <div className="flex gap-2 mb-2">
                                    <input
                                        type="text"
                                        value={keywordInput}
                                        onChange={e => setKeywordInput(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && addKeyword()}
                                        placeholder='Ej: "cerdo", "trigo", "pan"...'
                                        className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-300"
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
                            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Por categoría</p>
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
                <div className="p-4 border-t flex-shrink-0 bg-gray-50">
                    {activeTab === 'like' && (
                        <p className={`text-sm mb-3 ${selected.size < 3 ? 'text-red-500' : 'text-gray-500'}`}>
                            {selected.size < 3
                                ? `Selecciona al menos 3 categorías (${selected.size}/3)`
                                : `${selected.size} categorías seleccionadas`
                            }
                        </p>
                    )}
                    {activeTab === 'avoid' && (
                        <p className="text-sm mb-3 text-gray-500">
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
