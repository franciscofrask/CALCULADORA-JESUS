# Plan de trabajo · Doc de Jesús 16-08 · "Qué hay que hacer en la app"

Fuente: `C:\Users\Administrador\Desktop\12EN12 · Qué hay que hacer · para Francisco.html`.
Copia en texto plano con TODOS los literales: `_internos_proceso/doc_jesus_1608_texto_literal.txt`. **Los textos del doc son ley**: se copian tal cual (tuteo, sin guiones largos, español de España). Ante cualquier duda de método, se relee el doc, no se pregunta.

Qué es: sustituir los 13 correos de ActiveCampaign por 19 avisos dentro de la app, más el rediseño de Inicio, Suplementos, Entreno, Cierre del día, Diario, Seguimiento y los dos reportes. Doce tareas T1-T12.

**Plazo**: el lunes 17-08 a las 18:00 (España) entran los clientes antiguos. T1-T4 tienen que estar para entonces. T5 en adelante, el mismo día o el siguiente. **No se despliega a prod sin permiso explícito de Francisco.**

**Aparcado, no tocar**: el reporte de mujer y el asistente de IA.

**Regla transversal del doc**: cada pantalla nueva se tiene que poder apagar desde el panel sin desplegar (ver Fase 0.2).

---

## 0 · Lo que ya hay (verificado en código el 16-08)

Rutas: frontend `frontend/src/...`, backend `backend/...`.

| Área | Estado real |
|---|---|
| Inicio | `pages/ClientDashboard.jsx` (1136 líneas). Enseña macros CONSUMIDOS ("X de Y"), no "te faltan". Sin frase del día, sin línea de suplementación; la tarjeta "Entreno de hoy" (`:738-756`) existe pero apagada por `can('rutina')`. |
| Suplementos cliente | **YA EXISTE Y FUNCIONA**: `pages/SupplementsPage.jsx` + `GET /supplements/current` (`routes/supplements.py:70`), con protocolo versionado por fecha (actual/siguiente), nota, y aviso al guardar (`supplements.py:166`). El doc la da por vacía: lo que falla es el ACCESO/los datos, no la pantalla (ver T2). |
| Rutina cliente | `pages/RoutinePage.jsx` completa pero inalcanzable: dos banderas gemelas hardcodeadas `frontend/src/lib/planAccess.js:29` y `backend/core/plan_access.py:50`. **No existe ningún registro de sesión hecha** (ni colección, ni endpoint, ni UI). |
| Cierre del día | Existe como "¿Cómo vas hoy?": `pages/CheckInsPage.jsx` (`/dashboard/checkins`), 3 campos (energía, hambre/ansiedad, "¿qué has comido hoy?"). `POST /checkins` type daily -> colección `checkins` (`routes/checkins.py:147`). |
| Diario | No existe nada. |
| Seguimiento | `pages/ReportsPage.jsx` (839 líneas), portada con 4 tarjetas (`PortadaSeguimiento` `:131`); la "segunda pantalla" es CheckInsPage, que en escritorio también se titula "Seguimiento" (`CheckInsPage.jsx:398-405`). **Bug real**: `setActiveTab` ya no existe pero se llama en `ReportsPage.jsx:452` y `:794` -> ReferenceError justo al enviar un reporte. |
| Evolución | Cliente: solo `GraficaDePeso` (con "Empezaste en / Ahora / Cambio" ya incluido, `components/GraficaDePeso.jsx:112-134`). Admin: todo lo que pide el doc ya está en la ficha: `EvolucionMedidas` (`pages/ClientDetailPage.jsx:1788`), `ComparativaFases` (`:3149`) con etiquetas en `lib/comparativaFotos.js`, `% graso` editable (`BodyFatFoto` `:3095`). |
| Reportes | Un solo formulario para quincenal y mensual (`ReportsPage.jsx:541-741`); solo cambian las medidas (mensual). Ventanas en `routes/report_cadence.py`: viernes 00:00 -> lunes 06:00 **UTC** (deuda anotada en `:226-231`). Semanas parametrizadas en `core/calendario_reportes.py` (quincenal pos. 2 y 4, mensual pos. 3, ciclo de 4 -> 2/4/6... y 3/7/11, exacto al doc). |
| Informe del mes | `components/reports/InformeMensual.jsx` existe; se monta al vuelo con `GET /reports/{id}/informe` (`core/informe_mensual.py:355`). NO se genera al enviar, NO se persiste, NO hay estado de revisión, y el coach no tiene UI para verlo (el endpoint sí se lo permite). |
| Avisos in-app | **Sistema maduro**: `db.notifications`, helper `notify()` (`routes/notifications.py`), reglas en `core/avisos_cliente.py` (calendario + condicionadas con tope de 1 condicionada / 7 días, dedupe por clave y caducidad). Se evalúa AL ENTRAR en la app ("cron by request"), no hay scheduler. Campana del cliente en `ClientDashboard.jsx:876-886, 1045-1100`. |
| Push / scheduler / tz | Push: nada (sw.js sin listener). Scheduler: ninguno. Timezone: todo UTC, cero `ZoneInfo` en el repo. |
| Flags desde panel | Solo `db.plan_overrides` (por plan, `routes/plans.py`, `AdminPlansPage.jsx`). No hay ajustes globales: apagar una pantalla para todos = tocar código y desplegar. |
| Frase del día | No existe en ninguna parte. |
| Ganchos de guardado admin | Macros: `PUT /admin/clients/{id}/macros` (`routes/admin.py:862`, notify `:989`) y `POST .../calculator/apply` (`:1081`, notify `:1193`). Suplementos: `supplements.py:127-168` (notify `:166`). Rutina: `routines.py:176-205` (notify `:202` APAGADO por la bandera). Guardar una DIETA no notifica nada (bien: es lo que pide el doc). |
| Planes | Vendidos: nivel1/2/3 (`models/user.py:95-342`). Los legacy `gold/silver/bronze` (+`reto12en12_*`) existen aparte (`:246-275`) y son los de los clientes antiguos que entran el lunes. Ojo: `bronze` hoy SIN reportes y el doc le da el mensual. |
| Correo | `core/correo.py` listo; en PROD funciona por relay del Workspace desde el 13-08 (SMTP_USER vacío a propósito). En dev el `.env` no tiene SMTP y encola en `db.correos_pendientes`. ActiveCampaign: no hay integración ninguna (ni falta: se queda encendido por fuera). |

