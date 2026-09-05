/**
 * La basura del import no se pinta (punto 104 del artefacto «La app, pantalla por
 * pantalla», 4-09): Gonzalo seguía viendo «XX» como todo el último reporte de Montalvo.
 */
import { sinElRelleno, notaDelCliente, RELLENO_DEL_IMPORT } from './rellenoDelImport';

describe('el relleno del volcado de Calma', () => {
    test('las marcas del formulario viejo no son una respuesta', () => {
        for (const basura of ['XX', 'xx', 'xxx', 'x', '-', '--', '_', '.', '...', 'n/a', 'N/A', 'na',
            'nada', 'Nada', 'ninguno', 'Ninguna', 'null', 'none', '', '   ', null, undefined]) {
            expect(sinElRelleno(basura)).toBeNull();
        }
    });

    test('lo que escribió el cliente se queda tal cual', () => {
        expect(sinElRelleno('Mi compromiso es máximo')).toBe('Mi compromiso es máximo');
        expect(sinElRelleno('No tengo ninguna')).toBe('No tengo ninguna');
        expect(sinElRelleno('  con espacios  ')).toBe('con espacios');
        // Una palabra que EMPIEZA por x no es relleno.
        expect(sinElRelleno('Xavi me ayuda')).toBe('Xavi me ayuda');
    });

    test('«Sin calificar cumplimiento» se quita por delante y se queda lo que venga detrás', () => {
        expect(sinElRelleno('Sin calificar cumplimiento')).toBeNull();
        expect(sinElRelleno('Sin calificar el cumplimiento.')).toBeNull();
        expect(sinElRelleno('Sin calificar cumplimiento. Este mes lo haré 100 %')).toBe('Este mes lo haré 100 %');
        // Si detrás solo queda relleno, tampoco.
        expect(sinElRelleno('Sin calificar cumplimiento, xx')).toBeNull();
    });

    test('la nota del reporte: ni la marca de la migración ni el relleno', () => {
        expect(notaDelCliente({ notes: 'Importado de Calma' })).toBeNull();
        expect(notaDelCliente({ notes: 'XX' })).toBeNull();
        expect(notaDelCliente({ notes: null })).toBeNull();
        expect(notaDelCliente({})).toBeNull();
        expect(notaDelCliente(null)).toBeNull();
        expect(notaDelCliente({ notes: 'Este mes con poca energía' })).toBe('Este mes con poca energía');
    });

    test('la regla es una sola y se exporta para quien la necesite', () => {
        expect(RELLENO_DEL_IMPORT.test('XX')).toBe(true);
        expect(RELLENO_DEL_IMPORT.test('bien')).toBe(false);
    });
});
