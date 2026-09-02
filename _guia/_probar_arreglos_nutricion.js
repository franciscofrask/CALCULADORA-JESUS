/**
 * LOS DOS ARREGLOS DE NUTRICION, PROBADOS REPRODUCIENDO EL FALLO.
 *
 * De la revision del 1-09 («La pestaña de Nutricion, funcion por funcion»):
 *
 *   01  Abrir un dia para mirarlo lo reescribia y le quitaba el «cuadrado».
 *   05  El PDF y el guardado de despedida trabajaban en la cuenta equivocada
 *       (se montaban su propio `fetch` y se dejaban `X-Actuar-Como`).
 *
 * Aqui no se comprueba «que el codigo diga»: se abre la app, se hace lo que hacia el
 * cliente y se mira lo que sale por la red y lo que queda escrito.
 *
 * Uso:  node _guia/_probar_arreglos_nutricion.js
 */
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const EQUIPO = { correo: 'francisco@test.com', clave: 'demo123' };
const CLIENTE = { correo: 'clientedemo@test.com', clave: 'demo123' };
//: El user_id del cliente al que se suplanta, y un dia suyo con comida.
const CLIENTE_ID = 'f99879aa-8098-4676-a2d7-a2cd7b6bae22';
const DIA_CON_COMIDA = '2026-08-31';

