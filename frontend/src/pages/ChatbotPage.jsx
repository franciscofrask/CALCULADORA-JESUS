import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { leer as leerLocal, escribir as escribirLocal } from '../lib/almacenLocal';
import { useConfirm } from '../components/ui/confirm';
import { Send, Bot, User, Loader2, RefreshCw, Check, ChevronRight, Download, ClipboardList } from 'lucide-react';
import ChatMealSummary from '../components/nutrition/ChatMealSummary';
import ChatDayOverview from '../components/nutrition/ChatDayOverview';
import ChatSuggestions from '../components/nutrition/ChatSuggestions';
import ChatMenus from '../components/nutrition/ChatMenus';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Ni la configuración del día ("mejor 3 comidas", "en ayunas", "sin peri") ni la FECHA
// ("mañana", "el jueves") se parsean aquí con regex: las entiende el asistente-agente en
// el backend (configurar_dia y cambiar_de_dia) y vuelven en `state.config` /
// `state.fecha_pedida` de cada respuesta. El front solo obedece y recarga de Nutrición la
// configuración del día al que se va.
//
// El regex de la fecha se quitó el 08-08: pedía la palabra al principio de la frase, así
// que "hoy es día de descanso" -- dos peticiones en una -- se leía como "vete al día de
// hoy", cambiaba de fecha, se dejaba lo de descanso y ni siquiera llegaba a mandar el
// mensaje al backend.

// Ninguna petición del chat puede quedarse esperando para siempre.
//
// El 08-08 el chat se quedó tres minutos en «Actualizando la comida...» con el campo
// bloqueado y sin más salida que recargar; y recargando volvía a pasar, porque el que se
// colgaba entonces era el ARRANQUE. Cuando el backend acepta la conexión y luego no
// responde (se cae, se reinicia, la red se corta), un fetch sin `signal` no termina
// nunca: el `finally` que desbloquea la pantalla no llega, y da igual dónde esté escrito.
//
// 120 s es de sobra para lo más lento que hace el asistente, y sigue siendo mucho menos
// que «para siempre». El streaming tiene su propio tope, y ese es al silencio.
const TOPE_MS = 120000;

const fetchConTope = async (url, opciones = {}, ms = TOPE_MS) => {
  const ctrl = new AbortController();
  const campana = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...opciones, signal: ctrl.signal });
  } finally {
    clearTimeout(campana);
  }
};

const ETIQUETA_PERI = {
  intra_post: 'intra + post', solo_post: 'solo post',
  solo_intra: 'solo intra', sin_peri: 'sin peri',
};
const ETIQUETA_MOMENTO = {
  0: 'entrenas en ayunas', 1: 'entrenas tras la Comida 1',
  2: 'entrenas tras la Comida 2', 3: 'entrenas tras la Comida 3',
};

/** El resumen de la configuración, en una línea y en el mismo orden siempre. */
const resumenConfig = ({ tipo_dia, num_comidas, single_meal, momento_entreno, opcion_peri }) => {
  const partes = [`día de ${tipo_dia === 'descanso' ? 'descanso' : 'entreno'}`];
  partes.push(single_meal || num_comidas === 1 ? 'bloque único' : `${num_comidas} comidas`);
  if (tipo_dia !== 'descanso') {
    partes.push(ETIQUETA_MOMENTO[momento_entreno] || ETIQUETA_MOMENTO[1]);
    partes.push(ETIQUETA_PERI[opcion_peri] || 'intra + post');
  }
  return partes.join(', ');
};

// Persistencia de la conversación durante la sesión (sobrevive a navegación y recargas
// de la pestaña; se limpia al cerrar la pestaña o al reiniciar el chat).
//
// LA CONVERSACIÓN LLEVA DUEÑO (Francisco, 11-08-2026).
//
// Se guardaba en una clave suelta, `chatbot_session_state`, sin decir de quién era. Como el
// entrenador entra en la cuenta de su cliente desde la misma pestaña (ver core/actuar_como.py),
// al abrir el asistente allí le salía SU PROPIA conversación dentro de la sesión del cliente.
// Es el mismo fallo que ya se arregló para el día de Nutrición en el punto 4.7 del 09-08, y el
// asistente se había quedado fuera: allí se le puso dueño al día, pero no a la conversación.
//
// Aquí es sessionStorage y no localStorage, así que no vale `lib/almacenLocal`, pero la regla
// es la misma: sin id no se guarda nada, que es mejor que guardarlo donde lo vea otro.
const claveChat = (uid) => (uid ? `u:${uid}:chatbot_session_state` : null);
const CLAVE_HUERFANA = 'chatbot_session_state';

const loadPersisted = (uid) => {
  const k = claveChat(uid);
  if (!k) return {};
  try { return JSON.parse(sessionStorage.getItem(k)) || {}; }
  catch { return {}; }
};

