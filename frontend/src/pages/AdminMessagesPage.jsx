import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { Send, MessageCircle, Search, CheckCheck, Check } from 'lucide-react';

// Bandeja de mensajes del staff: conversaciones a la izquierda, chat a la derecha.
const AdminMessagesPage = () => {
    const { api, user } = useAuth();
    const [conversations, setConversations] = useState([]);
    const [selected, setSelected] = useState(null); // user_id de la conversacion abierta
    const [messages, setMessages] = useState([]);
    const [newMessage, setNewMessage] = useState('');
    const [sending, setSending] = useState(false);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
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
        if (!newMessage.trim() || !selected) return;
        setSending(true);
        try {
            await api.post('/messages', { receiver_id: selected, content: newMessage.trim() });
            setNewMessage('');
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
        !search || c.user?.name?.toLowerCase().includes(search.toLowerCase()) ||
        c.user?.email?.toLowerCase().includes(search.toLowerCase())
    );
    const selectedConv = conversations.find(c => c.user_id === selected);

    if (loading) return <div className="p-6 bg-[#0A0A0A] min-h-screen"><div className="animate-pulse space-y-4"><div className="h-8 bg-[#222] rounded w-1/4" /><div className="h-96 bg-[#111] rounded-xl" /></div></div>;

    return (
        <div className="p-4 md:p-6 h-[calc(100vh-4rem)] lg:h-screen flex flex-col bg-[#0A0A0A]" data-testid="admin-messages-page">
            <h1 className="text-2xl font-bold text-white tracking-tight mb-4" style={{ fontFamily: 'Barlow Condensed' }}>MENSAJES</h1>
            <div className="flex-1 flex gap-4 min-h-0">
                {/* Lista de conversaciones */}
                <div className={`w-full md:w-80 flex-shrink-0 bg-[#111] border border-[#222] rounded-xl flex flex-col min-h-0 ${selected ? 'hidden md:flex' : 'flex'}`}>
                    <div className="p-3 border-b border-[#222]">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                            <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar cliente..." className="pl-9 bg-[#0A0A0A] border-[#222] text-white" />
                        </div>
                    </div>
                    <div className="flex-1 overflow-y-auto">
                        {filtered.map(c => (
                            <button key={c.user_id} onClick={() => openConversation(c.user_id)}
                                className={`w-full text-left px-4 py-3 border-b border-[#1A1A1A] transition-all hover:bg-white/5 ${selected === c.user_id ? 'bg-[#FF671F]/10 border-l-2 border-l-[#FF671F]' : ''}`}
                                data-testid={`conv-${c.user_id}`}>
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-white text-sm font-medium truncate">{c.user?.name || c.user?.email || 'Sin nombre'}</p>
                                    <span className="text-white/30 text-[10px] flex-shrink-0">{formatTime(c.last_message.created_at)}</span>
                                </div>
                                <div className="flex items-center justify-between gap-2 mt-0.5">
                                    <p className="text-white/40 text-xs truncate">
                                        {c.last_message.sender_id === user.id ? 'Tú: ' : ''}{c.last_message.content}
                                    </p>
                                    {c.unread > 0 && (
                                        <span className="bg-[#FF671F] text-white text-[10px] font-bold rounded-full min-w-[18px] h-[18px] px-1 flex items-center justify-center flex-shrink-0">{c.unread}</span>
                                    )}
                                </div>
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
                                                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                                                </div>
                                                <div className={`flex items-center gap-1 mt-0.5 ${isOwn ? 'justify-end' : ''}`}>
                                                    <span className="text-[10px] text-white/25">{formatTime(msg.created_at)}</span>
                                                    {isOwn && (msg.read ? <CheckCheck className="w-3 h-3 text-[#FF671F]" /> : <Check className="w-3 h-3 text-white/25" />)}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                                {messages.length === 0 && <p className="text-white/20 text-sm text-center py-8">Sin mensajes con este cliente</p>}
                            </div>
                            <form onSubmit={handleSend} className="p-3 border-t border-[#222] flex items-center gap-2">
                                <Input value={newMessage} onChange={e => setNewMessage(e.target.value)} placeholder="Escribe tu respuesta..."
                                    className="flex-1 bg-[#0A0A0A] border-[#222] text-white" disabled={sending} data-testid="admin-message-input" />
                                <Button type="submit" size="icon" disabled={sending || !newMessage.trim()} className="bg-[#FF671F] hover:bg-[#FF671F]/90 text-white" data-testid="admin-send-btn">
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
