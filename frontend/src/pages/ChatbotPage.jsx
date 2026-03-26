import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, RefreshCw, Check, ChevronRight } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function ChatbotPage() {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState('init'); // init, config, building_meal, complete
  const [currentMeal, setCurrentMeal] = useState(1);
  const [macrosRestantes, setMacrosRestantes] = useState({ P: 0, H: 0, G: 0 });
  const [distribucion, setDistribucion] = useState(null);
  const [daySummary, setDaySummary] = useState(null);
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const getToken = () => localStorage.getItem('token');

  const addMessage = (content, isUser = false, data = null) => {
    setMessages(prev => [...prev, { content, isUser, data, timestamp: new Date() }]);
  };

  // Iniciar sesión de chatbot
  const startChat = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/chatbot/start`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        }
      });
      const data = await res.json();
      
      if (data.session_id) {
        setSessionId(data.session_id);
        setStep('config');
        addMessage(data.message, false);
      }
    } catch (error) {
      addMessage('Error al iniciar el chatbot. Por favor, recarga la página.', false);
    }
    setLoading(false);
  };

  // Configurar el día
  const configureDay = async (tipoDia) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/chatbot/configure?session_id=${sessionId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          tipo_dia: tipoDia,
          num_comidas: 4,
          momento_entreno: 1,
          opcion_peri: tipoDia === 'entrenamiento' ? 'intra_post' : 'sin_peri'
        })
      });
      const data = await res.json();
      
      if (data.distribucion) {
        setDistribucion(data.distribucion);
        setCurrentMeal(data.comida_actual);
        setMacrosRestantes(data.distribucion.comidas.C1);
        setStep('building_meal');
        addMessage(`Día de ${tipoDia}`, true);
        addMessage(data.mensaje, false);
      }
    } catch (error) {
      addMessage('Error al configurar el día.', false);
    }
    setLoading(false);
  };

  // Enviar mensaje
  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    
    const userMessage = input.trim();
    setInput('');
    addMessage(userMessage, true);
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/chatbot/message`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionId
        })
      });
      const data = await res.json();
      
      if (data.response) {
        // Actualizar estado
        if (data.state) {
          setCurrentMeal(data.state.comida_actual);
          setMacrosRestantes(data.state.restante);
          setStep(data.state.step);
        }
        
        // Mostrar respuesta
        if (data.response.action === 'meal_updated') {
          // Mostrar alimentos añadidos
          const foodsMsg = formatMealUpdate(data.response);
          addMessage(foodsMsg, false, data.response);
        } else {
          addMessage(data.response.message || JSON.stringify(data.response), false);
        }
      }
    } catch (error) {
      addMessage('Error al procesar el mensaje.', false);
    }
    setLoading(false);
    inputRef.current?.focus();
  };

  // Completar comida actual
  const completeMeal = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/chatbot/complete-meal?session_id=${sessionId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        }
      });
      const data = await res.json();
      
      if (data.dia_completo) {
        setStep('complete');
        setDaySummary(data.resumen);
        addMessage('Comida guardada ✓', true);
        addMessage(data.mensaje, false, data.resumen);
      } else {
        setCurrentMeal(data.comida_actual);
        setMacrosRestantes(data.objetivo);
        addMessage('Comida guardada ✓', true);
        addMessage(data.mensaje, false);
      }
    } catch (error) {
      addMessage('Error al completar la comida.', false);
    }
    setLoading(false);
  };

  // Formatear actualización de comida
  const formatMealUpdate = (response) => {
    let msg = '';
    
    if (response.foods_added?.length > 0) {
      msg += '**Alimentos añadidos:**\n';
      response.foods_added.forEach(f => {
        msg += `• ${f.nombre}: ${f.cantidad_display} (P=${f.macros?.P || 0}, H=${f.macros?.H || 0}, G=${f.macros?.G || 0})\n`;
      });
    }
    
    if (response.foods_not_found?.length > 0) {
      msg += '\n**No encontrados:**\n';
      response.foods_not_found.forEach(f => {
        msg += `• "${f.buscado}": ${f.razon}\n`;
      });
    }
    
    if (response.meal_status) {
      const ms = response.meal_status;
      msg += `\n**Comida ${ms.comida}:**\n`;
      msg += `Actual: P=${ms.actual?.P || 0}g, H=${ms.actual?.H || 0}g, G=${ms.actual?.G || 0}g\n`;
      msg += `Objetivo: P=${ms.objetivo?.P || 0}g, H=${ms.objetivo?.H || 0}g, G=${ms.objetivo?.G || 0}g\n`;
      msg += `Restante: P=${ms.restante?.P || 0}g, H=${ms.restante?.H || 0}g, G=${ms.restante?.G || 0}g`;
    }
    
    return msg;
  };

  // Reiniciar chat
  const resetChat = async () => {
    if (sessionId) {
      try {
        await fetch(`${API_URL}/api/chatbot/reset?session_id=${sessionId}`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${getToken()}` }
        });
      } catch (e) {}
    }
    setSessionId(null);
    setMessages([]);
    setStep('init');
    setCurrentMeal(1);
    setDistribucion(null);
    setDaySummary(null);
  };

  // Renderizar mensaje
  const renderMessage = (msg, idx) => {
    const isUser = msg.isUser;
    
    return (
      <div key={idx} className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
        <div className={`flex items-start gap-2 max-w-[85%] ${isUser ? 'flex-row-reverse' : ''}`}>
          <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
            isUser ? 'bg-orange-500' : 'bg-zinc-700'
          }`}>
            {isUser ? <User size={16} /> : <Bot size={16} />}
          </div>
          <div className={`rounded-2xl px-4 py-2 ${
            isUser 
              ? 'bg-orange-500 text-white rounded-br-md' 
              : 'bg-zinc-800 text-zinc-100 rounded-bl-md'
          }`}>
            <div className="whitespace-pre-wrap text-sm">
              {msg.content.split('**').map((part, i) => 
                i % 2 === 1 ? <strong key={i}>{part}</strong> : part
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Renderizar resumen del día
  const renderDaySummary = () => {
    if (!daySummary) return null;
    
    return (
      <div className="bg-zinc-800 rounded-xl p-4 mt-4">
        <h3 className="text-lg font-bold text-orange-500 mb-4">Resumen del Día</h3>
        
        {daySummary.comidas?.map((comida, idx) => (
          <div key={idx} className="mb-4 pb-4 border-b border-zinc-700 last:border-0">
            <h4 className="font-semibold text-zinc-300 mb-2">Comida {comida.numero}</h4>
            <div className="space-y-1 text-sm">
              {comida.alimentos?.map((a, i) => (
                <div key={i} className="text-zinc-400">
                  • {a.nombre}: {a.cantidad_display}
                </div>
              ))}
            </div>
            <div className="mt-2 text-xs text-zinc-500">
              Total: P={comida.macros?.P || 0}g | H={comida.macros?.H || 0}g | G={comida.macros?.G || 0}g
            </div>
          </div>
        ))}
        
        <div className="mt-4 pt-4 border-t border-zinc-600">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-orange-500">{daySummary.totales?.P || 0}g</div>
              <div className="text-xs text-zinc-500">Proteínas</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-blue-500">{daySummary.totales?.H || 0}g</div>
              <div className="text-xs text-zinc-500">Hidratos</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-yellow-500">{daySummary.totales?.G || 0}g</div>
              <div className="text-xs text-zinc-500">Grasas</div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-zinc-900 text-white flex flex-col">
      {/* Header */}
      <header className="bg-zinc-800 border-b border-zinc-700 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-orange-500 rounded-full flex items-center justify-center">
            <Bot size={24} />
          </div>
          <div>
            <h1 className="font-bold">Asistente de Nutrición</h1>
            <p className="text-xs text-zinc-400">
              {step === 'building_meal' && `Comida ${currentMeal} • Restante: P=${macrosRestantes.P}g H=${macrosRestantes.H}g G=${macrosRestantes.G}g`}
              {step === 'complete' && '¡Día completo!'}
              {step === 'init' && 'Listo para empezar'}
              {step === 'config' && 'Configurando día...'}
            </p>
          </div>
        </div>
        <button 
          onClick={resetChat}
          className="p-2 hover:bg-zinc-700 rounded-lg transition-colors"
          title="Reiniciar"
        >
          <RefreshCw size={20} />
        </button>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Pantalla inicial */}
        {step === 'init' && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-20 h-20 bg-orange-500/20 rounded-full flex items-center justify-center mb-4">
              <Bot size={40} className="text-orange-500" />
            </div>
            <h2 className="text-xl font-bold mb-2">¡Hola!</h2>
            <p className="text-zinc-400 mb-6 max-w-md">
              Soy tu asistente de nutrición. Te ayudaré a montar tu dieta del día, 
              comida por comida, respetando tus macros objetivo.
            </p>
            <button
              onClick={startChat}
              disabled={loading}
              className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-3 rounded-xl font-semibold flex items-center gap-2 transition-colors disabled:opacity-50"
            >
              {loading ? <Loader2 className="animate-spin" size={20} /> : <ChevronRight size={20} />}
              Empezar
            </button>
          </div>
        )}

        {/* Botones de configuración */}
        {step === 'config' && (
          <div className="mt-4">
            {messages.map(renderMessage)}
            <div className="flex gap-3 justify-center mt-4">
              <button
                onClick={() => configureDay('entrenamiento')}
                disabled={loading}
                className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-3 rounded-xl font-semibold transition-colors disabled:opacity-50"
              >
                Día de Entrenamiento
              </button>
              <button
                onClick={() => configureDay('descanso')}
                disabled={loading}
                className="bg-zinc-700 hover:bg-zinc-600 text-white px-6 py-3 rounded-xl font-semibold transition-colors disabled:opacity-50"
              >
                Día de Descanso
              </button>
            </div>
          </div>
        )}

        {/* Mensajes del chat */}
        {(step === 'building_meal' || step === 'complete') && (
          <>
            {messages.map(renderMessage)}
            {step === 'complete' && renderDaySummary()}
          </>
        )}

        {loading && (
          <div className="flex justify-start mb-4">
            <div className="flex items-center gap-2 bg-zinc-800 rounded-2xl px-4 py-2">
              <Loader2 className="animate-spin" size={16} />
              <span className="text-sm text-zinc-400">Pensando...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      {step === 'building_meal' && (
        <div className="border-t border-zinc-700 p-4 bg-zinc-800 mb-12 relative z-50">
          <div className="flex gap-2">
            <button
              onClick={completeMeal}
              disabled={loading}
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-3 rounded-xl font-semibold flex items-center gap-2 transition-colors disabled:opacity-50"
              data-testid="save-meal-btn"
            >
              <Check size={20} />
              Guardar
            </button>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
              placeholder="Escribe lo que quieres comer..."
              className="flex-1 bg-zinc-700 border border-zinc-600 rounded-xl px-4 py-3 text-white placeholder-zinc-500 focus:outline-none focus:border-orange-500"
              disabled={loading}
              data-testid="chat-input"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-3 rounded-xl transition-colors disabled:opacity-50"
              data-testid="send-message-btn"
            >
              <Send size={20} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
