import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { CAP } from '../lib/planAccess';
import { seLeOfreceLaRevision } from '../lib/revision';
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
const STEPS_ALTA = [
    { type: 'statement', title: 'Empecemos', desc: 'Cuatro preguntas y tienes tus macros. Un minuto.' },
    {
        type: 'choice', key: 'sex', title: '¿Cuál es tu sexo?',
        desc: 'Lo usamos para calcular tus macros con la tabla correcta.',
        options: [
            { value: 'hombre', label: 'Hombre' },
            { value: 'mujer', label: 'Mujer' },
        ],
    },
    {
        type: 'choice', key: 'goal', title: 'Lo más importante de todo: ¿Cuál es tu objetivo?',
        desc: 'Una de dos: ganar masa muscular o perder grasa. Las dos a la vez, NO. Piensa, prioriza y elige.',
        options: [
            { value: 'volumen', label: 'Quiero ganar Masa Muscular (VOLUMEN)' },
            { value: 'definicion', label: 'Quiero perder Grasa (DEFINICIÓN)' },
        ],
    },
    {
        type: 'choice', key: '_confirm', title: '¿Estás seguro?',
        desc: 'Mira bien, que luego no quiero que me digas que en realidad querías lo otro.',
        // opciones dinámicas según goal (se generan en render)
        confirm: true,
    },
    { type: 'number', key: 'weight', title: '¿Cuánto pesas?', desc: 'Pésate siempre igual: en ayunas, sin ropa y después de ir al baño.', unit: 'kg', required: true },
    { type: 'bf', key: 'body_fat', title: '¿Cuál dirías que es tu porcentaje de grasa actual?', desc: 'Elige el valor más cercano a tu % de grasa estimado.' },
    { type: 'final0', title: 'Ya está.', desc: 'Con esto ya podemos calcular tus macros de partida. Si quieres revisar alguna respuesta, ve hacia atrás.' },
    { type: 'result', title: 'Tus macros' },
];

