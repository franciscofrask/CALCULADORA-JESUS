import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { Avatar, AvatarFallback } from '../components/ui/avatar';
import { toast } from 'sonner';
import {
    Send, MessageCircle, User, Check, CheckCheck, ChevronRight, ArrowLeft,
    CreditCard, Wrench
} from 'lucide-react';
import {
    AdjuntarImagen, ImagenDelMensaje, PreviaDelAdjunto,
} from '../components/chat/ImagenAdjunta';

// EL CHAT CON DOS ENTRADAS (doc del 21-08, apartados 13 y 20).
//
// Antes esta pantalla era una sola conversación para todo, y eso producía la
// contradicción del catálogo: al plan Calculadora se le decía «Solo incidencias
// técnicas» pero se le escondía el chat entero, y con él la única vía para preguntar
// por su dinero. Ahora se entra eligiendo de qué va la cosa, y cada entrada abre la
// conversación de siempre etiquetada con su canal:
//
//   - «Mi suscripción»: cobros, renovación, cambio de plan o baja. Contesta el equipo.
//     La promesa de plazo del plan (`tiempo_respuesta`) SE QUEDA aquí: hay dinero de
//     por medio.
//   - «Algo no funciona»: la app no carga, no guarda... SIN promesa de 24 horas: lo
//     que el doc quiere ahí es un respondedor automático con el equipo detrás, y eso
//     es un agente aparte que no es de hoy.
//
// El canal viaja con cada mensaje al backend («suscripcion» | «tecnico») y el panel
// de Mensajes del equipo lo enseña como chip.
const CANAL = {
    suscripcion: { etiqueta: 'Mi suscripción', detalle: 'Cobros, renovación, cambio de plan o baja', icono: CreditCard },
    tecnico: { etiqueta: 'Algo no funciona', detalle: 'La app no carga, no me guarda, no encuentro dónde se hace', icono: Wrench },
};

