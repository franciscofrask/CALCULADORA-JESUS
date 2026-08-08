/**
 * Segunda pasada: la pestaña de Nutricion sin el modal de bienvenida, y los modales
 * que solo se ven al pulsar algo (buscador, calendario, menus, favoritas).
 *
 * Uso: node _capturas_guia2.js
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const SALIDA = path.join(__dirname, '_guia', 'capturas');
const CLIENTE = { email: 'clientedemo@test.com', password: 'demo123' };

async function entrar(page) {
    const r = await page.request.post(`${API}/api/auth/login`, { data: CLIENTE });
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => localStorage.setItem('token', t), access_token || token);
}

const foto = async (page, nombre) => {
    await page.screenshot({ path: path.join(SALIDA, `${nombre}.png`), fullPage: true });
    console.log('  ' + nombre);
};

(async () => {
    fs.mkdirSync(SALIDA, { recursive: true });
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await ctx.newPage();
    await entrar(page);

    // ── Nutricion ────────────────────────────────────────────────────────────
    // Primero se capturan las dos pantallas de bienvenida (primera dieta y tutorial),
    // y luego se marcan como vistas para poder llegar a la pantalla de verdad.
    await page.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(4500);
    if (await page.getByRole('button', { name: /Ver mi primera dieta/i }).count()) {
        await foto(page, '02a-nutricion-primera-dieta');
    }
    await page.evaluate(() => {
        localStorage.setItem('primera-dieta-hecha', '1');
        localStorage.setItem('nutrition-intro-seen', '1');
    });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(4500);
    await foto(page, '02b-nutricion-pantalla');

    // Las tres vistas de comidas (selector arriba a la derecha de "Comidas del día")
    for (const [id, nombre] of [['pestanas', '02c-nutricion-vista-pestanas'],
                                 ['continua', '02d-nutricion-vista-todo-seguido']]) {
        const b = page.locator(`button[title*="${id === 'pestanas' ? 'Pestañas' : 'Todo seguido'}"]`);
        if (await b.count()) { await b.first().click(); await page.waitForTimeout(1500); await foto(page, nombre); }
        else console.log(`  (no encontre el selector de vista ${id})`);
    }

    // Buscador de alimentos: se abre desde "Añadir ingrediente" o "Lo hago yo"
    const loHago = page.getByRole('button', { name: /Lo hago yo|Añadir ingrediente/i });
    if (await loHago.count()) {
        await loHago.first().click();
        await page.waitForTimeout(2500);
        await foto(page, '02e-nutricion-constructor-comida');
        await page.keyboard.press('Escape');
        await page.waitForTimeout(1200);
    }

    // Calendario del mes
    const cal = page.locator('[data-testid="open-calendar-btn"]');
    if (await cal.count()) {
        await cal.first().click(); await page.waitForTimeout(2000);
        await foto(page, '02f-nutricion-calendario');
        await page.keyboard.press('Escape'); await page.waitForTimeout(1000);
    }

    // ── Asistente IA: conversacion empezada ──────────────────────────────────
    await page.goto(`${APP}/dashboard/chatbot`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    const empezar = page.getByRole('button', { name: /^Empezar$/i });
    if (await empezar.count()) {
        await empezar.first().click();
        await page.waitForTimeout(4000);
        await foto(page, '03a-asistente-configurando');
    }

    // ── Ajustar macros: el quiz ──────────────────────────────────────────────
    await page.goto(`${APP}/dashboard/macro-calculator`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3500);
    await foto(page, '08a-ajustar-macros-detalle');

    await ctx.close();
    await nav.close();
    console.log('\nsegunda pasada lista');
})();
