/**
 * «LOS DIAS SABADO Y DOMINGO POR DEFECTO SON DE DESCANSO» (Francisco, 3-09-2026).
 *
 * La app abria TODOS los dias en «Entreno». Medido en produccion el 09-08: de las 14.027
 * dietas guardadas, 14.025 decian «entrenamiento» y 2 «descanso», o sea que casi todo el
 * mundo comia de dia de entreno tambien los domingos -- 60 g de hidratos y 45 de
 * perientreno de mas.
 *
 * OJO, QUE HAY OTRA REGLA POR DELANTE Y COSTO VERLA: si el cliente tiene RUTINA asignada,
 * la pantalla ya le pone a cada dia el tipo que diga la rutina (`is_rest`). Eso no es un
 * valor por defecto -- alguien lo ha dicho --, asi que manda sobre esto. La regla del fin de
 * semana entra cuando nadie ha dicho nada: sin rutina, o con una que no cubra ese dia.
 *
 * Por eso aqui se responde `/api/routines/current` en vacio para la primera parte: es la
 * unica forma de ver el valor por defecto sin que la rutina lo tape. Y la segunda parte se
 * hace SIN tapar nada, para comprobar que la rutina sigue mandando.
 *
 * Las tres cosas que se miran:
 *
 *   · sin rutina, un dia sin configurar abre en descanso si es sabado o domingo;
 *   · con rutina, manda la rutina;
 *   · un dia YA configurado NO se toca. Es un valor por defecto, no un candado, y ademas
 *     pisarlo seria el fallo 01 de la revision del 1-09.
 *
 * Se mira en dias apartados y se limpia lo que monta.
 *
 * Uso:  node _guia/_probar_finde_descanso.js
 */
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = { correo: 'francisco@test.com', clave: 'demo123' };

// Lunes 12 a domingo 18 de octubre de 2026: una semana entera y lejos de todo.
const LUNES = '2026-10-12';
const DIAS = ['2026-10-12', '2026-10-13', '2026-10-14', '2026-10-15',
              '2026-10-16', '2026-10-17', '2026-10-18'];
const NOMBRE = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];
const SE_ESPERA = ['entrenamiento', 'entrenamiento', 'entrenamiento', 'entrenamiento',
                   'entrenamiento', 'descanso', 'descanso'];

let fallos = 0;
const bien = (t, d) => console.log(`   OK   ${t}${d ? `  [${d}]` : ''}`);
const mal = (t, d) => { fallos++; console.log(`   MAL  ${t}${d ? `  [${d}]` : ''}`); };

let token = null;
const api = async (ruta, metodo = 'GET', cuerpo) => {
    const r = await fetch(API + ruta, {
        method: metodo,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    });
    if (!r.ok) throw new Error(`${metodo} ${ruta} -> ${r.status} ${await r.text()}`);
    return r.json();
};

(async () => {
    token = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA.correo, password: CUENTA.clave }),
    }).then((r) => r.json()).then((r) => r.access_token);

    // Los siete dias, SIN dieta: es la unica forma de ver el valor por defecto.
    for (const d of DIAS) await api(`/api/diets/${d}`, 'DELETE').catch(() => {});

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 390, height: 1200 },
                                            locale: 'es-ES', timezoneId: 'Europe/Madrid' })).newPage();
    // SIN RUTINA, para poder ver el valor por defecto. Con la rutina de la cuenta de
    // pruebas -- que solo entrena el lunes -- todos los demas dias salen en descanso por
    // ella, y esta prueba diria que la regla funciona sin haberla probado.
    let tapandoLaRutina = true;
    await p.route('**/api/routines/current', (route) => (tapandoLaRutina
        ? route.fulfill({ status: 200, json: {} }) : route.continue()));

    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, token);

    // Cual esta marcado: el selector pinta el activo con el naranja de la casa.
    const marcado = async () => p.evaluate(() => {
        for (const v of ['entrenamiento', 'descanso']) {
            const e = document.querySelector(`[data-testid="tipo-dia-${v}"]`);
            if (!e) continue;
            const c = getComputedStyle(e);
            if (!/rgba\(0, 0, 0, 0\)|transparent/.test(c.backgroundColor)) return v;
        }
        return null;
    });

    console.log('\nUn dia que nadie ha configurado');
    for (let i = 0; i < DIAS.length; i++) {
        await p.goto(`${APP}/dashboard/nutrition?date=${DIAS[i]}`, { waitUntil: 'networkidle' });
        await p.waitForTimeout(i === 0 ? 11000 : 6000);
        const tiene = await marcado();
        const linea = `${NOMBRE[i]} ${DIAS[i]}: ${tiene}`;
        if (tiene === SE_ESPERA[i]) bien(linea);
        else mal(`${linea}, y se esperaba ${SE_ESPERA[i]}`);
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\nCon rutina, manda la rutina');
    tapandoLaRutina = false;
    {
        // La de esta cuenta solo entrena el lunes: sus martes son descanso POR LA RUTINA,
        // no por esta regla. Si algun dia esto empieza a fallar, mirar su rutina antes que
        // el codigo.
        const rutina = await api('/api/routines/current');
        const dias = Object.fromEntries((rutina.days || [])
            .map((d) => [String(d.day).toLowerCase(), !!d.is_rest]));
        console.log('   su rutina: ' + JSON.stringify(dias));
        // Un dia de diario que la rutina marque como descanso: sin ella abriria en entreno,
        // asi que si sale descanso es que la rutina ha mandado.
        const martes = DIAS[1];
        await p.goto(`${APP}/dashboard/nutrition?date=${martes}`, { waitUntil: 'networkidle' });
        await p.waitForTimeout(9000);
        const tiene = await marcado();
        const esperado = dias['martes'] ? 'descanso' : 'entrenamiento';
        if (tiene === esperado) bien(`el martes lo dice su rutina: ${tiene}`);
        else mal(`el martes sale ${tiene} y su rutina dice ${esperado}`);
        if (dias['martes'] && tiene === 'descanso')
            bien('y la rutina gana al valor por defecto, que ahí decía entreno');
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\nY un sabado que YA esta configurado no se toca');
    const sabado = DIAS[5];
    await api('/api/diets', 'POST', {
        fecha: sabado, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 1,
        opcion_peri: 'intra_post',
        comidas: { C1: { alimentos: [
            { alimento_id: 119, nombre: 'Carne picada de pechuga de pollo', cantidad_g: 150 }] } },
    });
    await p.goto(`${APP}/dashboard/nutrition?date=${sabado}`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(8000);
    const suyo = await marcado();
    if (suyo === 'entrenamiento') bien('el sábado que él puso en entreno sigue en entreno', suyo);
    else mal('le han pisado su decisión', String(suyo));
    await p.locator('[data-testid="dia-resumen"], [data-testid="macros-de-hoy"]').first()
        .screenshot({ path: '_guia/_finde_descanso.png' }).catch(() => {});

    // Se limpia lo que se monto.
    for (const d of DIAS) await api(`/api/diets/${d}`, 'DELETE').catch(() => {});

    console.log(`\n${fallos ? `${fallos} FALLOS` : 'el fin de semana abre en descanso'}`);
    await nav.close();
    process.exit(fallos ? 1 : 0);
})();
