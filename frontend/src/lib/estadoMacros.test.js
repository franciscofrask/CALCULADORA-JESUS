/**
 * Los tres colores de Inicio (T1 del doc del 16-08): naranja lo que falta, amarillo lo
 * válido, verde lo cuadrado. La regla no es nueva -- es la de las tarjetas de comida --,
 * así que lo que se comprueba aquí es que se extrajo SIN cambiarla, y que el titular del
 * día solo sale cuando de verdad puede salir.
 */
import { MARGEN } from './exceso';
import {
    ESTADO, estadoMacro, estadoDelDia, faltanDe, porcentajeMacro, varianteDelDia,
} from './estadoMacros';

describe('el estado de un macro', () => {
    test('clavado es cuadrado', () => {
        expect(estadoMacro('P', 120, 120)).toBe(ESTADO.CUADRADO);
        expect(estadoMacro('H', 49.6, 50)).toBe(ESTADO.CUADRADO); // redondea a 0 de resto
    });

    test('dentro del margen es valido', () => {
        expect(estadoMacro('P', 120 - (MARGEN - 1), 120)).toBe(ESTADO.VALIDO);
        expect(estadoMacro('G', 50 - (MARGEN - 1), 50)).toBe(ESTADO.VALIDO);
    });

    test('mas lejos del margen, falta', () => {
        expect(estadoMacro('P', 26, 120)).toBe(ESTADO.FALTA);
        expect(estadoMacro('H', 0, 50)).toBe(ESTADO.FALTA);
    });

    test('pasarse de proteina no es un fallo, pasarse de hidratos si', () => {
        expect(estadoMacro('P', 160, 120)).toBe(ESTADO.CUADRADO);
        expect(estadoMacro('H', 50 + MARGEN, 50)).toBe(ESTADO.EXCESO);
    });

    test('sin objetivo no se le pone medalla a nadie', () => {
        expect(estadoMacro('P', 0, 0)).toBe(ESTADO.FALTA);
    });
});

describe('lo que falta y la barra', () => {
    test('nunca en negativo', () => {
        expect(faltanDe(94, 120)).toBe(26);
        expect(faltanDe(160, 120)).toBe(0);
    });

    test('la barra no se sale', () => {
        expect(porcentajeMacro(60, 120)).toBe(50);
        expect(porcentajeMacro(300, 120)).toBe(100);
        expect(porcentajeMacro(10, 0)).toBe(0);
    });
});

describe('el estado del dia', () => {
    const objetivos = { P: 120, H: 50, G: 50 };

    test('los tres clavados: cuadrado', () => {
        expect(estadoDelDia({ P: 120, H: 50, G: 50 }, objetivos)).toBe(ESTADO.CUADRADO);
    });

    test('uno dentro del margen y los otros clavados: valido', () => {
        expect(estadoDelDia({ P: 118, H: 50, G: 50 }, objetivos)).toBe(ESTADO.VALIDO);
    });

    test('si a uno le falta, no hay titular', () => {
        expect(estadoDelDia({ P: 26, H: 50, G: 50 }, objetivos)).toBe(null);
        expect(estadoDelDia({ P: 0, H: 0, G: 0 }, objetivos)).toBe(null);
    });

    test('pasarse de hidratos tampoco da el dia por bueno', () => {
        expect(estadoDelDia({ P: 120, H: 50 + MARGEN, G: 50 }, objetivos)).toBe(null);
    });

    test('sin objetivos no hay dia que valorar', () => {
        expect(estadoDelDia({ P: 0, H: 0, G: 0 }, { P: 0, H: 0, G: 0 })).toBe(null);
    });
});

describe('los cierres que rotan', () => {
    const tres = ['uno', 'dos', 'tres'];

    test('siempre uno de la lista y el mismo dentro del dia', () => {
        expect(tres).toContain(varianteDelDia(tres, 'cliente-1'));
        expect(varianteDelDia(tres, 'cliente-1')).toBe(varianteDelDia(tres, 'cliente-1'));
    });

    test('sin variantes no revienta', () => {
        expect(varianteDelDia([], 'x')).toBe('');
        expect(varianteDelDia(undefined, 'x')).toBe('');
    });
});
