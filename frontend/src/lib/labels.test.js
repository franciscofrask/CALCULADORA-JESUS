/**
 * El concepto de un cobro, tal y como lo lee quien mira la pantalla de Cobros.
 *
 * Llega de la pasarela y en inglés: «1 x El Lunes Empiezo (at €81.07 / month)» (punto 64
 * del informe de Jesús). Se traducía solo cuando el ciclo era UNA palabra, y en producción
 * la mayoría no lo son: 435 filas con «every 12 weeks» -- que es el ciclo natural del
 * método, doce semanas --, 34 con «every 4 weeks», 15 con «every 3 months» y una con
 * «every 48 weeks». O sea que fallaba justo en el caso más común (QA del 15-08).
 */
import { conceptoDeCobro } from './labels';

describe('el concepto de un cobro', () => {
    test('quita el «1 x», que no dice nada, y conserva las cantidades de verdad', () => {
        expect(conceptoDeCobro('1 x El Lunes Empiezo')).toBe('El Lunes Empiezo');
        expect(conceptoDeCobro('2 × Nivel 2')).toBe('2 × Nivel 2');
    });

    test('los ciclos de una palabra, como siempre', () => {
        expect(conceptoDeCobro('1 x El Lunes Empiezo (at €81.07 / month)'))
            .toBe('El Lunes Empiezo (81,07 € al mes)');
        expect(conceptoDeCobro('2 × Nivel 2 (at 150.00 EUR / year)'))
            .toBe('2 × Nivel 2 (150,00 € al año)');
    });

    test('y los contados, que son la mayoría', () => {
        expect(conceptoDeCobro('1 × Reto 12 en 12 (at €297.00 / every 12 weeks)'))
            .toBe('Reto 12 en 12 (297,00 € cada 12 semanas)');
        expect(conceptoDeCobro('1 × Reto 12 en 12 (at €167.00 / every 4 weeks)'))
            .toBe('Reto 12 en 12 (167,00 € cada 4 semanas)');
        expect(conceptoDeCobro('1 × Nivel 2 (at 150.00 EUR / every 3 months)'))
            .toBe('Nivel 2 (150,00 € cada 3 meses)');
    });

    test('«every 1 week» se dice «cada semana», no «cada 1 semanas»', () => {
        expect(conceptoDeCobro('1 × Algo (at €10.00 / every 1 week)'))
            .toBe('Algo (10,00 € cada semana)');
    });

    test('lo que no reconoce lo deja tal cual: mejor raro que recortado', () => {
        expect(conceptoDeCobro('1 × Cosa (at €5.00 / fortnight)'))
            .toBe('Cosa (at €5.00 / fortnight)');
    });

    test('sin concepto, un guion', () => {
        expect(conceptoDeCobro('')).toBe('-');
        expect(conceptoDeCobro(null)).toBe('-');
    });
});
