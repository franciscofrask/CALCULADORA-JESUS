/**
 * «GUÁRDAMELA COMO PLANTILLA», el botón del bloque 8 del informe del mes (doc del 1-09).
 *
 * Era lo único de ese documento que quedaba sin hacer. Esto lo comprueba de punta a punta:
 * que sale donde su maqueta lo dibuja -- bajo el desayuno y en ninguna otra fila --, que al
 * pulsarlo se guarda una favorita DE COMIDA de verdad, con sus alimentos y sus gramos, y
 * que el botón se queda diciendo dónde ha ido.
 *
 * Y de paso la regla que manda sobre todo el informe: «EL INFORME NO LE PIDE NADA». Se
 * cuenta todo lo que se puede tocar en la pantalla y tiene que ser exactamente esto: los
 * selectores de las fotos y este botón. Ni un campo, ni una pregunta.
 *
 * El informe se responde aquí (no se le crea ninguno al cliente de pruebas), pero el botón
 * SÍ escribe: guarda una favorita de verdad, y al final se borra.
 *
 * Antes hay que tener el ejemplo:
 *     cd backend && ./venv/Scripts/python.exe _probar_informe_del_mes.py
 *
 * Uso:  node _guia/_probar_plantilla_del_informe.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const ID = 'informe-de-prueba';

let fallos = 0;
const bien = (t, d) => console.log(`   OK   ${t}${d ? `  [${d}]` : ''}`);
const mal = (t, d) => { fallos++; console.log(`   MAL  ${t}${d ? `  [${d}]` : ''}`); };

(async () => {
    const login = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA, password: CLAVE }),
    }).then((r) => r.json());
    if (!login.access_token) throw new Error('no he podido entrar');
    const token = login.access_token;
    const api = async (ruta, metodo = 'GET', cuerpo) => {
        const r = await fetch(API + ruta, {
            method: metodo,
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
        });
        if (!r.ok) throw new Error(`${metodo} ${ruta} -> ${r.status} ${await r.text()}`);
        return r.json();
    };

    // EL DESAYUNO DEL EJEMPLO CAMBIA CASI CADA DÍA, y entonces no hay plantilla que guardar
    // (que es lo correcto). Para poder mirar el botón se le pone al ejemplo un desayuno
    // estable, con alimentos de verdad del catálogo: los dos que se guarden tienen que
    // poder volver a montarse.
    const informe = JSON.parse(fs.readFileSync('_guia/_informe_del_mes_ejemplo.json', 'utf8'));
    const DESAYUNO = [
        { nombre: 'Avena', unidad: 'g', cantidad: 80, alimento_id: 48, gramos: 80 },
        { nombre: 'Pollo', unidad: 'g', cantidad: 150, alimento_id: 119, gramos: 150 },
    ];
    informe.bloques.dia_tipo.filas[0] = {
        clave: 'C1', nombre: 'Desayuno', momento: 'En ayunas', dias: 28,
        combinaciones_distintas: 3, varia: false,
        texto: '80 g de Avena y 150 g de Pollo', cuantos: '21 de 28 días',
        items: DESAYUNO,
    };

    const antes = ((await api('/api/diets/favorites?ambito=comida')).favorites || []).length;

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 390, height: 1600 },
                                            locale: 'es-ES', timezoneId: 'Europe/Madrid' })).newPage();
    await p.route('**/api/reports', (route) => (route.request().method() === 'GET'
        ? route.fulfill({ status: 200, json: [{ id: ID, tipo: 'mensual', weight: 78.4,
            created_at: '2026-08-25T12:00:00+00:00', informe_estado: 'entregado' }] })
        : route.continue()));
    await p.route(`**/api/reports/${ID}/informe`, (route) =>
        route.fulfill({ status: 200, json: informe }));
    // LAS FOTOS TAMBIÉN, o el bloque 6 no sale y entonces la cuenta de «lo único que se
    // puede tocar» se hace sin las fotos, que son la mitad de la frase de su documento.
    const POSES = ['frente', 'espaldas', 'perfil'];
    const FECHAS = ['2026-08-04', '2026-09-01'];
    await p.route('**/api/reports/photos', (route) => (route.request().method() === 'GET'
        ? route.fulfill({ status: 200, json: { photos: POSES.flatMap(
            (pose) => FECHAS.map((f) => ({ id: `${pose}-${f}`, pose, taken_at: f }))) } })
        : route.continue()));
    await p.route('**/api/reports/photos/*', (route) => route.fulfill({
        status: 200, contentType: 'image/gif',
        body: Buffer.from('R0lGODlhAQABAIAAAMLCwgAAACH5BAAAAAAALAAAAAABAAEAAAICRAEAOw==', 'base64'),
    }));

    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, token);
    await p.goto(`${APP}/dashboard/reports`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(6000);
    for (let i = 0; i < 4; i++) {
        const s = p.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await p.waitForTimeout(900);
    }
    const historial = p.locator('[data-testid="seg-historial"]');
    if (await historial.count()) { await historial.click(); await p.waitForTimeout(2500); }
    const abrir = p.locator(`[data-testid="ver-informe-${ID}"]`);
    if (await abrir.count()) { await abrir.click(); await p.waitForTimeout(4000); }

    if (!(await p.locator('[data-testid="informe-del-mes"]').count())) {
        mal('no se abre el informe: sin él no hay nada que mirar');
        console.log(`\n${fallos} FALLOS`); await nav.close(); process.exit(1);
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\nEl botón, donde su maqueta lo pone');
    const boton = p.locator('[data-testid="informe-guardar-plantilla"]');
    if (!(await boton.count())) { mal('no sale el botón'); }
    else {
        bien('sale', (await boton.innerText()).trim());
        if ((await boton.innerText()).trim() === 'Guárdamela como plantilla') bien('con su texto, literal');
        else mal('el texto no es el de su maqueta', (await boton.innerText()).trim());
        if (await boton.count() === 1) bien('y UNO solo: no en todas las comidas');
        else mal('sale en más de una fila', String(await boton.count()));
        // Y dentro de la fila del desayuno, no suelto por ahí.
        const dentro = await p.locator('[data-testid="informe-dia-C1"] [data-testid="informe-guardar-plantilla"]').count();
        if (dentro) bien('dentro de la fila del desayuno');
        else mal('el botón no está en la fila del desayuno');
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n«El informe no le pide nada»');
    const tocables = await p.evaluate(() => {
        const dentro = document.querySelector('[data-testid="informe-del-mes"]');
        if (!dentro) return [];
        return [...dentro.querySelectorAll('button, a, input, select, textarea, [role="button"]')]
            .filter((e) => e.offsetParent !== null)
            .map((e) => e.getAttribute('data-testid')
                || (e.innerText || e.getAttribute('aria-label') || e.tagName).trim().slice(0, 30));
    });
    console.log('   se puede tocar: ' + JSON.stringify(tocables));
    const deLasFotos = tocables.filter((t) => /informe-pose-|informe-foto-|de agosto|de septiembre|de junio|de julio/i.test(t));
    const laPlantilla = tocables.filter((t) => /guardar-plantilla/.test(t));
    const otros = tocables.filter((t) => !deLasFotos.includes(t) && !laPlantilla.includes(t));
    if (!otros.length) bien('lo único tocable son las fotos y la plantilla');
    else mal('hay más cosas que tocar de las que su documento permite', otros.join(' · '));
    const campos = await p.locator('[data-testid="informe-del-mes"] input, [data-testid="informe-del-mes"] textarea').count();
    if (!campos) bien('y ni un campo donde escribir');
    else mal('hay campos donde escribir', String(campos));

    // ───────────────────────────────────────────────────────────────────────
    console.log('\nY al pulsarlo, se guarda de verdad');
    if (await boton.count()) {
        await boton.scrollIntoViewIfNeeded();
        await boton.screenshot({ path: '_guia/_informe_del_mes/3_plantilla.png' }).catch(() => {});
        await boton.click();
        await p.waitForTimeout(2500);
        const hecho = p.locator('[data-testid="informe-plantilla-hecha"]');
        if (await hecho.count()) bien('el botón dice dónde ha ido', (await hecho.innerText()).trim());
        else mal('el botón no confirma nada');
        if (!(await p.locator('[data-testid="informe-guardar-plantilla"]').count()))
            bien('y ya no se puede volver a guardar la misma');
        else mal('sigue el botón: se puede guardar dos veces');

        const ahora = (await api('/api/diets/favorites?ambito=comida')).favorites || [];
        console.log(`   favoritas de comida: ${antes} -> ${ahora.length}`);
        const nueva = ahora.find((f) => /Desayuno de siempre/.test(f.name || ''));
        if (!nueva) { mal('no se ha guardado ninguna favorita'); }
        else {
            bien('se guardó', `${nueva.name} · ${nueva.ambito} · de ${nueva.comida_origen}`);
            const g = (nueva.alimentos || []).map((a) => `${a.alimento_id}:${a.cantidad_g}`).sort().join(' ');
            if (g === '119:150 48:80') bien('con los alimentos y los gramos del día tipo', g);
            else mal('los alimentos guardados no son los del día tipo', g);
            await api(`/api/diets/favorites/${nueva.id}`, 'DELETE');
            console.log('   (borrada, que era de prueba)');
        }
    }

    console.log(`\n${fallos ? `${fallos} FALLOS` : 'el botón del bloque 8, cerrado'}`);
    await nav.close();
    process.exit(fallos ? 1 : 0);
})();
