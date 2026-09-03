/**
 * EL INFORME DEL MES, EN PANTALLA Y ENTERO.
 *
 * Abre Seguimiento -> Reportes con la cuenta de pruebas, entra en «Ver mi informe del mes»
 * y saca la captura. Comprueba de paso las tres cosas que fallaban:
 *
 *   la semana del ciclo    tiene que ser la de verdad, no «Semana 1» para todo el mundo
 *   Tus medidas            sale si el reporte trae medidas
 *   Tus fotos              sale si la cuenta tiene fotos subidas
 *
 * Antes: backend/venv/Scripts/python.exe _guia/_dejar_un_informe.py
 */
const { chromium } = require('playwright');

const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';

(async () => {
    const token = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'francisco@test.com', password: 'demo123' }),
    }).then(r => r.json()).then(r => r.access_token);

    const nav = await chromium.launch();
    const ctx = await nav.newContext({
        viewport: { width: 390, height: 1400 }, locale: 'es-ES', timezoneId: 'Europe/Madrid',
    });
    const p = await ctx.newPage();
    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, token);
    await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(10000);
    // El recorrido de bienvenida tapa la pantalla; se salta.
    for (let i = 0; i < 4; i++) {
        const s = p.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => { });
        await p.waitForTimeout(800);
    }

    await p.goto(`${APP}/dashboard/reports`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(5000);
    const historial = p.locator('[data-testid="seg-historial"]');
    if (await historial.count()) { await historial.click(); await p.waitForTimeout(3000); }

    const ver = p.locator('[data-testid^="ver-informe-"]').first();
    if (!(await ver.count())) { console.log('NO hay boton de informe: ¿dejaste el reporte?'); await nav.close(); return; }
    await ver.click();
    await p.waitForTimeout(5000);

    const texto = (await p.locator('[data-testid="informe-del-mes"]').innerText()).replace(/\s+/g, ' ');
    const di = (que, ok) => console.log(`${ok ? 'OK  ' : 'MAL '} ${que}`);

    // El rotulo se pinta en mayusculas por CSS, y `innerText` devuelve lo transformado.
    const ciclo = texto.match(/TU CICLO (Semana \d+(?: de \d+)?)/i);
    console.log(`el ciclo dice: ${ciclo ? ciclo[1] : '(nada)'}`);
    di('la semana NO es la 1 de todo el mundo', !!ciclo && !/Semana 1 de/.test(ciclo[1]));
    di('sale el bloque «Tus medidas»', await p.locator('[data-testid="informe-medidas"]').count() > 0);
    di('sale el bloque «Tus fotos»', await p.locator('[data-testid="informe-fotos"]').count() > 0);
    di('las medidas traen las dos columnas', /Mes ant/.test(texto) && /1ª toma/.test(texto));

    await p.screenshot({ path: '_guia/_mi_informe.png', fullPage: true });
    await nav.close();
})();
