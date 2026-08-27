/**
 * Monta el documento con TODO lo que la app le dice al cliente, a partir de
 * `_guia/_textos_app.json` (lo llena `_recoger_textos.js`).
 *
 * Uso:  node _guia/_recoger_textos.js && node _guia/_armar_doc_textos.js
 */
const fs = require('fs');
const path = require('path');

const RAIZ = path.resolve(__dirname, '..');
const d = JSON.parse(fs.readFileSync(path.join(RAIZ, '_guia/_textos_app.json'), 'utf8'));

const esc = (s) => String(s || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // Los huecos que rellena la app se pintan aparte: leyendo una lista de cien frases,
    // saber de un vistazo que es texto fijo y que es un dato es la mitad del trabajo.
    .replace(/\[([^\]]+)\]/g, '<span class="dato">[$1]</span>');

// Los nombres de fichero, dichos como se llaman las pantallas en la app.
const NOMBRES = {
    Nutrition: 'Nutrición', ClientDashboard: 'Inicio', Profile: 'Mi perfil',
    Routine: 'Mi rutina', CheckIns: 'Check-ins', Reports: 'Seguimiento',
    Questionnaire: 'El cuestionario', MacroCalculatorClient: 'Mis macros',
    Supplements: 'Suplementos', Messages: 'Chat', FoodSearch: 'Buscador de alimentos',
    Chatbot: 'Asistente', Diary: 'Diario', Semana: 'Mi semana', Auth: 'Entrar',
    BuildMealModal: 'Nutrición · montar una comida',
    PreferencesSetup: 'Nutrición · preferencias',
    SearchFoodModal: 'Nutrición · buscar alimento',
    LibraryMenusModal: 'Nutrición · elegir menú',
    FavoritesModal: 'Nutrición · favoritas', RepeatMealModal: 'Nutrición · repetir comida',
    CopyDietModal: 'Nutrición · copiar dieta', TresFotos: 'Seguimiento · tus tres fotos',
    TusFotosYMetricas: 'Seguimiento · fotos y métricas',
    ComparativaCliente: 'Seguimiento · tu comparativa',
    EditorDeRutina: 'Mi rutina · editar', Entreno: 'Mi rutina · entrenar',
    Renovacion: 'Renovar', QuizVenta: 'Quiz de venta', Welcome: 'Bienvenida',
    ImagenAdjunta: 'Chat · imágenes', NutritionIntro: 'Nutrición · intro',
};
const pantalla = (k) => NOMBRES[k] || k;

const TIPO = {
    success: ['Confirmación', 'ok'],
    error: ['Error', 'err'],
    warning: ['Aviso', 'avi'],
    info: ['Información', 'inf'],
    message: ['Información', 'inf'],
};

const filaTexto = (t) => `<tr><td class="txt">${esc(t.texto)}</td><td class="don">${esc(pantalla(t.donde))}</td></tr>`;

// Los mensajes emergentes, agrupados por pantalla y dentro por tipo.
const bloqueToasts = (quien) => {
    const suyos = d.toasts.filter((t) => t.quien === quien);
    const porPantalla = {};
    for (const t of suyos) (porPantalla[pantalla(t.donde)] ||= []).push(t);
    const orden = Object.keys(porPantalla).sort((a, b) => porPantalla[b].length - porPantalla[a].length);
    return orden.map((p) => {
        const lista = porPantalla[p];
        const porTipo = {};
        for (const t of lista) (porTipo[TIPO[t.tipo][0]] ||= []).push(t);
        const trozos = Object.entries(porTipo).map(([nombre, xs]) => `
            <p class="subtipo">${nombre} <span class="cuenta">${xs.length}</span></p>
            <ul class="frases">${xs.map((x) => `<li>${esc(x.texto)}</li>`).join('')}</ul>`).join('');
        return `<div class="pantalla"><h3>${esc(p)} <span class="cuenta">${lista.length}</span></h3>${trozos}</div>`;
    }).join('');
};

const bloqueDialogos = (quien) => {
    const suyos = d.dialogos.filter((x) => x.quien === quien);
    if (!suyos.length) return '<p class="vacio">No hay ninguno.</p>';
    return `<table><tr><th style="width:31%">Pregunta</th><th>Lo que explica</th><th style="width:13%">Botón</th><th style="width:17%">Dónde</th></tr>
        ${suyos.map((x) => `<tr>
            <td class="txt">${x.peligro ? '<span class="peligro">▲</span> ' : ''}${esc(x.titulo)}</td>
            <td>${esc(x.detalle) || '<span class="vacio">—</span>'}</td>
            <td class="boton">${esc(x.boton)}</td>
            <td class="don">${esc(pantalla(x.donde))}</td></tr>`).join('')}</table>`;
};

