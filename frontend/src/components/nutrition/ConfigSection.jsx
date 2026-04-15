import React from 'react';

const MOMENTO_OPTIONS = [
    { value: 0, label: 'En ayunas' },
    { value: 1, label: 'Después de Comida 1' },
    { value: 2, label: 'Después de Comida 2' },
    { value: 3, label: 'Después de Comida 3' },
];

const PERI_OPTIONS = [
    { value: 'intra_post', label: 'Intra + Post' },
    { value: 'solo_post', label: 'Solo Post' },
    { value: 'solo_intra', label: 'Solo Intra' },
    { value: 'sin_peri', label: 'Sin periworkout' },
];

const ConfigSection = ({ tipoDia, numComidas, setNumComidas, momentoEntreno, setMomentoEntreno, opcionPeri, setOpcionPeri }) => {
    const momentoOptions = numComidas === 3
        ? MOMENTO_OPTIONS.filter(o => o.value < 3)
        : MOMENTO_OPTIONS;

    return (
        <div className="bg-gray-100 rounded-xl p-3 mb-4" data-testid="config-section">
            <div className="flex items-center gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-600 font-medium">Comidas:</span>
                    <div className="flex gap-1">
                        {[3, 4].map(n => (
                            <button
                                key={n}
                                onClick={() => { setNumComidas(n); if (n === 3 && momentoEntreno > 2) setMomentoEntreno(2); }}
                                className={`w-8 h-8 rounded-full text-sm font-bold transition-all ${numComidas === n ? 'bg-brand-orange text-white shadow' : 'bg-white text-gray-600 border border-gray-300'}`}
                                data-testid={`comidas-${n}-btn`}
                            >{n}</button>
                        ))}
                    </div>
                </div>

                {tipoDia === 'entrenamiento' && (
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
