/**
 * PUNTOS 67 y 69 · el «Por hacer esta semana» del panel y la rutina en PDF.
 *
 * Lee la columna «Sin rutina» del Dashboard. Para que haya algo que ver hace falta que
 * antes se hayan puesto PDF de prueba con `_guia/_p67_pdfs_de_prueba.py --poner` (en dev
 * no hay ninguno, porque los datos no viajan de produccion).
 *
 * Uso:  node _guia/_p67_panel_2808.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const ADMIN = process.env.ADMIN || 'francisco@test.com';
const ADMIN_CLAVE = process.env.ADMIN_CLAVE || 'demo123';

let malas = 0;
const ok = (b) => { if (!b) malas++; return b ? 'BIEN' : 'MAL '; };

(async () => {
    const ancho = Number(process.argv[2]) || 1280;
    const nav = await chromium.launch();
    const page = await (await nav.newContext({ viewport: { width: ancho, height: 1400 } })).newPage();

    const tok = (await (await page.request.post(`${API}/api/auth/login`, { data: { email: ADMIN, password: ADMIN_CLAVE } })).json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };
    console.log(`\n=== EL PANEL Y LA RUTINA EN PDF · ${ancho} px ===\n`);

    const r = await (await page.request.get(`${API}/api/admin/todo-semana`, { headers: cab, timeout: 180000 })).json();
    const sin = (r.sin_rutina || []).length, total = r.con_rutina_en_plan || 0;
    console.log(`el servidor: ${sin} sin rutina de ${total}  (${Math.round(sin / total * 100)} %)`);

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/admin`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(14000);

    const panel = page.locator('[data-testid="todo-semana"]').first();
    if (!(await panel.count())) {
        console.log(`el panel «Por hacer esta semana» no sale   ${ok(false)}`);
    } else {
        const texto = (await panel.innerText()).replace(/\n+/g, ' | ');
        console.log(`\nel panel dice:\n   ${texto.slice(0, 260)}`);
        const sale = /Sin rutina/i.test(texto);
        console.log(`\n67 · la columna «Sin rutina» se ve        ${ok(sale)}`);
        if (sale) {
            const m = texto.match(/Sin rutina\s*\|\s*(\d+)/);
            console.log(`67 · y dice ${m ? m[1] : '?'}, el mismo número que el servidor   ${ok(Boolean(m) && Number(m[1]) === sin)}`);
        }
    }
    await page.screenshot({ path: `_guia/_p67_panel_${ancho}.png`, fullPage: true });
    await nav.close();
    console.log(`\n${malas ? malas + ' MAL' : 'todo BIEN'} · captura -> _guia/_p67_panel_${ancho}.png`);
    process.exit(malas ? 1 : 0);
})();
