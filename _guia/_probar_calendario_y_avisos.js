/**
 * LOS HALLAZGOS 04, 07, 09 Y 10 DE LA REVISION DE NUTRICION DEL 1-09.
 *
 *   04  «Cuadrar el dia» avisaba de que el dia quedo cuadrado cuando no lo estaba.
 *   07  La «X» del dialogo caia encima de la flecha de mes siguiente del calendario.
 *   09  El calendario no marcaba el dia que se esta mirando.
 *   10  El calendario daba por «completo» cualquier dia con cuatro comidas.
 *
 * La cuenta es la de la revision (`francisco@test.com`, C1 = 50P/30H/10G), que es la que
 * hace que el 04 salga: con esa comida el dia no cuadra y el aviso tenia que decirlo.
 *
 * Uso:  node _guia/_probar_calendario_y_avisos.js
 */
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = { correo: 'francisco@test.com', clave: 'demo123' };
const DIA = process.env.DIA || '2026-09-02';

(async () => {
    let fallos = 0;
    const bien = (t) => console.log(`   OK   ${t}`);
    const mal = (t) => { fallos++; console.log(`   MAL  ${t}`); };

    const token = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA.correo, password: CUENTA.clave }),
    }).then((r) => r.json()).then((r) => r.access_token);

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 390, height: 1600 },
                                            locale: 'es-ES', timezoneId: 'Europe/Madrid' })).newPage();
    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, token);
    await p.goto(`${APP}/dashboard/nutrition?date=${DIA}`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(11000);

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n04 · El aviso de «Cuadrar el dia» tiene que decir la verdad');
    {
        const boton = p.locator('[data-testid="boton-recuadrar-dia"]').first();
        if (!(await boton.count())) {
            console.log('   (hoy el dia ya cuadra: no sale el boton, no hay nada que comprobar)');
        } else {
            await boton.click({ force: true }).catch(() => {});
            await p.waitForTimeout(4000);
            // Lo que dice el aviso y lo que dicen los numeros de arriba, a la vez.
            const aviso = await p.evaluate(() =>
                [...document.querySelectorAll('[data-sonner-toast], [role="status"]')]
                    .map((n) => n.innerText.replace(/\n+/g, ' ').trim()).join(' | '));
            const numeros = await p.evaluate(() => {
                const t = (id) => document.querySelector(`[data-testid="${id}"]`)?.innerText?.replace(/\n+/g, ' ').trim();
                return [t('dia-P'), t('dia-H'), t('dia-G')].filter(Boolean).join(' · ');
            });
            console.log(`   aviso:   ${aviso || '(ninguno)'}`);
            console.log(`   numeros: ${numeros}`);
            const faltaAlgo = /faltan|sobran/i.test(numeros);
            const dijoCuadrado = /d[ií]a cuadrado a tus macros/i.test(aviso);
            if (faltaAlgo && dijoCuadrado) {
                mal('dice «Día cuadrado» con los números diciendo que falta algo');
            } else if (faltaAlgo && /no cuadra del todo/i.test(aviso)) {
                bien('dice que no cuadra del todo, que es lo que se ve');
            } else if (!faltaAlgo && dijoCuadrado) {
                bien('cuadra de verdad y lo dice');
            } else {
                mal(`el aviso y los números no se corresponden`);
            }
        }
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n07 · La «X» no puede estar encima de la flecha de mes siguiente');
    await p.locator('[data-testid="open-calendar-btn"]').first().click({ force: true }).catch(() => {});
    await p.waitForTimeout(2000);
    {
        const quien = await p.evaluate(() => {
            const flecha = [...document.querySelectorAll('[data-testid="diet-calendar-modal"] button')]
                .find((b) => b.querySelector('svg.lucide-chevron-right'));
            if (!flecha) return null;
            const r = flecha.getBoundingClientRect();
            // La esquina de arriba a la derecha de la flecha: por ahi se avanza de mes.
            const el = document.elementFromPoint(r.right - 4, r.top + 4);
            return { recibe: el?.closest('button')?.innerText?.trim()
                            || el?.closest('button')?.getAttribute('aria-label')
                            || (el?.closest('button')?.querySelector('.sr-only')?.textContent ?? '?'),
                     esLaFlecha: !!el?.closest('button')?.querySelector('svg.lucide-chevron-right'),
                     ancho: Math.round(r.width), alto: Math.round(r.height) };
        });
        console.log(`   la esquina de la flecha la recibe: ${JSON.stringify(quien)}`);
        if (!quien) mal('no he encontrado la flecha de mes siguiente');
        else if (quien.esLaFlecha) bien('el clic en la esquina de la flecha va a la flecha');
        else mal(`la esquina de la flecha la recibe «${quien.recibe}»`);

        // Y el boton de cerrar, con sitio para el dedo.
        const cerrar = await p.evaluate(() => {
            const b = [...document.querySelectorAll('[data-testid="diet-calendar-modal"] button')]
                .find((x) => /cerrar|close/i.test(x.querySelector('.sr-only')?.textContent || ''));
            if (!b) return null;
            const r = b.getBoundingClientRect();
            return { texto: b.querySelector('.sr-only')?.textContent,
                     ancho: Math.round(r.width), alto: Math.round(r.height) };
        });
        console.log(`   boton de cerrar: ${JSON.stringify(cerrar)}`);
        if (cerrar && cerrar.texto === 'Cerrar') bien('el botón de cerrar se anuncia en castellano');
        else mal(`el botón de cerrar se anuncia como «${cerrar?.texto}»`);
        if (cerrar && cerrar.ancho >= 28 && cerrar.alto >= 28) bien(`y mide ${cerrar.ancho}x${cerrar.alto}`);
        else mal(`sigue siendo pequeño para el dedo: ${cerrar?.ancho}x${cerrar?.alto}`);
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n09 · El calendario marca el dia que se esta mirando');
    {
        const dia = Number(DIA.slice(8, 10));
        const marcado = await p.evaluate((d) => {
            const b = document.querySelector(`[data-testid="cal-day-${d}"]`);
            return b ? { clase: b.className, aria: b.getAttribute('aria-current') } : null;
        }, dia);
        console.log(`   dia ${dia}: aria-current=${marcado?.aria} · relleno=${/bg-brand/.test(marcado?.clase || '')}`);
        if (marcado?.aria === 'date' && /bg-brand/.test(marcado.clase)) {
            bien('el día abierto sale marcado');
        } else {
            mal('el día abierto no se distingue de los demás');
        }
    }

    await nav.close();

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n10 · «Completo» sale del numero de comidas DE ESE DIA');
    {
        // EL CASO QUE LO DESTAPA: un dia de TRES comidas, entero. Con el 4 escrito a mano no
        // llegaba nunca a «completo». Se monta, se mira y se borra.
        const DIA_DE_TRES = `${DIA.slice(0, 8)}28`;
        const cabeceras = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };
        const comida = (n) => ({ alimentos: [{ alimento_id: 1657, nombre: `Arroz ${n}`, cantidad_g: 50 }] });
        await fetch(`${API}/api/diets`, {
            method: 'POST', headers: cabeceras,
            body: JSON.stringify({ fecha: DIA_DE_TRES, tipo_dia: 'descanso', num_comidas: 3,
                                   momento_entreno: 1, opcion_peri: 'sin_peri',
                                   comidas: { C1: comida(1), C2: comida(2), C3: comida(3) } }),
        }).catch(() => {});

        const mesTres = await fetch(
            `${API}/api/diets/calendar/${DIA.slice(0, 4)}/${Number(DIA.slice(5, 7))}`,
            { headers: cabeceras }).then((r) => r.json()).catch(() => ({ days: {} }));
        const suyo = (mesTres.days || {})[DIA_DE_TRES];
        console.log(`   dia de 3 comidas, con las 3 puestas -> «${suyo?.status}»`);
        if (suyo?.status === 'complete') bien('un día de tres comidas puede estar completo');
        else mal(`dice «${suyo?.status}»: sigue midiendo contra un 4 escrito a mano`);

        await fetch(`${API}/api/diets/${DIA_DE_TRES}`, { method: 'DELETE', headers: cabeceras })
            .catch(() => {});

        const mes = DIA.slice(0, 7);
        const cal = await fetch(`${API}/api/diets/calendar/${mes.slice(0, 4)}/${Number(mes.slice(5, 7))}`, {
            headers: { Authorization: `Bearer ${token}` },
        }).then((r) => r.json());
        const dias = cal.days || {};
        let comprobados = 0;
        for (const [fecha, d] of Object.entries(dias)) {
            const dia = await fetch(`${API}/api/diets/${fecha}`, {
                headers: { Authorization: `Bearer ${token}` },
            }).then((r) => r.json());
            const nc = dia.num_comidas || 4;
            const normales = Object.entries(dia.comidas || {})
                .filter(([k, v]) => !['Intra', 'Post'].includes(k) && (v?.alimentos || []).length).length;
            const esperado = normales >= Math.max(1, nc) ? 'complete'
                : (d.total_comidas > 0 ? 'partial' : 'empty');
            comprobados++;
            if (d.status !== esperado) {
                mal(`${fecha}: dice «${d.status}» y con ${normales} de ${nc} comidas tendría que decir «${esperado}»`);
            }
        }
        console.log(`   días comprobados: ${comprobados}`);
        if (comprobados) bien('el estado de cada día cuadra con SUS comidas');
        else console.log('   (no hay días con dieta ese mes: nada que comprobar)');
    }

    console.log(fallos ? `\n${fallos} comprobacion(es) MAL` : '\nTodo bien');
    process.exit(fallos ? 1 : 0);
})();
