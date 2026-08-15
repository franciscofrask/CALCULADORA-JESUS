/**
 * EL BUSCADOR BUENO, UNO SOLO PARA TODA LA APP.
 *
 * Jesús, 15-08-2026 (fallo 3): buscar «pechuga» en «Añadir ingrediente» devolvía Pepsi Max,
 * Pepsi Cola y Pera por gramos, mientras que en «Alimentos» devolvía 58 pechugas. Mismo
 * catálogo, dos buscadores: «el arreglo es usar el mismo en los dos sitios».
 *
 * Esto es el de «Alimentos», sacado de su pantalla y puesto donde puedan usarlo los dos.
 * Viene de Calma (group-home-utils): el filtro pide que TODAS las palabras escritas estén en
 * el nombre, y el orden lo decide `relevancia` -- cuanto más se parece el nombre a lo
 * escrito, más arriba --, no lo que le falta de macros a la comida.
 */

// h(): sin acentos y en mayúsculas, para comparar «salmón» con «salmon».
export const norm = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();

// H(): lo escrito no puede ser más largo que el nombre.
export const lenOk = (e, r) => (r === '' ? true : !(!r || !e.length || ('' + r).length > e.length));

// L()
export const inc = (e, r) => (lenOk(e, r) ? e.includes(r) : false);

// E(): ¿está esta palabra en este texto?
export const matchWord = (e, r) => (lenOk(e, r) ? inc(norm(e), norm(r)) : false);

// P(..., true): todas las palabras escritas tienen que estar en el nombre.
export const matchAll = (nombre, words) => words.every(w => matchWord(nombre, w));

/**
 * Ie(): cuánto se parece el nombre a lo que se ha escrito (más = mejor).
 *
 * Puntúa por partes: el nombre entero igual, que empiece por lo escrito, que una de sus
 * palabras sea o empiece por lo escrito, y por último que aparezca suelto. Es lo que hace
 * que «pechuga» saque pechugas y no cualquier cosa con esas letras dentro.
 */
export const relevancia = (nombre, words) => {
    let n = 0;
    const t = nombre.toUpperCase();
    const s = t.split(' ');
    const a = norm(nombre);
    const ia = s.map(norm);
    for (const f of words) {
        const l = f.toUpperCase();
        const p = norm(f);
        if (t === l) n += 5;
        if (a === p) n += 5;
        if (t.startsWith(l)) n += 4;
        if (a.startsWith(p)) n += 4;
        if (s.some(u => u === l)) n += 3;
        if (ia.some(u => u === p)) n += 2;
        if (s.some(u => u.startsWith(l))) n += 2;
        if (ia.some(u => u.startsWith(p))) n += 1;
        if (s.some(u => inc(u, l))) n += 1;
        if (ia.some(u => matchWord(u, p))) n += 1;
    }
    return n;
};

/** Lo escrito, partido en palabras. */
export const palabrasDe = (texto) => String(texto || '').trim().split(/\s+/).filter(Boolean);

/**
 * Una lista de alimentos filtrada y ordenada por lo que se ha escrito.
 * Sin texto devuelve la lista tal cual: ordenarla es cosa de quien llama.
 */
export const buscarPorNombre = (alimentos, texto) => {
    const words = palabrasDe(texto);
    if (!words.length) return alimentos;
    return alimentos
        .filter(f => matchAll(f.nombre || '', words))
        .sort((x, y) => relevancia(y.nombre || '', words) - relevancia(x.nombre || '', words));
};

/** Reordena por relevancia sin filtrar (la lista ya viene filtrada del servidor). */
export const ordenarPorRelevancia = (alimentos, texto) => {
    const words = palabrasDe(texto);
    if (!words.length) return alimentos;
    return [...alimentos].sort(
        (x, y) => relevancia(y.nombre || '', words) - relevancia(x.nombre || '', words));
};
