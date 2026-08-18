import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { CAP } from '../lib/planAccess';
import { plural } from '../lib/labels';
import { seLeOfreceLaRevision } from '../lib/revision';
import { verComo } from '../lib/modoRevision';
import { MEDIDAS, VIDEO_MEDIDAS } from '../lib/medidas';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { ArrowRight, ArrowLeft, Loader2, Check, ImagePlus } from 'lucide-react';
import Logo12EN12 from '../components/Logo12EN12';
import BrandArrow from '../components/BrandArrow';
import DesgloseChips from '../components/DesgloseChips';
import PreferencesSetup from '../components/nutrition/PreferencesSetup';

// Cuestionario inicial en DOS NIVELES (spec 18-07-2026):
//  - Nivel 0 (todo el mundo): las 8 preguntas que mueven los macros -> CALCULAR.
//  - Nivel 1 (solo planes con coach, calculadora == 'personalizado'): perfil largo
//    (biotipo, salud, historial...). NO toca los macros.
// Estilo paso a paso (una pregunta por pantalla).

const BIOTIPOS = [
    { value: 'ectomorfo', label: 'Ectomorfo (el delgado)', img: '/biotipos/ectomorfo.jpg', desc: 'Complexión delgada (hombros estrechos, huesos largos y finos, articulaciones pequeñas), pero aspecto un poco "blando" (no gordo), sin tono muscular. Metabolismo muy rápido, quema calorías con facilidad y le cuesta ganar peso. No suele tener apetito, le cuesta comer. Acumula poca grasa, sobre todo en abdomen y parte baja de la espalda.' },
    { value: 'ecto-meso', label: 'Ecto-meso (el "fibrado")', img: '/biotipos/ecto-meso.jpg', desc: 'Delgado pero "fibroso" (como el anterior, pero con tono). Suele ser nervioso y le gusta el deporte, normalmente cardio, que se le da mejor. Si entrena fuerza hace descansos cortos, no puede estar parado. Puede acumular algo de grasa en el abdomen, pero no suele ser problema por ser más activo.' },
    { value: 'ecto-endo', label: 'Ecto-endo (el "gordi-flaco")', img: '/biotipos/ecto-endo.jpg', desc: 'Delgado pero con "tripita", no se cuida mucho la dieta (el típico "fofisano"). Se ve claramente que es una persona delgada pero con más grasa. No la acumula concentrada en un solo sitio, sino dispersa por varias áreas (abdomen, caderas, espalda baja) en cantidades pequeñas.' },
    { value: 'mesomorfo', label: 'Mesomorfo (el fuerte)', img: '/biotipos/mesomorfo.jpg', desc: 'El típico que está fuerte de serie, con buena genética para desarrollar músculo en cuanto entrena. Estructura ósea ancha, ideal para la fuerza, con clavículas amplias y caderas estrechas. Come bastante y no coge grasa con facilidad. Si acumula, en abdomen y algo en piernas.' },
    { value: 'meso-endo', label: 'Meso-endo (el "gordi-fuerte")', img: '/biotipos/meso-endo.jpg', desc: 'Gana músculo con facilidad pero también grasa. Le gusta bastante comer; para no taparse tiene que cuidarse todo el año, incluso en volumen. Como no necesita comer mucho para ponerse fuerte y le gusta comer, lo normal es verle "tapado". Grasa en abdomen, caderas y espalda baja.' },
    { value: 'endo-meso', label: 'Endo-meso (el grande)', img: '/biotipos/endo-meso.jpg', desc: 'Como el meso-endo pero con más tendencia a ganar grasa. Se le ve "grande", tiene músculo pero niveles muy altos de grasa. Le gusta comer y para definir tiene que comer poco, cosa que le cuesta mucho. Grasa sobre todo en abdomen, caderas, espalda baja y muslos.' },
    { value: 'endomorfo', label: 'Endomorfo (el gordo)', img: '/biotipos/endomorfo.jpg', desc: 'Tendencia clara a engordar y niveles altos de grasa casi toda la vida. Suele llevar vida muy sedentaria y malos hábitos. El abdomen es la zona más problemática (barriga prominente, grasa visceral). También acumula en muslos, caderas, brazos y espalda.' },
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
        desc: 'Fútbol, running, ciclismo, artes marciales... cualquier deporte con regularidad.',
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
        textarea: true,
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
        type: 'choice', key: 'apetito', title: '¿Eres de buen comer?',
        options: [
            { value: 'mucho', label: 'Mucho' },
            { value: 'normal', label: 'Lo normal' },
            { value: 'poco', label: 'Poco' },
        ],
    },
    {
        type: 'choice', key: 'facilidad_engordar', title: 'Cuando te pasas comiendo, ¿engordas?',
        desc: 'Piensa en vacaciones, Navidades o épocas en las que comiste de más.',
        options: [
            { value: 'enseguida', label: 'Enseguida' },
            { value: 'normal', label: 'Lo normal' },
            { value: 'casi_no', label: 'Casi no' },
        ],
    },
    {
        // No mueve macros: alimenta el biotipo declarado.
        type: 'choice', key: 'cuesta_definir', title: '¿Te cuesta definir?',
        options: [
            { value: 'mucho', label: 'Mucho' },
            { value: 'normal', label: 'Lo normal' },
            { value: 'poco', label: 'Nada' },
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
    { type: 'final0', title: 'Y ya estaría.', desc: 'Si quieres revisar alguna respuesta, ve hacia atrás. Al calcular verás tus macros personalizados.' },
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
    {
        // P14. La respuesta se guarda; la regla de como afecta a los macros la dara Jesus.
        type: 'choice', key: 'trt', title: '¿Sigues algún tratamiento hormonal tipo TRT?',
        desc: 'Es información médica y la trata el equipo. No cambia tus macros.',
        options: [
            { value: 'si', label: 'Sí' },
            { value: 'no', label: 'No' },
            { value: 'antes', label: 'Lo seguí antes, ahora no' },
        ],
    },
    {
        // Bloque 4: la intención cuenta tanto como el uso. Quien piensa empezar hay que
        // saberlo ANTES, no cuando ya lo ha hecho.
        type: 'choice', key: 'farmacologia_uso',
        title: '¿Usas o has usado ayudas farmacológicas?',
        desc: 'Sin juicios: se pregunta porque cambia lo que se te puede pedir y lo que hay que vigilar.',
        options: [
            { value: 'uso', label: 'Sí, ahora mismo' },
            { value: 'use', label: 'He usado antes, ahora no' },
            { value: 'intencion', label: 'No, pero tengo intención' },
            { value: 'nunca', label: 'No, ni me lo planteo' },
        ],
    },
    // ── Bloque 5 · Tu suplementación ────────────────────────────────────────────
    // No existía. El equipo le pauta suplementos sin saber qué está tomando ya, que es
    // la forma más rápida de repetirle algo o de chocar con lo que lleva.
    {
        type: 'text', key: 'suplementos_ahora',
        title: '¿Qué suplementos tomas ahora?',
        desc: 'Cuáles y a qué dosis, si la sabes. Si no tomas ninguno, escribe "ninguno".',
        textarea: true,
    },
    {
        type: 'text', key: 'suplementos_antes',
        title: '¿Y cuáles has tomado antes?',
        desc: 'Sobre todo si notaste algo, bueno o malo. Si no has tomado nada, escribe "nada".',
        textarea: true,
    },
    {
        type: 'choice', key: 'quiere_pauta_suplementos',
        title: '¿Quieres que te pautemos suplementación?',
        desc: 'Nunca hace falta para conseguir resultados. Es tu decisión.',
        options: [
            { value: 'si', label: 'Sí, quiero que me lo pautéis' },
            { value: 'lo_justo', label: 'Solo lo imprescindible' },
            { value: 'no', label: 'No, prefiero no tomar nada' },
        ],
    },
    {
        // P15
        type: 'choice', key: 'zona_grasa', title: '¿Dónde acumulas más grasa?',
        options: [
            { value: 'abdomen', label: 'Abdomen' },
            { value: 'cintura', label: 'Cintura y flancos' },
            { value: 'espalda_baja', label: 'Espalda baja' },
            { value: 'pecho', label: 'Pecho' },
            { value: 'piernas', label: 'Piernas y glúteos' },
            { value: 'reparto', label: 'Se me reparte por igual' },
        ],
    },
    { type: 'pesos', title: 'Tu historial de peso', desc: 'Aproximado, en kg. Ayuda al equipo a entender tu recorrido.' },
    { type: 'historia', title: 'Tu recorrido', desc: 'Cuándo fue cada cosa y hasta dónde quieres llegar.' },
    {
        // P22
        type: 'choice', key: 'vario_peso_3m', title: '¿Ha variado tu peso de forma significativa en los últimos 3 meses?',
        options: [
            { value: 'subido', label: 'Sí, he subido' },
            { value: 'bajado', label: 'Sí, he bajado' },
            { value: 'estable', label: 'No, sigo más o menos igual' },
        ],
    },
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
        type: 'text', textarea: true, key: 'motivo_apuntarse',
        title: 'Dime el motivo principal de querer trabajar conmigo, qué esperas y por qué te decides a empezar ahora y no antes.',
    },
    { type: 'salud', title: 'Salud y descanso', desc: 'Sé sincero: todo esto condiciona tu estrategia.' },
    { type: 'text', key: 'dietas_previas', title: '¿Has hecho dietas antes? ¿Qué tal te fue?', desc: 'Cuáles, cuánto duraste, qué pasó con tu peso...', textarea: true },
    { type: 'text', key: 'entrenador_anterior', title: '¿Has tenido entrenador antes?', desc: 'Quién, cuánto tiempo y por qué lo dejaste. Si no, escribe "no".', textarea: true },
    // Comidas al día, días de entreno y cuándo entrena YA se preguntan en el
    // bloque de preferencias del Nivel 0 (no repetir); los alimentos a evitar
    // se eligen con el selector visual de preferencias, no en texto libre.
    {
        // Bloque 3: si entrena AHORA no es lo mismo que cuántos años lleva. Uno puede
        // llevar diez años entrenando y estar parado desde marzo.
        type: 'choice', key: 'entrena_ahora', title: '¿Entrenas ahora mismo de forma regular?',
        options: [
            { value: 'si', label: 'Sí, con constancia' },
            { value: 'irregular', label: 'Voy, pero de forma irregular' },
            { value: 'no', label: 'Ahora mismo no entreno' },
        ],
    },
    {
        type: 'multiselect', key: 'material', title: '¿Con qué material cuentas para entrenar?',
        desc: 'Marca todo lo que tengas disponible.',
        options: [
            { value: 'gimnasio_completo', label: 'Gimnasio completo' },
            { value: 'mancuernas', label: 'Mancuernas' },
            { value: 'barra_discos', label: 'Barra y discos' },
            { value: 'maquinas', label: 'Máquinas' },
            { value: 'bandas', label: 'Bandas elásticas' },
            { value: 'nada', label: 'Nada (solo peso corporal)' },
        ],
    },
    {
        // Lo que NO tiene importa tanto como lo que tiene: una rutina con jaula de
        // sentadilla no vale de nada si en su gimnasio no hay.
        type: 'text', key: 'maquinas_que_faltan',
        title: '¿Hay alguna máquina básica que no tengas?',
        desc: 'Jaula de sentadilla, prensa, poleas... Si lo tienes todo, escribe "no".',
        textarea: true,
    },
    {
        type: 'text', key: 'ejercicios_imposibles',
        title: '¿Hay algún ejercicio que no puedas hacer?',
        desc: 'Por una lesión, por dolor o porque nunca te ha ido bien. Si no hay ninguno, escribe "no".',
        textarea: true,
    },
    {
        type: 'choice', key: 'cardio', title: '¿Haces cardio?',
        options: [
            { value: 'no', label: 'No hago cardio' },
            { value: '1-2_semana', label: '1-2 veces por semana' },
            { value: '3+_semana', label: '3 o más veces por semana' },
        ],
    },
    // ── Bloque 6 · Tu comida ────────────────────────────────────────────────────
    // Lo que decide si sus menús le encajan en la vida o los abandona en tres días. Las
    // 36 categorías y el momento del día se preguntan aparte, en las preferencias.
    {
        type: 'choice', key: 'cocina_o_rapido',
        title: '¿Te gusta cocinar o prefieres cosas rápidas?',
        desc: 'No hay respuesta buena. Lo que hay que evitar es mandarte recetas de media hora si no vas a hacerlas.',
        options: [
            { value: 'cocinar', label: 'Me gusta cocinar y tengo tiempo' },
            { value: 'normal', label: 'Cocino lo justo, sin complicarme' },
            { value: 'rapido', label: 'Cuanto más rápido, mejor' },
        ],
    },
    {
        type: 'choice', key: 'conserva_o_fresco',
        title: '¿Te vale la conserva o lo quieres fresco?',
        options: [
            { value: 'conserva', label: 'La conserva me facilita la vida' },
            { value: 'ambos', label: 'Me da igual, según el día' },
            { value: 'fresco', label: 'Lo prefiero fresco' },
        ],
    },
    {
        type: 'choice', key: 'come_fuera',
        title: '¿Comes fuera de casa entre semana?',
        desc: 'Si comes fuera casi todos los días, la dieta tiene que contar con eso desde el principio.',
        options: [
            { value: 'no', label: 'No, como en casa' },
            { value: '1_2', label: '1 o 2 días por semana' },
            { value: '3_4', label: '3 o 4 días' },
            { value: 'casi_todos', label: 'Casi todos los días' },
        ],
    },
    {
        type: 'text', key: 'que_le_apetece',
        title: '¿Qué tipo de desayuno, comida, merienda y cena te apetecen?',
        desc: 'Cuéntamelo con tus palabras: qué sueles comer o qué te gustaría comer en cada momento del día.',
        textarea: true,
    },
    {
        type: 'text', key: 'favoritos_y_no_gustos',
        title: '¿Qué alimentos te encantan y cuáles no piensas comer?',
        desc: 'Por grupos: carnes, pescados, verduras, lácteos, hidratos... Lo que no te gusta pesa tanto como lo que sí.',
        textarea: true,
    },
    {
        type: 'text', key: 'plato_imprescindible',
        title: '¿Hay algún plato que quieras sí o sí?',
        desc: 'Ese que si no está, la dieta no te dura. Si no hay ninguno, escribe "no".',
        textarea: true,
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
        options: [
            { value: 'total', label: 'Total: nada de lácteos' },
            { value: 'tolera_algo', label: 'Tolero el yogur, el queso curado o el queso batido' },
        ],
    },
    {
        type: 'choice', key: 'gluten',
        title: '¿Es celiaquía diagnosticada o sensibilidad?',
        desc: '¿Toleras pequeñas cantidades como pan de molde o avena sin gluten?',
        options: [
            { value: 'celiaquia', label: 'Celiaquía diagnosticada: nada de gluten' },
            { value: 'sensibilidad', label: 'Sensibilidad: tolero pequeñas cantidades' },
        ],
    },
    { type: 'text', key: 'alergias', title: '¿Alguna otra alergia o intolerancia?', desc: 'Frutos secos, marisco, huevo... Si no tienes, escribe "no".', textarea: true },
    { type: 'final1', title: 'Perfil completo.', desc: 'El equipo usará todo esto para tu estrategia. Las fotos de progreso te las pedirán por el chat. Si quieres revisar algo, ve hacia atrás.' },
];