---

## 1 · Decisiones ya tomadas (no reabrir)

1. **Plan = dato, por habilitaciones, nunca por nombre.** "Gold" del doc = quien tenga `quincenal` en `habilitaciones.reportes`. "Silver"/"Bronze" = solo `mensual`, distinguidos por `habilitaciones` (rutina personalizada vs rutina del mes). Antes de nada hay que cuadrar por `plan_overrides` las habilitaciones de los planes legacy con lo que el doc reparte (bronze necesita `reportes: ["mensual"]`). Los nivel1/2/3 reciben el trato que les toque por sus propias habilitaciones.
2. **Sin scheduler.** No hay push, así que una hora fija solo decide DESDE CUÁNDO se ve el aviso. Se sigue con `sincronizar_avisos()` al entrar: cada aviso de calendario se genera con su fecha-hora programada en Europe/Madrid y se enseña si ya pasó. No montar APScheduler ni celery ahora.
3. **Timezone.** Helper único `ahora_madrid()` / `a_madrid(dt)` con `zoneinfo` (`ZoneInfo("Europe/Madrid")`) en `backend/core/`. Todas las ventanas y avisos nuevos en hora España; migrar las de `report_cadence.py`. Guardar en Mongo siempre UTC; convertir en los bordes.
4. **Kill switch global.** Colección `db.app_settings` (un doc, campos por pantalla: `t1_inicio_nuevo`, `t2_suplementos`, `t3_entreno`, `t4_cierre_nuevo`, `t5_diario`, `t6_evolucion`, `frase_del_dia_activa`...). Endpoint admin GET/PUT + los flags viajan al front en la respuesta de `/auth/me` (o endpoint ligero que ya se llame al arrancar). Las DOS banderas hardcodeadas de rutina (`planAccess.js:29`, `plan_access.py:50`) pasan a leer de aquí. Cada pantalla nueva del plan se envuelve en su flag, encendidas por defecto en dev y apagadas hasta el pase a prod.
5. **Registro de entreno**: colección nueva `workout_logs`: `{id, client_id, fecha (YYYY-MM-DD), routine_id, dia_rutina, hecho (bool), estrellas (1-5), nota, pesos: [{ejercicio, reps, peso_kg}], compartida (bool), tipo: "entreno"|"cardio", created_at}`. Única por `client_id+fecha` (upsert). Es LA fuente de "entrenaste X de Y" en Inicio, quincenal y mensual (regla 3 del doc: se mira el dato).
6. **Diario = vista, no colección.** Compone `workout_logs` (entradas de entreno) + notas del cierre del día (`checkins.notas`) con su marca privada/compartida. El coach solo ve las compartidas.
7. **Aviso de macros**: atado a `PUT .../macros` y `calculator/apply` (ya es así; documentado). "Este mes no te toco nada" = en el `PUT`, si los macros entrantes son iguales a los vigentes, `notify` con ese texto en vez del de macros nuevos.
8. **Rotación de textos**: helper `elegir_variante(user_id, clave, variantes)` que mira la última notificación de esa `clave` en `db.notifications` y devuelve una variante distinta. Lo usan TODOS los avisos nuevos.
9. **PDF de la rutina (T3)**: no bloquea el lunes. Primera pasada: botón "Ver la rutina". El PDF, en la segunda pasada de T3.
10. **Errores nunca técnicos** (regla de la casa): frase humana al usuario, detalle a consola.

