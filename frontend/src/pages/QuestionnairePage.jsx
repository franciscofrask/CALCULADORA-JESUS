import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { ArrowRight, ArrowLeft, Loader2, Check, ImagePlus } from 'lucide-react';
import Logo12EN12 from '../components/Logo12EN12';
import BrandArrow from '../components/BrandArrow';

// Cuestionario inicial obligatorio — réplica del Typeform "[ELM] Cuestionario inicial - hombre".
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

// Definición de los pasos. type: statement | text | email | tel | date | number | choice | biotype | bf
const STEPS = [
    { type: 'statement', title: 'Quiz Inicial', desc: 'Vamos a conocerte para personalizar tu plan. Tardarás un par de minutos. Responde con sinceridad.' },
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
    { type: 'date', key: 'birthdate', title: 'Fecha de nacimiento', desc: 'La verdadera, no me engañes.', required: true },
    { type: 'number', key: 'height', title: '¿Cuánto mides?', desc: 'Tu altura, en cm.', unit: 'cm', required: true },
    { type: 'number', key: 'weight', title: '¿Cuánto pesas?', desc: 'Pésate siempre igual: en ayunas, sin ropa y después de ir al baño.', unit: 'kg', required: true },
    {
        type: 'choice', key: 'activity_level', title: '¿Cómo describirías tu nivel de actividad diaria?',
        desc: 'Ir al gimnasio 1h 4-5 veces/semana no te hace activo. Piensa en cuánto te mueves en tu día a día.',
        options: [
            { value: 'sedentario', label: 'Muy sedentario: paso casi todo el día sentado, apenas me muevo.' },
            { value: 'ligero', label: 'Ligeramente activo: trabajo sentado pero intento moverme (paseos, escaleras, evito el coche).' },
            { value: 'moderado', label: 'Moderadamente activo: en movimiento gran parte del día, sin esfuerzos físicos importantes.' },
            { value: 'activo', label: 'Muy activo: mi día a día es muy demandante físicamente, no paro.' },
        ],
    },
    { type: 'biotype_intro', title: 'Ahora tienes que elegir tu biotipo, es decir, tu tipo de cuerpo.', desc: 'Es la tendencia natural de tu cuerpo según tu genética (independientemente de tu estado físico actual o los hábitos que tengas en este momento). Antes te explico los 7 que hay (después eliges):' },
    { type: 'biotype', key: 'biotype', title: 'Indica cuál de los 7 biotipos corporales es el tuyo', desc: 'Puedes volver atrás y leer las descripciones. Si no te identificas claramente con ninguno, elige el que más se acerque a ti.' },
    { type: 'bf', key: 'body_fat', title: '¿Cuál dirías que es tu porcentaje de grasa actual?', desc: 'Elige el valor más cercano a tu % de grasa estimado.' },
    { type: 'final', title: 'Y ya estaría.', desc: 'Si quieres revisar alguna respuesta, ve hacia atrás. Una vez envíes, recibirás tus macros personalizados.' },
];

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
    const { api, refreshProfile, user, profile } = useAuth();
    const [idx, setIdx] = useState(0);
    const [answers, setAnswers] = useState({});
    const [loading, setLoading] = useState(false);

    // Nombre y email ya los tenemos del login: autocompletar (el email no es editable).
    useEffect(() => {
        if (!user) return;
        setAnswers(a => ({
            ...a,
            name: a.name ?? user.name ?? '',
            email: user.email ?? a.email ?? '',
        }));
    }, [user]);

    // Si ya completó el cuestionario, no puede volver a rellenarlo (ni por el link).
    if (profile?.questionnaire_completed) {
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

    const step = STEPS[idx];
    const progress = ((idx + 1) / STEPS.length) * 100;

    const set = (key, value) => setAnswers(a => ({ ...a, [key]: value }));

    const goNext = () => setIdx(i => Math.min(i + 1, STEPS.length - 1));
    const goBack = () => setIdx(i => Math.max(i - 1, 0));

    const submit = async () => {
        setLoading(true);
        try {
            await api.post('/clients/questionnaire', {
                name: answers.name,
                email: answers.email,
                phone: answers.phone,
                goal: answers.goal,
                sex: answers.sex,
                training_experience: answers.training_experience,
                birthdate: answers.birthdate,
                height: answers.height ? parseFloat(answers.height) : null,
                weight: parseFloat(answers.weight),
                activity_level: answers.activity_level,
                biotype: answers.biotype,
                body_fat: parseFloat(answers.body_fat),
            });
            await refreshProfile();
            toast.success('¡Cuestionario enviado! Tus macros se han calculado.');
            navigate('/welcome');
        } catch (e) {
            toast.error(e.response?.data?.detail || 'Error al enviar el cuestionario');
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

    let body;
    if (step.type === 'statement' && idx === 0) {
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
    } else if (step.type === 'statement' || step.type === 'final') {
        body = (
            <div>
                <Title />
                <div className="flex gap-3">
                    {idx > 0 && (
                        <Button variant="ghost" onClick={goBack} className="text-foreground/60">
                            <ArrowLeft className="w-4 h-4 mr-1" /> Atrás
                        </Button>
                    )}
                    {step.type === 'final' ? (
                        <Button onClick={submit} disabled={loading}
                            className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8 py-6 text-lg">
                            {loading ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <Check className="w-5 h-5 mr-2" />}
                            {loading ? 'Enviando...' : 'Enviar'}
                        </Button>
                    ) : (
                        <Button onClick={goNext}
                            className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8 py-6 text-lg">
                            Empezar <ArrowRight className="w-5 h-5 ml-2" />
                        </Button>
                    )}
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
                            <button key={o.value} onClick={() => pickChoice(o.value)}
                                className={`w-full text-left px-5 py-4 rounded-xl border-2 transition-all ${selected ? 'border-[#FF671F] bg-[#FF671F]/10' : 'border-[#222222] hover:border-white/30'} text-foreground`}>
                                {o.label}
                            </button>
                        );
                    })}
                </div>
                {idx > 0 && (
                    <Button variant="ghost" onClick={goBack} className="text-foreground/60 mt-6">
                        <ArrowLeft className="w-4 h-4 mr-1" /> Atrás
                    </Button>
                )}
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
                    {idx > 0 && (
                        <Button variant="ghost" onClick={goBack} className="text-foreground/60">
                            <ArrowLeft className="w-4 h-4 mr-1" /> Atrás
                        </Button>
                    )}
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
                {idx > 0 && (
                    <Button variant="ghost" onClick={goBack} className="text-foreground/60 mt-6">
                        <ArrowLeft className="w-4 h-4 mr-1" /> Atrás
                    </Button>
                )}
            </div>
        );
    } else if (step.type === 'bf') {
        body = (
            <div>
                <Title />
                <BodyFatSlider value={answers.body_fat} onChange={(v) => set('body_fat', v)} />
                <div className="flex items-center gap-3 mt-6">
                    {idx > 0 && (
                        <Button variant="ghost" onClick={goBack} className="text-foreground/60">
                            <ArrowLeft className="w-4 h-4 mr-1" /> Atrás
                        </Button>
                    )}
                    <Button onClick={goNext}
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white font-bold px-8 py-6 text-lg">
                        Continuar <ArrowRight className="w-5 h-5 ml-2" />
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
                    {idx > 0 && (
                        <Button variant="ghost" onClick={goBack} className="text-foreground/60">
                            <ArrowLeft className="w-4 h-4 mr-1" /> Atrás
                        </Button>
                    )}
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
