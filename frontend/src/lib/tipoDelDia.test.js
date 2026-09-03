import { tipoPorDefecto } from './tipoDelDia';

// «Los días sábado y domingo por defecto son de descanso» (Francisco, 3-09-2026).
// Una semana entera, del lunes 31 de agosto al domingo 6 de septiembre de 2026.
describe('el tipo con el que abre un día que nadie ha configurado', () => {
    it('el sábado y el domingo abren en descanso', () => {
        expect(tipoPorDefecto('2026-09-05')).toBe('descanso');
        expect(tipoPorDefecto('2026-09-06')).toBe('descanso');
    });

    it('de lunes a viernes siguen abriendo en entreno', () => {
        ['2026-08-31', '2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04']
            .forEach((d) => expect(tipoPorDefecto(d)).toBe('entrenamiento'));
    });

    it('LA FECHA SE LEE EN LOCAL, NO EN UTC', () => {
        // `new Date('2026-09-05')` se lee como UTC y en un huso por detrás de Greenwich
        // devuelve el viernes: el sábado abriría en entreno. Este ordenador está en UTC-3,
        // así que este caso lo caza de verdad.
        expect(new Date('2026-09-05').getDay()).not.toBe(6);   // la trampa, por escrito
        expect(tipoPorDefecto('2026-09-05')).toBe('descanso');  // y la regla, bien
    });

    it('con una fecha rota se queda como estaba, que un dato raro no cambia dietas', () => {
        [null, undefined, '', 'mañana', '2026-13', 12345]
            .forEach((d) => expect(tipoPorDefecto(d)).toBe('entrenamiento'));
    });
});