---

## 2 · Fase 0 · Cimientos (antes de T1, medio día)

- 0.1 `backend/core/tiempo.py`: `ahora_madrid()`, `a_madrid()`, `hoy_madrid()` (date). Tests unitarios de cambio de día (00:30 Madrid = 22:30 UTC del día anterior).
- 0.2 `db.app_settings` + `routes/settings.py` (GET público de flags + PUT admin) + sección en el panel admin (puede ir en `AdminPlansPage` o página propia pequeña) + hook front `useAppSettings()`/inyección en AuthContext.
- 0.3 `elegir_variante()` en `core/avisos_cliente.py`.
- 0.4 Colección `workout_logs` + índice `client_id+fecha` en `core/database.py`.
- 0.5 Habilitaciones de planes legacy revisadas contra el doc (vía `plan_overrides`, sin tocar código): gold -> quincenal+mensual; silver -> mensual; bronze -> mensual. Anotar lo que se cambie.
- 0.6 Fijar el "contrato" de la línea de entreno de Inicio (qué devuelve `/routines/current` + `workout_logs` de hoy) para que T1 y T3 puedan ir en paralelo sin pisarse.

---

## 3 · Las doce tareas

Para cada una: los literales exactos están en `doc_jesus_1608_texto_literal.txt` (buscar por el título). Aquí va el QUÉ y el DÓNDE.

### T1 · Inicio (cambia entero · los tres planes)
Fichero: `pages/ClientDashboard.jsx`. Reordenar a: saludo + fecha, **frase del día**, bloque **"Lo que toca hoy"** (macros + suplementación + entreno), bloque **"Pendiente"**, cierre.

- **Frase del día**: campo en `app_settings` (`frase_del_dia: {texto, fecha}`) editable desde el panel; la misma para todos; si hoy no hay nueva, se queda la anterior (sin enseñar fecha). Endpoint: va dentro del GET de settings.
- **Macros**: pasar de "consumido" a **"Te faltan X · de Y"** por macro, con barra: naranja = falta, amarillo = válido (dentro del margen), verde = cuadrado. La lógica válido/cuadrado ya existe (motor `calma_suggest`, estados de la calculadora; referencia front: `components/nutrition/DayHeader.jsx` versión móvil "Te queda por comer" y `MealCard.jsx:150-159 macroState`). **Estado del día** solo cuando los tres cuadran o son válidos: "Día cuadrado · los tres clavados" (verde) / "Día válido · los tres dentro del margen" (amarillo).
- **Suplementación**: línea "Tu suplementación · Whey · Omega 3 · Creatina" con los nombres de `GET /supplements/current`; pincha -> `/dashboard/supplements`. NUNCA dice "pendiente". "✓ hecho" si en el cierre de hoy marcó suplementos = sí.
- **Entreno**: línea solo si `GET /routines/current` trae rutina activa (regla 3). "Lo que te toca entrenar · Pierna, abdomen · ver la rutina" -> pantalla T3. Día de solo cardio: "Hoy solo cardio · 40 minutos · ver la pauta". Tras registrar: "✓ hecho" + resumen "★★★★☆ · Press banca 80 kg". Si no lo marca, se queda sin marcar. **Nunca en rojo.**
- **Pendiente**: "¿Cómo fuiste hoy? · Para rellenar al final del día" -> T4; si ya hay checkin hoy o ayer, en su lugar "último registro: ayer, 21:40". "Completar perfil" y "Alimentos preferentes" (reusar la checklist actual `:86-138`). "Reporte mensual · Hasta el lunes 24 a las 18:00 h España · te quedan 2 días" desde `/reports/due`; **pasada la hora desaparece** (también en T6).
- **Cierres** cuando no queda nada, rotando (3 variantes del doc).

