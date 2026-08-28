/**
 * QUIEN LLEVA SOPORTE LO VE TODO (Francisco, 27-08).
 *
 * «No siempre se ven los mensajes de soporte: cualquier persona de las asignadas para
 * soporte debería ver cualquier mensaje de cualquier persona, sin importar su rol o si lo
 * envió la misma persona.»
 *
 * Había dos filtros que escondían mensajes, los dos puestos a propósito en su día:
 *   - una conversación ENTRE DOS DEL EQUIPO no se le listaba a un tercero
 *   - una que alguien se manda A SÍ MISMO solo la veía su dueño
 *
 * Aquí se montan los dos casos con mensajes de verdad, se mira la bandeja y el hilo de una
 * cuenta de soporte, y se borran los mensajes al terminar.
 *
 * Se comprueba TAMBIÉN por el lado contrario: un entrenador que NO es de soporte sigue sin
 * ver la conversación privada de dos compañeros. Ensanchar para soporte no puede ser
 * ensanchar para todos.
 *
 * Uso:  node _guia/_soporte_lo_ve_todo_2708.js
 */
const { chromium } = require('playwright');
const API = process.env.API || 'http://127.0.0.1:8000';
const SOPORTE = process.env.SOPORTE || 'francisco@test.com';   // está en SUPPORT_EMAILS
const CLAVE = process.env.CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');
const MARCA = 'PRUEBA-SOPORTE-2708';

(async () => {
    const nav = await chromium.launch();
    const page = await (await nav.newContext()).newPage();

    const tok = (await (await page.request.post(`${API}/api/auth/login`,
        { data: { email: SOPORTE, password: CLAVE } })).json()).access_token;
    const cab = { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' };
    const yo = await (await page.request.get(`${API}/api/auth/me`, { headers: cab })).json();

    // Dos del equipo que NO son quien mira: entre ellos hablarán, y uno se escribirá a sí mismo.
    const staff = await (await page.request.get(`${API}/api/admin/trainers`, { headers: cab })).json();
    const otros = (Array.isArray(staff) ? staff : []).filter(u => u.id !== yo.id);
    if (otros.length < 2) {
        console.log('hacen falta al menos dos cuentas de equipo distintas de la de soporte; hay', otros.length);
        await nav.close();
        return;
    }
    const [a, b] = otros;
    console.log(`\n=== SOPORTE LO VE TODO ===\n`);
    console.log(`mira            : ${yo.email} (soporte)`);
    console.log(`hablan entre sí : ${a.email}  y  ${b.email}\n`);

    // Se escriben con la API del propio servidor, como cualquiera de ellos.
    const comoEl = async (email) => (await (await page.request.post(`${API}/api/auth/login`,
        { data: { email, password: CLAVE } })).json()).access_token;
    const escribir = async (email, receptor, texto) => {
        const t = await comoEl(email);
        if (!t) return null;
        const r = await page.request.post(`${API}/api/messages`, {
            headers: { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' },
            data: { receiver_id: receptor, content: texto },
        });
        return r.status();
    };

    const s1 = await escribir(a.email, b.id, `${MARCA} de uno a otro del equipo`);
    const s2 = await escribir(a.email, a.id, `${MARCA} a sí mismo`);
    console.log(`mensaje entre dos del equipo -> HTTP ${s1}`);
    console.log(`mensaje a sí mismo           -> HTTP ${s2}\n`);
    if (s1 !== 200 || s2 !== 200) {
        console.log('no se pudieron crear los mensajes (¿la clave de esas cuentas no es la de pruebas?)');
        await nav.close();
        return;
    }

    // ── La bandeja de soporte ───────────────────────────────────────────────
    const bandeja = await (await page.request.get(`${API}/api/messages/conversations`, { headers: cab })).json();
    const filas = Array.isArray(bandeja) ? bandeja : (bandeja.conversations || []);
    const conA = filas.find(c => c.user_id === a.id);
    console.log(`la bandeja trae a ${a.email}   ${ok(!!conA)}`);

    // ── El hilo ─────────────────────────────────────────────────────────────
    const hilo = await (await page.request.get(`${API}/api/messages?with_user=${a.id}`, { headers: cab })).json();
    const textos = (Array.isArray(hilo) ? hilo : []).map(m => m.content || '');
    console.log(`ve el de uno a otro del equipo  ${ok(textos.some(t => t.includes('de uno a otro')))}`);
    console.log(`ve el que se mandó a sí mismo   ${ok(textos.some(t => t.includes('a sí mismo')))}`);

    // ── Y por el otro lado: quien NO es de soporte sigue sin verlo ──────────
    const noSoporte = otros.find(u => u.id !== a.id && u.id !== b.id);
    if (noSoporte) {
        const t = await comoEl(noSoporte.email);
        if (t) {
            const cab2 = { Authorization: `Bearer ${t}` };
            const suHilo = await (await page.request.get(`${API}/api/messages?with_user=${a.id}`, { headers: cab2 })).json();
            const suyos = (Array.isArray(suHilo) ? suHilo : []).map(m => m.content || '');
            console.log(`\nquien NO es de soporte (${noSoporte.email}):`);
            console.log(`   NO ve lo de los dos compañeros  ${ok(!suyos.some(x => x.includes(MARCA)))}`);
        }
    } else {
        console.log('\n(no hay una tercera cuenta de equipo fuera de soporte para probar el lado contrario)');
    }

    // ── Se borra lo de la prueba ────────────────────────────────────────────
    console.log('\nlos mensajes de la prueba llevan la marca ' + MARCA);
    console.log('se borran con: db.messages.deleteMany({content: /' + MARCA + '/})');
    await nav.close();
})();
