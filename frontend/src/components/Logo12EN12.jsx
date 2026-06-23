import React from 'react';
import BrandArrow from './BrandArrow';

// Logo de marca 12EN12 (réplica del existente). El acento (flecha) SIEMPRE es naranja.
// `tone` solo adapta el contraste del wordmark al fondo (claro/oscuro), no cambia la marca.
const SIZES = { xs: 'text-lg', sm: 'text-2xl', md: 'text-3xl', lg: 'text-5xl', xl: 'text-6xl' };

const Logo12EN12 = ({ size = 'md', tone = 'dark', className = '' }) => {
    const word = tone === 'light' ? 'text-[#0A0A0A]' : 'text-white';
    return (
        <div
            className={`flex items-center font-heading font-bold tracking-tight leading-none ${SIZES[size]} ${className}`}
            aria-label="12EN12"
        >
            <span className={word}>12EN12</span>
            <BrandArrow className="text-brand h-[0.85em] w-[0.85em] -ml-0.5" />
        </div>
    );
};

export default Logo12EN12;
