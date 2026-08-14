import React from 'react';
import BrandArrow from './BrandArrow';

// Logo de marca 12EN12 (réplica del existente). El acento (flecha) SIEMPRE es naranja.
// `tone` solo adapta el contraste del wordmark al fondo, no cambia la marca.
//
// EL TONO POR DEFECTO SIGUE AL TEMA (14-08-2026). Antes era `text-white` fijo, y la mitad de
// las pantallas donde sale el logo (el test, el cuestionario, la bienvenida, mi cuerpo, los
// planes) tienen fondo de tema: en claro eran letras blancas sobre blanco, o sea nada. Ahora
// el valor de fábrica es el color del texto de la página, que es blanco en oscuro y negro en
// claro, y sale bien sin que cada pantalla tenga que acordarse.
//
// `tone="dark"` se queda para las superficies que son negras SIEMPRE y no dependen del tema:
// la barra lateral y la cabecera del panel, la portada del test, entrar y recuperar clave.
const SIZES = { xs: 'text-lg', sm: 'text-2xl', md: 'text-3xl', lg: 'text-5xl', xl: 'text-6xl' };

const TONOS = {
    auto: 'text-foreground',    // el color del texto de la página
    dark: 'text-white',         // sobre fondo negro fijo
    light: 'text-[#0A0A0A]',    // sobre fondo claro fijo
};

// LA FLECHA MIDE LO QUE MIDEN LAS LETRAS, Y SE APOYA DONDE ELLAS.
//
// A ras por arriba y por abajo, que es como tiene que verse la marca. Son dos cosas:
//
//   1. VA DENTRO DEL RENGLÓN, no en una caja al lado. Puesta como columna de un `flex` caía
//      un par de píxeles por debajo de la línea de las letras y se veía descolgada. Como
//      parte del texto, el navegador la apoya en la misma línea que los números, exacto y a
//      cualquier tamaño.
//
//   2. MIDE 0,685em. Una mayúscula de Barlow Condensed mide 0,7075em medida a 400 px, pero a
//      los tamaños a los que se usa el logo (25,5 / 27 / 33,75 px) la letra se ajusta a
//      píxeles enteros y la flecha, que es un dibujo, no: con el valor exacto sobresalía UN
//      píxel por arriba en la barra lateral. Probados los seis valores entre 0,68 y 0,7075 a
//      los tres tamaños, 0,685 es el único que queda a ras arriba y abajo en los tres. Si
//      algún día cambia el tipo o los tamaños, se vuelve a probar: el número sale de medir,
//      no de la teoría.
const ARROW = 'text-brand inline-block align-baseline h-[0.685em] w-[0.685em] ml-[0.03em]';

const Logo12EN12 = ({ size = 'md', tone = 'auto', className = '' }) => (
    <div
        className={`font-heading font-bold tracking-tight leading-none whitespace-nowrap ${SIZES[size]} ${className}`}
        aria-label="12EN12"
    >
        <span className={TONOS[tone] || TONOS.auto}>12EN12</span><BrandArrow className={ARROW} />
    </div>
);

export default Logo12EN12;