const bloqueAvisos = () => {
    const porFichero = {};
    for (const a of d.avisos) (porFichero[a.fichero] ||= []).push(a);
    const TITULOS = {
        'backend/core/avisos_cliente.py': 'Los que salen solos, de su calendario y de sus datos',
        'backend/routes/notifications.py': 'Los que manda el equipo al hacer algo',
        'backend/core/renovacion.py': 'Los del final del ciclo y la renovación',
    };
    return Object.entries(porFichero).map(([f, xs]) => `
        <div class="pantalla"><h3>${esc(TITULOS[f] || f)} <span class="cuenta">${xs.length}</span></h3>
        <table><tr><th style="width:38%">Título</th><th>Cuerpo</th></tr>
        ${xs.map((a) => `<tr><td class="txt">${esc(a.titulo)}</td><td>${esc(a.mensaje) || '<span class="vacio">—</span>'}</td></tr>`).join('')}
        </table></div>`).join('');
};

const bloqueErrores = (quien) => {
    const suyos = d.errores.filter((x) => x.quien === quien);
    const porZona = {};
    for (const e of suyos) {
        const z = (e.fichero.match(/routes\/([a-z_]+)\.py/) || [, e.fichero])[1];
        (porZona[z] ||= []).push(e);
    }
    const ZONAS = {
        calculator: 'La calculadora y los alimentos', diets: 'La dieta del día',
        users: 'La cuenta y la ficha', auth: 'Entrar y la contraseña',
        billing: 'Pagos y renovación', reports: 'Reportes y fotos',
        routines: 'Rutinas', checkins: 'Check-ins', messages: 'El chat',
        supplements: 'Suplementos', notifications: 'Avisos', chatbot: 'El asistente',
        settings: 'Ajustes', plans: 'Planes', diary: 'El diario',
        menu_templates: 'Menús', biblioteca_menus: 'Biblioteca de menús',
        workout_logs: 'Entrenos', payments: 'Pagos', report_cadence: 'Cadencia de reportes',
    };
    const orden = Object.keys(porZona).sort((a, b) => porZona[b].length - porZona[a].length);
    return orden.map((z) => `
        <div class="pantalla"><h3>${esc(ZONAS[z] || z)} <span class="cuenta">${porZona[z].length}</span></h3>
        <ul class="frases">${porZona[z].map((e) => `<li>${esc(e.texto)}</li>`).join('')}</ul></div>`).join('');
};

const n = (k, quien) => d[k].filter((x) => !quien || x.quien === quien).length;

