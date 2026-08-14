import React from 'react';

// Flecha de marca JG (↗), réplica del SVG de Calma (logo / apple-touch-icon).
// El color se controla con la clase de texto (fill: currentColor).
//
// EL DIBUJO LLENA SU CAJA (14-08-2026). El recuadro traía 18 unidades de aire por cada lado
// ("-18 -18 136 136" para un trazo de 100x100), y ese aire de abajo era el que hacía que la
// flecha del logo se quedara colgando por encima del suelo de las letras: por mucho que se
// alineara la caja, dentro seguía sobrando un 13 % de hueco. Sin aire, el borde de la caja ES
// el borde de la flecha y ya se puede apoyar donde toque.
const BrandArrow = ({ className = '' }) => (
    <svg viewBox="0 0 100 100" className={className} fill="currentColor" aria-hidden="true">
        <path d="M0 0 H100 V100 H77 V50 L36 96 H3 L58 28 H0 Z" />
    </svg>
);

export default BrandArrow;
