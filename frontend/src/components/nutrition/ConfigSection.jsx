import React from 'react';

const MOMENTO_OPTIONS = [
    { value: 0, label: 'En ayunas' },
    { value: 1, label: 'Después de Comida 1' },
    { value: 2, label: 'Después de Comida 2' },
    { value: 3, label: 'Después de Comida 3' },
];

// Calma's peri model = a boolean `quiereIntraentrenamiento`: post is ALWAYS present, intra is
// optional. So only two states. `solo_intra` and `sin_peri` did not exist in Calma — removed.
const PERI_OPTIONS = [
    { value: 'intra_post', label: 'Intra + Post' },
    { value: 'solo_post', label: 'Solo Post' },
];

const ConfigSection = ({ tipoDia, momentoEntreno, setMomentoEntreno, opcionPeri, setOpcionPeri, singleMeal = false }) => {
    // Calma's diet is fixed at 4 meals (its z/J/W reparto tables are 4-meal). The 3-meal
    // option (equitable 33%) had no Calma equivalent, so it was removed — meals are always 4.
    const momentoOptions = MOMENTO_OPTIONS;

    return (
        <div className="bg-gray-100 rounded-xl p-3 mb-4" data-testid="config-section">
            <div className="flex items-center gap-3 flex-wrap">
                {tipoDia === 'entrenamiento' && !singleMeal && (
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-600 font-medium">Entrenas:</span>
                        <select value={momentoEntreno} onChange={(e) => setMomentoEntreno(Number(e.target.value))}
                            className="text-xs bg-white border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-orange"
                            data-testid="momento-entreno-select"
                        >
                            {momentoOptions.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                        </select>
                    </div>
                )}

                {tipoDia === 'entrenamiento' && (
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-600 font-medium">Peri:</span>
                        <select value={opcionPeri} onChange={(e) => setOpcionPeri(e.target.value)}
                            className="text-xs bg-white border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-orange"
                            data-testid="peri-select"
                        >
                            {PERI_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                        </select>
                    </div>
                )}
            </div>
        </div>
    );
};

export { MOMENTO_OPTIONS, PERI_OPTIONS };
export default ConfigSection;
