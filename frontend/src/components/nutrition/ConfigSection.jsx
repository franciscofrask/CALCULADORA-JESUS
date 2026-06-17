import React from 'react';

const MOMENTO_OPTIONS = [
    { value: 0, label: 'En ayunas' },
    { value: 1, label: 'Después de Comida 1' },
    { value: 2, label: 'Después de Comida 2' },
    { value: 3, label: 'Después de Comida 3' },
];

// Peri options. intra_post/solo_post = Calma. Added (custom): solo_intra (intra = 5% de cada
// macro del día, resto equitativo entre comidas) y sin_peri (sin intra/post; el peri se reparte
// entre las comidas).
const PERI_OPTIONS = [
    { value: 'intra_post', label: 'Intra + Post' },
    { value: 'solo_post', label: 'Solo Post' },
    { value: 'solo_intra', label: 'Solo Intra' },
    { value: 'sin_peri', label: 'Sin peri' },
];

const COMIDAS_OPTIONS = [
    { value: 1, label: 'Comida única' },
    { value: 3, label: '3 comidas' },
    { value: 4, label: '4 comidas' },
];

const selectCls = "w-full text-sm text-gray-900 [color-scheme:light] bg-white border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-orange";
const labelCls = "text-xs font-medium text-gray-500 mb-1";

const Field = ({ label, grow, children }) => (
    <label className={`flex flex-col ${grow ? 'flex-1 min-w-0' : 'w-44'}`}>
        <span className={labelCls}>{label}</span>
        {children}
    </label>
);

const ConfigSection = ({ tipoDia, momentoEntreno, setMomentoEntreno, opcionPeri, setOpcionPeri, numComidas = 4, setNumComidas }) => {
    const single = numComidas === 1;
    const entreno = tipoDia === 'entrenamiento';
    const soloComidas = !entreno || single; // Horario/Peri ocultos → solo queda Comidas

    return (
        <div className="bg-white shadow-md rounded-2xl p-4 mb-4" data-testid="config-section">
            <div className={`flex flex-wrap gap-3 ${soloComidas ? 'justify-center' : ''}`}>
                {entreno && !single && (
                    <Field label="Horario de entreno" grow>
                        <select value={momentoEntreno} onChange={(e) => setMomentoEntreno(Number(e.target.value))}
                            className={selectCls} data-testid="momento-entreno-select"
                        >
                            {MOMENTO_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                        </select>
                    </Field>
                )}

                {entreno && !single && (
                    <Field label="Peri" grow>
                        <select value={opcionPeri} onChange={(e) => setOpcionPeri(e.target.value)}
                            className={selectCls} data-testid="peri-select"
                        >
                            {PERI_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                        </select>
                    </Field>
                )}

                <Field label="Comidas" grow={!soloComidas}>
                    <select value={numComidas} onChange={(e) => setNumComidas(Number(e.target.value))}
                        className={selectCls} data-testid="num-comidas-select"
                    >
                        {COMIDAS_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                    </select>
                </Field>
            </div>
        </div>
    );
};

export { MOMENTO_OPTIONS, PERI_OPTIONS };
export default ConfigSection;
