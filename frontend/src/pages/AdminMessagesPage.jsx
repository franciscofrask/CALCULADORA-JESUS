import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { Send, MessageCircle, Search, CheckCheck, Check, Clock } from 'lucide-react';
import {
    AdjuntarImagen, ImagenDelMensaje, PreviaDelAdjunto,
} from '../components/chat/ImagenAdjunta';

// EL CANAL DEL MENSAJE (doc del 21-08, apartados 13 y 20): el cliente entra al chat por
// una de dos puertas -- «Mi suscripción» o «Algo no funciona» -- y cada mensaje llega
// etiquetado con la suya. El chip es informativo y nada más: la conversación sigue siendo
// una. Los mensajes de antes de las dos entradas (y los del propio equipo) no llevan
// canal y no pintan chip.
const CANAL_CHIP = {
    suscripcion: { texto: 'Suscripción', clase: 'bg-[#FF671F]/15 text-[#FF671F]' },
    tecnico: { texto: 'Algo no funciona', clase: 'bg-sky-500/15 text-sky-400' },
};
const ChipCanal = ({ canal }) => {
    const c = canal && CANAL_CHIP[canal];
    if (!c) return null;
    return (
        <span className={`text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded-full flex-shrink-0 ${c.clase}`}
            data-testid={`chip-canal-${canal}`}>
            {c.texto}
        </span>
    );
};

