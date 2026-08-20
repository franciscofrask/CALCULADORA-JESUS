"""
Modelos Pydantic para rutinas, reportes, mensajes y pagos.
"""
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Dict, List, Any

# Routine Models
class Exercise(BaseModel):
    name: str
    sets: int
    reps: str
    rest: str
    video_url: Optional[str] = None
    notes: Optional[str] = None

class RoutineDay(BaseModel):
    day: str
    is_rest: bool = False
    exercises: List[Exercise] = []
    cardio: Optional[Dict[str, Any]] = None

class RoutineCreate(BaseModel):
    client_id: str
    instructions: Optional[str] = None

class RoutineResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    days: List[RoutineDay]
    trainer_notes: Optional[str] = None
    created_at: str
    status: str = "active"

# ── El reporte, por bloques (T7 y T8 del doc 16-08) ──────────────────────────
#
# El quincenal y el mensual dejan de ser el mismo formulario. Lo que cambia no es solo
# que el mensual pida medidas: son dos cuestionarios distintos, y el mensual además no
# es el mismo para los tres planes. Por eso los campos nuevos van sueltos y todos
# opcionales, en vez de un bloque obligatorio: cada cliente contesta los suyos y el que
# no le toca llega vacío.
#
# Los valores son los del doc, en clave; los textos que ve el cliente viven en el front.


class LesionDelReporte(BaseModel):
    """Una lesión, como queda tras el reporte (bloque 06, solo quien lleva lesiones).

    `estado_mes` es lo que contesta ESTE mes (peor/igual/mejor/superada) y `ejercicios`
    los que no puede hacer. Se guarda igual en el reporte y en `client_profiles.lesiones`:
    en el reporte para saber qué contestó aquel mes, en el perfil para poder enseñárselo
    el mes que viene ("LO QUE YA ME CONTASTE").
    """
    zona: str
    desde: Optional[str] = None
    estado_mes: Optional[str] = Field(None, pattern="^(peor|igual|mejor|superada)$")
    ejercicios: List[str] = []


class SuplementacionDelReporte(BaseModel):
    """Bloque 08: si está tomando la pauta y, si no toda, cuál y por qué."""
    respuesta: Optional[str] = Field(None, pattern="^(todos|alguno_no|ninguno)$")
    detalle: Optional[str] = Field(None, max_length=2000)


class EntrenoDelReporte(BaseModel):
    """Bloque 05, que es el que cambia de un plan a otro.

    - Quien lleva entreno personalizado y quincenal solo ve el dato: no contesta nada.
    - Quien lleva la rutina del mes confirma los días que no rellenó, puntúa el mes y
      escribe lo que quiera.
    - Quien no lleva rutina contesta por su regularidad, y ahí es donde va la rutina del
      mes (la única oferta que queda en todo el reporte).
    """
    # {"2026-08-08": "si_no_lo_apunte" | "no_entrene"} · los días que la app no tiene
    confirmacion: Optional[Dict[str, str]] = None
    estrellas: Optional[int] = Field(None, ge=1, le=5)
    nota: Optional[str] = Field(None, max_length=4000)
    # Sin rutina cargada: "¿Entrenaste este mes de forma regular?"
    regularidad: Optional[str] = Field(
        None, pattern="^(a_mi_manera_sigo|a_mi_manera_quiero_rutina|con_tu_rutina_sigo)$")
    # La rutina del mes por 57 EUR: básica, avanzada o ahora no.
    # `aplazar_una_semana` (doc 19-08): la marca y se le vuelve a preguntar en 7 días.
    rutina_del_mes: Optional[str] = Field(None, pattern="^(basica|avanzada|ahora_no|aplazar_una_semana)$")
    # "¿O prefieres tenerla todos los meses?" -> el equipo le cuenta el plan de arriba.
    quiere_saber_del_silver: Optional[bool] = None


