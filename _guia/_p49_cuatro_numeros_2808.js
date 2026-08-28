/**
 * PUNTO 49 del documento del 24-08: «Cuatro pantallas dan cuatro números del mismo día.
 * Unas suman el perientreno y otras no, y ninguna lo dice».
 *
 * Monta UN día con comidas normales y con intra/post, y lee el MISMO dato en las cuatro
 * sitios donde sale: Inicio (sus cuatro pestañas), Nutrición y Mi semana.
 *
 * Solo mide. Repone el día al terminar.
 *
 * Uso:  node _guia/_p49_cuatro_numeros_2808.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const POLLO = 498, ARROZ = 1657, ACEITE = 3;

const quitarRecorrido = async (page) => {
    for (let i = 0; i < 4; i++) {
        const s = page.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await page.waitForTimeout(1200);
    }
    await page.waitForTimeout(1000);
};

(async () => {
    const ancho = Number(process.argv[2]) || 1280;
    const nav = await chromium.launch();
    const page = await (await nav.newContext({ viewport: { width: ancho, height: 1200 } })).newPage();

    const tok = (await (await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } })).json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };
    const d = new Date();
    const HOY = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    console.log(`\n=== PUNTO 49 · el mismo día contado en cuatro sitios · ${HOY} ===\n`);

    const antes = await (await page.request.get(`${API}/api/diets/${HOY}`, { headers: cab })).json();
    const habia = !!antes.exists;

    // Un día con comidas normales Y con perientreno: es la unica forma de que se note.
    await page.request.delete(`${API}/api/diets/${HOY}`, { headers: cab });
    await page.request.post(`${API}/api/diets`, { headers: cab,
        data: { fecha: HOY, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 1,
                opcion_peri: 'intra_post', comidas: {
                    // LAS CUATRO COMIDAS montadas: Mi semana solo enseña los macros de un
                    // dia «montada»; con una a medias pone «1 de 4 comidas» y no se ve.
                    C1: { alimentos: [{ alimento_id: POLLO, cantidad_g: 150 }, { alimento_id: ARROZ, cantidad_g: 80 }, { alimento_id: ACEITE, cantidad_g: 10 }] },
                    C2: { alimentos: [{ alimento_id: POLLO, cantidad_g: 120 }, { alimento_id: ARROZ, cantidad_g: 70 }, { alimento_id: ACEITE, cantidad_g: 8 }] },
                    C3: { alimentos: [{ alimento_id: POLLO, cantidad_g: 100 }, { alimento_id: ARROZ, cantidad_g: 60 }, { alimento_id: ACEITE, cantidad_g: 8 }] },
                    C4: { alimentos: [{ alimento_id: POLLO, cantidad_g: 100 }, { alimento_id: ARROZ, cantidad_g: 60 }, { alimento_id: ACEITE, cantidad_g: 8 }] },
                    Intra: { alimentos: [{ alimento_id: ARROZ, cantidad_g: 40 }] },
                    Post: { alimentos: [{ alimento_id: POLLO, cantidad_g: 120 }, { alimento_id: ARROZ, cantidad_g: 50 }] },
                } } });
    await page.request.post(`${API}/api/user/ajustes-app`, { headers: cab, data: { vista: 'actual' } });

    const dia = await (await page.request.get(`${API}/api/diets/${HOY}`, { headers: cab })).json();
    console.log('lo que dice el servidor:');
    console.log(`   objetivo_comidas (sin peri): ${JSON.stringify(dia.objetivo_comidas)}`);
    console.log(`   servido_comidas  (sin peri): ${JSON.stringify(dia.servido_comidas)}`);
    const rep = await (await page.request.post(`${API}/api/calculator/distribute`, { headers: cab,
        data: { fecha: HOY, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 1,
                opcion_peri: 'intra_post', single_meal: false } })).json();
    console.log(`   resumen del reparto (con peri en P y H): P_total=${rep?.resumen?.P_total} H_total=${rep?.resumen?.H_total} G_total=${rep?.resumen?.G_total}`);

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);

    const leerTrio = async (pref) => {
        const r = {};
        for (const k of ['P', 'H', 'G']) {
            const e = page.locator(`[data-testid="${pref}${k}"]`).first();
            if (!(await e.count())) { r[k] = '?'; continue; }
            const t = (await e.innerText()).replace(/\s+/g, ' ').trim();
            r[k] = t;
        }
        return r;
    };

    // ── Nutrición ───────────────────────────────────────────────────────────
    await page.goto(`${APP}/dashboard/nutrition?date=${HOY}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);
    const nutri = await leerTrio('dia-');
    console.log(`\nNUTRICIÓN  ->  P ${nutri.P.replace(/\n/g, ' ')} | H ${nutri.H.replace(/\n/g, ' ')} | G ${nutri.G.replace(/\n/g, ' ')}`);

    // ── Inicio, sus cuatro pestañas ─────────────────────────────────────────
    await page.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);
    const VISTAS = ['macros', 'dieta', 'llevas', 'falta'];
    console.log('\nINICIO, sus cuatro pestañas:');
    const deInicio = {};
    for (const v of VISTAS) {
        const b = page.locator(`[data-testid="vista-${v}"]`).first();
        if (!(await b.count())) { console.log(`   ${v.padEnd(7)} -> no sale`); continue; }
        await b.click().catch(() => {});
        await page.waitForTimeout(1600);
        // En «Llevas» hay que marcar algo o sale vacío; se lee lo que haya.
        const t = {};
        for (const k of ['P', 'H', 'G']) {
            const num = page.locator(`[data-testid="dieta-hoy-${v}-${k}"]`).first();
            t[k] = (await num.count()) ? (await num.innerText()).replace(/\s+/g, ' ').trim() : '-';
        }
        deInicio[v] = t;
        console.log(`   ${v.padEnd(7)} -> P ${t.P} | H ${t.H} | G ${t.G}`);
    }

    // ── Mis macros ──────────────────────────────────────────────────────────
    await page.goto(`${APP}/dashboard/macro-calculator`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);
    const hoyMM = page.locator('[data-testid="mis-macros-hoy"]').first();
    if (await hoyMM.count()) {
        console.log('\nMIS MACROS ->');
        for (const l of (await hoyMM.innerText()).split('\n').map(s => s.trim()).filter(Boolean)) {
            console.log('   ' + l);
        }
    } else {
        console.log('\nMIS MACROS -> no sale la tarjeta de hoy');
    }

    // ── Mi semana ───────────────────────────────────────────────────────────
    await page.goto(`${APP}/dashboard/semana`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(8000);
    await quitarRecorrido(page);
    const fila = page.locator(`[data-testid="dieta-${HOY}"]`).first();
    const enPantalla = (await fila.count()) ? (await fila.innerText()).replace(/\s+/g, ' ').trim() : '(no sale)';
    const sem = await (await page.request.get(`${API}/api/diets/semana?hoy_cliente=${HOY}`, { headers: cab })).json();
    const hoySem = (sem.dias || []).find(x => x.fecha === HOY);
    console.log(`\nMI SEMANA  ->  en pantalla: «${enPantalla}»`);
    console.log(`               del servidor: ${JSON.stringify(hoySem?.macros)}`);
    await page.screenshot({ path: `_guia/_p49_mi_semana_${ancho}.png`, fullPage: true });
    // ¿Caben los tres números en la fila, o el navegador los corta con «…»?
    const corte = await fila.evaluate((el) => {
        const t = el.querySelector('.whitespace-nowrap') || el.querySelector('.truncate');
        return t ? { sw: t.scrollWidth, cw: t.clientWidth, txt: String(t.textContent || '').replace(/\s+/g, ' ').trim() } : null;
    }).catch(() => null);
    if (corte) {
        console.log(`               los números «${corte.txt}» ocupan ${corte.sw}px y tienen ${corte.cw}px   ${corte.sw > corte.cw + 1 ? 'SE CORTAN' : 'se leen enteros'}`);
    }

    // ── El veredicto ────────────────────────────────────────────────────────
    const nDe = (t) => (String(t).match(/(\d+)/g) || []).slice(0, 1).map(Number)[0];
    const nutriP = nDe(nutri.P), dietaP = nDe((deInicio.dieta || {}).P), semP = hoySem?.macros?.P;
    console.log('\n49 · el mismo día, tres cuentas de lo creado:');
    console.log(`     Nutrición ${nutriP} P · Inicio ${dietaP} P · Mi semana ${Math.round(semP)} P`);
    console.log(`     ¿dicen lo mismo?  ${nutriP === dietaP && dietaP === Math.round(semP) ? 'BIEN' : 'MAL '}`);

    await nav.close();
    const limpio = await chromium.launch();
    const p2 = await (await limpio.newContext()).newPage();
    await p2.request.delete(`${API}/api/diets/${HOY}`, { headers: cab });
    if (habia) {
        await p2.request.post(`${API}/api/diets`, { headers: cab,
            data: { fecha: HOY, tipo_dia: antes.tipo_dia, num_comidas: antes.num_comidas,
                    momento_entreno: antes.momento_entreno, opcion_peri: antes.opcion_peri, comidas: antes.comidas } });
    }
    await limpio.close();
    console.log('\ndía repuesto');
})();
