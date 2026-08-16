/**
 * Al usuario, una frase; nunca un objeto.
 *
 * Esto existe por una pantalla en blanco: el cliente terminaba el cuestionario del alta,
 * pulsaba «Calcular mis macros» y se quedaba mirando una traza de React. El servidor había
 * rechazado un dato y `detail` no era una cadena, era la lista de errores de validación.
 */
import { mensajeDeError } from './mensajeDeError';

describe('mensajeDeError', () => {
    test('un detalle de toda la vida se dice tal cual', () => {
        const e = { response: { data: { detail: 'Tu plan no incluye esta función.' } } };
        expect(mensajeDeError(e)).toBe('Tu plan no incluye esta función.');
    });

    test('LA LISTA DE VALIDACIÓN NO SE PINTA: se dice qué campo falla', () => {
        const e = { response: { data: { detail: [
            { type: 'string_type', loc: ['body', 'deporte_cual'], msg: 'Input should be a valid string', input: 3 },
        ] } } };
        const texto = mensajeDeError(e);
        expect(typeof texto).toBe('string');
        expect(texto).toContain('deporte_cual');
        expect(texto).not.toContain('string_type');   // nada técnico
    });

    test('una lista rara tampoco rompe: cae en el texto de siempre', () => {
        const e = { response: { data: { detail: [{ algo: 'raro' }] } } };
        expect(mensajeDeError(e, 'No se pudo guardar')).toBe('No se pudo guardar');
    });

    test('un objeto suelto tampoco se pinta', () => {
        const e = { response: { data: { detail: { msg: 'Falta el peso' } } } };
        expect(mensajeDeError(e)).toBe('Falta el peso');
    });

    test('sin respuesta del servidor se habla de la conexión, no del código', () => {
        const e = { request: {}, message: 'Network Error' };
        expect(mensajeDeError(e)).toMatch(/conexión/i);
    });

    test('sin nada, el texto que le pase quien llama', () => {
        expect(mensajeDeError(undefined, 'No hemos podido leer tu dieta'))
            .toBe('No hemos podido leer tu dieta');
    });

    test('devuelve SIEMPRE una cadena, le eches lo que le eches', () => {
        for (const raro of [null, 0, 'texto', [], {}, { response: {} },
                            { response: { data: {} } }, new Error('boom')]) {
            expect(typeof mensajeDeError(raro)).toBe('string');
        }
    });
});