# Report Models
class ReportCreate(BaseModel):
    # El mismo rango que acepta la serie de peso, `core/series_cliente` (punto 5.4). El peso
    # del reporte es de donde salen la grafica, el ajuste del mes y lo que lee el agente: un
    # 5.000 aqui no se queda quieto en su fila.
    # OJO: solo en lo que ENTRA. El de salida (`ReportResponse`) va sin limites a proposito,
    # porque en la base ya hay pesos imposibles de antes y ponerselos haria que un reporte
    # viejo reventara al leerlo, que es peor que enseñarlo raro.
    weight: float = Field(..., ge=25, le=300)
    # El % de grasa, cada 12 semanas (bloque 6 del doc del 18-08). Es opcional porque solo se
    # le pregunta en el reporte que toca; el resto de meses no viaja. Con rango, por lo mismo
    # que el peso: un 300 aqui no se queda quieto, entra en el calculo de macros.
    body_fat: Optional[float] = Field(None, ge=3, le=70)
    measurements: Optional[Dict[str, float]] = None
    photos: Optional[List[str]] = None
    # Confirmación de huecos: {"dieta": "no_lo_hice"|"si_pero_no_apunte", "entrenamiento": ...}.
    # De aquí sale el cumplimiento; los dos campos de abajo quedan por compatibilidad con
    # los reportes viejos, que sí traían los deslizadores.
    huecos: Optional[Dict[str, str]] = None
    training_compliance: Optional[int] = None
    nutrition_compliance: Optional[int] = None
    sleep_quality: Optional[int] = None
    energy_level: Optional[int] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None
    # Las tres preguntas del formulario de siempre de Jesus que faltaban (punto 5 del
    # documento del 05-08):
    #  - `proximo_objetivo` DISPARA EL CAMBIO DE FASE: sin ella un Nivel 1 no puede cambiar
    #    de fase nunca, porque no tiene coach que se la cambie. Ademas es la que permite
    #    fechar el inicio de la fase (foto de "inicio de fase" del informe).
    #  - `viabilidad_ajuste` es el margen de la persona preguntado directamente: hasta ahora
    #    solo se sabia del cuestionario inicial, que se responde una vez y envejece.
    #  - `cumplimiento_entreno` devuelve la fuente a la barra de entrenos del informe, que
    #    se quedo sin dato en julio al recortar el check-in diario.
    proximo_objetivo: Optional[str] = None       # definicion | volumen | mantenimiento
    viabilidad_ajuste: Optional[str] = None      # me_adapto | necesito_mas | necesito_menos
    cumplimiento_entreno: Optional[str] = None   # todos | casi_todos | la_mitad | pocos | ninguno

    # ── Lo que trae el formulario nuevo (T7 y T8) ────────────────────────────
    # De qué reporte es. Lo manda el front y el servidor lo comprueba contra la semana
    # que le toca: sin esto, un reporte guardado no dice si era el quincenal o el mensual
    # y hay que deducirlo por si trae medidas, que es adivinar.
    tipo: Optional[str] = Field(None, pattern="^(quincenal|mensual|semanal)$")
    # QUINCENAL · las cuatro preguntas
    molestias: Optional[str] = Field(None, max_length=4000)
    sensaciones: Optional[int] = Field(None, ge=1, le=5)
    # MENSUAL · 04 dieta
    dieta_dificultad: Optional[str] = Field(
        None, pattern="^(nada|algun_dia|bastante|no_he_podido)$")
    # MENSUAL · 05 entreno (distinto por plan)
    entreno: Optional[EntrenoDelReporte] = None
    # MENSUAL · 06 lesiones y 07 cardio (solo quien los lleve en su plan)
    lesiones: Optional[List[LesionDelReporte]] = None
    lesion_nueva: Optional[str] = Field(None, max_length=4000)
    cardio_proximo_mes: Optional[str] = Field(None, pattern="^(mismas|mas|menos)$")
    # MENSUAL · 08 suplementación
    suplementacion: Optional[SuplementacionDelReporte] = None
    # MENSUAL · 09 energía (solo si la lleva baja: el bloque ni se enseña si va bien)
    energia_motivo: Optional[str] = Field(
        None, pattern="^(duermo_poco|estres_trabajo|como_poco|no_lo_se)$")
    # MENSUAL · 10 cómo lo valoras
    valoracion_resultado: Optional[int] = Field(None, ge=1, le=5)
    motivacion: Optional[int] = Field(None, ge=1, le=5)
    # MENSUAL · 13 sugerencias (opcional, y es para nosotros)
    sugerencias: Optional[str] = Field(None, max_length=4000)

class ReportResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    weight: float
    measurements: Optional[Dict[str, float]] = None
    photos: Optional[List[str]] = None
    training_compliance: Optional[int] = None
    nutrition_compliance: Optional[int] = None
    sleep_quality: Optional[int] = None
    energy_level: Optional[int] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None
    proximo_objetivo: Optional[str] = None
    viabilidad_ajuste: Optional[str] = None
    cumplimiento_entreno: Optional[str] = None
    trainer_feedback: Optional[str] = None
    # Lo del formulario nuevo, para que la ficha del cliente y el resumen puedan
    # enseñarlo. Los reportes viejos no lo traen y salen a null, que es lo que son.
    tipo: Optional[str] = None
    molestias: Optional[str] = None
    sensaciones: Optional[int] = None
    dieta_dificultad: Optional[str] = None
    entreno: Optional[Dict[str, Any]] = None
    lesiones: Optional[List[Dict[str, Any]]] = None
    lesion_nueva: Optional[str] = None
    cardio_proximo_mes: Optional[str] = None
    suplementacion: Optional[Dict[str, Any]] = None
    energia_motivo: Optional[str] = None
    valoracion_resultado: Optional[int] = None
    motivacion: Optional[int] = None
    sugerencias: Optional[str] = None
    # El informe que se monta al enviar (T9): mientras esté "pendiente_revision" el
    # cliente no lo ve; pasa a "entregado" cuando el coach lo publica.
    informe_estado: Optional[str] = None
    # LO QUE CONTESTÓ EN EL REPORTE MENSUAL DE CALMA: las ocho preguntas del formulario de
    # siempre, con sus palabras. No se meten en `training_compliance` y compañía porque allí
    # va un número y aquí lo que hay es una frase («Salvo algún día puntual, he cumplido con
    # todo lo que me has marcado»): convertirla en un porcentaje sería inventárselo.
    #
    # Sin declararlas aquí no llegan a ninguna pantalla. El modelo ignora lo que no conoce,
    # así que estaban escritas en la base de producción -- 1.796 reportes -- y no las veía
    # nadie, ni el cliente ni su entrenador.
    calma_respuestas: Optional[Dict[str, str]] = None
    photo_urls_calma: Optional[List[str]] = None
    created_at: str

# Check-In Models (3 niveles: daily, weekly, monthly) - portado de calmajp
class SuplementosDelDia(BaseModel):
    """La respuesta de "¿Tomaste tus suplementos?" y, si dijo "No todos", cuál y por qué."""
    respuesta: Optional[str] = Field(None, pattern="^(si|no_todos|no)$")
    detalle: Optional[str] = Field(None, max_length=1000)


class NotaDelDia(BaseModel):
    """Las "Notas personales" del cierre del día, con su marca. Van al Diario (T5) y el
    equipo solo ve las compartidas: la marca es del cliente y manda ella."""
    texto: Optional[str] = Field(None, max_length=4000)
    compartida: bool = False


