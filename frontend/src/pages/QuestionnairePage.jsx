import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { CAP } from '../lib/planAccess';
import { seLeOfreceLaRevision } from '../lib/revision';
import { verComo } from '../lib/modoRevision';
import { MEDIDAS, VIDEO_MEDIDAS } from '../lib/medidas';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { ArrowRight, ArrowLeft, Loader2, Check, ClipboardList, ImagePlus } from 'lucide-react';
import Logo12EN12 from '../components/Logo12EN12';
import BrandArrow from '../components/BrandArrow';
import PreferencesSetup, { CAJONES, PREFERENCE_CATEGORIES, EJEMPLOS } from '../components/nutrition/PreferencesSetup';
import TresFotos from '../components/reports/TresFotos';

// Cuestionario inicial en DOS NIVELES (spec 18-07-2026):
//  - Nivel 0 (todo el mundo): las 8 preguntas que mueven los macros -> CALCULAR.
//  - Nivel 1 (solo planes con coach, calculadora == 'personalizado'): perfil largo
//    (biotipo, salud, historial...). NO toca los macros.
// Estilo paso a paso (una pregunta por pantalla).

const BIOTIPOS = [
    { value: 'ectomorfo', label: 'Ectomorfo (el delgado)', img: '/biotipos/ectomorfo.webp', desc: 'Complexión delgada (hombros estrechos, huesos largos y finos, articulaciones pequeñas), pero aspecto un poco "blando" (no gordo), sin tono muscular. Metabolismo muy rápido, quema calorías con facilidad y le cuesta ganar peso. No suele tener apetito, le cuesta comer. Acumula poca grasa, sobre todo en abdomen y parte baja de la espalda.' },
    { value: 'ecto-meso', label: 'Ecto-meso (el "fibrado")', img: '/biotipos/ecto-meso.webp', desc: 'Delgado pero "fibroso" (como el anterior, pero con tono). Suele ser nervioso y le gusta el deporte, normalmente cardio, que se le da mejor. Si entrena fuerza hace descansos cortos, no puede estar parado. Puede acumular algo de grasa en el abdomen, pero no suele ser problema por ser más activo.' },
    { value: 'ecto-endo', label: 'Ecto-endo (el "gordi-flaco")', img: '/biotipos/ecto-endo.webp', desc: 'Delgado pero con "tripita", no se cuida mucho la dieta (el típico "fofisano"). Se ve claramente que es una persona delgada pero con más grasa. No la acumula concentrada en un solo sitio, sino dispersa por varias áreas (abdomen, caderas, espalda baja) en cantidades pequeñas.' },
    { value: 'mesomorfo', label: 'Mesomorfo (el fuerte)', img: '/biotipos/mesomorfo.webp', desc: 'El típico que está fuerte de serie, con buena genética para desarrollar músculo en cuanto entrena. Estructura ósea ancha, ideal para la fuerza, con clavículas amplias y caderas estrechas. Come bastante y no coge grasa con facilidad. Si acumula, en abdomen y algo en piernas.' },
    { value: 'meso-endo', label: 'Meso-endo (el "gordi-fuerte")', img: '/biotipos/meso-endo.webp', desc: 'Gana músculo con facilidad pero también grasa. Le gusta bastante comer; para no taparse tiene que cuidarse todo el año, incluso en volumen. Como no necesita comer mucho para ponerse fuerte y le gusta comer, lo normal es verle "tapado". Grasa en abdomen, caderas y espalda baja.' },
    { value: 'endo-meso', label: 'Endo-meso (el grande)', img: '/biotipos/endo-meso.webp', desc: 'Como el meso-endo pero con más tendencia a ganar grasa. Se le ve "grande", tiene músculo pero niveles muy altos de grasa. Le gusta comer y para definir tiene que comer poco, cosa que le cuesta mucho. Grasa sobre todo en abdomen, caderas, espalda baja y muslos.' },
    { value: 'endomorfo', label: 'Endomorfo (el gordo)', img: '/biotipos/endomorfo.webp', desc: 'Tendencia clara a engordar y niveles altos de grasa casi toda la vida. Suele llevar vida muy sedentaria y malos hábitos. El abdomen es la zona más problemática (barriga prominente, grasa visceral). También acumula en muslos, caderas, brazos y espalda.' },
];

import BodyFatSlider, { BF_PERCENTAGES, BF_DEFAULT } from '../components/SelectorGrasa';
import { mensajeDeError } from '../lib/mensajeDeError';

// ─────────────────────────────────────────────────────────────────────────────
// EL ALTA - cuatro preguntas y ya tiene macros (doc 29-07, paso 1).
//
// Solo lo que hace falta para leer la tabla: sexo, objetivo, % de grasa y peso. De aqui sale
// con MACROS PROVISIONALES y con la app usable el mismo dia. Todo lo demas espera al
// cuestionario de ajuste, detras de un boton, porque cada pantalla que se pone antes de
// entregar algo cuesta gente.
//
// El nombre y el telefono se piden en el registro, no aqui.
//
// type: statement | text | email | tel | date | number | choice | bf | dieta | final0 | result
// Los datos de la tabla: sexo, objetivo, peso y grasa. Ya NO terminan en un cálculo: desde
// el 07-08 el alta es un único recorrido (punto 15 del documento) y estas preguntas son solo
// su primer tramo. El cálculo va una sola vez, al final, cuando ya están también las
// respuestas que mueven los hidratos; así lo que se le entrega son sus macros de verdad y no
// unos provisionales que había que ajustar después en otro cuestionario.
// Los textos son los del documento «LOS TEXTOS DE LA APP» de Jesús (6 de agosto, versión
// definitiva), literales, con su aclaración debajo de cada pregunta. El orden también es el
// suyo: objetivo, confirmación, experiencia, datos, actividad, deporte, apetito, engordo,
// definir, biotipo, grasa y dieta.
const PREGUNTAS_ALTA = [
    { type: 'statement', title: 'Empecemos', desc: 'Unas preguntas y tienes tus macros.' },
    {
        type: 'choice', key: 'goal', title: '¿Cuál es tu objetivo?',
        desc: 'Una de dos: o ganar masa muscular o perder grasa. Las dos cosas a la vez, NO. Piensa, prioriza y elige, por ese orden.',
        options: [
            { value: 'volumen', label: 'Ganar Masa Muscular (VOLUMEN)' },
            { value: 'definicion', label: 'Perder Grasa (DEFINICIÓN)' },
        ],
    },
    {
        type: 'choice', key: '_confirm', title: '¿Estás seguro?',
        desc: 'Mira bien, que luego no quiero que me digas que tú en realidad lo que querías era definir y perder grasa.',
        // opciones dinámicas según goal (se generan en render)
        confirm: true,
    },
    {
        // Pantalla 3 del documento. Estaba en el cuestionario largo, que solo ven los planes
        // con entrenador, y con cinco opciones por años. Jesús la quiere en el test de
        // entrada y con estas cuatro: lo que le interesa no es el desarrollo muscular, es si
        // sabe entrenar.
        type: 'choice', key: 'training_experience', title: '¿Qué experiencia tienes entrenando fuerza en el gimnasio?',
        desc: 'Me da igual el grado de desarrollo muscular que tengas en este momento, me interesa saber si sabes entrenar y cuánta experiencia tienes.',
        options: [
            // Los cuatro, literales del documento del 18-08.
            { value: 'cero', label: 'Ninguna, empiezo ahora o hace mucho que no entreno. Parto de cero.' },
            { value: 'principiante', label: 'Llevo menos de 1 año entrenando con regularidad (principiante).' },
            { value: 'intermedio', label: 'Llevo más de un año entrenando, aunque no siempre me lo he tomado en serio (intermedio).' },
            { value: 'avanzado', label: 'Llevo años entrenando de forma seria (avanzado).' },
        ],
    },
    {
        type: 'choice', key: 'sex', title: 'Hombre o mujer.',
        desc: 'Lo usamos para calcular tus macros con la tabla correcta.',
        options: [
            { value: 'hombre', label: 'Hombre' },
            { value: 'mujer', label: 'Mujer' },
        ],
    },
    // El enunciado del documento, que es una pregunta y no una etiqueta.
    {
        type: 'number', key: 'weight', title: '¿Cuánto pesas?',
        desc: 'Pésate siempre en las mismas condiciones: en ayunas, sin ropa y después de ir al baño.',
        unit: 'kg', required: true,
    },
    {
        type: 'bf', key: 'body_fat', title: '¿Cuál dirías que es tu porcentaje de grasa actual?',
        // El enunciado del documento del 18-08, con sus dos paréntesis.
        desc: 'Pasa las fotos y quédate en el punto que más se parezca a cómo te ves ahora. '
            + 'Sin apretar ni meter tripa y con buena luz. (Procura que sean siempre en el mismo sitio.) '
            + '(Frente y espaldas, que coincidan, lógicamente. Si dudas entre dos, tira para arriba.)',
    },
];

// ─────────────────────────────────────────────────────────────────────────────
// AJUSTAR MACROS - el cuestionario del paso 2, detras de un boton.
//
// Todo lo que ajusta el numero: lo que hace fuera del gimnasio, como responde su cuerpo y la
// dieta que trae. Al terminar se le entregan los MACROS DEFINITIVOS.
// Trae una dieta de la que partir: la mide (`true`) o se cuida sin medirla (`parecido`).
// El "sin control pero no como mal" (`false`) y el "como mal y desorganizado"
// (`desorganizado`) no traen nada que copiar, asi que a esos dos no se les pregunta por su
// dieta. Se define aqui, en un solo sitio, porque de esto colgaban seis condiciones sueltas
// y al anadir la cuarta respuesta del documento de textos habia que acertar en las seis.
const traeDieta = (a) => a.sigue_dieta === true || a.sigue_dieta === 'parecido';

const STEPS_AJUSTE = [
    { type: 'statement', title: 'Ajusta tus macros', desc: 'Unas preguntas para ajustar tus números a tu vida real. Verás los macros moverse a medida que contestas.', cta: 'Vamos' },
    {
        // CUATRO opciones (pantalla 5 del documento de textos), donde antes había tres. Ojo
        // con los macros: el +10 % de hidratos lo cobra SOLO "muy activo", que es lo que dice
        // el documento del 07-08. Las otras tres no suben nada, ni siquiera la de en medio.
        // Los valores viejos (`sedentario` / `normal`) se conservan para los clientes que ya
        // contestaron: `sedentario` es ahora "muy sedentario" y `normal` "ligeramente activo".
        type: 'choice', key: 'actividad_diaria', title: '¿Cómo describirías tu nivel de actividad diaria?',
        desc: 'Ir al gimnasio 1 hora 4-5 veces a la semana no te convierte en una persona activa, OJO. Piensa en lo mucho o lo poco que te mueves en tu día a día.',
        options: [
            // Los cuatro textos, literales del documento del 18-08.
            { value: 'sedentario', label: 'Muy sedentario: paso casi todo el día sentado, apenas me muevo.' },
            { value: 'normal', label: 'Ligeramente activo: mi trabajo es mayormente sentado, pero intento moverme un poco (doy paseos, subo escaleras en vez de usar el ascensor, evito usar el coche, etc.).' },
            { value: 'moderado', label: 'Moderadamente activo: me mantengo en movimiento durante gran parte del día, aunque tampoco hago esfuerzos físicos importantes.' },
            { value: 'muy_activo', label: 'Muy activo: mi día a día es muy demandante a nivel físico, no paro.' },
        ],
    },
    {
        type: 'choice', key: 'deporte_extra', title: '¿Practicas otro deporte con intensidad?',
        // El subtítulo del doc del 23-08 (punto 11): lo que importa no es la lista de
        // deportes, es si compite o entrena en serio y piensa seguir.
        desc: 'Me refiero a si compites en algo, o entrenas con intensidad algún deporte y tienes intención de continuar con ello.',
        options: [
            { value: true, label: 'Sí' },
            { value: false, label: 'No' },
        ],
    },
    {
        // Las dos preguntas de seguimiento de la pantalla 6. Solo para el que ha dicho que sí.
        // No mueven macros: sirven para que el entrenador sepa qué hace y cuándo.
        type: 'text', key: 'deporte_cual', title: '¿Cuál, cuántos días y a qué intensidad?',
        cond: a => a.deporte_extra === true,
        placeholder: 'Por ejemplo: pádel, dos días entre semana, a buen ritmo',
        textarea: true, required: true,
    },
    {
        type: 'choice', key: 'deporte_en_descanso',
        title: '¿Habría posibilidad de que lo hicieras en días en que no vayas al gimnasio?',
        cond: a => a.deporte_extra === true,
        options: [
            { value: true, label: 'Sí' },
            { value: false, label: 'No' },
            { value: 'ya', label: 'Ya lo hago así' },
        ],
    },
    {
        // Pantalla 7, nueva. No mueve macros: alimenta el perfil.
        // «Casi nada» es del doc del 23-08 (punto 6): cuarta opción, tampoco mueve macros.
        type: 'choice', key: 'apetito', title: '¿Eres de buen comer?',
        options: [
            { value: 'mucho', label: 'Mucho' },
            { value: 'normal', label: 'Lo normal' },
            { value: 'poco', label: 'Poco' },
            { value: 'casi_nada', label: 'Casi nada' },
        ],
    },
    {
        // LAS CUATRO DEL DOC DEL 23-08 (punto 7). Los valores viejos se conservan
        // (enseguida/normal/casi_no); el cuarto es `nada` y en el motor cobra el mismo
        // +20 % de hidratos que `casi_no` (macro_engine.RESPUESTAS_QUE_SUBEN): quien dice
        // que le cuesta mucho coger peso no puede subir menos que quien dice «casi no».
        type: 'choice', key: 'facilidad_engordar', title: 'Cuando te pasas comiendo, ¿engordas?',
        desc: 'Piensa en vacaciones, Navidades o épocas en las que sueles comer de más.',
        options: [
            { value: 'enseguida', label: 'Sí, enseguida, a nada que me paso' },
            { value: 'normal', label: 'Lo normal' },
            { value: 'casi_no', label: 'Casi no' },
            { value: 'nada', label: 'No, nada, me cuesta mucho coger peso' },
        ],
    },
    {
        // No mueve macros: alimenta el biotipo declarado.
        // «¿Te cuesta perder peso?» (doc 23-08, punto 8): la palabra «definir» es de
        // gimnasio y no todo el mundo la tiene. La clave y los valores se conservan.
        type: 'choice', key: 'cuesta_definir', title: '¿Te cuesta perder peso?',
        options: [
            { value: 'mucho', label: 'Sí, mucho' },
            { value: 'normal', label: 'Lo normal' },
            { value: 'poco', label: 'Qué va, todo lo contrario' },
        ],
    },
    {
        // ── El biotipo y la altura, para LOS TRES PLANES ──────────────────────────
        // Estaban en el perfil largo, que solo ven los planes con coach, así que el de
        // 297 € nunca decía qué biotipo cree que es ni cuánto mide. Y sin altura no hay
        // índice de muscularidad, que es justo el regalo del acceso gratis.
        //
        // No mueven macros: el biotipo es una hipótesis de partida que el coach corrige
        // viendo cómo responde. Pero se guardan, y sin ellos no hay ni ficha ni modelo.
        type: 'biotype_intro',
        title: 'Ahora tienes que elegir tu biotipo, es decir, tu tipo de cuerpo.',
        desc: 'Es la tendencia natural de tu cuerpo según tu genética (independientemente de tu estado físico actual o los hábitos que tengas en este momento). Antes te explico los 7 que hay (después eliges):',
        // EN MUJERES NO SE ENSEÑA. Las siete fotos de los biotipos son de hombre y no hay
        // versión de mujer: enseñárselas para que se identifique es pedirle que elija mal.
        // Petición explícita del documento del 06-08-2026 ("que el test de mujer no
        // muestre la pantalla del biotipo"). Cuando existan las fotos, se quitan las dos
        // condiciones de aquí y de la pantalla siguiente.
        cond: a => a.sex !== 'mujer',
    },
    {
        type: 'biotype', key: 'biotype',
        title: 'Indica cuál de los 7 biotipos corporales es el tuyo',
        desc: 'Puedes volver atrás y leer las descripciones. Si no te identificas claramente con ninguno, elige el que más se acerque a ti.',
        cond: a => a.sex !== 'mujer',
    },
    {
        type: 'number', key: 'height', title: '¿Cuánto mides?', desc: 'Tu altura, en cm.',
        unit: 'cm', required: true,
    },
    {
        // CUATRO respuestas, las del documento de textos de Jesús (06-08, pantalla 12).
        // Antes eran tres, y antes de eso dos. La diferencia que importa: las dos primeras
        // traen una dieta de la que partir y las dos últimas no, pero "sin control pero no
        // como mal" y "como mal y desorganizado" no son lo mismo y hasta ahora caían las dos
        // en el mismo saco.
        //
        // Los valores se conservan (`true` / `parecido` / `false`) para no romper lo que ya
        // está guardado de los clientes que contestaron antes; el cuarto es `desorganizado`,
        // que es nuevo y se comporta como el "sin control" a efectos de macros.
        type: 'choice', key: 'sigue_dieta', title: '¿Sigues algún tipo de dieta en este momento?',
        desc: 'Si controlas más o menos tus cantidades, podremos partir de lo que ya comes.',
        options: [
            { value: true, label: 'Estricta, mido todo lo que como.' },
            { value: 'parecido', label: 'Pesar no, pero me cuido bastante.' },
            { value: false, label: 'Sin control, pero no como mal.' },
            { value: 'desorganizado', label: 'Como mal y desorganizado.' },
        ],
    },
    {
        // P7: se guarda. Un mes comiendo asi no dice lo mismo que seis.
        type: 'choice', key: 'tiempo_dieta', title: '¿Cuánto tiempo llevas con esa dieta, o con una parecida?',
        cond: traeDieta,
        options: [
            { value: 'menos_1m', label: 'Menos de un mes' },
            { value: '1_3m', label: 'Entre 1 y 3 meses' },
            { value: '3_6m', label: 'Entre 3 y 6 meses' },
            { value: 'mas_6m', label: 'Más de 6 meses' },
        ],
    },
    {
        // P8: la que decide que se hace con su dieta (paso 4 del metodo). Las opciones cambian
        // segun el objetivo, porque "ir bien" no es lo mismo definiendo que en volumen.
        // A LOS TRES, también al que come lo que surge. Es la mejor pregunta del
        // cuestionario: sitúa su comida respecto a su mantenimiento sin pedirle un solo
        // número. Si dice que mantiene, lo que come ES su mantenimiento, y eso pesa más
        // que "como bastante", que es una opinión. Antes solo se le preguntaba al que
        // seguía una dieta medida, que es justo el que menos falta le hace.
        type: 'choice', key: 'como_va',
        title: a => (!traeDieta(a)
            ? 'Con lo que comes ahora, ¿mantienes el peso, ganas o pierdes?'
            : '¿Cómo te está funcionando?'),
        desc: 'Sé sincero: de esto depende que partamos de lo que comes o de lo que te toca comer.',
        options: a => (a.goal === 'volumen' ? [
            { value: 'bien', label: 'Bien: estoy subiendo peso.' },
            { value: 'lento', label: 'Regular: subo, pero muy lento.' },
            { value: 'mucha_grasa', label: 'Regular: subo, pero cojo más grasa de la cuenta.' },
            { value: 'mantengo', label: 'Me mantengo igual, siento que necesito comer más.' },
            { value: 'bajando', label: 'Mal: en lugar de subir, estoy bajando.' },
        ] : [
            { value: 'bien', label: 'Bien: estoy bajando a buen ritmo.' },
            { value: 'lento', label: 'Estoy bajando, pero muy lento.' },
            { value: 'mantengo', label: 'Me mantengo.' },
            { value: 'cogiendo_peso', label: 'Mal: estoy cogiendo peso.' },
        ]),
    },
    {
        // P9: no cambia el macro de arranque; marca el ritmo de los ajustes de cada mes.
        type: 'choice', key: 'hambre_saturacion',
        title: a => (a.goal === 'volumen' ? '¿Estás saturado de comer?' : '¿Pasas hambre o ansiedad comiendo así?'),
        desc: 'No cambia tus macros de hoy: nos dice con cuánta mano irán los ajustes de cada mes.',
        cond: traeDieta,
        options: a => (a.goal === 'volumen' ? [
            { value: 'no_puedo_mas', label: 'No estoy saturado, pero tampoco me veo capaz de comer más.' },
            { value: 'puedo_mas', label: 'Puedo comer más sin problema.' },
        ] : [
            { value: 'mucho', label: 'Mucho.' },
            { value: 'normal', label: 'Lo normal cuando estás a dieta.' },
            { value: 'aguanto_mas', label: 'Nada: aguanto mucho más que esto.' },
        ]),
    },
    {
        // Al que no lo tiene medido se le pide UN DÍA, no "lo que comes en general".
        // Nadie sabe lo que come en general; todo el mundo se acuerda de lo que comió
        // ayer. Con un día tipo el sistema ya puede leerlo, y la pregunta imposible se
        // convierte en una fácil.
        // EL DÍA TIPO SE LO PIDE A TODOS (pantalla 19 del doc del 18-08). Antes solo salía
        // a quien decía seguir una dieta, y justo el que come «sin control» o «mal y
        // desorganizado» es del que menos se sabe. Su día no entra en el cálculo si no
        // trae dieta -- eso lo decide el motor, no esta pantalla -- pero se guarda, que es
        // de lo que va la pregunta: «para que sepamos de dónde partes más o menos».
        type: 'dieta', title: 'Indica un día tipo',
        desc: a => (a.sigue_dieta === 'parecido'
            ? 'Aunque no comas siempre lo mismo, ponme un día tipo. El de ayer, por ejemplo.'
            : 'Para que sepamos de dónde partes más o menos.'),
    },
    // «CONFIRMA TUS RESPUESTAS» (doc del 23-08, punto 16): antes decía «Y ya estaría» sin
    // enseñar ni una sola respuesta. Ahora es el repaso con la rejilla; tocar una tarjeta
    // salta a su pregunta y contestar devuelve aquí.
    { type: 'final0', title: 'Confirma tus respuestas', desc: 'Repásalas antes de calcular. Si quieres cambiar algo, toca encima.' },
    { type: 'result', title: 'Tus macros' },
];

// Lo que viene despues de entregar los macros. Aqui ya no se le PIDE nada: se le ENSEÑA.
//
// Salieron de aqui, por el doc del 29-07:
//   - cuantas comidas, cuantos dias entrena y cuando entrena -> al perfil, con los valores por
//     defecto del metodo. Ninguna cambia los totales, solo el reparto, y se cambian cuando quiera
//     desde Nutricion. Puestas aqui eran tres pantallas que no movian ningun numero.
//   - los alimentos que le gustan y las alergias -> a la primera dieta. No sirven para calcular
//     macros, sirven para generar comida, y tienen sentido justo cuando va a ver su primer menu.
const STEPS_ONBOARD = [
    // Paso 3 del doc: se le piden fotos y medidas justo despues de darle los macros, que es
    // cuando mas motivado esta. Y a cambio se le entrega su ficha.
    { type: 'partida', title: 'Ya tienes tus macros' },
    { type: 'ficha', title: 'Tu punto de partida' },
    { type: 'magia', title: 'Comidas que puedes comer hoy' },
];

// NIVEL 1 - solo planes con coach. Alimenta el perfil y el caso gemelo; NO toca macros.
//
// El biotipo y la altura SE FUERON DE AQUÍ a las preguntas que ven los tres planes
// (06-08-2026): estando aquí, el de 297 € no los daba nunca, y sin altura no hay índice
// de muscularidad. Preguntarlos otra vez aquí sería preguntar dos veces lo mismo.
// Las preguntas que viven en el cuestionario de ajuste y que el completo también usa. Se
// referencian, no se copian: una pregunta, un sitio donde se define. Si alguien le cambia el
// texto a una, cambia en los dos cuestionarios, que es lo que se quiere.
const delAjuste = (clave) => {
    const paso = STEPS_AJUSTE.find(s => s.key === clave);
    if (!paso) throw new Error(`El completo pide una pregunta del ajuste que no existe: ${clave}`);
    return paso;
};

// LOS HITOS DE PESO, cada uno con su año. Se definen aquí arriba porque los usan los dos
// cuestionarios: el básico se los pregunta a todo el mundo, y el completo solo al que
// entró antes de que el básico existiera.
//
// «EL PESO MÁS BAJO» SE QUITÓ ENTERO (doc del 23-08, punto 4): eran tres hitos y quedan
// dos. El campo `peso_minimo` sigue existiendo en el modelo y en las fichas que lo
// tienen contestado; solo deja de preguntarse.
const PESO_HITOS = [
    {
        // Obligatoria (regla 2 del doc del 23-08): el peso y su año. La nota sigue siendo
        // opcional, que para eso lo dice su etiqueta.
        type: 'peso_hito', key: 'peso_maximo', required: true,
        title: '¿Cuál fue tu máximo peso alcanzado y cuándo?',
        desc: 'Me refiero a cuándo estuviste en tu peor forma física.',
        nota: 'Cuéntame lo que quieras de esa época',
    },
    {
        // Con su salida «Si no, pásala» (doc 23-08, punto 3): el que nunca ha estado en
        // forma no tiene nada que contestar aquí y se le da la puerta con esas palabras.
        type: 'peso_hito', key: 'peso_mejor_momento', conFoto: true, pasala: true,
        title: '¿Has estado muy en forma alguna vez?',
        desc: 'Si es que sí, dime cuándo y tu peso en aquel momento.',
        nota: 'Cuéntame lo que quieras',
    },
];

