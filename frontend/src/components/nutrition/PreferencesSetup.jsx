import React, { useState, useEffect } from 'react';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { toast } from 'sonner';
import { Settings, Check } from 'lucide-react';

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

const PreferencesSetup = ({ api, initialPreferences = [], onSave, isEditMode = false }) => {
    const [selected, setSelected] = useState(new Set(initialPreferences));
    const [saving, setSaving] = useState(false);
    
    useEffect(() => {
        if (initialPreferences.length > 0) {
            setSelected(new Set(initialPreferences));
        }
    }, [initialPreferences]);
    
    const toggleCategory = (id) => {
        setSelected(prev => {
            const newSet = new Set(prev);
            if (newSet.has(id)) {
                newSet.delete(id);
            } else {
                newSet.add(id);
            }
            return newSet;
        });
    };
    
    const handleSave = async () => {
        if (selected.size < 3) {
            toast.error('Selecciona al menos 3 categorías');
            return;
        }
        
        setSaving(true);
        try {
            const preferences = Array.from(selected);
            await api('/api/user/preferences', {
                method: 'POST',
                body: JSON.stringify({ food_preferences: preferences })
            });
            toast.success('Preferencias guardadas');
            onSave(preferences);
        } catch (err) {
            toast.error('Error guardando preferencias');
            console.error(err);
        } finally {
            setSaving(false);
        }
    };
    
    return (
        <div className="min-h-screen bg-bg-dark flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl shadow-xl max-w-md w-full max-h-[90vh] flex flex-col">
                {/* Header */}
                <div className="p-6 border-b flex-shrink-0">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="w-10 h-10 rounded-full bg-brand-orange/10 flex items-center justify-center">
                            <Settings className="w-5 h-5 text-brand-orange" />
                        </div>
                        <h1 className="text-xl font-bold text-gray-900">
                            {isEditMode ? 'Editar preferencias' : 'Configura tus preferencias'}
                        </h1>
                    </div>
                    <p className="text-gray-500 text-sm">
                        Selecciona las categorías de alimentos que te gustan. Las usaremos para sugerirte los últimos toques de cada comida.
                    </p>
                    {!isEditMode && (
                        <p className="text-gray-400 text-xs mt-2">
                            Puedes cambiarlas después en tu perfil.
                        </p>
                    )}
                </div>
                
                {/* Categories List */}
                <div className="flex-1 overflow-y-auto p-4">
                    <div className="space-y-1">
                        {PREFERENCE_CATEGORIES.map(cat => (
                            <label
                                key={cat.id}
                                className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all ${
                                    selected.has(cat.id) 
                                        ? 'bg-brand-orange/10 border border-brand-orange' 
                                        : 'bg-gray-50 border border-transparent hover:bg-gray-100'
                                }`}
                                onClick={() => toggleCategory(cat.id)}
                            >
                                <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${
                                    selected.has(cat.id)
                                        ? 'bg-brand-orange border-brand-orange'
                                        : 'border-gray-300'
                                }`}>
                                    {selected.has(cat.id) && <Check className="w-3 h-3 text-white" />}
                                </div>
                                <span className={`text-sm ${selected.has(cat.id) ? 'text-gray-900 font-medium' : 'text-gray-700'}`}>
                                    {cat.label}
                                </span>
                            </label>
                        ))}
                    </div>
                </div>
                
                {/* Footer */}
                <div className="p-4 border-t flex-shrink-0 bg-gray-50">
                    <p className={`text-sm mb-3 ${selected.size < 3 ? 'text-red-500' : 'text-gray-500'}`}>
                        {selected.size < 3 
                            ? `Selecciona al menos 3 categorías (${selected.size}/3)`
                            : `${selected.size} categorías seleccionadas`
                        }
                    </p>
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