const entrar = async ({ correo, clave }) => fetch(`${API}/api/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: correo, password: clave }),
}).then((r) => r.json()).then((r) => r.access_token);

/** El dia tal y como esta guardado, preguntandoselo al servidor como el cliente. */
const diaGuardado = async (token, fecha) => fetch(`${API}/api/diets/${fecha}`, {
    headers: { Authorization: `Bearer ${token}` },
}).then((r) => r.json());

/**
 * Un cambio de verdad de los que hace el cliente: pasar el dia de entreno a descanso.
 *
 * Se eligio este y no el «+» de los gramos porque el «+» vive dentro de la comida y en la
 * vista de lista las comidas plegadas dejan sus botones en el DOM pero ocultos: pulsar el
 * primero que aparece es pulsar uno invisible, y el clic no hace nada. El tipo de dia es un
 * boton de arriba, siempre visible, con testid, y entra en la huella igual que los gramos.
 *
 * Devuelve a cual se cambio, para poder dejarlo despues como estaba.
 */
const cambiarTipoDeDia = async (p) => {
    // Cuál está marcado se lee de su clase: el botón activo va en naranja de marca.
    const enDescanso = await p.evaluate(() => {
        const b = document.querySelector('[data-testid="tipo-dia-descanso"]');
        return b ? /FF671F|bg-brand/.test(b.className) : null;
    });
    if (enDescanso === null) return null;
    const destino = enDescanso ? 'entrenamiento' : 'descanso';
    const b = p.locator(`[data-testid="tipo-dia-${destino}"]`).first();
    if (!(await b.count())) return null;
    await b.click({ force: true }).catch(() => {});
    return destino;
};

(async () => {
    let fallos = 0;
    const bien = (t) => console.log(`   OK   ${t}`);
    const mal = (t) => { fallos++; console.log(`   MAL  ${t}`); };

    const tokenCliente = await entrar(CLIENTE);
    const tokenEquipo = await entrar(EQUIPO);

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n01 · Abrir un dia para mirarlo NO puede cambiarlo');
    {
        const antes = await diaGuardado(tokenCliente, DIA_CON_COMIDA);
        const nav = await chromium.launch();
        const ctx = await nav.newContext({ viewport: { width: 390, height: 1400 },
                                           locale: 'es-ES', timezoneId: 'Europe/Madrid' });
        const p = await ctx.newPage();
        // Las escrituras del dia, contadas: la prueba de verdad es que no haya ninguna.
        let escrituras = 0;
        p.on('request', (r) => {
            if (r.method() === 'POST' && r.url().endsWith('/api/diets')) escrituras++;
        });
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tokenCliente);

        // Abrir el dia, esperar mas que el guardado con retardo (1,5 s), pasar al siguiente
        // con la flecha y volver: es exactamente lo que hizo el que encontro el fallo.
        await p.goto(`${APP}/dashboard/nutrition?date=${DIA_CON_COMIDA}`, { waitUntil: 'networkidle' });
        await p.waitForTimeout(9000);
        const siguiente = p.locator('[data-testid="dia-siguiente"], [aria-label="Día siguiente"]').first();
        if (await siguiente.count()) { await siguiente.click().catch(() => {}); await p.waitForTimeout(5000); }
        // Y la pestaña a segundo plano, que es lo que dispara el guardado de despedida.
        await p.evaluate(() => {
            Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
            document.dispatchEvent(new Event('visibilitychange'));
        });
        await p.waitForTimeout(2500);
        await nav.close();

        const despues = await diaGuardado(tokenCliente, DIA_CON_COMIDA);
        console.log(`   escrituras del dia: ${escrituras}`);
        console.log(`   updated_at  ${antes.updated_at}  ->  ${despues.updated_at}`);
        console.log(`   is_cuadrado ${antes.is_cuadrado}  ->  ${despues.is_cuadrado}`);
        if (escrituras === 0) bien('mirar el dia no manda ni un guardado');
        else mal(`mirar el dia mando ${escrituras} guardado(s)`);
        if (antes.updated_at === despues.updated_at) bien('el dia sigue con su fecha de siempre');
        else mal('el dia se reescribio con la fecha de hoy');
        if (antes.is_cuadrado === despues.is_cuadrado) bien('el «cuadrado» no se ha tocado');
        else mal('el «cuadrado» cambio solo por mirarlo');
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n01b · Pero tocar el dia SI lo guarda (el arreglo no puede romper esto)');
    {
        const nav = await chromium.launch();
        const ctx = await nav.newContext({ viewport: { width: 390, height: 1400 },
                                           locale: 'es-ES', timezoneId: 'Europe/Madrid' });
        const p = await ctx.newPage();
        let escrituras = 0;
        p.on('request', (r) => {
            if (r.method() === 'POST' && r.url().endsWith('/api/diets')) escrituras++;
        });
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tokenCliente);
        await p.goto(`${APP}/dashboard/nutrition?date=${DIA_CON_COMIDA}`, { waitUntil: 'networkidle' });
        await p.waitForTimeout(9000);
        const cambiado = await cambiarTipoDeDia(p);
        if (!cambiado) console.log('   (no he encontrado el selector de tipo de dia)');
        await p.waitForTimeout(5000);
        // Y se deja como estaba, que esto es una cuenta de pruebas pero no un vertedero.
        await cambiarTipoDeDia(p);
        await p.waitForTimeout(4000);
        await nav.close();
        if (escrituras > 0) bien(`tocar el dia lo guarda (${escrituras} guardado/s)`);
        else mal('tocar el dia ya no guarda: el arreglo se ha pasado de frenada');
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n05 · Las dos llamadas a mano mandan X-Actuar-Como');
    {
        const nav = await chromium.launch();
        const ctx = await nav.newContext({ viewport: { width: 390, height: 1400 },
                                           locale: 'es-ES', timezoneId: 'Europe/Madrid' });
        const p = await ctx.newPage();
        const vistas = [];
        p.on('request', (r) => {
            const u = r.url();
            if (u.includes('/api/diets') && (u.includes('/pdf') || r.method() === 'POST')) {
                vistas.push({ que: u.includes('/pdf') ? 'PDF' : 'guardado',
                              cabecera: r.headers()['x-actuar-como'] || null });
            }
        });
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate(([t, id]) => {
            localStorage.clear();
            localStorage.setItem('token', t);
            // Es lo que deja AuthContext al entrar en la calculadora de un cliente.
            sessionStorage.setItem('actuar_como', JSON.stringify({ userId: id }));
        }, [tokenEquipo, CLIENTE_ID]);
        await p.goto(`${APP}/dashboard/nutrition?date=${DIA_CON_COMIDA}`, { waitUntil: 'networkidle' });
        await p.waitForTimeout(9000);

        // El PDF.
        const pdf = p.locator('[data-testid="export-pdf-btn"]').first();
        if (await pdf.count()) { await pdf.click({ force: true }).catch(() => {}); await p.waitForTimeout(4000); }

        // Y el guardado de despedida: se toca algo y se manda la pestaña a segundo plano.
        // Se cambia algo y se manda la pestaña a segundo plano ANTES de que salte el
        // guardado con retardo (1,5 s): asi el que escribe es el de despedida, que es el
        // que se esta comprobando.
        if (!await cambiarTipoDeDia(p)) console.log('   (no he encontrado el selector de tipo de dia)');
        await p.waitForTimeout(700);
        await p.evaluate(() => {
            Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
            document.dispatchEvent(new Event('visibilitychange'));
        });
        await p.waitForTimeout(2500);
        // Y el dia, como estaba: la prueba escribe, asi que la prueba recoge.
        await cambiarTipoDeDia(p);
        await p.waitForTimeout(4000);
        await nav.close();

        for (const v of vistas) {
            console.log(`   ${v.que.padEnd(9)} X-Actuar-Como: ${v.cabecera || '(NO LA MANDA)'}`);
        }
        const pdfs = vistas.filter((v) => v.que === 'PDF');
        const guardados = vistas.filter((v) => v.que === 'guardado');
        if (!pdfs.length) mal('no se llego a pedir el PDF: la prueba no vale');
        else if (pdfs.every((v) => v.cabecera === CLIENTE_ID)) bien('el PDF va a la cuenta del cliente');
        else mal('el PDF sigue yendo a la cuenta del entrenador');
        if (!guardados.length) mal('no se llego a guardar: la prueba no vale');
        else if (guardados.every((v) => v.cabecera === CLIENTE_ID)) bien('el guardado escribe en la cuenta del cliente');
        else mal('el guardado sigue escribiendo en la cuenta del entrenador');
    }

    console.log(fallos ? `\n${fallos} comprobacion(es) MAL` : '\nTodo bien');
    process.exit(fallos ? 1 : 0);
})();
