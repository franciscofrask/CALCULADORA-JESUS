/**
 * ContadorFamilia - qué pasa hoy con la proteína de un alimento que se calibra.
 *
 * Jesús, 13-08-2026: «un contador en la línea del alimento desde el primer gramo». La
 * calibración progresiva es la regla más difícil de adivinar de toda la app: la proteína de
 * unas almendras no cuenta hasta que el DÍA pasa de 20 g, y hasta entonces eso ocurría sin
 * que nada lo dijera.
 *
 * DOS CAMBIOS DEL 26-08 (puntos 133 y 134), y los dos porque el cartel mentía:
 *
 *  · ANTES DEL TRAMO HAY UNA PUERTA. La proteína del alimento tiene que llegar a un tercio
 *    del macro dominante de su bloque; si no llega, no cuenta NUNCA, comas lo que comas.
 *    El cartel no la conocía y le salía a todos los frutos secos por igual: a las nueces
 *    (23 %) les decía «te cuenta entera» y aportaban 0. «Que salga sólo en los que llegan al
 *    tercio. A los demás, una sola frase y para siempre: su proteína no te cuenta.»
 *
 *  · Y AL QUE SÍ LLEGA, DECIRLE LO QUE GANA. «Te cuenta a la mitad» suena a castigo y no
 *    dice qué hacer; ahora la frase termina en lo que pasa si sigue: «con 40 g te cuenta
 *    toda». Y sale el «25 de 40 g»: el número no era la información, era el ruido.
 *
 * Los gramos son del DÍA entero, que es lo que decide el tramo desde el 13-08. Por eso el
 * mismo alimento enseña lo mismo esté en la comida que esté.
 */
import React from 'react';

// Los tramos de la spec (17-07-2026), los mismos que aplica `calibracion_dia.py`.
const FAMILIAS = {
    fruto_seco: { tramos: [20, 40] },
    cereal_pan: { tramos: [50, 100] },
};

export const ContadorFamilia = ({ bloque, gramos, proteinaCuenta = true }) => {
    const cfg = FAMILIAS[bloque];
    if (!cfg) return null;

    // NO LLEGA AL TERCIO: una frase y para siempre. Ni tramos, ni gramos, ni barra: no hay
    // nada que recorrer porque no va a cambiar coma lo que coma. Y esto sí se dice desde el
    // primer gramo, sin esperar al acumulado del día, porque no depende de él.
    if (!proteinaCuenta) {
        return (
            <div className="mt-0.5 text-[11px] text-muted-foreground" data-testid={`contador-${bloque}`}>
                su proteína no te cuenta
            </div>
        );
    }

    if (gramos == null) return null;

    const [primero, segundo] = cfg.tramos;
    const g = Math.round(gramos);
    const meta = g <= primero ? primero : g <= segundo ? segundo : null;
    const pct = meta ? Math.min(100, Math.round((g / meta) * 100)) : 100;
    // La misma información de antes, con una acción al final.
    const frase = g > segundo
        ? 'te cuenta toda su proteína'
        : g > primero
            ? `vas por la mitad de su proteína · con ${segundo} g te cuenta toda`
            : `su proteína todavía no te cuenta · con ${primero} g te cuenta la mitad`;

    return (
        // Sin `truncate`: en 390 px la frase entera no cabe y el corte se comía el final,
        // que es justo lo que dice qué hacer. Que parta de línea.
        <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground"
             data-testid={`contador-${bloque}`}>
            <span className="inline-block w-10 h-1 rounded-full bg-muted overflow-hidden shrink-0">
                <span className="block h-full rounded-full bg-brand/70" style={{ width: `${pct}%` }} />
            </span>
            <span className="min-w-0">{frase}</span>
        </div>
    );
};

export default ContadorFamilia;
