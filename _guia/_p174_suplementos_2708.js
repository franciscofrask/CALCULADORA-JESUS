/**
 * PUNTO 174 · los suplementos, con las comidas.
 *
 * «+ Creatina debajo de los macros de la comida 3. + Omega 3 · NAC en la 4. El intra y el post
 * no llevan: ellos son el suplemento, y ponerles otro debajo confunde.»
 *
 * La comida sale de la ficha si el coach la ha elegido y, si no, del texto del «¿Cuándo?»
 * (la opción C, decidida el 27-08: ver core/comida_del_suplemento.py).
 *
 * Se prueban los cuatro casos que hay en producción:
 *   «con el desayuno»          -> la primera comida
 *   «desayuno y cena»          -> la primera Y la última
 *   «durante el entreno»       -> en ninguna (es el intra)
 *   elegido a mano en la ficha -> manda sobre el texto
 *
 * Deja la cuenta como estaba: guarda el protocolo y el día que hubiera y los repone.
 *
 * Uso:  node _guia/_p174_suplementos_2708.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const ADMIN = process.env.ADMIN || 'francisco@test.com';
const ADMIN_CLAVE = process.env.ADMIN_CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');
const hoy = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

const quitarRecorrido = async (page) => {
    for (let i = 0; i < 4; i++) {
        const s = page.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await page.waitForTimeout(1200);
    }
    await page.locator('[data-testid="recorrido-overlay"]').waitFor({ state: 'detached', timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(1200);
};

// Los cuatro de la prueba, con los textos LITERALES que hay en producción.
const PRUEBA = [
    { titulo: 'Monohidrato de creatina', cuando: 'Todos los días, con el desayuno (entrenes o no)', cuanto: '10 g' },
    { titulo: 'Omega 3', cuando: 'Todos los días, en dos tomas (desayuno y cena)', cuanto: '2 perlas por toma' },
    { titulo: 'Ciclodextrina', cuando: 'Durante el entreno', cuanto: 'La que cuadre tus hidratos' },
    { titulo: 'NAC', cuando: 'En dos tomas, haciéndolas coincidir con el termogénico', cuanto: '1 cápsula', comida: 'ultima' },
];

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 900 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();

    const rc = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await rc.json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };
    const ra = await page.request.post(`${API}/api/auth/login`, { data: { email: ADMIN, password: ADMIN_CLAVE } });
    const cabAdmin = { Authorization: `Bearer ${(await ra.json()).access_token}` };

    // Quién es este cliente para el panel.
    const yo = await (await page.request.get(`${API}/api/auth/me`, { headers: cab })).json();
    // `/admin/clients` no filtra por correo y el correo va DENTRO de `user`, no en la raíz:
    // se trae la lista y se busca aquí. `id` es el del perfil, que es el que pide el panel.
    const lista = await (await page.request.get(`${API}/api/admin/clients?include_incomplete=true`, { headers: cabAdmin, timeout: 90000 })).json();
    const cliente = (Array.isArray(lista) ? lista : lista.clients || [])
        .find(c => ((c.user || {}).email || c.email || '').toLowerCase() === yo.email.toLowerCase());
    if (!cliente) { console.log('no encuentro al cliente en el panel'); await nav.close(); return; }
    const clientId = cliente.id;

    const FECHA = hoy();
    console.log(`\n=== PUNTO 174 · ${CUENTA} · ${FECHA} ===\n`);

    // ── Lo que había, para reponerlo ────────────────────────────────────────
    const antesProt = await (await page.request.get(`${API}/api/supplements/current`, { headers: cab })).json().catch(() => null);
    const habiaProt = !!(antesProt && (antesProt.versiones || []).length);
    const antesDia = await (await page.request.get(`${API}/api/diets/${FECHA}`, { headers: cab })).json();
    const habiaDia = !!antesDia.exists;
    console.log(habiaProt ? '(ya tenía protocolo: se repone)' : '(no tenía protocolo)');

    // ── El día, para que haya comidas donde colgarlos ───────────────────────
    if (!habiaDia) {
        await page.request.post(`${API}/api/diets`, {
            headers: cab,
            data: { fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                    opcion_peri: 'intra_post', comidas: { C1: { alimentos: [] } } },
        });
    }

    // ── El protocolo de prueba ──────────────────────────────────────────────
    const g = await page.request.post(`${API}/api/admin/supplements/save?client_id=${clientId}`, {
        headers: cabAdmin, data: { actual: PRUEBA, actual_fecha: FECHA, siguiente: [] },
    });
    console.log('protocolo de prueba guardado ->', g.status());

    // ── Lo que dice el servidor ─────────────────────────────────────────────
    const prot = await (await page.request.get(`${API}/api/supplements/current`, { headers: cab })).json();
    console.log('\nlo que resuelve el servidor:');
    const esperado = {
        'Monohidrato de creatina': 'primera',
        'Omega 3': 'primera,ultima',
        'Ciclodextrina': '',
        'NAC': 'ultima',
    };
    for (const it of prot.actual || []) {
        const sale = (it.en_comidas || []).join(',');
        console.log(`   ${ok(sale === esperado[it.titulo])} ${it.titulo.padEnd(26)} -> [${sale || 'en ninguna'}]   («${it.cuando.slice(0, 46)}»)`);
    }

    // ── Y lo que ve el cliente ──────────────────────────────────────────────
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);
    await page.waitForSelector('[data-testid="marca-comidas"]', { timeout: 25000 }).catch(() => {});

    console.log('\nlo que ve el cliente en su Inicio:');
    for (const k of ['C1', 'C2', 'C3', 'C4']) {
        const fila = page.locator(`[data-testid="comida-hoy-${k}"]`);
        if (!(await fila.count())) continue;
        const sup = fila.locator(`[data-testid="suplementos-${k}"]`);
        const texto = (await sup.count()) ? (await sup.innerText()).trim() : '(nada)';
        console.log(`   ${k}: ${texto}`);
    }
    for (const k of ['Intra', 'Post']) {
        const fila = page.locator(`[data-testid="comida-hoy-${k}"]`);
        if (!(await fila.count())) continue;
        const hay = await fila.locator(`[data-testid="suplementos-${k}"]`).count();
        console.log(`   ${k}: ${hay ? 'LLEVA SUPLEMENTO (mal, el punto dice que no)' : 'sin suplemento debajo   BIEN'}`);
    }
    await page.screenshot({ path: `_guia/_p174_inicio_${ancho}.png`, fullPage: true });

    // ── Se repone la cuenta ─────────────────────────────────────────────────
    if (habiaProt) {
        await page.request.post(`${API}/api/admin/supplements/save?client_id=${clientId}`, {
            headers: cabAdmin,
            data: { actual: antesProt.actual || [], actual_fecha: antesProt.actual_fecha || FECHA,
                    siguiente: antesProt.siguiente || [], siguiente_fecha: antesProt.siguiente_fecha || null },
        });
        console.log('\nprotocolo repuesto');
    } else {
        const d = await page.request.delete(`${API}/api/admin/supplements/version/${FECHA}?client_id=${clientId}`, { headers: cabAdmin });
        console.log('\nprotocolo de prueba borrado ->', d.status());
    }
    if (!habiaDia) await page.request.delete(`${API}/api/diets/${FECHA}`, { headers: cab });
    console.log(`captura -> _guia/_p174_inicio_${ancho}.png`);
    await nav.close();
})();