// CUÁNTAS SON, CONTADAS DE LA PROPIA LISTA.
// El aviso de arriba deja su `desc` vacía a propósito y se rellena aquí: si el número se
// escribiera a mano, se quedaría viejo el día que alguien añada una pregunta, y entonces el
// aviso mentiría, que es peor que no decir nada. Los `statement` no cuentan: son pantallas de
// texto, no preguntas.
STEPS_NIVEL1[0].desc =
    `Son ${STEPS_NIVEL1.filter(s => s.type !== 'statement').length} preguntas más y con ellas `
    + 'montamos tu estrategia, tu rutina y tus menús.';


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
// Y VAN CINCO MÁS DE LAS QUE PIDE EL DOCUMENTO (decisión de Francisco, 18-08): el deporte
// y las cuatro de la dieta. El documento se las lleva al completo, que solo hacen los de
// entrenador, y son las que mueven los macros: al de Calculadora se le habrían calculado
// con menos información que hoy. Se quedan aquí, sumadas, y NO se repiten en el completo.
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
    // 6, 7 y 8 · peso, altura y porcentaje de grasa
    q('weight'), q('height'), q('body_fat'),
    // 9, 10 y 11 · su recorrido de peso, cada hito con su año. Antes era UNA pantalla con
    // cuatro casillas sueltas, sin años y solo para quien llevaba entrenador.
    {
        type: 'peso_hito', key: 'peso_maximo',
        title: '¿Cuál fue tu máximo peso alcanzado y cuándo?',
        desc: 'Me refiero a cuándo estuviste en tu peor forma física.',
        nota: 'Cuéntame lo que quieras de esa época',
    },
    {
        type: 'peso_hito', key: 'peso_mejor_momento', conFoto: true,
        title: '¿Has estado muy en forma alguna vez?',
        desc: 'Si es que sí, dime cuándo y tu peso en aquel momento.',
        nota: 'Cuéntame lo que quieras',
    },
    {
        type: 'peso_hito', key: 'peso_minimo',
        title: '¿Cuál es el peso más bajo al que has llegado siendo adulto, y cuándo?',
        desc: 'No hablo de tu mejor forma, sino de lo más abajo que has estado, aunque no te vieras bien.',
        nota: 'Cuéntame lo que quieras de esa época',
    },
    // 12 · a qué se dedica y cuánto se mueve, JUNTAS. En pantallas seguidas se le pregunta
    // su trabajo y acto seguido se le pide que se clasifique en lo mismo, y suena a que no
    // se le ha escuchado.
    { type: 'ocupacion', title: '¿A qué te dedicas y cuánto te mueves en tu día a día?' },
    // 13 · la experiencia entrenando
    q('training_experience'),
    // Las del deporte: se quedan (decisión del 18-08), pegadas a la de entrenamiento.
    q('deporte_extra'), q('deporte_cual'), q('deporte_en_descanso'),
    // 14, 15 y 16 · cómo come, si engorda y si le cuesta definir
    q('apetito'), q('facilidad_engordar'), q('cuesta_definir'),
    // 17 y 18 · los siete biotipos y el suyo (en mujer no salen)
    porTipo('biotype_intro'), q('biotype'),
    // 19 · el día tipo, con el lector. Y con él las cuatro de la dieta, que se quedan.
    q('sigue_dieta'), q('tiempo_dieta'), porTipo('dieta'), q('como_va'), q('hambre_saturacion'),
    // 20 · las dietas de antes (estaba en el cuestionario largo)
    q('dietas_previas'),
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
    { ...q('lactosa'), cond: a => (a.alergias || []).includes('lactosa') },
    { ...q('gluten'), cond: a => (a.alergias || []).includes('gluten') },
    {
        type: 'text', key: 'alergia_otra', title: '¿Cuál?',
        desc: 'Dime a qué eres alérgico o intolerante.',
        cond: a => (a.alergias || []).includes('otra'),
    },
    // 22 · las proteínas que come habitualmente. Con esto y las intolerancias se le monta
    // el primer menú, que es lo que hace que no entre a una app vacía.
    {
        type: 'multiselect', key: 'proteinas_habituales',
        title: '¿Qué proteínas comes habitualmente?',
        desc: 'Marca al menos tres.',
        options: [
            { value: 'aves', label: 'Aves' },
            { value: 'ternera', label: 'Ternera o buey' },
            { value: 'cerdo', label: 'Cerdo' },
            { value: 'pescado', label: 'Pescados y mariscos' },
            { value: 'embutido', label: 'Embutido' },
            { value: 'huevos', label: 'Huevos y derivados' },
            { value: 'polvo', label: 'Proteínas en polvo y barritas' },
            { value: 'vegetal', label: 'Proteína vegetal' },
            { value: 'legumbres', label: 'Legumbres' },
            { value: 'lacteos', label: 'Lácteos' },
        ],
    },
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
const YA_ESTAN_EN_EL_BASICO = ['tiempo_intentandolo', 'motivo_apuntarse', 'dietas_previas',
                               'lactosa', 'gluten', 'alergias'];