### T2 · Suplementos (la pestaña existe, el contenido "no")
1. Diagnosticar por qué un Gold real no ve su protocolo: (a) `habilitaciones.suplementacion` de su plan (CapabilityRoute + `require_access`), (b) si tiene doc en `supplement_protocols` con versión vigente. Arreglar por datos/overrides, no a martillazos.
2. Entrada desde Inicio (línea de T1) además del menú.
3. Ajustar literales a los del doc: título "Tu suplementación", subtítulo "Lo que te he pautado y cuándo tomarlo", formato "1 cacito · después de entrenar".
4. El aviso al cambiar ya existe (`supplements.py:166`); verificar en navegador que llega y que la pantalla enseña lo nuevo.

### T3 · Entrenamiento (pantalla nueva · quien tenga rutina cargada)
1. Encender rutina: las dos banderas pasan a leer del flag `t3_entreno` de `app_settings` (0.2). El `notify` de rutina nueva (`routines.py:202`) se enciende con el mismo flag.
2. **Pantalla de registro** (ruta nueva, p. ej. `/dashboard/entreno`, enlazada desde la línea de Inicio): cabecera "[Grupo muscular] · Semana n · rutina n"; "Ver la rutina" -> RoutinePage (PDF en segunda pasada, decisión 9); "¿Lo has completado?" [Hecho][No hecho]; "Sensaciones" estrellas; "Algo que destacar" texto; "Pesos de referencia" opcional (filas ejercicio/reps/peso última serie + "Añadir ejercicio"), **precargando los de la última vez con esa misma rutina**; check "Compartir con nosotros"; Guardar -> `POST /workout-logs` (upsert por día).
3. Lo escrito aparece en el Diario (T5) y la línea de Inicio pasa a "✓ hecho" con estrellas + peso.

### T4 · Cierre del día · "¿Cómo fuiste hoy?" (existe, cambia el contenido · los tres planes)
Fichero: `pages/CheckInsPage.jsx` (parte daily) + `routes/checkins.py` (+ modelo en `models/common.py`).

- Renombrar a "¿Cómo fuiste hoy?".
- **Primero, lo que no ha marcado, en este orden** (todo condicional, campo libre, sin opciones cerradas salvo los botones del doc):
  1. Entreno (si tiene rutina y no hay workout_log hoy): "Hoy no entrenaste." [Sí, pero no lo puse -> **lleva a T3**] [No entrené] + "Cuéntame si quieres qué pasó. Opcional."
  2. Suplementos: "¿Tomaste tus suplementos?" [Sí][No todos][No]; si no todos: "¿Cuál y por qué?".
  3. Comida sin registrar (mirando `diets` del día): "Te queda la cena sin registrar." + check "La hice". **El check se guarda en el checkin y ya: NO toca la dieta ni lleva a Nutrición.**
  4. Pasado de macros: "Hoy te has pasado 40 g de hidratos." + campo libre opcional.
- **Luego lo de siempre**: "¿Cómo has descansado?" (NUEVO, "La noche de ayer.", 1-5 fatal -> de lujo); "Energía" (ya, 1-5); "Hambre / ansiedad" (ya, UNA escala); "¿Te moviste lo suficiente?" (NUEVO, 3 botones + subtítulo del doc); "Notas personales" + check "Compartir con nosotros" (van al Diario con su marca); "Peso · Opcional · último registro: 77,3 kg, ayer" (escribe la serie vía `anotar_peso`, sigue obligatorio en reportes).
- Quitar "¿Qué has comido hoy?" (T11). Al guardar: "Anotado. Mañana seguimos."
- Backend: ampliar el modelo daily con `descanso, movimiento, entreno_respuesta, suplementos {respuesta, detalle}, cena_hecha, exceso_nota, notas {texto, compartida}, weight` y aceptar los campos viejos por compatibilidad.

