/**
 * «AL PULSAR APLICAR EN UNA FAVORITA» (doc del 3-09), contra la app.
 *
 * Los cuatro casos y los cinco detalles del documento, uno a uno y en el navegador. La
 * regla del documento: la app mira DOS cosas -- si el dia ya tiene comidas y si la
 * favorita es del mismo tipo de dia --, cada una anade su frase, y van siempre antes de
 * los botones y en este orden: PRIMERO LO QUE SE PIERDE, DESPUES EL TIPO DE DIA.
 *
 *   1  dia vacio + favorita del mismo tipo   -> sin aviso, se aplica y ya
 *   2  dia vacio + favorita de otro tipo     -> la frase del tipo y los dos botones
 *   3  dia con comidas + favorita del mismo  -> la frase de lo que se pierde y «Aplicar»
 *   4  dia con comidas + favorita de otro    -> las dos frases y los botones del caso 2
 *
 * Se monta todo por API en dias apartados y con favoritas propias, para no tocar las del
 * cliente de pruebas ni los dias que miran otras pruebas.
 *
 * Uso:  node _guia/_probar_aplicar_favorita.js
 */
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = { correo: 'francisco@test.com', clave: 'demo123' };

const DIA_VACIO_ENTRENO = '2026-09-20';
const DIA_LLENO_ENTRENO = '2026-09-21';
const DIA_VACIO_DESCANSO = '2026-09-22';

const FAV_ENTRENO = 'zz prueba entreno';
const FAV_DESCANSO = 'zz prueba descanso';

let fallos = 0;
const bien = (t) => console.log(`   OK   ${t}`);
const mal = (t) => { fallos++; console.log(`   MAL  ${t}`); };

