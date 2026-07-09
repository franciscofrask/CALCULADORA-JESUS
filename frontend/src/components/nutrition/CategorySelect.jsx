import React from 'react';
import { X } from 'lucide-react';
import { CATEGORIA_NOMBRES, descripcionCategoria } from './calmaCategorias';

// Preparación = código solo con letras (GEN, FRE, LAT...); el resto son categorías numéricas.
const isPrep = (c) => /^[A-Za-z]+$/.test(c);
const depth = (c) => c.split('.').length - 1;

// Orden natural por segmentos numéricos (1 < 2 < 2.1 < 2.2 < 10), preparaciones al final.
const cmpCode = (a, b) => {
    const pa = a.split('.').map(Number);
    const pb = b.split('.').map(Number);
    for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
        const x = Number.isFinite(pa[i]) ? pa[i] : -1;
        const y = Number.isFinite(pb[i]) ? pb[i] : -1;
        if (x !== y) return x - y;
    }
    return 0;
};

// Opciones del desplegable: "código · nombre", con sangría según la profundidad.
const CODE_OPTIONS = (() => {
    const keys = [...CATEGORIA_NOMBRES.keys()];
    const numeric = keys.filter(k => !isPrep(k)).sort(cmpCode);
    const preps = keys.filter(isPrep).sort();
    const mk = (code) => ({
        code,
        label: `${'  '.repeat(depth(code))}${code} · ${CATEGORIA_NOMBRES.get(code)}`,
    });
    return [...numeric.map(mk), ...preps.map(mk)];
})();

const toArr = (value) => String(value || '').split('|').map(s => s.trim()).filter(Boolean);
const toStr = (arr) => arr.join('|');

// Selector en cascada de categorías: cada seleccionada añade otro desplegable para
// asignar más. `value` es una cadena "2.2|FRE"; `onChange` recibe la cadena actualizada.
const CategorySelect = ({ value, onChange }) => {
    const cats = toArr(value);

    const setAt = (idx, code) => {
        const next = [...cats];
        if (idx < cats.length) {
            if (code) next[idx] = code; else next.splice(idx, 1);
        } else if (code) {
            next.push(code);
        }
        onChange(toStr(next));
    };

    const remove = (code) => onChange(toStr(cats.filter(c => c !== code)));

    return (
        <div className="space-y-2">
            {/* Categorías ya asignadas (chips con nombre legible) */}
            {cats.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                    {cats.map(code => (
                        <span key={code} className="inline-flex items-center gap-1 bg-[#FF671F]/15 text-[#FF671F] border border-[#FF671F]/30 text-xs rounded-full pl-2 pr-1 py-0.5">
                            <span className="font-medium">{code}</span>
                            <span className="text-white/60">· {descripcionCategoria(code) || 'categoría'}</span>
                            <button type="button" onClick={() => remove(code)} className="hover:text-red-400">
                                <X className="w-3 h-3" />
                            </button>
                        </span>
                    ))}
                </div>
            )}

            {/* Un desplegable por categoría asignada + uno vacío para añadir otra */}
            {[...cats, ''].map((sel, idx) => {
                const otras = cats.filter((_, i) => i !== idx);
                const opciones = CODE_OPTIONS.filter(o => !otras.includes(o.code));
                return (
                    <select
                        key={idx}
                        value={sel}
                        onChange={e => setAt(idx, e.target.value)}
                        className="w-full bg-[#0A0A0A] border border-[#222] text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#FF671F]/40"
                    >
                        <option value="">
                            {idx === 0 ? 'Selecciona una categoría' : (sel ? 'Quitar esta categoría' : 'Añadir otra categoría')}
                        </option>
                        {opciones.map(o => (
                            <option key={o.code} value={o.code}>{o.label}</option>
                        ))}
                    </select>
                );
            })}
        </div>
    );
};

export default CategorySelect;
