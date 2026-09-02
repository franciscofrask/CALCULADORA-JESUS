/**
 * EL OBJETIVO DEL DIA, AL ABRIR (hallazgo 02 de la revision de Nutricion del 1-09).
 *
 * En un dia de descanso la cabecera arrancaba pidiendo los macros de un dia de ENTRENO, y no
 * se corregia sola: habia que tocar el selector Entreno/Descanso. El motivo era que el
 * efecto que vuelve a pedir el reparto leia `loading` pero NO lo tenia en sus dependencias,
 * asi que cuando la rutina cambiaba el tipo -- con la pantalla todavia cargando -- ese
 * reparto no se pedia nunca.
 *
 * Aqui se fuerza UNA cosa: que su rutina diga que hoy toca descanso. Lo que se comprueba es
 * lo que la app pide y lo que enseña, que no lo escribe este guion.
 *
 * OJO CON LO QUE ESTE GUION PRUEBA Y LO QUE NO. Pasa tambien con el codigo de antes del
 * arreglo del efecto, y no es que el arreglo sobre: es que la carrera que producia el fallo
 * la cerro el commit anterior (50e0e49), al hacer que el detector del tipo de dia corra
 * DESPUES de cargar y solo en los dias que nadie ha configurado. Lo que añade el arreglo del
 * efecto es que la pantalla se corrija sola si alguna vez lo que se ve deja de coincidir con
 * el ultimo reparto pedido, venga por donde venga. Esto queda como prueba de que el
 * comportamiento es el bueno, no como prueba de ese arreglo.
 *
 * Uso:  node _guia/_probar_objetivo_del_dia.js
 */
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CLIENTE = { correo: 'clientedemo@test.com', clave: 'demo123' };
//: Un dia sin dieta montada: el tipo lo tiene que poner la rutina, que es el caso del fallo.
const DIA_LIBRE = '2026-09-12';

const DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];

(async () => {
    let fallos = 0;
    const bien = (t) => console.log(`   OK   ${t}`);
    const mal = (t) => { fallos++; console.log(`   MAL  ${t}`); };

    const token = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CLIENTE.correo, password: CLIENTE.clave }),
    }).then((r) => r.json()).then((r) => r.access_token);

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 390, height: 1600 },
                                            locale: 'es-ES', timezoneId: 'Europe/Madrid' })).newPage();

    // Su rutina: TODOS los dias de descanso. Es el estado de partida del fallo.
    await p.route('**/api/routines/current*', (route) => route.fulfill({
        status: 200,
        json: { id: 'de-mentira', days: DIAS.map((d) => ({ day: d, is_rest: true, ejercicios: [] })) },
    }));

    // Lo que la pantalla le PIDE al servidor, que es donde se ve el fallo.
    const repartos = [];
    p.on('request', (r) => {
        if (r.url().includes('/api/calculator/distribute') && r.method() === 'POST') {
            try { repartos.push(JSON.parse(r.postData() || '{}').tipo_dia); } catch { /* */ }
        }
    });

    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, token);
    await p.goto(`${APP}/dashboard/nutrition?date=${DIA_LIBRE}`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(11000);

    // Lo que se ve arriba, sin tocar nada.
    const alAbrir = await p.evaluate(() => {
        const t = (id) => document.querySelector(`[data-testid="${id}"]`)?.innerText?.trim() || null;
        const marcado = document.querySelector('[data-testid="tipo-dia-descanso"]');
        return { P: t('dia-P'), H: t('dia-H'), G: t('dia-G'),
                 enDescanso: marcado ? /FF671F|bg-brand/.test(marcado.className) : null };
    });
    console.log('   repartos pedidos:', repartos.join(' · ') || '(ninguno)');
    console.log('   al abrir:', JSON.stringify(alAbrir));

    if (alAbrir.enDescanso) bien('la pantalla abre marcando Descanso, como dice su rutina');
    else mal('la pantalla abre en Entreno con una rutina que dice descanso');
    if (repartos.length && repartos[repartos.length - 1] === 'descanso') {
        bien('el ultimo reparto que pidio es el de DESCANSO');
    } else {
        mal(`el reparto del tipo bueno no se llego a pedir (pidio: ${repartos.join(', ')})`);
    }

    // Y ahora se toca el selector, que es lo que antes lo arreglaba: si el objetivo cambia,
    // es que lo de antes estaba mal.
    const antes = { P: alAbrir.P, H: alAbrir.H, G: alAbrir.G };
    await p.locator('[data-testid="tipo-dia-entrenamiento"]').first().click({ force: true }).catch(() => {});
    await p.waitForTimeout(3000);
    await p.locator('[data-testid="tipo-dia-descanso"]').first().click({ force: true }).catch(() => {});
    await p.waitForTimeout(4000);
    const despues = await p.evaluate(() => {
        const t = (id) => document.querySelector(`[data-testid="${id}"]`)?.innerText?.trim() || null;
        return { P: t('dia-P'), H: t('dia-H'), G: t('dia-G') };
    });
    console.log('   tras tocar el selector:', JSON.stringify(despues));
    if (JSON.stringify(antes) === JSON.stringify(despues)) {
        bien('tocar el selector ya no cambia nada: al abrir ya era el bueno');
    } else {
        mal('tocar el selector cambia el objetivo: al abrir estaba el del tipo equivocado');
    }

    await nav.close();
    console.log(fallos ? `\n${fallos} comprobacion(es) MAL` : '\nTodo bien');
    process.exit(fallos ? 1 : 0);
})();