class CheckInCreate(BaseModel):
    type: str  # "daily" | "weekly" | "monthly"
    # ── El cierre del día nuevo (T4 del doc 16-08) ────────────────────────────
    # Todo opcional a propósito: la pantalla enseña solo lo que le falta a ESE cliente
    # ese día, así que un cierre normal llega con la mitad de los campos vacíos. Los
    # campos de abajo (energy, hunger_anxiety, comido_hoy...) se siguen aceptando: los
    # check-ins ya guardados y las versiones viejas de la app no se tiran.
    descanso: Optional[int] = Field(None, ge=1, le=5)          # "¿Cómo has descansado?" · la noche de ayer
    movimiento: Optional[str] = Field(None, pattern="^(menos|igual|mas)$")
    # Qué contesta al "Hoy no entrenaste": lo puso pero no lo marcó, o no entrenó.
    entreno_respuesta: Optional[str] = Field(None, pattern="^(si_no_lo_puse|no_entrene)$")
    entreno_nota: Optional[str] = Field(None, max_length=1000)
    suplementos: Optional[SuplementosDelDia] = None
    # El check de la comida que le quedaba sin registrar. Se guarda AQUÍ y ya: no toca la
    # dieta ni le manda a Nutrición (criterio explícito del doc).
    cena_hecha: Optional[bool] = None
    # Y de cuál hablaba, que sin esto el booleano de arriba no se puede leer luego.
    comida_pendiente: Optional[str] = Field(None, max_length=20)
    exceso_nota: Optional[str] = Field(None, max_length=1000)
    notas: Optional[NotaDelDia] = None
    # Daily · DOS campos (documento 31-07-2026, partes 6 y 7.2): "solo lo que no está en
    # ningún dato: energía, y ansiedad y hambre. Lo de la dieta y el entreno se rellena
    # solo con lo registrado". `mood`, `trained` y `nutrition_followed` ya no se piden:
    # los dos últimos los deduce el servidor, y se conservan aquí por los check-ins viejos.
    energy: Optional[int] = None            # 1-5 (o 1-10 en weekly)
    hunger_anxiety: Optional[int] = None    # 1-5 · ansiedad y hambre (saturación en volumen)
    # Lo que ha comido hoy, con sus palabras (punto 18 del doc del 07-08). No es la dieta
    # planificada -- esa ya está en la app y el servidor la rellena solo -- sino lo que se ha
    # comido de verdad. Sirve para dos cosas, y las dos las dice Jesús: al cliente le hace
    # tomar conciencia de lo que se lleva a la boca, y a él le explica por qué alguien coge
    # peso sin saber por qué (el picoteo que nadie apunta en la dieta).
    comido_hoy: Optional[str] = None
    mood: Optional[int] = None
    trained: Optional[bool] = None
    nutrition_followed: Optional[bool] = None
    # Weekly
    # El mismo rango que el reporte y que la serie de peso: el check-in tambien escribe en
    # el historico (`anotar_peso`), asi que sin tope aqui se colaban por la otra puerta los
    # 50 y los 94 kg seguidos que salieron en las pruebas del 15-08 (#48).
    weight: Optional[float] = Field(None, ge=25, le=300)
    training_compliance: Optional[int] = None    # 0-100
    nutrition_compliance: Optional[int] = None   # 0-100
    sleep_quality: Optional[int] = None          # 1-10
    stress_level: Optional[int] = None           # 1-10
    # Monthly
    measurements: Optional[Dict[str, float]] = None
    body_fat_pct: Optional[float] = None
    photos: Optional[List[str]] = None
    goals_progress: Optional[str] = None
    challenges: Optional[str] = None
    # Común
    notes: Optional[str] = None

class CheckInResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    type: str
    # El cierre del día nuevo (T4). Salen a la respuesta porque de aquí los leen el
    # Diario (las notas) y el reporte del mes (descanso y movimiento).
    descanso: Optional[int] = None
    movimiento: Optional[str] = None
    entreno_respuesta: Optional[str] = None
    entreno_nota: Optional[str] = None
    suplementos: Optional[SuplementosDelDia] = None
    cena_hecha: Optional[bool] = None
    comida_pendiente: Optional[str] = None
    exceso_nota: Optional[str] = None
    notas: Optional[NotaDelDia] = None
    mood: Optional[int] = None
    energy: Optional[int] = None
    hunger_anxiety: Optional[int] = None
    comido_hoy: Optional[str] = None
    trained: Optional[bool] = None
    nutrition_followed: Optional[bool] = None
    weight: Optional[float] = None
    training_compliance: Optional[int] = None
    nutrition_compliance: Optional[int] = None
    sleep_quality: Optional[int] = None
    stress_level: Optional[int] = None
    measurements: Optional[Dict[str, float]] = None
    body_fat_pct: Optional[float] = None
    photos: Optional[List[str]] = None
    goals_progress: Optional[str] = None
    challenges: Optional[str] = None
    notes: Optional[str] = None
    # Las dos respuestas del reporte mensual de Calma, cada una en su campo.
    #
    # Venian pegadas dentro de `notes` en forma de "Importado de Calma. suplementacion=...
    # cumplimiento=...", que es el campo que el panel del entrenador pinta como "Comentario
    # cliente", asi que en 1.585 check-ins migrados esa columna enseñaba la cadena cruda en
    # vez de lo que escribio el cliente. Se separaron con _sync_reportes_medidas.py; aqui
    # salen a la respuesta para que la informacion no se pierda de vista al sacarla de ahi.
    calma_suplementacion: Optional[str] = None
    calma_cumplimiento_dieta: Optional[str] = None
    trainer_feedback: Optional[str] = None
    created_at: str

    # Los check-ins migrados de Calma guardan created_at como datetime (los que crea
    # la app lo guardan como texto ISO). Sin esto, un solo registro migrado tumbaba
    # la respuesta entera con un 500 y el coach no veia ningun check-in.
    @field_validator("created_at", mode="before")
    @classmethod
    def _fecha_a_texto(cls, v):
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        return v