### T5 · El Diario (pantalla nueva · los tres planes)
- Vive DENTRO de Seguimiento (sección nueva de `ReportsPage.jsx`, no pestaña del menú).
- `GET /diary` (o componer en `reports.py`): entradas de `workout_logs` (fecha + texto + estrellas + peso destacado + compartida) y de `checkins` con nota (fecha + texto + compartida). Solo lectura, orden cronológico inverso, marcas "🔒 Solo para ti" / "Compartida".
- El coach solo ve las compartidas (filtro server-side en la vista de admin; puede engancharse en `CoachCheckins` o ficha, segunda pasada).

### T6 · Seguimiento y Evolución (gran parte ya está en admin · se quitan 2 pantallas)
- Portada de `ReportsPage.jsx`: bloque superior "ESTA SEMANA · TE TOCA / Reporte quincenal ... Empezar" (+ "Después de este: tu reporte mensual, el viernes 21." con el `proximo` que ya existe) y TRES tarjetas: "Reportes · Los que mandaste y los informes que te di" (historial actual, con los informes dentro), "Evolución · Tus fotos y tus métricas", "Diario · Tus notas, día a día". Fuera la tarjeta "¿Cómo vas hoy?" (`seg-hoy`).
- CheckInsPage deja de titularse "Seguimiento" en escritorio: queda solo como el formulario del cierre (entrada desde Inicio). Los collapsibles semanal/mensual se quitan (T11).
- Pasada la hora del reporte, desaparece de aquí y de Inicio (filtrar `overdue`).
- **Evolución del cliente**: portar de la ficha admin: `GraficaDePeso` (ya la tiene) + `EvolucionMedidas` (extraer de `ClientDetailPage.jsx:1788` a `components/` compartido; datos de `GET /reports` propios) + `ComparativaFases` adaptada: **dos fotos por defecto** ("DE DÓNDE VENGO" y "CÓMO ESTOY HOY") + botones "+ La del medio" y "Mostrar todas"; **fuera el % graso** (lo rellena Jesús); etiquetas y el texto bajo la tabla, los de admin, tal cual (`lib/comparativaFotos.js`; unificar la copia duplicada de `InformeMensual.jsx:77`). Fotos propias: `GET /reports/photos` ya existe.
- Arreglar `setActiveTab` roto (`ReportsPage.jsx:452` y `:794`).

### T7 · El reporte quincenal (de 6 preguntas a 4 · solo Gold = quien tenga quincenal)
- Separar el formulario quincenal del mensual (hoy son el mismo). Contenido: bloque previo "ANTES DE RELLENAR · No registraste el entreno N días de los M que tenías" [No entrené][Sí entrené, no lo apunté] (de `workout_logs` vs días de rutina de las 2 semanas); Peso obligatorio con último registro; "¿Algún ejercicio de la rutina te da molestias o te falta alguna máquina?"; "Sensaciones" estrellas; "Y lo que quieras contarme."
- Fuera: dieta, cardio y suplementación (ya se marcan a diario).
- Ventana: **miércoles 09:00 -> jueves 20:00 Europe/Madrid** (`report_cadence.py`: usar `_client_deadline` en la ventana real y el helper de tz). Sustituye al WhatsForm (externo, nada que tocar en código).