// Bandeja de mensajes del staff: conversaciones a la izquierda, chat a la derecha.
const AdminMessagesPage = () => {
    const { api, user } = useAuth();
    const [conversations, setConversations] = useState([]);
    const [selected, setSelected] = useState(null); // user_id de la conversacion abierta
    const [messages, setMessages] = useState([]);
    const [newMessage, setNewMessage] = useState('');
    const [sending, setSending] = useState(false);
    // La imagen ya subida y esperando a que se mande la respuesta (null si no hay).
    const [adjunto, setAdjunto] = useState(null);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    // Ver solo la cola de soporte (clientes sin entrenador). Apagado por defecto: la
    // bandeja sigue siendo la de siempre hasta que alguien decide filtrar.
    const [soloSoporte, setSoloSoporte] = useState(false);
    const scrollRef = useRef(null);

    const fetchConversations = useCallback(async () => {
        try {
            const res = await api.get('/messages/conversations');
            setConversations(res.data || []);
        } catch (e) { /* silencioso en el poll */ }
        finally { setLoading(false); }
    }, [api]);

    const fetchMessages = useCallback(async (otherId) => {
        if (!otherId) return;
        try {
            const res = await api.get(`/messages?with_user=${otherId}`);
            setMessages([...res.data].reverse());
            await api.put(`/messages/read-all?with_user=${otherId}`);
        } catch (e) { /* silencioso */ }
    }, [api]);

    useEffect(() => {
        fetchConversations();
        const id = setInterval(fetchConversations, 10000);
        return () => clearInterval(id);
    }, [fetchConversations]);

    useEffect(() => {
        if (!selected) return;
        fetchMessages(selected);
        const id = setInterval(() => fetchMessages(selected), 5000);
        return () => clearInterval(id);
    }, [selected, fetchMessages]);

    useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [messages]);

    const handleSend = async (e) => {
        e.preventDefault();
        // Una imagen sola es una respuesta: una captura contesta mejor que un párrafo.
        if ((!newMessage.trim() && !adjunto) || !selected) return;
        setSending(true);
        try {
            await api.post('/messages', {
                receiver_id: selected, content: newMessage.trim(),
                adjunto_id: adjunto?.id || null,
            });
            setNewMessage('');
            setAdjunto(null);
            fetchMessages(selected);
            fetchConversations();
        } catch (err) { toast.error('Error al enviar el mensaje'); }
        finally { setSending(false); }
    };

    const openConversation = (otherId) => {
        setSelected(otherId);
        setConversations(prev => prev.map(c => c.user_id === otherId ? { ...c, unread: 0 } : c));
    };

    const formatTime = (dateString) => {
        const date = new Date(dateString);
        const diffDays = Math.floor((new Date() - date) / 86400000);
        if (diffDays === 0) return date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
        if (diffDays === 1) return 'Ayer';
        return date.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
    };

    const filtered = conversations.filter(c =>
        (!soloSoporte || c.es_soporte) &&
        (!search || c.user?.name?.toLowerCase().includes(search.toLowerCase()) ||
            c.user?.email?.toLowerCase().includes(search.toLowerCase()))
    );
    const selectedConv = conversations.find(c => c.user_id === selected);
    const esperando = conversations.filter(c => c.sin_respuesta).length;
    const deSoporte = conversations.filter(c => c.es_soporte).length;

    if (loading) return <div className="p-6 bg-[#0A0A0A] min-h-screen"><div className="animate-pulse space-y-4"><div className="h-8 bg-[#222] rounded w-1/4" /><div className="h-96 bg-[#111] rounded-xl" /></div></div>;

    return (
        // En móvil hay DOS barras: la cabecera de arriba (3.5rem) y la de navegación de abajo
        // (4rem); si solo se resta una, el campo de escribir cae tras la barra inferior. En
        // escritorio no hay barras y usa la pantalla entera.
        <div className="p-4 md:p-6 h-[calc(100vh-7.5rem)] lg:h-screen flex flex-col bg-[#0A0A0A]" data-testid="admin-messages-page">
            <div className="mb-4">
                <h1 className="text-2xl font-bold text-white tracking-tight" style={{ fontFamily: 'Barlow Condensed' }}>MENSAJES</h1>
                {esperando > 0 && (
                    <p className="text-white/50 text-sm mt-0.5" data-testid="conv-esperando">
                        <span className="text-yellow-400 font-semibold">{esperando}</span>
                        {esperando === 1 ? ' conversación espera' : ' conversaciones esperan'} respuesta. Van primero.
                    </p>
                )}
            </div>
            <div className="flex-1 flex gap-4 min-h-0">
                {/* Lista de conversaciones */}
                <div className={`w-full md:w-80 flex-shrink-0 bg-[#111] border border-[#222] rounded-xl flex flex-col min-h-0 ${selected ? 'hidden md:flex' : 'flex'}`}>
                    <div className="p-3 border-b border-[#222]">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                            <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar cliente..." className="pl-9 bg-[#0A0A0A] border-[#222] text-white" />
                        </div>
                        {/* Con quince personas mirando la misma bandeja, el que lleva el
                            soporte necesita quedarse solo con lo suyo. Solo sale si hay
                            alguna: un filtro que no filtra nada es un botón que estorba. */}
                        {deSoporte > 0 && (
                            <button type="button" onClick={() => setSoloSoporte(v => !v)}
                                data-testid="filtro-soporte"
                                className={`mt-2 w-full text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                                    soloSoporte
                                        ? 'bg-sky-500/15 border-sky-500/50 text-sky-300 font-semibold'
                                        : 'bg-[#0A0A0A] border-[#222] text-white/50 hover:text-white/80'}`}>
                                {soloSoporte ? `Viendo solo soporte (${deSoporte})` : `Ver solo soporte (${deSoporte})`}
                            </button>
                        )}
                    </div>
                    <div className="flex-1 overflow-y-auto">
                        {filtered.map(c => (
                            <button key={c.user_id} onClick={() => openConversation(c.user_id)}
                                className={`w-full text-left px-4 py-3 border-b border-[#1A1A1A] transition-all hover:bg-white/5 ${selected === c.user_id ? 'bg-[#FF671F]/10 border-l-2 border-l-[#FF671F]' : ''}`}
                                data-testid={`conv-${c.user_id}`}>
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-white text-sm font-medium truncate min-w-0">{c.user?.name || c.user?.email || 'Sin nombre'}</p>
                                    <span className="text-white/30 text-[10px] flex-shrink-0">{formatTime(c.last_message.created_at)}</span>
                                </div>
                                {/* DE QUIÉN ES ESTA CONVERSACIÓN (Francisco, 25-08). La
                                    bandeja es común para los quince del equipo y todas se
                                    veían iguales. «Soporte» es la cola de los que no tienen
                                    entrenador; con nombre, es de un compañero y contestar
                                    encima suyo es pisarle. El chip de canal, al lado, dice
                                    otra cosa: de qué va la consulta. */}
                                <p className="text-[10px] uppercase tracking-wide mt-0.5 truncate"
                                    data-testid={c.es_soporte ? 'conv-soporte' : 'conv-de-entrenador'}>
                                    {c.es_soporte
                                        ? <span className="text-sky-400 font-semibold">Soporte</span>
                                        : <span className="text-white/30">{c.entrenador_nombre || 'Con entrenador'}</span>}
                                </p>
                                <div className="flex items-center justify-between gap-2 mt-0.5">
                                    <p className="text-white/40 text-xs truncate min-w-0">
                                        {c.last_message.sender_id === user.id ? 'Tú: ' : ''}{c.last_message.content}
                                    </p>
                                    <ChipCanal canal={c.last_message.canal} />
                                    {c.unread > 0 && (
                                        <span className="bg-[#FF671F] text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] px-1 flex items-center justify-center flex-shrink-0">{c.unread}</span>
                                    )}
                                </div>
                                {/* «El cliente que se pierde es el que nadie ve» (Jesús, 11-08).
                                    Escribió él y nadie del equipo ha contestado todavía: eso es
                                    una tarea, y no se distinguía de una conversación cerrada. */}
                                {c.sin_respuesta && (
                                    <p className="text-yellow-400 text-[10px] font-semibold uppercase tracking-wide mt-1 flex items-center gap-1">
                                        <Clock className="w-3 h-3" /> Esperando respuesta
                                    </p>
                                )}
                            </button>
                        ))}
                        {filtered.length === 0 && (
                            <div className="p-8 text-center">
                                <MessageCircle className="w-10 h-10 text-white/10 mx-auto mb-3" />
                                <p className="text-white/30 text-sm">Sin conversaciones todavía. Cuando un cliente te escriba, aparecerá aquí.</p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Chat */}
                <div className={`flex-1 bg-[#111] border border-[#222] rounded-xl flex-col min-h-0 ${selected ? 'flex' : 'hidden md:flex'}`}>
                    {selected ? (
                        <>
                            <div className="p-3 border-b border-[#222] flex items-center gap-3">
                                <button onClick={() => setSelected(null)} className="md:hidden text-white/50 text-sm">&larr;</button>
                                <div className="w-9 h-9 bg-[#FF671F]/15 rounded-lg flex items-center justify-center">
                                    <span className="text-[#FF671F] font-bold">{(selectedConv?.user?.name || '?').charAt(0).toUpperCase()}</span>
                                </div>
                                <div className="min-w-0">
                                    <p className="text-white text-sm font-bold truncate">{selectedConv?.user?.name || 'Cliente'}</p>
                                    <p className="text-white/30 text-xs truncate">{selectedConv?.user?.email}</p>
                                </div>
                            </div>
                            <div className="flex-1 overflow-y-auto p-4 space-y-3" ref={scrollRef}>
                                {messages.map(msg => {
                                    const isOwn = msg.sender_id === user.id;
                                    return (
                                        <div key={msg.id} className={`flex ${isOwn ? 'justify-end' : 'justify-start'}`}>
                                            <div className="max-w-[75%]">
                                                <div className={`rounded-2xl px-4 py-2 ${isOwn ? 'bg-[#FF671F] text-white rounded-br-sm' : 'bg-[#1A1A1A] text-white/90 rounded-bl-sm'}`}>
                                                    {msg.content && (
                                                        <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                                                    )}
                                                    {msg.adjunto && (
                                                        <div className={msg.content ? 'mt-2' : ''}>
                                                            <ImagenDelMensaje api={api} adjunto={msg.adjunto} propio={isOwn} />
                                                        </div>
                                                    )}
                                                </div>
                                                <div className={`flex items-center gap-1 mt-0.5 ${isOwn ? 'justify-end' : ''}`}>
                                                    <ChipCanal canal={msg.canal} />
                                                    <span className="text-[10px] text-white/25">{formatTime(msg.created_at)}</span>
                                                    {isOwn && (msg.read ? <CheckCheck className="w-3 h-3 text-[#FF671F]" /> : <Check className="w-3 h-3 text-white/25" />)}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                                {messages.length === 0 && <p className="text-white/20 text-sm text-center py-8">Sin mensajes con este cliente</p>}
                            </div>
                            <div className="px-3 pt-2 border-t border-[#222]">
                                <PreviaDelAdjunto adjunto={adjunto} onQuitar={() => setAdjunto(null)} />
                            </div>
                            <form onSubmit={handleSend} className="px-3 pb-3 flex items-center gap-2">
                                <AdjuntarImagen api={api} adjunto={adjunto} onAdjunto={setAdjunto}
                                    deshabilitado={sending} />
                                <Input value={newMessage} onChange={e => setNewMessage(e.target.value)} placeholder="Escribe tu respuesta..."
                                    className="flex-1 bg-[#0A0A0A] border-[#222] text-white" disabled={sending} data-testid="admin-message-input" />
                                <Button type="submit" size="icon" disabled={sending || (!newMessage.trim() && !adjunto)} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white" data-testid="admin-send-btn">
                                    <Send className="w-4 h-4" />
                                </Button>
                            </form>
                        </>
                    ) : (
                        <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
                            <MessageCircle className="w-12 h-12 text-white/10 mb-3" />
                            <p className="text-white/30 text-sm">Elige una conversación para leer y responder</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AdminMessagesPage;