export default function ChatbotPage() {
  const { confirm } = useConfirm();
  const navigate = useNavigate();
  // EL DÍA QUE SE ESTÁ MIRANDO, GUARDADO CON DUEÑO (punto 4.7). Nutrición ya lo pasó a
  // `u:<id>:nutrition_last_date` cuando se arregló que la dieta de un cliente se viera en
  // la cuenta del siguiente, y el asistente se quedó fuera: seguía leyendo y escribiendo la
  // clave suelta. Con eso, en un ordenador compartido el asistente arrancaba en el día del
  // anterior, y además iba desincronizado con Nutrición, que ya leía la clave con dueño.
  const { user } = useAuth();
  const uid = user?.id || null;
  const diaEnNutricion = () => leerLocal('nutrition_last_date', uid);
  // El sello del dia va SIEMPRE con la fecha (QA 15-08): Nutricion solo restaura la fecha
  // guardada si el sello es de hoy, y aqui se escribia la fecha sin sello, asi que salir
  // del chat abria Nutricion en hoy, vacio, con el dia recien montado en otra fecha.
  const recordarDia = (dia) => {
    escribirLocal('nutrition_last_date', uid, dia);
    const n = new Date();
    escribirLocal('nutrition_last_date_guardado', uid,
      `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`);
  };

  // Movil: algunos textos van abreviados para que quepan en una linea.
  const [esMovil, setEsMovil] = useState(() => window.matchMedia('(max-width: 640px)').matches);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 640px)');
    const on = (e) => setEsMovil(e.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);

  // Snapshot persistido leído una sola vez al montar, el de ESTA persona.
  const persistedRef = useRef(undefined);
  if (persistedRef.current === undefined) {
    // La clave vieja sin dueño se barre de una vez: si no, la conversación que ya está
    // guardada en las pestañas abiertas seguiría apareciéndole al cliente hasta que alguien
    // cerrara el navegador. Es la misma red que HUERFANAS en lib/almacenLocal.
    try { sessionStorage.removeItem(CLAVE_HUERFANA); } catch { /* nada que hacer */ }
    persistedRef.current = loadPersisted(uid);
  }
  const p = persistedRef.current;

  const [sessionId, setSessionId] = useState(p.sessionId ?? null);
  const [messages, setMessages] = useState(p.messages ?? []);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  // Qué está haciendo el asistente ahora mismo ("Montando el menú..."), del SSE.
  const [progressText, setProgressText] = useState(null);
  const [step, setStep] = useState(p.step ?? 'init'); // init, config, building_meal, complete
  // Ya no hay fases de configuración (el día sale de Nutrición). Se conserva el estado
  // porque el snapshot de sesiones anteriores lo trae y para no romper la persistencia.
  const [configStage, setConfigStage] = useState(p.configStage ?? 'date');
  const [targetDate, setTargetDate] = useState(p.targetDate ?? null); // YYYY-MM-DD destino del volcado
  const [tipoDia, setTipoDia] = useState(p.tipoDia ?? null);
  const [numComidas, setNumComidas] = useState(p.numComidas ?? 4);
  const [opcionPeri, setOpcionPeri] = useState(p.opcionPeri ?? 'intra_post');
  const [momentoEntreno, setMomentoEntreno] = useState(p.momentoEntreno ?? 1);
  const [singleMeal, setSingleMeal] = useState(p.singleMeal ?? false);
  const [mealNombre, setMealNombre] = useState(p.mealNombre ?? 'Comida 1');
  const [dayOverview, setDayOverview] = useState(null);
  const [currentFoods, setCurrentFoods] = useState([]);
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
    const k = claveChat(uid);
    if (k) { try { sessionStorage.setItem(k, JSON.stringify(snapshot)); } catch (e) {} }
  }, [uid, sessionId, messages, step, configStage, targetDate, tipoDia, numComidas,
      opcionPeri, momentoEntreno, singleMeal, mealNombre, currentMeal, macrosRestantes, distribucion, daySummary]);

  // Al montar: si retomamos una sesión, verificar que sigue viva en el backend.
  // Si se perdió (p. ej. reinicio del backend), reiniciar limpio.
  useEffect(() => {
    const sid = p.sessionId;
    if (!sid || !p.step || p.step === 'init') return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetchConTope(`${API_URL}/api/chatbot/session-exists?session_id=${sid}`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        const d = await r.json();
        // EL ASISTENTE SIGUE AL DÍA DE NUTRICIÓN, TAMBIÉN AL VOLVER (vídeo 1 del 15-08).
        //
        // La conversación retomada traía su día de cuando se abrió: Jesús se iba al
        // domingo en Nutrición, volvía al asistente y este seguía en «Hoy» con la
        // comida 4 de hoy. No había ninguna forma visible de moverlo — acabó borrando
        // la conversación, que es justo lo que esta pantalla existe para evitar.
        //
        // Su regla es literal: «esto tiene que coincidir con el día, siempre». Así que
        // al retomar, si el día del chat no es el que está mirando en Nutrición, la
        // MISMA conversación se muda a ese día (reconfigura + precarga lo que tenga
        // guardado allí), con su mensaje de «Vamos con el domingo...» para que se vea.
        if (!cancelled && d.exists) {
          const dia = diaEnNutricion();
          if (dia && p.targetDate && dia !== p.targetDate) {
            setTargetDate(dia);
            arrancarConLaConfigDeNutricion(dia, {}, sid);
          }
          return;
        }
        if (!cancelled && !d.exists) {
          try { sessionStorage.removeItem(claveChat(uid) || CLAVE_HUERFANA); } catch (e) {}
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

  // Y AL VOLVER A LA PESTAÑA, LO MISMO. El caso de la ventana que se queda abierta (el
  // móvil de Jesús en el vídeo 7): cambias el día en otro sitio, vuelves a esta pestaña
  // horas después y la conversación sigue en el día viejo. Al recuperar el foco se hace
  // la misma comprobación que al montar. No se toca nada si está trabajando (loading) o
  // guardando: mudarse de día a mitad de una respuesta sería pisarla.
  useEffect(() => {
    const alVolver = () => {
      if (document.hidden || loading || saving) return;
      if (!sessionId || step === 'init') return;
      const dia = diaEnNutricion();
      if (dia && targetDate && dia !== targetDate) {
        setTargetDate(dia);
        arrancarConLaConfigDeNutricion(dia, {}, sessionId);
      }
    };
    window.addEventListener('focus', alVolver);
    document.addEventListener('visibilitychange', alVolver);
    return () => {
      window.removeEventListener('focus', alVolver);
      document.removeEventListener('visibilitychange', alVolver);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetDate, sessionId, loading, saving, step]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Mantener el foco en el input al terminar cada acción: cuando `loading` vuelve a false,
  // el input ya está re-habilitado, así que el foco funciona (llamarlo justo tras setLoading
  // no servía porque el input seguía disabled en ese instante).
  useEffect(() => {
    if (!loading) inputRef.current?.focus();
  }, [loading]);

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

  // Convierte texto/botón en YYYY-MM-DD; null si no se entiende. Lo usa el selector de
  // día de Nutrición al entrar; los cambios de día POR CHAT los decide el agente.
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
      const res = await fetchConTope(`${API_URL}/api/chatbot/start`, {
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
        // Ni una pregunta de configuración: el día que se está mirando en Nutrición y lo
        // que hay puesto ahí. Lo que el cliente quiera cambiar (otro día, descanso, otro
        // número de comidas) lo dice cuando quiera y se recoloca.
        const dia = diaEnNutricion() || todayLocal();
        setTargetDate(dia);
        arrancarConLaConfigDeNutricion(dia, {}, data.session_id);
      }
    } catch (error) {
      addMessage('Error al iniciar el chatbot. Por favor, recarga la página.', false);
    }
    setLoading(false);
  };

  /**
   * Arranca el día con la configuración que el cliente ya tiene puesta, en vez de
   * preguntarle cuatro cosas que ya ha contestado en Nutrición.
   *
   * Orden: la dieta guardada de ESE día manda (es lo que ve en la pestaña); si no hay
   * ninguna, sus preferencias guardadas (num de comidas, horario de entreno y peri), y
   * entonces lo único que no se puede adivinar es si hoy entrena: eso sí se pregunta.
   */
  const arrancarConLaConfigDeNutricion = async (iso, encima = {}, sid = null) => {
    setLoading(true);
    const cabecera = { Authorization: `Bearer ${getToken()}` };
    let dieta = null;
    let prefs = null;
    try {
      const r = await fetchConTope(`${API_URL}/api/diets/${iso}`, { headers: cabecera });
      if (r.ok) dieta = await r.json();
    } catch { /* sin dieta: se sigue con las preferencias */ }
    try {
      const r = await fetchConTope(`${API_URL}/api/user/diet-config`, { headers: cabecera });
      if (r.ok) prefs = await r.json();
    } catch { /* sin preferencias: se usan los valores por defecto */ }
    setLoading(false);

    const n = (dieta?.exists ? dieta.num_comidas : prefs?.num_comidas) ?? 4;
    // Mismos valores por defecto que la pantalla de Nutrición cuando ese día aún no tiene
    // dieta guardada (NutritionPage.loadDiet): día de entrenamiento y las preferencias del
    // cliente. Así el chat y la pestaña dicen siempre lo mismo, y no hay que preguntar.
    const cfg = {
      tipo_dia: (dieta?.exists ? dieta.tipo_dia : null) || 'entrenamiento',
      num_comidas: n,
      single_meal: n === 1,
      momento_entreno: (dieta?.exists ? dieta.momento_entreno : prefs?.momento_entreno) ?? 1,
      opcion_peri: (dieta?.exists ? dieta.opcion_peri : prefs?.opcion_peri) || 'intra_post',
      // Lo que venga dicho en el mismo mensaje manda sobre lo guardado: en "mañana
      // descanso" hay un día Y un tipo de día, y perder la mitad seria raro.
      ...encima,
    };
    if (cfg.tipo_dia === 'descanso') cfg.opcion_peri = 'sin_peri';
    setNumComidas(cfg.num_comidas);
    setSingleMeal(cfg.single_meal);
    setMomentoEntreno(cfg.momento_entreno);
    setOpcionPeri(cfg.opcion_peri);
    setTipoDia(cfg.tipo_dia);

    addMessage(`Vamos con ${formatDateLabel(iso)}, con lo que tienes en Nutrición: `
      + `${resumenConfig(cfg)}. Si quieres otro día o cambiar algo, dímelo cuando quieras: `
      + '"mañana", "hoy descanso", "3 comidas", "en ayunas" o "sin peri".', false);
    configureDay(cfg.tipo_dia, cfg.num_comidas, cfg.opcion_peri, cfg.momento_entreno,
                 cfg.single_meal, sid, iso);
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
  const configureDay = async (tipo, comidas, opPeri, momento = 1, single = false, sid = null,
                             fecha = null) => {
    setLoading(true);
    try {
      // `sid` explicito para el arranque: ahi el sessionId recien creado todavia no
      // esta en el estado de React y la peticion se iba con session_id=null.
      const res = await fetchConTope(`${API_URL}/api/chatbot/configure?session_id=${sid || sessionId}`, {
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
          single_meal: single,
          // Qué fecha se monta: el asistente resuelve "mañana" contra el día abierto.
          fecha: fecha || targetDate || null
        })
      });
      const data = await res.json();

      if (data.distribucion) {
        setDistribucion(data.distribucion);
        setCurrentMeal(data.comida_actual);
        setMealNombre(data.meal_nombre || 'Comida 1');
        setMacrosRestantes(data.objetivo || data.distribucion.comidas.C1);
        if (data.day_overview) setDayOverview(data.day_overview);
        // Lo que ya hubiera montado en esa comida, no una lista vacía: al cambiar de
        // configuración, lo que estaba en una comida que desaparece (el intra al pasar a
        // descanso) se traspasa a la más cercana, y el cliente tiene que verlo.
        setCurrentFoods(data.alimentos || []);
        setStep('building_meal');
        addMessage(data.mensaje, false);
      }
    } catch (error) {
      addMessage('Error al configurar el día.', false);
    }
    setLoading(false);
  };

  // El día (tipo, nº de comidas, peri...) puede cambiarlo el agente por chat: se
  // refleja aquí lo que diga el backend, que es quien manda.
  const syncEstado = (data) => {
    if (data?.day_overview) setDayOverview(data.day_overview);
    if (data?.state?.step) setStep(data.state.step);

    // Montar OTRO día lo decide el agente, no el front.
    //
    // Antes lo miraba aquí un regex (leerCambioDeDia): si el mensaje EMPEZABA por "hoy"
    // o "mañana", cambiaba de día y no llegaba a mandarse nada al backend. Con "hoy es
    // día de descanso" -- dos peticiones en una frase -- se quedaba con la que no era:
    // saltaba al día de hoy y tiraba lo de descanso. Ahora el agente entiende que hay
    // dos cosas, llama a cambiar_de_dia y a configurar_dia, y aquí solo se obedece. La
    // config que venga en la misma respuesta se aplica ENCIMA de la del día nuevo, que
    // si no la pisaría al recargarla de Nutrición.
    const cfg = data?.state?.config;
    const otroDia = data?.state?.fecha_pedida;
    if (otroDia && otroDia !== targetDate) {
      // La config solo viaja al día nuevo si la ha tocado ESTE turno («mañana
      // descanso»). Sin la bandera, aquí llegaba la config del día viejo -- el
      // descanso dicho para el lunes -- y se la plantaba al martes, que en
      // Nutrición era de entreno: el contagio de la ronda 1 del 15-08.
      const encima = {};
      if (data?.state?.config_tocada) {
        if (cfg?.tipo_dia) encima.tipo_dia = cfg.tipo_dia;
        if (cfg?.num_comidas) encima.num_comidas = cfg.num_comidas;
        if (cfg?.opcion_peri) encima.opcion_peri = cfg.opcion_peri;
        if (cfg?.momento_entreno !== null && cfg?.momento_entreno !== undefined) {
          encima.momento_entreno = cfg.momento_entreno;
        }
      }
      setTargetDate(otroDia);
      // El acuerdo va en los dos sentidos: si por chat se pide «mañana», Nutrición
      // también se muda. Sin esto, el día guardado con dueño seguía en el viejo y la
      // comprobación de foco devolvía el chat al día del que acababa de salir.
      recordarDia(otroDia);
      arrancarConLaConfigDeNutricion(otroDia, encima);
      return;
    }

    if (cfg) {
      if (cfg.tipo_dia) setTipoDia(cfg.tipo_dia);
      if (cfg.num_comidas) setNumComidas(cfg.num_comidas);
      if (cfg.opcion_peri) setOpcionPeri(cfg.opcion_peri);
      if (cfg.momento_entreno !== null && cfg.momento_entreno !== undefined) {
        setMomentoEntreno(cfg.momento_entreno);
      }
      setSingleMeal(!!cfg.single_meal);
    }
    // Si el cliente ha guardado una comida HABLANDO ("guarda la comida"), hay que
    // volcarla al plan igual que hace el botón «Guardar y siguiente».
    //
    // Había dos caminos para guardar y solo uno volcaba: el botón llama a
    // completeMeal(), que termina en syncToDiet(); por chat se ejecutaba la
    // herramienta del agente, la sesión avanzaba a la comida siguiente y nadie
    // sincronizaba. El cliente leía «Listo, he guardado el desayuno» y su plan seguía
    // vacío. Comprobado en vivo el 08-08 con una fecha limpia: 0 alimentos antes y 0
    // después de guardar.
    if (data?.comida_guardada || data?.response?.comida_guardada) {
      syncToDiet();
    }
  };

  // Enviar mensaje. Va por SSE (/message-stream) para poder enseñar qué está haciendo
  // el asistente mientras trabaja ("Montando el menú..."); si el stream falla, se cae
  // al POST clásico de /message.
  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    addMessage(userMessage, true);

    setLoading(true);
    setProgressText(null);

    const body = JSON.stringify({ message: userMessage, session_id: sessionId });
    const headers = { 'Authorization': `Bearer ${getToken()}`, 'Content-Type': 'application/json' };
    // Ni el stream ni el POST tienen final garantizado: si el backend se cae o se
    // reinicia a mitad, reader.read() se queda esperando para siempre, setLoading(false)
    // no llega nunca y el chat se queda en «Actualizando la comida...» con el input
    // bloqueado. Le pasó a Francisco el 08-08: tres minutos colgado sin salida salvo
    // recargar la página y perder el hilo.
    //
    // El tope NO es a la respuesta entera -- una petición que encadena varias
    // herramientas puede tardar de sobra y es legítima -- sino al SILENCIO: cada trozo
    // que llega (progreso o respuesta) rearma la cuenta. Solo salta si deja de llegar nada.
    const SILENCIO_MAX = 45000;
    const RESPALDO_MAX = 120000;
    let cortado = false;
    try {
      let respondido = false;
      try {
        const ctrl = new AbortController();
        let campana = setTimeout(() => { cortado = true; ctrl.abort(); }, SILENCIO_MAX);
        const rearmar = () => {
          clearTimeout(campana);
          campana = setTimeout(() => { cortado = true; ctrl.abort(); }, SILENCIO_MAX);
        };
        try {
          const res = await fetch(`${API_URL}/api/chatbot/message-stream`, {
            method: 'POST', headers, body, signal: ctrl.signal,
          });
          if (!res.ok || !res.body) throw new Error('sin stream');
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';
          for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            rearmar();
            buffer += decoder.decode(value, { stream: true });
            const trozos = buffer.split('\n\n');
            buffer = trozos.pop();
            for (const trozo of trozos) {
              const linea = trozo.split('\n').find(l => l.startsWith('data: '));
              if (!linea) continue;
              const ev = JSON.parse(linea.slice(6));
              if (ev.tipo === 'progreso') {
                setProgressText(ev.texto);
              } else if (ev.tipo === 'respuesta') {
                syncEstado(ev);
                await handleBotResponse(ev.response);
                respondido = true;
              } else if (ev.tipo === 'error') {
                addMessage('Error al procesar el mensaje.', false);
                respondido = true;
              }
            }
          }
        } finally {
          clearTimeout(campana);
        }
        if (!respondido) throw new Error('stream sin respuesta');
      } catch (e) {
        // Respaldo: el POST clásico (mismo backend, sin indicador de progreso). Con su
        // propio tope, que aquí no hay trozos que rearmen nada.
        const ctrl = new AbortController();
        const campana = setTimeout(() => { cortado = true; ctrl.abort(); }, RESPALDO_MAX);
        try {
          const res = await fetchConTope(`${API_URL}/api/chatbot/message`, {
            method: 'POST', headers, body, signal: ctrl.signal,
          });
          const data = await res.json();
          syncEstado(data);
          await handleBotResponse(data.response);
        } finally {
          clearTimeout(campana);
        }
      }
    } catch (error) {
      // Decir qué ha pasado y, sobre todo, que se puede seguir: el chat queda usable y
      // lo montado hasta aquí sigue en su sitio.
      addMessage(cortado
        ? 'Se me ha cortado la conexión y he dejado la petición a medias. Lo que llevabas '
          + 'montado sigue guardado: repite lo último que me pediste.'
        : 'Error al procesar el mensaje. Vuelve a intentarlo.', false);
    } finally {
      setProgressText(null);
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  // "Elegir este menú" en una tarjeta de menús del agente: aplica el borrador a la
  // comida pasando por la revisión del backend (si algo choca, el chat cuenta el porqué).
  const aplicarMenu = async (borrador) => {
    if (loading || !borrador?.id) return;
    addMessage(`Elijo: ${borrador.nombre || 'ese menú'}`, true);
    setLoading(true);
    try {
      const res = await fetch(
        `${API_URL}/api/chatbot/apply-draft?session_id=${sessionId}&borrador_id=${encodeURIComponent(borrador.id)}`,
        { method: 'POST', headers: { 'Authorization': `Bearer ${getToken()}` } });
      const data = await res.json();
      syncEstado(data);
      await handleBotResponse(data.response);
    } catch (e) {
      addMessage('Error al aplicar el menú.', false);
    }
    setLoading(false);
  };

  // Elegir una sugerencia pulsándola. Se manda al backend lo mismo que si el usuario
  // escribiera "la 3", que es lo que ya entiende (resuelve contra state.last_options).
  const elegirSugerencia = async (numero, sug) => {
    if (loading) return;
    addMessage((sug?.nombre || `la ${numero}`).trim(), true);
    setLoading(true);
    try {
      const res = await fetchConTope(`${API_URL}/api/chatbot/message`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `la ${numero}`, session_id: sessionId }),
      });
      const data = await res.json();
      if (data.day_overview) setDayOverview(data.day_overview);
      if (data.state?.step) setStep(data.state.step);
      await handleBotResponse(data.response);
    } catch (e) {
      addMessage('Error al añadir esa opción.', false);
    }
    setLoading(false);
  };

  // Aplica meal_status (etiqueta + restante) y resumen del día a la UI
  const applyMealResponse = (resp) => {
    if (resp?.meal_status) {
      if (resp.meal_status.comida_nombre) setMealNombre(resp.meal_status.comida_nombre);
      if (resp.meal_status.restante) setMacrosRestantes(resp.meal_status.restante);
      setCurrentFoods(resp.meal_status.alimentos || []);
    }
    if (resp?.day_overview) setDayOverview(resp.day_overview);
  };

  // Despacha la respuesta determinista del backend
  const handleBotResponse = async (resp) => {
    if (!resp) return;
    if (resp.day_overview) setDayOverview(resp.day_overview);
    // SI LA RESPUESTA TRAE EL ESTADO DE LA COMIDA, SE APLICA VENGA CON EL `action` QUE VENGA
    // (punto 10.5). Antes solo lo miraba la rama `meal_updated`, y un turno del asistente
    // puede buscar Y añadir a la vez: entonces llegaba `action: "suggestions"` y la cabecera
    // se quedaba diciendo «faltan 30P 20H 10G» con la comida ya montada. El asistente decía
    // la verdad y la pantalla la desmentía.
    if (resp.meal_status) applyMealResponse(resp);
    switch (resp.action) {
      case 'meal_updated':
        applyMealResponse(resp);
        // Si hay términos ambiguos (p.ej. "lomo"), el backend ya numera las opciones
        // en resp.message y el usuario elige por texto ("la 1", "el de salmón").
        addMessage(formatMealUpdate(resp), false, resp);
        break;
      case 'suggestions':
        // Las opciones las pinta <ChatSuggestions> (tarjetas que se pulsan) a partir de
        // resp.suggestions; el texto se queda con la frase de contexto, que a propósito
        // viene vacía cuando la tarjeta ya lo dice. El "no encuentro nada" SOLO cuando de
        // verdad no hay nada: se estaba imprimiendo encima de seis sugerencias.
        addMessage(resp.message || (resp.suggestions?.length ? '' : 'No encuentro alimentos que cuadren ahora mismo.'), false, resp);
        break;
      case 'menus':
        // Menús completos del agente: tarjetas <ChatMenus> con el botón de aplicar.
        addMessage(resp.message || '', false, resp);
        break;
      case 'complete_request':
        await completeMeal();
        break;
      case 'summary':
        addMessage(formatDayOverview(resp.day_overview), false);
        break;
      case 'status':
        // El mensaje va DELANTE del listado: a "¿qué comida sigue?" hay que contestarle
        // en una línea, y el desglose de lo que falta es el detalle, no la respuesta.
        addMessage([resp.message, formatMealsStatus(resp.meals_status)].filter(Boolean).join('\n\n'), false);
        break;
      case 'no_foods':
      default:
        // `vista: dia` (el listado de comidas) lo pinta <ChatDayOverview>; su `message` es
        // el texto de respaldo y no se enseña para no repetirlo.
        addMessage(
          resp.vista === 'dia'
            ? ''
            : (resp.message || 'No te entendí. Dime qué alimentos quieres o usa los botones.'),
          false, resp);
    }
  };

  // Informe de "qué falta y en qué comida"
  const formatMealsStatus = (meals) => {
    if (!meals?.length) return 'Aún no has configurado el día.';
    let msg = '**¿Qué te falta por cubrir?**\n';
    let todoOk = true;
    meals.forEach(m => {
      const r = m.restante || {};
      const faltan = ['P', 'H', 'G'].filter(k => (r[k] || 0) > 4).map(k => `${k}=${r[k]}g`);
      if (faltan.length) {
        todoOk = false;
        msg += `• ${m.nombre}: falta ${faltan.join(', ')}\n`;
      } else if (m.tiene_alimentos) {
        msg += `• ${m.nombre}: ✅ cuadrada\n`;
      } else {
        todoOk = false;
        msg += `• ${m.nombre}: vacía\n`;
      }
    });
    if (todoOk) msg += '\n¡Todo cuadrado! Puedes volcar la dieta.';
    return msg;
  };

  // Quitar un alimento de la comida actual.
  // Ahora mismo no la llama nadie: la lista de chips "En esta comida" con su × se quitó
  // porque repetía la tarjeta del asistente. Se deja preparada por si se vuelve a poner un
  // botón de quitar; mientras tanto, el usuario lo pide por chat ("quita el bacon").
  // eslint-disable-next-line no-unused-vars
  const removeFood = async (index) => {
    if (loading) return;
    const quitado = currentFoods[index];
    setLoading(true);
    try {
      const res = await fetchConTope(`${API_URL}/api/chatbot/remove-food?session_id=${sessionId}&index=${index}`, {
        method: 'POST', headers: { 'Authorization': `Bearer ${getToken()}` }
      });
      const data = await res.json();
      applyMealResponse(data.response);
      // El chat también refleja el borrado hecho desde el panel: sin esto, el
      // último mensaje del bot seguía contando el alimento recién quitado.
      addMessage(formatMealUpdate({
        ...data.response,
        message: quitado
          ? `He quitado ${quitado.nombre} (${quitado.cantidad_display}) de la comida.`
          : 'Alimento quitado.',
      }), false, data.response);
    } catch (e) { addMessage('Error al quitar el alimento.', false); }
    setLoading(false);
  };

  // Pedir sugerencias de alimentos sueltos para la comida actual
  const requestSuggestions = async () => {
    if (loading) return;
    setLoading(true);
    try {
      const res = await fetchConTope(`${API_URL}/api/chatbot/suggest-foods?session_id=${sessionId}`, {
        method: 'POST', headers: { 'Authorization': `Bearer ${getToken()}` }
      });
      const data = await res.json();
      await handleBotResponse(data.response);
    } catch (e) { addMessage('Error al sugerir alimentos.', false); }
    setLoading(false);
  };

  const formatDayOverview = (ov) => {
    if (!ov) return 'Aún no hay datos del día.';
    // Lo que falta y lo que sobra, por separado: "Te falta: Hidratos -1.7 g" no quiere
    // decir nada (QA 15-08, A4-F03). Un negativo dentro de "te falta" se lee al reves.
    const nombres = { P: 'proteína', H: 'hidratos', G: 'grasa' };
    const r = ov.restante || {};
    const faltan = ['P', 'H', 'G'].filter(k => Math.round(r[k] || 0) > 0)
      .map(k => `${Math.round(r[k])} g de ${nombres[k]}`);
    const sobran = ['P', 'H', 'G'].filter(k => Math.round(r[k] || 0) < 0)
      .map(k => `${Math.round(-r[k])} g de ${nombres[k]}`);
    let linea = 'El día ya te cuadra';
    if (faltan.length || sobran.length) {
      const partes = [];
      const enumerar = (xs) => (xs.length > 1 ? `${xs.slice(0, -1).join(', ')} y ${xs[xs.length - 1]}` : xs[0] || '');
      if (faltan.length) partes.push(`te falta ${enumerar(faltan)}`);
      if (sobran.length) partes.push(`te pasas ${enumerar(sobran)}`);
      linea = partes.join(' y ').replace(/^./, c => c.toUpperCase());
    }
    return `**Resumen del día**\nObjetivo: ${macrosLinea(ov.objetivo)}\nLlevas: ${macrosLinea(ov.consumido)}\n${linea}\nComidas guardadas: ${ov.completas}/${ov.total_comidas}`;
  };

  // Completar comida actual
  const completeMeal = async () => {
    setLoading(true);
    try {
      const res = await fetchConTope(`${API_URL}/api/chatbot/complete-meal?session_id=${sessionId}`, {
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
        if (data.day_overview) setDayOverview(data.day_overview);
        setCurrentFoods([]);
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
    if (!sessionId) return;
    // Sin día destino se volcaba en silencio a ninguna parte. Si por lo que sea no está
    // fijado, se usa el día que se esté mirando en Nutrición, o hoy: guardar en el día
    // equivocado sería peor, pero no guardar nada y decir que sí es lo que estaba
    // pasando.
    const dia = targetDate || diaEnNutricion() || todayLocal();
    try {
      if (!autoSyncRef.current.decided) {
        const ex = await fetchConTope(`${API_URL}/api/diets/${dia}`, {
          headers: { 'Authorization': `Bearer ${getToken()}` }
        }).then(r => r.json());
        const hasFood = ex.exists && Object.values(ex.comidas || {}).some(m => (m?.alimentos || []).length > 0);
        autoSyncRef.current.decided = true;
        if (hasFood) {
          const ok = await confirm({
            title: `Ya tienes una dieta el ${formatDateLabel(dia)}`,
            description: '¿Quieres que la vaya actualizando con lo que montemos aquí?',
            confirmLabel: 'Sí, actualizarla', cancelLabel: 'No, dejarla',
          });
          autoSyncRef.current.enabled = ok;
          if (!ok) {
            addMessage('Vale, no tocaré tu dieta guardada. Podrás volcarla manualmente al terminar.', false);
            return;
          }
        }
      }

      if (!autoSyncRef.current.enabled) return;

      const res = await fetch(
        `${API_URL}/api/chatbot/save-to-diet?session_id=${sessionId}&fecha=${dia}&overwrite=true`,
        { method: 'POST', headers: { 'Authorization': `Bearer ${getToken()}` } }
      );
      const data = await res.json();
      // Volcado saltado a proposito: la sesion ya esta en otra fecha (ventana del cambio
      // de dia). Ni "guardado" ni aviso: el dia nuevo arranca con su propia carga.
      if (res.ok && data.skipped) return;
      if (res.ok && !data.needs_confirmation) {
        recordarDia(dia);
        addMessage(`✅ Guardado en tu pestaña de nutrición (${formatDateLabel(dia)}).`, false);
      } else {
        // Antes esto se callaba: el cliente leía «comida guardada» y no lo estaba.
        addMessage('⚠️ No he podido guardarlo en tu pestaña de nutrición. Lo tienes montado aquí; vuelve a intentarlo o vuélcalo con el botón.', false);
      }
    } catch (e) {
      // Fallar en silencio era el problema: el cliente creía que su comida estaba
      // guardada y no estaba en ninguna parte.
      addMessage('⚠️ No he podido guardarlo en tu pestaña de nutrición. Lo tienes montado aquí; vuelve a intentarlo o vuélcalo con el botón.', false);
    }
  };

  // Formatear actualización de comida (siempre con los macros por su nombre:
  // Proteína/Hidratos/Grasa, nunca las iniciales P/H/G)
  const MACRO_NOMBRE = { P: 'proteína', H: 'hidratos', G: 'grasa' };
  const macrosLinea = (m) =>
    `Proteína ${m?.P || 0} g · Hidratos ${m?.H || 0} g · Grasa ${m?.G || 0} g`;

  // El texto de la burbuja se queda SOLO con la frase de conversación. Los alimentos, los
  // macros de la comida y los avisos los pinta <ChatMealSummary> a partir de los mismos
  // datos, que ya venían estructurados: antes se aplanaba todo a un texto larguísimo y no
  // se distinguía lo importante. Si la respuesta no trae nada que pintar, se deja una
  // frase para no dejar la burbuja vacía.
  const formatMealUpdate = (response) => {
    if (response.message) return response.message.trim();
    const hayTarjeta = response.meal_status
      || response.foods_added?.length > 0
      || response.foods_not_found?.length > 0;
    return hayTarjeta ? '' : 'No he podido procesar eso. Escríbelo otra vez, por favor.';
  };

  // Reiniciar chat
  const resetChat = async () => {
    if (sessionId) {
      try {
        await fetchConTope(`${API_URL}/api/chatbot/reset?session_id=${sessionId}`, {
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
    setDayOverview(null);
    setCurrentFoods([]);
    setCurrentMeal(1);
    setDistribucion(null);
    setDaySummary(null);
    autoSyncRef.current = { decided: false, enabled: true };
    try { sessionStorage.removeItem(claveChat(uid) || CLAVE_HUERFANA); } catch (e) {}
  };

  // Renderizar mensaje
  const renderMessage = (msg, idx) => {
    const isUser = msg.isUser;
    const conTarjetas = !isUser && (
      msg.data?.action === 'suggestions' || msg.data?.action === 'menus' || msg.data?.vista === 'dia'
    );

    return (
      <div key={idx} className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
        {/* EL ANCHO DE LAS BURBUJAS EN EL TELÉFONO. Medido en un iPhone 13: al mensaje del
            asistente le quedaban 220 px de texto de los 390 de la pantalla -- el 44% se iba
            en el muñeco, los huecos y el margen del 15% --, así que se leía en columnas de
            tres palabras y un solo mensaje suyo ocupaba 288 px de los 505 que tiene la
            conversación. Con la letra de la app a 18 px en móvil, a propósito, eso es
            justamente lo que no puede pasar.
            Aquí el margen baja al 4% y el muñeco no sale: quién habla ya se sabe por el lado
            y por el color, como en cualquier chat. De 640 px para arriba, todo como estaba. */}
        <div className={`flex items-start gap-2 max-w-[96%] sm:max-w-[85%] ${isUser ? 'flex-row-reverse' : ''}`}>
          <div className={`w-8 h-8 rounded-full hidden sm:flex items-center justify-center flex-shrink-0 ${
            isUser ? 'bg-orange-500' : 'bg-muted'
          }`}>
            {isUser ? <User size={16} /> : <Bot size={16} />}
          </div>
          {/* Cuando el mensaje trae tarjetas -- opciones, menús o el resumen del día -- la
              burbuja ocupa todo el ancho que tiene permitido en vez de encogerse a la frase
              que las acompaña, que suele ser una línea. Si no, las opciones se pintan en una
              columna de 275 px con el nombre partido en tres renglones. Solo en el teléfono. */}
          <div className={`rounded-2xl px-4 py-2 ${conTarjetas ? 'w-full sm:w-auto' : ''} ${
            isUser
              ? 'bg-orange-500 text-white rounded-br-md'
              : 'bg-card text-foreground rounded-bl-md'
          }`}>
            {msg.content && (
              <div className="whitespace-pre-wrap text-sm">
                {msg.content.split('**').map((part, i) =>
                  i % 2 === 1 ? <strong key={i}>{part}</strong> : part
                )}
              </div>
            )}
            {/* Alimentos de la comida + barras de macros, en vez del muro de texto */}
            {!isUser && <ChatMealSummary data={msg.data} />}
            {/* Resumen del día y sugerencias, también como tarjetas */}
            {!isUser && msg.data?.vista === 'dia' && <ChatDayOverview data={msg.data} />}
            {!isUser && msg.data?.action === 'suggestions' && (
              <ChatSuggestions data={msg.data} disabled={loading} onElegir={elegirSugerencia} />
            )}
            {!isUser && msg.data?.action === 'menus' && (
              <ChatMenus data={msg.data} disabled={loading} onAplicar={aplicarMenu} />
            )}
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
      const res = await fetchConTope(`${API_URL}/api/chatbot/export-pdf?session_id=${sessionId}`, {
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
        const exRes = await fetchConTope(`${API_URL}/api/diets/${targetDate}`, {
          headers: { 'Authorization': `Bearer ${getToken()}` }
        });
        const ex = await exRes.json();
        const hasFood = ex.exists && Object.values(ex.comidas || {}).some(m => (m?.alimentos || []).length > 0);
        if (hasFood) {
          const ok = await confirm({
            title: `Ya tienes una dieta el ${formatDateLabel(targetDate)}`,
            description: 'Si sigues, se sustituye por esta.',
            confirmLabel: 'Sobrescribir', danger: true,
          });
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
        const ok = await confirm({
          title: '¿Sobrescribir la dieta existente?',
          description: data.message || 'Ese día ya tiene alimentos guardados.',
          confirmLabel: 'Sobrescribir', danger: true,
        });
        if (ok) { setSaving(false); return saveToDiet(true); }
        setSaving(false);
        return;
      }

      if (!res.ok) throw new Error(data.detail || 'Error al volcar');

      // 3. Handoff a la pestaña de nutrición en ese día
      addMessage(`✅ Dieta volcada en tu pestaña de nutrición (${formatDateLabel(targetDate)}). Abriéndola…`, false);
      recordarDia(targetDate);
      // Con el dia explicito en la URL: "Abriendola..." tiene que abrir ESE dia, no hoy.
      setTimeout(() => navigate(`/dashboard/nutrition?date=${targetDate}`), 600);
    } catch (error) {
      addMessage('Error al volcar la dieta. Inténtalo de nuevo.', false);
    }
    setSaving(false);
  };

  const renderDaySummary = () => {
    if (!daySummary) return null;
    const r1 = (n) => Math.round((Number(n) || 0) * 10) / 10;

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
              Total: Proteína {r1(comida.macros?.P)} g · Hidratos {r1(comida.macros?.H)} g · Grasa {r1(comida.macros?.G)} g
            </div>
          </div>
        ))}
        
        <div className="mt-4 pt-4 border-t border-input">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-orange-500">{r1(daySummary.totales?.P)}g</div>
              <div className="text-xs text-muted-foreground">Proteínas</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-blue-500">{r1(daySummary.totales?.H)}g</div>
              <div className="text-xs text-muted-foreground">Hidratos</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-yellow-500">{r1(daySummary.totales?.G)}g</div>
              <div className="text-xs text-muted-foreground">Grasas</div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Está montando una comida: es el estado en el que la cabecera deja de anunciarse y pasa a
  // decir en qué va. Se usa en varios sitios de la cabecera, así que se nombra una vez.
  const montando = step === 'building_meal';

  /**
   * LO QUE LE QUEDA A LA COMIDA, EN UNA LÍNEA Y SIN NÚMEROS NEGATIVOS.
   *
   * `macrosRestantes` viene con signo: si se pasa de hidratos, llega -8.4. Puesto en fila
   * salía «Te faltan 8 P · -8 H · 12 G», que no quiere decir nada -- y con 200 g de pollo y
   * 80 g de arroz es exactamente lo que se leía. Lo que falta y lo que sobra son dos cosas
   * distintas y se cuentan por separado, como ya hace la tarjeta de la comida.
   */
  const loQueQueda = (() => {
    const macros = [['P', macrosRestantes.P], ['H', macrosRestantes.H], ['G', macrosRestantes.G]];
    const faltan = macros.filter(([, v]) => Math.round(v) > 0).map(([k, v]) => `${Math.round(v)} ${k}`);
    const sobran = macros.filter(([, v]) => Math.round(v) < 0).map(([k, v]) => `${Math.round(-v)} ${k}`);
    if (!faltan.length && !sobran.length) return 'Esta comida ya cuadra';
    const partes = [];
    if (faltan.length) partes.push(`Te faltan ${faltan.join(' · ')}`);
    if (sobran.length) partes.push(`te pasas ${sobran.join(' · ')}`);
    return partes.join(' · ');
  })();

  // La misma línea para el ordenador, con las palabras enteras. La versión de escritorio
  // seguía pintando el número crudo con su signo -- «Falta: proteína -9.2 g» -- y es
  // justo lo que Jesús enseñó en los vídeos del 15-08 (los grabó desde el portátil). Un
  // negativo no es una cantidad: lo pasado se dice «te pasas».
  const loQueQuedaLargo = (() => {
    const nombres = { P: 'proteína', H: 'hidratos', G: 'grasa' };
    const macros = [['P', macrosRestantes.P], ['H', macrosRestantes.H], ['G', macrosRestantes.G]];
    const faltan = macros.filter(([, v]) => Math.round(v) > 0)
      .map(([k, v]) => `${Math.round(v)} g de ${nombres[k]}`);
    const sobran = macros.filter(([, v]) => Math.round(v) < 0)
      .map(([k, v]) => `${Math.round(-v)} g de ${nombres[k]}`);
    if (!faltan.length && !sobran.length) return 'esta comida ya cuadra';
    const partes = [];
    if (faltan.length) partes.push(`faltan ${faltan.join(' · ')}`);
    if (sobran.length) partes.push(`te pasas ${sobran.join(' · ')}`);
    return partes.join(' · ');
  })();

  return (
    // Altura fija de viewport (en móvil descontando top bar y nav inferior del layout):
    // el header y el input quedan fijos y solo la zona de mensajes hace scroll.
    <div className="h-[calc(100dvh-8.5rem)] lg:h-screen bg-background text-foreground flex flex-col">
      {/* Header */}
      {/* En movil la cabecera va al minimo: cada pixel de aqui es un pixel menos de
          conversacion, y con el teclado abierto quedan unos 300 px utiles. */}
      <header className="bg-card border-b border-border px-3 sm:px-4 py-2 sm:py-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          {/* EL ROBOT NO SALE EN EL TELÉFONO MIENTRAS SE MONTA LA COMIDA. Son 32 px de ancho
              para un dibujo que ya está en cada mensaje suyo, y ese ancho es justo lo que le
              falta a la línea de macros para no cortarse. */}
          <div className={`w-8 h-8 sm:w-10 sm:h-10 bg-orange-500 rounded-full items-center justify-center flex-shrink-0 ${montando ? 'hidden sm:flex' : 'flex'}`}>
            <Bot className="w-5 h-5 sm:w-6 sm:h-6" />
          </div>
          <div className="min-w-0">
            {/* MIENTRAS MONTA, MANDA LO QUE ESTÁ HACIENDO, NO EL NOMBRE DE LA PANTALLA.
                En el teléfono ponía «Asistente de Nutrición» en grande -- que ya lo sabe:
                acaba de entrar desde ahí -- y debajo, pequeño, lo único que de verdad
                necesita: en qué comida va y cuánto le falta. Se cambian de sitio.

                Y AQUÍ NO VA «MARCO». Se preguntó (punto 6 del repaso del 13-08-2026) y
                Jesús dijo que no: «El nombre en el saludo, una vez, y la cabecera para lo
                que cambia. Esa cabecera es donde va "Comida 1 · 0 de 4 hechas · te faltan
                59 P · 66 H · 12 G", que es lo que miras veinte veces; un nombre fijo ahí
                arriba ocupa el sitio de lo que sí se mueve». El asistente se presenta como
                Marco en el saludo (ver `core/guion_peri.py` y el prompt del agente). */}
            <h1 className={`font-bold truncate ${montando ? 'hidden sm:block' : ''}`} data-testid="chatbot-heading">Asistente de Nutrición</h1>
            {montando && (
              <p className="sm:hidden font-bold truncate" data-testid="chatbot-comida">
                {mealNombre}
                {dayOverview && <span className="font-normal text-muted-foreground"> · {dayOverview.completas} de {dayOverview.total_comidas} hechas</span>}
              </p>
            )}
            {/* En movil el detalle va abreviado y en una sola linea: la version larga
                ocupaba tres y dejaba la conversacion en un tercio de la pantalla. */}
            <p className="text-xs text-muted-foreground truncate">
              {step === 'building_meal' && (
                <>
                  {/* SIN DECIMALES. Ponía «faltan 58.8P · 66.0H · 12.0G»: nadie se sirve
                      0,8 g de proteína, y esos cuatro caracteres de más son los que hacían
                      que la línea se cortara. Los objetivos exactos siguen en el mensaje
                      del asistente, que es donde se miran con calma. */}
                  <span className="sm:hidden">{loQueQueda}</span>
                  <span className="hidden sm:inline">
                    {mealNombre} • {loQueQuedaLargo}
                    {dayOverview && ` · Día: ${dayOverview.completas} de ${dayOverview.total_comidas} comidas`}
                  </span>
                </>
              )}
              {step === 'complete' && '¡Día completo!'}
              {step === 'init' && 'Listo para empezar'}
              {step === 'config' && 'Configurando día...'}
            </p>
          </div>
        </div>
        <button
          onClick={resetChat}
          className="p-2 hover:bg-muted rounded-lg transition-colors flex-shrink-0"
          title="Reiniciar"
        >
          <RefreshCw size={20} />
        </button>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 sm:p-4">
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
              {/* El SSE va contando qué hace el asistente; sin evento aún, "Pensando..." */}
              <span className="text-sm text-muted-foreground">{progressText || 'Pensando...'}</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input + controles de montaje */}
      {(step === 'building_meal' || step === 'complete') && (
        <div className="border-t border-border p-2 sm:p-3 bg-card relative z-40 space-y-2">
          {/* Aquí iba la lista "En esta comida" con un chip por alimento. Se quitó porque
              repetía lo que ya enseña la tarjeta de la última respuesta del asistente, que
              lista la comida entera con sus macros. Para quitar un alimento se le dice al
              chat ("quita el bacon"), que ya lo entiende. */}

          {/* Botones de control. En movil se reparten el ancho en UNA fila: envueltos
              se iban a dos y con el teclado abierto se comian media conversacion.
              Con el día COMPLETO se quedan solo el resumen y el chat vivo: guardar y
              sugerir hablan de una comida en curso que ya no existe -- pero cortar el
              input dejaba el día cerrado a cal y canto («vacía la comida 1» tras
              completar caía en una caja muerta, ronda 1 del 15-08). */}
          <div className="grid grid-cols-3 sm:flex sm:flex-wrap gap-1.5 sm:gap-2">
            {montando && (
              <button
                onClick={completeMeal}
                disabled={loading}
                className="bg-green-600 hover:bg-green-700 text-white px-2 sm:px-3 py-2 rounded-xl font-semibold text-[13px] sm:text-sm flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
                data-testid="save-meal-btn"
              >
                <Check size={16} className="flex-shrink-0" />
                <span className="sm:hidden">Guardar</span>
                <span className="hidden sm:inline">Guardar y siguiente</span>
              </button>
            )}
            {montando && (
              <button
                onClick={requestSuggestions}
                disabled={loading}
                className="bg-muted hover:bg-accent border border-input text-foreground px-2 sm:px-3 py-2 rounded-xl font-semibold text-[13px] sm:text-sm transition-colors disabled:opacity-50"
                data-testid="suggest-foods-btn"
              >
                <span className="sm:hidden">Sugerir</span>
                <span className="hidden sm:inline">Sugerir alimentos</span>
              </button>
            )}
            <button
              onClick={async () => {
                // Fresco del backend: el estado de React iba un guardado por detras
                // y el resumen decia 5/6 con las seis comidas guardadas.
                let ov = dayOverview;
                try {
                  const r = await fetchConTope(`${API_URL}/api/chatbot/day-overview?session_id=${sessionId}`,
                    { headers: { 'Authorization': `Bearer ${getToken()}` } });
                  if (r.ok) {
                    const d = await r.json();
                    if (d.day_overview) { ov = d.day_overview; setDayOverview(d.day_overview); }
                  }
                } catch { /* sin red se ensena lo que hay */ }
                addMessage(formatDayOverview(ov), false);
              }}
              disabled={loading || !dayOverview}
              className="bg-muted hover:bg-accent border border-input text-foreground px-2 sm:px-3 py-2 rounded-xl font-semibold text-[13px] sm:text-sm transition-colors disabled:opacity-50"
            >
              <span className="sm:hidden">Resumen</span>
              <span className="hidden sm:inline">Resumen del día</span>
            </button>
          </div>

          {/* Escribir alimentos */}
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
              // Al abrirse el teclado, el navegador encoge la ventana y el input se
              // queda debajo. Un scroll al enfocar lo devuelve a la vista.
              onFocus={(e) => setTimeout(
                () => e.target.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 250)}
              // Mientras guarda o piensa, el input se deshabilita: si además dice lo de
              // siempre, parece colgado. Que diga lo que está pasando.
              // En movil el placeholder largo se corta a mitad de frase y no se entiende.
              placeholder={saving ? 'Guardando la comida y pasándola a Nutrición…'
                : loading ? 'Un momento, estoy con ello…'
                : step === 'complete'
                ? 'El día está completo. ¿Quieres cambiar algo? Dímelo aquí…'
                : esMovil
                ? 'Escribe qué quieres comer…'
                : 'Escribe qué quieres comer, o pídeme cosas como "edita la comida 2" o "vacía el post-entreno"…'}
              // 16px de fuente: por debajo, iOS hace zoom al enfocar y descuadra la pantalla.
              className="flex-1 min-w-0 bg-muted border border-input rounded-xl px-3 sm:px-4 py-3 text-base sm:text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-brand"
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