### T8 · El reporte mensual (orden nuevo, bloques por plan: Gold 13 · Silver 11 · Bronze 11)
- Ventana: viernes -> **lunes 18:00 España**, semanas 3/7/11 (la cadencia ya lo da).
- Cabecera con plazo + **"¿No has podido hacer el programa completo estas 3 semanas? Márcalo y te lo aplazo 7 días."** -> `POST /reports/aplazar`: corre la ventana 7 días para ese cliente (campo en `client_profiles`, p. ej. `reporte_aplazado_hasta`) + aviso de confirmación (T10).
- Orden: 01 Peso · 02 Medidas (las 10, **con la del mes pasado al lado**, de `GET /reports/previous`; vídeo ya existe) · 03 Fotos (`TresFotos`, ya) · 04 Dieta CON EL DATO ("has registrado 25 de 28 días", "cuadraste 19", "6 corto de proteína": de `diets` + `calma_suggest`) + "¿Te ha costado seguirla?" + "¿Podrías con un ajuste nuevo?" (ya existe como `viabilidad_ajuste`) · 05 Entreno POR PLAN (Gold: dato + media de estrellas de `workout_logs`; Silver: confirmar los no rellenados + estrellas + libre; Bronze: pregunta de regularidad + **la rutina del mes a 57 €** básica/avanzada con autorización de cargo + "Cuéntame el Silver" [-> aviso al equipo, `avisar_al_equipo`]) · 06 Lesiones SOLO GOLD (estructura nueva `client_profiles.lesiones: [{zona, desde, estado_mes, ejercicios_vetados[]}]`, con "LO QUE YA ME CONTASTE" + peor/igual/mejor/superada + "¿Alguna nueva?") · 07 Cardio SOLO GOLD (dato de `workout_logs` tipo cardio + "de cara al mes que viene") · 08 Suplementación (los tres) · 09 Energía CONDICIONAL (solo si la media de `checkins.energy` del mes < 3) · 10 Valoración + motivación (estrellas, nuevas) · 11 Próximo objetivo (ya existe) · 12 Libre · 13 Sugerencias (nueva, opcional).
- Fuera: sliders de sueño/energía/estrés (el sueño ya vive en T4) y toda oferta que no sea la rutina del Bronze.
- El cargo de 57 € necesita un price en Stripe LIVE: **lo crea Francisco** (ver sección 6). Mientras no esté, el bloque se enseña sin cobro real solo en dev.

### T9 · Al enviar · resumen e informe (no existe · distinto por plan)
- **Resumen antes de enviar**: pantalla "Revisa antes de enviar" con TODO lo contestado (literales del doc) y volver atrás a editar. Componente nuevo en el flujo del formulario.
- Al enviar: Silver/Bronze -> "Reporte enviado. Antes del viernes tienes tus ajustes nuevos. Te aviso por aquí."; Gold -> "... Antes del sábado tienes tu informe completo con mi feedback y tus ajustes ...".
- **Informe con estado**: al `POST /reports`, generar el informe (`montar_informe`) y guardarlo en el report con `informe_estado: "pendiente_revision"`. Vista ADMIN del informe montado en la ficha (el endpoint `/reports/{id}/informe` ya acepta admin; falta la UI) + campo para "lo suyo" (feedback, ya existe `PUT /reports/{id}/feedback`) + botón **"Publicar"** -> `informe_estado: "entregado"` + aviso "Tu informe está listo" (solo Gold).
- Silver/Bronze no ven informe con feedback: su aviso "Tienes ajustes nuevos" sale de que Jesús les guarde macros (gancho de T10); el cliente ve los ajustes en Nutrición/MisMacros.

### T10 · Los 19 avisos (el sistema de reglas existe, los avisos no)
Todo en `core/avisos_cliente.py` + `sincronizar_avisos()`, con `elegir_variante()` (decisión 8) y hora España (0.1). **Los textos, LITERALES del doc, con todas sus variantes** (sección "Los 19 avisos" del texto literal).