const html = `<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>12EN12 · Todo lo que la app le dice al cliente</title>
<style>
  @page { size: A4; margin: 15mm 13mm 13mm 13mm; }
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
         font-size: 9.4pt; line-height: 1.4; color: #1a1a1a; margin: 0; }
  h1 { font-size: 19pt; margin: 0 0 2mm; letter-spacing: -.4px; }
  .sub { color: #666; font-size: 9.4pt; margin: 0 0 6mm; }
  h2 { font-size: 12.5pt; margin: 8mm 0 2mm; padding-bottom: 1.2mm;
       border-bottom: 2px solid #FF671F; page-break-after: avoid; }
  h2 .cuenta { font-size: 9pt; }
  h3 { font-size: 10pt; margin: 4mm 0 1mm; page-break-after: avoid; color: #222; }
  p { margin: 0 0 2mm; }
  .intro { color: #555; margin-bottom: 3mm; }
  /* Las tablas largas SI se parten entre paginas: si no, un bloque de 60 filas
     salta entero y deja media pagina en blanco. Lo que no se parte es la fila. */
  .pantalla { margin: 0 0 3.5mm; }
  tr, li { page-break-inside: avoid; }
  .subtipo { font-size: 8.4pt; text-transform: uppercase; letter-spacing: .4px;
             color: #999; margin: 1.5mm 0 0.8mm; font-weight: 600; }
  .cuenta { display: inline-block; background: #eee; color: #666; border-radius: 8px;
            padding: 0 1.6mm; font-size: 7.6pt; font-weight: 700; vertical-align: 1px; }
  ul.frases { margin: 0 0 1.5mm; padding-left: 4.5mm; }
  ul.frases li { margin-bottom: 0.7mm; }
  table { width: 100%; border-collapse: collapse; margin: 1mm 0 3mm; font-size: 8.8pt; }
  th, td { text-align: left; padding: 1.2mm 1.6mm; border-bottom: 1px solid #e8e8e8;
           vertical-align: top; }
  th { background: #f7f7f7; font-weight: 600; font-size: 8.2pt; }
  .txt { font-weight: 600; }
  .don, .boton { color: #888; font-size: 8.2pt; }
  .vacio { color: #bbb; }
  /* Los huecos que rellena la app, en gris: se distinguen del texto fijo sin leerlos. */
  .dato { color: #b06030; font-weight: 600; }
  .peligro { color: #d33; font-weight: 700; }
  .caja { background: #fdf5f0; border: 1px solid #f3d9c8; border-radius: 3px;
          padding: 2.5mm 3.5mm; margin: 3mm 0; page-break-inside: avoid; }
  .caja h3 { margin-top: 0; }
  .pie { margin-top: 6mm; padding-top: 2.5mm; border-top: 1px solid #ddd;
         color: #777; font-size: 8pt; }
  .salto { page-break-before: always; }
</style></head><body>

<h1>Todo lo que la app le dice al cliente</h1>
<p class="sub">Los textos de avisos, mensajes y preguntas, sacados del código el 26 de agosto de 2026.</p>

<div class="caja">
  <h3>Cómo está ordenado</h3>
  <p class="intro">La app habla de cuatro maneras, y cada una está en su apartado:</p>
  <ul class="frases">
    <li><b>Los avisos</b> (${n('avisos')}): llegan a la campana sin que estés mirando.</li>
    <li><b>Las preguntas</b> (${n('dialogos', 'cliente')}): paran y esperan un sí o un no.</li>
    <li><b>Los mensajes</b> (${n('toasts', 'cliente')}): salen, dicen lo que ha pasado y se van solos.</li>
    <li><b>Los errores</b> (${n('errores', 'cliente')}): lo que sale cuando algo no se puede hacer.</li>
  </ul>
  <p class="intro">Al final va lo del <b>panel del equipo</b>, que no lo ve ningún cliente.
     Los <span class="peligro">▲</span> son las preguntas antes de borrar algo.</p>
  <p class="intro"><b>Lo que va entre corchetes no falta: lo rellena la app.</b>
     «<span class="dato">[el alimento]</span> fuera de la comida» sale como «Pechuga de
     pollo fuera de la comida»; «Copiada <span class="dato">[la comida]</span> del
     <span class="dato">[la fecha]</span>» sale con el nombre y el día de verdad. Y una
     barra entre dos trozos son las <b>dos redacciones</b> del mismo mensaje: «Un alimento
     ya no está <span class="dato">/</span> … alimentos ya no están».</p>
</div>

<h2>1 · Los avisos <span class="cuenta">${n('avisos')}</span></h2>
<p class="intro">Lo que la app le manda por su cuenta. Los de su calendario van siempre; los
   demás solo cuando sus datos lo justifican, y como mucho uno por semana. Cada aviso tiene
   dos o tres redacciones que rotan: el mismo mensaje repetido doce semanas deja de leerse.</p>
${bloqueAvisos()}

<h2 class="salto">2 · Las preguntas <span class="cuenta">${n('dialogos', 'cliente')}</span></h2>
<p class="intro">Lo que se le pregunta antes de hacer algo que no tiene vuelta atrás.</p>
${bloqueDialogos('cliente')}

<h2>3 · Los mensajes <span class="cuenta">${n('toasts', 'cliente')}</span></h2>
<p class="intro">Por pantalla, y dentro por lo que son: una confirmación de que algo salió
   bien, un error, un aviso de cuidado o una explicación.</p>
${bloqueToasts('cliente')}

<h2 class="salto">4 · Los errores <span class="cuenta">${n('errores', 'cliente')}</span></h2>
<p class="intro">Lo que responde el servidor cuando algo no se puede hacer. La app los enseña
   tal cual, así que se leen como cualquier otro mensaje.</p>
${bloqueErrores('cliente')}

<h2 class="salto">5 · El panel del equipo <span class="cuenta">${n('toasts', 'equipo') + n('dialogos', 'equipo') + n('errores', 'equipo')}</span></h2>
<p class="intro">Esto no lo ve ningún cliente: es lo que leen Jesús y los entrenadores.</p>

<h3>Las preguntas <span class="cuenta">${n('dialogos', 'equipo')}</span></h3>
${bloqueDialogos('equipo')}

<h3>Los mensajes <span class="cuenta">${n('toasts', 'equipo')}</span></h3>
${bloqueToasts('equipo')}

<h3>Los errores <span class="cuenta">${n('errores', 'equipo')}</span></h3>
${bloqueErrores('equipo')}

<div class="pie">
  12EN12 · ${n('avisos') + n('toasts') + n('dialogos') + n('errores')} textos ·
  generado el 26 de agosto de 2026 desde el código (<code>_guia/_recoger_textos.js</code>)
</div>
</body></html>`;

fs.writeFileSync(path.join(RAIZ, '_guia/_doc_textos.html'), html);
console.log('documento montado con',
    n('avisos') + n('toasts') + n('dialogos') + n('errores'), 'textos');
