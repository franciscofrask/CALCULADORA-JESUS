/**
 * QUÉ SUPLEMENTO VA CON CADA COMIDA (punto 174 del 27-08, y la maqueta de la parte 6).
 *
 * «+ Creatina debajo de los macros de la comida 3. + Omega 3 · NAC en la 4.»
 *
 * SÓLO EL NOMBRE, NUNCA LA DOSIS. Jesús lo dice tres veces en el vídeo del 27-08: «que salga
 * creatina, no la dosis, sino el nombre». La dosis y el momento viven en su pantalla, que es
 * donde se leen enteros; aquí lo que hace falta es acordarse de tomárselo.
 *
 * EL INTRA Y EL POST NO LLEVAN NADA DEBAJO: «ellos son el suplemento, y ponerles otro debajo
 * confunde». Por eso `en_comidas` nunca trae el peri: la regla del servidor manda a «ninguna»
 * todo lo que dice «durante el entreno» o «después de entrenar»
 * (`backend/core/comida_del_suplemento.py`).
 *
 * VIVE AQUÍ Y NO EN UNA PANTALLA porque lo pintan DOS: el Inicio (`inicio/TuDietaHoy`) y
 * Nutrición (`nutrition/MealCard`). Con la cuenta escrita dos veces, el día que cambie la
 * regla una de las dos se quedaría vieja y nadie lo vería.
 *
 * El servidor da el hueco en SIMBÓLICO -- «primera», «última» -- porque quien sabe cuántas
 * comidas tiene el día es la pantalla que lo tiene delante: la cena es la 3 en quien come tres
 * veces y la 4 en quien come cuatro.
 */
export const suplementosPorComida = (suplementos, claves) => {
    const porClave = {};
    if (!claves || !claves.length) return porClave;
    const donde = { primera: claves[0], ultima: claves[claves.length - 1] };
    (suplementos || []).forEach((s) => {
        (s.en_comidas || []).forEach((hueco) => {
            const k = donde[hueco] || hueco;
            // Un hueco que este día no existe -- «Comida 4» en quien hoy come tres veces -- no
            // se recoloca en otra: se calla. Moverlo sería decirle que se tome algo en un
            // momento que no es el suyo.
            if (!claves.includes(k)) return;
            const lista = (porClave[k] = porClave[k] || []);
            // Sin repetir: un suplemento que cae dos veces en la misma comida (el cliente de
            // una sola toma, con «desayuno y cena») se nombra una.
            if (!lista.includes(s.titulo)) lista.push(s.titulo);
        });
    });
    return porClave;
};
