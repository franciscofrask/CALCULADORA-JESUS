import React from 'react';

// Flecha de marca JG (↗), réplica del SVG de Calma (logo / apple-touch-icon).
// El color se controla con la clase de texto (fill: currentColor).
const BrandArrow = ({ className = '' }) => (
    <svg viewBox="-18 -18 136 136" className={className} fill="currentColor" aria-hidden="true">
        <path d="M0 0 H100 V100 H77 V50 L36 96 H3 L58 28 H0 Z" />
    </svg>
);

export default BrandArrow;
