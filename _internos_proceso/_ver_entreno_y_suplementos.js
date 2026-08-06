/**
 * Comprueba los puntos 2.5 y 2.7 del documento de Jesus (05-08):
 *   2.5 maquinaria, lesiones y observaciones EDITABLES en la pestana de Entreno
 *   2.7 los suplementos del catalogo se pueden editar (dosis, momento, observaciones)
 * Deja el cliente como estaba.
 *
 * Uso:  node _internos_proceso/_ver_entreno_y_suplementos.js
 */
const { chromium } = require('playwright');

const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const ADMIN = { email: 'francisco@test.com', password: 'demo123' };

(async () => {
    const tok = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(ADMIN),
    }).then(r => r.json()).then(d => d.access_token);
    const H = { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' };
    const lista = await fetch(`${API}/api/admin/clients`, { headers: H })
        .then(r => r.json()).then(c => Array.isArray(c) ? c : (c.clients || c.items || []));
    const id = lista[0].id;
    const antes = await fetch(`${API}/api/admin/clients/${id}`, { headers: H }).then(r => r.json());
    console.log(`cliente ${id}`);
    console.log(`  antes -> equipamiento: ${JSON.stringify(antes.profile?.equipment || [])} · lesiones: ${JSON.stringify(antes.profile?.injuries || [])} · notas: ${JSON.stringify(antes.profile?.training_notes || '')}`);

    const browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
    await page.goto(`${APP}/login`);
    await page.fill('input[type="email"]', ADMIN.email);
    await page.fill('input[type="password"]', ADMIN.password);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/admin**', { timeout: 20000 });
    await page.goto(`${APP}/admin/clients/${id}`);
    await page.waitForTimeout(4000);

    // ---- 2.5 · pestana de entreno
    await page.getByRole('tab', { name: /entreno/i }).first().click();
    await page.waitForTimeout(1500);
    await page.locator('[data-testid="equip-mancuernas"]').click();
    await page.locator('[data-testid="nueva-lesion"]').fill('hombro derecho (prueba)');
    await page.locator('[data-testid="nueva-lesion"]').press('Enter');
    await page.locator('[data-testid="entreno-notas"]').fill('sustituye sentadilla libre por hack (prueba)');
    await page.waitForTimeout(600);
    await page.locator('[data-testid="save-entreno-btn"]').click();
    await page.waitForTimeout(2500);

    const dsp = await fetch(`${API}/api/admin/clients/${id}`, { headers: H }).then(r => r.json());
    console.log(`\n2.5 · despues de guardar en la pestana Entreno:`);
    console.log(`  equipamiento: ${JSON.stringify(dsp.profile?.equipment || [])}`);
    console.log(`  lesiones: ${JSON.stringify(dsp.profile?.injuries || [])}`);
    console.log(`  observaciones: ${JSON.stringify(dsp.profile?.training_notes || '')}`);
    const ok25 = (dsp.profile?.injuries || []).includes('hombro derecho (prueba)')
        && (dsp.profile?.training_notes || '').includes('hack');
    console.log(`  -> ${ok25 ? 'GUARDA CORRECTAMENTE' : '*** NO GUARDA ***'}`);

    // ---- 2.7 · suplementos editables
    await page.getByRole('tab', { name: /suplementos/i }).first().click();
    await page.waitForTimeout(1500);
    // Si no tiene ninguno, se carga uno del catalogo: lo que quiere Jesus es poder tocar
    // justamente los que vienen cargados.
    let campos = await page.locator('[data-testid^="sup-cuanto-"]').count();
    if (campos === 0) {
        const sel = page.locator('select').filter({ hasText: 'Añadir del catálogo' }).first();
        const opciones = await sel.locator('option').count();
        if (opciones > 1) {
            await sel.selectOption({ index: 1 });
            await page.waitForTimeout(1200);
            campos = await page.locator('[data-testid^="sup-cuanto-"]').count();
            console.log('  (se carga uno del catalogo para la prueba)');
        }
    }
    console.log(`\n2.7 · campos de dosis editables en pantalla: ${campos}`);
    if (campos > 0) {
        const antesDosis = await page.locator('[data-testid^="sup-cuanto-"]').first().inputValue();
        await page.locator('[data-testid^="sup-cuanto-"]').first().fill('2 capsulas (prueba)');
        await page.locator('[data-testid^="sup-cuando-"]').first().fill('con la cena (prueba)');
        await page.waitForTimeout(500);
        const ahora = await page.locator('[data-testid^="sup-cuanto-"]').first().inputValue();
        console.log(`  dosis del catalogo: "${antesDosis}" -> editada a: "${ahora}"`);
        console.log(`  -> ${ahora === '2 capsulas (prueba)' ? 'LOS SUPLEMENTOS CARGADOS SE PUEDEN EDITAR' : '*** NO SE PUEDEN EDITAR ***'}`);
    } else {
        console.log('  (no hay catalogo de suplementos en dev: no se puede comprobar aqui)');
    }
    await page.screenshot({ path: '_internos_proceso/_entreno_suplementos.png' });

    // ---- limpieza: dejar el perfil como estaba
    await fetch(`${API}/api/admin/clients/${id}`, {
        method: 'PUT', headers: H,
        body: JSON.stringify({
            equipment: antes.profile?.equipment || [],
            injuries: Array.isArray(antes.profile?.injuries) ? antes.profile.injuries : [],
            training_notes: antes.profile?.training_notes || '',
        }),
    });
    const fin = await fetch(`${API}/api/admin/clients/${id}`, { headers: H }).then(r => r.json());
    console.log(`\nlimpieza -> lesiones: ${JSON.stringify(fin.profile?.injuries || [])} · notas: ${JSON.stringify(fin.profile?.training_notes || '')}`);
    await browser.close();
})();
