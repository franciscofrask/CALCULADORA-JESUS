/**
 * EL BOTON DE LA RUTINA DICE «VER RUTINA», NO «VER PDF» (Francisco, 3-09-2026).
 *
 * Son DOS botones que abren lo mismo -- el de la cabecera de la semana y el de la tarjeta
 * -- y no pueden llamarse distinto. Aqui se miran los dos, y ademas que la palabra «PDF»
 * no se le quede al cliente por ninguna otra esquina de esa pantalla: es la palabra que
 * Jesus pidio quitar en el video del 27-08 («olvida el PDF, olvida la palabra PDF»).
 *
 * La tarjeta solo sale si el cliente TIENE rutina en PDF, asi que se responde
 * `/routines/pdf/info` aqui para poder mirarla sin subirle nada a nadie.
 *
 * Uso:  node _guia/_probar_ver_rutina.js
 */
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

let fallos = 0;
const bien = (t, d) => console.log(`   OK   ${t}${d ? `  [${d}]` : ''}`);
const mal = (t, d) => { fallos++; console.log(`   MAL  ${t}${d ? `  [${d}]` : ''}`); };

(async () => {
    const login = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA, password: CLAVE }),
    }).then((r) => r.json());
    if (!login.access_token) throw new Error('no he podido entrar');

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 390, height: 1400 },
                                            locale: 'es-ES', timezoneId: 'Europe/Madrid' })).newPage();
    // Una rutina en PDF, para que la tarjeta exista.
    await p.route('**/api/routines/pdf/info', (route) => route.fulfill({
        status: 200, json: { hay: true, uploaded_at: '2026-08-24T10:00:00Z' } }));

    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, login.access_token);
    await p.goto(`${APP}/dashboard/routine`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(9000);
    for (let i = 0; i < 4; i++) {
        const s = p.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await p.waitForTimeout(800);
    }

    console.log('\nLos dos botones que abren la rutina');
    let vistos = 0;
    for (const [donde, sel] of [['la tarjeta', '[data-testid="routine-pdf-btn"]'],
                                ['la cabecera de la semana', '[data-testid="semana-rutina-pdf"]']]) {
        const b = p.locator(sel).first();
        if (!(await b.count())) { console.log(`   (${donde}: no sale con esta cuenta)`); continue; }
        vistos++;
        const t = (await b.innerText()).replace(/\s+/g, ' ').trim();
        if (t === 'Ver rutina') bien(`${donde}: «${t}»`);
        else mal(`${donde} dice «${t}»`);
    }
    if (!vistos) mal('no sale ninguno de los dos botones: la prueba no ha probado nada');

    // Y que la palabra no se quede por otra esquina de la pantalla.
    const pantalla = await p.locator('[data-testid="routine-page"]').first().innerText().catch(() => '');
    const conPdf = pantalla.split('\n').map((l) => l.trim())
        .filter((l) => /\bPDF\b/i.test(l));
    console.log('   líneas con «PDF»: ' + JSON.stringify(conPdf));
    if (!conPdf.length) bien('«PDF» no se le dice al cliente por ninguna parte');
    else mal('sigue diciéndole «PDF»', conPdf.join(' · '));

    await p.locator('[data-testid="routine-pdf-preview"], [data-testid="semana-rutina"]').first()
        .screenshot({ path: '_guia/_ver_rutina.png' }).catch(() => {});

    console.log(`\n${fallos ? `${fallos} FALLOS` : 'dice «Ver rutina»'}`);
    await nav.close();
    process.exit(fallos ? 1 : 0);
})();
