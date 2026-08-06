/**
 * Comprueba la tabla de macros de la ficha del coach (peticion de Jesus 05-08, punto 2.1):
 * va ARRIBA del editor, lo que cambia respecto al ajuste anterior sale en rojo, el peso
 * maximo y el minimo van pintados, y el ajuste que se esta escribiendo aparece en gris.
 *
 * Uso:  node _internos_proceso/_ver_tabla_macros.js
 */
const { chromium } = require('playwright');

const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const ADMIN = { email: 'francisco@test.com', password: 'demo123' };

(async () => {
    // Cliente con mas historial de macros, que es donde se ve la escalera
    const tok = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ADMIN),
    }).then(r => r.json()).then(d => d.access_token);
    const cli = await fetch(`${API}/api/admin/clients`, { headers: { Authorization: `Bearer ${tok}` } }).then(r => r.json());
    const lista = Array.isArray(cli) ? cli : (cli.clients || cli.items || []);
    let mejor = null;
    for (const c of lista.slice(0, 40)) {
        const d = await fetch(`${API}/api/admin/clients/${c.id}`, { headers: { Authorization: `Bearer ${tok}` } }).then(r => r.json());
        const n = (d.macro_history || []).length;
        if (!mejor || n > mejor.n) mejor = { id: c.id, n, nombre: d.user?.name || d.user?.email };
    }
    console.log(`cliente con mas historial: ${mejor.nombre} (${mejor.n} ajustes)`);

    const browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
    await page.goto(`${APP}/login`);
    await page.fill('input[type="email"]', ADMIN.email);
    await page.fill('input[type="password"]', ADMIN.password);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/admin**', { timeout: 20000 });   // el admin aterriza en /admin
    await page.goto(`${APP}/admin/clients/${mejor.id}`);
    await page.waitForTimeout(4000);

    // Pestana de macros
    const tab = page.getByRole('tab', { name: /macros/i });
    if (await tab.count()) { await tab.first().click(); await page.waitForTimeout(2500); }

    // 1. Orden en la pagina: la tabla tiene que ir ANTES del editor
    const orden = await page.evaluate(() => {
        const txt = document.body.innerText;
        const t = txt.toUpperCase(); return { tabla: t.indexOf('HISTORIAL DE MACROS'), editor: t.indexOf('MACROS DEL CLIENTE') };
    });
    console.log(`\nposicion de "Historial de macros": ${orden.tabla} | de "Macros del cliente": ${orden.editor}`);
    console.log(orden.tabla >= 0 && orden.tabla < orden.editor ? '-> LA TABLA VA ARRIBA' : '-> *** la tabla NO va arriba ***');

    // 2. Numeros en rojo (los que cambiaron) y pesos pintados
    const rojos = await page.locator('td.text-red-400').count();
    const verTodo = await page.locator('[data-testid="macro-hist-ver-todo"]').innerText().catch(()=>'(sin boton)');
    console.log('boton de desplegar:', verTodo);
    const filasVisibles = await page.locator('tbody tr').count();
    console.log('filas a la vista:', filasVisibles);
    const pesoMax = await page.locator('[title="Peso máximo del recorrido"]').count();
    const pesoMin = await page.locator('[title="Peso mínimo del recorrido"]').count();
    console.log(`celdas en rojo (cambios): ${rojos} | peso maximo pintado: ${pesoMax} | peso minimo pintado: ${pesoMin}`);

    await page.screenshot({ path: '_internos_proceso/_tabla_macros.png', fullPage: false });

    // 3. Tocar un macro y ver la fila en gris
    const input = page.locator('[data-testid="macro-input-tp"]');
    if (await input.count()) {
        await input.fill('999');
        await page.waitForTimeout(1500);
        const borrador = await page.locator('[data-testid="macro-fila-borrador"]').count();
        console.log(`\ntras teclear un macro -> filas "sin guardar" en la tabla: ${borrador}`);
        console.log(borrador === 1 ? '-> LA FILA EN CURSO SE VE EN LA TABLA' : '-> *** no aparece la fila en curso ***');
        await page.screenshot({ path: '_internos_proceso/_tabla_macros_borrador.png', fullPage: false });
    } else {
        console.log('\n(no hay editor de macros en esta ficha)');
    }
    console.log('capturas -> _internos_proceso/_tabla_macros*.png');
    await browser.close();
})();
