/**
 * ¿ESTE ALIMENTO ES GENÉRICO O ES DE MARCA? EN UN SOLO SITIO.
 *
 * El catálogo NO guarda el dato: `db.foods` tiene `{nombre, categorias, racion, macros,
 * unidades, minimo, url, imagen, codigoBarras}` y nada más -- comprobado en producción, no
 * hay `marca`, ni `es_generico`, ni `sin_web`. Así que se deduce, y hasta hoy se deducía de
 * la URL: «sin enlace = genérico».
 *
 * Francisco, 29-08-2026: «el filtro de genérico no está funcionando bien, se le escapan
 * alimentos con marca, no pasa en todas las categorías». Y era eso: en producción hay SEIS
 * alimentos de marca sin enlace, y el filtro los daba por genéricos. Cada uno en una
 * categoría distinta -- 29, 51, 2.1, 5.4, 19.3.2 y 7.1.2 --, de ahí lo de «no en todas»:
 *
 *   Chicharrón ibérico (7 Hermanos)          Batido proteico Smart Protein... (Nutrisport)
 *   Levadura nutricional (Sol Natural)       Café con leche sin azúcares... (Hacendado)
 *   Barrita proteica apple pie (Nutrisport)  Copos de avena integral sin gluten (Esgir)
 *
 * SE MIRAN LAS DOS COSAS: el enlace y el paréntesis del nombre. El paréntesis es el criterio
 * que confirmó Francisco el 08-07 (2.736 de 3.211 lo llevan), pero él solo no vale porque hay
 * paréntesis que son ACLARACIÓN y no marca. Se listaron todos los que hay entre los 475 sin
 * enlace: son 18 y se parten limpios en 12 aclaraciones (tres patrones nada más) y 6 marcas.
 * De ahí sale ACLARACIONES: si el paréntesis encaja ahí, sigue siendo genérico.
 *
 * Lo que esto NO resuelve, y conviene saberlo: una marca sin paréntesis y sin enlace pasaría
 * igual (Aquarius, Gatorade y Monster son así, aunque hoy los tres tienen enlace). La
 * solución de verdad es un campo en el catálogo; mientras no exista, esto es lo más cerca que
 * se puede estar sin tocar 3.211 fichas.
 */

// Los paréntesis que son una aclaración del alimento, no una marca. Salen de mirar los 18
// que hay en el catálogo entre los alimentos sin enlace, no de imaginarlos.
const ACLARACIONES = /corte magro|corte graso|m[áa]s del|menos del|\d\s*%|c[áa]scara|al natural|en conserva|congelad|cocinad|cocid|crud|desgrasad|sin az[úu]car|sin sal|light|enter[oa]|peque[nñ]|grande|mediano|por gramos|macros orientativos|aprox/i;

/** El texto del paréntesis si parece una MARCA; null si es una aclaración o no hay. */
export const marcaDelNombre = (nombre) => {
    const m = /\(([^)]+)\)/.exec(nombre || '');
    if (!m) return null;
    const dentro = m[1].trim();
    return ACLARACIONES.test(dentro) ? null : dentro;
};

/** De marca: tiene enlace a la web del súper, o lleva la marca en el nombre. */
export const esDeMarca = (food) => Boolean(food?.url) || Boolean(marcaDelNombre(food?.nombre));

/** Genérico: ni enlace ni marca en el nombre. */
export const esGenerico = (food) => !esDeMarca(food);

export default esGenerico;
