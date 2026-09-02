/**
 * LOS HALLAZGOS 06 Y 08 DE LA REVISION DE NUTRICION DEL 1-09, probados reproduciendolos.
 *
 *   06  Marcar los 37 grupos a evitar y que la franja siga diciendo «podemos cuadrarte».
 *   08  El PDF dice «descargado» y deja un `.crdownload` que no se cierra nunca.
 *
 * NO SE TOCAN LAS PREFERENCIAS GUARDADAS: el 06 se comprueba contra el endpoint que
 * responde la franja, que es lo que decide lo que se ve, y no se llega a pulsar Guardar.
 *
 * QUE PRUEBA CADA UNA, Y QUE NO:
 *
 *   06  DISTINGUE. Con el codigo de antes falla («sigue diciendo que puede cuadrarte con el
 *       catalogo entero fuera») y con el arreglo pasa.
 *   08  NO DISTINGUE, y hay que saberlo: pasa igual antes y despues. Playwright se queda la
 *       descarga por su cuenta y no reproduce la carrera del `revokeObjectURL`, que se
 *       midio en un Chrome de verdad (un `.crdownload` de 6.768 bytes que no se cerraba).
 *       Se queda como red: comprueba que el PDF se descarga, que es un PDF y que llega
 *       entero.
 *
 * Uso:  node _guia/_probar_preferencias_y_pdf.js
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = { correo: 'francisco@test.com', clave: 'demo123' };
//: Un dia con dieta guardada de esa cuenta, que es lo que el PDF necesita.
const DIA = process.env.DIA || '2026-09-02';
//: Los 37 grupos de `routes/calculator.AVOIDABLE_PREFIXES`.
const TODOS_LOS_GRUPOS = ["grasas_buenas", "grasas_todo", "aperitivos", "arroces", "aves", "barritas", "bebidas", "isotonicas", "beb_vegetales", "bolleria", "cacao", "casqueria", "cerdo", "cereales", "chocolates", "cocina_esp", "comida_rapida", "embutidos", "fruta", "helados", "huevos", "lacteos", "legumbres", "carnes_blancas", "carnes_rojas", "panes", "pasta", "pescados", "pizza", "proteina_polvo", "proteina_vegetal", "salsas", "sopas", "superalimentos", "tuberculos", "vacuno", "verduras"];

const entrar = () => fetch(`${API}/api/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: CUENTA.correo, password: CUENTA.clave }),
}).then((r) => r.json()).then((r) => r.access_token);

(async () => {
    let fallos = 0;
    const bien = (t) => console.log(`   OK   ${t}`);
    const mal = (t) => { fallos++; console.log(`   MAL  ${t}`); };
    const token = await entrar();

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n06 · Marcarlo todo para evitar no puede decir que si');
    {
        const cuadra = (cuerpo) => fetch(`${API}/api/calculator/preferencias/cuadra`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify(cuerpo),
        }).then((r) => r.json());

        // Los 37 grupos que se pueden marcar. Son las claves de `AVOIDABLE_PREFIXES`,
        // que es la lista de la que salen las dos pestañas de preferencias.
        const todos = TODOS_LOS_GRUPOS;
        console.log(`   grupos que se pueden marcar: ${todos.length}`);

        const conTodo = await cuadra({ marcadas: todos });
        console.log(`   con todo marcado como PREFERIDO:  ${JSON.stringify(conTodo)}`);
        if (conTodo.proteina && conTodo.hidratos) bien('con el catálogo entero, dice que sí');
        else mal('con el catálogo entero dice que no: la prueba no vale');

        const todoFuera = await cuadra({ marcadas: todos, evitar_categorias: todos });
        console.log(`   y todo marcado además para EVITAR: ${JSON.stringify(todoFuera)}`);
        if (!todoFuera.proteina && !todoFuera.hidratos) {
            bien('marcándolo todo para evitar, la franja dice que NO se puede cuadrar');
        } else {
            mal('sigue diciendo que puede cuadrarte con el catálogo entero fuera');
        }

        // Y que no se pase de frenada: evitar una cosa suelta no puede tumbarlo todo.
        const soloUno = await cuadra({ marcadas: todos, evitar_categorias: [todos[0]] });
        console.log(`   evitando solo un grupo:            ${JSON.stringify(soloUno)}`);
        if (soloUno.proteina && soloUno.hidratos) bien('evitar un grupo suelto no tumba la franja');
        else mal('evitar un solo grupo ya dice que no se puede: se ha pasado de frenada');
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n08 · El PDF tiene que quedar como un PDF, no como un .crdownload');
    {
        const carpeta = fs.mkdtempSync(path.join(os.tmpdir(), 'pdf-'));
        const nav = await chromium.launch();
        const ctx = await nav.newContext({ viewport: { width: 390, height: 1400 },
                                           locale: 'es-ES', timezoneId: 'Europe/Madrid',
                                           acceptDownloads: true });
        const p = await ctx.newPage();
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, token);
        await p.goto(`${APP}/dashboard/nutrition?date=${DIA}`, { waitUntil: 'networkidle' });
        await p.waitForTimeout(10000);

        const esperando = p.waitForEvent('download', { timeout: 25000 }).catch(() => null);
        await p.locator('[data-testid="export-pdf-btn"]').first().click({ force: true }).catch(() => {});
        const descarga = await esperando;
        if (!descarga) {
            mal('no se llegó a descargar nada: la prueba no vale');
        } else {
            const destino = path.join(carpeta, descarga.suggestedFilename());
            // `saveAs` espera a que la descarga TERMINE. Si el navegador se queda esperando
            // datos que ya no existen -- que es el fallo -- aquí se cuelga y falla.
            let guardado = null;
            try { await descarga.saveAs(destino); guardado = destino; } catch (e) {
                mal(`la descarga no llegó a terminar: ${String(e).slice(0, 80)}`);
            }
            if (guardado) {
                const bytes = fs.statSync(guardado).size;
                const cabecera = fs.readFileSync(guardado).subarray(0, 5).toString();
                console.log(`   fichero: ${descarga.suggestedFilename()} · ${bytes} bytes · empieza por ${JSON.stringify(cabecera)}`);
                if (cabecera === '%PDF-') bien('el fichero es un PDF de verdad');
                else mal('lo descargado no es un PDF');
                if (bytes > 1000) bien(`y llega entero (${bytes} bytes)`);
                else mal(`el fichero se queda en ${bytes} bytes`);
            }
        }
        await nav.close();
        fs.rmSync(carpeta, { recursive: true, force: true });
    }

    console.log(fallos ? `\n${fallos} comprobacion(es) MAL` : '\nTodo bien');
    process.exit(fallos ? 1 : 0);
})();
