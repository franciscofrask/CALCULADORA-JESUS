/**
 * Comprueba los puntos 2.2, 2.3 y 2.4 del documento de Jesus (05-08) en la ficha del coach:
 *   2.2 el peso del ajuste es el ACTUAL, con la comparacion contra el del ajuste anterior
 *   2.3 la fecha por defecto es MANANA, no hoy
 *   2.4 pide confirmacion al guardar macros
 *
 * Uso:  node _internos_proceso/_ver_editor_macros.js
 */
const { chromium } = require('playwright');

const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const ADMIN = { email: 'francisco@test.com', password: 'demo123' };

const iso = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);

(async () => {
    const tok = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(ADMIN),
    }).then(r => r.json()).then(d => d.access_token);
    const lista = await fetch(`${API}/api/admin/clients`, { headers: { Authorization: `Bearer ${tok}` } })
        .then(r => r.json()).then(c => Array.isArray(c) ? c : (c.clients || c.items || []));
    // Un cliente con peso y con historial, que es donde se ve la comparacion
    let elegido = null;
    for (const c of lista.slice(0, 40)) {
        const d = await fetch(`${API}/api/admin/clients/${c.id}`, { headers: { Authorization: `Bearer ${tok}` } }).then(r => r.json());
        // Hace falta que el HISTORIAL traiga pesos: si no, no hay con que comparar
        const conPeso = (d.macro_history || []).filter(h => typeof (h.peso ?? h.client_weight) === 'number');
        if (d.profile?.weight && conPeso.length > 2) { elegido = { id: c.id, peso: d.profile.weight, n: d.macro_history.length, conPeso: conPeso.length }; break; }
    }
    console.log(`cliente: ${elegido.id} · peso en ficha ${elegido.peso} kg · ${elegido.n} ajustes`);

    const browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
    await page.goto(`${APP}/login`);
    await page.fill('input[type="email"]', ADMIN.email);
    await page.fill('input[type="password"]', ADMIN.password);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/admin**', { timeout: 20000 });
    await page.goto(`${APP}/admin/clients/${elegido.id}`);
    await page.waitForTimeout(4000);
    const tab = page.getByRole('tab', { name: /macros/i });
    if (await tab.count()) { await tab.first().click(); await page.waitForTimeout(2500); }

    const manana = iso(new Date(Date.now() + 86400000));
    const fecha = await page.locator('[data-testid="macro-effective-date"]').inputValue();
    console.log(`\n2.3 · fecha por defecto: ${fecha} (manana es ${manana}) -> ${fecha === manana ? 'CORRECTO' : '*** MAL ***'}`);

    const peso = await page.locator('[data-testid="macro-peso"]').inputValue();
    console.log(`2.2 · peso precargado: ${peso} (ficha ${elegido.peso}) -> ${parseFloat(peso) === elegido.peso ? 'CORRECTO' : '*** MAL ***'}`);

    // La comparacion contra el peso del ajuste anterior
    const txt = await page.locator('body').innerText();
    const comp = txt.match(/Últimos macros: [\d.]+ kg · (ha ganado [\d.]+ kg|ha perdido [\d.]+ kg|sin cambios)/);
    console.log(`2.2 · comparacion con el ajuste anterior: ${comp ? comp[0] : '*** no aparece ***'}`);

    // 2.4 · confirmacion al guardar
    await page.locator('[data-testid="macro-input-tp"]').fill('185');
    await page.locator('[data-testid="macro-note"]').fill('prueba de confirmacion');
    await page.waitForTimeout(800);
    await page.locator('[data-testid="save-macros-btn"]').click();
    await page.waitForTimeout(1500);
    const dlg = await page.locator('text=¿Guardar estos macros?').count();
    console.log(`\n2.4 · dialogo de confirmacion al guardar: ${dlg ? 'SALE' : '*** NO SALE ***'}`);
    if (dlg) {
        console.log('   texto:', (await page.locator('[role="alertdialog"], [role="dialog"]').first().innerText()).replace(/\n/g, ' | ').slice(0, 260));
        await page.screenshot({ path: '_internos_proceso/_editor_macros_confirm.png' });
        // Cancelar: no se guarda nada en la prueba
        const cancelar = page.getByRole('button', { name: /cancelar/i });
        if (await cancelar.count()) await cancelar.first().click();
    }
    console.log('\ncaptura -> _internos_proceso/_editor_macros_confirm.png');
    await browser.close();
})();