// ─────────────────────────────────────────────────────────────────────────────
// AJUSTAR MACROS - el cuestionario del paso 2, detras de un boton.
//
// Todo lo que afina el numero: lo que hace fuera del gimnasio, como responde su cuerpo y la
// dieta que trae. Al terminar se le entregan los MACROS DEFINITIVOS.
const STEPS_AJUSTE = [
    { type: 'statement', title: 'Afina tus macros', desc: 'Unas preguntas para ajustar tus números a tu vida real. Verás los macros moverse a medida que contestas.', cta: 'Vamos' },
    {
        type: 'choice', key: 'actividad_diaria', title: '¿Cómo es tu actividad diaria, fuera del gimnasio?',
        desc: 'Ir al gimnasio 1h 4-5 veces/semana no te hace activo. Piensa en cuánto te mueves en tu día a día.',
        options: [
            { value: 'sedentario', label: 'Sedentario: paso casi todo el día sentado, apenas me muevo.' },
            { value: 'normal', label: 'Normal: me muevo a diario, pero sin esfuerzos físicos importantes.' },
            { value: 'muy_activo', label: 'Muy activo: mi día a día es muy demandante físicamente, no paro.' },
        ],
    },
    {
        type: 'choice', key: 'deporte_extra', title: '¿Practicas otro deporte además de las pesas?',
        desc: 'Fútbol, running, ciclismo, artes marciales... cualquier deporte con regularidad.',
        options: [
            { value: true, label: 'Sí' },
            { value: false, label: 'No' },
        ],
    },
    {
        type: 'choice', key: 'facilidad_engordar', title: 'Cuando te pasas comiendo, ¿engordas?',
        desc: 'Piensa en vacaciones, Navidades o épocas en las que comiste de más.',
        options: [
            { value: 'enseguida', label: 'Enseguida: en cuanto me descuido, subo de peso.' },
            { value: 'normal', label: 'Normal: si me paso una temporada, se nota.' },
            { value: 'casi_no', label: 'Casi no: puedo comer de más y apenas engordo.' },
        ],
    },
    {
        // P5 del doc: se guarda, no mueve los macros.
        type: 'choice', key: 'cuesta_definir', title: '¿Te cuesta definir?',
        desc: 'Nos ayuda a situarte entre los clientes que ya han pasado por aquí.',
        options: [
            { value: 'mucho', label: 'Mucho: siempre me ha costado quitarme la grasa.' },
            { value: 'normal', label: 'Lo normal: con esfuerzo, lo consigo.' },
            { value: 'poco', label: 'Poco: defino con facilidad.' },
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
        // Tres respuestas, no dos. Faltaba la de en medio, que es la más común: come
        // siempre parecido pero no lo tiene medido. Con dos opciones esa persona marcaba
        // "no controlo" y se perdía su dieta real, que es el mejor dato que hay.
        type: 'choice', key: 'sigue_dieta', title: '¿Sigues una dieta ahora mismo?',
        desc: 'Si controlas más o menos tus cantidades, podremos partir de lo que ya comes.',
        options: [
            { value: true, label: 'Sí, y sé exactamente lo que como.' },
            { value: 'parecido', label: 'Como siempre parecido, pero no lo tengo medido.' },
            { value: false, label: 'No, como lo que surge.' },
        ],
    },
    {
        // P7: se guarda. Un mes comiendo asi no dice lo mismo que seis.
        type: 'choice', key: 'tiempo_dieta', title: '¿Cuánto tiempo llevas con esa dieta, o con una parecida?',
        cond: a => a.sigue_dieta !== false && a.sigue_dieta != null,
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
        title: a => (a.sigue_dieta === false
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
        cond: a => a.sigue_dieta !== false && a.sigue_dieta != null,
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
        type: 'dieta', title: 'Cuéntanos qué comes',
        desc: a => (a.sigue_dieta === 'parecido'
            ? 'Aunque no comas siempre lo mismo, ponme un día tipo. El de ayer, por ejemplo.'
            : 'Con esto partimos de tu dieta real en vez de empezar de cero.'),
        cond: a => a.sigue_dieta !== false && a.sigue_dieta != null,
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
    { type: 'statement', title: 'Ahora, tu perfil completo', desc: 'Unas preguntas más para el equipo: le sirven para tu estrategia, tu rutina y tus menús. Estas ya no cambian tus macros.', cta: 'Seguir' },
    { type: 'date', key: 'birthdate', title: 'Fecha de nacimiento', desc: 'La verdadera, no me engañes.', required: true },
    {
        // P13 del doc: los tramos son los suyos (menos de 1, 1-3, 3-10, mas de 10, y el que
        // entreno antes pero lleva parado, que no es lo mismo que empezar de cero).
        type: 'choice', key: 'training_experience', title: '¿Cuántos años llevas entrenando con pesas de forma regular?',
        desc: 'Me da igual tu desarrollo muscular actual: me interesa la experiencia que tienes entrenando.',
        options: [
            { value: 'menos_1', label: 'Menos de 1 año' },
            { value: '1_3', label: 'Entre 1 y 3 años' },
            { value: '3_10', label: 'Entre 3 y 10 años' },
            { value: 'mas_10', label: 'Más de 10 años' },
            { value: 'parado', label: 'He entrenado antes, pero llevo tiempo parado' },
        ],
    },
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
        options: [
            { value: 'menos_6m', label: 'Menos de 6 meses' },
            { value: '6m_2a', label: 'Entre 6 meses y 2 años' },
            { value: 'mas_2a', label: 'Más de 2 años' },
            { value: 'siempre', label: 'Toda la vida' },
        ],
    },
    {
        // P26, el cierre
        type: 'choice', key: 'motivo_apuntarse', title: '¿Cuál ha sido el motivo principal para apuntarte?',
        options: [
            { value: 'saturado', label: 'Estoy saturado de dietas' },
            { value: 'esfuerzo_sin_premio', label: 'Me esfuerzo mucho y mejoro poco' },
            { value: 'no_se_como', label: 'No sé cómo hacerlo por mi cuenta' },
            { value: 'evento', label: 'Tengo una fecha concreta (boda, verano, competición...)' },
            { value: 'salud', label: 'Por salud' },
        ],
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
    { type: 'text', key: 'alergias', title: '¿Alergias o intolerancias alimentarias?', desc: 'Si no tienes, escribe "no".', textarea: true },
    { type: 'final1', title: 'Perfil completo.', desc: 'El equipo usará todo esto para tu estrategia. Las fotos de progreso te las pedirán por el chat. Si quieres revisar algo, ve hacia atrás.' },
];

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
            {linea('Peri', macros.perientreno?.hidratos, previos?.perientreno?.hidratos)}
        </div>
    );
};

const Shell = ({ progress, children, tramo, cabecera }) => (
    <div className="min-h-screen bg-background relative overflow-hidden flex flex-col">
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
                <Logo12EN12 size="sm" tone="dark" />
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
    // Momento mágico: primeros menús del banco personal (null = cargando).
    const [menusMagia, setMenusMagia] = useState(null);
    // Macros recalculados a cada respuesta, para verlos moverse. No se aplican: son un avance.
    const [vistaPrevia, setVistaPrevia] = useState(null);
    const [calculandoVivo, setCalculandoVivo] = useState(false);
    const progresoCargadoRef = useRef(false);
    // Los macros de antes de la ultima respuesta, para poder mostrar cuanto se ha movido cada uno.
    const previosRef = useRef(null);
    // Punto de partida: fotos subidas y la ficha que se le entrega a cambio.
    const [fotosPartida, setFotosPartida] = useState(0);
    const [subiendoFotos, setSubiendoFotos] = useState(false);
    const [ficha, setFicha] = useState(null);
    // P10: lo que hemos entendido de su dieta, pendiente de que lo confirme.
    const [lecturaDieta, setLecturaDieta] = useState(null);
    const [leyendoDieta, setLeyendoDieta] = useState(false);
    const [misDias, setMisDias] = useState(null);   // null = sin pedir todavia

    // Nivel 1 solo para planes con coach (calculadora == 'personalizado').
    const tieneCoach = can(CAP.MACROS_PERSONALIZADOS);
    // Si ha pulsado "Ajustar macros" manda eso y nada más: sin esta comprobación, un cliente con
    // coach que le diera al botón acababa en el perfil largo en vez de en el cuestionario.
    const pidioAjustar = new URLSearchParams(location.search).get('ajustar') === '1';
    // Retomar: Nivel 0 hecho en otra sesión pero Nivel 1 pendiente.
    const retomandoNivel1 = !pidioAjustar && !!profile?.questionnaire_completed && !nivel0Enviado
        && tieneCoach && !profile?.questionnaire_nivel1_completed;

    // Dos modos, como pide el doc del 29-07:
    //   ALTA   -> cuatro preguntas y macros provisionales. Es lo que ve quien acaba de entrar.
    //   AJUSTE -> el cuestionario que afina, detras del boton "Ajustar macros". Se llega con
    //             ?ajustar=1, o solo con el alta ya hecha (por si vuelve por el enlace).
    const modoAjuste = pidioAjustar
        || (!!profile?.questionnaire_completed && !nivel0Enviado && !retomandoNivel1);

    const flow = retomandoNivel1
        ? STEPS_NIVEL1
        : modoAjuste
            ? [...STEPS_AJUSTE, ...STEPS_ONBOARD, ...(tieneCoach ? STEPS_NIVEL1 : [])]
            : STEPS_ALTA;

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

    // Retomar el cuestionario de ajuste donde lo dejó, y arrancar la cabecera con los macros
    // que tiene ahora mismo (los provisionales del alta) para que se vea de dónde parte.
    useEffect(() => {
        if (!modoAjuste || progresoCargadoRef.current || !profile) return;
        progresoCargadoRef.current = true;
        const guardado = profile.ajuste_macros_progreso;
        if (guardado?.respuestas && Object.keys(guardado.respuestas).length) {
            answersRef.current = { ...answersRef.current, ...guardado.respuestas };
            setAnswers(a => ({ ...a, ...guardado.respuestas }));
            const paso = Number(guardado.paso) || 0;
            if (paso > 0 && paso < flow.length) setIdx(paso);
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
        answersRef.current = {
            ...answersRef.current,
            sex: answersRef.current.sex ?? profile.sex ?? undefined,
            goal: answersRef.current.goal ?? profile.goal ?? undefined,
        };
        setAnswers(a => ({
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
    const guardarProgreso = useCallback((respuestas, paso) => {
        if (!modoAjuste) return;
        api.put('/clients/ajuste-progreso', { respuestas, paso }).catch(() => {});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [api, modoAjuste]);

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
    if (profile?.questionnaire_completed && !nivel0Enviado && !retomandoNivel1 && !pidioAjustar) {
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


    // ── Punto de partida: fotos y medidas del dia 1 ──────────────────────────
    // Las fotos van por el endpoint de siempre (multipart), que ya sabe validarlas y guardarlas
    // en disco; aqui solo se eligen y se suben.
    const elegirFotosPartida = () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.multiple = true;
        input.onchange = async (ev) => {
            const files = [...(ev.target.files || [])];
            if (!files.length) return;
            setSubiendoFotos(true);
            let subidas = 0;
            for (const file of files) {
                try {
                    const fd = new FormData();
                    fd.append('file', file);
                    const r = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/reports/photos`, {
                        method: 'POST',
                        headers: { Authorization: `Bearer ${token}` },
                        body: fd,
                    });
                    if (r.ok) subidas += 1;
                    else {
                        const e = await r.json().catch(() => ({}));
                        toast.error(e.detail || `No se ha podido subir ${file.name}`);
                    }
                } catch (e) {
                    toast.error(`No se ha podido subir ${file.name}`);
                }
            }
            setFotosPartida(n => n + subidas);
            setSubiendoFotos(false);
            if (subidas) toast.success(`${subidas} foto${subidas > 1 ? 's' : ''} guardada${subidas > 1 ? 's' : ''}`);
        };
        input.click();
    };

    const guardarPuntoDePartida = async () => {
        const medidas = {};
        for (const [clave, campo] of [['cintura', 'medida_cintura'], ['abdomen', 'medida_abdomen'],
                                      ['cadera', 'medida_cadera']]) {
            const n = num(answers[campo]);
            if (n) medidas[clave] = n;
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
            toast.error(e.response?.data?.detail || 'No hemos podido leer tu dieta');
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
    const goBack = () => setIdx(i => {
        let j = i - 1;
        while (j > 0 && !visible(flow[j])) j--;
        return Math.max(j, 0);
    });

    const num = (v) => { const n = parseFloat(v); return isNaN(n) ? null : n; };

    // Las respuestas que afinan los macros, en el formato que espera el backend.
    // Recibe las respuestas por parametro para poder calcular con las de ESTE instante: el
    // estado de React aun no se ha actualizado cuando se acaba de pulsar una opcion.
    const ajustesDe = (a) => ({
        actividad_diaria: a.actividad_diaria ?? null,
        deporte_extra: a.deporte_extra ?? null,
        facilidad_engordar: a.facilidad_engordar ?? null,
        cuesta_definir: a.cuesta_definir ?? null,
        sigue_dieta: a.sigue_dieta ?? null,
        tiempo_dieta: a.sigue_dieta ? (a.tiempo_dieta ?? null) : null,
        como_va: a.sigue_dieta ? (a.como_va ?? null) : null,
        hambre_saturacion: a.sigue_dieta ? (a.hambre_saturacion ?? null) : null,
        dieta_texto: a.sigue_dieta ? (a.dieta_texto || null) : null,
        dieta_hc_entreno: a.sigue_dieta ? num(a.dieta_hc_entreno) : null,
        dieta_grasa_entreno: a.sigue_dieta ? num(a.dieta_grasa_entreno) : null,
        dieta_confirmada: a.dieta_confirmada === true,
    });

    const ajustesDelCuestionario = () => ({
        actividad_diaria: answers.actividad_diaria ?? null,
        deporte_extra: answers.deporte_extra ?? null,
        facilidad_engordar: answers.facilidad_engordar ?? null,
        cuesta_definir: answers.cuesta_definir ?? null,
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
    const conDieta = () => answers.sigue_dieta !== false && answers.sigue_dieta != null;

    // CALCULAR. En el alta van los cuatro datos de la tabla y salen macros provisionales; en el
    // cuestionario de ajuste van las respuestas que afinan y salen los definitivos.
    const submitNivel0 = async () => {
        setLoading(true);
        try {
            const res = modoAjuste
                ? await api.post('/clients/ajustar-macros', ajustesDelCuestionario())
                : await api.post('/clients/questionnaire', {
                    name: answers.name,
                    email: answers.email,
                    phone: answers.phone,
                    goal: answers.goal,
                    sex: answers.sex,
                    weight: parseFloat(answers.weight),
                    body_fat: parseFloat(answers.body_fat),
                });
            setResultado(res.data?.resultado || null);
            setEntrega(res.data?.entrega || null);
            setNivel0Enviado(true);
            await refreshProfile();
            toast.success('¡Macros calculados!');
            goNext(); // -> pantalla de resultados
        } catch (e) {
            toast.error(e.response?.data?.detail || 'Error al enviar el cuestionario');
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
            toast.error(e.response?.data?.detail || 'Error al guardar el perfil');
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
        // antes de pasar a la siguiente pregunta.
        setTimeout(goNext, modoAjuste ? 550 : 150);
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
                    <Logo12EN12 size="xl" tone="dark" />
                </div>
                <h2 className="font-heading font-bold text-4xl md:text-5xl uppercase tracking-tight text-foreground mb-3">{step.title}</h2>
                {step.desc && <p className="text-foreground/60 mb-10 text-base max-w-md mx-auto">{step.desc}</p>}
                <Button onClick={goNext}
                    className="bg-brand hover:bg-brand/90 text-white font-bold uppercase tracking-wider px-10 py-6 text-lg">
                    Empezar <BrandArrow className="w-5 h-5 ml-2 text-white" />
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
        body = (
            <div>
                <Title />
                <div className="flex gap-3">
                    <BackBtn />
                    <Button onClick={isN0 ? submitNivel0 : submitNivel1} disabled={loading}
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8 py-6 text-lg">
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
                {/* En el alta son PROVISIONALES y hay que decirlo con esas palabras: ya puede comer
                    hoy, y afinarlos es el paso siguiente. Tras el cuestionario, son los definitivos. */}
                {/* Tres mensajes distintos (doc 29-07): provisionales en el alta; en el ajuste,
                    definitivos si el plan se autogestiona, o "de partida, tu coach los revisa" si
                    hay entrenador detrás. Al que paga más no se le deja esperando con peores
                    números: ya tiene los suyos y encima se los van a repasar. */}
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-2 leading-tight">
                    {/* Al del plan con coach hay que decirle con estas palabras que lo que
                        tiene NO es lo definitivo: si no, se queda con estos números
                        creyendo que son los suyos y luego le cambian sin entender por qué. */}
                    {!modoAjuste && tieneCoach ? 'Estos son tus macros provisionales'
                        : !modoAjuste ? 'Tus macros de partida'
                        : entrega?.con_entrenador ? 'Tus macros de partida'
                        : 'Estos son tus macros de inicio'}
                </h2>
                <p className="text-foreground/60 mb-6 text-sm md:text-base">
                    {!modoAjuste && tieneCoach
                        /* Texto de Jesús, literal. Así tiene con qué empezar desde el
                           minuto uno y sabe que lo que tiene no es lo definitivo. */
                        ? 'No son los definitivos. Son para que puedas empezar a usar la app desde hoy, mientras tu entrenador revisa tu caso. Completa tu cuestionario inicial y en menos de 48 horas tendrás tus macros definitivos.'
                        : !modoAjuste
                        ? 'Ya puedes empezar a comer hoy. Termina de ajustarlos para afinarlos a tu caso.'
                        /* Sin entrenador asignado no se dice "tu entrenador": casi ningún
                           cliente tiene uno puesto y prometer una persona que no existe se
                           nota. Quien lo revisa entonces es el equipo, que es la verdad. */
                        : entrega?.con_entrenador
                            ? `${entrega.coach || 'El equipo'} los va a revisar contigo${entrega.proxima_revision ? ` el ${entrega.proxima_revision}` : ''} y los ajustará a tu caso.`
                            /* Texto cerrado por Jesús el 06-08-2026 (momento 1 de la revisión
                               suelta): lo que sostiene el número es el perfil parecido, y así
                               se le cuenta. La próxima revisión automática se queda donde
                               estaba, al final de la misma línea: el documento no dice nada de
                               ella, y lo que no toca se deja como está. */
                            : `Están adaptados a tu perfil, a partir de tus respuestas y tomando como referencia otros perfiles parecidos al tuyo.${entrega?.proxima_revision ? ` Tu próxima revisión automática será el ${entrega.proxima_revision}.` : ''}`}
                </p>
                {m ? (
                    <div className="space-y-4">
                        <div className="grid grid-cols-3 gap-3 text-center">
                            {[
                                ['Día de entreno', m.entreno.proteina, m.entreno.hidratos, m.entreno.grasa],
                                ['Perientreno', m.perientreno.proteina, m.perientreno.hidratos, null],
                                ['Día de descanso', m.descanso.proteina, m.descanso.hidratos, m.descanso.grasa],
                            ].map(([lbl, p, h, g]) => (
                                <div key={lbl} className="rounded-xl border-2 border-[#222222] bg-card py-4 px-2">
                                    <p className="text-[11px] text-foreground/50 uppercase font-bold mb-2">{lbl}</p>
                                    <p className="font-heading font-extrabold text-2xl text-brand">{p}<span className="text-foreground/40 text-base">P</span></p>
                                    <p className="font-heading font-extrabold text-2xl text-brand">{h}<span className="text-foreground/40 text-base">H</span></p>
                                    {g != null && <p className="font-heading font-extrabold text-2xl text-brand">{g}<span className="text-foreground/40 text-base">G</span></p>}
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

                <div className="flex flex-col sm:flex-row gap-3 mt-8">
                    {modoAjuste ? (
                        <Button onClick={goNext}
                            className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                            Continuar <ArrowRight className="w-5 h-5 ml-2" />
                        </Button>
                    ) : (
                        <>
                            <Button onClick={() => navigate('/questionnaire?ajustar=1')}
                                className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
                                {/* Para el de coach no es "ajustar macros": es completar su
                                    cuestionario, que es lo que espera su entrenador. */}
                                {tieneCoach ? 'Completar mi cuestionario' : 'Ajustar mis macros'} <ArrowRight className="w-5 h-5 ml-2" />
                            </Button>
                            <Button variant="ghost" onClick={() => navigate('/dashboard')}
                                className="text-foreground/60 py-6 text-base">
                                Lo hago más tarde
                            </Button>
                        </>
                    )}
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
        const esUltimo = !tieneCoach;
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
                            Continuar con tu perfil <ArrowRight className="w-5 h-5 ml-2" />
                        </Button>
                    )}
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
                                        <span className="text-foreground/50 text-xs ml-2">{d.alimentos} alimentos</span>
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
                            <p className="text-foreground text-base mb-3">
                                He entendido que estás comiendo{' '}
                                <strong className="text-brand">{lecturaDieta.macros.hidratos} g de hidratos</strong>,{' '}
                                <strong className="text-brand">{lecturaDieta.macros.proteina} g de proteína</strong> y{' '}
                                <strong className="text-brand">{lecturaDieta.macros.grasa} g de grasa</strong>. ¿Es correcto?
                            </p>
                            <ul className="text-xs text-foreground/50 space-y-0.5 max-h-40 overflow-y-auto">
                                {lecturaDieta.alimentos.map((a, i) => (
                                    <li key={i}>{a.cantidad_g} g · {a.nombre}</li>
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
        // Fotos y medidas del dia 1. Se piden aqui porque es el momento de mas ganas, y porque
        // sin una foto de hoy dentro de un mes no hay con que comparar.
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-2 leading-tight">
                    Ya tienes tus macros
                </h2>
                <p className="text-foreground/60 mb-6 text-sm md:text-base">
                    Hazte las fotos de hoy para poder comparar dentro de un mes. Es lo único que no
                    se puede recuperar después.
                </p>

                <div className="space-y-4 mb-6">
                    <div>
                        <label className="block text-xs font-bold text-foreground/50 uppercase tracking-wider mb-1.5">
                            Tus fotos de hoy
                        </label>
                        <button type="button" onClick={elegirFotosPartida} disabled={subiendoFotos}
                            className="w-full rounded-xl border-2 border-dashed border-[#333] py-7 text-center hover:border-brand transition-colors disabled:opacity-50">
                            {subiendoFotos ? (
                                <span className="inline-flex items-center gap-2 text-foreground/60 text-sm">
                                    <Loader2 className="w-4 h-4 animate-spin" /> Subiendo...
                                </span>
                            ) : fotosPartida > 0 ? (
                                <span className="inline-flex items-center gap-2 text-foreground/80 text-sm">
                                    <Check className="w-4 h-4 text-emerald-500" /> {fotosPartida} foto{fotosPartida > 1 ? 's' : ''} subida{fotosPartida > 1 ? 's' : ''}. Toca para añadir más
                                </span>
                            ) : (
                                <span className="inline-flex items-center gap-2 text-foreground/50 text-sm">
                                    <ImagePlus className="w-5 h-5" /> Subir fotos (frente, lateral y espalda)
                                </span>
                            )}
                        </button>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                        <MiniInput {...mini} k="medida_cintura" label="Cintura" type="number" unit="cm" placeholder="85" />
                        <MiniInput {...mini} k="medida_abdomen" label="Abdomen" type="number" unit="cm" placeholder="90" />
                        <MiniInput {...mini} k="medida_cadera" label="Cadera" type="number" unit="cm" placeholder="98" />
                        {!answers.height && (
                            <MiniInput {...mini} k="height" label="Altura" type="number" unit="cm" placeholder="178" />
                        )}
                    </div>
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
                <BodyFatSlider value={answers.body_fat} onChange={(v) => set('body_fat', v)} />
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
