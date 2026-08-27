/**
 * TODO LO QUE LA APP LE DICE AL CLIENTE, recogido del codigo.
 *
 * Cuatro familias, que son las cuatro formas que tiene la app de hablar:
 *   · los mensajes emergentes (toast): lo que sale y se va solo
 *   · los dialogos que preguntan (confirm/prompt): lo que espera respuesta
 *   · los avisos de la campana y los correos: lo que llega sin que estes mirando
 *   · los errores del servidor: lo que sale cuando algo no se puede hacer
 *
 * Deja `_guia/_textos_app.json`, que es de donde sale el documento.
 *
 * Uso:  node _guia/_recoger_textos.js
 */
const fs = require('fs');
const path = require('path');

const RAIZ = path.resolve(__dirname, '..');

const recorrer = (dir, ext, fuera = []) => {
    let r = [];
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, e.name);
        const rp = p.split(path.sep).join('/');
        if (fuera.some((f) => rp.includes(f))) continue;
        if (e.isDirectory()) r = r.concat(recorrer(p, ext, fuera));
        else if (ext.some((x) => e.name.endsWith(x))) r.push(p);
    }
    return r;
};

const rel = (p) => path.relative(RAIZ, p).split(path.sep).join('/');

// La pantalla, deducida del nombre del fichero: es como lo nombra alguien que usa la app.
const pantallaDe = (p) => {
    const r = rel(p);
    const m = r.match(/(?:pages|components)\/(?:[^/]+\/)?([^/]+)\.jsx?$/);
    if (!m) return r;
    return m[1].replace(/Page$/, '');
};

const literal = (s) => s.replace(/^f/, '').slice(1, -1).trim();

// Quien lo lee. El panel del equipo y la app del cliente comparten codigo, asi que no vale
// con mirar si el fichero se llama `Admin*`: la ficha del cliente y los leads son del panel
// y no lo llevan en el nombre. La lista sale de las rutas que cuelgan de `/admin` en App.js.
const DEL_EQUIPO = [
    'ClientDetailPage', 'LeadsPage', 'SupplementsCatalogPage', 'AdminPlansPage',
    'PlanesPage', 'ComparativaCoach',
];
const deQuien = (p) => {
    const r = rel(p);
    if (/Admin/.test(r) || DEL_EQUIPO.some((n) => r.includes(n))) return 'equipo';
    if (/routes\/(admin|paneles|leads|tareas|audit|pagos_historicos)\.py/.test(r)) return 'equipo';
    return 'cliente';
};

/**
 * El texto tal y como lo lee el cliente, resolviendo los huecos.
 *
 * DENTRO DE UN HUECO PUEDE HABER TEXTO, Y ESE TEXTO SE LEE. Al principio esto ponia «…» en
 * todos, y asi «Comida cuadrada a tus macros.${notaRedondeo}» perdia entera la frase
 * «Cantidades redondeadas para pesarlas facil: los macros pueden variar unos gramos», que
 * es justo lo que hay que revisar en un documento de textos. Tres casos:
 *
 *   · el hueco trae literales (`${n === 1 ? 'uno' : 'varios'}`) -> se sacan y se enseñan
 *     como las dos redacciones que son: «uno / varios»;
 *   · el hueco es una variable que en el mismo fichero vale un texto (`notaRedondeo`) ->
 *     se resuelve y se pone su contenido;
 *   · el hueco es un dato (un nombre, una fecha, un numero) -> «…», que es lo que es.
 */
/**
 * La cadena que empieza en `i`, ENTERA, aunque lleve otra dentro.
 *
 * Una expresion regular como /`[^`]*`/ se corta en el primer acento de cierre, y ese acento
 * puede ser el de un template ANIDADO: «Comida cuadrada. ${n === 1 ? 'uno' : `${n} varios`}
 * en el catalogo y se quito.» salia cortada en «uno» y se perdia el final de la frase.
 * Aqui se cuenta el anidamiento, que es la unica forma de leerla completa.
 */
