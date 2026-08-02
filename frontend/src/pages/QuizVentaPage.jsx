/**
 * QuizVentaPage - Las cuatro preguntas de antes de comprar.
 *
 * Especificación 31-07-2026, partes 3 y 4. Cuatro preguntas, y al final el nivel que le
 * pega explicado con sus propias palabras, con los otros dos debajo por si prefiere otro.
 *
 * Lo que no se toca: **ve su resultado sin dar el correo**. Es una decisión cerrada del
 * documento y aquí se nota en que esta pantalla no pide nada para funcionar — ni sesión,
 * ni email. El correo se ofrece DESPUÉS, para guardar el resultado o recibirlo.
 *
 * Y el Nivel 3 no lleva a un pago, lleva a una llamada.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { ArrowLeft, ArrowRight, Check, Loader2, Phone } from 'lucide-react';
import Logo12EN12 from '../components/Logo12EN12';

const API = process.env.REACT_APP_BACKEND_URL || '';

const QuizVentaPage = () => {
    const navigate = useNavigate();
    const [preguntas, setPreguntas] = useState([]);
    const [idx, setIdx] = useState(0);
    const [respuestas, setRespuestas] = useState({});
    const [resultado, setResultado] = useState(null);
    const [enviando, setEnviando] = useState(false);
    // El correo es el paso de después: null = no lo hemos pedido, 'guardar' | 'llamada'.
    const [pidiendo, setPidiendo] = useState(null);
    const [email, setEmail] = useState('');
    const [nombre, setNombre] = useState('');
    const [telefono, setTelefono] = useState('');
    const [guardado, setGuardado] = useState(false);
    const esLlamada = pidiendo === 'llamada';

    useEffect(() => {
        axios.get(`${API}/api/quiz-venta`)
            .then(r => setPreguntas(r.data.preguntas || []))
            .catch(() => toast.error('No hemos podido cargar el test'));
    }, []);

    const responder = async (opcionId) => {
        const nuevas = { ...respuestas, [preguntas[idx].id]: opcionId };
        setRespuestas(nuevas);

        if (idx < preguntas.length - 1) {
            setIdx(idx + 1);
            return;
        }
        setEnviando(true);
        try {
            const r = await axios.post(`${API}/api/quiz-venta`, { respuestas: nuevas });
            setResultado(r.data);
        } catch {
            toast.error('No hemos podido calcular tu resultado');
        } finally {
            setEnviando(false);
        }
    };

    const elegir = (plan, porLlamada) => {
        if (porLlamada) {
            // El Nivel 3 "se compra por llamada", así que no hay botón de pago que valga.
            // Se le pide el correo y queda como lead pidiendo llamada.
            setPidiendo('llamada');
            return;
        }
        // Sin sesión no se puede cobrar: se le lleva a registrarse. El plan elegido viaja
        // en sessionStorage porque /auth no lee query params — si se pasara en la URL se
        // perdería igual, y aquí al menos sobrevive hasta la pantalla de planes.
        try { sessionStorage.setItem('plan_elegido', plan); } catch { /* modo privado */ }
        navigate('/auth');
    };

    const guardar = async (e) => {
        e.preventDefault();
        if (!email.trim()) return;
        setEnviando(true);
        try {
            await axios.post(`${API}/api/quiz-venta/guardar`, {
                email, nombre, telefono,
                respuestas: resultado.respuestas,
                recomendado: resultado.recomendado,
                quiere_llamada: esLlamada,
            });
            setGuardado(true);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'No hemos podido guardarlo');
        } finally {
            setEnviando(false);
        }
    };

    // ── Resultado ────────────────────────────────────────────────────────────
    if (resultado) {
        const recomendado = resultado.niveles.find(n => n.recomendado);
        const otros = resultado.niveles.filter(n => !n.recomendado);
        return (
            <div className="min-h-screen bg-background text-foreground px-4 py-10">
                <div className="max-w-2xl mx-auto">
                    <div className="flex justify-center mb-8"><Logo12EN12 size="md" /></div>

                    <p className="caption text-brand text-center mb-2">Lo que te pega</p>
                    <h1 className="font-heading text-4xl font-bold uppercase text-center mb-4">
                        {recomendado?.nombre}
                    </h1>
                    <p className="text-center text-foreground/80 leading-relaxed max-w-lg mx-auto mb-8">
                        {resultado.por_que}
                    </p>

                    <div className="surface p-5 border-brand mb-3">
                        <div className="flex items-baseline justify-between mb-4">
                            <span className="font-heading text-2xl font-bold uppercase">{recomendado?.nombre}</span>
                            <span className="font-heading text-2xl font-bold text-brand">{recomendado?.precio} €</span>
                        </div>
                        <button onClick={() => elegir(recomendado.plan, recomendado.por_llamada)}
                            data-testid="quiz-elegir-recomendado"
                            className="w-full h-12 rounded-xl bg-brand text-white font-bold flex items-center justify-center gap-2">
                            {recomendado?.por_llamada
                                ? <><Phone className="w-4 h-4" /> Agendar una llamada</>
                                : <>Empezar <ArrowRight className="w-4 h-4" /></>}
                        </button>
                    </div>

                    {/* Los otros dos, visibles: la recomendación orienta, no encierra. */}
                    <p className="caption text-center my-4">O si prefieres otro</p>
                    <div className="grid sm:grid-cols-2 gap-3">
                        {otros.map(n => (
                            <button key={n.plan} onClick={() => elegir(n.plan, n.por_llamada)}
                                data-testid={`quiz-elegir-${n.plan}`}
                                className="surface surface-hover p-4 text-left">
                                <div className="flex items-baseline justify-between">
                                    <span className="font-bold">{n.nombre}</span>
                                    <span className="font-heading text-lg font-bold">{n.precio} €</span>
                                </div>
                                <span className="text-sm text-muted-foreground">
                                    {n.por_llamada ? 'Se contrata por llamada' : 'Empezar con este'}
                                </span>
                            </button>
                        ))}
                    </div>

                    {/* El correo, DESPUES de haber visto el resultado y nunca antes. */}
                    <div className="mt-8">
                        {guardado ? (
                            <div className="surface p-5 text-center" data-testid="quiz-guardado">
                                <Check className="w-6 h-6 text-brand mx-auto mb-2" />
                                <p className="font-bold">
                                    {esLlamada ? 'Te llamamos' : 'Guardado'}
                                </p>
                                <p className="text-sm text-muted-foreground mt-1">
                                    {esLlamada
                                        ? 'Te llamamos al número que nos has dejado para hablar del Nivel 3.'
                                        : 'Te lo hemos guardado. Puedes volver cuando quieras.'}
                                </p>
                            </div>
                        ) : pidiendo ? (
                            <form onSubmit={guardar} className="surface p-5" data-testid="quiz-form-email">
                                <p className="font-bold mb-1">
                                    {esLlamada ? 'El Nivel 3 se contrata hablando' : 'Te lo guardamos'}
                                </p>
                                <p className="text-sm text-muted-foreground mb-4">
                                    {esLlamada
                                        ? 'Déjanos tu nombre y tu teléfono y te llamamos nosotros.'
                                        : 'Déjanos tu correo y tendrás este resultado a mano.'}
                                </p>
                                <div className="grid sm:grid-cols-2 gap-2 mb-3">
                                    <input value={nombre} onChange={e => setNombre(e.target.value)}
                                        required={esLlamada} placeholder="Tu nombre" data-testid="quiz-nombre"
                                        className="h-11 px-3 rounded-xl bg-muted text-base sm:text-sm" />
                                    <input value={email} onChange={e => setEmail(e.target.value)}
                                        type="email" required placeholder="Tu correo" data-testid="quiz-email"
                                        className="h-11 px-3 rounded-xl bg-muted text-base sm:text-sm" />
                                    {/* El telefono solo cuando hay que llamarle: pedirlo para
                                        guardar un resultado seria pedirlo por pedirlo. */}
                                    {esLlamada && (
                                        <input value={telefono} onChange={e => setTelefono(e.target.value)}
                                            type="tel" required placeholder="Tu teléfono" data-testid="quiz-telefono"
                                            className="h-11 px-3 rounded-xl bg-muted text-base sm:text-sm sm:col-span-2" />
                                    )}
                                </div>
                                <button type="submit" disabled={enviando} data-testid="quiz-guardar"
                                    className="w-full h-11 rounded-xl bg-brand text-white font-bold disabled:opacity-60">
                                    {enviando ? 'Enviando…' : esLlamada ? 'Que me llamen' : 'Guardar'}
                                </button>
                            </form>
                        ) : (
                            <button onClick={() => setPidiendo('guardar')} data-testid="quiz-pedir-guardar"
                                className="w-full text-sm text-muted-foreground hover:text-foreground underline underline-offset-4">
                                Guardar este resultado para más tarde
                            </button>
                        )}
                    </div>

                    <p className="text-center text-[11px] text-muted-foreground mt-8">
                        Todos los ciclos son de 12 semanas. Tu precio se congela mientras no te des de baja.
                    </p>
                </div>
            </div>
        );
    }

    // ── Preguntas ────────────────────────────────────────────────────────────
    const pregunta = preguntas[idx];
    if (!pregunta) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2 className="w-6 h-6 animate-spin text-brand" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background text-foreground px-4 py-10">
            <div className="max-w-xl mx-auto">
                <div className="flex justify-center mb-8"><Logo12EN12 size="md" /></div>

                {/* Cuántas van: cuatro preguntas se aguantan si se ve el final */}
                <div className="flex items-center gap-2 mb-8">
                    {preguntas.map((p, i) => (
                        <div key={p.id} className={`h-1 flex-1 rounded-full transition-colors ${
                            i < idx ? 'bg-brand' : i === idx ? 'bg-brand/50' : 'bg-muted'}`} />
                    ))}
                </div>

                <p className="caption text-brand mb-2">Pregunta {idx + 1} de {preguntas.length}</p>
                <h1 className="font-heading text-2xl sm:text-3xl font-bold uppercase leading-tight mb-6">
                    {pregunta.texto}
                </h1>

                <div className="space-y-2.5">
                    {pregunta.opciones.map(o => {
                        const elegida = respuestas[pregunta.id] === o.id;
                        return (
                            <button key={o.id} onClick={() => responder(o.id)} disabled={enviando}
                                data-testid={`quiz-p${pregunta.id}-${o.id}`}
                                className={`w-full surface surface-hover p-4 text-left flex items-center gap-3 disabled:opacity-60 ${
                                    elegida ? 'border-brand' : ''}`}>
                                <span className={`w-7 h-7 rounded-lg flex-shrink-0 grid place-items-center text-xs font-bold ${
                                    elegida ? 'bg-brand text-white' : 'bg-muted text-muted-foreground'}`}>
                                    {elegida ? <Check className="w-4 h-4" /> : o.id}
                                </span>
                                <span className="text-[15px]">{o.texto}</span>
                            </button>
                        );
                    })}
                </div>

                {idx > 0 && (
                    <button onClick={() => setIdx(idx - 1)}
                        className="mt-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
                        <ArrowLeft className="w-4 h-4" /> Atrás
                    </button>
                )}

                {enviando && (
                    <p className="mt-6 text-sm text-muted-foreground flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" /> Mirando qué te pega…
                    </p>
                )}
            </div>
        </div>
    );
};

export default QuizVentaPage;