# Message Models
class MessageCreate(BaseModel):
    # Opcional: si no se indica (o "support"), el backend lo resuelve al coach del
    # cliente o al primer admin (ver _resolve_receiver en routes/messages.py).
    receiver_id: Optional[str] = None
    content: str

class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    sender_id: str
    receiver_id: str
    content: str
    read: bool = False
    created_at: str

# Payment Models (Mocked)
class PaymentResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    amount: float
    status: str
    method: str = "card"
    currency: Optional[str] = None
    stripe_invoice_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    paid_at: Optional[str] = None
    created_at: str

# ---- Stripe billing ----
class CheckoutSessionRequest(BaseModel):
    plan: str
    # La pantalla de planes es /planes (documento 31-07). /onboarding redirige allí, así
    # que un pago que volviera a la vieja perdía el session_id por el camino.
    success_path: Optional[str] = "/planes?checkout=success"
    cancel_path: Optional[str] = "/onboarding?checkout=canceled"

class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: Optional[str] = None
    profile_id: Optional[str] = None

class BillingPortalResponse(BaseModel):
    url: str

class AlertResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    type: str
    severity: str
    title: str
    message: str
    related_data: Optional[Dict[str, Any]] = None
    acknowledged: bool = False
    resolved: bool = False
    created_at: str

# Food Suggestion Models
class FoodSuggestion(BaseModel):
    """Datos que rellena el cliente al sugerir un alimento (formulario del proceso).
    Los nombres de campo replican los del documento de `db.foods` para que la
    aprobación por el admin sea una copia directa al catálogo."""
    nombre: str
    por_unidad: bool = False          # False = valores por 100 g; True = por unidad
    racion: float = 100.0             # gramos de la ración (100 si por 100 g; peso de la unidad si por_unidad)
    peso_tipo: str = "neto"           # "neto" | "escurrido" (informativo; el admin lo revisa a mano)
    proteinas: float = 0.0
    hidratos: float = 0.0
    grasas: float = 0.0
    url: Optional[str] = None         # enlace a la fuente de los datos nutricionales

class FoodSuggestionUpdate(BaseModel):
    """Campos que el admin puede editar de una sugerencia durante la revisión."""
    model_config = ConfigDict(extra="ignore")
    nombre: Optional[str] = None
    por_unidad: Optional[bool] = None
    racion: Optional[float] = None
    proteinas: Optional[float] = None
    hidratos: Optional[float] = None
    grasas: Optional[float] = None
    url: Optional[str] = None
    categorias: Optional[str] = None   # categorías asignadas por el admin (pipe: "2.2|FRE")
    admin_notes: Optional[str] = None

class AdminFoodCreate(BaseModel):
    """Alta directa de un alimento en el catálogo desde el panel admin."""
    model_config = ConfigDict(extra="ignore")
    nombre: str
    por_unidad: bool = False
    racion: float = 100.0
    proteinas: float = 0.0
    hidratos: float = 0.0
    grasas: float = 0.0
    url: Optional[str] = None
    categorias: Optional[str] = None

class FoodSuggestionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    client_id: str
    food: FoodSuggestion
    status: str = "pending"
    created_at: str
    categorias: Optional[str] = None
    admin_notes: Optional[str] = None
    photos: List[str] = []            # tipos de foto subidos: "frontal" y/o "reverso"