const cadenaDesde = (src, i) => {
    const comilla = src[i];
    if (!['`', "'", '"'].includes(comilla)) return null;
    let j = i + 1, nivel = 0;
    while (j < src.length) {
        const c = src[j];
        if (c === '\\') { j += 2; continue; }
        if (comilla === '`' && c === '$' && src[j + 1] === '{') { nivel++; j += 2; continue; }
        if (nivel > 0) {
            if (c === '{') nivel++;
            else if (c === '}') nivel--;
            else if (['`', "'", '"'].includes(c)) {          // cadena dentro del hueco
                const anidada = cadenaDesde(src, j);
                if (anidada) { j = anidada.fin; continue; }
            }
            j++;
            continue;
        }
        if (c === comilla) return { texto: src.slice(i + 1, j), fin: j + 1 };
        if (c === '\n' && comilla !== '`') return null;      // '...' y "..." no saltan de linea
        j++;
    }
    return null;
};

// Dentro de un hueco hay de todo: frases que se leen y claves que no («quitar_o_bajar»,
// «anadir», los valores con los que el codigo compara). Se quedan las frases: una clave no
// lleva espacios y va en minusculas con guiones bajos.
const esFrase = (s) => s.trim().length > 2 && !/^[a-z0-9_.]+$/.test(s.trim());

