/**
 * Los tres colores de Inicio (T1 del doc del 16-08): naranja lo que falta, amarillo lo
 * válido, verde lo cuadrado. La regla no es nueva -- es la de las tarjetas de comida --,
 * así que lo que se comprueba aquí es que se extrajo SIN cambiarla, y que el titular del
 * día solo sale cuando de verdad puede salir.
 */
import { MARGEN } from './exceso';
import {
    ESTADO, estadoMacro, estadoDelDia, objetivoDelDia,
    faltanDe, porcentajeMacro, varianteDelDia,
} from './estadoMacros';

describe('el objetivo del dia', () => {
    test('es el que resuelve el servidor, el mismo que ve en Nutricion', () => {
        // El caso del fallo: el total del dia era 235,1 y las comidas piden 225.
        expect(objetivoDelDia({ P: 225, H: 170, G: 60 })).toEqual({ P: 225, H: 170, G: 60 });
    });

    test('SIN SEGUNDA FUENTE: si el servidor no lo dice, no hay objetivo', () => {
        // Aqui estaba el numero que bailaba: mientras no llegaba la dieta se pintaban los
        // macros crudos (190) y luego el bueno (225), en la misma pantalla y el mismo dia.
        expect(objetivoDelDia(null)).toBe(null);
        expect(objetivoDelDia(undefined)).toBe(null);
        expect(objetivoDelDia({ P: 0, H: 0, G: 0 })).toBe(null);
    });

    test('el objetivo no depende de que mas haya llegado', () => {
        // Da igual el orden en que respondan las peticiones de Inicio: el objetivo sale de
        // un solo sitio, asi que dos lecturas del mismo dia dan el mismo numero.
        const delServidor = { P: 225, H: 170, G: 60 };
        const primeraLectura = objetivoDelDia(delServidor);
        const segundaLectura = objetivoDelDia(delServidor);
        expect(primeraLectura).toEqual(segundaLectura);
        // Y no hay ningun otro argumento que lo pueda cambiar.
        expect(objetivoDelDia.length).toBe(1);
    });
});

describe('el estado de un macro', () => {
    test('clavado es cuadrado', () => {
        expect(estadoMacro('P', 120, 120)).toBe(ESTADO.CUADRADO);
        expect(estadoMacro('H', 49.6, 50)).toBe(ESTADO.CUADRADO); // redondea a 0 de resto
    });

    // «Si está dentro del margen, cuadra» (Francisco, 17-08). Antes esto era un segundo
    // escalón, «válido», y Nutrición ya lo había quitado ese mismo día: la misma comida
    // salía cuadrada allí y «válida» en Inicio.
    test('dentro del margen tambien cuadra', () => {
        expect(estadoMacro('P', 120 - (MARGEN - 1), 120)).toBe(ESTADO.CUADRADO);
        expect(estadoMacro('G', 50 - (MARGEN - 1), 50)).toBe(ESTADO.CUADRADO);
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

    test('uno dentro del margen y los otros clavados: tambien cuadrado', () => {
        expect(estadoDelDia({ P: 118, H: 50, G: 50 }, objetivos)).toBe(ESTADO.CUADRADO);
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
