import React from 'react';

const MOMENTO_OPTIONS = [
    { value: 0, label: 'En ayunas' },
    { value: 1, label: 'Después de Comida 1' },
    { value: 2, label: 'Después de Comida 2' },
    { value: 3, label: 'Después de Comida 3' },
];

// Peri options. 4 modos oficiales: intra_post/solo_post (base Calma) + solo_intra/sin_peri (propios).
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

const selectCls = "w-full h-11 text-sm text-foreground bg-card border border-border rounded-xl px-3 focus:outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 transition-all";
const labelCls = "text-[11px] font-bold text-muted-foreground uppercase tracking-wider mb-2";

const Field = ({ label, children, className = '' }) => (
    <label className={`flex flex-col ${className}`}>
        <span className={labelCls}>{label}</span>
        {children}
    </label>
);

// inline=true: renderiza solo los campos (Fragment) para colocarlos en una barra horizontal
// superior; inline=false: tarjeta vertical "Configuración del día" (layout lateral/móvil).
const ConfigSection = ({ tipoDia, momentoEntreno, setMomentoEntreno, opcionPeri, setOpcionPeri, numComidas = 4, setNumComidas, inline = false }) => {
    const single = numComidas === 1;
    const entreno = tipoDia === 'entrenamiento';

    const fields = (
        <>
            <Field label="Número de comidas" className={inline ? 'w-full sm:flex-1 sm:min-w-0' : ''}>
                <select value={numComidas} onChange={(e) => setNumComidas(Number(e.target.value))}
                    className={selectCls} data-testid="num-comidas-select">
                    {COMIDAS_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
            </Field>

            {entreno && !single && (
                <Field label="Horario de entreno" className={inline ? 'w-full sm:flex-1 sm:min-w-0' : ''}>
                    <select value={momentoEntreno} onChange={(e) => setMomentoEntreno(Number(e.target.value))}
                        className={selectCls} data-testid="momento-entreno-select">
                        {MOMENTO_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                    </select>
                </Field>
            )}

            {entreno && !single && (
                <Field label="Perientreno" className={inline ? 'w-full sm:flex-1 sm:min-w-0' : ''}>
                    <select value={opcionPeri} onChange={(e) => setOpcionPeri(e.target.value)}
                        className={selectCls} data-testid="peri-select">
                        {PERI_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                    </select>
                </Field>
            )}
        </>
    );

    if (inline) return fields;

    return (
        <div className="surface p-5 space-y-4" data-testid="config-section">
            <p className="caption">Configuración del día</p>
            {fields}
        </div>
    );
};

export { MOMENTO_OPTIONS, PERI_OPTIONS };
export default ConfigSection;
