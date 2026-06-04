import React from 'react';
import { Calculator } from 'lucide-react';

const MacroCalculatorClientPage = () => {
    return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-6">
            <div className="w-16 h-16 rounded-full bg-orange-100 flex items-center justify-center">
                <Calculator className="w-8 h-8 text-brand-orange" />
            </div>
            <h2 className="text-xl font-bold text-gray-800">Calculadora de Macros</h2>
            <p className="text-gray-500 text-sm max-w-xs">
                Calcula tus macros personalizados según el método JG. Próximamente disponible.
            </p>
        </div>
    );
};

export default MacroCalculatorClientPage;
