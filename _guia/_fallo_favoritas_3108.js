/**
 * LOS DOS FALLOS QUE REPORTÓ UN CLIENTE EL 31-08, REPRODUCIDOS CONTRA EL SERVIDOR.
 *
 *   1) «Al copiar un menú que guardé como favorito, se me desajustan los macros.»
 *      Con 3 comidas, aplicar una favorita pide el reparto para CUATRO.
 *
 *   2) «Al copiarlo en otro día me aparece [...] lentejas cocidas, que obviamente
 *      se añadió solo.»
 *      Guardar un día NUNCA sustituye: fusiona. Lo que había en el destino y no
 *      trae el origen se queda dentro, y se pinta.
 *
 * No toca ningún dato de nadie: trabaja en una fecha lejana de la cuenta de pruebas
 * y la borra al terminar.
 *
 * Uso:  node _guia/_fallo_favoritas_3108.js
 */
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const FECHA = '2026-12-15';   // un día suelto, sin nada dentro

let TOKEN = '';
const pide = async (ruta, opciones = {}) => {
    const r = await fetch(`${API}/api${ruta}`, {
        ...opciones,
        headers: {
            'Content-Type': 'application/json',
            ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
            ...(opciones.headers || {}),
        },
    });
    const t = await r.text();
    try { return JSON.parse(t); } catch { return { _status: r.status, _texto: t }; }
};

const g = (n) => Math.round((n || 0) * 10) / 10;
const linea = (k, t) => `      ${k.padEnd(6)} P ${String(g(t.P)).padStart(6)}   H ${String(g(t.H)).padStart(6)}   G ${String(g(t.G)).padStart(6)}`;

(async () => {
    TOKEN = (await pide('/auth/login', {
        method: 'POST', body: JSON.stringify({ email: CUENTA, password: CLAVE }),
    })).access_token;
    if (!TOKEN) { console.log('no he podido entrar'); return; }

    // Una favorita de TRES comidas, como la del cliente.
    const favorita = {
        name: 'prueba 3 comidas',
        tipo_dia: 'entrenamiento',
        num_comidas: 3,
        momento_entreno: 1,
        opcion_peri: 'intra_post',
        comidas: {
            C1: { alimentos: [{ id: 1, nombre: 'Pechuga de pollo', cantidad_g: 200 }] },
            C2: { alimentos: [{ id: 1, nombre: 'Pechuga de pollo', cantidad_g: 200 }] },
            C3: { alimentos: [{ id: 1, nombre: 'Pechuga de pollo', cantidad_g: 200 }] },
        },
    };

    console.log('\n════ FALLO 1 · el reparto de una favorita de 3 comidas ════\n');
    const reparto = async (n) => {
        const res = await pide('/calculator/refit-diet', {
            method: 'POST',
            body: JSON.stringify({
                fecha: FECHA,
                tipo_dia: favorita.tipo_dia,
                num_comidas: n,
                momento_entreno: favorita.momento_entreno,
                opcion_peri: favorita.opcion_peri,
                comidas: favorita.comidas,
            }),
        });
        return res.distribution?.comidas || {};
    };

    const conTres = await reparto(3);
    const conCuatro = await reparto(4);   // lo que manda hoy la app

    const suma = (d) => Object.values(d).reduce(
        (a, t) => ({ P: a.P + (t.P || 0), H: a.H + (t.H || 0), G: a.G + (t.G || 0) }), { P: 0, H: 0, G: 0 });

    console.log('   LO QUE DEBERÍA PEDIR (num_comidas: 3)');
    Object.entries(conTres).forEach(([k, t]) => console.log(linea(k, t)));
    console.log(linea('TOTAL', suma(conTres)));
    console.log('\n   LO QUE PIDE HOY LA APP (num_comidas: 4, por el `=== 3 ? 4`)');
    Object.entries(conCuatro).forEach(([k, t]) => console.log(linea(k, t)));
    console.log('   ...y las tres que se pintan suman:');
    const tresDeCuatro = Object.fromEntries(Object.entries(conCuatro).filter(([k]) => k !== 'C4'));
    console.log(linea('C1..C3', suma(tresDeCuatro)));
    const falta = suma(conTres).P - suma(tresDeCuatro).P;
    console.log(`\n   => al cliente le faltan ${g(falta)} g de proteína al día: son los de la Comida 4,`);
    console.log('      que se reparte pero no se pinta.');

    console.log('\n════ FALLO 2 · copiar un día encima de otro ════\n');
    // El destino: un día con lentejas en la Comida 3.
    await pide('/diets', {
        method: 'POST',
        body: JSON.stringify({
            fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 3,
            momento_entreno: 1, opcion_peri: 'intra_post',
            comidas: {
                C1: { alimentos: [{ id: 1, nombre: 'Pechuga de pollo', cantidad_g: 100 }] },
                C2: { alimentos: [{ id: 1, nombre: 'Pechuga de pollo', cantidad_g: 100 }] },
                C3: { alimentos: [{ id: 999, nombre: 'Lentejas cocidas', cantidad_g: 250 }] },
            },
        }),
    });
    const antes = await pide(`/diets/${FECHA}`);
    console.log('   El día destino, antes de copiar:');
    Object.entries(antes.comidas || {}).forEach(([k, c]) =>
        console.log(`      ${k.padEnd(6)} ${(c.alimentos || []).map(a => a.nombre).join(', ') || '(vacía)'}`));

    // Ahora se copia encima un día de DOS comidas, como hace «Copiar a otro día»
    // (mismo cuerpo, mismo POST /api/diets, sin `comidas_completas`).
    await pide('/diets', {
        method: 'POST',
        body: JSON.stringify({
            fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 3,
            momento_entreno: 1, opcion_peri: 'intra_post',
            comidas: {
                C1: { alimentos: [{ id: 1, nombre: 'Merluza', cantidad_g: 200 }] },
                C2: { alimentos: [{ id: 1, nombre: 'Merluza', cantidad_g: 200 }] },
            },
        }),
    });
    const despues = await pide(`/diets/${FECHA}`);
    console.log('\n   Después de copiar encima un día que SOLO tiene C1 y C2:');
    Object.entries(despues.comidas || {}).forEach(([k, c]) =>
        console.log(`      ${k.padEnd(6)} ${(c.alimentos || []).map(a => a.nombre).join(', ') || '(vacía)'}`));
    const fantasma = (despues.comidas?.C3?.alimentos || []).map(a => a.nombre);
    console.log(fantasma.length
        ? `\n   => ahí siguen: ${fantasma.join(', ')}. La app dijo «se sustituye» y no sustituyó.`
        : '\n   => la C3 se fue: el día se sustituye de verdad.');

    await pide(`/diets/${FECHA}`, { method: 'DELETE' });
    const limpio = await pide(`/diets/${FECHA}`);
    console.log(`\n(día de pruebas borrado: ${limpio.exists ? 'NO, revísalo' : 'sí'})`);
})();