- **8 de calendario** (siempre salen): domingo 19:00 antes del día 1 "Mañana empiezas" (ya hay uno parecido: ajustar textos); cada día 20:00 "Cierra tu día" si no cerró (NUEVO; activado por defecto, **con toggle para apagarlo** en Perfil -> `profile.avisos.cierre_dia`); mié 09:00 semanas pares "quincenal abierto" (solo Gold; `report_cadence.py:381` ya notifica apertura: ajustar texto/hora/variantes); jue 09:00 "último día quincenal" si no lo mandó; viernes semanas 3/7/11 "mensual abierto"; domingo 10:00 "último día mensual"; **martes "No me llegó tu reporte" si pasó la hora sin mandarlo (NUEVO, hoy no existe ni el correo lo cubre bien)**; semana 11 "Tu ciclo acaba en una semana" (ya hay uno de fin de ciclo: ajustar).
- **6 de acción de Jesús** (al guardar, sin hora): macros nuevos (ya, revisar texto + variantes + "+ tu nota"); **macros sin cambios "Este mes no te toco nada" (NUEVO, comparar antes/después en el PUT)**; ajustes nuevos S/B (T9); informe listo Gold (T9); suplementación (ya, revisar texto); rutina nueva (encender el notify, T3).
- **4 condicionadas** (tope 1/semana YA implementado; el orden de prioridad es el del doc): 1 reporte hace <=7 días sin fotos (ya hay una parecida); 2 dos semanas o más sin ajuste (ya hay una); 3 **cinco días sin cerrar el día** (nuevo criterio: `checkins`, no dieta); 4 catorce días sin entrar (ya). **Quitar las condicionadas viejas que el doc no trae** (estancado, sin peso 7d, sin dieta 5d): sustituidas por estas.
- **1 de confirmación**: al aplazar (T8): "Te lo he aplazado 7 días...".
- ActiveCampaign NO se apaga: convive unas semanas. Nada que tocar en código; sus dos fallos (hora quincenal, UTC) se corrigen ALLÍ y eso es de Jesús/Francisco.

### T11 · Lo que se quita
| Qué | Dónde |
|---|---|
| Check-in semanal | `CheckInsPage.jsx:512-527` (backend sigue aceptando por compat) |
| Check-in mensual | `CheckInsPage.jsx:529-561` |
| Segunda pantalla "Seguimiento" | CheckInsPage como pantalla titulada Seguimiento (T6) |
| Tarjeta "¿Cómo vas hoy?" | `ReportsPage.jsx:200-207` (T6) |
| "¿Qué has comido hoy?" | `CheckInsPage.jsx:472-484` (T4) |
| Sueño/energía/estrés del reporte | sliders en `ReportsPage.jsx` form (T8) |
| Formularios de Google (x3) y WhatsForm | externos, nada en código; se retiran al apagar ActiveCampaign |
| FIT3D, CBD, menús, trimestral, "otros servicios" | NO están en el form actual de la app (verificado): viven en los formularios externos. Verificar que ningún texto legacy los mencione y listo |
| Texto del chat | `MessagesPage.jsx:176-181`: el literal viejo ya no está; ajustar el estado vacío de Silver/Bronze a "aquí te llegan los mensajes y los avisos" según el doc |

### T12 · Cinco fallos del panel de admin (localizados, causa confirmada)
1. **Dietas con P0 H0 G0**: `admin.py:739-749` (`get_client_diet`) devuelve el doc crudo; 3.731 de 4.166 alimentos guardados no traen `macros_efectivos` (medido en `diets.py:679-690`). Arreglo: enriquecer en el backend reutilizando `_macros_de()` (`diets.py:676-703`) y `_adjuntar_urls()` (`diets.py:461-512`) extraídos a helper compartido. NO parchear con defaults en el front (`ClientDetailPage.jsx:3537-3597`).
2. **"Huevo = 1 g"**: mismo endpoint; falta pasar por `_normalizar_cantidades` (`diets.py:419-458`) y devolver el texto resuelto tipo `_cantidad_de()` -> "2 ud (126 g)". El front (`ClientDetailPage.jsx:3581`) pinta lo que llegue.
3. **"152/135" arriba vs "faltan 4,1" abajo**: `components/nutrition/DayHeader.jsx:242-263` (bloque ESCRITORIO; el móvil `:150-199` ya está bien) -> "Te faltan X de Y". No tocar `DaySummary.jsx` (está sin uso).
4. **Tope de cantidad en la calculadora**: hoy solo `TOPE_GRAMOS = 2000` (`lib/cantidades.js:19`). Llevar el tope por alimento del asistente (`chatbot.py:1044-1102` `_get_max_cantidad_razonable`) a la calculadora: mejor vía backend (devolver `max_razonable` en la ficha/búsqueda del catálogo) y aplicarlo en `leerCantidad` + los 5 call sites (`NutritionPage.jsx:1296-1301, 1319-1345`, `BuildMealModal.jsx:787, 851-890`, inputs sin `max` en `BuildMealModal.jsx:1239` y `MealCard.jsx:266`). Como el asistente: por encima del tope AVISA/pide confirmación, no bloquea en seco.
5. **"62800 kg"**: `EvolutionTimeline` (`ClientDetailPage.jsx:2860-2931`) mezcla pesos de la app (kg) con `calma_raw.formularios_mensuales` (GRAMOS) sin sanear. Arreglo en el origen: aplicar `sanea_peso` (`core/series_cliente.py:49-69`, ya usado en otros endpoints) a `calma_raw` y `reports` dentro de `get_client_detail` (`admin.py:321-405`). Cubre de paso `MuralFotos` y `ComparativaFases`, que comparten `_pesoCercano`.
- **Y lo que hay que atar** (pedido del doc): el aviso de macros se dispara SOLO al guardar la pestaña Macros (`PUT .../macros` / `calculator/apply`), nunca al guardar la dieta de un día. Ya es así: dejarlo escrito en un comentario en ambos endpoints para que nadie lo mueva.
- **No tocar**: la barra de suplantación y el método de la calculadora (faltan/sobran, Válido/Cuadrado, prioridad, Cuadrar, Vaciar). El doc lo da por bien resuelto.

