import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { toast } from 'sonner';
import { Send, MessageCircle, User, Check, CheckCheck } from 'lucide-react';

const MessagesPage = () => {
    const { api, user, profile } = useAuth();
    const [messages, setMessages] = useState([]);
    const [newMessage, setNewMessage] = useState('');
    const [loading, setLoading] = useState(true);
    const [sending, setSending] = useState(false);
    const scrollRef = useRef(null);
    const inputRef = useRef(null);

    const trainerId = profile?.trainer_id || 'support';

    useEffect(() => {
        fetchMessages();
        const interval = setInterval(fetchMessages, 5000);
        return () => clearInterval(interval);
        // eslint-disable-next-line react-hooks/exhaustive-deps -- repoll al cambiar trainerId
    }, [trainerId]);

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
        if (!newMessage.trim()) return;
        
        setSending(true);
        try {
            await api.post('/messages', {
                receiver_id: trainerId,
                content: newMessage.trim()
            });
            setNewMessage('');
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
                {/* La inicial de su entrenador, no un muñeco de dicebear (punto 4.18). */}
                <Avatar className="border-2 border-[#FF671F]">
                    <AvatarFallback className="bg-[#FF671F] text-white font-bold">
                        {profile?.entrenador?.nombre?.charAt(0)?.toUpperCase() || <User className="w-4 h-4" />}
                    </AvatarFallback>
                </Avatar>
                <div>
                    {/* SU NOMBRE, NO «Tu Entrenador» (punto 4.16). Hablar con la persona que
                        te lleva no puede parecerse a un formulario de soporte. El nombre lo
                        da el servidor en el perfil: el cliente no tiene acceso al listado
                        del equipo. */}
                    <h2 className="font-bold text-foreground uppercase tracking-wider" data-testid="messages-heading">
                        {profile?.entrenador?.nombre || '12EN12'}
                    </h2>
                    {/* DEBAJO DEL NOMBRE, CUÁNTO SE TARDA EN CONTESTAR.
                        Aquí ponía «Tu entrenador» otra vez, repitiendo el puesto debajo del
                        nombre. Lo que de verdad falta es el plazo: sin él, la mitad de los
                        mensajes son «¿hay alguien?» (Jesús, 11-08). Y al plan de 897 € se le
                        vende un chat con una persona: decir cuándo responde es parte de eso.
                        EL PLAZO ES EL DE SU PLAN (tarea 1.5): aquí ponía «menos de 24 horas»
                        fijo para todos, y eso solo lo promete el catálogo en los planes con
                        chat de dudas. Lo trae el perfil (`tiempo_respuesta`); si su plan no
                        promete plazo, la línea no se pinta -- prometer de más es peor que
                        no decir nada. */}
                    {profile?.tiempo_respuesta && (
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
                                            <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
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
                <form onSubmit={handleSend} className="flex items-center gap-2">
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
                        disabled={sending || !newMessage.trim()}
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