let token = null;
const api = async (ruta, metodo = 'GET', cuerpo = undefined) => {
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

    const pollo = { alimento_id: 119, nombre: 'Carne picada de pechuga de pollo', cantidad_g: 150 };
    const arroz = { alimento_id: 48, nombre: 'Arroz Integral con quinoa', cantidad_g: 120 };
    const comida = () => ({ alimentos: [{ ...pollo }, { ...arroz }] });

    // ── Las dos favoritas, recien hechas ──
    for (const f of (await api('/api/diets/favorites?ambito=dia')).favorites || []) {
        if ((f.name || '').startsWith('zz prueba')) await api(`/api/diets/favorites/${f.id}`, 'DELETE');
    }
    const favs = {};
    for (const [nombre, tipo, peri] of [[FAV_ENTRENO, 'entrenamiento', 'intra_post'],
                                        [FAV_DESCANSO, 'descanso', null]]) {
        const r = await api('/api/diets/favorites', 'POST', {
            name: nombre, tipo_dia: tipo, num_comidas: 4,
            momento_entreno: tipo === 'descanso' ? null : 1, opcion_peri: peri,
            comidas: { C1: comida(), C2: comida(), C3: comida(), C4: comida() },
        });
        favs[tipo] = r.favorite.id;
    }
    console.log(`favoritas: entreno ${favs.entrenamiento} · descanso ${favs.descanso}`);

    // ── Los dias ──
    const dia = (fecha, tipo, comidas) => api('/api/diets', 'POST', {
        fecha, tipo_dia: tipo, num_comidas: 4,
        momento_entreno: tipo === 'descanso' ? null : 1,
        opcion_peri: tipo === 'descanso' ? null : 'intra_post',
        comidas,
    });
    await dia(DIA_VACIO_ENTRENO, 'entrenamiento', { C1: { alimentos: [] }, C2: { alimentos: [] },
                                                    C3: { alimentos: [] }, C4: { alimentos: [] } });
    await dia(DIA_LLENO_ENTRENO, 'entrenamiento', { C1: comida(), C2: comida(), C3: comida(),
                                                    C4: { alimentos: [] } });
    await dia(DIA_VACIO_DESCANSO, 'descanso', { C1: { alimentos: [] }, C2: { alimentos: [] },
                                                C3: { alimentos: [] }, C4: { alimentos: [] } });

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 1280, height: 1200 },
                                            locale: 'es-ES', timezoneId: 'Europe/Madrid' })).newPage();
    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, token);

    const abrirFavoritas = async (fecha) => {
        await p.goto(`${APP}/dashboard/nutrition?date=${fecha}`, { waitUntil: 'networkidle' });
        await p.waitForTimeout(11000);
        // Las favoritas se abren por el boton «Favoritas» de la parrilla del dia vacio o,
        // si el dia ya tiene comidas, por el menu de la pantalla.
        const boton = p.getByRole('button', { name: /^Favoritas$/ }).first();
        if (await boton.count()) { await boton.click(); }
        else {
            await p.locator('[data-testid="menu-pantalla"]').first().click();
            await p.locator('[data-testid="menu-pantalla-favoritas"]').first().click();
        }
        await p.waitForTimeout(1200);
    };
    const panel = (id) => p.locator(`[data-testid="fav-adapt-panel-${id}"]`).first();
    const texto = async (loc) => (await loc.count()) ? (await loc.innerText()).replace(/\s+/g, ' ').trim() : null;

    // ───────────────────────────────────────────────────────────────────────
    console.log('\ncaso 2 · Dia vacio y favorita de otro tipo (entreno, favorita de descanso)');
    await abrirFavoritas(DIA_VACIO_ENTRENO);
    {
        await p.locator(`[data-testid="fav-apply-${favs.descanso}"]`).click();
        await p.waitForTimeout(600);
        const t = await texto(panel(favs.descanso));
        console.log('   aviso: ' + t);
        if (!t) { mal('no sale el aviso'); }
        else {
            if (t.includes('Esta favorita es de día de descanso; hoy tienes entreno.')) bien('la frase del tipo de dia, literal');
            else mal('la frase del tipo de dia no es la del documento');
            if (t.includes('ya tiene')) mal('dice lo que se pierde en un dia VACIO');
            else bien('no habla de lo que se pierde: el dia esta vacio');
            // Detalle 2: de descanso a entreno, el peri SE ANADE vacio.
            if (t.includes('se añaden el intra y el post, que tendrás que rellenar')) bien('la linea gris, en el sentido que toca');
            else mal('la linea gris no es la del sentido descanso -> entreno');
            for (const frase of ['Aplicar y adaptar a mi día de hoy',
                                 'Aplicar como se guardó (pasa el día a descanso)', 'Cancelar']) {
                if (t.includes(frase)) bien(`boton «${frase}»`); else mal(`falta «${frase}»`);
            }
            await panel(favs.descanso).screenshot({ path: '_guia/_fav_caso2.png' });
        }

        // Detalle 4: los dos que aplican son BOTONES, Cancelar es un enlace en gris sin caja.
        const pinta = await p.evaluate((id) => {
            const caja = document.querySelector(`[data-testid="fav-adapt-panel-${id}"]`);
            const mide = (el) => { const s = getComputedStyle(el);
                return { fondo: s.backgroundColor, borde: s.borderTopWidth, subrayado: s.textDecorationLine }; };
            const botones = [...caja.querySelectorAll('button')];
            const cancelar = botones.find(b => b.innerText.trim() === 'Cancelar');
            const aplican = botones.filter(b => b !== cancelar);
            return { aplican: aplican.map(mide), cancelar: cancelar ? mide(cancelar) : null };
        }, favs.descanso);
        console.log('   pinta: ' + JSON.stringify(pinta));
        const transparente = (c) => /rgba\(0, 0, 0, 0\)|transparent/.test(c);
        if (pinta.aplican[0] && !transparente(pinta.aplican[0].fondo)) bien('el primero, relleno');
        else mal('el primer boton no esta relleno');
        if (pinta.aplican[1] && transparente(pinta.aplican[1].fondo) && parseFloat(pinta.aplican[1].borde) > 0) bien('el segundo, solo con el borde');
        else mal('el segundo boton no es solo borde');
        if (pinta.cancelar && transparente(pinta.cancelar.fondo) && parseFloat(pinta.cancelar.borde) === 0) bien('Cancelar, sin caja');
        else mal('Cancelar tiene caja');

        // Detalle 5: Cancelar cierra el aviso y deja la lista abierta.
        await p.getByRole('button', { name: 'Cancelar' }).first().click();
        await p.waitForTimeout(400);
        if (!(await panel(favs.descanso).count())) bien('Cancelar cierra el aviso');
        else mal('Cancelar no cierra el aviso');
        if (await p.locator(`[data-testid="fav-apply-${favs.descanso}"]`).count()) bien('y deja la lista de favoritas abierta');
        else mal('Cancelar cierra las favoritas enteras');

        // Y volver a pulsar Aplicar en esa favorita tambien lo cierra.
        await p.locator(`[data-testid="fav-apply-${favs.descanso}"]`).click();
        await p.waitForTimeout(400);
        await p.locator(`[data-testid="fav-apply-${favs.descanso}"]`).click();
        await p.waitForTimeout(400);
        if (!(await panel(favs.descanso).count())) bien('volver a pulsar Aplicar lo cierra tambien');
        else mal('volver a pulsar Aplicar no lo cierra');
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\ncaso 1 · Dia vacio y favorita del mismo tipo: sin aviso');
    {
        await p.locator(`[data-testid="fav-apply-${favs.entrenamiento}"]`).click();
        await p.waitForTimeout(3500);
        if (await panel(favs.entrenamiento).count()) mal('sale aviso y no debe salir');
        else bien('no sale aviso');
        const puestas = await p.locator('[data-testid^="meal-card-"]').count();
        if (puestas) bien(`se aplico (${puestas} comidas en pantalla)`);
        else mal('no parece que se haya aplicado');
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\ncaso 3 · Dia con comidas y favorita del mismo tipo');
    await abrirFavoritas(DIA_LLENO_ENTRENO);
    {
        await p.locator(`[data-testid="fav-apply-${favs.entrenamiento}"]`).click();
        await p.waitForTimeout(600);
        const t = await texto(panel(favs.entrenamiento));
        console.log('   aviso: ' + t);
        if (!t) { mal('no sale el aviso: el dia tiene comidas y se van a perder'); }
        else {
            if (t.includes('Este día ya tiene 3 comidas. Al aplicar la favorita se borran y se quedan las de la favorita.'))
                bien('la frase de lo que se pierde, literal y CON EL NUMERO');
            else mal('la frase de lo que se pierde no es la del documento');
            if (t.includes('hoy tienes')) mal('habla del tipo de dia y es el mismo');
            else bien('no habla del tipo de dia: es el mismo');
            const botones = t.split('\n').map(x => x.trim());
            if (t.includes('Aplicar') && !t.includes('Aplicar y adaptar')) bien('un solo boton, «Aplicar»');
            else mal('los botones no son los del caso 3');
            if (t.includes('Cancelar')) bien('y Cancelar'); else mal('falta Cancelar');
            await panel(favs.entrenamiento).screenshot({ path: '_guia/_fav_caso3.png' });
        }
        await p.getByRole('button', { name: 'Cancelar' }).first().click();
        await p.waitForTimeout(400);
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\ncaso 4 · Dia con comidas y favorita de otro tipo: las DOS frases, en orden');
    {
        await p.locator(`[data-testid="fav-apply-${favs.descanso}"]`).click();
        await p.waitForTimeout(600);
        const t = await texto(panel(favs.descanso));
        console.log('   aviso: ' + t);
        if (!t) { mal('no sale el aviso'); }
        else {
            const iPierde = t.indexOf('Este día ya tiene');
            const iTipo = t.indexOf('Esta favorita es de día de');
            if (iPierde >= 0) bien('esta la frase de lo que se pierde'); else mal('falta lo que se pierde');
            if (iTipo >= 0) bien('esta la frase del tipo de dia'); else mal('falta el tipo de dia');
            if (iPierde >= 0 && iTipo > iPierde) bien('y en ese orden: primero lo que se pierde');
            else mal('el orden de las dos frases no es el del documento');
            if (t.includes('Aplicar y adaptar a mi día de hoy')) bien('los botones son los del caso 2');
            else mal('no salen los botones del caso 2');
            await panel(favs.descanso).screenshot({ path: '_guia/_fav_caso4.png' });
        }
        await p.getByRole('button', { name: 'Cancelar' }).first().click();
        await p.waitForTimeout(400);
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\ndetalle 2 · La linea gris, en el otro sentido (dia de descanso, favorita de entreno)');
    await abrirFavoritas(DIA_VACIO_DESCANSO);
    {
        await p.locator(`[data-testid="fav-apply-${favs.entrenamiento}"]`).click();
        await p.waitForTimeout(600);
        const t = await texto(panel(favs.entrenamiento));
        console.log('   aviso: ' + t);
        if (t && t.includes('Esta favorita es de día de entreno; hoy tienes descanso.')) bien('la frase del tipo, literal');
        else mal('la frase del tipo no es la del documento');
        if (t && t.includes('el intra y el post se quitan')) bien('la linea gris dice que se QUITAN');
        else mal('la linea gris no es la del sentido entreno -> descanso');
        if (t && t.includes('Aplicar como se guardó (pasa el día a entreno)')) bien('el segundo boton nombra el tipo de la favorita');
        else mal('el segundo boton no dice a que pasa el dia');

        // Detalle 3: al adaptar de descanso a entreno, el peri se anade VACIO y el dia
        // queda sin cuadrar de entrada. Se comprueba aplicando de verdad.
        console.log('\ndetalle 3 · De descanso a entreno el peri se anade vacio, y el dia no cuadra');
    }
    await abrirFavoritas(DIA_VACIO_ENTRENO);
    {
        await p.locator(`[data-testid="fav-apply-${favs.descanso}"]`).click();
        await p.waitForTimeout(600);
        await p.locator(`[data-testid="fav-adapt-${favs.descanso}"]`).click();
        // Los avisos que salen al aplicar. El detalle 3 dice que el dia queda sin cuadrar y
        // que «no hace falta avisar aparte», asi que hay que saber cuales salen de verdad.
        const dichos = new Set();
        for (let i = 0; i < 14; i++) {
            await p.waitForTimeout(500);
            for (const t of await p.locator('[data-sonner-toast][data-visible="true"]').allInnerTexts()) {
                dichos.add(t.replace(/\s+/g, ' ').trim());
            }
        }
        console.log('   avisos: ' + (dichos.size ? [...dichos].map(x => `«${x}»`).join(' · ') : '(ninguno)'));
        const peri = await p.evaluate(() => ['Intra', 'Post'].map((k) => {
            const c = document.querySelector(`[data-testid="meal-card-${k}"]`);
            return { comida: k, esta: !!c, texto: c ? (c.innerText || '').replace(/\s+/g, ' ').slice(0, 90) : null };
        }));
        console.log('   peri: ' + JSON.stringify(peri));
        if (peri.every(x => x.esta)) bien('el intra y el post estan en la pantalla');
        else mal('el peri no se ha anadido');
        const dia = await texto(p.locator('[data-testid="dia-resumen"]').first());
        console.log('   dia: ' + dia);
        if (dia && /faltan/i.test(dia)) bien('y el dia queda sin cuadrar, como dice el documento');
        else mal('el dia no dice que falte nada');
        await p.screenshot({ path: '_guia/_fav_detalle3.png' });
    }

    console.log(`\n${fallos ? `${fallos} FALLOS` : 'los cuatro casos y los cinco detalles, bien'}`);
    await nav.close();
    process.exit(fallos ? 1 : 0);
})();