const literalesDe = (dentro) => {
    const m = dentro.match(/(['"`])((?:\\.|(?!\1)[^\\])*)\1/g) || [];
    // Sin `trim`: la frase suele empezar con un espacio a proposito, porque se pega detras
    // de otra («...a tus macros.» + « Cantidades redondeadas...»).
    const textos = m.map((x) => x.slice(1, -1)).filter(esFrase);
    return [...new Set(textos)];
};

const legible = (t, src = '', interno = false) => {
    let r = '';
    for (let i = 0; i < t.length; i++) {
        if (t[i] === '{') {
            if (r.endsWith('$')) r = r.slice(0, -1);
            let nivel = 1, j = i + 1;
            while (j < t.length && nivel > 0) {
                if (t[j] === '{') nivel++;
                else if (t[j] === '}') nivel--;
                j++;
            }
            const dentro = t.slice(i + 1, nivel > 0 ? t.length : j - 1);
            let puesto = literalesDe(dentro);
            // Una variable a secas: se busca lo que vale en el mismo fichero. Hasta el
            // proximo `;` a principio de linea, no al primero que aparezca: las definiciones
            // de estas frases suelen ocupar tres o cuatro lineas (un ternario con los dos
            // textos), y cortando antes se pierde justo la frase que se busca.
            if (!puesto.length && /^\s*[A-Za-z_$][\w$.]*\s*$/.test(dentro) && src) {
                const nombre = dentro.trim().split('.')[0];
                const def = new RegExp(`(?:const|let|var)\\s+${nombre}\\s*=([\\s\\S]{0,400}?);\\s*\\n`).exec(src);
                if (def) puesto = literalesDe(def[1]);
            }
            // Lo sacado puede traer SUS PROPIOS huecos («${nEx} alimentos ya no están»), asi
            // que se vuelve a pasar por aqui. Sin esto quedaban nombres de variable impresos.
            r += puesto.length ? puesto.map((x) => legible(x, src, true)).join(' / ') : '…';
            if (nivel > 0) break;   // el hueco no cierra: lo que sigue es codigo cortado
            i = j - 1;
            continue;
        }
        r += t[i];
    }
    // En la recursion NO se recorta: la frase que sale de un hueco suele empezar con un
    // espacio a proposito, porque se pega detras de otra («…a tus macros.» + « Cantidades
    // redondeadas…»). Recortandolo salian pegadas: «macros.Cantidades».
    const limpio = r.replace(/[ \t]+/g, ' ').replace(/\n+/g, ' ');
    return interno ? limpio : limpio.trim();
};

const out = { toasts: [], dialogos: [], avisos: [], correos: [], errores: [] };

// ── 1 · Mensajes emergentes y dialogos (frontend) ──────────────────────────
for (const f of recorrer(path.join(RAIZ, 'frontend/src'), ['.jsx', '.js'], ['node_modules'])) {
    const src = fs.readFileSync(f, 'utf8');

    const re = /toast\.(success|error|warning|info|message)\(\s*/g;
    let m;
    while ((m = re.exec(src))) {
        const c = cadenaDesde(src, m.index + m[0].length);
        if (!c) continue;
        const texto = c.texto.trim();
        if (texto.length < 3) continue;
        out.toasts.push({ tipo: m[1], texto: legible(texto, src), quien: deQuien(f), donde: pantallaDe(f), fichero: rel(f) });
    }

    const rc = /(?:await\s+)?(confirm|prompt)\(\s*\{([\s\S]{0,500}?)\}\s*\)/g;
    while ((m = rc.exec(src))) {
        const bloque = m[2];
        const t = /title:\s*(`[^`]*`|'[^']*'|"[^"]*")/.exec(bloque);
        if (!t) continue;
        const d = /description:\s*(`[^`]*`|'[^']*'|"[^"]*")/.exec(bloque);
        const c = /confirmLabel:\s*(`[^`]*`|'[^']*'|"[^"]*")/.exec(bloque);
        const peligro = /danger:\s*true/.test(bloque);
        out.dialogos.push({
            modo: m[1],
            titulo: legible(t[1].slice(1, -1), src),
            detalle: d ? legible(d[1].slice(1, -1), src) : '',
            boton: c ? c[1].slice(1, -1).trim() : (m[1] === 'confirm' ? 'Aceptar' : ''),
            peligro,
            quien: deQuien(f), donde: pantallaDe(f), fichero: rel(f),
        });
    }
}

// ── 2 · Avisos, correos y errores (backend) ───────────────────────────────
const fueraPy = ['__pycache__', 'venv', '/tests/', '/backend/_'];
for (const f of recorrer(path.join(RAIZ, 'backend'), ['.py'], fueraPy)) {
    const src = fs.readFileSync(f, 'utf8');
    let m;

    // Los avisos llevan `titulo` y, al lado, `cuerpo` o `mensaje`. Los del cliente van
    // ademas en `variantes`: dos o tres redacciones del MISMO aviso que rotan para que no
    // se lea siempre lo mismo (regla 6 del doc 16-08). Se recogen todas.
    const ra = /["']titulo["']\s*:\s*((?:f?"[^"]*"|f?'[^']*')(?:\s*\n?\s*(?:f?"[^"]*"|f?'[^']*'))*)/g;
    while ((m = ra.exec(src))) {
        const t = m[1].split('\n').map((s) => literal(s.trim())).join(' ').trim();
        if (!t) continue;
        const cerca = src.slice(m.index, m.index + 600);
        const msg = /["'](?:mensaje|cuerpo)["']\s*:\s*((?:f?"[^"]*"|f?'[^']*')(?:\s*\n?\s*(?:f?"[^"]*"|f?'[^']*'))*)/.exec(cerca);
        out.avisos.push({
            titulo: legible(t, src),
            mensaje: msg ? legible(msg[1].split('\n').map((s) => literal(s.trim())).join(' ')) : '',
            quien: deQuien(f), fichero: rel(f),
        });
    }

    const rs = /(?:asunto|subject)\s*=\s*(f?"[^"]*"|f?'[^']*')/g;
    while ((m = rs.exec(src))) {
        const t = literal(m[1]);
        if (t) out.correos.push({ asunto: legible(t, src), quien: deQuien(f), fichero: rel(f) });
    }

    const rd = /detail\s*=\s*(f?"[^"]*"|f?'[^']*')/g;
    while ((m = rd.exec(src))) {
        const t = literal(m[1]);
        if (t.length > 8) out.errores.push({ texto: legible(t, src), quien: deQuien(f), fichero: rel(f) });
    }
}

const unicos = (arr, clave) => {
    const v = new Map();
    for (const x of arr) { const k = clave(x); if (!v.has(k)) v.set(k, x); }
    return [...v.values()];
};
out.toasts = unicos(out.toasts, (x) => x.tipo + '|' + x.texto);
out.dialogos = unicos(out.dialogos, (x) => x.titulo + '|' + x.detalle);
out.avisos = unicos(out.avisos, (x) => x.titulo + '|' + x.mensaje);
out.correos = unicos(out.correos, (x) => x.asunto);
out.errores = unicos(out.errores, (x) => x.texto);

fs.writeFileSync(path.join(RAIZ, '_guia/_textos_app.json'), JSON.stringify(out, null, 1));

const porTipo = (t) => out.toasts.filter((x) => x.tipo === t).length;
console.log('mensajes emergentes:', out.toasts.length,
    `(exito ${porTipo('success')} · error ${porTipo('error')} · aviso ${porTipo('warning')} · info ${porTipo('info') + porTipo('message')})`);
console.log('dialogos que preguntan:', out.dialogos.length);
console.log('avisos de la campana:', out.avisos.length);
console.log('asuntos de correo:', out.correos.length);
console.log('errores del servidor:', out.errores.length);
