import { leerMacro } from './estadoDelMacro';

// «CONTRA QUÉ SE MIDE, SIEMPRE» (Francisco, 3-09, con la maqueta del bloque 06 delante:
// «250 / de 250 / ya lo tienes» y «212 / de 210 / cuadrado (+2)»). Son dos líneas debajo
// del número: arriba el objetivo y abajo el estado. Antes se turnaban en la misma línea,
// así que el objetivo desaparecía justo cuando el estado tenía algo que decir.
describe('el «de N», que se ve pase lo que pase', () => {
    it('en Llevas sale aunque el macro ya esté cubierto', () => {
        const r = leerMacro({ vista: 'llevas', hay: 250, objetivo: 250 });
        expect(r.referencia).toBe('de 250');
        expect(r.palabra).toBe('ya lo tienes');
    });

    it('en Llevas, yendo por debajo, sale el objetivo y NADA más', () => {
        // Es «AL EMPEZAR» de su maqueta: «0 / de 250», sin palabra. Ir por debajo a media
        // mañana no es un estado que haya que nombrar.
        const r = leerMacro({ vista: 'llevas', hay: 0, objetivo: 250 });
        expect(r.referencia).toBe('de 250');
        expect(r.palabra).toBeNull();
    });

    it('en Llevas, pasándose, salen los dos', () => {
        const r = leerMacro({ vista: 'llevas', hay: 71, objetivo: 60 });
        expect(r.referencia).toBe('de 60');
        expect(r.palabra).toBe('te pasas 11');
    });

    it('en Dieta también van los dos: «de 250» y «faltan 50»', () => {
        const r = leerMacro({ vista: 'dieta', hay: 200, objetivo: 250 });
        expect(r.referencia).toBe('de 250');
        expect(r.palabra).toBe('faltan 50');
    });

    it('en Macros NO: ahí el número YA es el objetivo', () => {
        const r = leerMacro({ vista: 'macros', hay: 250, objetivo: 250 });
        expect(r.referencia).toBeNull();
        expect(r.palabra).toBe('tu objetivo');
    });

    it('y en Falta tampoco: ahí el número es lo que queda', () => {
        const r = leerMacro({ vista: 'falta', hay: 151, objetivo: 250 });
        expect(r.referencia).toBeNull();
        expect(r.palabra).toBe('para llegar');
    });
});

// La decisión del 3-09 sobre las palabras, que no cambia con lo de arriba.
describe('cuadrado es el exacto; dentro del margen, válido', () => {
    it('exacto', () => {
        expect(leerMacro({ vista: 'dieta', hay: 250, objetivo: 250 }).palabra).toBe('cuadrado');
    });
    it('dentro de los 4 g', () => {
        expect(leerMacro({ vista: 'dieta', hay: 252, objetivo: 250 }).palabra).toBe('válido (+2)');
        expect(leerMacro({ vista: 'dieta', hay: 246, objetivo: 250 }).palabra).toBe('válido (−4)');
    });
    it('y fuera, lo que falta o lo que sobra', () => {
        expect(leerMacro({ vista: 'dieta', hay: 245, objetivo: 250 }).palabra).toBe('faltan 5');
        expect(leerMacro({ vista: 'dieta', hay: 255, objetivo: 250 }).palabra).toBe('sobran 5');
    });
});

// UNA SOLA REGLA DE REDONDEO (Francisco, 3-09: «que muestre también en el global, así no hay
// desfase, tal cual lo hace Calma»). El día iba en enteros y la comida a la décima, así que la
// misma comida decía «16G» en la fila de Inicio, «15,7» abierta y «válido +1» plegada.
describe('la décima, también en el global', () => {
    it('el número que se lee lleva su decimal', () => {
        const r = leerMacro({ vista: 'dieta', hay: 245.4, objetivo: 250 });
        expect(r.palabra).toBe('faltan 4,6');
        expect(r.referencia).toBe('de 250');
    });

    it('y la referencia también, cuando el objetivo lo tiene', () => {
        expect(leerMacro({ vista: 'llevas', hay: 0, objetivo: 200.9 }).referencia).toBe('de 200,9');
    });

    it('el desvío se cuenta contra lo que se ve, no contra el entero', () => {
        // Lo que hacía saltar el desfase: 193,4 de 200,9 son 7,5, no 8 ni 7.
        expect(leerMacro({ vista: 'dieta', hay: 193.4, objetivo: 200.9 }).palabra).toBe('faltan 7,5');
    });

    it('«cuadrado» es el medio gramo de Calma, no el gramo', () => {
        // `Math.round(objetivo − servido) == 0` en su bundle. Con el suelo viejo de 1 g, 0,7
        // salía «cuadrado» debajo de un «249,3 de 250» que se ve que no lo está.
        expect(leerMacro({ vista: 'dieta', hay: 249.7, objetivo: 250 }).palabra).toBe('cuadrado');
        expect(leerMacro({ vista: 'dieta', hay: 249.3, objetivo: 250 }).palabra).toBe('válido (−0,7)');
    });

    it('y el margen sigue siendo 4, inclusivo', () => {
        expect(leerMacro({ vista: 'dieta', hay: 254, objetivo: 250 }).palabra).toBe('válido (+4)');
        expect(leerMacro({ vista: 'dieta', hay: 254.1, objetivo: 250 }).palabra).toBe('sobran 4,1');
    });
});
