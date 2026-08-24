/**
 * La hora de España en el front (doc del 16-08, regla 1). Lo que se comprueba es lo que
 * de verdad se rompe: que el día del cliente no lo decida UTC ni la zona del aparato, y
 * que «ayer, 21:40» diga ayer.
 */
import {
    aFecha, diaEnEspana, horaEnEspana, hoyEnEspana, diasDesdeHoy, etiquetaMomento, textoPlazo,
} from './horaEspana';

describe('el dia y la hora del cliente', () => {
    test('a las 23:30 de Madrid, en UTC ya es manana: manda Madrid', () => {
        // 2026-08-16T21:30Z = 23:30 del 16 en Madrid (verano, +2).
        expect(diaEnEspana(aFecha('2026-08-16T21:30:00Z'))).toBe('2026-08-16');
        expect(horaEnEspana(aFecha('2026-08-16T21:30:00Z'))).toBe('23:30');
        // Y media hora despues ya es el 17 para los dos.
        expect(diaEnEspana(aFecha('2026-08-16T22:30:00Z'))).toBe('2026-08-17');
    });

    test('en invierno el desfase es de una hora, no de dos', () => {
        expect(horaEnEspana(aFecha('2026-01-15T21:30:00Z'))).toBe('22:30');
    });

    test('un ISO sin zona se toma como UTC, que es como escribe el backend', () => {
        expect(horaEnEspana(aFecha('2026-08-16T16:18:02.251468'))).toBe('18:18');
    });

    test('lo que no se entiende no revienta', () => {
        expect(aFecha(null)).toBe(null);
        expect(aFecha('vete a saber')).toBe(null);
        expect(etiquetaMomento(null)).toBe('');
        expect(textoPlazo('')).toBe(null);
    });
});

describe('el ultimo registro', () => {
    const mediodiaDe = (dia) => `${dia}T10:00:00Z`;
    const diaMas = (dia, n) => new Date(Date.parse(`${dia}T00:00:00Z`) + n * 86400000)
        .toISOString().slice(0, 10);

    test('hoy, ayer y una fecha de antes', () => {
        const hoy = hoyEnEspana();
        expect(etiquetaMomento(mediodiaDe(hoy))).toMatch(/^hoy, \d{2}:\d{2}$/);
        expect(etiquetaMomento(mediodiaDe(diaMas(hoy, -1)))).toMatch(/^ayer, \d{2}:\d{2}$/);
        expect(etiquetaMomento(mediodiaDe(diaMas(hoy, -5)))).toMatch(/^\d{1,2} de \w+, \d{2}:\d{2}$/);
    });

    test('los dias se cuentan por el calendario, no por horas', () => {
        expect(diasDesdeHoy(hoyEnEspana())).toBe(0);
        expect(diasDesdeHoy(diaMas(hoyEnEspana(), -2))).toBe(2);
    });
});

describe('el plazo del reporte', () => {
    test('dice el dia, la hora y lo que queda; con la de Espana entre parentesis si el reloj es otro', () => {
        // Doc 21-08: el plazo se fija en Espana y se enseña en la hora del navegador. Si
        // el reloj de la maquina de test es el de Espana, sale sin coletilla; si es otro,
        // con «(HH:MM h España)». Este test acepta las dos formas porque no controla el
        // huso del ejecutor; las ramas exactas se prueban abajo con horas fijas.
        const dentroDeDosDias = new Date(Date.now() + 2 * 86400000).toISOString();
        const plazo = textoPlazo(dentroDeDosDias);
        expect(plazo.pasado).toBe(false);
        // EL NOMBRE DEL DIA LLEVA TILDE dos veces por semana. Aqui ponia `\w+`, que sin la
        // bandera `u` no casa con la «e» de «miercoles» ni con la «a» de «sabado», asi que
        // este test se ponia rojo solo los dias en que el plazo caia en uno de esos dos y
        // parecia una regresion del codigo. Con `[^\s]+` da igual el dia que sea.
        expect(plazo.texto).toMatch(
            /^Hasta el [^\s]+ \d{1,2} a las \d{2}:\d{2}( \(\d{2}:\d{2} h España\))? · te quedan? \d+ días?$/);
    });

    test('con el reloj del navegador fuera de Espana, la hora local y la de Espana', () => {
        // La rama del parentesis solo puede comprobarse de verdad si el huso del ejecutor
        // no es el de España; en un ejecutor en hora de España se comprueba la contraria.
        const plazo = textoPlazo('2026-08-22T08:00:00Z');    // sabado 10:00 de Madrid
        const husoLocal = new Intl.DateTimeFormat('es-ES', {
            hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
        }).format(new Date('2026-08-22T08:00:00Z'));
        if (husoLocal === '10:00') {
            expect(plazo.texto).toContain('a las 10:00');
            expect(plazo.texto).not.toContain('h España');
        } else {
            expect(plazo.texto).toContain(`a las ${husoLocal} (10:00 h España)`);
        }
    });

    test('pasada la hora, se sabe: es lo que hace desaparecer la linea', () => {
        const plazo = textoPlazo(new Date(Date.now() - 3600000).toISOString());
        expect(plazo.pasado).toBe(true);
        expect(plazo.texto).not.toContain('te quedan');
    });
});
