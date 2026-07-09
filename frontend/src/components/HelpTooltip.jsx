import React, { useState, useEffect, useRef } from 'react';
import { HelpCircle } from 'lucide-react';

// Icono "?" con un globo de ayuda. Se muestra al pasar el ratón por encima y
// también al hacer clic (para pantallas táctiles). Se cierra al hacer clic fuera.
const HelpTooltip = ({ text, className = '' }) => {
    const [open, setOpen] = useState(false);
    const [hover, setHover] = useState(false);
    const ref = useRef(null);

    useEffect(() => {
        if (!open) return;
        const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
        document.addEventListener('mousedown', onDoc);
        return () => document.removeEventListener('mousedown', onDoc);
    }, [open]);

    const visible = open || hover;

    return (
        <span ref={ref} className={`relative inline-flex ${className}`}>
            <button
                type="button"
                aria-label="Ayuda"
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(o => !o); }}
                onMouseEnter={() => setHover(true)}
                onMouseLeave={() => setHover(false)}
                className="text-muted-foreground hover:text-brand-orange focus:outline-none"
            >
                <HelpCircle className="w-3.5 h-3.5" />
            </button>
            {visible && (
                <span
                    role="tooltip"
                    className="absolute left-1/2 bottom-full mb-1.5 -translate-x-1/2 z-50 w-56 rounded-lg bg-[#111] text-white text-xs leading-snug p-2 shadow-lg border border-[#333]"
                >
                    {text}
                    <span className="absolute left-1/2 top-full -translate-x-1/2 -mt-px border-4 border-transparent border-t-[#111]" />
                </span>
            )}
        </span>
    );
};

export default HelpTooltip;
