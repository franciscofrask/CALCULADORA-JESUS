import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Send, Bot, User, Loader2, RefreshCw, Check, ChevronRight, Download, ClipboardList } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Persistencia de la conversación durante la sesión (sobrevive a navegación y recargas
// de la pestaña; se limpia al cerrar la pestaña o al reiniciar el chat).
const PERSIST_KEY = 'chatbot_session_state';
const loadPersisted = () => {
  try { return JSON.parse(sessionStorage.getItem(PERSIST_KEY)) || {}; }
  catch { return {}; }
};

export default function ChatbotPage() {
  const navigate = useNavigate();

  // Snapshot persistido leído una sola vez al montar
  const persistedRef = useRef(undefined);
  if (persistedRef.current === undefined) persistedRef.current = loadPersisted();
  const p = persistedRef.current;

  const [sessionId, setSessionId] = useState(p.sessionId ?? null);
  const [messages, setMessages] = useState(p.messages ?? []);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(p.step ?? 'init'); // init, config, building_meal, complete
  // Config conversacional híbrida: subfases mientras step === 'config'
  const [configStage, setConfigStage] = useState(p.configStage ?? 'date'); // date, tipo, comidas
  const [targetDate, setTargetDate] = useState(p.targetDate ?? null); // YYYY-MM-DD destino del volcado
  const [tipoDia, setTipoDia] = useState(p.tipoDia ?? null);
  const [numComidas, setNumComidas] = useState(p.numComidas ?? 4);
  const [opcionPeri, setOpcionPeri] = useState(p.opcionPeri ?? 'intra_post');
  const [momentoEntreno, setMomentoEntreno] = useState(p.momentoEntreno ?? 1);
  const [singleMeal, setSingleMeal] = useState(p.singleMeal ?? false);
  const [mealNombre, setMealNombre] = useState(p.mealNombre ?? 'Comida 1');
  const [saving, setSaving] = useState(false);
  const [currentMeal, setCurrentMeal] = useState(p.currentMeal ?? 1);
  const [macrosRestantes, setMacrosRestantes] = useState(p.macrosRestantes ?? { P: 0, H: 0, G: 0 });
  const [distribucion, setDistribucion] = useState(p.distribucion ?? null);
  const [daySummary, setDaySummary] = useState(p.daySummary ?? null);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  // Decisión (una sola vez) sobre sobrescribir el día al sincronizar con nutrición
  const autoSyncRef = useRef(p.autoSync ?? { decided: false, enabled: true });

  // Guardar la conversación en sessionStorage cada vez que cambia algo relevante
  useEffect(() => {
    const snapshot = {
      sessionId, messages, step, configStage, targetDate, tipoDia, numComidas,
      opcionPeri, momentoEntreno, singleMeal, mealNombre, currentMeal, macrosRestantes, distribucion, daySummary,
      autoSync: autoSyncRef.current,
    };
    try { sessionStorage.setItem(PERSIST_KEY, JSON.stringify(snapshot)); } catch (e) {}
  }, [sessionId, messages, step, configStage, targetDate, tipoDia, numComidas,
      opcionPeri, momentoEntreno, singleMeal, mealNombre, currentMeal, macrosRestantes, distribucion, daySummary]);

  // Al montar: si retomamos una sesión, verificar que sigue viva en el backend.
  // Si se perdió (p. ej. reinicio del backend), reiniciar limpio.
  useEffect(() => {
    const sid = p.sessionId;
    if (!sid || !p.step || p.step === 'init') return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API_URL}/api/chatbot/session-exists?session_id=${sid}`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        const d = await r.json();
        if (!cancelled && !d.exists) {
          try { sessionStorage.removeItem(PERSIST_KEY); } catch (e) {}
          setSessionId(null);
          setMessages([]);
          setStep('init');
          setConfigStage('date');
          setTargetDate(null);
          setTipoDia(null);
          setNumComidas(4);
          setOpcionPeri('intra_post');
          setMomentoEntreno(1);
          setSingleMeal(false);
          setMealNombre('Comida 1');
          setCurrentMeal(1);
          setDistribucion(null);
          setDaySummary(null);
          autoSyncRef.current = { decided: false, enabled: true };
        }
      } catch (e) {}
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  // ── Fechas (resolución en el cliente para respetar el timezone local) ──
  const todayLocal = () => {
    const n = new Date();
    return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`;
  };

  const stripAccents = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '');

  // Convierte texto/botón en YYYY-MM-DD; null si no se entiende.
  const parseTargetDate = (raw) => {
    if (!raw) return null;
    const t = stripAccents(raw.toString().trim().toLowerCase());
    if (t === 'hoy') return todayLocal();
    if (t === 'manana') {
      const d = new Date(todayLocal() + 'T12:00:00');
      d.setDate(d.getDate() + 1);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }
    if (/^\d{4}-\d{2}-\d{2}$/.test(t)) return t;
    const dm = t.match(/^(\d{1,2})\/(\d{1,2})(?:\/(\d{4}))?$/);
    if (dm) {
      const day = +dm[1], mon = +dm[2], yr = dm[3] ? +dm[3] : new Date().getFullYear();
      if (mon >= 1 && mon <= 12 && day >= 1 && day <= 31) {
        return `${yr}-${String(mon).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      }
    }
    return null;
  };

  const formatDateLabel = (iso) => {
    if (iso === todayLocal()) return 'Hoy';
    const [y, m, d] = iso.split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long' });
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
        setConfigStage('date');
        addMessage('¡Hola! Soy tu asistente de nutrición. ¿Para qué día quieres montar la dieta?', false);
      }
    } catch (error) {
      addMessage('Error al iniciar el chatbot. Por favor, recarga la página.', false);
    }
    setLoading(false);
  };

  // Maneja una respuesta de configuración (desde botón o texto libre)
  const submitConfig = (rawValue) => {
    const value = (rawValue ?? '').toString().trim();
    if (!value || loading) return;

    if (configStage === 'date') {
      const iso = parseTargetDate(value);
      if (!iso) {
        addMessage(value, true);
        addMessage('No entendí la fecha. Dime "Hoy", "Mañana" o una fecha como 2026-07-01.', false);
        return;
      }
      setTargetDate(iso);
      addMessage(formatDateLabel(iso), true);
      addMessage('¿Es día de entrenamiento o de descanso?', false);
      setConfigStage('tipo');
      return;
    }

    if (configStage === 'tipo') {
      const v = stripAccents(value.toLowerCase());
      const tipo = v.includes('entren') ? 'entrenamiento' : v.includes('descan') ? 'descanso' : null;
      if (!tipo) {
        addMessage(value, true);
        addMessage('Dime "Entrenamiento" o "Descanso".', false);
        return;
      }
      setTipoDia(tipo);
      addMessage(tipo === 'entrenamiento' ? 'Día de entrenamiento' : 'Día de descanso', true);
      addMessage('¿Cuántas comidas vas a hacer, 3 o 4?', false);
      setConfigStage('comidas');
      return;
    }

    if (configStage === 'comidas') {
      const v = stripAccents(value.toLowerCase());
      const isSingle = v.includes('bloque') || v.includes('unic') || v.includes('una comida') || value.trim() === '1';
      const n = isSingle ? 1 : (value.includes('3') ? 3 : value.includes('4') ? 4 : null);
      if (!n) {
        addMessage(value, true);
        addMessage('Dime 3 comidas, 4 comidas o bloque único.', false);
        return;
      }
      setNumComidas(n);
      setSingleMeal(isSingle);
      addMessage(isSingle ? 'Bloque único (1 comida)' : `${n} comidas`, true);
      if (tipoDia === 'entrenamiento') {
        addMessage('¿Cómo gestionas el peri-entreno (Intra/Post)?', false);
        setConfigStage('peri');
      } else {
        configureDay(tipoDia, n, 'sin_peri', 1, isSingle);
      }
      return;
    }

    if (configStage === 'peri') {
      const v = stripAccents(value.toLowerCase());
      let op = null;
      if (v.includes('intra') && v.includes('post')) op = 'intra_post';
      else if (v.includes('solo') && v.includes('post')) op = 'solo_post';
      else if (v.includes('solo') && v.includes('intra')) op = 'solo_intra';
      else if (v.includes('sin') || v.includes('nada') || v.includes('ningun')) op = 'sin_peri';
      else if (v.includes('post')) op = 'solo_post';
      else if (v.includes('intra')) op = 'solo_intra';
      if (!op) {
        addMessage(value, true);
        addMessage('Elige: "Intra + Post", "Solo Post", "Solo Intra" o "Sin peri".', false);
        return;
      }
      setOpcionPeri(op);
      addMessage(periLabel(op), true);
      // En bloque único las peri van tras la comida única: no preguntamos el momento.
      if (singleMeal) {
        configureDay(tipoDia, numComidas, op, 1, true);
      } else {
        addMessage('¿Cuándo entrenas?', false);
        setConfigStage('momento');
      }
      return;
    }

    if (configStage === 'momento') {
      const v = stripAccents(value.toLowerCase());
      let m = null;
      if (v.includes('ayun')) m = 0;
      else if (v.includes('3')) m = 3;
      else if (v.includes('2')) m = 2;
      else if (v.includes('1')) m = 1;
      if (m === null) {
        addMessage(value, true);
        addMessage('Dime: "En ayunas", o "Después de la comida 1/2/3".', false);
        return;
      }
      setMomentoEntreno(m);
      addMessage(momentoLabel(m), true);
      configureDay(tipoDia, numComidas, opcionPeri, m, singleMeal);
    }
  };

  const periLabel = (op) => ({
    intra_post: 'Intra + Post',
    solo_post: 'Solo Post',
    solo_intra: 'Solo Intra',
    sin_peri: 'Sin peri',
  }[op] || op);

  const momentoLabel = (m) => ({
    0: 'En ayunas',
    1: 'Después de la comida 1',
    2: 'Después de la comida 2',
    3: 'Después de la comida 3',
  }[m] || `Momento ${m}`);

  // Configurar el día (llama al backend con tipo, nº de comidas, peri, momento y bloque único)
  const configureDay = async (tipo, comidas, opPeri, momento = 1, single = false) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/chatbot/configure?session_id=${sessionId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          tipo_dia: tipo,
          num_comidas: comidas,
          momento_entreno: momento,
          opcion_peri: opPeri || (tipo === 'entrenamiento' ? 'intra_post' : 'sin_peri'),
          single_meal: single
        })
      });
      const data = await res.json();

      if (data.distribucion) {
        setDistribucion(data.distribucion);
        setCurrentMeal(data.comida_actual);
        setMealNombre(data.meal_nombre || 'Comida 1');
        setMacrosRestantes(data.objetivo || data.distribucion.comidas.C1);
        setStep('building_meal');
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
          if (data.state.meal_nombre) setMealNombre(data.state.meal_nombre);
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
      
      // Si la comida está vacía, mostrar error
      if (data.error) {
        addMessage(data.error, false);
        setLoading(false);
        return;
      }
      
      if (data.dia_completo) {
        setStep('complete');
        setDaySummary(data.resumen);
        addMessage('Comida guardada ✓', true);
        addMessage(data.mensaje, false, data.resumen);
      } else {
        setCurrentMeal(data.comida_actual);
        setMacrosRestantes(data.objetivo);
        if (data.meal_nombre) setMealNombre(data.meal_nombre);
        addMessage('Comida guardada ✓', true);
        addMessage(data.mensaje, false);
      }

      // Sincronizar la dieta en la pestaña de nutrición tras guardar cada comida
      await syncToDiet();
    } catch (error) {
      addMessage('Error al completar la comida.', false);
    }
    setLoading(false);
  };

  // Vuelca el progreso actual en la pestaña de nutrición del día destino.
  // Decide UNA sola vez si sobrescribir un día que ya tuviera dieta.
  const syncToDiet = async () => {
    if (!sessionId || !targetDate) return;
    try {
      if (!autoSyncRef.current.decided) {
        const ex = await fetch(`${API_URL}/api/diets/${targetDate}`, {
          headers: { 'Authorization': `Bearer ${getToken()}` }
        }).then(r => r.json());
        const hasFood = ex.exists && Object.values(ex.comidas || {}).some(m => (m?.alimentos || []).length > 0);
        autoSyncRef.current.decided = true;
        if (hasFood) {
          const ok = window.confirm(
            `Ya tienes una dieta guardada el ${formatDateLabel(targetDate)}. ¿Quieres que el chatbot la vaya actualizando con esta?`
          );
          autoSyncRef.current.enabled = ok;
          if (!ok) {
            addMessage('Vale, no tocaré tu dieta guardada. Podrás volcarla manualmente al terminar.', false);
            return;
          }
        }
      }

      if (!autoSyncRef.current.enabled) return;

      const res = await fetch(
        `${API_URL}/api/chatbot/save-to-diet?session_id=${sessionId}&fecha=${targetDate}&overwrite=true`,
        { method: 'POST', headers: { 'Authorization': `Bearer ${getToken()}` } }
      );
      const data = await res.json();
      if (res.ok && !data.needs_confirmation) {
        localStorage.setItem('nutrition_last_date', targetDate);
        addMessage(`✅ Guardado en tu pestaña de nutrición (${formatDateLabel(targetDate)}).`, false);
      }
    } catch (e) {
      // Silencioso: no bloquea el flujo del chat si la sincronización falla
    }
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
      msg += '\n**No encontrados/No caben:**\n';
      response.foods_not_found.forEach(f => {
        msg += `• "${f.buscado}": ${f.razon}\n`;
        if (f.sugerencia) {
          msg += `  ${f.sugerencia}\n`;
        }
      });
    }
    
    if (response.meal_status) {
      const ms = response.meal_status;
      msg += `\n**Comida ${ms.comida}:**\n`;
      msg += `Actual: P=${ms.actual?.P || 0}g, H=${ms.actual?.H || 0}g, G=${ms.actual?.G || 0}g\n`;
      msg += `Objetivo: P=${ms.objetivo?.P || 0}g, H=${ms.objetivo?.H || 0}g, G=${ms.objetivo?.G || 0}g\n`;
      msg += `Restante: P=${ms.restante?.P || 0}g, H=${ms.restante?.H || 0}g, G=${ms.restante?.G || 0}g`;
      
      // Si está cuadrado, indicarlo
      if (ms.cuadrado) {
        msg += '\n\n✅ **¡Comida cuadrada!** Puedes guardarla.';
      }
    }
    
    // Mostrar sugerencia de lo que falta
    if (response.sugerencia) {
      msg += `\n\n💡 ${response.sugerencia}`;
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
    setConfigStage('date');
    setTargetDate(null);
    setTipoDia(null);
    setNumComidas(4);
    setOpcionPeri('intra_post');
    setMomentoEntreno(1);
    setSingleMeal(false);
    setMealNombre('Comida 1');
    setCurrentMeal(1);
    setDistribucion(null);
    setDaySummary(null);
    autoSyncRef.current = { decided: false, enabled: true };
    try { sessionStorage.removeItem(PERSIST_KEY); } catch (e) {}
  };

  // Renderizar mensaje
  const renderMessage = (msg, idx) => {
    const isUser = msg.isUser;
    
    return (
      <div key={idx} className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
        <div className={`flex items-start gap-2 max-w-[85%] ${isUser ? 'flex-row-reverse' : ''}`}>
          <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
            isUser ? 'bg-orange-500' : 'bg-muted'
          }`}>
            {isUser ? <User size={16} /> : <Bot size={16} />}
          </div>
          <div className={`rounded-2xl px-4 py-2 ${
            isUser 
              ? 'bg-orange-500 text-white rounded-br-md' 
              : 'bg-card text-foreground rounded-bl-md'
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
  // Exportar a PDF
  const exportToPDF = async () => {
    if (!sessionId) return;
    
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/chatbot/export-pdf?session_id=${sessionId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${getToken()}`
        }
      });
      
      if (!res.ok) throw new Error('Error al generar PDF');
      
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dieta_jg12_${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      addMessage('Error al exportar el PDF. Inténtalo de nuevo.', false);
    }
    setLoading(false);
  };

  // Volcar la dieta construida en la pestaña de nutrición del día destino
  const saveToDiet = async (force = false) => {
    if (!sessionId || !targetDate || saving) return;
    setSaving(true);
    try {
      // Si la auto-sincronización ya está activa, el día ya es nuestro: no re-preguntar
      if (!force && autoSyncRef.current.decided && autoSyncRef.current.enabled) {
        force = true;
      }

      // 1. Si no forzamos, comprobar si ese día ya tiene alimentos
      if (!force) {
        const exRes = await fetch(`${API_URL}/api/diets/${targetDate}`, {
          headers: { 'Authorization': `Bearer ${getToken()}` }
        });
        const ex = await exRes.json();
        const hasFood = ex.exists && Object.values(ex.comidas || {}).some(m => (m?.alimentos || []).length > 0);
        if (hasFood) {
          const ok = window.confirm(`Ya tienes una dieta guardada el ${formatDateLabel(targetDate)}. ¿Sobrescribirla?`);
          if (!ok) { setSaving(false); return; }
          force = true;
        }
      }

      // 2. Volcar
      const res = await fetch(
        `${API_URL}/api/chatbot/save-to-diet?session_id=${sessionId}&fecha=${targetDate}&overwrite=${force}`,
        { method: 'POST', headers: { 'Authorization': `Bearer ${getToken()}` } }
      );
      const data = await res.json();

      if (data.needs_confirmation) {
        const ok = window.confirm(data.message || '¿Sobrescribir la dieta existente?');
        if (ok) { setSaving(false); return saveToDiet(true); }
        setSaving(false);
        return;
      }

      if (!res.ok) throw new Error(data.detail || 'Error al volcar');

      // 3. Handoff a la pestaña de nutrición en ese día
      addMessage(`✅ Dieta volcada en tu pestaña de nutrición (${formatDateLabel(targetDate)}). Abriéndola…`, false);
      localStorage.setItem('nutrition_last_date', targetDate);
      setTimeout(() => navigate('/dashboard/nutrition'), 600);
    } catch (error) {
      addMessage('Error al volcar la dieta. Inténtalo de nuevo.', false);
    }
    setSaving(false);
  };

  const renderDaySummary = () => {
    if (!daySummary) return null;
    
    return (
      <div className="bg-card rounded-xl p-4 mt-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-orange-500">Resumen del Día</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => saveToDiet(false)}
              disabled={saving || loading}
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg font-semibold flex items-center gap-2 transition-colors disabled:opacity-50"
              data-testid="volcar-dieta-btn"
            >
              {saving ? <Loader2 className="animate-spin" size={18} /> : <ClipboardList size={18} />}
              Volcar a mi dieta
            </button>
            <button
              onClick={exportToPDF}
              disabled={loading}
              className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg font-semibold flex items-center gap-2 transition-colors disabled:opacity-50"
              data-testid="export-pdf-btn"
            >
              <Download size={18} />
              Exportar PDF
            </button>
          </div>
        </div>
        
        {daySummary.comidas?.map((comida, idx) => (
          <div key={idx} className="mb-4 pb-4 border-b border-border last:border-0">
            <h4 className="font-semibold text-foreground mb-2">{comida.nombre || `Comida ${comida.numero}`}</h4>
            <div className="space-y-1 text-sm">
              {comida.alimentos?.map((a, i) => (
                <div key={i} className="text-muted-foreground">
                  • {a.nombre}: {a.cantidad_display}
                </div>
              ))}
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              Total: P={comida.macros?.P || 0}g | H={comida.macros?.H || 0}g | G={comida.macros?.G || 0}g
            </div>
          </div>
        ))}
        
        <div className="mt-4 pt-4 border-t border-input">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-orange-500">{daySummary.totales?.P || 0}g</div>
              <div className="text-xs text-muted-foreground">Proteínas</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-blue-500">{daySummary.totales?.H || 0}g</div>
              <div className="text-xs text-muted-foreground">Hidratos</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-yellow-500">{daySummary.totales?.G || 0}g</div>
              <div className="text-xs text-muted-foreground">Grasas</div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Header */}
      <header className="bg-card border-b border-border px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-orange-500 rounded-full flex items-center justify-center">
            <Bot size={24} />
          </div>
          <div>
            <h1 className="font-bold" data-testid="chatbot-heading">Asistente de Nutrición</h1>
            <p className="text-xs text-muted-foreground">
              {step === 'building_meal' && `${mealNombre} • Restante: P=${macrosRestantes.P}g H=${macrosRestantes.H}g G=${macrosRestantes.G}g`}
              {step === 'complete' && '¡Día completo!'}
              {step === 'init' && 'Listo para empezar'}
              {step === 'config' && 'Configurando día...'}
            </p>
          </div>
        </div>
        <button 
          onClick={resetChat}
          className="p-2 hover:bg-muted rounded-lg transition-colors"
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
            <p className="text-muted-foreground mb-6 max-w-md">
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

        {/* Configuración conversacional (híbrida: botones + texto libre) */}
        {step === 'config' && (
          <div className="mt-4">
            {messages.map(renderMessage)}
            <div className="flex flex-wrap gap-3 justify-center mt-4">
              {configStage === 'date' && [
                { label: 'Hoy', value: 'hoy' },
                { label: 'Mañana', value: 'manana' },
              ].map(opt => (
                <button
                  key={opt.value}
                  onClick={() => submitConfig(opt.value)}
                  disabled={loading}
                  className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-3 rounded-xl font-semibold transition-colors disabled:opacity-50"
                >
                  {opt.label}
                </button>
              ))}
              {configStage === 'tipo' && [
                { label: 'Día de Entrenamiento', value: 'entrenamiento' },
                { label: 'Día de Descanso', value: 'descanso' },
              ].map(opt => (
                <button
                  key={opt.value}
                  onClick={() => submitConfig(opt.value)}
                  disabled={loading}
                  className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-3 rounded-xl font-semibold transition-colors disabled:opacity-50"
                >
                  {opt.label}
                </button>
              ))}
              {configStage === 'comidas' && [
                { label: '3 comidas', value: '3' },
                { label: '4 comidas', value: '4' },
                { label: 'Bloque único', value: 'bloque unico' },
              ].map(opt => (
                <button
                  key={opt.value}
                  onClick={() => submitConfig(opt.value)}
                  disabled={loading}
                  className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-3 rounded-xl font-semibold transition-colors disabled:opacity-50"
                >
                  {opt.label}
                </button>
              ))}
              {configStage === 'peri' && [
                { label: 'Intra + Post', value: 'intra y post' },
                { label: 'Solo Post', value: 'solo post' },
                { label: 'Solo Intra', value: 'solo intra' },
                { label: 'Sin peri', value: 'sin peri' },
              ].map(opt => (
                <button
                  key={opt.value}
                  onClick={() => submitConfig(opt.value)}
                  disabled={loading}
                  className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-3 rounded-xl font-semibold transition-colors disabled:opacity-50"
                >
                  {opt.label}
                </button>
              ))}
              {configStage === 'momento' && [
                { label: 'En ayunas', value: 'ayunas' },
                ...Array.from({ length: Math.max(1, numComidas - 1) }, (_, i) => ({
                  label: `Después de comida ${i + 1}`, value: `comida ${i + 1}`,
                })),
              ].map(opt => (
                <button
                  key={opt.value}
                  onClick={() => submitConfig(opt.value)}
                  disabled={loading}
                  className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-3 rounded-xl font-semibold transition-colors disabled:opacity-50"
                >
                  {opt.label}
                </button>
              ))}
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
            <div className="flex items-center gap-2 bg-card rounded-2xl px-4 py-2">
              <Loader2 className="animate-spin" size={16} />
              <span className="text-sm text-muted-foreground">Pensando...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input de texto libre durante la configuración (fecha, tipo, comidas) */}
      {step === 'config' && (
        <div className="border-t border-border p-4 bg-card mb-12 relative z-50">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { submitConfig(input); setInput(''); } }}
              placeholder={configStage === 'date' ? 'O escribe una fecha (ej: 2026-07-01)…' : 'O escríbelo aquí…'}
              className="flex-1 bg-muted border border-input rounded-xl px-4 py-3 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-brand"
              disabled={loading}
              data-testid="config-input"
            />
            <button
              onClick={() => { submitConfig(input); setInput(''); }}
              disabled={loading || !input.trim()}
              className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-3 rounded-xl transition-colors disabled:opacity-50"
            >
              <Send size={20} />
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      {step === 'building_meal' && (
        <div className="border-t border-border p-4 bg-card mb-12 relative z-50">
          <div className="flex gap-2">
            <button
              onClick={completeMeal}
              disabled={loading}
              className="bg-green-600 hover:bg-green-700 text-foreground px-4 py-3 rounded-xl font-semibold flex items-center gap-2 transition-colors disabled:opacity-50"
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
              className="flex-1 bg-muted border border-input rounded-xl px-4 py-3 text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-brand"
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
