/**
 * «COMO ABRE INICIO» (doc de Jesus del 3-09), contra la app.
 *
 * Siete bloques: donde va el aviso de la dieta sin terminar, que sale en cada pestana de
 * «Tu dieta hoy» y de que color. Esto NO da nada por hecho: mira la pantalla y dice, de
 * cada punto, si esta o no esta, con el dato que lo prueba (el texto, el color calculado
 * del punto y de la barra, y la palabra de cada macro).
 *
 * Se monta un dia con cuatro comidas por API y se marcan a mano en la pantalla, que es la
 * unica forma de ver Llevas al empezar y Llevas al terminar.
 *
 * Uso:  node _guia/_probar_como_abre_inicio.js
 */
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = { correo: 'francisco@test.com', clave: 'demo123' };

const estan = [];
const faltan = [];
const esta = (t, dato) => { estan.push(t); console.log(`   ESTA    ${t}${dato ? `  [${dato}]` : ''}`); };
const falta = (t, dato) => { faltan.push(t); console.log(`   FALTA   ${t}${dato ? `  [${dato}]` : ''}`); };

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

    // El dia de HOY del navegador, que es con el que trabaja Inicio.
    const hoy = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
        .toISOString().slice(0, 10);
    const comida = () => ({ alimentos: [
        { alimento_id: 119, nombre: 'Carne picada de pechuga de pollo', cantidad_g: 150 },
        { alimento_id: 48, nombre: 'Arroz Integral con quinoa', cantidad_g: 120 },
    ] });
    // EL DIA VA CUADRADO A PROPOSITO. Con un dia corto, el gris de las barras es lo
    // CORRECTO («gris mientras va por debajo»), asi que no se puede saber si siguen el
    // estado o si son grises siempre, que es lo que dice el documento. Cuadrado, la barra
    // tiene que ponerse verde; y con un chorro de aceite de mas, naranja.
    const base = { fecha: hoy, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 1,
                   opcion_peri: 'intra_post' };
    const crudo = { C1: comida(), C2: comida(), C3: comida(), C4: comida() };
    const cuadrado = await api('/api/calculator/refit-diet', 'POST', { ...base, comidas: crudo });
    const comidas = {};
    for (const [k, v] of Object.entries(cuadrado.comidas || crudo)) comidas[k] = { alimentos: v.alimentos || [] };
    await api('/api/diets', 'POST', { ...base, comidas });
    // Y SE DESMARCA TODO. La marca de cada comida la guarda el SERVIDOR
    // (`comidas.{k}.marcada`), no el navegador, asi que limpiar el localStorage no sirve:
    // sin esto, la vuelta anterior deja el dia marcado y «Llevas al empezar» no se ve.
    for (const k of ['C1', 'C2', 'C3', 'C4', 'Intra', 'Post']) {
        await api(`/api/diets/${hoy}/comida-marcada`, 'PATCH', { comida: k, marcada: false });
    }
    const desf = cuadrado.desfases || {};
    console.log(`dia montado y cuadrado: ${hoy}`);
    console.log('   desfase por comida: ' + Object.entries(desf)
        .map(([k, d]) => `${k} ${['P','H','G'].map(m => `${m}${(d?.[m] ?? 0) > 0 ? '+' : ''}${d?.[m] ?? 0}`).join('/')}`)
        .join(' · '));

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 390, height: 900 },
                                            locale: 'es-ES', timezoneId: 'Europe/Madrid' })).newPage();
    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, token);
    await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(9000);

    const txt = async (sel) => {
        const l = p.locator(sel).first();
        return (await l.count()) ? (await l.innerText()).replace(/\s+/g, ' ').trim() : null;
    };
    // El color de verdad, el calculado, no la clase.
    const color = (sel) => p.evaluate((s) => {
        const e = document.querySelector(s);
        if (!e) return null;
        const c = getComputedStyle(e);
        return { fondo: c.backgroundColor, texto: c.color, clase: e.className };
    }, sel);

    // ───────────────────────────────────────────────────────────────────────
    // ANTES DE TOCAR NADA: ¿POR DONDE ABRE? El documento dice «Abre en Llevas, como
    // ahora», y de ahi cuelga su bloque 02 entero (el punto de 7 px se ve poco para el que
    // abre en Llevas y no toca Dieta). Si abre en Dieta, esa pega no existe.
    console.log('\n00 · La pestana por la que abre');
    const abre = await p.evaluate(() => {
        const a = [...document.querySelectorAll('[data-testid^="vista-"]')]
            .find(e => /bg-brand|bg-orange|text-white/.test(e.className));
        return a ? { id: a.getAttribute('data-testid'), texto: a.innerText.trim(), clase: a.className } : null;
    });
    console.log('   abre en: ' + JSON.stringify(abre));
    if (abre && /dieta/i.test(abre.id)) esta('abre en Dieta (Francisco, 2-09), no en Llevas', abre.texto);
    else falta('no abre en Dieta', abre ? abre.texto : '(no se sabe)');

    console.log('\n01 · El aviso, dentro de la pestana Dieta');
    await p.locator('[data-testid="vista-dieta"]').click();
    await p.waitForTimeout(900);
    const enDieta = await txt('[data-testid="macros-de-hoy"]');
    console.log('   Dieta dice: ' + enDieta);
    if (/por meter/.test(enDieta || '')) esta('la caja «Te faltan X g de … por meter»');
    else falta('la caja «Te faltan X g de … por meter»');
    if (/Terminarla/.test(enDieta || '')) esta('el boton «Terminarla»');
    else falta('el boton «Terminarla»', /Verlo/.test(enDieta || '') ? 'sigue el «Verlo»' : 'no hay ningun boton');

    // Y LO QUE DA SENTIDO A PONERLO AQUI: que el numero del aviso sea EL MISMO que el de
    // debajo. Es el argumento del documento -- «en Dieta, ese mismo 12 es el mismo 12 que
    // ves debajo» --, y se rompe con solo redondear cada uno por su cuenta.
    const enCaja = await txt('[data-testid="aviso-dieta"]');
    const numerosCaja = [...(enCaja || '').matchAll(/(\d+) g de (proteína|hidratos|grasa)/g)]
        .map(([, n, m]) => [{ 'proteína': 'P', hidratos: 'H', grasa: 'G' }[m], n]);
    const descuadres = [];
    for (const [k, n] of numerosCaja) {
        const abajo = await txt(`[data-testid="palabra-dieta-${k}"]`);
        if (!new RegExp(`\\b${n}\\b`).test(abajo || '')) descuadres.push(`${k}: caja ${n} vs «${abajo}»`);
    }
    if (numerosCaja.length && !descuadres.length)
        esta('el aviso dice el mismo numero que hay debajo', numerosCaja.map(([k, n]) => `${k}=${n}`).join(' '));
    else if (descuadres.length) falta('el aviso y el numero de debajo no dicen lo mismo', descuadres.join(' · '));

    console.log('\n02 · El punto de la pestana Dieta, en ROJO fuerte');
    // CON DIETA APAGADA. Con la pestana activa el punto va en blanco a proposito, para que
    // se vea sobre el naranja del selector, asi que mirarlo ahi no dice nada del color.
    await p.locator('[data-testid="vista-llevas"]').click();
    await p.waitForTimeout(700);
    const punto = await color('[data-testid="dieta-no-cuadra"]');
    console.log('   punto: ' + JSON.stringify(punto));
    if (!punto) falta('el punto de la pestana Dieta', 'hoy la dieta cuadra: no sale');
    else if (/rgb\(2[0-4]\d, [0-9]{1,2}, [0-9]{1,2}\)/.test(punto.fondo)) esta('el punto en rojo', punto.fondo);
    else falta('el punto en ROJO: sigue en naranja', `${punto.fondo} · ${punto.clase}`);

    console.log('\n03 · Como se comporta: la «×» y «Terminarla»');
    await p.locator('[data-testid="vista-dieta"]').click();
    await p.waitForTimeout(700);
    await p.locator('[data-testid="aviso-dieta"]').first().screenshot({ path: '_guia/_inicio_aviso.png' })
        .catch(() => {});

    // «Terminarla te lleva a arreglarlo», y arreglar una dieta se hace en Nutricion.
    if (await p.locator('[data-testid="terminar-dieta"]').count()) {
        await p.locator('[data-testid="terminar-dieta"]').click();
        await p.waitForTimeout(2500);
        const donde = p.url();
        console.log('   «Terminarla» lleva a: ' + donde);
        if (/\/dashboard\/nutrition/.test(donde)) esta('«Terminarla» lleva a arreglarla', donde.split('/dashboard')[1]);
        else falta('«Terminarla» no lleva a Nutricion', donde);
        await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' });
        await p.waitForTimeout(9000);
        await p.locator('[data-testid="vista-dieta"]').click();
        await p.waitForTimeout(700);
    }
    if (!(await p.locator('[data-testid="cerrar-aviso-dieta"]').count())) {
        falta('la «×» que quita el aviso por hoy', 'no hay aviso que cerrar');
    } else {
        esta('la «×» que quita el aviso por hoy');
        await p.locator('[data-testid="cerrar-aviso-dieta"]').click();
        await p.waitForTimeout(600);
        const caja = await p.locator('[data-testid="aviso-dieta"]').count();
        // El punto se mira con Dieta apagada, que es donde tiene color propio.
        await p.locator('[data-testid="vista-llevas"]').click();
        await p.waitForTimeout(500);
        const sigueElPunto = await p.locator('[data-testid="dieta-no-cuadra"]').count();
        if (!caja && sigueElPunto) esta('la «×» se lleva la caja y DEJA el punto');
        else falta('la «×» no se comporta como dice el documento', `caja ${caja} · punto ${sigueElPunto}`);
        // «por ese día, no para siempre»: al recargar sigue quitada.
        await p.reload({ waitUntil: 'networkidle' });
        await p.waitForTimeout(9000);
        await p.locator('[data-testid="vista-dieta"]').click();
        await p.waitForTimeout(700);
        if (!(await p.locator('[data-testid="aviso-dieta"]').count())) esta('y sigue quitada al recargar');
        else falta('vuelve a salir al recargar: no se guarda que se quito');
        // Se devuelve, que las pruebas de abajo miran la pantalla entera.
        await p.evaluate(() => Object.keys(localStorage)
            .filter((k) => k.includes('inicio-aviso-dieta'))
            .forEach((k) => localStorage.removeItem(k)));
        await p.reload({ waitUntil: 'networkidle' });
        await p.waitForTimeout(9000);
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n04 y 05 · Las cuatro pestanas, una a una');
    for (const vista of ['macros', 'dieta', 'llevas', 'falta']) {
        await p.locator(`[data-testid="vista-${vista}"]`).click();
        await p.waitForTimeout(700);
        const filas = [];
        for (const k of ['P', 'H', 'G']) {
            const palabra = await txt(`[data-testid="palabra-${vista}-${k}"]`);
            const barra = await color(`[data-testid="barra-${vista}-${k}"]`);
            const numero = await color(`[data-testid="dieta-hoy-${vista}-${k}"] .numero-grande`);
            filas.push(`${k}: «${palabra}»${barra ? ` barra ${barra.fondo}` : ' sin barra'}`
                       + `${numero ? ` numero ${numero.texto}` : ''}`);
        }
        console.log(`   ${vista.toUpperCase()}  ${filas.join('  |  ')}`);
        await p.locator('[data-testid="macros-de-hoy"]').screenshot({ path: `_guia/_inicio_${vista}.png` });
    }

    // El numero grande, SIEMPRE en blanco (bloque 04).
    const numeros = await p.evaluate(() => [...document.querySelectorAll('.numero-grande')]
        .map(e => getComputedStyle(e).color));
    const unicos = [...new Set(numeros)];
    console.log('   colores del numero grande: ' + JSON.stringify(unicos));
    if (unicos.length === 1) esta('el numero grande no se colorea nunca', unicos[0]);
    else falta('el numero grande se pinta de mas de un color', unicos.join(' · '));

    // Las barras, ¿siguen el estado o son grises siempre? (bloque 04, punto 83)
    const barras = await p.evaluate(() => [...document.querySelectorAll('[data-testid^="barra-"]')]
        .map(e => `${e.getAttribute('data-testid')}=${getComputedStyle(e).backgroundColor}`));
    console.log('   barras: ' + barras.join(' · '));

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n06 · Llevas: al empezar y al terminar');
    await p.locator('[data-testid="vista-llevas"]').click();
    await p.waitForTimeout(700);
    const vacio = await txt('[data-testid="llevas-vacio"]');
    console.log('   al empezar: ' + vacio);
    if (vacio && /Todavía no has marcado nada/.test(vacio) && /Marca abajo lo que vayas comiendo/.test(vacio))
        esta('el texto de Llevas sin nada marcado');
    else falta('el texto de Llevas sin nada marcado', vacio || '(no sale: ya hay algo marcado)');

    // Se marcan TODAS las comidas, que es la unica forma de ver Llevas al final del dia.
    const marcables = await p.locator('[data-testid^="marcar-"]').count();
    for (let i = 0; i < marcables; i++) {
        const b = p.locator('[data-testid^="marcar-"]').nth(0);
        if (!(await b.count())) break;
        await b.scrollIntoViewIfNeeded();
        await b.click();
        await p.waitForTimeout(700);
    }
    await p.locator('[data-testid="vista-llevas"]').click();
    await p.waitForTimeout(1200);
    const alFinal = [];
    for (const k of ['P', 'H', 'G']) {
        const palabra = await txt(`[data-testid="palabra-llevas-${k}"]`);
        const barra = await color(`[data-testid="barra-llevas-${k}"]`);
        alFinal.push(`${k}: «${palabra}» barra ${barra ? barra.fondo : '(sin barra)'}`);
    }
    console.log('   al terminar: ' + alFinal.join('  |  '));
    console.log('   contador: ' + await txt('[data-testid="contador-llevas"]'));
    // Con el dia cuadrado y marcado entero, «gris» ya no puede ser lo correcto: si todas
    // siguen del mismo gris, es que no siguen al estado (punto 83).
    const coloresBarra = [...new Set(alFinal.map(x => x.split('barra ')[1]))];
    const gris = (c) => /163, 163, 163|128, 128, 128|156, 163|107, 114/.test(c || '');
    if (coloresBarra.every(gris)) falta('las barras siguen grises siempre', coloresBarra.join(' · '));
    else esta('las barras siguen el estado', coloresBarra.join(' · '));
    await p.locator('[data-testid="macros-de-hoy"]').screenshot({ path: '_guia/_inicio_llevas_final.png' });

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n07 · Las dos de la lista de comidas');
    const hechas = await txt('[data-testid="resumen-hechas"]');
    console.log('   linea de las hechas: ' + hechas);
    if (hechas && /\d+P/.test(hechas)) esta('la linea de las hechas dice QUE llevas', hechas);
    else falta('la linea de las hechas solo dice cuantas', hechas || '(no sale)');

    // Y la marca de la comida: ¿palabra o barra sin leyenda?
    await p.locator('[data-testid="ver-hechas"]').click().catch(() => {});
    await p.waitForTimeout(700);
    const marca = await p.evaluate(() => {
        const fila = [...document.querySelectorAll('[data-testid^="comida-hoy-"]')]
            .find(e => /border-l-4/.test(e.className));
        if (!fila) return null;
        return { clase: fila.className, texto: (fila.innerText || '').replace(/\s+/g, ' ').slice(0, 80) };
    });
    console.log('   marca de la fila: ' + JSON.stringify(marca));
    if (marca && /AHORA/i.test(marca.texto)) esta('la marca es una palabra que se entiende');
    else falta('la marca sigue siendo una barra sin leyenda', marca ? marca.texto : '(no hay fila marcada)');
    await p.locator('[data-testid="marca-comidas"]').screenshot({ path: '_guia/_inicio_comidas.png' });

    // ───────────────────────────────────────────────────────────────────────
    // EL VERDE, QUE CON EL DIA DE ANTES NO SE VE. Alli ningun macro llegaba al objetivo,
    // asi que el gris era lo correcto y solo se pudo comprobar el naranja. Con un dia de
    // UNA comida el objetivo de la comida es el del dia entero, el motor lo clava y ahi
    // tienen que salir el verde y el «ya lo tienes» del bloque 06.
    // La configuracion del dia de una comida la usan los dos bloques de abajo, asi que vive
    // fuera de los dos.
    const solo = { fecha: hoy, tipo_dia: 'descanso', num_comidas: 1,
                   momento_entreno: null, opcion_peri: null };
    console.log('\n04 y 06 · El verde: un dia cuadrado de una sola comida');
    {
        const r = await api('/api/calculator/refit-diet', 'POST', { ...solo, comidas: { C1: { alimentos: [
            { alimento_id: 119, nombre: 'Carne picada de pechuga de pollo', cantidad_g: 300 },
            { alimento_id: 48, nombre: 'Arroz Integral con quinoa', cantidad_g: 150 },
            { alimento_id: 3, nombre: 'Aceite de oliva virgen extra una cucharada sopera', cantidad_g: 20 },
        ] } } });
        // LAS DEMAS SE MANDAN VACIAS. El servidor FUSIONA las comidas a proposito (para que
        // dos pestanas no se pisen), asi que mandar solo la C1 deja las otras cuatro y el
        // peri del dia anterior dentro: el dia salia pasado de todo y parecia que la app
        // avisaba de mas cuando el que estaba mal era el escenario.
        await api('/api/diets', 'POST', { ...solo, comidas: {
            C1: { alimentos: r.comidas?.C1?.alimentos || [] },
            C2: { alimentos: [] }, C3: { alimentos: [] }, C4: { alimentos: [] },
            Intra: { alimentos: [] }, Post: { alimentos: [] },
        } });
        await api(`/api/diets/${hoy}/comida-marcada`, 'PATCH', { comida: 'C1', marcada: true });
        await p.reload({ waitUntil: 'networkidle' });
        await p.waitForTimeout(9000);
        for (const vista of ['dieta', 'llevas']) {
            await p.locator(`[data-testid="vista-${vista}"]`).click();
            await p.waitForTimeout(800);
            const filas = [];
            for (const k of ['P', 'H', 'G']) {
                const palabra = await txt(`[data-testid="palabra-${vista}-${k}"]`);
                const barra = await color(`[data-testid="barra-${vista}-${k}"]`);
                filas.push(`${k}: «${palabra}» ${barra ? barra.fondo : '(sin barra)'}`);
            }
            console.log(`   ${vista.toUpperCase()}  ${filas.join('  |  ')}`);
            await p.locator('[data-testid="macros-de-hoy"]').screenshot({ path: `_guia/_inicio_verde_${vista}.png` });
        }
        const verdes = await p.evaluate(() => [...document.querySelectorAll('[data-testid^="barra-"]')]
            .map(e => getComputedStyle(e).backgroundColor));
        if (verdes.some(c => /rgb\(34, 197, 94\)|rgb\(22, 163, 74\)|0, 1[0-9]{2}, /.test(c)))
            esta('la barra se pone VERDE cuando llega', verdes.join(' · '));
        else falta('la barra no se pone verde al llegar', verdes.join(' · '));
        const llevaP = await txt('[data-testid="palabra-llevas-P"]');
        if (/ya lo tienes|cuadrado|válido/i.test(llevaP || '')) esta('Llevas dice el estado al llegar', llevaP);
        else falta('Llevas no dice el estado al llegar', llevaP || '(nada)');
    }

    // ───────────────────────────────────────────────────────────────────────
    // Y EL FINAL DEL BLOQUE 03: al terminar la dieta, la caja y el punto se van SOLOS. El
    // dia de una comida quedo cuadrado por el motor, asi que aqui no debe quedar ninguno.
    console.log('\n03 · Al terminar la dieta, caja y punto se van solos');
    {
        // EL MOTOR NO LO CLAVA DEL TODO: deja unos gramos de hidratos fuera del margen, y
        // con eso el aviso SIGUE siendo correcto. Para probar que se va solo hay que
        // terminar la dieta de verdad, asi que se cierra el hueco con arroz, leyendo lo que
        // falta de la propia pantalla y no de una cuenta aparte.
        const porGramo = (await api('/api/calculator/macros-efectivos', 'POST',
            { alimento_id: 48, cantidad_g: 100, es_vegano: false })).efectivos.H / 100;
        for (let vuelta = 1; vuelta <= 3; vuelta++) {
            await p.locator('[data-testid="vista-dieta"]').click();
            await p.waitForTimeout(700);
            const palabra = await txt('[data-testid="palabra-dieta-H"]');
            const m = /faltan (\d+)/.exec(palabra || '');
            const caja = await txt('[data-testid="aviso-dieta"]');
            console.log(`   vuelta ${vuelta}: hidratos «${palabra}»  ·  aviso «${caja}»`);
            // EL CASO QUE CAZA EL REDONDEO. Aqui el desvio real son ~7,5 g: redondeando el
            // desvio exacto salen 8 y abajo pone 7. Es el unico sitio de la prueba donde los
            // dos redondeos pueden discrepar, asi que se mira aqui a proposito.
            if (m && caja) {
                // Y de paso la foto del caso de SU maqueta: un solo macro fuera.
                await p.locator('[data-testid="aviso-dieta"]').first()
                    .screenshot({ path: '_guia/_inicio_aviso_uno.png' }).catch(() => {});
                if (new RegExp(`\\b${m[1]}\\b`).test(caja)) esta('con medio gramo de por medio, siguen diciendo lo mismo', `${m[1]} g`);
                else falta('con medio gramo de por medio, el aviso y el numero discrepan', `abajo ${m[1]} · aviso «${caja}»`);
            }
            if (!m) break;
            const dia = await api(`/api/diets/${hoy}`);
            const alimentos = [...(dia.comidas?.C1?.alimentos || [])];
            const arroz = alimentos.find((a) => a.alimento_id === 48);
            if (!arroz) break;
            arroz.cantidad_g = Math.round(arroz.cantidad_g + Number(m[1]) / porGramo);
            await api('/api/diets', 'POST', { ...solo, comidas: {
                C1: { alimentos }, C2: { alimentos: [] }, C3: { alimentos: [] },
                C4: { alimentos: [] }, Intra: { alimentos: [] }, Post: { alimentos: [] },
            } });
            await p.reload({ waitUntil: 'networkidle' });
            await p.waitForTimeout(9000);
        }
        await p.locator('[data-testid="vista-dieta"]').click();
        await p.waitForTimeout(700);
        const dieta = await txt('[data-testid="macros-de-hoy"]');
        console.log('   Dieta dice: ' + dieta);
        const caja = await p.locator('[data-testid="aviso-dieta"]').count();
        await p.locator('[data-testid="vista-llevas"]').click();
        await p.waitForTimeout(500);
        const punto = await p.locator('[data-testid="dieta-no-cuadra"]').count();
        if (!caja && !punto) esta('con la dieta cuadrada no queda ni caja ni punto');
        else falta('la dieta cuadra y sigue avisando', `caja ${caja} · punto ${punto}`);
    }

    console.log(`\n${estan.length} de ${estan.length + faltan.length} puntos, hechos. Faltan ${faltan.length}:`);
    faltan.forEach((t) => console.log(`   · ${t}`));
    await nav.close();
})();