---

## 4 · Orden y reparto

El doc manda entrega **en orden T1 -> T12**, T1-T4 para el lunes 18:00. Reparto compatible con eso (ficheros disjuntos):

- **Oleada 1 (hoy/mañana)**: Fase 0 -> luego en paralelo: agente A = T1+T2 (ClientDashboard, settings, supplements), agente B = T3+T4 (workout_logs, pantalla entreno, CheckInsPage; el contrato de la línea de Inicio queda fijado en 0.6), agente C = T12 entero (solo admin, no pisa a nadie).
- **Oleada 2 (lunes/martes)**: T5+T6 (ReportsPage, Diario, Evolución), luego T7+T8+T9 (reportes, mismo terreno: mejor UN agente o en fila), y T10 al final (necesita los ganchos de T3/T8/T9 ya puestos).
- T11 se va haciendo dentro de T4/T6/T8 (cada quita pertenece a una tarea); repasar la tabla al final.

Reglas de la casa que aplican: probar SIEMPRE en navegador con la extensión (cuentas: admin `francisco@test.com` / demo123, cliente `clientedemo@test.com` / demo123); si un cambio "no hace nada", mirar primero si el backend de dev sirve código viejo (puerto duplicado); commitear y pushear solo lo tocado por cada uno; **nada de guiones largos** en textos; los tests con `REACT_APP_BACKEND_URL` y el backend vivo.

---

## 5 · Riesgos y trampas conocidas

- **Claves de macros inglés/castellano** conviven en la base: nunca leer una sola familia con default (da 160/50/40 o ceros sin error). Usar los normalizadores existentes.
- **`macro_history`**: la fecha buena es `effective_date`, nunca `created_at` (en filas de Calma es el día de la importación).
- **Dos ids de cliente**: `users.id` vs `client_profiles.id` según la tabla; cuidado en `workout_logs` y el diario (usar el mismo criterio que `checkins`: `client_id` = profile id).
- **Cadencia UTC -> Madrid**: al mover las ventanas, revisar los tests de `report_cadence` y los textos `opens_label/closes_label`.
- **Clientes migrados de Calma**: dietas con `cantidad_g` = piezas, pesos en gramos, reportes sin fotos (3.151 con 0 fotos). Todo lo que enseñe "el dato" tiene que sobrevivir a esos datos.
- **La campana del equipo no se pinta en ningún panel** (`avisar_al_equipo` escribe y nadie lee): el "Cuéntame el Silver" de T8 avisará a un panel que no lo enseña. Añadir la lectura en el panel admin cuando toque T8, o el aviso se pierde.
- Los reportes de mujer y el asistente: NO tocar aunque pasen por delante.

## 6 · Lo que no depende del código (Francisco / Jesús)

- Crear en Stripe LIVE el price de la rutina del mes (57 €) para el Bronze, y decidir el copy del cargo.
- Cuadrar con Jesús las habilitaciones definitivas de gold/silver/bronze legacy (0.5) y confirmar que Bronze hace el mensual.
- Meter las frases del día en el panel cuando exista el campo.
- Corregir en ActiveCampaign (mientras siga encendido) la hora del quincenal (dice 20:00, cierra 18:00) y el UTC. Y decidir cuándo se apaga (cuando los reportes lleguen igual o mejor por la app).
- Dar el OK al despliegue a prod (nunca sin permiso).