const STEPS_NIVEL1 = [
    // Sin el «estas ya no cambian tus macros» del final (punto 4.18, decisión de Jesús): el
    // cliente no tiene por qué saber qué pregunta mueve qué número, y decírselo solo invita
    // a contestar a la ligera lo que él cree que no cuenta.
    // «Para el equipo» suena a departamento; al cliente se le habla de nosotros. Y el número
    // de preguntas se dice: sin él, «tu perfil completo» deja la sensación de que puede ser
    // eterno, y eso cuesta altas (Jesús, 11-08). El número se cuenta abajo sobre la lista de
    // verdad, para que no se quede viejo en cuanto alguien añada o quite una.
    { type: 'statement', title: 'Ahora, tu perfil completo', desc: '', cta: 'Seguir' },
    { type: 'date', key: 'birthdate', title: 'Fecha de nacimiento', desc: 'La verdadera, no me engañes.', required: true },
    // La experiencia entrenando SE FUE DE AQUÍ al test de entrada (pantalla 3 del documento
    // de textos de Jesús), y con sus cuatro opciones, no con los cinco tramos por años que
    // había. Aquí solo la veían los planes con entrenador; ahora la contestan los tres, que
    // es lo que él quiere: le interesa saber si sabe entrenar, no cuántos años lleva.
    //
    // ── Pantallas 6 y 7 · lo médico ─────────────────────────────────────────────
    // LAS DOS FALTABAN. Estaban en el cuestionario de siempre y desaparecieron por el
    // camino, así que hoy se le monta una rutina y una dieta sin saber si tiene una
    // patología que se lo desaconseje o si está medicado. Vuelven con su enunciado literal.
    {
        type: 'choice', key: 'patologia',
        title: '¿Tienes algún tipo de enfermedad o patología que te condicione a la hora de practicar cualquier tipo de actividad física o iniciar un programa nutricional?',
        options: [
            { value: 'si', label: 'Sí' },
            { value: 'no', label: 'No' },
        ],
    },
    {
        type: 'text', key: 'patologia_detalle', textarea: true,
        title: 'Necesito que me des más detalles en este sentido para poder confeccionar un programa lo más adaptado posible a tus necesidades, pero sobre todo para evitar correr riesgos de forma innecesaria.',
        cond: a => a.patologia === 'si',
    },
    {
        type: 'choice', key: 'medicacion',
        title: '¿Tomas algún tipo de medicación o estás realizando algún tratamiento con fármacos bajo prescripción médica?',
        options: [
            { value: 'si', label: 'Sí' },
            { value: 'no', label: 'No' },
        ],
    },
    {
        type: 'text', key: 'medicacion_detalle', textarea: true,
        title: 'Indica cuál, en qué dosis, tiempo que llevas usándolo y para qué lo tienes pautado.',
        cond: a => a.medicacion === 'si',
    },
    {
        // P14. La respuesta se guarda; la regla de como afecta a los macros la dara Jesus.
        // La tercera opción es «Lo estoy valorando», no «lo seguí antes»: lo que hay que
        // saber es si va a empezar, que es cuando el equipo tiene algo que decir. Las fichas
        // viejas pueden traer `antes`, y se siguen leyendo.
        type: 'choice', key: 'trt', title: '¿Sigues algún tratamiento hormonal tipo TRT?',
        desc: 'Es información médica y la trata el equipo. No cambia tus macros.',
        options: [
            { value: 'si', label: 'Sí' },
            { value: 'no', label: 'No' },
            { value: 'valorando', label: 'Lo estoy valorando' },
        ],
    },
    {
        // Bloque 4: la intención cuenta tanto como el uso. Quien piensa empezar hay que
        // saberlo ANTES, no cuando ya lo ha hecho.
        //
        // LAS CINCO RESPUESTAS DEL DOCUMENTO, literales. Las cuatro que había las escribí yo
        // y se quedaban cortas justo donde importa: metían en el mismo saco al que usó hace
        // años y al que está con un quemagrasas ahora mismo. Los valores viejos
        // (`uso` / `use` / `intencion` / `nunca`) se siguen leyendo en las fichas antiguas.
        type: 'choice', key: 'farmacologia_uso',
        title: '¿Usas o has usado ayudas farmacológicas?',
        desc: 'Sin juicios: se pregunta porque cambia lo que se te puede pedir y lo que hay que vigilar.',
        options: [
            { value: 'no', label: 'No.' },
            { value: 'pasado', label: 'Actualmente no, lo hice en el pasado, pero no planeo repetirlo.' },
            { value: 'frecuente', label: 'Ahora mismo no, pero suelo usarlos con frecuencia.' },
            { value: 'quemagrasas', label: 'Si te refieres a anabolizantes para ganar masa muscular no, pero en este momento estoy usando fármacos para quemar grasa (Ozempic, efedrina, etc.).' },
            { value: 'ciclo', label: 'Sí, estoy haciendo un ciclo de esteroides anabolizantes en este momento.' },
        ],
    },
    {
        type: 'text', key: 'farmacologia_detalle', textarea: true,
        title: 'Necesito que me des todos los detalles en este sentido: cuántos sueles hacer, cuándo terminaste el último, qué dosis usaste, durante cuánto tiempo, si recuperaste bien y lo comprobaste con una analítica, etc. Si tienes previsto hacer más, dímelo también.',
        cond: a => !!a.farmacologia_uso && a.farmacologia_uso !== 'no' && a.farmacologia_uso !== 'nunca',
    },
    // ── Pantallas 10 y 11 · el descanso ─────────────────────────────────────────
    // Estaban dentro de una pantalla de «Salud y descanso» con cinco campos sueltos, con
    // tres respuestas de andar por casa («Bien (7-8h)») en vez de los tramos de Jesús. Y el
    // nivel de estrés, que compartía pantalla con ellas, se va: decisión suya, bloque 5.
    {
        type: 'choice', key: 'horas_sueno', title: '¿Cuántas horas duermes al día normalmente?',
        options: [
            { value: 'min_7_30', label: 'Mínimo 7 y media' },
            { value: '6_7_30', label: 'Entre 6 y 7 horas y media' },
            { value: '5_6', label: 'Entre 5 y 6, no más' },
            { value: 'menos_5', label: 'Menos de 5' },
        ],
    },
    {
        type: 'choice', key: 'ayuda_dormir', title: '¿Tomas algún suplemento o fármaco para dormir mejor?',
        options: [
            { value: 'duermo_bien', label: 'No, duermo sin problema.' },
            { value: 'nada_ni_quiero', label: 'No, aunque no duermo muy bien, no tomo nada, ni quiero.' },
            { value: 'abierto', label: 'No, aunque no duermo bien, no tomo nada, pero estaría abierto a tomar algún tipo de suplemento que me ayudara en este sentido.' },
            { value: 'suplementos', label: 'Sí, tomo suplementos para esto, no fármacos.' },
            { value: 'benzos_sin_pauta', label: 'Sí, de vez en cuando utilizo benzodiacepinas, pero no las tengo pautadas por mi médico.' },
            { value: 'medicacion_pautada', label: 'Sí, soy incapaz de dormir a no ser que utilice medicación (la tengo pautada).' },
        ],
    },
    // ── Pantallas 12, 13 y 14 · su suplementación ───────────────────────────────
    // No existía. El equipo le pauta suplementos sin saber qué está tomando ya, que es
    // la forma más rápida de repetirle algo o de chocar con lo que lleva.
    {
        // Las cuatro del documento. La pregunta no es si la quiere, es hasta dónde le
        // dejas llegar: las cuatro empiezan por «no» y lo que cambia es cuánto acepta.
        // Los valores `lo_justo` y `no` son los de antes, así que lo contestado se conserva.
        type: 'choice', key: 'quiere_pauta_suplementos',
        title: '¿Tienes algún inconveniente en utilizar suplementación deportiva?',
        options: [
            { value: 'libertad', label: 'No. De hecho, suelo utilizarlos habitualmente. Tienes libertad absoluta para mandarme todo lo que consideres que me vaya a ayudar a avanzar más deprisa.' },
            { value: 'abierto', label: 'No. Normalmente no utilizo, pero no tendría problema en empezar a usarlos si lo consideras oportuno.' },
            { value: 'lo_justo', label: 'No, pero ponme 1 o 2 como mucho, no me puedo permitir más o sencillamente no me apetece.' },
            { value: 'no', label: 'No me pongas nada, el tema de la suplementación lo descarto por completo.' },
        ],
    },
    {
        type: 'text', key: 'suplementos_ahora',
        title: '¿Qué suplementos tomas ahora?',
        desc: 'Cuáles y a qué dosis, si la sabes. Si no tomas ninguno, escribe "ninguno".',
        textarea: true,
    },
    {
        // Sustituye a «¿Y cuáles has tomado antes?», que se va (bloque 5: nadie se acuerda y
        // no cambia lo que se le pauta). Esta sí: lo que no puede o no quiere tomar es lo
        // único de las dos que cambia la pauta que se le manda.
        type: 'text', key: 'suplementos_veto',
        title: '¿Existe algún suplemento en concreto que tengas contraindicado o que no quieras tomar?',
        desc: 'Si no hay ninguno, escribe "no".',
        textarea: true,
    },
    // ── Las cuatro de la dieta: AQUÍ, no en el básico (punto 26 del doc del 19-08) ──
    // «Las cuatro de la dieta se van al cuestionario largo: si sigue una, cuánto lleva,
    // cómo le va y si pasa hambre.» El cliente nuevo con entrenador las contesta aquí; al
    // que ya las tenga contestadas de antes no se le repiten (la condición de abajo).
    //
    // Son las mismas preguntas, no copias: se referencian del cuestionario de ajuste, que es
    // donde viven. La condición se les pone abajo, junto a las demás.
    delAjuste('sigue_dieta'), delAjuste('tiempo_dieta'), delAjuste('como_va'),
    delAjuste('hambre_saturacion'),
    // ── Las que ya contestó en el básico ────────────────────────────────────────
    // El deporte se queda en el básico (lo necesita el motor); aquí solo sale para el que
    // entró antes de que el básico existiera.
    delAjuste('deporte_extra'), delAjuste('deporte_cual'), delAjuste('deporte_en_descanso'),
    // Y sus tres hitos de peso, por lo mismo: subieron al básico y el que no pasó por él no
    // los ha dado nunca.
    ...PESO_HITOS,
    {
        // P23
        type: 'choice', key: 'tiempo_intentandolo', title: '¿Cuánto tiempo llevas intentando conseguir este objetivo?',
        // CINCO, las del documento del 18-08. Faltaba «Empiezo ahora», que es justo la del
        // que se acaba de dar de alta sin haberlo intentado nunca: sin esa opción se veía
        // obligado a decir que lleva menos de seis meses, que no es verdad.
        options: [
            { value: 'ahora', label: 'Empiezo ahora' },
            { value: 'menos_6m', label: 'Menos de 6 meses' },
            { value: '6m_2a', label: 'Entre 6 meses y 2 años' },
            { value: 'mas_2a', label: 'Más de 2 años' },
            { value: 'siempre', label: 'Llevo toda la vida con esto' },
        ],
    },
    {
        // P26, el cierre. EN TEXTO LIBRE, no con cinco opciones (doc del 18-08: «el motivo
        // de apuntarse, de Francisco: la versión de siempre dice lo mismo y mejor»). Las
        // opciones cerradas le hacen elegir el motivo que más se parece al suyo; el texto
        // libre es donde de verdad cuenta por qué ahora y no antes, que es lo que se lee.
        type: 'text', textarea: true, key: 'motivo_apuntarse', required: true,
        title: 'Dime el motivo principal de querer trabajar conmigo, qué esperas y por qué te decides a empezar ahora y no antes.',
    },
    // Desde la fusión del 23-08 (punto 13), al cliente nuevo esto se lo pregunta el básico
    // dentro de «¿Has tenido entrenador o has hecho dietas antes?»: aquí solo le sale a
    // quien no contestó ninguna de las dos (los de Calma). La condición del básico
    // (YA_ESTAN_EN_EL_BASICO) le añade encima el «solo si dietas_previas está vacía».
    { type: 'text', key: 'dietas_previas', title: '¿Has hecho dietas antes? ¿Qué tal te fue?', desc: 'Cuáles, cuánto duraste, qué pasó con tu peso...', textarea: true, required: true,
      cond: a => a.entrenador_anterior === undefined || a.entrenador_anterior === null || a.entrenador_anterior === '' },
    // ── Pantallas 19, 20 y 21 · cómo entrena hoy ────────────────────────────────
    // Comidas al día, días de entreno y cuándo entrena YA no se preguntan: van por defecto
    // y se cambian en Preferencias (bloque 5 del doc del 18-08).
    {
        // Bloque 3: si entrena AHORA no es lo mismo que cuántos años lleva. Uno puede
        // llevar diez años entrenando y estar parado desde marzo.
        //
        // Las CUATRO del documento. Las tres de antes no distinguían al que está parado por
        // una temporada del que no entrena, y a uno le montas la rutina de vuelta y al otro
        // una de empezar de cero.
        type: 'choice', key: 'entrena_ahora', title: '¿Entrenas ahora mismo de forma regular?',
        options: [
            { value: 'si', label: 'Sí, voy mínimo 3 días y entreno en serio.' },
            { value: 'irregular', label: 'Sí, pero voy poco y no entreno en serio.' },
            { value: 'parada_puntual', label: 'Actualmente no, pero ha sido una parada muy puntual, generalmente entreno siempre.' },
            { value: 'no', label: 'No.' },
        ],
    },
    {
        // SOLO AL QUE NO PRACTICA OTRO DEPORTE (pantalla 21 del doc): «Si ya ha dicho que
        // practica un deporte con intensidad, esta no se le enseña. No tiene sentido.»
        // Y las cuatro respuestas de Jesús, que no preguntan cuánto cardio hace sino qué
        // relación tiene con él, que es lo que decide cuánto se le puede mandar.
        type: 'choice', key: 'cardio', title: '¿Haces cardio?',
        cond: a => a.deporte_extra !== true,
        options: [
            { value: 'si_me_gusta', label: 'Sí, además me gusta, pero sé que ahora lo principal es el entrenamiento de fuerza. Por eso, en cuanto al cardio, ponme lo que consideres que me irá mejor.' },
            { value: 'si_lo_odio', label: 'Sí, pero lo odio. Lo hago porque quiero perder grasa, pero cuanto menos cardio me marques mejor.' },
            { value: 'no_pero_abierto', label: 'No, pero no tendría inconveniente en empezar a hacerlo si lo consideras oportuno.' },
            { value: 'no_jamas', label: 'No, no me gusta y no lo haré en ningún caso. Ahórratelo (aunque soy consciente de que esto implica apretar más la dieta).' },
        ],
    },
    // ── Pantalla 22 · las lesiones ──────────────────────────────────────────────
    // Antes era una sola pregunta suelta («¿hay algún ejercicio que no puedas hacer?») y
    // un campo perdido dentro de la pantalla de salud. Ahora son la pregunta y sus tres
    // detalles, que es lo que el entrenador necesita para no mandarle lo que le duele.
    {
        type: 'choice', key: 'lesion',
        title: '¿Arrastras alguna lesión o molestia que te condicione a la hora de entrenar fuerza?',
        options: [
            { value: 'si', label: 'Sí' },
            { value: 'no', label: 'No' },
        ],
    },
    {
        type: 'text', key: 'lesion_cual', title: 'Especifica tu lesión', textarea: true,
        cond: a => a.lesion === 'si',
    },
    {
        type: 'text', key: 'lesion_tiempo', title: '¿Cuánto tiempo llevas arrastrándola?',
        cond: a => a.lesion === 'si',
    },
    {
        type: 'text', key: 'ejercicios_imposibles', textarea: true,
        title: 'Enumera ejercicios concretos que no puedes hacer a causa de tu lesión',
        cond: a => a.lesion === 'si',
        pie: 'Tanto esta lista como la de la maquinaria las revisaremos todos los meses, por si hubiera cualquier novedad.',
    },
    // ── Pantallas 23 y 24 · con qué cuenta para entrenar ────────────────────────
    {
        // LAS SIETE DEL DOCUMENTO. Iba una lista mía de seis que mezclaba cosas («Máquinas»
        // a secas) y se dejaba fuera el banco, que decide media rutina de empuje.
        // OJO: esta lista es una de las cinco que Jesús marcó en amarillo para revisar.
        type: 'multiselect', key: 'material', title: '¿Con qué material cuentas para entrenar?',
        desc: 'Marca todo lo que tengas disponible.',
        options: [
            { value: 'gimnasio_completo', label: 'Gimnasio completo' },
            { value: 'banco', label: 'Banco' },
            { value: 'barra_olimpica', label: 'Barra olímpica' },
            { value: 'mancuernas', label: 'Mancuernas' },
            { value: 'bandas', label: 'Bandas elásticas' },
            { value: 'poleas', label: 'Máquinas de poleas' },
            { value: 'peso_corporal', label: 'Solo peso corporal' },
        ],
    },
    {
        // Lo que NO tiene importa tanto como lo que tiene: una rutina con jaula de
        // sentadilla no vale de nada si en su gimnasio no hay. Con el enunciado de Jesús,
        // que además pide lo contrario: la máquina rara que sí tiene.
        type: 'text', key: 'maquinas_que_faltan',
        title: 'En lo referente a maquinaria, si se te viene a la cabeza alguna máquina de esas que te encuentras en prácticamente cualquier gimnasio y sepas que en el tuyo no la hay, dímelo para evitar incluirla en tu rutina. Y si tienes alguna máquina más «especial», lo mismo, pónmela aquí.',
        textarea: true,
        pie: 'Tanto esta lista como la de las lesiones las revisaremos todos los meses, por si hubiera cualquier novedad.',
    },
    // Las intolerancias, por separado y no en texto libre: de "soy intolerante a la
    // lactosa" no se puede sacar si puede comer yogur o queso curado, y de ahí depende
    // media lista de la compra.
    {
        // LOS DOS ENUNCIADOS DEL DOCUMENTO (pantalla 21 del 18-08). Preguntaban «¿llevas
        // bien la lactosa?», que es volver a preguntarle lo que acaba de contestar: estas
        // dos solo salen si ya ha marcado esa intolerancia. Lo que falta saber es hasta
        // dónde le llega.
        type: 'choice', key: 'lactosa',
        title: '¿Es total o toleras algunos lácteos como yogur, queso curado o queso batido?',
        // SOLO SI HA DICHO QUE LE PASA ALGO CON LA LACTOSA. La condición vive aquí, con la
        // pregunta, y no solo en el básico: en el cuestionario largo salía siempre, y el que
        // no tiene ninguna intolerancia se encontraba «¿es total o toleras algunos lácteos?»
        // sin haber dicho nunca que le sentaran mal. Vale para la lista del básico y para el
        // texto libre del cuestionario viejo, porque `includes` sirve para las dos cosas.
        cond: a => !!(a.alergias || []).includes('lactosa'),
        options: [
            { value: 'total', label: 'Total: nada de lácteos' },
            { value: 'tolera_algo', label: 'Tolero el yogur, el queso curado o el queso batido' },
        ],
    },
    {
        type: 'choice', key: 'gluten',
        title: '¿Es celiaquía diagnosticada o sensibilidad?',
        desc: '¿Toleras pequeñas cantidades como pan de molde o avena sin gluten?',
        cond: a => !!(a.alergias || []).includes('gluten'),
        options: [
            { value: 'celiaquia', label: 'Celiaquía diagnosticada: nada de gluten' },
            { value: 'sensibilidad', label: 'Sensibilidad: tolero pequeñas cantidades' },
        ],
    },
    { type: 'text', key: 'alergias', title: '¿Alguna otra alergia o intolerancia?', desc: 'Frutos secos, marisco, huevo... Si no tienes, escribe "no".', textarea: true },
    // ── Pantalla 25 · sus fotos y sus medidas ───────────────────────────────────
    // El completo termina aquí, no en una pantalla de «ya está». Es obligatorio para
    // arrancar: sin fotos y sin medidas su entrenador no puede ponerle los macros buenos ni
    // montarle la rutina. No se le bloquea el paso (qué hacer con el que no las sube sigue
    // sin decidirse, bloque 6 del doc), pero se le dice por qué hacen falta.
    { type: 'fotos_medidas', obligatorio: true },
    { type: 'final1', title: 'Perfil completo.', desc: 'El equipo usará todo esto para tu estrategia. Si quieres revisar algo, ve hacia atrás.' },
];

// ═══════════════════════════════════════════════════════════════════════════════
// EL BÁSICO · las pantallas del bloque 2 del doc del 18-08, en su orden
// ═══════════════════════════════════════════════════════════════════════════════
//
// «24 pantallas en hombre, 22 en mujer (la mujer no lleva biotipo). Una pregunta por
// pantalla, sin títulos de sección: la barra de progreso se encarga.»
//
// Lo hace TODO EL MUNDO y es la única vez: «a los que no llevan plan personalizado no se
// les vuelve a preguntar nunca más». Por eso el básico es largo, y por eso lo que se
// conteste aquí va al perfil y no a un cuestionario de segunda fila.
//
// LAS PREGUNTAS NO SE DUPLICAN: las que ya existían se referencian por su clave, así que
// cada una sigue teniendo un solo sitio donde se define, con sus opciones y sus textos.
//
// EL DEPORTE SE QUEDA Y LAS CUATRO DE LA DIETA SE VAN (punto 26 del doc del 19-08). El
// 18-08 se quedaron aquí las cinco para no calcularle al de autogestión con menos
// información; Jesús contesta: «"¿Practicas otro deporte con intensidad?" se queda en el
// básico, con sus dos preguntas de detalle. Esa la necesita el motor. Las cuatro de la
// dieta se van al cuestionario largo. Sé lo que implica: al de autogestión se le
// calcularán los macros desde la tabla, sin ajustar por lo que ya come. Está decidido
// así.» El día tipo no es una de las cuatro y se queda: se guarda para el perfil, entre
// o no en el cálculo.
const _TODAS = [...PREGUNTAS_ALTA, ...STEPS_AJUSTE, ...STEPS_NIVEL1];
const q = (clave) => {
    const paso = _TODAS.find(s => s.key === clave);
    if (!paso) throw new Error(`El básico pide una pregunta que no existe: ${clave}`);
    return paso;
};
const porTipo = (tipo) => {
    const paso = _TODAS.find(s => s.type === tipo);
    if (!paso) throw new Error(`El básico pide una pantalla que no existe: ${tipo}`);
    return paso;
};

// ENTRENADOR Y DIETAS, FUSIONADAS EN UNA (doc del 23-08, punto 13). Antes eran la pareja
// del punto 42 («¿Has tenido entrenador o has seguido un plan de nutrición antes?» + su
// «¿qué tal te fue?») y, once pantallas después, OTRA VEZ «¿Has hecho dietas antes? ¿Qué
// tal te fue?». El mismo «qué tal te fue» dos veces. Ahora es una sola pregunta y un solo
// relato; las claves se conservan (`entrenador_anterior` + `entrenador_anterior_que_tal`)
// y `dietas_previas` deja de preguntarse en el básico (en el completo solo les sale a los
// que no contestaron ni esta ni aquella: los migrados de Calma).
//
// El «qué tal te fue» solo sale si dice que sí: al que nunca ha tenido no hay nada que
// contarle.
const PREGUNTA_DEL_ENTRENADOR_ANTERIOR = [
    {
        type: 'choice', key: 'entrenador_anterior',
        title: '¿Has tenido entrenador o has hecho dietas antes?',
        options: [
            { value: 'si', label: 'Sí' },
            { value: 'no', label: 'No' },
        ],
    },
    {
        type: 'text', key: 'entrenador_anterior_que_tal', title: '¿Qué tal te fue?',
        desc: 'Cuáles, cuánto duraste, qué pasó con tu peso...',
        cond: a => a.entrenador_anterior === 'si',
        textarea: true, required: true,
    },
];

