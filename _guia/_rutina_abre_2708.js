/**
 * LA RUTINA, QUE EN EL IPHONE NO ABRÍA (vídeo de Jesús del 27-08, minuto 6:06).
 *
 * «Tarda en abrirse, estoy tocando y no abre. No sé por qué. Toco y no abre. No abre la
 * rutina.» Y no salía ni aviso.
 *
 * CAUSA: `window.open` iba DESPUÉS del `await` que baja el fichero, así que para entonces el
 * navegador ya no lo cuenta como gesto del usuario y Safari lo bloquea en silencio.
 *
 * ESTO ES LO QUE HAY QUE PROBAR, y no «si abre en Chrome»: Chrome de escritorio no bloquea
 * nada, así que abriría igual con el fallo puesto. Lo que se comprueba es el ORDEN: que la
 * ventana se pide ANTES de que llegue el fichero. Si es así, el iPhone la deja pasar.
 *
 * Y de paso, que no quede ni una «PDF» delante del cliente (minuto 8:46: «olvida la palabra
 * PDF, eso no tiene sentido»).
 *
 * Uso:  node _guia/_rutina_abre_2708.js
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');

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

(async () => {
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 390, height: 900 } });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await r.json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };

    console.log('\n=== LA RUTINA · que abra y que no diga PDF ===\n');

    const info = await (await page.request.get(`${API}/api/routines/pdf/info`, { headers: cab })).json().catch(() => ({}));
    console.log('¿esta cuenta tiene rutina subida? ->', info?.hay ? 'sí' : 'no');

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);

    // EL ORDEN, MEDIDO DENTRO DE LA PÁGINA. Apuntarlo desde Node no vale: el aviso de que
    // llegó la respuesta cruza al proceso de fuera y vuelve, y para cuando se anota ya han
    // pasado milisegundos que no son los de verdad. Con el fallo puesto salía «bien» por eso.
    // Aquí se marcan las tres cosas en el mismo reloj: el toque, la ventana y el fichero.
    await page.addInitScript(() => {
        window.__orden = [];
        const apunta = (que) => window.__orden.push({ que, t: performance.now() });
        document.addEventListener('click', () => apunta('el toque'), true);
        const abrirDeVerdad = window.open;
        window.open = function (...args) {
            apunta('se pide la ventana');
            return abrirDeVerdad.apply(window, args);
        };
        // axios va por XHR: se marca cuando ESTA petición termina, en el reloj de la página.
        const enviar = XMLHttpRequest.prototype.send;
        const abrirXhr = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function (metodo, url, ...resto) {
            this.__url = String(url || '');
            return abrirXhr.call(this, metodo, url, ...resto);
        };
        XMLHttpRequest.prototype.send = function (...args) {
            if (/\/routines\/pdf(\?|$)/.test(this.__url || '')) {
                this.addEventListener('loadend', () => apunta('llega el fichero'));
            }
            return enviar.apply(this, args);
        };
    });

    await page.goto(`${APP}/dashboard/routine`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(8000);
    await quitarRecorrido(page);

    // Todos los textos que ve el cliente en esta pantalla.
    const texto = await page.locator('body').innerText();
    const conPdf = texto.split('\n').map(s => s.trim()).filter(s => /\bPDF\b/i.test(s));
    console.log(`\n«PDF» delante del cliente        -> ${conPdf.length === 0 ? 'ni una' : conPdf.join(' | ')}   ${ok(conPdf.length === 0)}`);
    console.log(`«tu entrenador te la ha preparado» -> ${/entrenador te la ha preparado/i.test(texto) ? 'SIGUE' : 'fuera'}   ${ok(!/entrenador te la ha preparado/i.test(texto))}`);

    // Y el orden, tocando el botón de abrir.
    const boton = page.locator('[data-testid="routine-pdf-btn"], [data-testid="semana-rutina-pdf"], [data-testid="routine-pdf-link"]').first();
    if (await boton.count()) {
        await boton.click();
        await page.waitForTimeout(6000);
        const orden = await page.evaluate(() => window.__orden || []);
        console.log('\nel orden de las cosas:');
        orden.forEach(o => console.log(`   ${Math.round(o.t)} ms · ${o.que}`));
        const iToque = orden.findIndex(o => o.que === 'el toque');
        const iVentana = orden.findIndex(o => o.que === 'se pide la ventana');
        const iFichero = orden.findIndex(o => o.que === 'llega el fichero');
        if (iVentana < 0) {
            console.log('   MAL: no se pidió ninguna ventana');
        } else if (iFichero < 0) {
            console.log('   la ventana se pidió y el fichero ya estaba descargado de antes   BIEN');
        } else {
            const enElToque = iVentana < iFichero;
            console.log(`   ¿la ventana ANTES del fichero? ${ok(enElToque)}   <- esto es lo que el iPhone exige`);
            if (iToque >= 0) {
                const salto = Math.round(orden[iVentana].t - orden[iToque].t);
                console.log(`   del toque a la ventana: ${salto} ms   ${ok(salto < 50)}   <- si no es casi cero, ya no cuenta como gesto`);
            }
        }
    } else {
        console.log('\n(esta cuenta no tiene rutina subida: el botón de abrir no sale)');
    }

    // Y en el Inicio, la línea.
    await page.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(8000);
    await quitarRecorrido(page);
    const inicio = await page.locator('body').innerText();
    const pdfEnInicio = inicio.split('\n').map(s => s.trim()).filter(s => /\bPDF\b/i.test(s));
    console.log(`\nen el INICIO, «PDF»              -> ${pdfEnInicio.length === 0 ? 'ni una' : pdfEnInicio.join(' | ')}   ${ok(pdfEnInicio.length === 0)}`);

    await page.screenshot({ path: '_guia/_rutina_sin_pdf.png', fullPage: true });
    console.log('\ncaptura -> _guia/_rutina_sin_pdf.png');
    await nav.close();
})();
