import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { CAP } from '../lib/planAccess';
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

// Referencias de % de grasa (de mayor a menor), réplica del carrusel de la web.
const BF_PERCENTAGES = [50, 48, 46, 44, 42, 40, 38, 36, 34, 32, 30, 28, 26, 24, 22, 20, 18, 16, 14, 12, 10, 8];
const BF_DEFAULT = 20;

// Slider de % de grasa: carrusel horizontal de imágenes de referencia con la
// foto del cliente fija en el centro. Se desliza hasta situar la foto entre dos
// porcentajes; el valor es el de la referencia que queda centrada.
const BodyFatSlider = ({ value, onChange }) => {
    const scrollRef = useRef(null);
    const [photo, setPhoto] = useState(null);

    const handleScroll = useCallback(() => {
        const el = scrollRef.current;
        if (!el) return;
        const col = el.clientWidth / 3; // 3 columnas visibles
        const i = Math.max(0, Math.min(BF_PERCENTAGES.length - 1, Math.round(el.scrollLeft / col)));
        const pct = BF_PERCENTAGES[i];
        if (pct !== value) onChange(pct);
    }, [value, onChange]);

    // Posicionar el carrusel en el valor inicial al montar.
    useEffect(() => {
        const el = scrollRef.current;
        if (!el) return;
        const start = value ?? BF_DEFAULT;
        const i = BF_PERCENTAGES.indexOf(start);
        el.scrollLeft = (i < 0 ? BF_PERCENTAGES.indexOf(BF_DEFAULT) : i) * (el.clientWidth / 3);
        if (value == null) onChange(start);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const pickPhoto = () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = (ev) => {
            const file = ev.target.files?.[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (e) => setPhoto(e.target.result);
            reader.readAsDataURL(file);
        };
        input.click();
    };

    return (
        <div>
            <style>{`.bf-scroll::-webkit-scrollbar{height:6px}.bf-scroll::-webkit-scrollbar-track{background:transparent}.bf-scroll::-webkit-scrollbar-thumb{background:#FF671F;border-radius:9999px}`}</style>

            <div className="text-center mb-4">
                <span className="font-heading font-extrabold text-5xl text-brand">{value ?? BF_DEFAULT}%</span>
            </div>

            <div className="relative rounded-xl overflow-hidden border-2 border-[#222222] select-none" style={{ aspectRatio: '1800 / 933' }}>
                {/* Foto del cliente, fija en el centro (clic para subir). */}
                <button type="button" onClick={pickPhoto}
                    className="absolute top-0 bottom-0 left-1/3 w-1/3 z-30 flex flex-col items-center justify-center bg-[#e9eae5] cursor-pointer overflow-hidden"
                    style={photo ? { backgroundImage: `url(${photo})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}}>
                    {!photo && (
                        <>
                            <ImagePlus className="w-7 h-7 text-black/40" />
                            <span className="text-black/50 text-xs font-bold mt-2 px-2 text-center leading-tight">Sube tu foto</span>
                        </>
                    )}
                </button>

                {/* Carrusel de referencias. */}
                <div ref={scrollRef} onScroll={handleScroll}
                    className="bf-scroll h-full flex overflow-x-scroll overflow-y-hidden scroll-smooth">
                    <div className="flex-shrink-0 w-1/3 h-full" aria-hidden="true" />
                    {BF_PERCENTAGES.map((n) => (
                        <div key={n} className="relative flex-shrink-0 w-1/3 h-full border-r-4 border-white/80 last:border-r-0">
                            <img src={`/bodyfat/frente/${n}.webp`} alt={`${n}%`} draggable="false"
                                className="w-full h-full object-cover" />
                            <span className="absolute inset-x-0 bottom-[8%] flex items-end justify-center font-extrabold text-3xl text-white"
                                style={{ textShadow: '1px 1px 6px rgba(0,0,0,.9)' }}>{n}%</span>
                        </div>
                    ))}
                    <div className="flex-shrink-0 w-1/3 h-full" aria-hidden="true" />
                </div>
            </div>

            <p className="text-foreground/50 text-xs mt-3 text-center">
                Sube tu foto y desliza el carrusel hasta situarla entre dos porcentajes.
            </p>
        </div>
    );
};

// ─────────────────────────────────────────────────────────────────────────────
// NIVEL 0 - lo contesta TODO EL MUNDO (estas preguntas SÍ mueven los macros).
// type: statement | text | email | tel | date | number | choice | bf | dieta | final0 | result
const STEPS_NIVEL0 = [
    { type: 'statement', title: 'Quiz Inicial', desc: 'Vamos a conocerte para calcular tus macros. Tardarás un par de minutos. Responde con sinceridad.' },
    { type: 'text', key: 'name', title: 'Nombre y apellidos', required: true },
    { type: 'tel', key: 'phone', title: 'Número de teléfono', required: true },
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
    { type: 'statement', title: 'Afina tus macros', desc: 'Cuatro preguntas rápidas para ajustar tus números a tu vida real. Responde con sinceridad: cada respuesta cuenta.', cta: 'Vamos' },
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
        type: 'choice', key: 'sigue_dieta', title: '¿Sigues una dieta ahora mismo y sabes lo que comes?',
        desc: 'Si controlas más o menos tus cantidades, podremos partir de lo que ya comes.',
        options: [
            { value: true, label: 'Sí, sé lo que como.' },
            { value: false, label: 'No, como sin controlar.' },
        ],
    },
    { type: 'dieta', title: 'Cuéntanos qué comes', desc: 'Con esto partimos de tu dieta real en vez de empezar de cero.', cond: a => a.sigue_dieta === true },
    { type: 'final0', title: 'Y ya estaría.', desc: 'Si quieres revisar alguna respuesta, ve hacia atrás. Al calcular verás tus macros personalizados.' },
    { type: 'result', title: 'Tus macros' },
];

// Onboarding tras el quiz (doc "FLUJO COMPLETO" 17-07): preferencias en asistente
// (una cosa por pantalla) y el "momento mágico" (primeros menús del banco personal).
// Pantallas pendientes de revisión por Jesús: montadas con piezas reutilizables.
const STEPS_ONBOARD = [
    { type: 'statement', title: 'Ahora, tus gustos', desc: 'Con tus macros y tus gustos, la app te prepara un banco de menús a tu medida: comida real que ya cuadra contigo. Un minuto más y lo ves.', cta: 'Vamos' },
    {
        type: 'choice', key: 'pref_num_comidas', title: '¿Cuántas comidas quieres hacer al día?',
        desc: 'Sin contar el perientreno. Podrás cambiarlo cuando quieras desde Nutrición.',
        options: [
            { value: 3, label: '3 comidas' },
            { value: 4, label: '4 comidas' },
        ],
    },
    {
        type: 'choice', key: 'pref_dias_entreno', title: '¿Cuántos días entrenas por semana?',
        options: [
            { value: 2, label: '2 días' }, { value: 3, label: '3 días' }, { value: 4, label: '4 días' },
            { value: 5, label: '5 días' }, { value: 6, label: '6 días' },
        ],
    },
    { type: 'momento', key: 'pref_momento', title: '¿Cuándo sueles entrenar?', desc: 'Con esto colocamos tu perientreno (intra y post) en el momento correcto del día.' },
    { type: 'prefs', title: 'Tus alimentos' },
    { type: 'magia', title: 'Comidas que puedes comer hoy' },
];

// NIVEL 1 - solo planes con coach. Alimenta el perfil y el caso gemelo; NO toca macros.
const STEPS_NIVEL1 = [
    { type: 'statement', title: 'Ahora, tu perfil completo', desc: 'Unas preguntas más para tu coach: le sirven para tu estrategia, tu rutina y tus menús. Estas ya no cambian tus macros.', cta: 'Seguir' },
    { type: 'biotype_intro', title: 'Ahora tienes que elegir tu biotipo, es decir, tu tipo de cuerpo.', desc: 'Es la tendencia natural de tu cuerpo según tu genética (independientemente de tu estado físico actual o los hábitos que tengas en este momento). Antes te explico los 7 que hay (después eliges):' },
    { type: 'biotype', key: 'biotype', title: 'Indica cuál de los 7 biotipos corporales es el tuyo', desc: 'Puedes volver atrás y leer las descripciones. Si no te identificas claramente con ninguno, elige el que más se acerque a ti.' },
    { type: 'number', key: 'height', title: '¿Cuánto mides?', desc: 'Tu altura, en cm.', unit: 'cm', required: true },
    { type: 'date', key: 'birthdate', title: 'Fecha de nacimiento', desc: 'La verdadera, no me engañes.', required: true },
    {
        type: 'choice', key: 'training_experience', title: '¿Qué experiencia tienes entrenando fuerza en el gimnasio?',
        desc: 'Me da igual tu desarrollo muscular actual, me interesa saber si sabes entrenar y cuánta experiencia tienes.',
        options: [
            { value: 'cero', label: 'Ninguna, empiezo ahora o hace mucho que no entreno. Parto de cero.' },
            { value: 'principiante', label: 'Llevo menos de 1 año entrenando con regularidad (principiante).' },
            { value: 'intermedio', label: 'Llevo más de un año, aunque no siempre en serio (intermedio).' },
            { value: 'avanzado', label: 'Llevo años entrenando de forma seria (avanzado).' },
        ],
    },
    { type: 'pesos', title: 'Tu historial de peso', desc: 'Aproximado, en kg. Ayuda a tu coach a entender tu recorrido.' },
    { type: 'salud', title: 'Salud y descanso', desc: 'Sé sincero: todo esto condiciona tu estrategia.' },
    { type: 'text', key: 'dietas_previas', title: '¿Has hecho dietas antes? ¿Qué tal te fue?', desc: 'Cuáles, cuánto duraste, qué pasó con tu peso...', textarea: true },
    { type: 'text', key: 'entrenador_anterior', title: '¿Has tenido entrenador antes?', desc: 'Quién, cuánto tiempo y por qué lo dejaste. Si no, escribe "no".', textarea: true },
    {
        type: 'choice', key: 'dias_entreno', title: '¿Cuántos días vas a entrenar por semana?',
        options: [
            { value: 2, label: '2 días' }, { value: 3, label: '3 días' }, { value: 4, label: '4 días' },
            { value: 5, label: '5 días' }, { value: 6, label: '6 días' },
        ],
    },
    {
        type: 'choice', key: 'hora_entreno', title: '¿A qué hora sueles entrenar?',
        options: [
            { value: 'manana', label: 'Por la mañana' },
            { value: 'mediodia', label: 'A mediodía' },
            { value: 'tarde', label: 'Por la tarde' },
            { value: 'noche', label: 'Por la noche' },
            { value: 'variable', label: 'Depende del día' },
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
        type: 'choice', key: 'cardio', title: '¿Haces cardio?',
        options: [
            { value: 'no', label: 'No hago cardio' },
            { value: '1-2_semana', label: '1-2 veces por semana' },
            { value: '3+_semana', label: '3 o más veces por semana' },
        ],
    },
    { type: 'text', key: 'alimentos_evitados', title: '¿Qué alimentos evitas o no te gustan?', desc: 'Sepáralos por comas: lácteos, pescado azul...', textarea: true },
    { type: 'text', key: 'alergias', title: '¿Alergias o intolerancias alimentarias?', desc: 'Si no tienes, escribe "no".', textarea: true },
    {
        type: 'choice', key: 'num_comidas', title: '¿Cuántas comidas al día prefieres hacer?',
        options: [
            { value: 3, label: '3 comidas' }, { value: 4, label: '4 comidas' },
            { value: 5, label: '5 comidas' }, { value: 6, label: '6 comidas' },
        ],
    },
    { type: 'final1', title: 'Perfil completo.', desc: 'Tu coach usará todo esto para tu estrategia. Las fotos de progreso te las pedirá por el chat. Si quieres revisar algo, ve hacia atrás.' },
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

const Shell = ({ progress, children }) => (
    <div className="min-h-screen bg-background relative overflow-hidden flex flex-col">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-brand/10 rounded-full blur-[150px]" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-brand/5 rounded-full blur-[120px]" />
        {/* Flecha de marca gigante de fondo */}
        <BrandArrow className="absolute -right-16 -bottom-16 w-[420px] h-[420px] text-brand/[0.04] pointer-events-none" />
        {/* Barra de progreso */}
        <div className="fixed top-0 left-0 right-0 h-1 bg-white/10 z-20">
            <div className="h-full bg-brand transition-all duration-300" style={{ width: `${progress}%` }} />
        </div>
        {/* Cabecera con logo de marca */}
        <div className="relative z-10 flex items-center h-16 px-6 md:px-10">
            <Logo12EN12 size="sm" tone="dark" />
        </div>
        <div className="flex-1 flex items-center justify-center p-6 relative z-10">
            <div className="w-full max-w-2xl">{children}</div>
        </div>
    </div>
);

const QuestionnairePage = () => {
    const navigate = useNavigate();
    const { api, refreshProfile, user, profile, can, token } = useAuth();
    const [idx, setIdx] = useState(0);
    const [answers, setAnswers] = useState({});
    const [loading, setLoading] = useState(false);
    // Resultado del motor v2 tras enviar el Nivel 0 (los 8 números + desglose).
    const [resultado, setResultado] = useState(null);
    // El Nivel 0 se completó EN ESTA SESIÓN: seguimos en el flujo aunque el
    // perfil ya diga questionnaire_completed (para ver resultados y el Nivel 1).
    const [nivel0Enviado, setNivel0Enviado] = useState(false);
    // Momento mágico: primeros menús del banco personal (null = cargando).
    const [menusMagia, setMenusMagia] = useState(null);

    // Nivel 1 solo para planes con coach (calculadora == 'personalizado').
    const tieneCoach = can(CAP.MACROS_PERSONALIZADOS);
    // Retomar: Nivel 0 hecho en otra sesión pero Nivel 1 pendiente.
    const retomandoNivel1 = !!profile?.questionnaire_completed && !nivel0Enviado
        && tieneCoach && !profile?.questionnaire_nivel1_completed;

    const flow = retomandoNivel1
        ? STEPS_NIVEL1
        : [...STEPS_NIVEL0, ...STEPS_ONBOARD, ...(tieneCoach ? STEPS_NIVEL1 : [])];

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

    // Momento mágico: pedir los primeros menús del banco (la biblioteca filtrada
    // por sus macros recién calculados y sus gustos recién guardados).
    useEffect(() => {
        const s = flow[idx];
        if (s?.type !== 'magia' || menusMagia !== null) return;
        api.post('/calculator/library-menus', {
            mealKey: 'C1',
            macros_objetivo: {},   // el backend reparte el día y toma el target de C1
            margen: 5,
            limit: 3,
            num_comidas: answers.pref_num_comidas || 4,
            momento_entreno: answers.pref_momento ?? 1,
        }).then(r => setMenusMagia(r.data?.menus || []))
          .catch(() => setMenusMagia([]));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [idx]);

    // Nombre y email ya los tenemos del login: autocompletar (el email no es editable).
    useEffect(() => {
        if (!user) return;
        setAnswers(a => ({
            ...a,
            name: a.name ?? user.name ?? '',
            email: user.email ?? a.email ?? '',
        }));
    }, [user]);

    // Todo completado: no puede volver a rellenarlo (ni por el link).
    if (profile?.questionnaire_completed && !nivel0Enviado && !retomandoNivel1) {
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

    const set = (key, value) => setAnswers(a => ({ ...a, [key]: value }));

    // Pasos condicionales (p.ej. el detalle de la dieta solo si sigue_dieta).
    const visible = (s) => !s.cond || s.cond(answers);
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

    // Nivel 0 -> CALCULAR: envía las 8 preguntas, recibe los 8 números + desglose.
    const submitNivel0 = async () => {
        setLoading(true);
        try {
            const res = await api.post('/clients/questionnaire', {
                name: answers.name,
                email: answers.email,
                phone: answers.phone,
                goal: answers.goal,
                sex: answers.sex,
                weight: parseFloat(answers.weight),
                body_fat: parseFloat(answers.body_fat),
                ajustes: {
                    actividad_diaria: answers.actividad_diaria ?? null,
                    deporte_extra: answers.deporte_extra ?? null,
                    facilidad_engordar: answers.facilidad_engordar ?? null,
                    sigue_dieta: answers.sigue_dieta ?? null,
                    dieta_texto: answers.sigue_dieta ? (answers.dieta_texto || null) : null,
                    dieta_hc_entreno: answers.sigue_dieta ? num(answers.dieta_hc_entreno) : null,
                    dieta_grasa_entreno: answers.sigue_dieta ? num(answers.dieta_grasa_entreno) : null,
                },
            });
            setResultado(res.data?.resultado || null);
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
                dias_entreno: answers.dias_entreno ?? null,
                hora_entreno: answers.hora_entreno || null,
                material: answers.material || null,
                cardio: answers.cardio || null,
                alimentos_evitados: answers.alimentos_evitados
                    ? answers.alimentos_evitados.split(',').map(s => s.trim()).filter(Boolean)
                    : null,
                alergias: answers.alergias || null,
                num_comidas: answers.num_comidas ?? null,
            });
            await refreshProfile();
            toast.success('¡Perfil completo! Tu coach ya tiene toda la información.');
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
        setTimeout(goNext, 150);
    };

    const confirmOptions = () => {
        const isVol = answers.goal === 'volumen';
        return [
            { value: 'si', label: isVol ? 'Sí, lo tengo claro: quiero ganar Masa Muscular (VOLUMEN)' : 'Sí, lo tengo claro: quiero perder Grasa (DEFINICIÓN)' },
            { value: 'no', label: isVol ? 'No, en realidad quiero perder Grasa (DEFINICIÓN)' : 'No, en realidad quiero ganar Masa Muscular (VOLUMEN)' },
        ];
    };

    const Title = () => (
        <>
            <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-2 leading-tight">{step.title}</h2>
            {step.desc && <p className="text-foreground/60 mb-8 text-sm md:text-base">{step.desc}</p>}
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
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-2 leading-tight">Estos son tus macros</h2>
                <p className="text-foreground/60 mb-6 text-sm md:text-base">Calculados con el método a partir de tus respuestas. Los verás siempre en tu panel.</p>
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
                                Lo que comes ahora no cuadra con lo esperado para tu % graso: tu entrenador lo revisará.
                            </p>
                        )}
                    </div>
                ) : (
                    <p className="text-foreground/60">Tus macros se han guardado y los verás en tu panel.</p>
                )}
                <div className="flex gap-3 mt-8">
                    <Button onClick={goNext}
                        className="bg-brand hover:bg-brand/90 text-white font-bold px-8 py-6 text-lg">
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
        const esUltimo = !tieneCoach;
        body = (
            <div>
                <h2 className="font-heading font-bold text-3xl md:text-4xl text-foreground mb-2 leading-tight">
                    Estas son comidas que puedes comer hoy
                </h2>
                <p className="text-foreground/60 mb-6 text-sm md:text-base">
                    De tu banco personal: menús reales que cuadran con tus macros y tus gustos.
                </p>
                {menusMagia === null ? (
                    <div className="flex justify-center py-10">
                        <div className="animate-spin rounded-full h-9 w-9 border-4 border-brand border-t-transparent" />
                    </div>
                ) : menusMagia.length === 0 ? (
                    <p className="text-foreground/60 text-sm mb-4">
                        Tu banco de menús te espera en <span className="font-bold text-foreground">Nutrición</span>:
                        en cada comida, pulsa "Sugiéreme un menú" y elige entre comida real que ya cuadra contigo.
                    </p>
                ) : (
                    <div className="space-y-3 mb-2">
                        {menusMagia.map((menu, i) => (
                            <div key={menu.biblioteca_id || i} className="rounded-xl border-2 border-[#222222] bg-card p-4">
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
                            Tienes muchos más en Nutrición, en "Sugiéreme un menú" de cada comida.
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
        // Dieta reportada: números para el motor + texto libre para el coach.
        const hcOk = !isNaN(parseFloat(answers.dieta_hc_entreno)) && parseFloat(answers.dieta_hc_entreno) > 0;
        body = (
            <div>
                <Title />
                <div className="space-y-4 mb-8">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <MiniInput {...mini} k="dieta_hc_entreno" label="Hidratos totales de tu día de entreno" type="number" unit="g" placeholder="250" />
                        <MiniInput {...mini} k="dieta_grasa_entreno" label="Grasa aproximada (opcional)" type="number" unit="g" placeholder="60" />
                    </div>
                    <div>
                        <label className="block text-xs font-bold text-foreground/50 uppercase tracking-wider mb-1.5">¿Qué comes en un día normal?</label>
                        <textarea value={answers.dieta_texto ?? ''} onChange={e => set('dieta_texto', e.target.value)}
                            rows={4} placeholder="Desayuno, comida, cena... con cantidades si las sabes. Se guarda tal cual para tu entrenador."
                            className="w-full rounded-xl bg-card border-2 border-[#222222] p-3 text-foreground text-sm resize-none focus:outline-none focus:border-brand" />
                    </div>
                </div>
                <div className="flex gap-3">
                    <BackBtn />
                    <Button onClick={goNext} disabled={!hcOk}
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8">
                        OK <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                </div>
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
        const opts = step.confirm ? confirmOptions() : step.options;
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

    return <Shell progress={progress}>{body}</Shell>;
};

export default QuestionnairePage;