const EL_BASICO = [
    // 1 · cinco campos en una pantalla. El nombre y el sexo solo se piden si no vienen del
    // pago; la fecha de nacimiento, el teléfono y el email se piden siempre.
    { type: 'contacto', title: 'Antes de empezar', desc: 'Cinco datos y arrancamos.' },
    // 2 · la portada
    porTipo('statement'),
    // 3 y 4 · el objetivo y su confirmación
    q('goal'), q('_confirm'),
    // 5 · cuánto tiempo lleva intentándolo (estaba en el cuestionario largo)
    q('tiempo_intentandolo'),
    // PORTADAS DE BLOQUE (doc del 23-08, regla 4: «una pantalla de título al empezar cada
    // bloque»). Son pantallas sin pregunta: sitúan y se pasan con un botón. En el
    // ?completar=1 no salen (falta() no las reconoce y las deja fuera, que es lo que toca:
    // ahí el recorrido es la lista de huecos, no el alta entero).
    { type: 'titulo', title: 'Tus datos.', desc: 'Tu peso, tu altura, tu grasa y de dónde vienes.' },
    // 6, 7 y 8 · peso, altura y porcentaje de grasa
    q('weight'), q('height'), q('body_fat'),
    // 9, 10 y 11 · su recorrido de peso, cada hito con su año. Antes era UNA pantalla con
    // cuatro casillas sueltas, sin años y solo para quien llevaba entrenador.
    ...PESO_HITOS,
    { type: 'titulo', title: 'Tu día a día.', desc: 'Tu trabajo, cuánto te mueves y cómo entrenas.' },
    // 12 · a qué se dedica y cuánto se mueve, JUNTAS. En pantallas seguidas se le pregunta
    // su trabajo y acto seguido se le pide que se clasifique en lo mismo, y suena a que no
    // se le ha escuchado.
    { type: 'ocupacion', title: '¿A qué te dedicas y cuánto te mueves en tu día a día?' },
    // 13 · la experiencia entrenando
    q('training_experience'),
    // Y SI YA LE HA PAGADO A ALGUIEN (corrección del punto 42, doc del 19-08). Va aquí,
    // pegada a la anterior, porque es justo la que se confunde con ella y no son lo mismo:
    // «una dice cuántos años lleva levantando peso, la otra si ya le ha pagado a alguien y
    // qué tal le fue». En el básico, para todos, con el texto literal de Jesús.
    ...PREGUNTA_DEL_ENTRENADOR_ANTERIOR,
    // Las del deporte: se quedan (decisión del 18-08), pegadas a la de entrenamiento.
    q('deporte_extra'), q('deporte_cual'), q('deporte_en_descanso'),
    // QUÉ DÍAS DE LA SEMANA ENTRENA (tarea 7.1 del 21-08, apartados 12 y 19 del doc de
    // Jesús). CUÁNTOS días ya no se pregunta (son cuatro, bloque 5 del 18-08); CUÁLES sí,
    // porque dependen de su vida y no de la rutina: con ellos y el reparto del PDF la app
    // sabe qué grupo toca cada día, y los planes de autogestión también los necesitan
    // para marcar el entreno o el descanso en Mi semana. Nombres sin tilde a propósito:
    // son los mismos que usa el backend (routes/workout_logs.DIAS_SEMANA).
    {
        type: 'multiselect', key: 'training_weekdays',
        // Los textos del doc del 23-08 (punto 12): «tienes previsto» y la semana «tipo».
        title: '¿Qué días de la semana tienes previsto entrenar?',
        desc: 'Es para confeccionar tu semana «tipo» (después lo podrás cambiar si quieres).',
        options: [
            { value: 'lunes', label: 'Lunes' },
            { value: 'martes', label: 'Martes' },
            { value: 'miercoles', label: 'Miércoles' },
            { value: 'jueves', label: 'Jueves' },
            { value: 'viernes', label: 'Viernes' },
            { value: 'sabado', label: 'Sábado' },
            { value: 'domingo', label: 'Domingo' },
        ],
    },
    { type: 'titulo', title: 'Tu cuerpo.', desc: 'Cómo responde cuando comes de más y de menos.' },
    // 14, 15 y 16 · cómo come, si engorda y si le cuesta definir
    q('apetito'), q('facilidad_engordar'), q('cuesta_definir'),
    // 17 y 18 · los siete biotipos y el suyo (en mujer no salen)
    porTipo('biotype_intro'), q('biotype'),
    { type: 'titulo', title: 'Tu alimentación.', desc: 'Lo que comes hoy y lo que no quieres en el plato.' },
    // 19 · el día tipo, con el lector. Las cuatro de la dieta ya no van con él: se
    // preguntan en el cuestionario largo (punto 26 del doc del 19-08).
    porTipo('dieta'),
    // «¿Has hecho dietas antes?» YA NO VA AQUÍ (doc 23-08, punto 13): se fusionó con la
    // del entrenador de más arriba y su relato cae en `entrenador_anterior_que_tal`.
    // 21 · alergias e intolerancias, y el detalle de las dos que lo llevan
    {
        type: 'multiselect', key: 'alergias',
        title: '¿Tienes alguna alergia o intolerancia alimentaria?',
        desc: 'Se pueden marcar varias.',
        options: [
            { value: 'ninguna', label: 'No, ninguna' },
            { value: 'lactosa', label: 'Lactosa' },
            { value: 'gluten', label: 'Gluten' },
            { value: 'otra', label: 'Otra (dime cuál)' },
        ],
    },
    // Las dos llevan su condición puesta en la propia pregunta: solo salen si ha marcado esa
    // intolerancia.
    q('lactosa'), q('gluten'),
    {
        type: 'text', key: 'alergia_otra', title: '¿Cuál?',
        desc: 'Dime a qué eres alérgico o intolerante.',
        cond: a => (a.alergias || []).includes('otra'),
        required: true,
    },
    // 22 · LO QUE NO QUIERE VER EN EL PLATO (doc del 23-08, punto 14). Sustituye a «¿Qué
    // proteínas comes habitualmente?»: para el menú de arranque lo único imprescindible es
    // no meterle lo que ha dicho que no quiere. Es la única de preferencias que hace falta
    // aquí; las de «me gusta» siguen en su pantalla de Preferencias. La clave de las
    // proteínas se queda en el modelo con lo ya contestado, solo deja de preguntarse.
    {
        type: 'exclusiones',
        title: '¿Existe algún alimento o grupo de alimentos que no te guste y que no quieras introducir en ningún caso?',
        desc: 'Puedes marcar una categoría entera (lácteos, casquería, pescado...) o buscar un alimento concreto por su nombre. Si no hay nada, sigue sin marcar.',
    },
    { type: 'titulo', title: 'Para terminar.', desc: 'Dos preguntas más y calculamos tus macros.' },
    // 23 · cómo le conoció
    {
        type: 'choice', key: 'como_me_conociste', title: '¿Cómo me has conocido?',
        options: [
            { value: 'newsletter', label: 'De tu newsletter, leo habitualmente tus emails.' },
            { value: 'instagram', label: 'Instagram.' },
            { value: 'ex_cliente', label: 'Fui antiguo cliente de tus asesorías.' },
            { value: 'ex_alumno', label: 'Fui antiguo alumno de una formación.' },
            { value: 'recomendacion', label: 'Por recomendación de otros clientes o personas que te conocen.' },
            { value: 'medios', label: 'Por artículos o noticias que he visto publicadas en medios de comunicación.' },
            { value: 'otro', label: 'Otro' },
        ],
    },
    // 24 · y por qué ahora
    q('motivo_apuntarse'),
    // El cierre del básico: revisar y calcular.
    porTipo('final0'), porTipo('result'),
];

// EL COMPLETO NO REPITE NADA DEL BÁSICO (doc del 18-08). Estas seis subieron al básico y
// en el cuestionario largo dejan de preguntarse... pero SOLO a quien ya las tenga
// contestadas: los que entraron antes de esto no pasaron por el básico nuevo, y quitárselas
// del completo sería perder su respuesta para siempre. Por eso se condicionan al dato en vez
// de borrarlas.
//
// Se sustituyen por una copia con la condición puesta, no se muta el objeto: es el mismo que
// usa el básico, y mutarlo le pondría al básico la condición de no preguntar lo que no está
// contestado, que es justo lo contrario.
const YA_ESTAN_EN_EL_BASICO = [
    'birthdate', 'tiempo_intentandolo', 'motivo_apuntarse', 'dietas_previas',
    'lactosa', 'gluten', 'alergias',
    // Los tres hitos de peso, con sus años
    'peso_maximo', 'peso_mejor_momento', 'peso_minimo',
    // Las cinco que se quedaron en el básico porque mueven los macros (decisión del 18-08)
    // Las cuatro de la dieta YA NO están en el básico (punto 26 del doc del 19-08): al
    // cliente nuevo el completo se las pregunta siempre, porque llega sin contestarlas. En
    // esta lista siguen por lo mismo de todas: al que las contestó -- en el básico de
    // agosto o en un ajuste -- no se le repiten.
    'sigue_dieta', 'tiempo_dieta', 'como_va', 'hambre_saturacion',
    'deporte_extra', 'deporte_cual', 'deporte_en_descanso',
];

// «No contestada» NO ES «vacía». Media docena de estas respuestas valen `false` -- el que
// dice que no practica otro deporte, el que come sin control -- y darlas por no contestadas
// se las volvía a preguntar a quien las acababa de responder, que es justo lo que el
// documento no quiere.
const sinContestar = (a, k) => a[k] === undefined || a[k] === null || a[k] === '';

for (let i = 0; i < STEPS_NIVEL1.length; i++) {
    const paso = STEPS_NIVEL1[i];
    if (!YA_ESTAN_EN_EL_BASICO.includes(paso.key)) continue;
    const antes = paso.cond;
    STEPS_NIVEL1[i] = {
        ...paso,
        // La mejor forma pasada con «Si no, pásala» ES una respuesta (doc 23-08): al que
        // la dio, el completo no se la repesca aunque el campo esté vacío.
        cond: (a) => sinContestar(a, paso.key) && (!antes || antes(a))
            && !(paso.key === 'peso_mejor_momento' && a.mejor_forma_pasada),
    };
}

// ═══════════════════════════════════════════════════════════════════════════════
// EL BÁSICO, PARA LOS QUE YA ESTABAN DENTRO
// ═══════════════════════════════════════════════════════════════════════════════
//
// «Todo esto solo lo contesta quien entre a partir de ahora. De los que ya tienes: 91 sin
// objetivo, 158 sin días de entreno, y ninguno con biotipo, zona de grasa, peso máximo,
// mejor forma ni preferencias. Es el hueco más caro que queda, porque son personas que ya
// pagan y es el dato que alimenta el modelo. Lo barato: pasarles el básico dentro de la app
// la próxima vez que entren, con la razón por delante.» (bloque 6 del doc del 18-08)
//
// No se le vuelve a pasar el básico entero: se le pasan SOLO las pantallas cuya respuesta no
// tenemos. A quien ya dio su altura no se le pregunta la altura otra vez, que es la forma más
// rápida de que cierre la pestaña.
const falta = (paso, a) => {
    // «¿Estás seguro?» es la confirmación del objetivo: sin la pregunta del objetivo delante
    // no significa nada, y el que ya está dentro tiene objetivo desde el primer día.
    if (paso.key === '_confirm') return !a.goal;
    // El «pásala» de la mejor forma cuenta como contestada: no se le vuelve a pedir.
    if (paso.key === 'peso_mejor_momento' && a.mejor_forma_pasada) return false;
    if (paso.key) return a[paso.key] === undefined || a[paso.key] === null || a[paso.key] === '';
    // Las pantallas compuestas no tienen clave: se miran los campos que rellenan.
    if (paso.type === 'contacto') return !a.birthdate || !a.phone;
    if (paso.type === 'ocupacion') return !a.profesion || !a.actividad_diaria;
    // Los siete biotipos, solo si le falta el suyo (y en mujer no salen nunca).
    if (paso.type === 'biotype_intro') return a.sex !== 'mujer' && !a.biotype;
    // El día tipo, solo si tampoco sabemos qué dieta sigue: si eso ya está, su día tipo lo
    // dio en su último ajuste y no hace falta pedírselo otra vez.
    if (paso.type === 'dieta') return a.sigue_dieta === undefined || a.sigue_dieta === null;
    return false;      // portadas, revisión y resultado: los pone el recorrido, no el filtro
};

// LO QUE GANA, SEGÚN QUIÉN LE LLEVE LOS MACROS. Al de autogestión se le recalculan al
// terminar; al que los lleva el equipo NO se le tocan -- y está bien que no se le toquen --,
// así que prometerle un recálculo es prometerle lo que no va a pasar. Lo que gana él es que
// su entrenador trabaje con la ficha entera.
const LA_PORTADA_DE_COMPLETAR = (conEquipoDetras) => ({
    type: 'statement',
    title: 'Nos faltan cosas tuyas',
    desc: 'Son las que no llegamos a preguntarte cuando entraste. '
        + (conEquipoDetras
            ? 'Con ellas tu entrenador ajusta tus macros con todo delante, y te montamos los '
              + 'menús con lo que de verdad comes.'
            : 'Con ellas te recalculamos los macros y te montamos los menús con lo que de '
              + 'verdad comes.'),
    cta: 'Vamos',
});

// CUÁNTAS SON, CONTADAS DE LA PROPIA LISTA.
// La portada deja su `desc` vacía a propósito y se rellena aquí: si el número se escribiera a
// mano, se quedaría viejo el día que alguien añada una pregunta, y entonces el aviso mentiría,
// que es peor que no decir nada.
//
// SE CUENTAN SOLO LAS QUE VE TODO EL MUNDO: las que tienen condición o no salen (el detalle de
// la lesión) o solo le salen al que entró antes del básico. Y se cuenta AQUÍ ABAJO, después de
// ponerles la condición, no arriba: contado antes de eso prometía 26 preguntas cuando de
// verdad son 13, y el que se ve 26 por delante cierra la pestaña.
STEPS_NIVEL1[0].desc =
    `Son ${STEPS_NIVEL1.filter(s => !s.cond && !['statement', 'final1', 'fotos_medidas']
        .includes(s.type)).length} preguntas más y con ellas `
    + 'montamos tu estrategia, tu rutina y tus menús.';

// A nivel de módulo para que los inputs conserven el FOCO al teclear: definidos
// dentro del componente de la página se recrean en cada render (tipo nuevo para
// React = desmontar/montar el input) y el cursor se pierde con cada carácter.
const MiniInput = ({ k, label, type = 'text', unit, placeholder, answers, set }) => (
    <div>
        <label className="block text-xs font-bold text-foreground/50 uppercase tracking-wider mb-1.5">{label}</label>
        <div className="flex items-center gap-2">
            <Input type={type} value={answers[k] ?? ''} onChange={e => set(k, e.target.value)}
                placeholder={placeholder || ''} className="bg-card border-[#222222]" />
            {unit && <span className="text-foreground/50">{unit}</span>}
        </div>
    </div>
);

