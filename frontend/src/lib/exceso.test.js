/**
 * La regla del 13-08 de Jesús, fijada: «el rojo por arriba, solo en hidratos y grasa --
 * pasarse de proteína no». Antes vivía repetida en siete sitios de la pantalla de
 * Nutrición y no había forma de comprobarla sin abrir el navegador.
 */
import { seExcede, excesos, textoExceso, fraseExceso, MARGEN } from './exceso';

describe('pasarse de un macro', () => {
    test('pasarse de PROTEINA no es pasarse, por mucho que sea', () => {
        expect(seExcede('P', 120, 59)).toBe(false);
        expect(seExcede('P', 59.1, 59)).toBe(false);
    });

    test('pasarse de hidratos o de grasa si, a partir del margen', () => {
        expect(seExcede('H', 66 + MARGEN, 66)).toBe(true);
        expect(seExcede('G', 12 + MARGEN, 12)).toBe(true);
        // Justo por debajo del margen todavia no: es el margenValido de Calma.
        expect(seExcede('H', 66 + MARGEN - 0.1, 66)).toBe(false);
        expect(seExcede('G', 12 + MARGEN - 0.1, 12)).toBe(false);
    });

    test('quedarse corto nunca es pasarse', () => {
        expect(seExcede('H', 10, 66)).toBe(false);
        expect(seExcede('G', 0, 12)).toBe(false);
        expect(seExcede('P', 0, 59)).toBe(false);
    });

    test('en el peri la grasa no cuenta, asi que tampoco puede pasarse', () => {
        expect(seExcede('G', 40, 0, { esPeri: true })).toBe(false);
        expect(seExcede('G', 40, 0, { esPeri: false })).toBe(true);
    });

    test('el caso real medido en la app: +18 g de proteina no pinta nada', () => {
        const servido = { P: 77, H: 65, G: 11.2 };
        const objetivo = { P: 59, H: 66, G: 12 };
        expect(excesos(servido, objetivo)).toEqual([]);
        expect(fraseExceso(servido, objetivo)).toBe('');
    });
});

describe('decir POR CUANTO te pasas', () => {
    test('un solo macro, con sus gramos', () => {
        expect(fraseExceso({ P: 40, H: 66, G: 20 }, { P: 59, H: 66, G: 12 }))
            .toBe('Te pasas 8 g de grasa');
    });

    test('dos macros, con la "y" y sin la proteina de en medio', () => {
        // El caso de la comida 2 de la prueba: +29 H, +12 G y +5 P.
        expect(textoExceso({ P: 64, H: 95, G: 24 }, { P: 59, H: 66, G: 12 }))
            .toBe('29 g de hidratos y 12 g de grasa');
    });

    test('los decimales solo cuando los hay, y con coma', () => {
        expect(textoExceso({ H: 81.2, G: 12 }, { H: 66, G: 12 })).toBe('15,2 g de hidratos');
        expect(textoExceso({ H: 82, G: 12 }, { H: 66, G: 12 })).toBe('16 g de hidratos');
    });
});
