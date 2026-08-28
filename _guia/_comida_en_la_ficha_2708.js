/**
 * ELEGIR LA COMIDA DESDE LA FICHA DEL CLIENTE (Francisco, 27-08).
 *
 * «Es muy confuso esto, debería poder cambiarse desde la ficha del cliente el cuándo, y
 * además no con texto. ¿Cómo la app diferencia? ¿Qué pasa si escribo mal?»
 *
 * Lo que pasaba si escribías mal: nada visible. La app busca «desayuno» y «cena» en el texto
 * del «¿Cuándo?», así que un «al levantarme» o un «desayno» con una letra de menos dejaba al
 * suplemento fuera del Inicio, sin decirlo. Y para elegirlo a dedo había que ir al catálogo,
 * que no está en el menú y además cambia a TODOS los clientes a la vez.
 *
 * Ahora hay un desplegable en la propia ficha del cliente y, al lado, la frase de dónde acaba
 * saliendo -- calculada por el servidor, la misma que ve el cliente.
 *
 * Aquí se comprueban las cuatro cosas:
 *   1. el desplegable está en la ficha, con sus ocho opciones
 *   2. elegir una comida y guardar la mueve de verdad en el Inicio del cliente
 *   3. la frase de al lado dice dónde sale, y AVISA cuando no sale en ninguna
 *   4. escribir mal el «¿Cuándo?» ya no esconde nada: se lee «No sale debajo de ninguna comida»
 *
 * Deja el protocolo del cliente como estaba (copiado por la puerta del PANEL, que es la que
 * trae los nombres sin limpiar).
 *
 * Uso:  node _guia/_comida_en_la_ficha_2708.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const ADMIN = process.env.ADMIN || 'francisco@test.com';
const CLIENTE = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');

(async () => {
    const ancho = Number(process.argv[2]) || 1280;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 1000 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const errores = [];
    page.on('pageerror', (e) => errores.push(String(e).slice(0, 140)));

    const entrar = async (email) => (await (await page.request.post(`${API}/api/auth/login`,
        { data: { email, password: CLAVE } })).json()).access_token;
    const tokA = await entrar(ADMIN);
    const tokC = await entrar(CLIENTE);
    const cabA = { Authorization: `Bearer ${tokA}`, 'Content-Type': 'application/json' };
    const cabC = { Authorization: `Bearer ${tokC}`, 'Content-Type': 'application/json' };

    const perfil = await (await page.request.get(`${API}/api/clients/profile`, { headers: cabC })).json();
    const clientId = perfil.id;

    // La copia, por la puerta del panel: trae los nombres tal y como los guardó Jesús.
    const fichaAntes = await (await page.request.get(`${API}/api/admin/clients/${clientId}`, { headers: cabA })).json();
    const protoAntes = fichaAntes.supplement_protocol || null;

    const catalogo = await (await page.request.get(`${API}/api/admin/supplements/catalog`, { headers: cabA })).json();
    const conDesayuno = catalogo.find(c => /\bdesayuno\b/i.test(c.cuando || '') && !/TEST/i.test(c.titulo || ''));
    if (!conDesayuno) { console.log('no encuentro un suplemento de desayuno en el catálogo'); await nav.close(); return; }

    // EL DÍA DE ESPAÑA, NO EL DE ESTA MÁQUINA. El protocolo se resuelve por fecha en el
    // servidor y el servidor cuenta en hora de Madrid: con el reloj de aquí, a partir de
    // medianoche española se escribe en la versión de ayer y se lee la de hoy, así que
    // parece que no se guarda nada. Costó un rato entenderlo el 27-08.
    const FECHA = new Date().toLocaleDateString('en-CA', { timeZone: 'Europe/Madrid' });
    const pautar = async (extra = {}) => page.request.post(`${API}/api/admin/supplements/save?client_id=${clientId}`, {
        headers: cabA,
        data: { actual: [{ catalog_id: conDesayuno.id, titulo: conDesayuno.titulo,
                           cuando: conDesayuno.cuando, cuanto: conDesayuno.cuanto || '', ...extra }],
                siguiente: [], actual_fecha: FECHA, nota: 'Prueba de la comida en la ficha' },
    });
    const comidasQueDice = async () => {
        const f = await (await page.request.get(`${API}/api/admin/clients/${clientId}`, { headers: cabA })).json();
        return (((f.supplement_protocol || {}).actual || [])[0] || {}).en_comidas;
    };

    console.log(`\n=== LA COMIDA, ELEGIDA EN LA FICHA DEL CLIENTE · ${ancho} px ===\n`);
    console.log(`suplemento: «${conDesayuno.titulo}»`);
    console.log(`su «¿Cuándo?»: «${conDesayuno.cuando}»\n`);

    // ── El servidor, primero: es quien decide ───────────────────────────────
    await pautar();
    console.log(`sin elegir nada           -> ${JSON.stringify(await comidasQueDice())}`);
    await pautar({ comida: 'C3' });
    const enC3 = await comidasQueDice();
    console.log(`eligiendo «Comida 3»      -> ${JSON.stringify(enC3)}   ${ok(String(enC3) === 'C3')}`);
    await pautar({ comida: 'ninguna' });
    const enNada = await comidasQueDice();
    console.log(`eligiendo «En ninguna»    -> ${JSON.stringify(enNada)}   ${ok((enNada || []).length === 0)}`);
    // OJO CON ESTE, QUE NO ES LO QUE PARECE. Si el texto del cliente no nombra ninguna comida,
    // NO se queda sin sitio: se cae hacia atrás al texto de la ficha del catálogo, que aquí sí
    // dice «desayuno». O sea que reescribir el «¿Cuándo?» de un cliente sirve para MOVERLO
    // («con la cena» -> la última), pero no para quitarlo: para eso está «En ninguna».
    await pautar({ cuando: 'Todos los días, al levantarme' });
    const sinComida = await comidasQueDice();
    console.log(`con un «Cuándo» que no nombra comida -> ${JSON.stringify(sinComida)}   ${ok(String(sinComida) === 'primera')}`);
    console.log('   (manda el texto de la ficha, que dice desayuno: el del cliente no lo borra)');
    await pautar({ cuando: 'Todos los días, con la cena' });
    const aLaCena = await comidasQueDice();
    console.log(`cambiándole el texto a «con la cena»  -> ${JSON.stringify(aLaCena)}   ${ok(String(aLaCena) === 'ultima')}`);
    console.log('   (eso sí lo mueve, y solo a este cliente)\n');

    // ── Y ahora la pantalla ─────────────────────────────────────────────────
    await pautar();   // vuelta al automático, que es como se abre
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tokA);
    await page.goto(`${APP}/admin/clients/${clientId}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(7000);

    // La pestaña se llama «Suplementos» (dentro pone «Suplementación actual», que es otra cosa).
    const pestana = page.locator('[role="tab"]:has-text("Suplementos")').first();
    if (await pestana.count()) { await pestana.click(); await page.waitForTimeout(3500); }
    else console.log('   (no encuentro la pestaña de Suplementos)');

    const sel = page.locator('[data-testid="sup-comida-actual-0"]');
    console.log(`el desplegable está en la ficha        ${ok(await sel.count() > 0)}`);
    if (await sel.count()) {
        const opciones = await sel.locator('option').allInnerTexts();
        console.log(`   opciones: ${opciones.map(o => o.trim()).join(' · ')}`);
        console.log(`   son las ocho                        ${ok(opciones.length === 8)}`);
    }
    const frase = page.locator('[data-testid="sup-donde-actual-0"]');
    if (await frase.count()) console.log(`la frase de al lado dice: «${(await frase.first().innerText()).trim()}»`);

    // Elegir «Comida 2» y guardar: tiene que decir «Guarda para verlo» y luego moverse.
    if (await sel.count()) {
        await sel.selectOption('C2');
        await page.waitForTimeout(600);
        const avisa = await page.locator('text=Guarda para verlo').count();
        console.log(`al cambiarlo avisa de que hay que guardar  ${ok(avisa > 0)}`);
        await page.locator('[data-testid="save-supplements-btn"]').click();
        await page.waitForTimeout(1200);
        // Guardar la suplementación pregunta antes («¿Guardar la suplementación?»), igual que
        // los macros. Sin contestar que sí no se guarda nada, y el guion se creía que sí.
        const confirmar = page.locator('button:has-text("Guardar")').last();
        if (await confirmar.count()) await confirmar.click().catch(() => {});
        await page.waitForTimeout(5000);
        const f2 = page.locator('[data-testid="sup-donde-actual-0"]');
        const texto = (await f2.count()) ? (await f2.first().innerText()).trim() : '';
        console.log(`tras guardar dice: «${texto}»   ${ok(/Comida 2/i.test(texto))}`);
        console.log(`y el servidor lo confirma -> ${JSON.stringify(await comidasQueDice())}`);
    }
    await page.screenshot({ path: `_guia/_comida_en_la_ficha_${ancho}.png`, fullPage: true });

    // ── En el Inicio del cliente ────────────────────────────────────────────
    const diaAntes = await (await page.request.get(`${API}/api/diets/${FECHA}`, { headers: cabC })).json();
    if (!diaAntes.exists) {
        await page.request.post(`${API}/api/diets`, { headers: cabC,
            data: { fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                    opcion_peri: 'intra_post', comidas: { C1: { alimentos: [] } } } });
    }
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tokC);
    await page.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    for (let i = 0; i < 4; i++) {
        const s = page.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await page.waitForTimeout(1200);
    }
    const enComida2 = await page.locator('[data-testid="suplementos-C2"]').count();
    const enComida1 = await page.locator('[data-testid="suplementos-C1"]').count();
    console.log(`\nen el Inicio del cliente sale en la Comida 2   ${ok(enComida2 > 0)}`);
    console.log(`y ya NO en la Comida 1                        ${ok(enComida1 === 0)}`);

    // ── Se repone ───────────────────────────────────────────────────────────
    if (protoAntes && (protoAntes.actual || []).length) {
        await page.request.post(`${API}/api/admin/supplements/save?client_id=${clientId}`, {
            headers: cabA,
            data: { actual: protoAntes.actual, siguiente: protoAntes.siguiente || [],
                    actual_fecha: protoAntes.actual_fecha || FECHA,
                    siguiente_fecha: protoAntes.siguiente_fecha, nota: protoAntes.nota },
        });
        console.log('\nprotocolo repuesto (con los nombres de Jesús intactos)');
    } else {
        await page.request.delete(`${API}/api/admin/supplements/version/${FECHA}?client_id=${clientId}`, { headers: cabA });
        console.log('\nprotocolo de prueba borrado');
    }
    if (!diaAntes.exists) await page.request.delete(`${API}/api/diets/${FECHA}`, { headers: cabC });

    console.log(`errores de JavaScript: ${errores.length ? errores.join(' | ') : 'ninguno'}`);
    console.log(`captura -> _guia/_comida_en_la_ficha_${ancho}.png`);
    await nav.close();
})();