// LO QUE NO QUIERE VER EN EL PLATO (doc 23-08, punto 14). Las mismas 37 categorías y el
// mismo buscador validado contra el catálogo que la pantalla de Preferencias, pero solo
// la mitad de «evitar»: aquí no se le pregunta qué le gusta, solo qué no quiere. Va a
// nivel de módulo por lo mismo que MiniInput (definido dentro, cada render lo remonta y
// el buscador pierde el foco al teclear).
const ExclusionesDelAlta = ({ answers, set, api }) => {
    const [buscando, setBuscando] = useState('');
    const evitadas = answers.avoided_categories || [];
    const palabras = answers.avoided_keywords || [];
    // Las grasas de buena calidad no se pueden vetar: el método las necesita (misma regla
    // que en Preferencias).
    const vetable = (id) => id !== 'grasas_buenas';
    const alternar = (id) => {
        if (!vetable(id)) { toast.info('Las grasas de buena calidad no se pueden evitar: el método las necesita.'); return; }
        set('avoided_categories', evitadas.includes(id) ? evitadas.filter(x => x !== id) : [...evitadas, id]);
    };
    const anadirPalabra = async () => {
        const kw = buscando.trim().toLowerCase();
        if (!kw) return;
        if (palabras.includes(kw)) { toast.error(`«${kw}» ya está en la lista`); return; }
        set('avoided_keywords', [...palabras, kw]);
        setBuscando('');
        try {
            const res = await api.get(`/calculator/search?q=${encodeURIComponent(kw)}&limit=1`);
            if (!(res.data?.alimentos || []).length) {
                toast.warning(`«${kw}» no coincide con ningún alimento del catálogo: guardada, pero hoy no bloquea nada.`);
            }
        } catch (e) { /* la palabra ya está guardada; un error de red no aporta nada aquí */ }
    };
    return (
        <div className="space-y-5">
            <div className="space-y-4 max-h-[46vh] overflow-y-auto pr-1">
                {CAJONES.map(cajon => (
                    <div key={cajon.id}>
                        <p className="text-[11px] uppercase tracking-wider text-foreground/40 font-bold mb-2">{cajon.nombre}</p>
                        <div className="flex flex-wrap gap-2">
                            {cajon.cats.map(id => {
                                const cat = PREFERENCE_CATEGORIES.find(c => c.id === id);
                                if (!cat) return null;
                                const fuera = evitadas.includes(id);
                                return (
                                    <button key={id} type="button" onClick={() => alternar(id)}
                                        title={EJEMPLOS[id] || ''} data-testid={`excluir-${id}`}
                                        className={`px-3 py-1.5 rounded-lg border-2 text-xs font-semibold transition-all ${
                                            fuera ? 'border-red-500/70 bg-red-500/10 text-red-400 line-through'
                                                  : 'border-[#222222] text-foreground/80 hover:border-white/30'}`}>
                                        {cat.label}
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                ))}
            </div>
            <div>
                <p className="text-sm text-foreground/60 mb-2">O un alimento concreto, por su nombre:</p>
                <div className="flex gap-2">
                    <Input value={buscando} onChange={e => setBuscando(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); anadirPalabra(); } }}
                        placeholder="Por ejemplo: atún" data-testid="exclusiones-buscador"
                        className="bg-card border-[#222222]" />
                    <Button type="button" variant="outline" onClick={anadirPalabra}
                        className="border-[#333] text-foreground flex-shrink-0">Añadir</Button>
                </div>
                {palabras.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-3">
                        {palabras.map(kw => (
                            <span key={kw} className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-500/10 border border-red-500/40 text-red-400 text-xs font-semibold">
                                {kw}
                                <button type="button" onClick={() => set('avoided_keywords', palabras.filter(k => k !== kw))}
                                    className="hover:text-red-200" aria-label={`Quitar ${kw}`}>×</button>
                            </span>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

const MiniChoice = ({ k, options, answers, set }) => (
    <div className="flex flex-wrap gap-2">
        {options.map(o => (
            <button key={o.value} onClick={() => set(k, o.value)}
                className={`px-4 py-2 rounded-xl border-2 text-sm font-semibold transition-all ${answers[k] === o.value ? 'border-[#FF671F] bg-[#FF671F]/10 text-brand' : 'border-[#222222] text-foreground hover:border-white/30'}`}>
                {o.label}
            </button>
        ))}
    </div>
);

// Los macros que va teniendo, siempre a la vista, con lo que se mueve cada uno respecto a lo
// anterior. Es la pieza que hace que valga la pena contestar la pregunta siguiente.
const MacrosEnVivo = ({ macros, previos, calculando }) => {
    if (!macros) return null;
    const linea = (etiqueta, ahora, antes) => {
        const delta = (antes != null && ahora != null) ? ahora - antes : 0;
        return (
            <div className="flex items-baseline gap-1.5">
                <span className="text-[10px] uppercase tracking-wider text-foreground/40">{etiqueta}</span>
                {/* Con macro y unidad (punto 29 del 23-08): «TUS MACROS · ENTRENO 140»
                    era un número suelto que no decía de qué hablaba. */}
                <span className="font-heading font-extrabold text-xl text-brand tabular-nums">{ahora}<span className="text-xs font-bold text-brand/70"> g</span></span>
                {delta !== 0 && (
                    <span className={`text-[11px] font-bold ${delta > 0 ? 'text-emerald-500' : 'text-amber-500'}`}>
                        {delta > 0 ? '+' : ''}{delta}
                    </span>
                )}
            </div>
        );
    };
    const hcE = macros.entreno?.hidratos, hcD = macros.descanso?.hidratos;
    return (
        <div className={`flex items-center gap-5 flex-wrap transition-opacity ${calculando ? 'opacity-50' : ''}`}>
            <span className="text-[10px] uppercase tracking-wider text-foreground/30">Tus hidratos</span>
            {linea('Entreno', hcE, previos?.entreno?.hidratos)}
            {linea('Descanso', hcD, previos?.descanso?.hidratos)}
            {/* «Perientreno», el mismo nombre que en el resto de la app (punto 4.18). */}
            {linea('Perientreno', macros.perientreno?.hidratos, previos?.perientreno?.hidratos)}
        </div>
    );
};

// overflow-x-hidden y no overflow-hidden: lo que sobra a los lados son los fondos difuminados
// y hay que recortarlo, pero el eje vertical tiene que poder moverse. Con overflow-hidden, en
// una pantalla baja el final de un paso largo quedaba fuera y sin forma de llegar a él.
const Shell = ({ progress, children, tramo, cabecera }) => (
    <div className="min-h-screen bg-background relative overflow-x-hidden flex flex-col">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-brand/10 rounded-full blur-[150px]" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-brand/5 rounded-full blur-[120px]" />
        {/* Flecha de marca gigante de fondo */}
        <BrandArrow className="absolute -right-16 -bottom-16 w-[420px] h-[420px] text-brand/[0.04] pointer-events-none" />
        {/* Barra de progreso: sin números a propósito (regla 5 del doc del 23-08), que se
            vea avanzar sin decirle cuántas le quedan. */}
        <div className="fixed top-0 left-0 right-0 h-1.5 bg-white/10 z-20">
            <div className="h-full bg-brand transition-all duration-300" style={{ width: `${progress}%` }} />
        </div>
        {/* Cabecera: logo, en qué tramo va y los macros en vivo */}
        <div className="relative z-10 flex items-center justify-between gap-4 min-h-16 px-6 md:px-10 py-2 flex-wrap">
            <div className="flex items-center gap-4">
                {/* Fondo de tema: el logo va del color del texto, no blanco fijo. */}
                <Logo12EN12 size="sm" />
                {tramo && <span className="text-[11px] uppercase tracking-wider text-foreground/40 font-semibold">{tramo}</span>}
            </div>
            {cabecera}
        </div>
        <div className="flex-1 flex items-center justify-center p-6 relative z-10">
            <div className="w-full max-w-2xl">{children}</div>
        </div>
    </div>
);

const QuestionnairePage = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { api, refreshProfile, user, profile, can, token } = useAuth();
    const [idx, setIdx] = useState(0);
    const [answers, setAnswers] = useState({});
    // Espejo de las respuestas siempre al dia, para las comprobaciones que no pueden esperar al
    // siguiente render (ver `visible`).
    const answersRef = useRef({});
    const [loading, setLoading] = useState(false);
    // Resultado del motor v2 tras enviar el Nivel 0 (los 8 números + desglose).
    const [resultado, setResultado] = useState(null);
    // Como se le entrega el resultado: aplicado solo, o propuesta que revisa su coach (seccion 6).
    const [entrega, setEntrega] = useState(null);
    // El Nivel 0 se completó EN ESTA SESIÓN: seguimos en el flujo aunque el
    // perfil ya diga questionnaire_completed (para ver resultados y el Nivel 1).
    const [nivel0Enviado, setNivel0Enviado] = useState(false);
    // El día de hoy montado y guardado en cuanto salen sus macros: termina el alta y ya tiene
    // comida puesta, en vez de unos números y una pantalla vacía por delante.
    const [diaMontado, setDiaMontado] = useState(null);
    // Los menús de arranque (doc 23-08, punto 18): mañana y pasado, escritos de verdad.
    // null = cargando; [] = no se pudieron montar.
    const [diasArranque, setDiasArranque] = useState(null);
    // «Próximos pasos» (doc 23-08, punto 26): el cierre del camino con entrenador. Guarda
    // a dónde ir tras el «Entendido»; mientras tiene valor, esa pantalla manda sobre todo.
    const [pasosFinales, setPasosFinales] = useState(null);
    // Macros recalculados a cada respuesta, para verlos moverse. No se aplican: son un avance.
    const [vistaPrevia, setVistaPrevia] = useState(null);
    const [calculandoVivo, setCalculandoVivo] = useState(false);
    const progresoCargadoRef = useRef(false);
    // EL «ATRÁS» QUE FUNCIONABA UNA VEZ Y DEJABA DE FUNCIONAR (punto 4.12 del 09-08).
    //
    // Al elegir una opción se programa el avance con `setTimeout(goNext, 550)` -- esos 550 ms
    // son a propósito: dan tiempo a ver moverse los macros de la cabecera. Si dentro de ese
    // medio segundo largo el cliente pulsa Atrás, se retrocede y acto seguido el temporizador,
    // que seguía vivo, avanza otra vez. Desde fuera es exactamente lo que describe el punto:
    // el botón deja de responder, y de forma intermitente, según lo rápido que vayas.
    //
    // Retroceder cancela el avance pendiente: el último gesto del cliente manda sobre
    // cualquier cosa que estuviera programada.
    const avancePendienteRef = useRef(null);
    // «Toca encima» del repaso (doc 23-08, punto 16): guarda a qué pantalla volver después
    // de corregir una respuesta desde «Confirma tus respuestas». null = recorrido normal.
    const volverAlRepasoRef = useRef(null);
    // Los macros de antes de la ultima respuesta, para poder mostrar cuanto se ha movido cada uno.
    const previosRef = useRef(null);
    // Punto de partida: fotos subidas y la ficha que se le entrega a cambio.
    const [ficha, setFicha] = useState(null);
    // P10: lo que hemos entendido de su dieta, pendiente de que lo confirme.
    const [lecturaDieta, setLecturaDieta] = useState(null);
    const [leyendoDieta, setLeyendoDieta] = useState(false);
    // LA VENTANA DEL CUESTIONARIO LARGO (el reloj del 19-08): abre el viernes a las 10:00
    // y cierra el lunes a las 18:00, hora de España. La pregunta el que lleva entrenador y
    // tiene el largo pendiente; al resto ni se consulta. null = sin contestar todavía (no
    // se corta a nadie por una petición que aún no volvió).
    const [ventanaLargo, setVentanaLargo] = useState(null);
    // Las medidas del encadenado del final del alta (doc 19-08, apartado 06).
    const [medidasAlta, setMedidasAlta] = useState({});

    // Nivel 1 solo para planes con coach (calculadora == 'personalizado')...
    const conEntrenador = can(CAP.MACROS_PERSONALIZADOS);
    // ...Y PARA QUIEN COMPRA EL AJUSTE A MEDIDA. Es la última línea de la regla que ordena
    // el documento del cuestionario: «el que compra el ajuste de 87 € hace el completo,
    // exactamente igual que un Gold». Su plan no cambia -- sigue siendo el suyo -- pero el
    // cuestionario largo se le abre igual, porque es lo que ha pagado.
    //
    // Se mira `cobrado`, no `quiere`: querer no es haber pagado. Hoy nadie lo tiene a true
    // porque todavía no hay cobro montado (ver POST /clients/ajuste-a-medida), así que esto
    // no se lo abre a nadie por su cuenta; queda puesto para el día que se cobre.
    const tieneCoach = conEntrenador || !!profile?.ajuste_a_medida?.cobrado;

    // La ventana del largo se pregunta al servidor -- la regla vive allí -- y solo cuando
    // aplica: con entrenador (o los 87 € pagados) y el perfil largo sin terminar.
    useEffect(() => {
        if (!profile || !tieneCoach || profile?.questionnaire_nivel1_completed) return;
        api.get('/clients/questionnaire/nivel1/ventana')
            .then(r => setVentanaLargo(r.data))
            .catch(() => setVentanaLargo(null));   // sin respuesta no se corta a nadie
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [profile?.id, tieneCoach]);

    // CUÁNDO EMPIEZA. Todo el mundo arranca en lunes, pague el día que pague, y ese lunes se
    // calcula y se guarda al cobrar (`current_period_start`, el que ancla su ciclo). Lo que
    // faltaba era decírselo. Y solo eso: el día de sus macros definitivos NO se le dice
    // (punto 46 del doc del 19-08), porque los recibe el miércoles anterior a su lunes y
    // cualquier fecha que le demos aquí le sonaría a que empieza antes de tenerlos.
    const arranque = useMemo(() => {
        const inicio = profile?.current_period_start;
        // SI NO TIENE CICLO GUARDADO, SE CALCULA IGUAL. Ese campo lo escribe el cobro por
        // Stripe, así que el que entró de otra forma -- los de Calma, las altas a mano -- se
        // quedaba con el «empiezas siempre un lunes» sin fecha, que es lo que el documento
        // manda quitar. La regla es la misma que aplica el servidor: el lunes que viene, y si
        // faltan menos de 48 horas, el siguiente.
        const lunes = inicio ? new Date(inicio) : (() => {
            const hoy = new Date();
            const d = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());
            d.setDate(d.getDate() + ((8 - d.getDay()) % 7 || 7));   // el próximo lunes
            if ((d - hoy) < 48 * 3600 * 1000) d.setDate(d.getDate() + 7);
            return d;
        })();
        if (isNaN(lunes)) return null;
        const comoSeDice = (d) => d.toLocaleDateString('es-ES', { day: 'numeric', month: 'long' });
        return { lunes: comoSeDice(lunes) };
    }, [profile?.current_period_start]);
    // Si ha pulsado "Ajustar macros" manda eso y nada más: sin esta comprobación, un cliente con
    // coach que le diera al botón acababa en el perfil largo en vez de en el cuestionario.
    const pidioAjustar = new URLSearchParams(location.search).get('ajustar') === '1';
    // Modo revisión (solo equipo): `?ver=alta`, `?ver=ajuste` o `?ver=perfil` abren el tramo
    // que se pida aunque el cuestionario ya esté hecho. Sin esto no hay forma de mirar el
    // alta una vez pasada, y es justo la que más textos tiene.
    const revision = verComo(user);
    // Retomar: Nivel 0 hecho en otra sesión pero Nivel 1 pendiente.
    const retomandoNivel1 = revision
        ? revision === 'perfil'
        : (!pidioAjustar && !!profile?.questionnaire_completed && !nivel0Enviado
           && tieneCoach && !profile?.questionnaire_nivel1_completed);

    // Dos modos, como pide el doc del 29-07:
    //   ALTA   -> cuatro preguntas y macros provisionales. Es lo que ve quien acaba de entrar.
    //   AJUSTE -> el cuestionario que ajusta, detras del boton "Ajustar macros". Se llega con
    //             ?ajustar=1, o solo con el alta ya hecha (por si vuelve por el enlace).
    const modoAjuste = revision
        ? revision === 'ajuste'
        : (pidioAjustar
           || (!!profile?.questionnaire_completed && !nivel0Enviado && !retomandoNivel1));

    // Un solo recorrido (punto 15 del doc del 07-08). Quien se da de alta contesta los datos
    // de la tabla y sigue de largo con lo que ajusta los hidratos, sin cortes y sin un segundo
    // cuestionario: por eso el alta es el mismo flujo que el ajuste con las cuatro preguntas
    // de partida delante. Quien vuelve más adelante por el botón "Ajustar macros" ya tiene
    // esos cuatro datos en su ficha, así que entra directo por el tramo de ajuste.
    // EL FINAL SE PARTE POR PLAN, no por momento (doc del cuestionario, 18-08: «la regla que
    // ordena todo»). Hasta aquí llegan todos igual, con sus macros y su primer día montado.
    // A partir de aquí: quien lleva entrenador elige entre empezar ya o terminar su perfil;
    // quien no lo lleva sube fotos y medidas y recibe la oferta del ajuste a medida.
    // El cierre, que es igual para los dos recorridos: los macros, la ficha, el primer día
    // de comidas y, a partir de ahí, lo que cambia por plan.
    const elCierre = [
        ...STEPS_ONBOARD,
        ...(tieneCoach
            ? [{ type: 'elegir_perfil', title: 'Ya puedes empezar' }, ...STEPS_NIVEL1]
            // EL FINAL DEL QUE NO LLEVA ENTRENADOR, ENCADENADO (doc 19-08, apartado 06):
            // «Tres cosas y terminamos» → fotos → medidas → preferencias → «Ya está
            // todo», y detrás la oferta de los 87 €. Se guarda al pasar de pantalla, no
            // al final: las fotos suben al elegirlas y las medidas al continuar. «Lo hago
            // luego» salta directo a la oferta y deja el aviso pendiente.
            : [{ type: 'tres_cosas', title: 'Tres cosas y terminamos' },
               { type: 'fotos_alta', title: 'Tus fotos' },
               { type: 'medidas_alta', title: 'Tus medidas' },
               { type: 'prefs' },
               { type: 'ya_esta_todo', title: 'Ya está todo' },
               { type: 'oferta_ajuste', title: 'Una cosa más' }]),
    ];
    // LO QUE LE FALTA DE LA BASE, PREGUNTADO ANTES DE AJUSTAR NADA.
    //
    // El ajuste lee del perfil los cuatro datos de la tabla (peso, sexo, grasa y objetivo) y
    // no los pregunta, porque se dan en el alta. Pero hay 124 clientes activos a los que les
    // falta alguno -- 104 sin objetivo, 63 sin grasa, 8 sin peso, casi todos de la migración
    // de Calma -- y esos contestaban el cuestionario entero para estrellarse en el botón de
    // calcular con «Faltan tus datos de partida. Completa el alta primero». El alta no se
    // puede repetir (contesta 409), así que era un callejón sin salida: no había forma de
    // arreglarlo desde la app.
    //
    // Ahora, si falta alguno, se le pregunta AQUÍ, delante de todo, y se guarda con la misma
    // puerta que usa «nos faltan cosas tuyas»: rellena huecos y no pisa nada.
    // SE MIRA UNA VEZ Y NO SE VUELVE A MIRAR. Lo que le falta decide qué pantallas tiene su
    // recorrido, y al terminar se guarda y se refresca su ficha: si esto se recalculara ahí,
    // el recorrido cambiaría DEBAJO del cliente en el último clic y le devolvía a la primera
    // pantalla en vez de enseñarle sus macros.
    const loQueLeFaltabaRef = useRef(null);
    if (profile && !loQueLeFaltabaRef.current) {
        loQueLeFaltabaRef.current = ['goal', 'weight', 'body_fat'].filter(
            k => profile[k] === undefined || profile[k] === null || profile[k] === '');
    }
    const faltaLaBase = loQueLeFaltabaRef.current || [];
    const laBaseQueFalta = useMemo(() => {
        if (!faltaLaBase.length) return [];
        const pantallas = [];
        if (faltaLaBase.includes('goal')) pantallas.push(q('goal'), q('_confirm'));
        if (faltaLaBase.includes('weight')) pantallas.push(q('weight'));
        if (faltaLaBase.includes('body_fat')) pantallas.push(porTipo('bf'));
        return pantallas;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [faltaLaBase.join(',')]);

    const preguntasDeAjuste = [...laBaseQueFalta, ...STEPS_AJUSTE, ...elCierre];

    // EL BÁSICO PARA EL QUE YA ESTABA (?completar=1). Solo lo que falte, con la portada que
    // dice por qué se le pregunta y terminando en sus macros nuevos, que es lo que gana.
    // Se calcula una vez con las respuestas ya sembradas del perfil: si se recalculara en
    // cada tecla, la pantalla en la que está escribiendo desaparecería al contestarla.
    const pidioCompletar = new URLSearchParams(location.search).get('completar') === '1';

    // LAS PANTALLAS DEL BÁSICO QUE ESTE CLIENTE NO HA CONTESTADO NUNCA. Se calcula una vez,
    // con las respuestas ya sembradas del perfil: si se recalculara en cada tecla, la
    // pantalla en la que está escribiendo desaparecería al contestarla.
    // Igual que arriba: se decide una vez, con la ficha tal y como estaba al entrar.
    const delBasicoRef = useRef(null);
    const loQueFaltaDelBasico = useMemo(() => {
        if (!profile) return [];
        if (delBasicoRef.current) return delBasicoRef.current;
        // CON LA FICHA, NO CON EL ESPEJO DE RESPUESTAS (23-08). Los efectos que siembran
        // `answersRef` desde el perfil corren DESPUÉS de este cálculo, así que aquí el
        // espejo llegaba vacío y TODO parecía sin contestar: al que volvía a por el
        // completo (el de los 87 €, un Gold que lo dejó a medias) se le volvía a abrir el
        // básico entero por «Antes de empezar». Lo tapaba el borrador del alta, que
        // saltaba por encima con su número de paso... aterrizándole a mitad del completo.
        // Se mira lo mismo que siembra el efecto: el perfil plano y sus ajustes de macros.
        const a = { ...(profile.ajustes_macros || {}), ...profile,
                    phone: profile.phone ?? user?.phone };
        // Sin las de la base: esas van por su cuenta, delante de todo, y preguntarle el
        // objetivo dos veces seguidas es lo que hace que cierre la pestaña.
        const yaVanDelante = new Set(laBaseQueFalta.map(p => p.key).filter(Boolean));
        delBasicoRef.current = EL_BASICO.filter(p => falta(p, a) && !yaVanDelante.has(p.key));
        return delBasicoRef.current;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [profile, laBaseQueFalta]);

    const elBasicoQueFalta = useMemo(() => {
        if (!pidioCompletar || !profile) return null;
        if (!laBaseQueFalta.length && !loQueFaltaDelBasico.length) return [];
        // CON LAS DE LA BASE DELANTE. `loQueFaltaDelBasico` las deja fuera a propósito -- para
        // no preguntar el objetivo dos veces cuando van por su cuenta -- y aquí no iba nadie a
        // ponerlas: al cliente de Calma sin objetivo no se le preguntaba, y al calcular se
        // estrellaba con «Revisa tu objetivo: no hemos podido guardarlo así», que es el
        // servidor diciendo que le llegó vacío.
        return [LA_PORTADA_DE_COMPLETAR(conEntrenador), ...laBaseQueFalta, ...loQueFaltaDelBasico,
                porTipo('final0'), porTipo('result')];
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [pidioCompletar, profile, laBaseQueFalta, loQueFaltaDelBasico, conEntrenador]);

    // Y EL COMPLETO EMPIEZA POR AHÍ CUANDO HACE FALTA (18-08).
    //
    // El cuestionario largo da por hecho que el básico está contestado: son las 21 pantallas
    // que NO se repiten. Pero el cliente que viene de Calma nunca pasó por el básico -- de
    // los 140 con acceso vivo, a la mayoría le faltan las cinco cosas -- y a ese la app le
    // metía directo en el largo. Salía de él con su ficha igual de coja: sin objetivo, sin
    // biotipo, sin sus pesos y sin saber qué come. Y sin macros nuevos, porque el largo no
    // los toca.
    //
    // Así que delante van lo que le falte de la base y lo que le falte del básico. Al que
    // hizo el alta aquí no le cambia nada: no le falta ninguna y esto queda en cero.
    const flow = elBasicoQueFalta?.length
        ? elBasicoQueFalta
        : retomandoNivel1
            ? [...laBaseQueFalta, ...loQueFaltaDelBasico, ...STEPS_NIVEL1]
            : modoAjuste
                ? preguntasDeAjuste
                : [...EL_BASICO, ...elCierre];

    // PreferencesSetup espera el helper estilo fetch (endpoint, {method, body}).
    const fetchApi = useCallback(async (endpoint, options = {}) => {
        const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
                ...options.headers,
            },
        });
        if (!res.ok) {
            const error = await res.json().catch(() => ({ detail: 'Error de red' }));
            throw new Error(error.detail || 'Error');
        }
        return res.json();
    }, [token]);

    // Al llegar a "Tus alimentos": persistir la config elegida (comidas, momento
    // del entreno, días) para que el banco y Nutrición ya la usen.
    const prefsPersistedRef = useRef(false);
    useEffect(() => {
        const s = flow[idx];
        if (!s || prefsPersistedRef.current || (s.type !== 'prefs' && s.type !== 'magia')) return;
        prefsPersistedRef.current = true;
        const cfg = {};
        if (answers.pref_num_comidas != null) cfg.num_comidas = answers.pref_num_comidas;
        if (answers.pref_momento != null) cfg.momento_entreno = answers.pref_momento;
        if (Object.keys(cfg).length) api.patch('/user/diet-config', cfg).catch(() => {});
        // Los días de entreno ya no se preguntan aquí (bloque 5 del doc del 18-08: son cuatro
        // siempre y la ficha nace con cuatro), así que no hay nada que persistir.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [idx]);

    // La ficha se pide al llegar a su pantalla, no antes: hasta ese momento el cliente puede
    // haber cambiado su altura o sus medidas, y la ficha saldria con datos viejos.
    // Y ANTES DE PEDIRLE FOTOS Y MEDIDAS, TAMBIÉN: de ahí sale cuántas fotos tiene subidas,
    // que es lo que decide si esa pantalla le sobra o le falta media.
    useEffect(() => {
        if (!['ficha', 'fotos_medidas'].includes(flow[idx]?.type) || ficha) return;
        api.get('/clients/mi-ficha')
            .then(r => setFicha(r.data))
            .catch(() => setFicha({ composicion: null, referencia: null }));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [idx]);

    // LOS DOS MENÚS DE ARRANQUE (doc del 23-08, punto 18). Antes eran tres recetas
    // sueltas cuadradas a su C1; ahora son los días de MAÑANA y PASADO enteros, escritos
    // de verdad (`montar-dia` con fecha y guardar): «para que los tengas de referencia».
    // El de hoy ya lo escribe el envío del cuestionario, como siempre. El tipo de día
    // sale de sus días de entreno; sin ellos, entrenamiento, que es el conservador.
    useEffect(() => {
        const s = flow[idx];
        if (s?.type !== 'magia' || diasArranque !== null) return;
        const DIAS_JS = ['domingo', 'lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado'];
        const fechaEn = (mas) => { const d = new Date(); d.setDate(d.getDate() + mas); return d; };
        const iso = (mas) => fechaEn(mas).toLocaleDateString('en-CA');
        const tipoDe = (mas) => {
            const dias = answersRef.current.training_weekdays;
            if (!Array.isArray(dias) || !dias.length) return 'entrenamiento';
            return dias.includes(DIAS_JS[fechaEn(mas).getDay()]) ? 'entrenamiento' : 'descanso';
        };
        (async () => {
            try {
                const montados = await Promise.all([1, 2].map(mas =>
                    api.post('/calculator/montar-dia', {
                        fecha: iso(mas), guardar: true, tipo_dia: tipoDe(mas),
                        num_comidas: answers.pref_num_comidas || 4,
                        momento_entreno: answers.pref_momento ?? 1,
                    }).then(r => ({ ...r.data, tipo_dia: tipoDe(mas) })).catch(() => null)));
                setDiasArranque(montados.filter(Boolean));
            } catch {
                setDiasArranque([]);
            }
        })();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [idx]);

    // Al pasar del alta al cuestionario de ajuste, el flujo es OTRA lista: hay que volver al
    // primer paso. Sin esto, el numero de paso que traia del alta apuntaba a una pregunta
    // cualquiera de la lista nueva y el cuestionario arrancaba por la mitad.
    //
    // Se compara contra el modo anterior en un ref (y no con la lista de dependencias) porque
    // este componente ya reinicia `idx` por otras vias y un setState suelto en un efecto se
    // encadenaba con ellas.
    // SE MIRA EL RECORRIDO, NO EL MODO (19-08). Estaba atado a `modoAjuste`, y ese cambia
    // solo al ENVIAR -- en cuanto se marca que el cuestionario ya está mandado --, aunque las
    // pantallas sean exactamente las mismas. Resultado en la pasada de «nos faltan cosas
    // tuyas»: el cliente contestaba las quince, pulsaba «Calcular mis macros», sus respuestas
    // se guardaban... y la pantalla volvía a la primera pregunta en vez de enseñarle sus
    // macros. Comparando la lista de pasos, el reinicio solo ocurre cuando de verdad es otro
    // cuestionario.
    const recorridoAnteriorRef = useRef(null);
    useEffect(() => {
        const firma = flow.map(s => s.key || s.type).join('|');
        if (recorridoAnteriorRef.current === null) { recorridoAnteriorRef.current = firma; return; }
        if (recorridoAnteriorRef.current !== firma) {
            recorridoAnteriorRef.current = firma;
            setIdx(0);
        }
    });

    // Y si se sale de la pantalla con un avance programado, que no quede vivo (punto 4.12).
    useEffect(() => () => {
        if (avancePendienteRef.current) clearTimeout(avancePendienteRef.current);
    }, []);

    // Retomar el cuestionario de ajuste donde lo dejó, y arrancar la cabecera con los macros
    // que tiene ahora mismo (los provisionales del alta) para que se vea de dónde parte.
    useEffect(() => {
        // En modo revisión NO se retoma nada: se viene a ver el cuestionario desde el
        // principio, y reanudarlo por la mitad deja fuera justo las pantallas que se quieren
        // repasar. Las respuestas guardadas siguen intactas: aquí solo no se cargan.
        if (revision) return;
        if (progresoCargadoRef.current || !profile) return;
        progresoCargadoRef.current = true;
        const guardado = profile.ajuste_macros_progreso;
        // CADA RECORRIDO RETOMA EL SUYO (doc del cuestionario, 18-08). El alta y el ajuste
        // guardan en el mismo sitio, y el número de pantalla de uno no significa nada en el
        // otro: sin esta comprobación, quien dejó el ajuste por la séptima aterrizaría en la
        // séptima del alta, que es otra pregunta. Lo guardado sin `flujo` es de antes de
        // esto y solo puede ser del ajuste, que era el único que se guardaba.
        //
        // Y EL DE RETOMAR EL COMPLETO NO RETOMA NINGUNO (23-08): su lista es otra (los
        // huecos + el nivel 1) y el paso del borrador del alta apuntaba a mitad del
        // completo. El que compró los 87 € volvía al cuestionario y aterrizaba en «¿Qué
        // suplementos tomas ahora?» sin haber visto ni la portada.
        const flujoDeAhora = retomandoNivel1 ? 'nivel1' : (modoAjuste ? 'ajuste' : 'alta');
        const suyo = (guardado?.flujo || 'ajuste') === flujoDeAhora;
        if (suyo && guardado?.respuestas && Object.keys(guardado.respuestas).length) {
            answersRef.current = { ...answersRef.current, ...guardado.respuestas };
            setAnswers(a => ({ ...a, ...guardado.respuestas }));
            // AL REANUDAR, SALTARSE LAS QUE YA NO APLICAN (punto 4.12 del 09-08).
            //
            // Aquí se hacía `setIdx(paso)` a secas, y el paso guardado puede ser una pregunta
            // cuya condición ya no se cumple. Jesús aterrizaba en «¿Habría posibilidad de que
            // lo hicieras en días en que no vayas al gimnasio?» -- que solo sale si practica
            // otro deporte -- teniendo contestado que NO. Doblemente mal: la pregunta no le
            // tocaba, y ese «lo» se refiere a una pregunta que no está en pantalla.
            //
            // Se avanza hasta la primera que sí aplique con las respuestas ya restauradas,
            // que es exactamente lo que hace `goNext` durante el recorrido normal.
            const paso = Number(guardado.paso) || 0;
            if (paso > 0 && paso < flow.length) {
                let j = paso;
                while (j < flow.length - 1 && !visible(flow[j])) j++;
                setIdx(Math.min(j, flow.length - 1));
            }
            recalcularEnVivo(guardado.respuestas);
            toast.info('Seguimos donde lo dejaste');
        } else {
            recalcularEnVivo({});
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [modoAjuste, profile]);

    // Nombre y email ya los tenemos del login: autocompletar (el email no es editable).
    useEffect(() => {
        if (!user) return;
        setAnswers(a => ({
            ...a,
            name: a.name ?? user.name ?? '',
            email: user.email ?? a.email ?? '',
            // El teléfono vive en la cuenta, no en la ficha: sin sembrarlo, al que ya lo dio
            // se le volvía a pedir al completar su ficha.
            phone: a.phone ?? user.phone ?? '',
        }));
        if (user.phone) answersRef.current = { ...answersRef.current, phone: user.phone };
    }, [user]);

    // El sexo y el objetivo se contestaron en el ALTA y viven en el perfil, no en las
    // respuestas de este cuestionario. Se siembran aquí porque hay preguntas que dependen
    // de ellos: las opciones cambian según el objetivo, y la pantalla del biotipo no se
    // le enseña a una mujer (las siete fotos son de hombre). Sin esto, en el cuestionario
    // de ajuste `answers.sex` venía vacío y la condición no se cumplía nunca.
    useEffect(() => {
        if (!profile) return;
        // También en la ref: quien decide qué pantallas se saltan (`visible`) lee de
        // answersRef, no del estado, así que sembrar solo el estado no cambiaba nada.
        // Y LO QUE YA CONTESTÓ DEL BÁSICO, por lo mismo: el cuestionario largo no repite lo
        // que ya está en su ficha, y para saberlo tiene que verlo aquí. Al que entró antes
        // del básico nuevo esto le llega vacío y sus preguntas siguen saliendo, que es lo
        // que se quiere.
        const delBasico = {};
        for (const clave of ['tiempo_intentandolo', 'motivo_apuntarse', 'dietas_previas',
                             'lactosa', 'gluten', 'alergias', 'peso_maximo', 'peso_minimo',
                             'peso_mejor_momento', 'mejor_forma_pasada', 'profesion', 'como_me_conociste',
                             'proteinas_habituales', 'birthdate', 'height', 'biotype',
                             'training_experience',
                             'entrenador_anterior', 'entrenador_anterior_que_tal',
                             // Y los números que ya tiene, para que al completar su ficha no
                             // se le vuelva a preguntar el peso y la grasa que ya constan.
                             'weight', 'body_fat', 'profesion']) {
            const v = profile[clave];
            if (v !== null && v !== undefined && v !== '') delBasico[clave] = v;
        }
        // Los días de entreno (7.1 del 21-08), solo si están guardados COMO NOMBRES: las
        // fichas heredadas de Calma traen enteros sin semántica verificable, y sembrarlos
        // daría la pregunta por contestada con un dato que no sirve para colocar grupos.
        if (Array.isArray(profile.training_weekdays)
            && profile.training_weekdays.some(d => typeof d === 'string')) {
            delBasico.training_weekdays = profile.training_weekdays.filter(d => typeof d === 'string');
        }
        // Y LAS CINCO QUE MUEVEN LOS MACROS, que no viven sueltas en el perfil sino dentro de
        // `ajustes_macros`. Sin esto el completo se las volvía a preguntar a todo el mundo,
        // porque aquí no las veía: son las mismas preguntas, guardadas en otro cajón.
        for (const clave of ['sigue_dieta', 'tiempo_dieta', 'como_va', 'hambre_saturacion',
                             'deporte_extra', 'deporte_cual', 'deporte_en_descanso',
                             'actividad_diaria', 'apetito', 'facilidad_engordar',
                             'cuesta_definir']) {
            const v = (profile.ajustes_macros || {})[clave];
            if (v !== null && v !== undefined && v !== '') delBasico[clave] = v;
        }
        answersRef.current = {
            ...delBasico,
            ...answersRef.current,
            sex: answersRef.current.sex ?? profile.sex ?? undefined,
            goal: answersRef.current.goal ?? profile.goal ?? undefined,
        };
        setAnswers(a => ({
            ...delBasico,
            ...a,
            sex: a.sex ?? profile.sex ?? undefined,
            goal: a.goal ?? profile.goal ?? undefined,
        }));
    }, [profile]);

    // ── Macros en vivo (doc 29-07) ────────────────────────────────────────────
    // Tras cada respuesta se recalcula y el cliente ve moverse los numeros. Si contesta y no
    // pasa nada visible, no contesta la siguiente. Se calcula sin aplicar nada: lo definitivo
    // se guarda al terminar el cuestionario.
    const recalcularEnVivo = useCallback(async (respuestas) => {
        // Con lo que haya contestado EN EL PROPIO CUESTIONARIO por delante de la ficha:
        // al retomar un borrador, el peso y el % graso que acaba de escribir todavía no
        // están en el perfil, y la barra no llegaba a montarse nunca (hallazgo del P29,
        // recorrido del 23-08). Sin peso u objetivo no hay cálculo posible y se calla.
        const r = respuestas || {};
        const peso = r.weight ?? profile?.weight;
        const objetivo = r.goal ?? profile?.goal;
        const grasa = r.body_fat ?? profile?.body_fat;
        if (!modoAjuste || !peso || !objetivo) return;
        setCalculandoVivo(true);
        try {
            const res = await api.post('/calculator/targets', {
                peso,
                sexo: r.sex || profile?.sex || 'hombre',
                porcentaje_graso: grasa,
                objetivo,
                ajustes: ajustesDe(respuestas),
            });
            // El valor anterior se guarda desde dentro del setState: asi es el real y no uno
            // capturado en un closure viejo.
            setVistaPrevia(anterior => {
                previosRef.current = anterior?.macros || null;
                return res.data || null;
            });
        } catch (e) {
            /* el recalculo es un extra: si falla, se sigue contestando */
        } finally {
            setCalculandoVivo(false);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [api, modoAjuste, profile]);

    // SI EL PASO EN EL QUE ESTÁ DEJA DE TENER SENTIDO, SE PASA SOLO.
    //
    // Qué pantallas se saltan se mira AL AVANZAR, así que una que se vuelve innecesaria con
    // el cliente ya dentro se queda pintada. Pasa con las fotos y las medidas: cuántas fotos
    // tiene se pide al llegar, y hasta que llega la respuesta la pantalla ya está en la
    // pantalla, así que a quien las tenía todas se le seguía pidiendo lo que ya había dado.
    //
    // VA AQUÍ ARRIBA, con los demás hooks, y no junto a `visible`: más abajo hay un `return`
    // (el «ya completaste el cuestionario»), y un hook detrás de un return se llama unas
    // veces sí y otras no. React no lo permite y el proyecto entero deja de compilar.
    useEffect(() => {
        if (!flow.length || idx >= flow.length - 1) return;
        const s = flow[idx];
        const sobra = (s.type === 'fotos_medidas'
                       && !!(profile?.punto_de_partida_hecho || profile?.medidas_inicio)
                       && (ficha?.fotos_subidas || 0) > 0)
                   || (s.cond && !s.cond(answersRef.current));
        if (sobra) setIdx(i => Math.min(i + 1, flow.length - 1));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [idx, ficha, profile]);

    // El progreso se guarda a cada respuesta: si se sale y vuelve, sigue donde lo dejo.
    //
    // TAMBIÉN EN EL ALTA desde el 18-08. Antes esto se cortaba en seco si no era el
    // cuestionario de ajuste, así que el alta -- que es el recorrido largo, y el único que
    // se hace una sola vez en la vida -- era justo el que no se guardaba. Va con el nombre
    // del recorrido para que cada uno retome el suyo.
    const guardarProgreso = useCallback((respuestas, paso) => {
        if (revision) return;   // en modo revisión no se escribe nada
        // Con el alta ya enviada, el borrador sobra: el recorrido que queda (el cierre)
        // no se reanuda, y seguir escribiéndolo dejaba un paso enorme que luego
        // descolocaba al que volvía a por el completo.
        if (nivel0Enviado) return;
        // Las fotos NO viajan en el borrador: son base64 de megas y esto se guarda a cada
        // avance. Van una sola vez, en el envío final. Quien salga a mitad pierde solo la
        // foto (se le vuelve a pedir), no las respuestas.
        const { foto_grasa, foto_mejor_momento, dieta_imagen, ...ligeras } = respuestas;
        api.put('/clients/ajuste-progreso',
                { respuestas: ligeras, paso, flujo: modoAjuste ? 'ajuste' : 'alta' }).catch(() => {});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [api, modoAjuste, revision, nivel0Enviado]);

    // ── P10: leer la dieta que trae el cliente ────────────────────────────────
    // (La puerta «Un día mío» se quitó el 23-08: en el alta nadie tiene días creados,
    // así que `mis-dias` ya no se consulta desde aquí.)

    // «PRÓXIMOS PASOS» (doc del 23-08, punto 26): la última pantalla del camino con
    // entrenador, después de enviar el cuestionario completo. Va aquí arriba y manda
    // sobre el recorrido: el largo ya está enviado y no hay paso al que volver.
    if (pasosFinales) {
        return (
            <Shell progress={100}>
                <div data-testid="proximos-pasos">
                    <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-6 leading-tight">
                        Próximos pasos
                    </h2>
                    <div className="space-y-4 mb-6">
                        {[['Hoy', 'Ya puedes usar la app (estos días no cuentan, van de regalo).'],
                          ['Antes del viernes', 'Recibirás tu primer programa: macros definitivos, plan de suplementación y primera rutina.'],
                          ['Lunes', 'Comienzo oficial.']]
                            .map(([cuando, que]) => (
                                <div key={cuando} className="flex items-start gap-4">
                                    <span className="w-36 flex-shrink-0 text-sm font-bold text-brand uppercase tracking-wide mt-0.5">{cuando}</span>
                                    <p className="text-sm text-foreground/80">{que}</p>
                                </div>
                            ))}
                    </div>
                    <p className="text-sm text-foreground/60 mb-8">
                        Ahora danos unos días para poder revisar tus respuestas y preparar tu
                        plan. Cualquier duda, tienes el chat.
                    </p>
                    <Button data-testid="proximos-pasos-entendido" disabled={loading}
                        onClick={async () => {
                            setLoading(true);
                            try { await refreshProfile(); } catch (e) { /* la app refresca sola al entrar */ }
                            navigate(pasosFinales);
                        }}
                        className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                        Entendido <ArrowRight className="w-5 h-5 ml-2" />
                    </Button>
                </div>
            </Shell>
        );
    }

    // El ALTA no se puede repetir (ni por el enlace). El cuestionario de AJUSTE sí: si cambia de
    // trabajo o empieza a hacer otro deporte, lo vuelve a pasar y sus macros se recalculan.
    // Y tampoco corta al que viene a COMPLETAR lo que le falta (?completar=1): ese no está
    // repitiendo el alta, está contestando por primera vez lo que no llegamos a preguntarle.
    if (!revision && profile?.questionnaire_completed && !nivel0Enviado && !retomandoNivel1
            && !pidioAjustar && !elBasicoQueFalta?.length) {
        return (
            <Shell progress={100}>
                <div className="text-center">
                    <div className="w-16 h-16 rounded-full bg-brand/10 flex items-center justify-center mx-auto mb-6">
                        <Check className="w-8 h-8 text-brand" />
                    </div>
                    <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-2 leading-tight">
                        Ya completaste el cuestionario inicial
                    </h2>
                    <p className="text-foreground/60 mb-8 text-sm md:text-base">
                        Solo se rellena una vez. Tus respuestas ya están guardadas y tus macros calculados.
                    </p>
                    <div className="flex justify-center">
                        <Button onClick={() => navigate('/dashboard')}
                            className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8 py-6 text-lg">
                            Ir al inicio <ArrowRight className="w-5 h-5 ml-2" />
                        </Button>
                    </div>
                </div>
            </Shell>
        );
    }

    // LA PUERTA DEL CUESTIONARIO LARGO (el reloj del 19-08). Se abre el viernes a las
    // 10:00 y se cierra el lunes a las 18:00: fuera de ahí, al que viene a hacerlo se le
    // dice cuándo abre en vez de dejarle entrar. Solo cierra el COMPLETO del cliente: el
    // ajuste, el completar-huecos y el modo revisión del equipo pasan siempre, y el que
    // está en mitad del ALTA tampoco se corta (su puerta es la pantalla de elegir, que
    // con la ventana cerrada no le ofrece entrar).
    //
    // LA VENTANA ES DEL ALTA, NO DEL PERFIL (Francisco, 25-08). El doc dice «se abre el
    // cuestionario largo AL QUE SE ESTÁ DANDO DE ALTA», y explica para qué: el recién
    // llegado usa la calculadora con macros PROVISIONALES, el largo cierra el lunes y
    // «el miércoles tiene sus macros». La ventana existe para que el equipo saque los
    // macros de todos de una tacada. Al que YA TIENE LOS SUYOS puestos -- el migrado de
    // Calma al que nunca se le llenó el perfil largo -- esa cinta de montaje no le
    // aplica: no hay nada que entregarle el miércoles, así que esperar al viernes no
    // sirve para nada. Y era exactamente lo que le pasaba: Inicio le decía «completa tu
    // perfil» todos los días y la pantalla le contestaba «vuelve el viernes».
    const yaTieneSusMacros = !!(profile?.ajuste_macros_completado
        || profile?.macros_puestos_por_alguien);
    if (!revision && retomandoNivel1 && !yaTieneSusMacros
        && ventanaLargo && !ventanaLargo.abierta) {
        return (
            <Shell progress={0}>
                <div className="text-center" data-testid="ventana-largo-cerrada">
                    <div className="w-16 h-16 rounded-full bg-brand/10 flex items-center justify-center mx-auto mb-6">
                        <ClipboardList className="w-8 h-8 text-brand" />
                    </div>
                    <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-2 leading-tight">
                        Tu cuestionario se abre el {ventanaLargo.abre_label}
                    </h2>
                    <p className="text-foreground/60 mb-8 text-sm md:text-base">
                        Lo tendrás abierto hasta el {ventanaLargo.cierra_label}, hora de España.
                        Mientras tanto puedes usar la calculadora con tus macros de ahora.
                    </p>
                    <div className="flex justify-center">
                        <Button onClick={() => navigate('/dashboard')}
                            className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8 py-6 text-lg">
                            Ir a mi panel <ArrowRight className="w-5 h-5 ml-2" />
                        </Button>
                    </div>
                </div>
            </Shell>
        );
    }

    const step = flow[idx] || flow[0];
    // El progreso se calcula abajo, sobre los pasos que aplican de verdad (ver `visible`).

    // «LO HAGO LUEGO» (doc 19-08): salta directo a la oferta de los 87 € y le deja el
    // aviso pendiente de las preferencias («Son 2 minutos y nos ayudará a mostrarte las
    // cosas que te gustan»). Si por lo que sea no hay oferta en el recorrido, al panel.
    const saltarAOferta = () => {
        api.post('/clients/me/aviso-preferencias').catch(() => {});
        const i = flow.findIndex(s => s.type === 'oferta_ajuste');
        if (i > idx) setIdx(i);
        else navigate('/welcome');
    };

    const set = (key, value) => {
        // El ref se actualiza a la vez que el estado para que `visible()` vea la respuesta que
        // se acaba de dar, sin esperar al siguiente render.
        answersRef.current = { ...answersRef.current, [key]: value };
        setAnswers(a => ({ ...a, [key]: value }));
    };


    // ── Punto de partida: las medidas del dia 1 ──────────────────────────────
    //
    // Aquí también se le pedían las fotos, y se han quitado (punto 19 del doc del 07-08). El
    // motivo: acaba de darse de alta, todavía no sabe qué es un reporte ni para qué sirven
    // esas tres poses, y pedírselas ahí es pedirle que se desnude delante del móvil sin
    // haberle explicado nada. Las fotos van con el reporte, que es donde tienen sentido: se
    // le enseñan las del mes pasado al lado para que se coloque igual, y ahí sí entiende que
    // son para comparar.
    //
    // Lo que se pierde, y conviene saberlo: la foto "inicial" pasa a ser la de su primer
    // reporte y no la del día 1. Las medidas sí se siguen pidiendo aquí, con el vídeo de
    // Jesús explicando cómo se toman los perímetros, porque de esas no hay pudor que valga.

    const guardarPuntoDePartida = async () => {
        // Las MISMAS diez que en el reporte. Había tres listas distintas en la app -- aquí
        // cuatro (cintura, abdomen, cadera y la altura), en el check-in cinco y en el
        // reporte otras cinco -- y ninguna era la suya. Con listas distintas, la medida
        // del punto de partida no se puede comparar con la del mes siguiente, que es lo
        // único para lo que sirve tomarla.
        //
        // La altura NO va aquí: es un dato fijo, no una medida de seguimiento. Se pregunta
        // una vez en el cuestionario y se manda aparte.
        const medidas = {};
        for (const { key } of MEDIDAS) {
            const n = num(answers[`medida_${key}`]);
            if (n) medidas[key] = n;
        }
        try {
            await api.post('/clients/punto-de-partida', { medidas, altura: num(answers.height) });
        } catch (e) { /* no bloquea: lo importante son las fotos, que ya estan subidas */ }
        goNext();
    };

    const elegirFotoDieta = () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = (ev) => {
            const file = ev.target.files?.[0];
            if (!file) return;
            if (file.size > 8 * 1024 * 1024) { toast.error('La foto pesa demasiado (máximo 8 MB)'); return; }
            const reader = new FileReader();
            reader.onload = (e) => set('dieta_imagen', e.target.result);
            reader.readAsDataURL(file);
        };
        input.click();
    };

    const leerMiDieta = async () => {
        const modo = answers.dieta_modo || 'texto';
        const cuerpo = modo === 'foto' ? { imagen: answers.dieta_imagen }
            : { texto: answers.dieta_texto };
        const vacio = modo === 'foto' ? !answers.dieta_imagen
            : !(answers.dieta_texto || '').trim();
        if (vacio) {
            toast.error(modo === 'foto' ? 'Sube la foto de tu dieta'
                : 'Cuéntanos qué comes en un día');
            return;
        }
        setLeyendoDieta(true);
        try {
            const r = await api.post('/clients/leer-dieta', cuerpo);
            setLecturaDieta(r.data);
        } catch (e) {
            toast.error(mensajeDeError(e, 'No hemos podido leer tu dieta'));
        } finally {
            setLeyendoDieta(false);
        }
    };

    // Confirmada: ya puede entrar en el cálculo. Los hidratos que manda el método son los del
    // día de entreno (comidas + peri), que es lo que el cliente acaba de validar.
    const confirmarDieta = () => {
        const m = lecturaDieta?.macros || {};
        const respuestas = {
            ...answers,
            dieta_hc_entreno: m.hidratos ?? null,
            dieta_grasa_entreno: m.grasa ?? null,
            dieta_confirmada: true,
        };
        answersRef.current = respuestas;
        setAnswers(respuestas);
        recalcularEnVivo(respuestas);
        guardarProgreso(respuestas, idx);
        setLecturaDieta(null);
        goNext();
    };

    // La oferta del final: se apunta lo que conteste y se le lleva a su panel. No cobra
    // nada todavía (ver POST /clients/ajuste-a-medida): falta decidir cómo se cobra.
    // SE COBRA AQUÍ MISMO (Francisco, 18-08). Antes solo se apuntaba lo que contestaba y el
    // equipo lo veía en su campana: quien decía que sí se quedaba esperando un correo que no
    // salía de ningún sitio. Ahora el sí va derecho a Stripe, y al volver el ajuste ya está
    // en la cola del lunes.
    //
    // El no se sigue guardando: saber cuánta gente lo rechaza vale igual que saber quién lo
    // compra, y es lo que dice si la oferta está bien puesta o no.
    const responderOferta = async (quiere) => {
        setLoading(true);
        try {
            await api.post('/clients/ajuste-a-medida', { quiere });
            if (quiere) {
                const { data } = await api.post('/billing/ajuste-a-medida/checkout', {});
                if (data?.checkout_url) {
                    window.location.href = data.checkout_url;   // se va a Stripe
                    return;
                }
                throw new Error('sin checkout_url');
            }
            toast.success('Perfecto, seguimos con tu plan.');
        } catch (e) {
            // Al usuario nunca la traza: si el cobro no arranca, se le dice que lo tenemos
            // apuntado -- que es verdad, la respuesta sí se guardó -- y el equipo lo ve.
            console.error('[alta] la oferta del ajuste a medida', e);
            if (quiere) {
                toast.info('Lo tenemos apuntado. Te escribimos para cerrarlo.');
            }
        } finally {
            setLoading(false);
            navigate('/welcome');
        }
    };

    // Una respuesta contestada: se recalcula y se guarda, las dos cosas con lo de este instante.
    const trasResponder = (key, value) => {
        const respuestas = { ...answers, [key]: value };
        recalcularEnVivo(respuestas);
        guardarProgreso(respuestas, idx);
    };

    // Pasos condicionales (p.ej. las preguntas de la dieta solo si sigue_dieta).
    //
    // Se leen de un ref y no del estado a proposito: al pasar de pantalla se comprueba que pasos
    // hay que saltar, y esa comprobacion ocurre justo despues de contestar, cuando el estado de
    // React todavia tiene el valor anterior. Con `answers` a secas, decir "si, sigo una dieta"
    // se saltaba las cuatro preguntas de la dieta, que es justo lo que acababa de habilitar.
    // Lo que YA TIENE, para no pedírselo otra vez. Las medidas se marcan en el perfil y las
    // fotos se cuentan en su ficha; sin mirar las dos, a quien ya las subió se le seguía
    // diciendo «sube tus fotos y toma tus medidas», que es pedirle lo que acaba de dar.
    const yaTieneMedidas = !!(profile?.punto_de_partida_hecho || profile?.medidas_inicio);
    const yaTieneFotos = (ficha?.fotos_subidas || 0) > 0;

    const visible = (s) => {
        // Y si tiene las dos, la pantalla entera sobra: no hay nada que pedirle.
        if (s.type === 'fotos_medidas' && yaTieneMedidas && yaTieneFotos) return false;
        // El encadenado del 19-08 no pide lo que ya está dado.
        if (s.type === 'fotos_alta' && yaTieneFotos) return false;
        if (s.type === 'medidas_alta' && yaTieneMedidas) return false;
        // Sin entrenador, las medidas del día 1 se piden en el encadenado («2 · Tomar las
        // medidas»), no aquí: con las dos pantallas se le pedían las mismas diez medidas
        // dos veces seguidas, y la segunda ni salía porque la primera ya la marcaba hecha.
        if (s.type === 'partida' && !tieneCoach) return false;
        return !s.cond || s.cond(answersRef.current);
    };
    // Solo en desarrollo: deja a mano el recorrido y en qué paso va, para poder mirar desde
    // la consola por qué una pantalla no avanza. En producción no se ejecuta.
    if (process.env.NODE_ENV === 'development') {
        window.__quiz = { idx, pasos: flow.map(s => s.key || s.type), respuestas: answersRef.current };
    }

    // PEDIR «SIGUIENTE» EN LA ÚLTIMA PANTALLA ES HABER TERMINADO.
    //
    // `goNext` se topaba con el final de la lista y se quedaba donde estaba, en silencio. Con
    // eso, cualquier botón de la última pantalla es un botón muerto: el cliente lo pulsa, no
    // pasa nada y no tiene forma de salir salvo el botón de atrás del navegador. Pasaba en la
    // pantalla de macros de «nos faltan cosas tuyas», que ahí es la última.
    const goNext = () => {
        if (idx >= flow.length - 1) { navigate('/welcome'); return; }
        // Si vino del repaso a corregir una respuesta, contestar le devuelve al repaso.
        if (volverAlRepasoRef.current != null) {
            const destino = volverAlRepasoRef.current;
            volverAlRepasoRef.current = null;
            guardarProgreso(answersRef.current, destino);
            setIdx(destino);
            return;
        }
        let j = idx + 1;
        while (j < flow.length - 1 && !visible(flow[j])) j++;
        const destino = Math.min(j, flow.length - 1);
        // EL BORRADOR SE GUARDA AL AVANZAR, CON TODO (regla 3 del doc del 23-08). Antes
        // solo guardaban las preguntas de opciones (pickChoice): lo escrito en textos,
        // números y multiselects se quedaba en memoria, y quien salía a mitad volvía a una
        // pantalla anterior a la suya. Se guarda el índice de DESTINO, no el actual: al
        // volver se aterriza en la primera pregunta sin contestar, no en la última que
        // acababa de responder.
        guardarProgreso(answersRef.current, destino);
        setIdx(destino);
    };

    const cancelarAvancePendiente = () => {
        if (avancePendienteRef.current) {
            clearTimeout(avancePendienteRef.current);
            avancePendienteRef.current = null;
        }
    };
    const goBack = () => {
        cancelarAvancePendiente();
        // Retroceder a mano cancela la vuelta automática al repaso: manda su último gesto.
        volverAlRepasoRef.current = null;
        setIdx(i => {
            let j = i - 1;
            while (j > 0 && !visible(flow[j])) j--;
            return Math.max(j, 0);
        });
    };

    const num = (v) => { const n = parseFloat(v); return isNaN(n) ? null : n; };

    // TODO LO QUE TRAE EL BÁSICO, en un solo sitio: lo mandan el alta y también el cierre del
    // cuestionario largo cuando el cliente no había pasado nunca por el básico (los de Calma).
    // Escrito dos veces se quedaría viejo en una de las dos el día que se añada una pregunta.
    const cuerpoDelBasico = () => ({
        name: answers.name,
        email: answers.email,
        phone: answers.phone,
        goal: answers.goal,
        sex: answers.sex,
        weight: parseFloat(answers.weight),
        body_fat: parseFloat(answers.body_fat),
        birthdate: answers.birthdate || null,
        height: num(answers.height),
        biotype: answers.biotype || null,
        training_experience: answers.training_experience || null,
        // Sus días de entreno (7.1 del 21-08): nombres de día, los guarda el perfil.
        training_weekdays: answers.training_weekdays || null,
        profesion: answers.profesion || null,
        como_me_conociste: answers.como_me_conociste || null,
        proteinas_habituales: answers.proteinas_habituales || null,
        peso_maximo: num(answers.peso_maximo),
        peso_maximo_ano: num(answers.peso_maximo_ano),
        peso_maximo_nota: answers.peso_maximo_nota || null,
        peso_mejor_momento: num(answers.peso_mejor_momento),
        peso_mejor_momento_ano: num(answers.peso_mejor_momento_ano),
        peso_mejor_momento_nota: answers.peso_mejor_momento_nota || null,
        // El «pásala» viaja como respuesta: sin él, la ficha no distingue «no he estado
        // en forma» de «no llegó a contestar».
        mejor_forma_pasada: answers.mejor_forma_pasada === true ? true : null,
        foto_mejor_momento: answers.foto_mejor_momento || null,
        peso_minimo: num(answers.peso_minimo),
        peso_minimo_ano: num(answers.peso_minimo_ano),
        peso_minimo_nota: answers.peso_minimo_nota || null,
        alergias: answers.alergias || null,
        lactosa: answers.lactosa || null,
        gluten: answers.gluten || null,
        alergia_otra: answers.alergia_otra || null,
        // La foto del carrusel de grasa (doc 23-08, punto 1) y lo que no quiere ver en el
        // plato (punto 14). El backend guarda la foto aparte y funde las exclusiones con
        // las que salen de sus intolerancias.
        foto_grasa: answers.foto_grasa || null,
        avoided_categories: answers.avoided_categories || null,
        avoided_keywords: answers.avoided_keywords || null,
        dietas_previas: answers.dietas_previas || null,
        tiempo_intentandolo: answers.tiempo_intentandolo || null,
        motivo_apuntarse: answers.motivo_apuntarse || null,
        entrenador_anterior: answers.entrenador_anterior || null,
        // El relato solo si ha dicho que sí: si contesta «sí», escribe, y luego se vuelve
        // atrás y lo cambia a «no», lo escrito deja de tener a qué referirse.
        entrenador_anterior_que_tal: answers.entrenador_anterior === 'si'
            ? (answers.entrenador_anterior_que_tal || null) : null,
    });

    // Las respuestas que ajustan los macros, en el formato que espera el backend.
    // Recibe las respuestas por parametro para poder calcular con las de ESTE instante: el
    // estado de React aun no se ha actualizado cuando se acaba de pulsar una opcion.
    const ajustesDe = (a) => ({
        actividad_diaria: a.actividad_diaria ?? null,
        deporte_extra: a.deporte_extra ?? null,
        facilidad_engordar: a.facilidad_engordar ?? null,
        cuesta_definir: a.cuesta_definir ?? null,
        sigue_dieta: a.sigue_dieta ?? null,
        tiempo_dieta: traeDieta(a) ? (a.tiempo_dieta ?? null) : null,
        como_va: traeDieta(a) ? (a.como_va ?? null) : null,
        hambre_saturacion: traeDieta(a) ? (a.hambre_saturacion ?? null) : null,
        dieta_texto: traeDieta(a) ? (a.dieta_texto || null) : null,
        dieta_hc_entreno: traeDieta(a) ? num(a.dieta_hc_entreno) : null,
        dieta_grasa_entreno: traeDieta(a) ? num(a.dieta_grasa_entreno) : null,
        dieta_confirmada: a.dieta_confirmada === true,
    });

    const ajustesDelCuestionario = () => ({
        actividad_diaria: answers.actividad_diaria ?? null,
        deporte_extra: answers.deporte_extra ?? null,
        // Las dos del deporte solo tienen sentido si ha dicho que sí practica alguno.
        deporte_cual: answers.deporte_extra === true ? (answers.deporte_cual || null) : null,
        deporte_en_descanso: answers.deporte_extra === true ? (answers.deporte_en_descanso ?? null) : null,
        facilidad_engordar: answers.facilidad_engordar ?? null,
        apetito: answers.apetito ?? null,
        cuesta_definir: answers.cuesta_definir ?? null,
        training_experience: answers.training_experience ?? null,
        sigue_dieta: answers.sigue_dieta ?? null,
        // Lo que solo tiene sentido si trae dieta. `parecido` cuenta como que la trae.
        tiempo_dieta: conDieta() ? (answers.tiempo_dieta ?? null) : null,
        hambre_saturacion: conDieta() ? (answers.hambre_saturacion ?? null) : null,
        dieta_texto: conDieta() ? (answers.dieta_texto || null) : null,
        dieta_hc_entreno: conDieta() ? num(answers.dieta_hc_entreno) : null,
        dieta_grasa_entreno: conDieta() ? num(answers.dieta_grasa_entreno) : null,
        dieta_confirmada: answers.dieta_confirmada === true,
        // Esta va SIEMPRE: ahora se le pregunta a los tres, también al que come lo que
        // surge, y ahí es donde más dice. Condicionarla a que siga una dieta era tirar la
        // respuesta de quien no la sigue.
        como_va: answers.como_va ?? null,
        // El biotipo y la altura ya no están en el perfil largo: se contestan aquí, en el
        // cuestionario que ven los tres planes, así que aquí se guardan.
        biotype: answers.biotype || null,
        height: num(answers.height),
    });

    // Trae dieta: la mide (true) o come parecido sin medirla ('parecido'). Solo el
    // "no, como lo que surge" (false) se queda fuera.
    const conDieta = () => traeDieta(answers);

    // CALCULAR. En el alta van los cuatro datos de la tabla y salen macros provisionales; en el
    // cuestionario de ajuste van las respuestas que ajustan y salen los definitivos.
    const submitNivel0 = async () => {
        setLoading(true);
        try {
            // Los cuatro datos de la tabla van primero, porque son los que crean la ficha y
            // sin ficha no hay nada que ajustar. Pero no se le enseña ningún número todavía:
            // el resultado que ve es uno solo, el de después, ya con los modificadores.
            // Y TAMBIÉN CUANDO VIENE A COMPLETAR: ese ya tiene el cuestionario dado por
            // hecho, así que sin esto su pasada no llegaba a guardarse (el servidor la
            // rechazaba con un 409) y se quedaba mirando el botón de calcular.
            //
            // Y cuando le falta algo de la base (peso, grasa u objetivo): esas respuestas
            // TIENEN que estar escritas antes de pedir el ajuste, porque el ajuste las lee
            // del perfil. Sin esto contestaba las preguntas nuevas y el servidor seguía
            // diciendo que le faltaban.
            const rellenandoHuecos = !!elBasicoQueFalta?.length || !!faltaLaBase.length;
            if (!profile?.questionnaire_completed || rellenandoHuecos) {
                await api.post('/clients/questionnaire', {
                    // SIEMPRE `true` cuando se van a rellenar huecos, sin mirar la bandera del
                    // perfil que hay en memoria: si esa llega vieja -- y llega, justo después
                    // del alta -- se mandaba `false` sobre un cuestionario ya guardado y el
                    // servidor contestaba «el cuestionario ya fue completado». El servidor solo
                    // le hace caso si de verdad estaba completado, así que mandarlo de más no
                    // abre ninguna puerta.
                    completar: rellenandoHuecos,
                    ...cuerpoDelBasico(),
                });
            }
            // EL AJUSTE PUEDE DECIR QUE NO, Y NO ES UN ERROR.
            //
            // Al cliente cuyos macros lleva el equipo se le contesta 403 -- «tus macros los
            // llevamos nosotros» -- y eso es correcto: nadie va a machacar lo que le puso su
            // entrenador. Lo que no puede pasar es que se le caiga encima al final de veinte
            // pantallas, en rojo y sin dejarle salir, cuando sus respuestas YA se han
            // guardado en la línea de arriba. Se sigue adelante y ve los macros que tiene.
            let res = null;
            try {
                res = await api.post('/clients/ajustar-macros', ajustesDelCuestionario());
            } catch (e) {
                if (e?.response?.status !== 403) throw e;
                console.info('[alta] sus macros los lleva el equipo: no se recalculan', e);
            }
            setResultado(res?.data?.resultado || null);
            // Con los macros ya calculados, se le deja el día de hoy montado. Va en segundo
            // plano y sin bloquear: si falla, se queda como estaba (con su día por montar) y
            // no se le estropea el final del alta por esto.
            // Con LA FECHA DEL CLIENTE (bloque F, 23-08): sin ella el servidor montaba el
            // dia en su propio reloj y un alta de madrugada estrenaba la app con el hoy
            // vacio y la dieta puesta en ayer.
            api.post('/calculator/montar-dia',
                     { guardar: true, fecha: new Date().toLocaleDateString('en-CA') })
                .then(r => setDiaMontado(r.data || null))
                .catch(() => {});
            setEntrega(res?.data?.entrega || null);
            setNivel0Enviado(true);
            await refreshProfile();
            // Y lo que se le dice, según lo que haya pasado de verdad: al que se los llevamos
            // nosotros no se le canta «macros calculados», porque no se le han calculado.
            toast.success(res ? '¡Macros calculados!' : 'Guardado. Tu entrenador lo tiene ya.');
            goNext(); // -> pantalla de resultados
        } catch (e) {
            toast.error(mensajeDeError(e, 'Error al enviar el cuestionario'));
        } finally {
            setLoading(false);
        }
    };

    // Nivel 1 -> guardar perfil largo (no toca macros).
    //
    // `destino` es a dónde se le manda después. Por defecto a su Inicio, pero desde la última
    // pantalla del completo -- las fotos y las medidas -- se le manda a subirlas, y ahí hay
    // que GUARDAR ANTES de sacarle del cuestionario: si no, se va a la pantalla de reportes y
    // las veinte respuestas que acaba de dar se quedan sin escribir en su ficha.
    // Se comprueba que sea texto porque este mismo método es el `onClick` del botón de
    // enviar, y un onClick recibe el evento del clic como primer argumento.
    const submitNivel1 = async (destino) => {
        const irA = typeof destino === 'string' ? destino : '/welcome';
        setLoading(true);
        try {
            // LO DEL BÁSICO PRIMERO, si este cliente nunca pasó por él (los que vienen de
            // Calma). El cuestionario largo no escribe el objetivo, ni el peso, ni las
            // proteínas, ni recalcula macros: eso lo hace la puerta del alta, y sin esta
            // llamada el cliente contestaba veinte pantallas más y su ficha seguía coja.
            if (laBaseQueFalta.length || loQueFaltaDelBasico.length) {
                await api.post('/clients/questionnaire', {
                    completar: true,     // ver el comentario en el envío del alta
                    ...cuerpoDelBasico(),
                });
            }
            // LAS QUE MUEVEN LOS MACROS, TAMBIÉN DESDE AQUÍ (punto 26 del doc del 19-08).
            // Las cuatro de la dieta ya no se preguntan en el alta: el que lleva entrenador
            // las contesta en este cuestionario, y el envío de abajo no las lleva -- el
            // nivel1 no toca macros --. Van por el mismo camino que en el alta: ese
            // endpoint guarda las respuestas ANTES de su candado, así que al de plan
            // personalizado le contesta 403 sin recalcular nada -- que es lo que se quiere
            // -- pero su `ajustes_macros` queda escrito y su entrenador lo puede leer.
            // Si falla por otra cosa no se le estropea el cierre del completo: sus veinte
            // respuestas van en la llamada de abajo, que es la que manda.
            try {
                await api.post('/clients/ajustar-macros', ajustesDelCuestionario());
            } catch (e) {
                console.info('[completo] los ajustes no se recalcularon', e?.response?.status, e);
            }
            await api.post('/clients/questionnaire/nivel1', {
                biotype: answers.biotype || null,
                height: num(answers.height),
                birthdate: answers.birthdate || null,
                training_experience: answers.training_experience || null,
                peso_maximo: num(answers.peso_maximo),
                peso_minimo: num(answers.peso_minimo),
                peso_mejor_momento: num(answers.peso_mejor_momento),
                dietas_previas: answers.dietas_previas || null,
                // Los días de entreno y la hora ya no se preguntan: van por defecto y se
                // cambian en Preferencias (bloque 5 del doc del 18-08).
                material: answers.material || null,
                cardio: answers.cardio || null,
                // Bloque 3: lo que hace falta para montarle la rutina. Entrenar AHORA no es
                // lo mismo que llevar años, y lo que NO tiene pesa tanto como lo que tiene.
                entrena_ahora: answers.entrena_ahora || null,
                maquinas_que_faltan: answers.maquinas_que_faltan || null,
                // Pantalla 22: la lesión y sus tres detalles.
                lesion: answers.lesion || null,
                lesion_cual: answers.lesion_cual || null,
                lesion_tiempo: answers.lesion_tiempo || null,
                ejercicios_imposibles: answers.ejercicios_imposibles || null,
                // Pantallas 6 y 7: lo médico, que faltaba entero.
                patologia: answers.patologia || null,
                patologia_detalle: answers.patologia_detalle || null,
                medicacion: answers.medicacion || null,
                medicacion_detalle: answers.medicacion_detalle || null,
                // Pantallas 10 y 11: el descanso, con los tramos de Jesús.
                horas_sueno: answers.horas_sueno || null,
                ayuda_dormir: answers.ayuda_dormir || null,
                // Pantallas 12, 13 y 14: su suplementación. Sin esto se le pauta a ciegas.
                suplementos_ahora: answers.suplementos_ahora || null,
                suplementos_veto: answers.suplementos_veto || null,
                quiere_pauta_suplementos: answers.quiere_pauta_suplementos || null,
                // Pantalla 9: la intención cuenta tanto como el uso.
                farmacologia_uso: answers.farmacologia_uso || null,
                farmacologia_detalle: answers.farmacologia_detalle || null,
                lactosa: answers.lactosa || null,
                gluten: answers.gluten || null,
                alergias: answers.alergias || null,
                // Pantalla 8: no mueve macros, sirve para emparejarlo con casos anteriores.
                trt: answers.trt || null,
                tiempo_intentandolo: answers.tiempo_intentandolo || null,
                motivo_apuntarse: answers.motivo_apuntarse || null,
            });
            toast.success('¡Perfil completo! El equipo ya tiene toda la información.');
            // «PRÓXIMOS PASOS» ANTES DE SOLTARLE EN LA APP (doc 23-08, punto 26). El
            // refresco del perfil espera al «Entendido»: hecho aquí, el recorrido se
            // recompone debajo de la pantalla (el largo pasa a completado) y se la lleva
            // por delante antes de que la lea.
            setPasosFinales(irA);
        } catch (e) {
            toast.error(mensajeDeError(e, 'Error al guardar el perfil'));
        } finally {
            setLoading(false);
        }
    };

    // LO QUE ESTÁ MAL, DICHO EN SU PANTALLA Y NO AL FINAL.
    //
    // El servidor tiene rangos para el peso, la altura y la grasa, pero solo los comprueba al
    // enviar: quien escribía 80 en la altura contestaba veinte pantallas más y se estrellaba
    // en el botón de calcular con «Revisa el campo height», sin saber a cuál de las veinte
    // tenía que volver. Ahora se dice aquí, con el rango que esperamos, y el botón no deja
    // pasar hasta que cuadre.
    const RANGOS = {
        height: [120, 230, 'Tu altura, en centímetros. Entre 120 y 230.'],
        weight: [25, 300, 'Tu peso, en kilos. Entre 25 y 300.'],
        peso_maximo: [25, 300, 'En kilos, entre 25 y 300.'],
        peso_minimo: [25, 300, 'En kilos, entre 25 y 300.'],
        peso_mejor_momento: [25, 300, 'En kilos, entre 25 y 300.'],
    };

    // El aviso de este paso, o null si lo que ha escrito está bien. Se enseña solo cuando ya
    // ha escrito algo: en blanco no hay nada que corregir todavía.
    const avisoDelPaso = (() => {
        const rango = RANGOS[step.key];
        if (!rango) return null;
        const v = answers[step.key];
        if (v === undefined || v === null || `${v}`.trim() === '') return null;
        const n = parseFloat(String(v).replace(',', '.'));
        const [min, max, texto] = rango;
        return (isNaN(n) || n < min || n > max) ? texto : null;
    })();

    // Validación del paso actual (para inputs de texto/número).
    const inputValid = () => {
        if (avisoDelPaso) return false;
        if (!step.key || !step.required) return true;
        const v = answers[step.key];
        if (v === undefined || v === null || `${v}`.trim() === '') return false;
        if (step.type === 'email') return /\S+@\S+\.\S+/.test(v);
        if (step.type === 'number') return !isNaN(parseFloat(v)) && parseFloat(v) > 0;
        return true;
    };

    // Lo que hace falta para poder calcular unos macros que signifiquen algo (punto 12 del
    // doc del 07-08). Antes se podía llegar al botón de calcular sin haber contestado, y la
    // app devolvía unos números como si fueran suyos: los cuatro datos de la tabla salían del
    // perfil y los tres modificadores viajaban vacíos, así que no movían nada.
    //
    // Solo se exige lo que de verdad cambia el número. El resto de preguntas del recorrido
    // (las que sirven para conocerle) se pueden dejar en blanco, que para eso están ahí.
    const OBLIGATORIAS = [
        { key: 'sex', label: 'tu sexo' },
        { key: 'goal', label: 'tu objetivo' },
        { key: 'weight', label: 'tu peso' },
        { key: 'body_fat', label: 'tu porcentaje de grasa' },
        { key: 'actividad_diaria', label: 'tu actividad diaria' },
        { key: 'deporte_extra', label: 'si practicas otro deporte' },
        { key: 'facilidad_engordar', label: 'con qué facilidad engordas' },
    ];

    // Las que este recorrido pregunta de verdad: en el ajuste los cuatro datos de partida ya
    // están en la ficha y no se vuelven a preguntar, así que no se pueden exigir aquí.
    const clavesDelFlujo = new Set(flow.map(s => s.key).filter(Boolean));
    const faltanPorContestar = OBLIGATORIAS.filter(o =>
        clavesDelFlujo.has(o.key) &&
        (answers[o.key] === undefined || answers[o.key] === null || `${answers[o.key]}`.trim() === ''));

    // Selección de una opción de tipo choice → guarda y avanza.
    const pickChoice = (value) => {
        if (step.confirm) {
            // "¿Estás seguro?": Sí mantiene el goal; No lo invierte.
            if (value === 'no') set('goal', answers.goal === 'volumen' ? 'definicion' : 'volumen');
            goNext();
            return;
        }
        set(step.key, value);
        trasResponder(step.key, value);
        // Un poco mas de pausa que antes: da tiempo a ver moverse los macros de la cabecera
        // antes de pasar a la siguiente pregunta. Se guarda para poder cancelarlo: si el
        // cliente pulsa Atrás mientras corre, manda el Atrás (punto 4.12).
        cancelarAvancePendiente();
        avancePendienteRef.current = setTimeout(() => {
            avancePendienteRef.current = null;
            goNext();
        }, modoAjuste ? 550 : 150);
    };

    const confirmOptions = () => {
        const isVol = answers.goal === 'volumen';
        return [
            { value: 'si', label: isVol ? 'Sí, lo tengo claro: quiero ganar Masa Muscular (VOLUMEN)' : 'Sí, lo tengo claro: quiero perder Grasa (DEFINICIÓN)' },
            { value: 'no', label: isVol ? 'No, en realidad quiero perder Grasa (DEFINICIÓN)' : 'No, en realidad quiero ganar Masa Muscular (VOLUMEN)' },
        ];
    };

    // El titulo, la descripcion y las opciones pueden ser funcion de las respuestas: hay preguntas
    // que se formulan distinto segun el objetivo (definicion o volumen).
    const segunRespuestas = (v) => (typeof v === 'function' ? v(answers) : v);

    // EL TAMAÑO, SEGÚN LO LARGA QUE SEA LA PREGUNTA. Los enunciados de Jesús son de dos y de
    // cuatro líneas -- el de la maquinaria tiene 250 caracteres -- y a tamaño de titular
    // llenaban la pantalla entera: el campo para contestar y el botón se iban por debajo, y
    // el cliente veía un muro de letras sin nada que hacer.
    const Title = () => {
        const texto = segunRespuestas(step.title) || '';
        const tam = texto.length > 160 ? 'text-xl md:text-2xl'
            : texto.length > 90 ? 'text-2xl md:text-3xl'
                : 'text-3xl md:text-4xl';
        return (
            <>
                <h2 className={`font-heading font-bold ${tam} text-foreground mb-2 leading-tight`}>{texto}</h2>
                {step.desc && <p className="text-foreground/60 mb-8 text-sm md:text-base">{segunRespuestas(step.desc)}</p>}
            </>
        );
    };

    const BackBtn = () => (idx > 0 ? (
        <Button variant="ghost" onClick={goBack} className="text-foreground/60">
            <ArrowLeft className="w-4 h-4 mr-1" /> Atrás
        </Button>
    ) : null);

    // Props comunes de los inputs de pasos compuestos (dieta, pesos, salud).
    const mini = { answers, set };

    let body;
    if (step.type === 'statement' && idx === 0 && !retomandoNivel1) {
        // Portada: logo de marca grande + flecha, estilo Typeform.
        body = (
            <div className="text-center">
                <div className="flex justify-center mb-8">
                    <Logo12EN12 size="xl" />
                </div>
                <h2 className="font-heading font-bold text-4xl md:text-5xl uppercase tracking-tight text-foreground mb-3">{step.title}</h2>
                {step.desc && <p className="text-foreground/60 mb-10 text-base max-w-md mx-auto">{step.desc}</p>}
                <Button onClick={goNext}
                    className="bg-brand hover:bg-brand/90 text-white font-bold uppercase tracking-wider px-10 py-6 text-lg">
                    {/* w-4: la flecha ya no trae aire dentro, así que con el tamaño de antes
                        se veía más grande que el texto del botón. */}
                    Empezar <BrandArrow className="w-4 h-4 ml-2 text-white" />
                </Button>
            </div>
        );
    } else if (step.type === 'statement' || step.type === 'titulo') {
        body = (
            <div>
                {/* Las portadas de bloque (doc 23-08) llevan una ceja que dice qué son:
                    sin ella, un título suelto parece una pregunta a la que le falta algo. */}
                {step.type === 'titulo' && (
                    <p className="text-[11px] uppercase tracking-[0.2em] text-brand font-bold mb-3">Siguiente bloque</p>
                )}
                <Title />
                <div className="flex gap-3">
                    <BackBtn />
                    <Button onClick={goNext} data-testid={step.type === 'titulo' ? 'titulo-continuar' : undefined}
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8 py-6 text-lg">
                        {step.cta || 'Continuar'} <ArrowRight className="w-5 h-5 ml-2" />
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'final0' || step.type === 'final1') {
        const isN0 = step.type === 'final0';
        // Sin las respuestas que mueven el número no hay nada que calcular: el botón espera y
        // se dice cuáles faltan, en vez de devolver unos macros que no son de nadie.
        const bloqueado = isN0 && faltanPorContestar.length > 0;
        // LA REJILLA DEL REPASO (doc del 23-08, punto 16): lo contestado, tarjeta a
        // tarjeta; tocar una lleva a su pregunta y contestar devuelve aquí. Solo salen
        // las que su recorrido de verdad preguntó (en mujer no hay biotipo, por ejemplo).
        const cap = (s) => s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
        const etiquetaDe = (paso, valor) => {
            const opts = segunRespuestas(paso?.options) || [];
            const o = opts.find(x => x.value === valor);
            // La etiqueta corta: lo de antes de los dos puntos («Muy sedentario: paso...»).
            return o ? String(o.label).split(':')[0] : null;
        };
        const conAno = (v, ano) => (v == null || v === '') ? null : `${v} kg${ano ? ` (${ano})` : ''}`;
        const REPASO = [
            ['goal', 'Objetivo', answers.goal === 'volumen' ? 'Ganar masa muscular'
                : answers.goal === 'definicion' ? 'Perder grasa' : null],
            ['weight', 'Peso', answers.weight ? `${answers.weight} kg` : null],
            ['height', 'Altura', answers.height ? `${answers.height} cm` : null],
            ['body_fat', 'Grasa', answers.body_fat != null ? `${answers.body_fat} %` : null],
            ['ocupacion', 'Actividad', etiquetaDe(q('actividad_diaria'), answers.actividad_diaria)],
            ['biotype', 'Biotipo', (BIOTIPOS.find(b => b.value === answers.biotype)?.label || '').split(' (')[0] || null],
            ['peso_maximo', 'Tu máximo', conAno(answers.peso_maximo, answers.peso_maximo_ano)],
            ['peso_mejor_momento', 'Tu mejor forma', conAno(answers.peso_mejor_momento, answers.peso_mejor_momento_ano)],
            ['training_weekdays', 'Cuándo entrenas',
                Array.isArray(answers.training_weekdays) && answers.training_weekdays.length
                    // Con sus tildes: los valores van sin ellas a propósito (backend), pero
                    // aquí se enseñan las etiquetas de la pregunta.
                    ? answers.training_weekdays
                        .map(v => ({ miercoles: 'Miércoles', sabado: 'Sábado' }[v] || cap(v)))
                        .join(', ')
                    : null],
        ];
        const irACorregir = (clave) => {
            const destino = flow.findIndex(s => s.key === clave || s.type === clave);
            if (destino < 0) return;
            volverAlRepasoRef.current = idx;
            setIdx(destino);
        };
        // «Su recorrido de verdad»: el paso tiene que existir Y aplicarle (en mujer el
        // biotipo está en la lista pero su condición lo apaga; enseñarle esa tarjeta
        // «Sin contestar» es enseñarle un hueco que no puede rellenar).
        const enElFlujo = (clave) => flow.some(s => (s.key === clave || s.type === clave) && visible(s));
        body = (
            <div>
                <Title />
                {isN0 && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 mb-6" data-testid="repaso-respuestas">
                        {REPASO.filter(([clave]) => enElFlujo(clave)).map(([clave, rotulo, valor]) => (
                            <button key={clave} type="button" onClick={() => irACorregir(clave)}
                                data-testid={`repaso-${clave}`}
                                className="text-left rounded-xl border-2 border-[#222222] bg-card px-3.5 py-3 hover:border-brand/60 transition-all">
                                <p className="text-[10px] uppercase tracking-wider text-foreground/40 font-bold">{rotulo}</p>
                                <p className={`text-sm font-semibold mt-0.5 ${valor ? 'text-foreground' : 'text-foreground/35'}`}>
                                    {valor || 'Sin contestar'}
                                </p>
                            </button>
                        ))}
                    </div>
                )}
                {bloqueado && (
                    <p className="text-sm text-amber-500 mb-5" data-testid="faltan-obligatorias">
                        Antes de calcular falta que nos digas {faltanPorContestar.map(o => o.label).join(', ')}.
                        Toca la tarjeta y complétalo.
                    </p>
                )}
                <div className="flex gap-3">
                    <BackBtn />
                    <Button onClick={isN0 ? submitNivel0 : submitNivel1} disabled={loading || bloqueado}
                        data-testid="calcular-macros-btn"
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8 py-6 text-lg disabled:opacity-40">
                        {loading ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <Check className="w-5 h-5 mr-2" />}
                        {loading ? 'Enviando...' : isN0 ? 'Confirmar' : 'Enviar'}
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'result') {
        // Los 8 números del motor v2 + desglose explicable.
        const m = resultado?.macros;
        body = (
            <div>
                {/* Ya no hay macros "provisionales" que decir: desde que el alta es un solo
                    recorrido (punto 15 del doc del 07-08), lo que se calcula aquí ya lleva
                    dentro las respuestas que mueven los hidratos. Así que el mensaje solo
                    depende de si hay un entrenador detrás que los vaya a repasar. */}
                {/* LOS TEXTOS DEL DOC DEL 23-08 (punto 17) para quien no lleva entrenador:
                    «Y ya estaría» de ceja, «iniciales» en el título -- van a mejorar con el
                    tiempo, y se le dice --, y la próxima revisión con sus semanas y su
                    fecha. Al del plan con entrenador se le mantiene su cierre (el aviso de
                    las 48 horas va debajo de los números, punto 4.1). */}
                {!entrega?.con_entrenador && (
                    <p className="text-[11px] uppercase tracking-[0.2em] text-brand font-bold mb-2">Y ya estaría</p>
                )}
                <h2 className="font-heading font-bold text-2xl md:text-3xl text-foreground mb-2 leading-tight">
                    {/* Al del plan con entrenador, el título del doc del 23-08 (punto 23):
                        «primeros», porque los definitivos se los manda su equipo. */}
                    {entrega?.con_entrenador ? 'Ya tienes tus primeros macros' : 'Estos son tus macros iniciales'}
                </h2>
                {!entrega?.con_entrenador && (
                    <p className="text-foreground/60 mb-4 text-sm">
                        Están adaptados a tu perfil, basándonos en tus respuestas y tomando como
                        referencia otros perfiles parecidos al tuyo. Conforme más tiempo estés y
                        más información registres, mejores ajustes podremos ofrecerte cada vez
                        que toque revisar tus macros.
                        {entrega?.proxima_revision && (
                            <span className="block mt-1.5 text-foreground font-semibold" data-testid="proxima-revision">
                                {`Próxima revisión${entrega?.revision_en_dias ? ` en ${Math.round(entrega.revision_en_dias / 7)} semana${Math.round(entrega.revision_en_dias / 7) === 1 ? '' : 's'}` : ''}: ${entrega.proxima_revision}.`}
                            </span>
                        )}
                    </p>
                )}
                {m ? (
                    /* Punto 13 del doc del 07-08: los números tienen que verse enteros sin
                       mover nada. Es el momento más importante del alta y antes había que
                       bajar para llegar a ellos, así que todo lo de esta pantalla va apretado
                       (títulos más pequeños, menos aire entre bloques) para que las tres
                       tarjetas y los botones entren de una vez. */
                    <div className="space-y-3">
                        <div className="grid grid-cols-3 gap-2 sm:gap-3 text-center">
                            {[
                                ['Día de entreno', m.entreno.proteina, m.entreno.hidratos, m.entreno.grasa],
                                ['Perientreno', m.perientreno.proteina, m.perientreno.hidratos, null],
                                ['Día de descanso', m.descanso.proteina, m.descanso.hidratos, m.descanso.grasa],
                            ].map(([lbl, p, h, g]) => (
                                <div key={lbl} className="rounded-xl border-2 border-[#222222] bg-card py-3 px-2">
                                    <p className="text-[10px] sm:text-[11px] text-foreground/50 uppercase font-bold mb-1.5 leading-tight">{lbl}</p>
                                    <p className="font-heading font-extrabold text-xl sm:text-2xl text-brand">{p}<span className="text-foreground/40 text-sm sm:text-base">P</span></p>
                                    <p className="font-heading font-extrabold text-xl sm:text-2xl text-brand">{h}<span className="text-foreground/40 text-sm sm:text-base">H</span></p>
                                    {g != null && <p className="font-heading font-extrabold text-xl sm:text-2xl text-brand">{g}<span className="text-foreground/40 text-sm sm:text-base">G</span></p>}
                                </div>
                            ))}
                        </div>
                        {/* Las etiquetas de colores del desglose («Otro deporte +20 %»,
                            «Engordas enseguida: sin subidas»...) SE VAN de esta pantalla
                            (doc del 23-08, punto 17: «sobra»). El desglose sigue vivo en
                            la calculadora de macros, que es pantalla de trabajo. */}
                        {resultado.revision?.requiere_revision && (
                            <p className="text-xs text-amber-500 font-medium">
                                Lo que comes ahora no cuadra con lo esperado para tu % graso: el equipo lo revisará.
                            </p>
                        )}
                    </div>
                ) : (
                    <p className="text-foreground/60">Tus macros se han guardado y los verás en tu panel.</p>
                )}

                {/* EL TEXTO DE CIERRE DEL TEST, literal del documento de Jesús del 06-08 y
                    DEBAJO DE LOS NÚMEROS, que es donde él lo pide (punto 4.1). Solo para los
                    planes con entrenador: es a ellos a quienes les queda una revisión. */}
                {entrega?.con_entrenador && (
                    <div className="mt-4 rounded-xl border border-brand/30 bg-brand/5 p-3" data-testid="cierre-del-test">
                        {/* El texto del doc del 23-08 (punto 23), literal. */}
                        <p className="text-sm text-foreground/80">
                            Recuerda que son provisionales: en menos de 48 horas revisamos tus
                            respuestas y terminamos de ajustarlos. Mientras tanto, ya puedes
                            empezar a crear tu día.
                        </p>
                    </div>
                )}

                {/* MOMENTO 1 de la revisión suelta (documento del 06-08-2026): al recibir sus
                    macros de inicio. Línea pequeña y sin botón, nunca un popup: si interrumpe,
                    es publicidad aunque el texto sea suave. */}
                {modoAjuste && !entrega?.con_entrenador && seLeOfreceLaRevision(profile, can) && (
                    <p className="text-xs text-foreground/50 mt-4" data-testid="revision-partida">
                        Si consideras que tu caso necesita una revisión más profunda, puedes{' '}
                        <button onClick={() => navigate('/dashboard/revision')}
                            className="underline text-brand hover:text-brand/80 font-medium">
                            solicitar tu revisión de partida
                        </button>.
                    </p>
                )}

                {/* Y el día de hoy, ya montado. Termina el alta con comida puesta y no con
                    una pantalla en blanco, que es donde se cae la gente: montar la primera
                    dieta desde cero sin conocer la app no lo hace casi nadie. Lo que acepte o
                    cambie de aquí es además lo que nos va diciendo qué le gusta, sin tener
                    que preguntárselo. */}
                {diaMontado?.montadas?.length > 0 && (
                    <div className="mt-5 rounded-xl border border-border bg-muted/30 p-4" data-testid="primer-dia-montado">
                        <p className="text-sm font-semibold text-foreground mb-1">
                            Y tu día de hoy ya está creado
                        </p>
                        <p className="text-xs text-foreground/50 mb-3">
                            Cuadrado a estos macros. Cámbialo a tu gusto: así aprendemos qué te gusta.
                        </p>
                        <ul className="space-y-1">
                            {diaMontado.montadas.map(m => (
                                <li key={m.comida} className="flex gap-2 text-sm">
                                    <span className="text-foreground/40 font-semibold w-14 flex-shrink-0">
                                        {m.comida.replace('C', 'Comida ')}
                                    </span>
                                    <span className="text-foreground/80 truncate">{m.menu}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Un solo botón: el recorrido continúa donde estaba. Antes, al venir del
                    alta, aquí se le mandaba a un SEGUNDO cuestionario ("Ajustar mis macros");
                    ya no hay segundo cuestionario que ofrecer. */}
                <div className="flex flex-col sm:flex-row gap-3 mt-5">
                    <Button onClick={goNext}
                        className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-5 text-base">
                        Continuar <ArrowRight className="w-5 h-5 ml-2" />
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'momento') {
        // Opciones adaptadas al nº de comidas elegido (coloca el perientreno).
        const n = answers.pref_num_comidas || 4;
        const opciones = [{ value: 0, label: 'En ayunas, antes de la primera comida' }];
        for (let i = 1; i <= Math.min(3, n - 1); i++) {
            opciones.push({ value: i, label: `Después de la comida ${i}` });
        }
        body = (
            <div>
                <Title />
                <div className="space-y-3">
                    {opciones.map(o => (
                        <button key={o.value} onClick={() => pickChoice(o.value)}
                            className={`w-full text-left px-5 py-4 rounded-xl border-2 transition-all ${answers[step.key] === o.value ? 'border-[#FF671F] bg-[#FF671F]/10' : 'border-[#222222] hover:border-white/30'} text-foreground`}>
                            {o.label}
                        </button>
                    ))}
                </div>
                <div className="mt-6"><BackBtn /></div>
            </div>
        );
    } else if (step.type === 'prefs') {
        // Selector completo de alimentos (mostrar + evitar): mismo componente que
        // "Mis preferencias" de Nutrición; al guardar, sigue el flujo.
        // DENTRO DEL MARCO (hallazgo del mapeo del 23-08): esto hacía `return` a secas y
        // era la única pantalla del alta sin barra de progreso ni logo, como si el
        // cliente se hubiera salido del cuestionario a mitad.
        body = (
            <PreferencesSetup
                api={fetchApi}
                initialPreferences={[]}
                initialAvoidedCategories={[]}
                initialAvoidedKeywords={[]}
                onSave={() => goNext()}
            />
        );
    } else if (step.type === 'magia') {
        // Momento mágico: comida real, suya, que ya cuadra. Cierra con comida,
        // no con un tutorial.
        // ÚLTIMA ES LA ÚLTIMA, no «la del que no lleva entrenador» (18-08). Esto estaba
        // atado al plan, y desde que el final se parte por plan al que no lleva entrenador
        // le quedan dos pantallas detrás -- las fotos y la oferta --, así que el botón decía
        // «Ir a mi panel» y se las saltaba las dos. Se vio recorriendo el alta entera con una
        // cuenta de dev; por API no se ve, porque el recorrido lo compone la pantalla.
        const esUltimo = idx >= flow.length - 1;
        // «Sin el CUADRA CONTIGO en verde: eso fuera» (doc 23-08). Y los menús ya no son
        // recetas sueltas: son mañana y pasado, escritos, con sus comidas.
        const nombreComida = (k) => (k.toLowerCase().startsWith('peri') ? 'Perientreno' : k.replace('C', 'Comida '));
        body = (
            <div>
                <h2 className="font-heading font-bold text-2xl md:text-3xl text-foreground mb-2 leading-tight">
                    Ahora, una muestra de lo que podrías comer con estos macros
                </h2>
                <p className="font-semibold text-foreground mb-1">Dos menús para empezar.</p>
                <p className="text-foreground/60 mb-5 text-sm md:text-base">
                    Mañana y pasado tienes dos menús con las cantidades ajustadas a tus macros,
                    para que los tengas de referencia (puedes cambiar lo que quieras).
                </p>
                {diasArranque === null ? (
                    <div className="flex justify-center py-10">
                        <div className="animate-spin rounded-full h-9 w-9 border-4 border-brand border-t-transparent" />
                    </div>
                ) : diasArranque.length === 0 ? (
                    <p className="text-foreground/60 text-sm mb-4">
                        El recetario te espera en <span className="font-bold text-foreground">Nutrición</span>:
                        en cada comida, pulsa "Sugiéreme un menú" y elige la receta que te apetezca.
                    </p>
                ) : (
                    <div className="space-y-3 mb-2 max-h-[46vh] overflow-y-auto pr-1" data-testid="menus-arranque">
                        {diasArranque.map((dia, i) => (
                            <div key={dia.fecha} className="rounded-xl border-2 border-[#222222] bg-card p-4">
                                <div className="flex items-baseline justify-between gap-2 mb-2">
                                    <p className="text-base font-black text-foreground">
                                        Menú {i + 1} · {i === 0 ? 'mañana' : 'pasado mañana'}
                                    </p>
                                    <span className="text-[10px] uppercase tracking-wider text-foreground/40 font-bold">
                                        {dia.tipo_dia === 'descanso' ? 'Día de descanso' : 'Día de entreno'}
                                    </span>
                                </div>
                                <div className="space-y-2">
                                    {Object.entries(dia.comidas || {})
                                        .filter(([, v]) => (v.alimentos || []).length)
                                        .sort(([a], [b]) => a.localeCompare(b))
                                        .map(([k, v]) => (
                                            <div key={k}>
                                                <p className="text-sm text-foreground">
                                                    <span className="text-foreground/40 font-semibold">{nombreComida(k)}</span>
                                                    {v.menu_nombre && <span className="font-semibold"> · {v.menu_nombre}</span>}
                                                </p>
                                                <p className="text-xs text-foreground/60">
                                                    {(v.alimentos || []).map(a =>
                                                        `${Math.round(a.cantidad_g || 0)} g ${a.nombre}`).join(' · ')}
                                                </p>
                                            </div>
                                        ))}
                                </div>
                            </div>
                        ))}
                        <p className="text-xs text-foreground/50">
                            Los tienes puestos en Nutrición, en su día. Y el recetario entero en
                            "Sugiéreme un menú" de cada comida.
                        </p>
                    </div>
                )}
                <div className="flex gap-3 mt-6">
                    {esUltimo ? (
                        <Button onClick={() => navigate('/welcome')} data-testid="empezar-menu-1"
                            className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                            Empezar con el menú 1 <ArrowRight className="w-5 h-5 ml-2" />
                        </Button>
                    ) : (
                        <Button onClick={goNext} data-testid="empezar-menu-1"
                            className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                            {diasArranque?.length ? 'Empezar con el menú 1' : 'Continuar'} <ArrowRight className="w-5 h-5 ml-2" />
                        </Button>
                    )}
                </div>
            </div>
        );
    } else if (step.type === 'contacto') {
        // PANTALLA 1 DEL BÁSICO: cinco campos juntos, que es la excepción que hace el
        // propio documento a lo de una pregunta por pantalla. El nombre y el sexo solo se
        // piden si no vienen del pago; el resto siempre.
        const faltaNombre = !user?.name;
        const faltaSexo = !profile?.sex;
        const listo = answers.birthdate && answers.phone && answers.email
            && (!faltaNombre || answers.name) && (!faltaSexo || answers.sex);
        body = (
            <div>
                <Title />
                <div className="space-y-4 mb-8">
                    {faltaNombre && (
                        <MiniInput {...mini} k="name" label="Nombre completo" />
                    )}
                    {faltaSexo && (
                        <div>
                            <p className="text-sm text-foreground/60 mb-2">Hombre o mujer</p>
                            <div className="grid grid-cols-2 gap-3">
                                {[['hombre', 'Hombre'], ['mujer', 'Mujer']].map(([v, etiqueta]) => (
                                    <button key={v} onClick={() => set('sex', v)}
                                        className={`px-5 py-3 rounded-xl border-2 transition-all ${
                                            answers.sex === v
                                                ? 'border-[#FF671F] bg-[#FF671F]/10 text-foreground'
                                                : 'border-[#222222] hover:border-white/30 text-foreground'}`}>
                                        {etiqueta}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}
                    <MiniInput {...mini} k="birthdate" label="Fecha de nacimiento" type="date"
                        placeholder="La verdadera, no me engañes." />
                    <MiniInput {...mini} k="phone" label="Teléfono" type="tel"
                        placeholder="Un whatsapp de contacto." />
                    <MiniInput {...mini} k="email" label="Email" type="email"
                        placeholder="Uno que revises a diario." />
                    <p className="text-xs text-foreground/50">
                        Si pagaste con otro email distinto, no pasa nada: seguirás entrando con el
                        de siempre, pero te escribiremos a este, salvo que nos digas lo contrario.
                    </p>
                </div>
                <Button onClick={goNext} disabled={!listo}
                    className="bg-brand hover:bg-brand/90 text-white font-bold px-8 disabled:opacity-40">
                    Seguir <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
            </div>
        );
    } else if (step.type === 'ocupacion') {
        // PANTALLA 12: la profesión y el sedentarismo, juntas, CADA UNA CON SU ETIQUETA
        // (punto 5 del doc del 23-08). Y el candado de la regla 1: marcar la opción de
        // abajo NO puede saltar a la siguiente sin recoger la de arriba, que era
        // exactamente lo que pasaba y por lo que se perdía «¿A qué te dedicas?».
        const actividad = q('actividad_diaria');
        const sinProfesion = !(answers.profesion || '').trim();
        const listo = !sinProfesion && !!answers.actividad_diaria;
        body = (
            <div>
                <h2 className="font-heading font-bold text-2xl md:text-3xl text-foreground mb-4 leading-tight">¿A qué te dedicas?</h2>
                <div className="mb-8">
                    <Input value={answers.profesion ?? ''} onChange={e => set('profesion', e.target.value)}
                        placeholder="Escribe tu respuesta..." data-testid="ocupacion-profesion"
                        className="text-lg py-6 bg-card border-[#222222]" />
                </div>
                <h2 className="font-heading font-bold text-2xl md:text-3xl text-foreground mb-2 leading-tight">¿Cuánto te mueves en tu día a día?</h2>
                <p className="text-sm text-foreground/60 mb-4">{actividad.desc}</p>
                <div className="space-y-3">
                    {actividad.options.map(o => (
                        <button key={o.value}
                            onClick={() => {
                                set('actividad_diaria', o.value);
                                trasResponder('actividad_diaria', o.value);
                                // Solo avanza si la de arriba está recogida; si no, se queda
                                // con la opción marcada y el aviso de abajo se lo dice.
                                if ((answersRef.current.profesion || '').trim()) goNext();
                            }}
                            className={`w-full text-left px-5 py-4 rounded-xl border-2 transition-all ${
                                answers.actividad_diaria === o.value
                                    ? 'border-[#FF671F] bg-[#FF671F]/10'
                                    : 'border-[#222222] hover:border-white/30'} text-foreground`}>
                            {o.label}
                        </button>
                    ))}
                </div>
                {!!answers.actividad_diaria && sinProfesion && (
                    <p className="text-sm text-amber-500 mt-4" data-testid="falta-profesion">
                        Te falta la primera: dinos a qué te dedicas y seguimos.
                    </p>
                )}
                <div className="flex gap-3 mt-6">
                    <BackBtn />
                    <Button onClick={goNext} disabled={!listo} data-testid="ocupacion-ok"
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8 disabled:opacity-40">
                        OK <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'peso_hito') {
        // PANTALLAS 9, 10 y 11: cada hito de su peso con SU AÑO. Antes eran cuatro casillas
        // sueltas en una sola pantalla, sin años y solo para quien llevaba entrenador: «si
        // viene como "unos 95 hace tres años" no se puede calcular nada con él».
        const kPeso = step.key, kAno = `${step.key}_ano`, kNota = `${step.key}_nota`;
        // El año, EN BLANCO (punto 2 del doc del 23-08): el placeholder «2019» se leía como
        // valor puesto. Y validado: cuatro cifras entre 1940 y el año actual.
        const anoCrudo = `${answers[kAno] ?? ''}`.trim();
        const anoNum = parseInt(anoCrudo, 10);
        const anoMal = anoCrudo !== '' && (isNaN(anoNum) || anoNum < 1940 || anoNum > new Date().getFullYear());
        const hitoListo = !step.required
            || (!avisoDelPaso && `${answers[kPeso] ?? ''}`.trim() !== '' && anoCrudo !== '' && !anoMal);
        body = (
            <div>
                <Title />
                <div className="grid grid-cols-2 gap-4 mb-4">
                    <MiniInput {...mini} k={kPeso} label="Peso" type="number" unit="kg" />
                    <MiniInput {...mini} k={kAno} label="Año" type="number" />
                </div>
                {(avisoDelPaso || anoMal) && (
                    <p className="text-sm text-amber-500 -mt-2 mb-4" data-testid="aviso-del-paso">
                        {avisoDelPaso || 'El año, con sus cuatro cifras.'}
                    </p>
                )}
                <div className="mb-4">
                    <MiniInput {...mini} k={kNota} label={`${step.nota} (opcional)`} placeholder="" />
                </div>
                {step.conFoto && (
                    <div className="mb-6">
                        {/* EL BOTÓN EN ESPAÑOL (doc 23-08, punto 3): el input de fichero
                            crudo pintaba el «Choose File · No file chosen» del navegador. */}
                        <p className="text-sm text-foreground/60 mb-2">
                            Sube la foto de tu mejor forma <span className="text-foreground/40">(opcional)</span>
                        </p>
                        <button type="button" data-testid="foto-mejor-forma"
                            onClick={() => {
                                const input = document.createElement('input');
                                input.type = 'file';
                                input.accept = 'image/*';
                                input.onchange = (ev) => {
                                    const f = ev.target.files?.[0];
                                    if (!f) return;
                                    if (f.size > 8 * 1024 * 1024) { toast.error('La foto pesa demasiado (máximo 8 MB)'); return; }
                                    const reader = new FileReader();
                                    reader.onload = (e) => set('foto_mejor_momento', e.target.result);
                                    reader.readAsDataURL(f);
                                };
                                input.click();
                            }}
                            className="w-full rounded-xl border-2 border-dashed border-[#333] py-6 text-center hover:border-brand transition-colors">
                            <ImagePlus className="w-6 h-6 text-foreground/40 mx-auto mb-1.5" />
                            <span className="text-foreground/60 text-sm">
                                {answers.foto_mejor_momento ? 'Foto lista. Toca para cambiarla' : 'Elegir la foto'}
                            </span>
                        </button>
                    </div>
                )}
                <div className="flex flex-wrap gap-3">
                    <BackBtn />
                    <Button onClick={goNext} disabled={!hitoListo} data-testid="peso-hito-ok"
                        className="bg-brand hover:bg-brand/90 text-white font-bold px-8 disabled:opacity-40">
                        OK <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                    {/* La salida del que no (doc 23-08, punto 3). Y SE APUNTA: «pásala» es
                        una respuesta («no he estado»), no un olvido. Sin la marca, la
                        tarjeta del Inicio y el cuestionario completo se la volvían a pedir
                        como si no hubiera contestado. */}
                    {step.pasala && (
                        <Button variant="ghost" data-testid="peso-hito-pasala"
                            onClick={() => {
                                if (step.key === 'peso_mejor_momento') set('mejor_forma_pasada', true);
                                goNext();
                            }}
                            className="text-foreground/50">
                            Si no, pásala
                        </Button>
                    )}
                </div>
            </div>
        );
    } else if (step.type === 'elegir_perfil') {
        // EL FINAL DE QUIEN LLEVA ENTRENADOR (doc del cuestionario, 18-08). Antes de esto se
        // le metía de cabeza en el cuestionario largo sin preguntarle: veinticinco pantallas
        // más justo cuando acaba de terminar veinticuatro. Ahora elige, y si se va a la
        // calculadora le queda la tarjeta de «Completa tu perfil» en Inicio.
        // LOS TEXTOS DEL DOC DEL 23-08 (punto 24): la pregunta en el título, lo que falta
        // dicho entero, y cada botón con su coletilla. «Lo dejo para luego» deja la
        // tarjeta «Completar perfil» en Inicio (ya existe) y el aviso llega a los 3 días.
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-3 leading-tight">
                    ¿Seguimos ahora o lo dejas para luego?
                </h2>
                <p className="text-foreground/70 mb-4">
                    Nos faltan tus fotos, tus medidas, tus preferencias de comida y unas
                    preguntas más. Sin eso no podemos terminar de ajustarte los macros ni
                    prepararte la rutina.
                </p>
                {/* CON LA FECHA, no con «siempre un lunes» (bloque 6 del doc del 18-08). El
                    lunes de arranque ya está calculado desde que paga. Y nada más
                    (corrección del punto 46 del 19-08): los macros definitivos llegan el
                    miércoles anterior a su lunes y aquí no se promete ninguna otra fecha. */}
                <p className="text-xs text-foreground/50 mb-6">
                    {arranque
                        ? <>Empiezas el <b className="text-foreground/80">lunes {arranque.lunes}</b>.</>
                        : 'Te apuntas cualquier día y empiezas siempre un lunes.'}
                </p>
                {/* CON LA VENTANA CERRADA NO SE LE OFRECE ENTRAR (el reloj del 19-08: el
                    largo abre el viernes a las 10:00 y cierra el lunes a las 18:00). Al
                    que se apunta un martes se le dice cuándo, y su única salida es la
                    calculadora. */}
                {ventanaLargo && !ventanaLargo.abierta && !revision ? (
                    <>
                        <p className="text-sm text-foreground/70 mb-4" data-testid="largo-abre-el">
                            Tu cuestionario se abre el <b className="text-foreground">{ventanaLargo.abre_label}</b> y
                            lo tendrás hasta el {ventanaLargo.cierra_label}, hora de España. Te avisaremos.
                        </p>
                        <Button onClick={() => navigate('/welcome')} data-testid="empezar-calculadora"
                            className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                            Empezar a usar la calculadora <ArrowRight className="w-5 h-5 ml-2" />
                        </Button>
                    </>
                ) : (
                    <div className="space-y-3">
                        <button onClick={goNext} data-testid="terminar-perfil-ahora"
                            className="w-full text-left p-4 rounded-xl border-2 border-brand bg-brand/10 hover:bg-brand/15 transition-all">
                            <span className="font-semibold text-foreground">Seguimos ahora</span>
                            <span className="block text-sm text-foreground/60 italic mt-0.5">En 10 min lo tienes hecho.</span>
                        </button>
                        <button onClick={() => navigate('/welcome')} data-testid="empezar-calculadora"
                            className="w-full text-left p-4 rounded-xl border-2 border-border hover:border-brand/50 transition-all">
                            <span className="font-semibold text-foreground">Lo dejo para luego</span>
                            <span className="block text-sm text-foreground/60 italic mt-0.5">Te lo dejo apuntado en Inicio.</span>
                        </button>
                    </div>
                )}
            </div>
        );
    } else if (step.type === 'tres_cosas') {
        // LA PANTALLA DEL DOC 19-08, con su texto literal. «Lo hago luego» va directo a
        // la oferta de los 87 € y le deja el aviso pendiente de las preferencias.
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-3 leading-tight">
                    Tres cosas y terminamos
                </h2>
                <p className="text-foreground/70 mb-6">
                    Déjalo hecho cuanto antes. Las dos primeras son para que puedas llevar un
                    control objetivo de tus progresos y la tercera nos ayudará a conocerte mejor
                    y ofrecerte las cosas que más te gustan.
                </p>
                <div className="space-y-3 mb-6">
                    {[['1 · Subir tus fotos', 'Frente, espaldas y perfil (elige un perfil y no cambies)'],
                      ['2 · Tomar las medidas', 'Aquí vas a necesitar que te ayude alguien (y si puede ser siempre el mismo, mejor)'],
                      ['3 · Completar las preferencias', 'Sabiendo lo que te gusta, te haremos la dieta más fácil']]
                        .map(([t, d]) => (
                            <div key={t} className="surface p-4">
                                <p className="font-semibold text-foreground">{t}</p>
                                <p className="text-sm text-foreground/50">{d}</p>
                            </div>
                        ))}
                </div>
                <div className="flex flex-col sm:flex-row gap-3">
                    <Button onClick={goNext} data-testid="empezar-por-las-fotos"
                        className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                        Empezar por las fotos <ArrowRight className="w-5 h-5 ml-2" />
                    </Button>
                    <Button variant="outline" onClick={saltarAOferta} data-testid="lo-hago-luego"
                        className="px-8 py-6 text-lg">
                        Lo hago luego
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'fotos_alta') {
        // PASO 1 · Tus fotos, con el texto literal. Se guardan al elegirlas (TresFotos
        // sube cada una al momento), así que salir por aquí no pierde nada.
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-3 leading-tight">
                    Tus fotos
                </h2>
                <p className="text-foreground/70 mb-4 text-sm">
                    Hazlas con buena luz y siempre en el mismo sitio. Solo si haces las fotos en
                    las mismas condiciones podrás ser objetivo a la hora de comparar. Te
                    recomiendo repetirlas cada 4 semanas, que es un tiempo prudencial para
                    apreciar cambios.
                </p>
                <div className="mb-6">
                    <TresFotos api={api} token={token} esMensual={false} />
                </div>
                <div className="flex flex-col sm:flex-row gap-3">
                    <Button onClick={goNext} data-testid="fotos-continuar"
                        className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                        Continuar <ArrowRight className="w-5 h-5 ml-2" />
                    </Button>
                    <Button variant="outline" onClick={saltarAOferta} className="px-8 py-6 text-lg">
                        Lo hago luego
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'medidas_alta') {
        // PASO 2 · Tus medidas. Se guardan al continuar («se guarda al pasar de pantalla,
        // no al final»): quien salga después no las pierde.
        const guardarMedidasAlta = async () => {
            const conValor = Object.fromEntries(
                Object.entries(medidasAlta).filter(([, v]) => v !== '' && v != null));
            if (Object.keys(conValor).length) {
                try {
                    // Son las medidas del DÍA 1: van al punto de partida (medidas_inicio y
                    // la marca de hecho), no a la serie de Seguimiento. Así la ficha y la
                    // comparativa del mes que viene salen de aquí, y al que vuelva al alta
                    // no se le piden otra vez.
                    await api.post('/clients/punto-de-partida', { medidas: conValor });
                } catch (e) {
                    console.error('[alta] las medidas no se guardaron', e);
                    toast.error('No se pudieron guardar las medidas. Puedes añadirlas después en Seguimiento.');
                }
            }
            goNext();
        };
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-3 leading-tight">
                    Tus medidas
                </h2>
                <p className="text-foreground/70 mb-4 text-sm">
                    Si te puede medir alguien, y siempre el mismo, mejor. Cada 4 semanas. En cm.
                </p>
                <div className="grid grid-cols-2 gap-2 mb-6">
                    {MEDIDAS.map(({ key, label }) => (
                        <label key={key} className="text-xs text-foreground/50">
                            {label}
                            <Input type="number" inputMode="decimal" step="0.5"
                                value={medidasAlta[key] ?? ''} data-testid={`alta-medida-${key}`}
                                onChange={e => setMedidasAlta(m => ({ ...m, [key]: e.target.value }))}
                                className="mt-0.5 bg-card border-[#222222]" />
                        </label>
                    ))}
                </div>
                <div className="flex flex-col sm:flex-row gap-3">
                    <Button onClick={guardarMedidasAlta} data-testid="medidas-continuar"
                        className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                        Continuar <ArrowRight className="w-5 h-5 ml-2" />
                    </Button>
                    <Button variant="outline" onClick={saltarAOferta} className="px-8 py-6 text-lg">
                        Lo hago luego
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'ya_esta_todo') {
        // PASO 4 · después de las preferencias, con el literal del doc del 23-08 (punto
        // 20): «Ya está todo · Este es tu punto de partida», la lista con lo que de
        // verdad ha dejado hecho, la promesa del mes que viene y «Seguir» (detrás va la
        // oferta).
        const nMedidas = Object.values(medidasAlta).filter(v => v !== '' && v != null).length;
        const estadoMedidas = nMedidas > 0 ? `${nMedidas} de ${MEDIDAS.length}`
            : yaTieneMedidas ? 'Guardadas' : 'Pendientes';
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-2 leading-tight">
                    Ya está todo
                </h2>
                <p className="text-foreground/70 mb-6">Este es tu punto de partida.</p>
                <div className="space-y-3 mb-6" data-testid="punto-de-partida-lista">
                    {[['Las tres fotos', yaTieneFotos ? 'Guardadas' : 'Pendientes'],
                      ['Tus medidas', estadoMedidas],
                      ['Tus preferencias', 'Guardadas']]
                        .map(([t, d]) => (
                            <div key={t} className="flex items-start gap-3">
                                <Check className="w-5 h-5 text-brand mt-0.5 shrink-0" />
                                <div>
                                    <p className="font-semibold text-foreground">{t}</p>
                                    <p className="text-sm text-foreground/50">{d}</p>
                                </div>
                            </div>
                        ))}
                </div>
                <p className="text-sm text-foreground/60 mb-8">
                    El mes que viene te pedimos las siguientes y las vas a ver al lado de estas.
                </p>
                <Button onClick={goNext} data-testid="ir-a-mi-panel"
                    className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                    Seguir <ArrowRight className="w-5 h-5 ml-2" />
                </Button>
            </div>
        );
    } else if (step.type === 'fotos_medidas') {
        // Y EL DE QUIEN NO LO LLEVA. Sin fotos ni medidas no tiene evolución que mirar, que
        // es lo que le hace volver. No se le obliga: se le dice y se le deja ir.
        //
        // Y SE CUENTA LO QUE DE VERDAD LE FALTA. Las medidas se piden dos pantallas antes,
        // en «Ya tienes tus macros», así que a quien las acaba de apuntar decirle «te quedan
        // dos cosas» y pedirle las medidas otra vez es tratarle como si no hubiera hecho
        // nada. Si ya están, lo que le queda es una: las fotos.
        // SE CUENTA LO QUE DE VERDAD LE FALTA, mirando las dos cosas. Antes solo miraba las
        // medidas, así que a quien ya había subido sus fotos se le seguía diciendo «sube tus
        // fotos y toma tus medidas»: pedirle lo que acaba de dar. Si ya tiene las dos, esta
        // pantalla ni sale (ver `visible`).
        //
        // Y EL DEL QUE SÍ LLEVA ENTRENADOR (pantalla 25, el cierre del completo). Ahí la
        // razón no es que él vea su evolución: es que su entrenador no puede trabajar sin
        // esto. Se le dice tal cual, porque es la verdad y porque es lo que le mueve.
        const leFalta = [!yaTieneFotos && 'tus fotos', !yaTieneMedidas && 'tus medidas']
            .filter(Boolean);
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-3 leading-tight">
                    {step.obligatorio
                        ? 'Tus fotos y tus medidas'
                        : leFalta.length === 2 ? 'Te quedan dos cosas' : 'Te queda una cosa'}
                </h2>
                <p className="text-foreground/70 mb-6">
                    {step.obligatorio
                        ? 'Es lo último, y hace falta para arrancar: sin fotos y sin medidas tu entrenador no puede ponerte los macros buenos ni crearte la rutina. Si te puede medir alguien, y siempre el mismo, mejor.'
                        : leFalta.length === 2
                            ? 'Sube tus fotos y toma tus medidas. Sin eso no puedes ver tu evolución, que es lo que de verdad enseña lo que cambia.'
                            : `Te faltan ${leFalta[0] || 'un par de cosas'}. Con eso ya puedes ver tu evolución, que es lo que de verdad enseña lo que cambia.`}
                </p>
                <div className="flex flex-col sm:flex-row gap-3">
                    <Button data-testid="ir-a-fotos-medidas" disabled={loading}
                        onClick={() => (step.obligatorio
                            ? submitNivel1('/dashboard/reports')
                            : navigate('/dashboard/reports'))}
                        className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                        {loading ? 'Guardando...' : 'Vamos'} <ArrowRight className="w-5 h-5 ml-2" />
                    </Button>
                    {/* «Ahora no» NUNCA deja clavado: si esta es la última pantalla del
                        recorrido, `goNext` se queda donde está -- se topa con el final de la
                        lista -- y la única salida era el botón de atrás del navegador. */}
                    <Button variant="outline" disabled={loading} className="px-8 py-6 text-lg"
                        onClick={() => (idx >= flow.length - 1 ? navigate('/welcome') : goNext())}>
                        Ahora no
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'oferta_ajuste') {
        // LA OFERTA DE LOS 87 €, CON SU TEXTO LITERAL. Todavía no cobra: el documento deja sin
        // decidir cómo se cobra, así que se apunta lo que contesta -- el sí y el no, que
        // saber cuánta gente lo rechaza vale igual -- y el equipo lo ve en su campana.
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-4 leading-tight">
                    Una cosa más
                </h2>
                <p className="text-foreground/80 mb-3 leading-relaxed">
                    Puedes continuar con tu plan actual y empezar a usar la calculadora con unos
                    macros ajustados según tu perfil y teniendo en cuenta la evolución de otras
                    personas con un perfil parecido al tuyo que ya han pasado por aquí, o puedes
                    solicitar tus macros personalizados y recibir tu ajuste a medida.
                </p>
                <p className="text-sm text-foreground/50 italic mb-6">
                    (Esta segunda opción no está incluida en tu plan, tiene un coste adicional e
                    incluye también tu plan personalizado de suplementación.)
                </p>
                <div className="space-y-3">
                    <button data-testid="oferta-no" disabled={loading}
                        onClick={() => responderOferta(false)}
                        className="w-full text-left p-4 rounded-xl border-2 border-border hover:border-brand/50 transition-all disabled:opacity-50">
                        <span className="font-semibold text-foreground">
                            Me vale con la primera opción, la que está incluida en mi plan
                        </span>
                    </button>
                    <button data-testid="oferta-si" disabled={loading}
                        onClick={() => responderOferta(true)}
                        className="w-full text-left p-4 rounded-xl border-2 border-border hover:border-brand transition-all disabled:opacity-50">
                        <span className="font-semibold text-foreground">
                            Quiero el ajuste a medida, aunque implique pagar más
                        </span>
                        <span className="block text-sm text-brand font-bold mt-1">
                            87 € · macros personalizados + programa de suplementación
                        </span>
                    </button>
                </div>
            </div>
        );
    } else if (step.type === 'dieta') {
        // P10 del doc: tres formas de meter la dieta y CONFIRMACIÓN OBLIGATORIA. El cliente no
        // calcula nada: cuenta lo que come y le devolvemos lo que hemos entendido. Sin su
        // confirmación el dato no entra en el cálculo, porque manda sobre todo lo demás.
        body = (
            <div>
                <Title />

                {!lecturaDieta ? (
                    <div className="space-y-4 mb-6">
                        {/* DOS PUERTAS, NO TRES (doc del 23-08, punto 10): «Un día mío» se
                            quita. Era elegir un día ya creado en la calculadora, y quien
                            está en el alta no tiene ninguno. */}
                        <div className="grid grid-cols-2 gap-2">
                            {[['texto', 'Escribirla'], ['foto', 'Una foto']].map(([modo, etiqueta]) => (
                                <button key={modo} onClick={() => set('dieta_modo', modo)}
                                    className={`px-3 py-2.5 rounded-xl border-2 text-sm font-semibold transition-all ${
                                        (answers.dieta_modo || 'texto') === modo
                                            ? 'border-brand bg-brand/10 text-foreground'
                                            : 'border-[#222222] text-foreground/60 hover:border-white/30'}`}>
                                    {etiqueta}
                                </button>
                            ))}
                        </div>

                        {(answers.dieta_modo || 'texto') === 'texto' && (
                            <textarea value={answers.dieta_texto ?? ''} onChange={e => set('dieta_texto', e.target.value)}
                                rows={5} placeholder="Un día tipo, con cantidades. Por ejemplo: desayuno 80 g de avena y 30 g de proteína; comida 200 g de pollo con 100 g de arroz; cena merluza con ensalada."
                                className="w-full rounded-xl bg-card border-2 border-[#222222] p-3 text-foreground text-sm resize-none focus:outline-none focus:border-brand" />
                        )}

                        {answers.dieta_modo === 'foto' && (
                            <div>
                                <button onClick={elegirFotoDieta}
                                    className="w-full rounded-xl border-2 border-dashed border-[#333] py-8 text-center hover:border-brand transition-colors">
                                    <ImagePlus className="w-7 h-7 text-foreground/40 mx-auto mb-2" />
                                    <span className="text-foreground/60 text-sm">
                                        {answers.dieta_imagen ? 'Foto elegida. Toca para cambiarla' : 'Sube la foto de tu dieta'}
                                    </span>
                                </button>
                            </div>
                        )}

                        <div className="flex flex-wrap gap-3">
                            <BackBtn />
                            <Button onClick={leerMiDieta} disabled={leyendoDieta}
                                className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8">
                                {leyendoDieta ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Leyendo...</> : <>Calcular <ArrowRight className="w-4 h-4 ml-2" /></>}
                            </Button>
                            <Button variant="ghost" onClick={goNext} className="text-foreground/50">
                                No lo sé, sáltalo
                            </Button>
                        </div>
                    </div>
                ) : (
                    /* Lo que hemos entendido, para que lo confirme */
                    <div className="space-y-4 mb-6">
                        <div className="rounded-xl border-2 border-brand/40 bg-brand/5 p-5">
                            {/* PROTEÍNA · HIDRATOS · GRASA, como en toda la app (punto 18 del
                                17-08). Aquí iba hidratos primero, y es la única pantalla que lo
                                hacía: la tabla de macros de dos pasos después, las tarjetas de
                                comida, la cabecera del día y el asistente van todos en el orden
                                del método. */}
                            <p className="text-foreground text-base mb-3">
                                He entendido que estás comiendo{' '}
                                <strong className="text-brand">{lecturaDieta.macros.proteina} g de proteína</strong>,{' '}
                                <strong className="text-brand">{lecturaDieta.macros.hidratos} g de hidratos</strong> y{' '}
                                <strong className="text-brand">{lecturaDieta.macros.grasa} g de grasa</strong>. ¿Es correcto?
                            </p>
                            {/* QUÉ PIDIÓ Y QUÉ HEMOS COGIDO (punto 17 del 17-08). Decía solo
                                «250 g · Leche desnatada» cuando el cliente había escrito
                                «leche»: la variante la elegimos nosotros y él no tenía forma de
                                verlo ni de corregirlo. El backend ya devuelve `pedido`. */}
                            <ul className="text-xs text-foreground/50 space-y-0.5 max-h-40 overflow-y-auto">
                                {lecturaDieta.alimentos.map((a, i) => (
                                    <li key={i}>
                                        {a.cantidad_g} g{a.cantidad_asumida && <span className="text-foreground/35"> (a ojo)</span>} · {a.nombre}
                                        {a.pedido && a.nombre
                                            && !a.nombre.toLowerCase().startsWith(String(a.pedido).toLowerCase())
                                            && <span className="text-foreground/35"> · tú dijiste «{a.pedido}»</span>}
                                    </li>
                                ))}
                            </ul>
                            {lecturaDieta.no_reconocidos?.length > 0 && (
                                <p className="text-xs text-amber-500 mt-2">
                                    No hemos reconocido: {lecturaDieta.no_reconocidos.join(', ')}
                                </p>
                            )}
                        </div>
                        <div className="flex flex-wrap gap-3">
                            <Button onClick={confirmarDieta}
                                className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8">
                                Sí, es correcto <ArrowRight className="w-4 h-4 ml-2" />
                            </Button>
                            <Button variant="outline" onClick={() => setLecturaDieta(null)}
                                className="border-[#333] text-foreground">
                                No, corregir
                            </Button>
                        </div>
                    </div>
                )}
            </div>
        );
    } else if (step.type === 'partida') {
        // Las medidas del día 1. Las fotos ya NO se piden aquí: van con el reporte (punto 19
        // del doc del 07-08), que es donde el cliente entiende para qué son.
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-2 leading-tight">
                    Ya tienes tus macros
                </h2>
                <p className="text-foreground/60 mb-6 text-sm md:text-base">
                    Apunta tus medidas de hoy para poder comparar más adelante. Las fotos te las
                    pediremos en tu primer reporte, con las poses explicadas.
                </p>

                <div className="space-y-4 mb-6">
                    {/* Las MISMAS diez que en el reporte, para que la del día 1 se pueda
                        comparar con la del mes que viene. Antes aquí se pedían cuatro
                        (cintura, abdomen, cadera y la altura), en el check-in cinco y en el
                        reporte otras cinco: tres listas distintas y ninguna comparable. */}
                    <div>
                        <label className="block text-xs font-bold text-foreground/50 uppercase tracking-wider mb-2">
                            Tus medidas de hoy
                        </label>
                        <div className="rounded-xl overflow-hidden bg-black mb-3" style={{ aspectRatio: '16 / 9' }}>
                            <iframe src={VIDEO_MEDIDAS} title="Cómo medir los perímetros"
                                allow="fullscreen; picture-in-picture" className="w-full h-full border-0" />
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                            {MEDIDAS.map(({ key, label }) => (
                                <MiniInput key={key} {...mini} k={`medida_${key}`} label={label}
                                    type="number" unit="cm" placeholder="--" />
                            ))}
                        </div>
                    </div>

                    {/* La altura es un dato FIJO, no una medida de seguimiento: va aparte y
                        solo si todavía no la ha dado. */}
                    {!answers.height && (
                        <div className="max-w-[10rem]">
                            <MiniInput {...mini} k="height" label="Tu altura" type="number" unit="cm" placeholder="178" />
                        </div>
                    )}
                </div>

                <div className="flex flex-wrap gap-3">
                    <Button onClick={guardarPuntoDePartida}
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8">
                        Ver mi ficha <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                    <Button variant="ghost" onClick={goNext} className="text-foreground/50">
                        Ahora no
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'ficha') {
        // Lo que se le da a cambio: de que esta hecho y que le paso a gente como el.
        const c = ficha?.composicion;
        const r = ficha?.referencia;
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-2 leading-tight">
                    Tu punto de partida
                </h2>
                <p className="text-foreground/60 mb-6 text-sm md:text-base">
                    De aquí sales hoy. Dentro de un mes lo comparamos con esto.
                </p>

                {!ficha ? (
                    <div className="flex justify-center py-10">
                        <Loader2 className="w-8 h-8 animate-spin text-brand" />
                    </div>
                ) : (
                    <div className="space-y-4">
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                            {[['Peso', `${c.peso} kg`], ['Grasa', `${c.masa_grasa} kg`],
                              ['Masa magra', `${c.masa_magra} kg`]].map(([lbl, val]) => (
                                <div key={lbl} className="rounded-xl border-2 border-[#222222] bg-card py-4 px-3 text-center">
                                    <p className="text-[11px] text-foreground/50 uppercase font-bold mb-1">{lbl}</p>
                                    <p className="font-heading font-extrabold text-2xl text-brand">{val}</p>
                                </div>
                            ))}
                        </div>

                        {c.indice_muscular != null ? (
                            <div className="rounded-xl border-2 border-brand/40 bg-brand/5 p-4">
                                <p className="text-[11px] text-foreground/50 uppercase font-bold mb-1">Índice de muscularidad</p>
                                <p className="font-heading font-extrabold text-3xl text-brand mb-1">{c.indice_muscular}</p>
                                <p className="text-sm text-foreground/70">
                                    Músculo que llevas para tu altura: <strong className="text-foreground">{c.indice_muscular_lectura}</strong>.
                                </p>
                            </div>
                        ) : (
                            <p className="text-foreground/50 text-sm">
                                Dinos tu altura y te calculamos cuánto músculo llevas para tu estatura.
                            </p>
                        )}

                        {r && (
                            <div className="rounded-xl border-2 border-[#222222] bg-card p-4">
                                <p className="text-[11px] text-foreground/50 uppercase font-bold mb-1">Gente que empezó como tú</p>
                                <p className="text-sm text-foreground/80">
                                    De {r.casos} casos parecidos al tuyo, <strong className="text-foreground">{r.avanzaron} avanzaron</strong>,
                                    y los que avanzaron se movieron{' '}
                                    <strong className="text-brand">{r.kg_mes} kg al mes</strong>{' '}
                                    ({r.ritmo_mediano_pct_mes}% de su peso).
                                </p>
                                <p className="text-xs text-foreground/40 mt-1">
                                    No es un objetivo ni una promesa: es lo que les pasó de verdad, y ya ves
                                    que no le sale a todo el mundo.
                                </p>
                            </div>
                        )}
                    </div>
                )}

                <div className="mt-8">
                    <Button onClick={goNext} className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                        Continuar <ArrowRight className="w-5 h-5 ml-2" />
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'exclusiones') {
        body = (
            <div>
                <Title />
                <ExclusionesDelAlta answers={answers} set={set} api={api} />
                <div className="flex gap-3 mt-6">
                    <BackBtn />
                    <Button onClick={goNext} data-testid="exclusiones-ok"
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8">
                        OK <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'multiselect') {
        // NO REVIENTA CON FICHAS ANTIGUAS (doc 23-08, punto 15; la causa real del «botón
        // de confirmar que a veces no responde»): `alergias` puede llegar como STRING de
        // los cuestionarios viejos, y `selected.filter` sobre un string tiraba un
        // TypeError que dejaba la pantalla muerta. Se normaliza: del texto se rescatan
        // las opciones que nombre, y a partir de ahí ya es una lista normal.
        const crudo = answers[step.key];
        const selected = Array.isArray(crudo) ? crudo
            : (typeof crudo === 'string' && crudo)
                ? step.options.map(o => o.value).filter(v => crudo.toLowerCase().includes(String(v).toLowerCase()))
                : [];
        // «No, ninguna» ES EXCLUYENTE (mismo punto): marcarla desmarca el resto, y marcar
        // cualquier otra la desmarca a ella. Antes se podía tener «ninguna» + «lactosa» a
        // la vez, que no significa nada.
        const excluyente = step.key === 'alergias' ? 'ninguna' : null;
        const toggle = (v) => {
            let next;
            if (selected.includes(v)) next = selected.filter(x => x !== v);
            else if (excluyente && v === excluyente) next = [v];
            else next = [...selected.filter(x => x !== excluyente), v];
            set(step.key, next);
        };
        body = (
            <div>
                <Title />
                <div className="space-y-3">
                    {step.options.map(o => {
                        const on = selected.includes(o.value);
                        return (
                            <button key={o.value} onClick={() => toggle(o.value)}
                                className={`w-full text-left px-5 py-4 rounded-xl border-2 transition-all flex items-center justify-between ${on ? 'border-[#FF671F] bg-[#FF671F]/10' : 'border-[#222222] hover:border-white/30'} text-foreground`}>
                                {o.label}
                                {on && <Check className="w-5 h-5 text-brand" />}
                            </button>
                        );
                    })}
                </div>
                {/* El botón apagado tiene que decir por qué: sin esto se percibía como
                    «no responde» (doc 23-08, punto 15). */}
                {!selected.length && (
                    <p className="text-sm text-foreground/50 mt-4" data-testid="multiselect-pista">
                        Marca al menos una opción para seguir.
                    </p>
                )}
                <div className="flex gap-3 mt-6">
                    <BackBtn />
                    <Button onClick={goNext} disabled={!selected.length}
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8">
                        OK <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'choice') {
        const opts = step.confirm ? confirmOptions() : segunRespuestas(step.options);
        body = (
            <div>
                <Title />
                <div className="space-y-3">
                    {opts.map(o => {
                        const selected = !step.confirm && answers[step.key] === o.value;
                        return (
                            <button key={String(o.value)} onClick={() => pickChoice(o.value)}
                                className={`w-full text-left px-5 py-4 rounded-xl border-2 transition-all ${selected ? 'border-[#FF671F] bg-[#FF671F]/10' : 'border-[#222222] hover:border-white/30'} text-foreground`}>
                                {o.label}
                            </button>
                        );
                    })}
                </div>
                <div className="mt-6"><BackBtn /></div>
            </div>
        );
    } else if (step.type === 'biotype_intro') {
        body = (
            <div>
                <Title />
                <div className="space-y-3 max-h-[52vh] overflow-y-auto pr-1">
                    {BIOTIPOS.map((b, n) => (
                        <div key={b.value} className="flex gap-4 p-3 rounded-xl border-2 border-[#222222]">
                            <img src={b.img} alt={b.label} loading="lazy"
                                className="w-20 h-24 object-cover rounded-lg flex-shrink-0 bg-card" />
                            <div>
                                <p className="font-bold text-foreground">{n + 1}. {b.label}</p>
                                <p className="text-foreground/50 text-sm mt-1">{b.desc}</p>
                            </div>
                        </div>
                    ))}
                </div>
                <div className="flex gap-3 mt-6">
                    <BackBtn />
                    <Button onClick={goNext} className="bg-brand hover:bg-brand/90 text-white font-bold px-8">
                        Elegir mi biotipo <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'biotype') {
        body = (
            <div>
                <Title />
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[58vh] overflow-y-auto pr-1">
                    {BIOTIPOS.map(b => {
                        const selected = answers.biotype === b.value;
                        return (
                            <button key={b.value} onClick={() => { set('biotype', b.value); setTimeout(goNext, 150); }}
                                className={`rounded-xl border-2 overflow-hidden transition-all text-left ${selected ? 'border-brand ring-2 ring-brand/40' : 'border-[#222222] hover:border-white/30'}`}>
                                <img src={b.img} alt={b.label} loading="lazy"
                                    className="w-full aspect-[3/4] object-cover bg-card" />
                                <p className={`px-2 py-2 text-xs font-bold ${selected ? 'text-brand' : 'text-foreground'}`}>{b.label}</p>
                            </button>
                        );
                    })}
                </div>
                <div className="mt-6"><BackBtn /></div>
            </div>
        );
    } else if (step.type === 'bf') {
        // LOS DOS HUECOS DEBAJO DEL CARRUSEL (doc del 23-08, punto 1): arriba la foto que
        // sube él, debajo la foto tipo del porcentaje en el que se ha quedado, para verse
        // al lado del modelo. En mujer solo el suyo: las fotos de modelo de mujer no
        // existen todavía (duda 1 del plan, pendiente de Jesús).
        const esMujerBf = String(answers.sex || '').toLowerCase().startsWith('muj');
        const valorBf = answers.body_fat;
        body = (
            <div>
                <Title />
                <BodyFatSlider value={answers.body_fat} onChange={(v) => set('body_fat', v)}
                    sexo={answers.sex}
                    photo={answers.foto_grasa || null}
                    onPhoto={(f) => set('foto_grasa', f)} />
                {/* LA COLETILLA CAMBIA SEGÚN SU PLAN (doc del 18-08, pantalla 8). A quien
                    lleva entrenador se le quita el peso de encima -- se lo van a revisar con
                    sus fotos -- y a quien no, se le dice desde el primer día que esto lo
                    repite él cada doce semanas. */}
                {/* Su foto y la del modelo, una encima de la otra (doc 23-08, punto 1). */}
                {(answers.foto_grasa || !esMujerBf) && (
                    <div className="mt-5 grid grid-cols-2 gap-3 max-w-sm" data-testid="bf-comparativa">
                        <div className="rounded-xl border-2 border-[#222222] overflow-hidden">
                            {answers.foto_grasa ? (
                                <img src={answers.foto_grasa} alt="Tu foto"
                                    className="w-full aspect-[3/4] object-cover" />
                            ) : (
                                <div className="w-full aspect-[3/4] flex flex-col items-center justify-center bg-card">
                                    <ImagePlus className="w-6 h-6 text-foreground/30" />
                                    <span className="text-foreground/40 text-xs mt-1.5 px-2 text-center">Tu foto, arriba en el carrusel</span>
                                </div>
                            )}
                            <p className="text-[11px] uppercase tracking-wider text-foreground/50 font-bold text-center py-1.5">La tuya</p>
                        </div>
                        {!esMujerBf && (
                            <div className="rounded-xl border-2 border-[#222222] overflow-hidden">
                                <img src={`/bodyfat/frente/${valorBf ?? 20}.webp`} alt={`Modelo ${valorBf ?? 20}%`}
                                    className="w-full aspect-[3/4] object-cover" />
                                <p className="text-[11px] uppercase tracking-wider text-foreground/50 font-bold text-center py-1.5">El modelo del {valorBf ?? 20}%</p>
                            </div>
                        )}
                    </div>
                )}
                <p className="text-foreground/50 text-xs mt-3">
                    {tieneCoach
                        ? 'Esto te lo damos nosotros, no te comas mucho la cabeza, es solo para arrancar. Tu entrenador lo revisará con tus fotos.'
                        : 'Si tu plan no lo incluye, te toca repetir este ejercicio cada 12 semanas máximo.'}
                </p>
                <div className="flex items-center gap-3 mt-6">
                    <BackBtn />
                    <Button onClick={goNext}
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8 py-6 text-lg">
                        Continuar <ArrowRight className="w-5 h-5 ml-2" />
                    </Button>
                </div>
            </div>
        );
    } else if (step.textarea) {
        body = (
            <div>
                <Title />
                <textarea value={answers[step.key] ?? ''} onChange={e => set(step.key, e.target.value)}
                    rows={4} placeholder="Escribe tu respuesta..."
                    className="w-full rounded-xl bg-card border-2 border-[#222222] p-4 text-foreground text-lg resize-none focus:outline-none focus:border-brand mb-8" />
                <div className="flex gap-3">
                    <BackBtn />
                    <Button onClick={goNext} disabled={!inputValid()}
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8">
                        OK <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                </div>
            </div>
        );
    } else {
        // text | email | tel | date | number
        const inputType = step.type === 'number' ? 'number' : step.type === 'tel' ? 'tel' : step.type === 'date' ? 'date' : step.type === 'email' ? 'email' : 'text';
        body = (
            <div>
                <Title />
                <div className="flex items-center gap-2 mb-8">
                    <Input
                        type={inputType}
                        autoFocus={!step.locked}
                        disabled={step.locked}
                        readOnly={step.locked}
                        value={answers[step.key] ?? ''}
                        onChange={e => set(step.key, e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter' && inputValid()) goNext(); }}
                        placeholder="Escribe tu respuesta..."
                        className={`text-lg py-6 bg-card border-[#222222] ${step.locked ? 'opacity-60 cursor-not-allowed' : ''}`}
                    />
                    {step.unit && <span className="text-foreground/50 text-lg">{step.unit}</span>}
                </div>
                {/* El aviso, aquí y no veinte pantallas después. */}
                {avisoDelPaso && (
                    <p className="text-sm text-amber-500 -mt-4 mb-6" data-testid="aviso-del-paso">
                        {avisoDelPaso}
                    </p>
                )}
                <div className="flex gap-3">
                    <BackBtn />
                    <Button onClick={goNext} disabled={!inputValid()}
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8">
                        OK <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                </div>
            </div>
        );
    }

    // La barra va en dos tramos (doc 29-07): el primero ajusta los macros y al acabarlo ya se
    // los entregamos; el segundo completa el perfil y es opcional. Los pasos de STEPS_AJUSTE
    // son el primer tramo; lo que viene detras (preferencias y perfil largo) es el segundo.
    //
    // SE CUENTAN SOLO LOS PASOS QUE APLICAN (regla 5 del doc del 23-08). Con `flow.length` a
    // secas la barra contaba pantallas condicionales que luego se saltan -- el detalle del
    // deporte de quien dijo que no, el biotipo en mujer -- y avanzaba a trompicones: un salto
    // grande al pasar tres condicionales de golpe y pasos enanos entre medias. Filtrando por
    // `visible` la barra mide el camino que este cliente va a recorrer de verdad con lo que
    // ha contestado hasta ahora.
    const limiteTramo1 = modoAjuste ? laBaseQueFalta.length + STEPS_AJUSTE.length : flow.length;
    const visiblesTotal = flow.filter(visible).length;
    const visiblesTramo1 = modoAjuste ? flow.slice(0, limiteTramo1).filter(visible).length : visiblesTotal;
    const posVisible = flow.slice(0, idx + 1).filter(visible).length;
    const enTramo1 = idx < limiteTramo1;
    const progresoTramo = enTramo1
        ? (posVisible / Math.max(1, visiblesTramo1)) * 100
        : ((posVisible - visiblesTramo1) / Math.max(1, visiblesTotal - visiblesTramo1)) * 100;
    const progress = (posVisible / Math.max(1, visiblesTotal)) * 100;
    const etiquetaTramo = !modoAjuste
        ? null
        : enTramo1 ? 'Ajustando tus macros' : 'Completando tu perfil (opcional)';

    return (
        <Shell
            progress={modoAjuste ? progresoTramo : progress}
            tramo={etiquetaTramo}
            cabecera={modoAjuste && enTramo1 && step.type !== 'result'
                ? <MacrosEnVivo macros={vistaPrevia?.macros} previos={previosRef.current} calculando={calculandoVivo} />
                : null}
        >
            {body}
            {/* El pie de la pantalla, cuando lo lleva. Hoy solo lo llevan las dos del
                documento -- las lesiones y la maquinaria -- y dicen lo mismo: que esa lista
                se revisa cada mes. Va aquí, en un solo sitio, y no repetido en cada pantalla
                que lo necesite. */}
            {step.pie && (
                <p className="mt-6 text-sm text-foreground/50 border-t border-border pt-4 max-w-2xl">
                    {step.pie}
                </p>
            )}
        </Shell>
    );
};

export default QuestionnairePage;