for (let i = 0; i < STEPS_NIVEL1.length; i++) {
    const paso = STEPS_NIVEL1[i];
    const yaContestada = YA_ESTAN_EN_EL_BASICO.includes(paso.key)
        ? (a) => !a[paso.key]
        : paso.type === 'pesos'
            ? (a) => !a.peso_maximo && !a.peso_minimo && !a.peso_mejor_momento
            : null;
    if (yaContestada) {
        const antes = paso.cond;
        STEPS_NIVEL1[i] = { ...paso, cond: (a) => yaContestada(a) && (!antes || antes(a)) };
    }
}

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
                <span className="font-heading font-extrabold text-xl text-brand tabular-nums">{ahora}</span>
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
            <span className="text-[10px] uppercase tracking-wider text-foreground/30">Tus macros</span>
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
        {/* Barra de progreso */}
        <div className="fixed top-0 left-0 right-0 h-1 bg-white/10 z-20">
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
    // Momento mágico: primeros menús del banco personal (null = cargando).
    const [menusMagia, setMenusMagia] = useState(null);
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
    // Los macros de antes de la ultima respuesta, para poder mostrar cuanto se ha movido cada uno.
    const previosRef = useRef(null);
    // Punto de partida: fotos subidas y la ficha que se le entrega a cambio.
    const [ficha, setFicha] = useState(null);
    // P10: lo que hemos entendido de su dieta, pendiente de que lo confirme.
    const [lecturaDieta, setLecturaDieta] = useState(null);
    const [leyendoDieta, setLeyendoDieta] = useState(false);
    const [misDias, setMisDias] = useState(null);   // null = sin pedir todavia

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
            : [{ type: 'fotos_medidas', title: 'Te quedan dos cosas' },
               { type: 'oferta_ajuste', title: 'Una cosa más' }]),
    ];
    const preguntasDeAjuste = [...STEPS_AJUSTE, ...elCierre];
    const flow = retomandoNivel1
        ? STEPS_NIVEL1
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
        if (answers.pref_dias_entreno != null) {
            api.put('/clients/profile', { training_days: answers.pref_dias_entreno }).catch(() => {});
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [idx]);

    // La ficha se pide al llegar a su pantalla, no antes: hasta ese momento el cliente puede
    // haber cambiado su altura o sus medidas, y la ficha saldria con datos viejos.
    useEffect(() => {
        if (flow[idx]?.type !== 'ficha' || ficha) return;
        api.get('/clients/mi-ficha')
            .then(r => setFicha(r.data))
            .catch(() => setFicha({ composicion: null, referencia: null }));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [idx]);

    // Momento mágico: tres recetas del recetario cuadradas a los macros que acaba de
    // calcular. Antes salían de la biblioteca de menús de clientes; desde el 06-08-2026
    // esa fuente está apagada (ver lib/menuFuentes) y el recetario es la única.
    // Se piden por separado -- el catálogo no trae cantidades, las pone menu-apply al
    // elegir cada receta -- y a cambio el menú viene con su nombre.
    useEffect(() => {
        const s = flow[idx];
        if (s?.type !== 'magia' || menusMagia !== null) return;
        const config = {
            mealKey: 'C1',
            macros_objetivo: {},   // el backend reparte el día y toma el target de C1
            num_comidas: answers.pref_num_comidas || 4,
            momento_entreno: answers.pref_momento ?? 1,
        };
        (async () => {
            try {
                const cat = await api.get('/calculator/menu-catalog');
                // Si entrena en ayunas su primera comida es la de después del entreno, y
                // ahí toca plato, no un desayuno.
                const enAyunas = (answers.pref_momento ?? 1) === 1;
                const quiero = enAyunas ? 'comida' : 'desayuno';
                const todas = cat.data?.menus || [];
                const pegan = todas.filter(m => (m.momentos || []).includes(quiero));
                // Se cuadran más de las que se enseñan y se muestran las tres que mejor
                // encajan: una receta cualquiera puede quedarse lejos de sus macros, y el
                // momento mágico es justo donde no puede verse flojo.
                const candidatas = (pegan.length >= 3 ? pegan : todas).slice(0, 8);
                if (!candidatas.length) { setMenusMagia([]); return; }
                const cuadradas = await Promise.all(candidatas.map(r =>
                    api.post('/calculator/menu-apply', { plantilla_id: r.id, ...config })
                        .then(res => ({ ...res.data, macros_metodo: res.data.macros_totales }))
                        .catch(() => null)
                ));
                setMenusMagia(cuadradas.filter(Boolean)
                    .sort((a, b) => (a.err ?? 999) - (b.err ?? 999))
                    .slice(0, 3));
            } catch {
                setMenusMagia([]);
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
    const modoAnteriorRef = useRef(modoAjuste);
    useEffect(() => {
        if (modoAnteriorRef.current !== modoAjuste) {
            modoAnteriorRef.current = modoAjuste;
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
        const suyo = (guardado?.flujo || 'ajuste') === (modoAjuste ? 'ajuste' : 'alta');
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
        }));
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
                             'peso_mejor_momento', 'profesion', 'como_me_conociste',
                             'proteinas_habituales', 'birthdate', 'height', 'biotype',
                             'training_experience']) {
            const v = profile[clave];
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
        if (!modoAjuste || !profile?.weight || !profile?.goal) return;
        setCalculandoVivo(true);
        try {
            const res = await api.post('/calculator/targets', {
                peso: profile.weight,
                sexo: profile.sex || 'hombre',
                porcentaje_graso: profile.body_fat,
                objetivo: profile.goal,
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

    // El progreso se guarda a cada respuesta: si se sale y vuelve, sigue donde lo dejo.
    //
    // TAMBIÉN EN EL ALTA desde el 18-08. Antes esto se cortaba en seco si no era el
    // cuestionario de ajuste, así que el alta -- que es el recorrido largo, y el único que
    // se hace una sola vez en la vida -- era justo el que no se guardaba. Va con el nombre
    // del recorrido para que cada uno retome el suyo.
    const guardarProgreso = useCallback((respuestas, paso) => {
        if (revision) return;   // en modo revisión no se escribe nada
        api.put('/clients/ajuste-progreso',
                { respuestas, paso, flujo: modoAjuste ? 'ajuste' : 'alta' }).catch(() => {});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [api, modoAjuste, revision]);

    // ── P10: leer la dieta que trae el cliente ────────────────────────────────
    const cargarMisDias = useCallback(async () => {
        if (misDias !== null) return;
        try {
            const r = await api.get('/clients/mis-dias');
            setMisDias(r.data?.dias || []);
        } catch (e) { setMisDias([]); }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [api, misDias]);

    // El ALTA no se puede repetir (ni por el enlace). El cuestionario de AJUSTE sí: si cambia de
    // trabajo o empieza a hacer otro deporte, lo vuelve a pasar y sus macros se recalculan.
    if (!revision && profile?.questionnaire_completed && !nivel0Enviado && !retomandoNivel1 && !pidioAjustar) {
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

    const step = flow[idx] || flow[0];
    const progress = ((idx + 1) / flow.length) * 100;

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

    // Igual que la de la dieta, pero para la foto del peso maximo (P19).
    const elegirFotoPesoMaximo = () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = (ev) => {
            const file = ev.target.files?.[0];
            if (!file) return;
            if (file.size > 8 * 1024 * 1024) { toast.error('La foto pesa demasiado (máximo 8 MB)'); return; }
            const reader = new FileReader();
            reader.onload = (e) => set('foto_peso_maximo', e.target.result);
            reader.readAsDataURL(file);
        };
        input.click();
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
        const cuerpo = modo === 'menu' ? { fecha_menu: answers.dieta_fecha_menu }
            : modo === 'foto' ? { imagen: answers.dieta_imagen }
            : { texto: answers.dieta_texto };
        const vacio = modo === 'menu' ? !answers.dieta_fecha_menu
            : modo === 'foto' ? !answers.dieta_imagen
            : !(answers.dieta_texto || '').trim();
        if (vacio) {
            toast.error(modo === 'menu' ? 'Elige uno de tus días'
                : modo === 'foto' ? 'Sube la foto de tu dieta'
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
    const responderOferta = async (quiere) => {
        setLoading(true);
        try {
            await api.post('/clients/ajuste-a-medida', { quiere });
            toast.success(quiere
                ? 'Anotado. Te escribimos con los detalles.'
                : 'Perfecto, seguimos con tu plan.');
        } catch (e) {
            // Que no se le atasque el final del alta por esto: el aviso al equipo puede
            // esperar, la persona no.
            console.error('[alta] no se pudo guardar la respuesta a la oferta', e);
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
    const visible = (s) => !s.cond || s.cond(answersRef.current);
    const goNext = () => setIdx(i => {
        let j = i + 1;
        while (j < flow.length - 1 && !visible(flow[j])) j++;
        return Math.min(j, flow.length - 1);
    });
    const cancelarAvancePendiente = () => {
        if (avancePendienteRef.current) {
            clearTimeout(avancePendienteRef.current);
            avancePendienteRef.current = null;
        }
    };
    const goBack = () => {
        cancelarAvancePendiente();
        setIdx(i => {
            let j = i - 1;
            while (j > 0 && !visible(flow[j])) j--;
            return Math.max(j, 0);
        });
    };

    const num = (v) => { const n = parseFloat(v); return isNaN(n) ? null : n; };

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
            if (!profile?.questionnaire_completed) {
                await api.post('/clients/questionnaire', {
                    name: answers.name,
                    email: answers.email,
                    phone: answers.phone,
                    goal: answers.goal,
                    sex: answers.sex,
                    weight: parseFloat(answers.weight),
                    body_fat: parseFloat(answers.body_fat),
                    // TODO LO DEMÁS QUE TRAE EL BÁSICO (bloque 2 del doc del 18-08). Antes
                    // aquí viajaban siete campos y el servidor esperaba trece: por eso el
                    // perfil se quedaba vacío. Ahora se manda lo que se pregunta.
                    birthdate: answers.birthdate || null,
                    height: num(answers.height),
                    biotype: answers.biotype || null,
                    training_experience: answers.training_experience || null,
                    profesion: answers.profesion || null,
                    como_me_conociste: answers.como_me_conociste || null,
                    proteinas_habituales: answers.proteinas_habituales || null,
                    peso_maximo: num(answers.peso_maximo),
                    peso_maximo_ano: num(answers.peso_maximo_ano),
                    peso_maximo_nota: answers.peso_maximo_nota || null,
                    peso_mejor_momento: num(answers.peso_mejor_momento),
                    peso_mejor_momento_ano: num(answers.peso_mejor_momento_ano),
                    peso_mejor_momento_nota: answers.peso_mejor_momento_nota || null,
                    foto_mejor_momento: answers.foto_mejor_momento || null,
                    peso_minimo: num(answers.peso_minimo),
                    peso_minimo_ano: num(answers.peso_minimo_ano),
                    peso_minimo_nota: answers.peso_minimo_nota || null,
                    alergias: answers.alergias || null,
                    lactosa: answers.lactosa || null,
                    gluten: answers.gluten || null,
                    alergia_otra: answers.alergia_otra || null,
                    dietas_previas: answers.dietas_previas || null,
                    tiempo_intentandolo: answers.tiempo_intentandolo || null,
                    motivo_apuntarse: answers.motivo_apuntarse || null,
                });
            }
            const res = await api.post('/clients/ajustar-macros', ajustesDelCuestionario());
            setResultado(res.data?.resultado || null);
            // Con los macros ya calculados, se le deja el día de hoy montado. Va en segundo
            // plano y sin bloquear: si falla, se queda como estaba (con su día por montar) y
            // no se le estropea el final del alta por esto.
            api.post('/calculator/montar-dia', { guardar: true })
                .then(r => setDiaMontado(r.data || null))
                .catch(() => {});
            setEntrega(res.data?.entrega || null);
            setNivel0Enviado(true);
            await refreshProfile();
            toast.success('¡Macros calculados!');
            goNext(); // -> pantalla de resultados
        } catch (e) {
            toast.error(mensajeDeError(e, 'Error al enviar el cuestionario'));
        } finally {
            setLoading(false);
        }
    };

    // Nivel 1 -> guardar perfil largo (no toca macros).
    const submitNivel1 = async () => {
        setLoading(true);
        try {
            await api.post('/clients/questionnaire/nivel1', {
                biotype: answers.biotype || null,
                height: num(answers.height),
                birthdate: answers.birthdate || null,
                training_experience: answers.training_experience || null,
                peso_maximo: num(answers.peso_maximo),
                peso_minimo: num(answers.peso_minimo),
                peso_habitual: num(answers.peso_habitual),
                peso_mejor_momento: num(answers.peso_mejor_momento),
                salud: {
                    sueno: answers.salud_sueno || null,
                    estres: answers.salud_estres || null,
                    medicacion: answers.salud_medicacion || null,
                    hormonal: answers.salud_hormonal || null,
                    lesiones: answers.salud_lesiones || null,
                },
                dietas_previas: answers.dietas_previas || null,
                entrenador_anterior: answers.entrenador_anterior || null,
                // Preguntados en las preferencias del Nivel 0 (aquí no se repiten);
                // los alimentos evitados viven en las preferencias del perfil.
                dias_entreno: answers.pref_dias_entreno ?? null,
                hora_entreno: null,
                material: answers.material || null,
                cardio: answers.cardio || null,
                // Bloque 3: lo que hace falta para montarle la rutina. Entrenar AHORA no es
                // lo mismo que llevar años, y lo que NO tiene pesa tanto como lo que tiene.
                entrena_ahora: answers.entrena_ahora || null,
                maquinas_que_faltan: answers.maquinas_que_faltan || null,
                ejercicios_imposibles: answers.ejercicios_imposibles || null,
                // Bloque 5: su suplementación. Sin esto se le pauta a ciegas.
                suplementos_ahora: answers.suplementos_ahora || null,
                suplementos_antes: answers.suplementos_antes || null,
                quiere_pauta_suplementos: answers.quiere_pauta_suplementos || null,
                // Bloque 4: la intención cuenta tanto como el uso.
                farmacologia_uso: answers.farmacologia_uso || null,
                // Bloque 6: lo que decide si sus menús le encajan en la vida.
                cocina_o_rapido: answers.cocina_o_rapido || null,
                conserva_o_fresco: answers.conserva_o_fresco || null,
                come_fuera: answers.come_fuera || null,
                que_le_apetece: answers.que_le_apetece || null,
                favoritos_y_no_gustos: answers.favoritos_y_no_gustos || null,
                plato_imprescindible: answers.plato_imprescindible || null,
                lactosa: answers.lactosa || null,
                gluten: answers.gluten || null,
                alimentos_evitados: null,
                alergias: answers.alergias || null,
                num_comidas: answers.pref_num_comidas ?? null,
                // Bloque 4 del doc: no mueven macros, sirven para emparejarlo con casos anteriores.
                trt: answers.trt || null,
                zona_grasa: answers.zona_grasa || null,
                peso_maximo_cuando: answers.peso_maximo_cuando || null,
                foto_peso_maximo: answers.foto_peso_maximo || null,
                mejor_definicion_cuando: answers.mejor_definicion_cuando || null,
                hasta_donde: answers.hasta_donde || null,
                vario_peso_3m: answers.vario_peso_3m || null,
                tiempo_intentandolo: answers.tiempo_intentandolo || null,
                dieta_que_funciona: answers.dieta_que_funciona || null,
                por_que_fallaron: answers.por_que_fallaron || null,
                motivo_apuntarse: answers.motivo_apuntarse || null,
            });
            await refreshProfile();
            toast.success('¡Perfil completo! El equipo ya tiene toda la información.');
            navigate('/welcome');
        } catch (e) {
            toast.error(mensajeDeError(e, 'Error al guardar el perfil'));
        } finally {
            setLoading(false);
        }
    };

    // Validación del paso actual (para inputs de texto/número).
    const inputValid = () => {
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

    const Title = () => (
        <>
            <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-2 leading-tight">{segunRespuestas(step.title)}</h2>
            {step.desc && <p className="text-foreground/60 mb-8 text-sm md:text-base">{segunRespuestas(step.desc)}</p>}
        </>
    );

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
    } else if (step.type === 'statement') {
        body = (
            <div>
                <Title />
                <div className="flex gap-3">
                    <BackBtn />
                    <Button onClick={goNext}
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
        body = (
            <div>
                <Title />
                {bloqueado && (
                    <p className="text-sm text-amber-500 mb-5 -mt-6" data-testid="faltan-obligatorias">
                        Antes de calcular falta que nos digas {faltanPorContestar.map(o => o.label).join(', ')}.
                        Vuelve atrás y complétalo.
                    </p>
                )}
                <div className="flex gap-3">
                    <BackBtn />
                    <Button onClick={isN0 ? submitNivel0 : submitNivel1} disabled={loading || bloqueado}
                        data-testid="calcular-macros-btn"
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8 py-6 text-lg disabled:opacity-40">
                        {loading ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <Check className="w-5 h-5 mr-2" />}
                        {loading ? 'Enviando...' : isN0 ? 'Calcular mis macros' : 'Enviar'}
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
                <h2 className="font-heading font-bold text-2xl md:text-3xl text-foreground mb-2 leading-tight">
                    {/* Al del plan con entrenador hay que decirle con estas palabras que lo
                        que tiene NO es lo definitivo: le queda el cuestionario largo por
                        rellenar y su coach se lo revisa. El texto es el del documento de
                        Jesús del 06-08, literal.

                        Se había quitado al unificar el alta (punto 15), y era pasarse: lo que
                        dejó de tener sentido es llamar "provisionales" a unos macros que ya
                        llevan dentro los modificadores, no el aviso al que espera revisión. */}
                    {/* EL AVISO VA DEBAJO DE LOS NÚMEROS (punto 4.1): «Debe ir DEBAJO DE LOS
                        MACROS al terminar, para los planes con entrenador». Aquí arriba estaba
                        antes de verlos, y leer «estos no son tus macros definitivos» sin haber
                        visto todavía ningún macro no dice nada. */}
                    Estos son tus macros
                </h2>
                {!entrega?.con_entrenador && (
                    <p className="text-foreground/60 mb-4 text-sm">
                        {/* Sin entrenador asignado no se dice "tu entrenador": casi ningún cliente
                            tiene uno puesto y prometer una persona que no existe se nota. Quien lo
                            revisa entonces es el equipo, que es la verdad.
                            Texto cerrado por Jesús el 06-08-2026 (momento 1 de la revisión
                            suelta): lo que sostiene el número es el perfil parecido. */}
                        {`Están adaptados a tu perfil, a partir de tus respuestas y tomando como referencia otros perfiles parecidos al tuyo.${entrega?.proxima_revision ? ` Tu próxima revisión automática será el ${entrega.proxima_revision}.` : ''}`}
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
                        <DesgloseChips desglose={resultado.desglose} />
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
                        <p className="text-sm font-semibold text-foreground">Estos no son tus macros definitivos.</p>
                        <p className="text-sm text-foreground/70 mt-0.5">
                            Son los que vas a usar hasta que revisemos tu cuestionario. Rellénalo lo antes posible y en
                            menos de 48 horas recibirás los tuyos personalizados.
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
                            Y tu día de hoy ya está montado
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
        return (
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
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-2 leading-tight">
                    Estas son comidas que puedes comer hoy
                </h2>
                <p className="text-foreground/60 mb-6 text-sm md:text-base">
                    Recetas del recetario, con las cantidades ya puestas para tus macros.
                </p>
                {menusMagia === null ? (
                    <div className="flex justify-center py-10">
                        <div className="animate-spin rounded-full h-9 w-9 border-4 border-brand border-t-transparent" />
                    </div>
                ) : menusMagia.length === 0 ? (
                    <p className="text-foreground/60 text-sm mb-4">
                        El recetario te espera en <span className="font-bold text-foreground">Nutrición</span>:
                        en cada comida, pulsa "Sugiéreme un menú" y elige la receta que te apetezca.
                    </p>
                ) : (
                    <div className="space-y-3 mb-2">
                        {menusMagia.map((menu, i) => (
                            <div key={menu.plantilla_id || menu.biblioteca_id || i} className="rounded-xl border-2 border-[#222222] bg-card p-4">
                                {menu.nombre && (
                                    <p className="text-base font-black text-foreground mb-1">{menu.nombre}</p>
                                )}
                                <div className="flex items-center justify-between gap-2 mb-1.5">
                                    <p className="text-sm font-black text-brand">
                                        {Math.round(menu.macros_metodo?.P || 0)}P · {Math.round(menu.macros_metodo?.H || 0)}H · {Math.round(menu.macros_metodo?.G || 0)}G
                                    </p>
                                    {(menu.cuadrada || menu.clavado) && (
                                        <span className="text-[10px] font-bold uppercase tracking-wide bg-emerald-500/15 text-emerald-500 px-2 py-0.5 rounded-full">Cuadra contigo</span>
                                    )}
                                </div>
                                <ul className="space-y-0.5">
                                    {(menu.items || []).map((it, j) => (
                                        <li key={j} className="text-sm text-foreground/80">
                                            <span className="font-bold text-brand">{it.cantidad_display}</span> {it.nombre}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ))}
                        <p className="text-xs text-foreground/50">
                            Tienes el recetario entero en Nutrición, en "Sugiéreme un menú" de cada comida.
                        </p>
                    </div>
                )}
                <div className="flex gap-3 mt-6">
                    {esUltimo ? (
                        <Button onClick={() => navigate('/welcome')}
                            className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                            Ir a mi panel <ArrowRight className="w-5 h-5 ml-2" />
                        </Button>
                    ) : (
                        <Button onClick={goNext}
                            className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                            {tieneCoach ? 'Continuar con tu perfil' : 'Continuar'} <ArrowRight className="w-5 h-5 ml-2" />
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
        // PANTALLA 12: la profesión y el sedentarismo, juntas. En pantallas seguidas se le
        // pregunta a qué se dedica y acto seguido se le pide que se clasifique en lo mismo,
        // y eso suena a que no se le ha escuchado.
        const actividad = q('actividad_diaria');
        body = (
            <div>
                <Title />
                <div className="mb-6">
                    <MiniInput {...mini} k="profesion" label="¿A qué te dedicas?" />
                </div>
                <p className="text-sm text-foreground/60 mb-3">{actividad.desc}</p>
                <div className="space-y-3">
                    {actividad.options.map(o => (
                        <button key={o.value}
                            onClick={() => { set('actividad_diaria', o.value); trasResponder('actividad_diaria', o.value); goNext(); }}
                            className={`w-full text-left px-5 py-4 rounded-xl border-2 transition-all ${
                                answers.actividad_diaria === o.value
                                    ? 'border-[#FF671F] bg-[#FF671F]/10'
                                    : 'border-[#222222] hover:border-white/30'} text-foreground`}>
                            {o.label}
                        </button>
                    ))}
                </div>
                <div className="mt-6"><BackBtn /></div>
            </div>
        );
    } else if (step.type === 'peso_hito') {
        // PANTALLAS 9, 10 y 11: cada hito de su peso con SU AÑO. Antes eran cuatro casillas
        // sueltas en una sola pantalla, sin años y solo para quien llevaba entrenador: «si
        // viene como "unos 95 hace tres años" no se puede calcular nada con él».
        const kPeso = step.key, kAno = `${step.key}_ano`, kNota = `${step.key}_nota`;
        body = (
            <div>
                <Title />
                <div className="grid grid-cols-2 gap-4 mb-4">
                    <MiniInput {...mini} k={kPeso} label="Peso" type="number" unit="kg" />
                    <MiniInput {...mini} k={kAno} label="Año" type="number" placeholder="2019" />
                </div>
                <div className="mb-4">
                    <MiniInput {...mini} k={kNota} label={step.nota} placeholder="Opcional." />
                </div>
                {step.conFoto && (
                    <div className="mb-6">
                        <p className="text-sm text-foreground/60 mb-2">
                            Sube la foto de tu mejor forma <span className="text-foreground/40">(opcional)</span>
                        </p>
                        <input type="file" accept="image/*" data-testid="foto-mejor-forma"
                            onChange={(e) => {
                                const f = e.target.files?.[0];
                                if (!f) return;
                                const reader = new FileReader();
                                reader.onload = (ev) => set('foto_mejor_momento', ev.target.result);
                                reader.readAsDataURL(f);
                            }}
                            className="text-sm text-foreground/70" />
                        {answers.foto_mejor_momento && (
                            <p className="text-xs text-brand mt-2">Foto lista.</p>
                        )}
                    </div>
                )}
                <div className="flex gap-3">
                    <BackBtn />
                    <Button onClick={goNext}
                        className="bg-brand hover:bg-brand/90 text-white font-bold px-8">
                        OK <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'elegir_perfil') {
        // EL FINAL DE QUIEN LLEVA ENTRENADOR (doc del cuestionario, 18-08). Antes de esto se
        // le metía de cabeza en el cuestionario largo sin preguntarle: veinticinco pantallas
        // más justo cuando acaba de terminar veinticuatro. Ahora elige, y si se va a la
        // calculadora le queda la tarjeta de «Completa tu perfil» en Inicio.
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-3 leading-tight">
                    Ya puedes empezar a usar la calculadora
                </h2>
                <p className="text-foreground/70 mb-4">
                    O terminamos tu perfil ahora. Los macros que tienes son provisionales, pero
                    puedes montar tu día desde ya.
                </p>
                <div className="surface p-4 mb-6 border-l-4 border-l-brand">
                    <p className="text-sm text-foreground/80">
                        Para arrancar de verdad necesitamos <strong className="text-foreground">tus fotos y tus
                        medidas</strong>: sin eso no podemos ponerte los macros buenos ni montarte la rutina.
                    </p>
                    <p className="text-xs text-foreground/50 mt-2">
                        Te apuntas cualquier día y empiezas siempre un lunes.
                    </p>
                </div>
                <div className="flex flex-col sm:flex-row gap-3">
                    <Button onClick={goNext} data-testid="terminar-perfil-ahora"
                        className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                        Terminar mi perfil ahora <ArrowRight className="w-5 h-5 ml-2" />
                    </Button>
                    <Button variant="outline" data-testid="empezar-calculadora"
                        onClick={() => navigate('/welcome')}
                        className="px-8 py-6 text-lg">
                        Empezar a usar la calculadora
                    </Button>
                </div>
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
        const yaTieneMedidas = !!(profile?.punto_de_partida_hecho || profile?.medidas_inicio);
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-3 leading-tight">
                    {yaTieneMedidas ? 'Te queda una cosa' : 'Te quedan dos cosas'}
                </h2>
                <p className="text-foreground/70 mb-6">
                    {yaTieneMedidas
                        ? 'Sube tus fotos. Con ellas y las medidas que acabas de apuntar ya puedes ver tu evolución, que es lo que de verdad enseña lo que cambia.'
                        : 'Sube tus fotos y toma tus medidas. Sin eso no puedes ver tu evolución, que es lo que de verdad enseña lo que cambia.'}
                </p>
                <div className="flex flex-col sm:flex-row gap-3">
                    <Button onClick={() => navigate('/dashboard/reports')} data-testid="ir-a-fotos-medidas"
                        className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                        Vamos <ArrowRight className="w-5 h-5 ml-2" />
                    </Button>
                    <Button variant="outline" onClick={goNext} className="px-8 py-6 text-lg">
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
                <p className="text-sm text-foreground/50 mb-6">
                    Esta segunda opción no está incluida en tu plan, tiene un coste adicional e
                    incluye también tu plan personalizado de suplementación.
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
                        {/* Las tres puertas */}
                        <div className="grid grid-cols-3 gap-2">
                            {[['texto', 'Escribirla'], ['menu', 'Un día mío'], ['foto', 'Una foto']].map(([modo, etiqueta]) => (
                                <button key={modo} onClick={() => { set('dieta_modo', modo); if (modo === 'menu') cargarMisDias(); }}
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

                        {answers.dieta_modo === 'menu' && (
                            <div className="space-y-2 max-h-64 overflow-y-auto">
                                {misDias === null && <p className="text-foreground/50 text-sm">Buscando tus días...</p>}
                                {misDias?.length === 0 && (
                                    <p className="text-foreground/50 text-sm">
                                        Todavía no tienes ningún día montado en la calculadora. Escríbela o sube una foto.
                                    </p>
                                )}
                                {misDias?.map(d => (
                                    <button key={d.fecha} onClick={() => set('dieta_fecha_menu', d.fecha)}
                                        className={`w-full text-left px-4 py-3 rounded-xl border-2 transition-all ${
                                            answers.dieta_fecha_menu === d.fecha
                                                ? 'border-brand bg-brand/10' : 'border-[#222222] hover:border-white/30'}`}>
                                        <span className="text-foreground text-sm font-semibold">{d.fecha}</span>
                                        <span className="text-foreground/50 text-xs ml-2">{plural(d.alimentos, 'alimento')}</span>
                                    </button>
                                ))}
                            </div>
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
    } else if (step.type === 'pesos') {
        body = (
            <div>
                <Title />
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
                    <MiniInput {...mini} k="peso_maximo" label="Peso máximo que has tenido" type="number" unit="kg" />
                    <MiniInput {...mini} k="peso_minimo" label="Peso mínimo (de adulto)" type="number" unit="kg" />
                    <MiniInput {...mini} k="peso_habitual" label="Peso habitual" type="number" unit="kg" />
                    <MiniInput {...mini} k="peso_mejor_momento" label="Peso en tu mejor momento físico" type="number" unit="kg" />
                </div>
                <div className="flex gap-3">
                    <BackBtn />
                    <Button onClick={goNext} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8">
                        OK <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                </div>
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
    } else if (step.type === 'historia') {
        // P18-P21 y P24-P25 juntas: son de texto corto y preguntarlas de una en una serian seis
        // pantallas seguidas sin devolverle nada, que es justo lo que el doc quiere evitar.
        body = (
            <div>
                <Title />
                <div className="space-y-4 mb-8 max-h-[55vh] overflow-y-auto pr-1">
                    <MiniInput {...mini} k="peso_maximo_cuando" label="¿Cuándo tuviste tu peso máximo?" placeholder="Por ejemplo: en 2019, o hace 3 años" />
                    {/* P19 del doc: la foto de aquel momento, opcional. Al coach le dice mucho mas
                        que el numero, porque el mismo peso es otra cosa segun como lo llevaras. */}
                    <div>
                        <label className="block text-xs font-bold text-foreground/50 uppercase tracking-wider mb-1.5">
                            Foto de aquel momento (opcional)
                        </label>
                        <button type="button" onClick={elegirFotoPesoMaximo}
                            className="w-full rounded-xl border-2 border-dashed border-[#333] py-5 text-center hover:border-brand transition-colors">
                            {answers.foto_peso_maximo ? (
                                <span className="inline-flex items-center gap-2 text-foreground/70 text-sm">
                                    <Check className="w-4 h-4 text-emerald-500" /> Foto elegida. Toca para cambiarla
                                </span>
                            ) : (
                                <span className="inline-flex items-center gap-2 text-foreground/50 text-sm">
                                    <ImagePlus className="w-5 h-5" /> Subir una foto
                                </span>
                            )}
                        </button>
                    </div>
                    <MiniInput {...mini} k="mejor_definicion_cuando"
                        label="¿Cuál ha sido tu mejor punto de definición? ¿Cuándo?"
                        placeholder='Cuándo fue, o escribe "nunca" si no has estado definido' />
                    <MiniInput {...mini} k="hasta_donde" label="¿Hasta dónde quieres llegar?" placeholder="Tu meta real: un peso, un aspecto, una talla..." />
                    <MiniInput {...mini} k="dieta_que_funciona" label="¿Qué tipo de dieta consideras que te funciona mejor?" placeholder="Y por qué crees que contigo funciona" />
                    <MiniInput {...mini} k="por_que_fallaron" label="¿Por qué crees que no te han funcionado las dietas anteriores?" placeholder='Si nunca has hecho, escribe "no he hecho"' />
                </div>
                <div className="flex gap-3">
                    <BackBtn />
                    <Button onClick={goNext} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8">
                        OK <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'salud') {
        body = (
            <div>
                <Title />
                <div className="space-y-5 mb-8 max-h-[55vh] overflow-y-auto pr-1">
                    <div>
                        <label className="block text-xs font-bold text-foreground/50 uppercase tracking-wider mb-2">¿Cómo duermes?</label>
                        <MiniChoice {...mini} k="salud_sueno" options={[
                            { value: 'bien', label: 'Bien (7-8h)' },
                            { value: 'regular', label: 'Regular' },
                            { value: 'mal', label: 'Mal (poco o roto)' },
                        ]} />
                    </div>
                    <div>
                        <label className="block text-xs font-bold text-foreground/50 uppercase tracking-wider mb-2">¿Nivel de estrés en tu día a día?</label>
                        <MiniChoice {...mini} k="salud_estres" options={[
                            { value: 'bajo', label: 'Bajo' },
                            { value: 'medio', label: 'Medio' },
                            { value: 'alto', label: 'Alto' },
                        ]} />
                    </div>
                    <MiniInput {...mini} k="salud_medicacion" label="¿Tomas medicación? ¿Cuál?" placeholder='Si no, escribe "no"' />
                    <MiniInput {...mini} k="salud_hormonal" label="¿Algún problema hormonal (tiroides, etc.)?" placeholder='Si no, escribe "no"' />
                    <MiniInput {...mini} k="salud_lesiones" label="¿Lesiones o molestias a tener en cuenta?" placeholder='Si no, escribe "no"' />
                </div>
                <div className="flex gap-3">
                    <BackBtn />
                    <Button onClick={goNext} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8">
                        OK <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                </div>
            </div>
        );
    } else if (step.type === 'multiselect') {
        const selected = answers[step.key] || [];
        const toggle = (v) => {
            const next = selected.includes(v) ? selected.filter(x => x !== v) : [...selected, v];
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
        body = (
            <div>
                <Title />
                <BodyFatSlider value={answers.body_fat} onChange={(v) => set('body_fat', v)}
                    sexo={answers.sex} />
                {/* LA COLETILLA CAMBIA SEGÚN SU PLAN (doc del 18-08, pantalla 8). A quien
                    lleva entrenador se le quita el peso de encima -- se lo van a revisar con
                    sus fotos -- y a quien no, se le dice desde el primer día que esto lo
                    repite él cada doce semanas. */}
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
    const pasosTramo1 = modoAjuste ? STEPS_AJUSTE.length : flow.length;
    const enTramo1 = idx < pasosTramo1;
    const progresoTramo = enTramo1
        ? ((idx + 1) / pasosTramo1) * 100
        : ((idx + 1 - pasosTramo1) / Math.max(1, flow.length - pasosTramo1)) * 100;
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
        </Shell>
    );
};

export default QuestionnairePage;