const MessagesPage = () => {
    const { api, user, profile, habilitaciones } = useAuth();
    const [canal, setCanal] = useState(null); // null = pantalla de las dos entradas
    const [messages, setMessages] = useState([]);
    const [newMessage, setNewMessage] = useState('');
    const [loading, setLoading] = useState(true);
    const [sending, setSending] = useState(false);
    // La imagen ya subida y esperando a que se mande el mensaje (null si no hay).
    const [adjunto, setAdjunto] = useState(null);
    const scrollRef = useRef(null);
    const inputRef = useRef(null);

    const trainerId = profile?.trainer_id || 'support';

    // El Premium habla de lo suyo con su entrenador por WhatsApp. Sale del CATÁLOGO
    // (habilitaciones.acompanamiento), jamás del nombre del plan: un plan legacy con
    // llamadas también lo es. El Gold pregunta entre reportes por «Algo no funciona»
    // sin texto especial: basta con no bloquearle.
    const seguimientoPorWhatsapp = habilitaciones?.acompanamiento === 'con_entrenador_y_llamadas';

    useEffect(() => {
        // La conversación solo se carga (y solo se marca como leída) cuando se entra
        // por una de las dos puertas: leer por debajo de la pantalla de entrada
        // marcaría como vistos mensajes que nadie vio.
        if (!canal) return;
        fetchMessages();
        const interval = setInterval(fetchMessages, 5000);
        return () => clearInterval(interval);
        // eslint-disable-next-line react-hooks/exhaustive-deps -- repoll al cambiar trainerId o canal
    }, [trainerId, canal]);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    const fetchMessages = async () => {
        try {
            const response = await api.get(`/messages?with_user=${trainerId}`);
            setMessages(response.data.reverse());

            response.data.forEach(async (msg) => {
                if (!msg.read && msg.receiver_id === user.id) {
                    await api.put(`/messages/${msg.id}/read`);
                }
            });
        } catch (error) {
            console.error('Error fetching messages:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSend = async (e) => {
        e.preventDefault();
        // Una imagen sola es un mensaje: si hay adjunto, no hace falta escribir nada.
        if (!newMessage.trim() && !adjunto) return;

        setSending(true);
        try {
            await api.post('/messages', {
                receiver_id: trainerId,
                content: newMessage.trim(),
                // La etiqueta de la puerta por la que entró: es lo que el equipo ve
                // como chip en su bandeja.
                canal,
                adjunto_id: adjunto?.id || null,
            });
            setNewMessage('');
            setAdjunto(null);
            fetchMessages();
            inputRef.current?.focus();
        } catch (error) {
            toast.error('Error al enviar mensaje');
        } finally {
            setSending(false);
        }
    };

    const formatTime = (dateString) => {
        const date = new Date(dateString);
        const now = new Date();
        const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));

        if (diffDays === 0) {
            return date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
        } else if (diffDays === 1) {
            return 'Ayer ' + date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
        } else {
            return date.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
        }
    };

    // ─── La pantalla de entrada: «¿Con qué te ayudamos?» ───────────────────────
    // Tarjetas como las del Inicio (mockup del apartado 20 del doc).
    if (!canal) {
        return (
            <div className="p-4 md:p-6 max-w-2xl mx-auto space-y-4 animate-fade-in bg-background" data-testid="chat-entradas">
                <div>
                    <h1 className="text-xl font-bold text-foreground uppercase tracking-wider" data-testid="messages-heading">
                        ¿Con qué te ayudamos?
                    </h1>
                </div>
                {Object.entries(CANAL).map(([clave, c]) => (
                    <button key={clave} onClick={() => { setLoading(true); setCanal(clave); }}
                        data-testid={`entrada-${clave}`}
                        className="surface surface-hover group w-full p-4 flex items-center gap-4 text-left">
                        <div className="w-11 h-11 bg-brand/10 rounded-xl flex items-center justify-center flex-shrink-0">
                            <c.icono className="w-5 h-5 text-brand" />
                        </div>
                        <div className="min-w-0 flex-1">
                            <p className="font-bold text-foreground text-sm">{c.etiqueta}</p>
                            <p className="text-muted-foreground text-sm">{c.detalle}</p>
                        </div>
                        <span className="flex items-center gap-1 text-sm font-semibold text-brand flex-shrink-0">
                            Escribir <ChevronRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                        </span>
                    </button>
                ))}
                {/* El Premium no pregunta por aquí lo suyo: lo suyo va por WhatsApp con su
                    entrenador, como siempre. Es una tarjeta informativa, no una puerta. */}
                {seguimientoPorWhatsapp && (
                    <div className="surface w-full p-4 flex items-center gap-4" data-testid="entrada-seguimiento">
                        <div className="w-11 h-11 bg-brand/10 rounded-xl flex items-center justify-center flex-shrink-0">
                            <MessageCircle className="w-5 h-5 text-brand" />
                        </div>
                        <div className="min-w-0 flex-1">
                            <p className="font-bold text-foreground text-sm">Tu seguimiento</p>
                            <p className="text-muted-foreground text-sm">
                                Para lo tuyo - dieta, entreno, cómo vas - hablas con tu entrenador por WhatsApp, como siempre.
                            </p>
                        </div>
                    </div>
                )}
            </div>
        );
    }

    // ─── La conversación de siempre, etiquetada con su canal ───────────────────
    if (loading) {
        return (
            <div className="h-[calc(100vh-8rem)] md:h-[calc(100vh-2rem)] flex items-center justify-center bg-background">
                <div className="animate-spin w-8 h-8 border-2 border-[#FF671F] border-t-transparent rounded-full"></div>
            </div>
        );
    }

    return (
        <div className="h-[calc(100vh-8rem)] md:h-[calc(100vh-2rem)] flex flex-col animate-fade-in bg-background">
            {/* Header */}
            <div className="p-4 border-b border-border flex items-center gap-3 bg-card" data-testid="messages-content">
                <button onClick={() => setCanal(null)} data-testid="volver-entradas"
                    className="text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
                    aria-label="Volver a elegir con qué te ayudamos">
                    <ArrowLeft className="w-5 h-5" />
                </button>
                {/* La inicial de su entrenador, no un muñeco de dicebear (punto 4.18). */}
                <Avatar className="border-2 border-[#FF671F]">
                    <AvatarFallback className="bg-[#FF671F] text-white font-bold">
                        {profile?.entrenador?.nombre?.charAt(0)?.toUpperCase() || <User className="w-4 h-4" />}
                    </AvatarFallback>
                </Avatar>
                <div className="min-w-0">
                    {/* SU NOMBRE, NO «Tu Entrenador» (punto 4.16). Hablar con la persona que
                        te lleva no puede parecerse a un formulario de soporte. El nombre lo
                        da el servidor en el perfil: el cliente no tiene acceso al listado
                        del equipo. */}
                    <div className="flex items-center gap-2">
                        <h2 className="font-bold text-foreground uppercase tracking-wider" data-testid="messages-heading">
                            {profile?.entrenador?.nombre || '12EN12'}
                        </h2>
                        <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-brand/10 text-brand flex-shrink-0"
                            data-testid="chip-canal">
                            {CANAL[canal].etiqueta}
                        </span>
                    </div>
                    {/* DEBAJO DEL NOMBRE, CUÁNTO SE TARDA EN CONTESTAR.
                        EL PLAZO ES EL DE SU PLAN (tarea 1.5): lo trae el perfil
                        (`tiempo_respuesta`); si su plan no promete plazo, la línea no se
                        pinta -- prometer de más es peor que no decir nada.
                        Y SOLO EN «MI SUSCRIPCIÓN» (doc 21-08): la promesa de tiempo de
                        respuesta se queda donde hay dinero de por medio. En «Algo no
                        funciona» no se promete plazo ninguno. */}
                    {canal === 'suscripcion' && profile?.tiempo_respuesta && (
                        <p className="text-xs text-[#FF671F]">Te respondemos en {profile.tiempo_respuesta}</p>
                    )}
                </div>
            </div>

            {/* Messages Area */}
            <ScrollArea className="flex-1 p-4" ref={scrollRef}>
                {messages.length > 0 ? (
                    <div className="space-y-4">
                        {messages.map((msg) => {
                            const isOwn = msg.sender_id === user.id;
                            return (
                                <div
                                    key={msg.id}
                                    className={`flex ${isOwn ? 'justify-end' : 'justify-start'}`}
                                >
                                    <div className={`max-w-[80%] ${isOwn ? 'order-2' : 'order-1'}`}>
                                        <div
                                            className={`rounded-2xl px-4 py-2 ${
                                                isOwn
                                                    ? 'bg-[#FF671F] text-white rounded-br-sm'
                                                    : 'bg-muted text-foreground rounded-bl-sm'
                                            }`}
                                        >
                                            {msg.content && (
                                                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                                            )}
                                            {/* La imagen, dentro de la burbuja: con texto va
                                                debajo, y sola es la burbuja entera. */}
                                            {msg.adjunto && (
                                                <div className={msg.content ? 'mt-2' : ''}>
                                                    <ImagenDelMensaje api={api} adjunto={msg.adjunto} propio={isOwn} />
                                                </div>
                                            )}
                                        </div>
                                        <div className={`flex items-center gap-1 mt-1 ${isOwn ? 'justify-end' : 'justify-start'}`}>
                                            <span className="text-xs text-foreground/40">
                                                {formatTime(msg.created_at)}
                                            </span>
                                            {isOwn && (
                                                msg.read
                                                    ? <CheckCheck className="w-3 h-3 text-[#FF671F]" />
                                                    : <Check className="w-3 h-3 text-foreground/40" />
                                            )}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <div className="h-full flex flex-col items-center justify-center text-center p-8">
                        <div className="w-20 h-20 bg-[#FF671F]/10 rounded-full flex items-center justify-center mb-4">
                            <MessageCircle className="w-10 h-10 text-[#FF671F]" />
                        </div>
                        <h3 className="font-bold text-foreground uppercase tracking-wider mb-2">Sin mensajes</h3>
                        {/* Que diga lo mismo que la cabecera (punto 4.16). Sin entrenador
                            asignado, arriba pone «Soporte JG12» y aquí ponía «envía un mensaje
                            a tu entrenador»: la misma pantalla se contradecía a sí misma, y le
                            prometía una persona que ese cliente no tiene todavía.

                            Y NO SE PROMETE UN ENTRENADOR QUE NO VA A LLEGAR (#50 del 15-08).
                            Aquí ponía «en cuanto tengas entrenador asignado, hablarás aquí
                            mismo con él» a un cliente cuyo plan pone «Con entrenador»: el que
                            paga por llevarlo lee que todavía no lo tiene. El acompañamiento
                            del plan y el campo `trainer_id` son dos cosas distintas -- de 247
                            clientes solo 8 lo tienen puesto -- y esta pantalla no es el sitio
                            para explicarlo. Se dice lo único que es verdad siempre: escribe y
                            te contesta quien te lleva. */}
                        <p className="text-sm text-foreground/50">
                            {profile?.entrenador?.nombre
                                ? `Escribe a ${profile.entrenador.nombre} para empezar.`
                                : 'Escríbenos por aquí: te contesta el equipo que lleva tu seguimiento.'}
                        </p>
                    </div>
                )}
            </ScrollArea>

            {/* Input Area */}
            <div className="p-4 border-t border-border bg-card">
                <PreviaDelAdjunto adjunto={adjunto} onQuitar={() => setAdjunto(null)} />
                <form onSubmit={handleSend} className="flex items-center gap-2">
                    <AdjuntarImagen api={api} adjunto={adjunto} onAdjunto={setAdjunto}
                        deshabilitado={sending} />
                    <Input
                        ref={inputRef}
                        value={newMessage}
                        onChange={(e) => setNewMessage(e.target.value)}
                        placeholder="Escribe un mensaje..."
                        className="flex-1 bg-background border-input text-foreground placeholder:text-muted-foreground focus:border-brand"
                        disabled={sending}
                        data-testid="message-input"
                    />
                    <Button
                        type="submit"
                        size="icon"
                        disabled={sending || (!newMessage.trim() && !adjunto)}
                        className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white"
                        data-testid="send-message-btn"
                    >
                        <Send className="w-4 h-4" />
                    </Button>
                </form>
            </div>
        </div>
    );
};

export default MessagesPage;
