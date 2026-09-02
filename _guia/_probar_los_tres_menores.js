/**
 * LOS TRES MENORES QUE QUEDABAN DE LA REVISION DE NUTRICION DEL 1-09.
 *
 *   menor 1  Los avisos se apilan y tapan la esquina: llego a haber tres a la vez encima
 *            del boton «···» de la comida y del panel de extras.
 *   menor 2  «Este dia se pasa de tus macros de ahora» cuando el dia se queda CORTO. El
 *            estado «sobra» se enciende con que UN macro se pase, y el 19 de agosto
 *            faltaban 199 g de proteina y 200 de hidratos con solo 7 de grasa de mas.
 *   menor 3  «Con lo que has marcado podemos cuadrarte 20 g de proteina» se lee como un
 *            techo cuando es un minimo de viabilidad.
 *
 * La cuenta es la de la revision (`francisco@test.com`). Los dias se montan por API en
 * fechas apartadas para no tocar los del calendario que se miran en otras pruebas.
 *
 * Uso:  node _guia/_probar_los_tres_menores.js
 */
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = { correo: 'francisco@test.com', clave: 'demo123' };

const DIA_CORTO = '2026-09-10';   // se pasa de hidratos y va corto de todo lo demas
const DIA_PASADO = '2026-09-11';  // solo se pasa: es el caso que dibuja la maqueta de Jesus

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

    // Arroz: mucho hidrato y casi nada de lo demas, que es justo lo que hace falta para
    // dejar el dia pasado de un macro y corto de los otros dos.
    const arroz = (await api('/api/calculator/foods?search=arroz&limit=40'))
        .find((f) => /arroz/i.test(f.nombre) && !/crema|tortita|leche|bebida|delicias|3 delicias/i.test(f.nombre));
    if (!arroz) throw new Error('no encuentro un arroz en el catalogo');
    console.log(`alimento: ${arroz.nombre} (id ${arroz.id})`);

    const comidaDeArroz = (g) => ({ alimentos: [{ alimento_id: arroz.id, nombre: arroz.nombre, cantidad_g: g }] });

    // ── El dia corto: cuatro comidas con arroz de sobra ──
    await api('/api/diets', 'POST', {
        fecha: DIA_CORTO, tipo_dia: 'descanso', num_comidas: 4, momento_entreno: null,
        opcion_peri: null,
        comidas: { C1: comidaDeArroz(400), C2: comidaDeArroz(400), C3: comidaDeArroz(400), C4: comidaDeArroz(400) },
    });

    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 1280, height: 1400 },
                                       locale: 'es-ES', timezoneId: 'Europe/Madrid' });
    const p = await ctx.newPage();
    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, token);

    const abrirDia = async (dia) => {
        await p.goto(`${APP}/dashboard/nutrition?date=${dia}`, { waitUntil: 'networkidle' });
        await p.waitForTimeout(11000);
    };

    // ───────────────────────────────────────────────────────────────────────
    console.log('\nmenor 2 · El titular dice lo que pasa, no siempre lo mismo');
    await abrirDia(DIA_CORTO);
    {
        const aviso = p.locator('[data-testid="banner-recuadrar"]').first();
        if (!(await aviso.count())) {
            mal('no sale el aviso: con 1.600 g de arroz el dia tiene que pasarse de hidratos');
        } else {
            const t = (await aviso.innerText()).toLowerCase();
            console.log('   texto: ' + t.replace(/\n/g, ' | '));
            if (t.includes('se pasa de tus macros')) {
                mal('sigue diciendo «se pasa» con el dia corto de proteina y de grasa');
            } else if (t.includes('no cuadra con tus macros')) {
                bien('dice «no cuadra», que es lo que pasa');
            } else {
                mal('no reconozco el titular');
            }
            if (/faltan .* g de/.test(t)) bien('y pone los numeros de lo que falta');
            else mal('no dice cuanto falta');
            await aviso.screenshot({ path: '_guia/_menor2_dia_corto.png' });
        }
    }

    // El caso de la maqueta de Jesus: pasarse SIN quedarse corto de nada. Se monta
    // cuadrando el dia con el propio motor y anadiendo despues un poco de arroz.
    console.log('\nmenor 2 · Y cuando de verdad solo se pasa, la frase suya no se toca');
    {
        // Con un dia de UNA comida el objetivo de la comida es el del dia entero, asi que
        // cuadrarla cuadra el dia. Y hacen falta las tres cosas: solo con arroz el motor se
        // queda a 300 g de proteina y el dia no llega a estar cuadrado nunca.
        //
        // El motor no clava el objetivo a la primera (queda a 10-25 g), asi que se corrige
        // con las CIFRAS QUE IMPRIME EL PROPIO AVISO: se lee lo que falta o sobra, se
        // reparte entre los tres alimentos y se vuelve a mirar. Se acaba con el dia pasado
        // solo de hidratos, que es el caso que dibuja la maqueta de Jesus.
        const base = { fecha: DIA_PASADO, tipo_dia: 'descanso', num_comidas: 1,
                       momento_entreno: null, opcion_peri: null };
        const POR_GRAMO = { P: { id: 119, nombre: 'Carne picada de pechuga de pollo' },
                            H: { id: arroz.id, nombre: arroz.nombre },
                            G: { id: 3, nombre: 'Aceite de oliva virgen extra una cucharada sopera' } };
        const rinde = {};
        for (const m of ['P', 'H', 'G']) {
            const e = (await api('/api/calculator/macros-efectivos', 'POST',
                { alimento_id: POR_GRAMO[m].id, cantidad_g: 100, es_vegano: false })).efectivos;
            rinde[m] = (e[m] || 0) / 100;   // gramos de ese macro por gramo de alimento
        }

        // El objetivo del dia, sacado del propio motor: `objetivo = servido - desfase`.
        const tanteo = await api('/api/calculator/refit-diet', 'POST', { ...base, comidas: { C1: { alimentos:
            ['P', 'H', 'G'].map((m) => ({ alimento_id: POR_GRAMO[m].id, nombre: POR_GRAMO[m].nombre,
                                          cantidad_g: 200 })) } } });
        const servido = (tanteo.comidas?.C1?.alimentos || []).reduce((a, x) => ({
            P: a.P + x.macros_efectivos.P, H: a.H + x.macros_efectivos.H, G: a.G + x.macros_efectivos.G,
        }), { P: 0, H: 0, G: 0 });
        const objetivo = Object.fromEntries(['P', 'H', 'G']
            .map((m) => [m, servido[m] - (tanteo.desfases?.C1?.[m] || 0)]));
        console.log(`   objetivo del dia: P ${objetivo.P} · H ${objetivo.H} · G ${objetivo.G}`);

        // Cada alimento cubre su macro, y de hidratos se pone de mas a proposito.
        const cant = { P: objetivo.P / rinde.P, H: (objetivo.H + 25) / rinde.H, G: objetivo.G / rinde.G };
        const leerDesfase = (texto) => {
            const d = { P: 0, H: 0, G: 0 };
            const clave = { 'proteína': 'P', hidratos: 'H', grasa: 'G' };
            for (const [, verbo, n, macro] of texto.matchAll(
                    /(faltan|sobran) ([\d.,]+) g de (proteína|hidratos|grasa)/g)) {
                d[clave[macro]] = (verbo === 'faltan' ? -1 : 1) * Number(n.replace(',', '.'));
            }
            return d;
        };

        let texto = null;
        for (let vuelta = 1; vuelta <= 4; vuelta++) {
            await api('/api/diets', 'POST', { ...base, comidas: { C1: { alimentos:
                ['P', 'H', 'G'].map((m) => ({ alimento_id: POR_GRAMO[m].id,
                                              nombre: POR_GRAMO[m].nombre,
                                              cantidad_g: Math.round(cant[m]) })) } } });
            await abrirDia(DIA_PASADO);
            const aviso = p.locator('[data-testid="banner-recuadrar"]').first();
            if (!(await aviso.count())) {
                console.log(`   vuelta ${vuelta}: sin aviso (el dia no se pasa todavia)`);
                cant.H += 25 / rinde.H;   // mas hidratos hasta que se pase
                continue;
            }
            texto = (await aviso.innerText()).toLowerCase();
            const d = leerDesfase(texto);
            console.log(`   vuelta ${vuelta}: P ${d.P} · H ${d.H} · G ${d.G}`
                        + `   [pollo ${Math.round(cant.P)} · arroz ${Math.round(cant.H)} · aceite ${Math.round(cant.G)}]`);
            // Ya es el caso que se busca. Se reconoce por el propio titular: si el aviso no
            // dice «no cuadra», es que no falta nada y el dia solo se pasa. Los numeros solo
            // salen en el otro caso, asi que aqui no hay nada que leer.
            if (!texto.includes('no cuadra con tus macros')) break;
            for (const m of ['P', 'G']) if (d[m] < 0) cant[m] += (-d[m]) / rinde[m];
            if (d.H <= 0) cant.H += (15 - d.H) / rinde.H;
            texto = null;
        }

        if (!texto) {
            mal('no consigo montar un dia que SOLO se pase: sin el, este caso no se prueba');
        } else {
            console.log('   texto: ' + texto.replace(/\n/g, ' | '));
            if (texto.includes('se pasa de tus macros de ahora')) bien('la frase de su maqueta, intacta');
            else mal('se ha perdido la frase de su maqueta en el caso que ella dibuja');
            await p.locator('[data-testid="banner-recuadrar"]').first()
                .screenshot({ path: '_guia/_menor2_dia_pasado.png' });
        }
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\nmenor 1 · Los avisos no pueden tapar lo que hay que pulsar');
    // EN MOVIL, que es donde muerde. En el escritorio de 1280 px la esquina de abajo a la
    // derecha esta vacia y no tapa nada; la revision iba por el telefono.
    const movil = await (await nav.newContext({ viewport: { width: 390, height: 844 },
                                                locale: 'es-ES', timezoneId: 'Europe/Madrid' })).newPage();
    await movil.goto(APP, { waitUntil: 'domcontentloaded' });
    await movil.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, token);
    await movil.goto(`${APP}/dashboard/nutrition?date=${DIA_CORTO}`, { waitUntil: 'networkidle' });
    await movil.waitForTimeout(11000);
    {
        const p = movil;
        // Se quita un ingrediente de tres comidas seguidas, que es lo que hacia la revision.
        //
        // OJO CON EL RELOJ: un aviso dura 6 s y el guion tarda mas que eso en dar los tres
        // toques, asi que al mirar al final no queda ninguno y la prueba pasaria sin haber
        // probado nada. Se cuenta el MAXIMO que llega a haber a la vez, mirando mientras.
        // OJO: sonner NO desmonta los avisos que pasan del tope, los deja en el DOM con
        // `data-visible=false`, sin opacidad y sin recibir clics. Contarlos todos daria
        // tres siempre y el tope pareceria no funcionar.
        const avisos = p.locator('[data-sonner-toast][data-visible="true"]');
        let ala_vez = 0;
        const mirar = async () => { ala_vez = Math.max(ala_vez, await avisos.count()); };

        for (const c of ['C1', 'C2', 'C3']) {
            // En el telefono las comidas son un acordeon (`meal-card-C1`) y hay que
            // abrirlas; la lista del escritorio (`meal-select-C1`) esta en el DOM pero
            // apagada por CSS, y pulsarla no hace nada. De ahi el `:visible`.
            const tarjeta = p.locator(`[data-testid="meal-card-${c}"]:visible`).first();
            if (await tarjeta.count()) {
                await tarjeta.scrollIntoViewIfNeeded();
                await tarjeta.click();
                await p.waitForTimeout(500);
            }
            await mirar();
            // VACIAR, no quitar un ingrediente: quitar no deja aviso ninguno (no lleva
            // `toast`), y el de vaciar dura 8 s porque trae «Deshacer». Es el unico que
            // aguanta lo bastante para que tres coincidan, que es el caso a mirar.
            const menu = p.locator(`[data-testid="meal-card-${c}"]:visible [data-testid="menu-pantalla"]:visible`).first();
            if (!(await menu.count())) { console.log(`   (no veo el menu de ${c})`); continue; }
            await menu.click();
            const vaciar = p.locator(`[data-testid="menu-pantalla-vaciar-${c}"]`).first();
            await vaciar.waitFor({ state: 'visible', timeout: 3000 }).catch(() => {});
            if (!(await vaciar.count())) { console.log(`   (no veo «Vaciar» en ${c})`); continue; }
            await vaciar.click();
            const ok = p.locator('[data-testid="confirm-ok"]').first();
            await ok.waitFor({ state: 'visible', timeout: 3000 }).catch(() => {});
            if (await ok.count()) await ok.click();
            await p.waitForTimeout(250);
            await mirar();
        }
        await mirar();

        console.log(`   avisos a la vez: ${ala_vez}`);
        if (!ala_vez) { mal('no salio ningun aviso: la prueba no ha probado nada'); }
        else if (ala_vez <= 2) bien(`nunca tres: como mucho ${ala_vez}`);
        else mal(`se ven ${ala_vez} a la vez`);

        // Y lo que de verdad importa: que no haya un aviso encima de un boton.
        const tapados = await p.evaluate(() => {
            const choca = (a, b) => !(a.right <= b.left || a.left >= b.right
                                   || a.bottom <= b.top || a.top >= b.bottom);
            const avisos = [...document.querySelectorAll('[data-sonner-toast][data-visible="true"]')]
                .map(e => e.getBoundingClientRect());
            const pulsables = [...document.querySelectorAll('button, a, input, [role="button"]')]
                .filter(e => e.offsetParent !== null && !e.closest('[data-sonner-toast]'));
            return pulsables
                .filter(e => avisos.some(a => choca(a, e.getBoundingClientRect())))
                .map(e => e.getAttribute('data-testid') || (e.innerText || e.ariaLabel || '').trim().slice(0, 30))
                .filter(Boolean);
        });
        if (!tapados.length) bien('ningun boton queda debajo de un aviso');
        else mal(`tapados: ${tapados.join(' · ')}`);
        await p.screenshot({ path: '_guia/_menor1_avisos.png' });
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\nmenor 3 · La franja de preferencias dice que es un minimo');
    {
        // Se abre por el menu de la pantalla, que es por donde se abre de verdad.
        await abrirDia(DIA_CORTO);
        await p.locator('[data-testid="menu-pantalla"]').first().click();
        const op = p.locator('[data-testid="menu-pantalla-preferencias"]').first();
        if (await op.count()) await op.click();
        await p.waitForTimeout(4000);
        const franja = p.locator('[data-testid="cuadra-en-vivo"]').first();
        if (!(await franja.count())) {
            mal('no consigo abrir la pantalla de preferencias');
        } else {
            const t = (await franja.innerText()).toLowerCase();
            console.log('   texto: ' + t.replace(/\n/g, ' | '));
            if (t.includes('podemos cuadrarte')) mal('sigue leyendose como un techo');
            else if (t.includes('como minimo') || t.includes('como mínimo')) bien('dice «como minimo»');
            else mal('no reconozco la frase');
            await franja.screenshot({ path: '_guia/_menor3_franja.png' });
        }
    }

    console.log(`\n${fallos ? `${fallos} FALLOS` : 'los tres, bien'}`);
    await nav.close();
    process.exit(fallos ? 1 : 0);
})();
