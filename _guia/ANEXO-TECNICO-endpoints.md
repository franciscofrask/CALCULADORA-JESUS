# Anexo técnico · Los 194 endpoints, uno por uno

Complemento de `GUIA-COMPLETA-12EN12.md`. La guía explica **qué hace la app**; esto explica
**por dónde**. Todos los endpoints cuelgan de `/api`.

**Quién puede llamar a qué**:
- *Sesión* — cualquier usuario con la sesión iniciada
- *Cliente* — además, con ficha de cliente y el plan que corresponda
- *Equipo* — admin **o** trainer
- *Solo admin* — trainer excluido
- *Público* — sin sesión

---

## auth · 5 endpoints

| Endpoint | Acceso | Qué hace |
|---|---|---|
| `POST /auth/register` | Público | Crea el usuario (rol `client`, sin plan). No crea ficha de cliente todavía. 400 si el correo existe |
| `POST /auth/login` | Público | Devuelve el token. 401 genérico si falla (no revela si el correo existe). 403 si la cuenta está de baja. Migra al vuelo las contraseñas antiguas de Firebase |
| `GET /auth/me` | Sesión | Los datos del usuario |
| `PUT /auth/me` | Sesión | Cambia nombre y teléfono |
| `POST /auth/change-password` | Sesión | Pide la actual; la nueva, 8+ caracteres |

## plans · 7 endpoints

| Endpoint | Acceso | Qué hace |
|---|---|---|
| `GET /plans` | Sesión | El catálogo con los cambios del admin aplicados. Filtrable por estado |
| `GET /quiz-venta` | **Público** | Las 4 preguntas del test de nivel |
| `POST /quiz-venta` | **Público** | Calcula el nivel recomendado. No guarda nada |
| `POST /quiz-venta/guardar` | **Público** | Guarda el resultado como lead. Exige nombre y teléfono si pide llamada. Si el correo ya existe, responde lo mismo sin decirlo (si no, sería un enumerador de correos) |
| `GET /admin/plans` | Equipo | El catálogo, marcando cuáles tienen cambios |
| `PUT /admin/plans/{code}` | Equipo | Edita un plan. Solo 8 campos son editables; el resto se ignora |
| `DELETE /admin/plans/{code}` | Equipo | Restaura el plan a su valor por defecto |

## users · 21 endpoints

| Endpoint | Acceso | Qué hace |
|---|---|---|
| `GET /clients/profile` | Sesión | La ficha del cliente |
| `PUT /clients/profile` | Cliente | Actualiza campos de la ficha |
| `POST /clients/questionnaire` | Cliente | El alta (4 preguntas). 409 si ya está hecho, 404 si no hay ficha |
| `POST /clients/questionnaire/nivel1` | Cliente | El perfil largo. No toca macros |
| `POST /clients/ajustar-macros` | Cliente | El quiz de ajuste. **Si el plan tiene coach, deja una propuesta pendiente en vez de aplicar** |
| `PUT /clients/ajuste-progreso` | Cliente | Guarda el quiz a medias para poder retomarlo |
| `GET /clients/mis-dias` | Cliente | Sus días ya montados, para "contar mi dieta" |
| `POST /clients/leer-dieta` | Cliente | Lee su dieta actual de texto, foto o un día suyo |
| `POST /clients/punto-de-partida` | Cliente | Guarda medidas y altura |
| `GET /clients/mi-ficha` | Cliente | Composición corporal, índice de muscularidad y casos parecidos |
| `PATCH /clients/onboarding` | Cliente | Marca pasos del "empieza aquí" |
| `GET`/`POST /user/preferences` | Cliente | Preferencias y evitados. Mínimo 3 categorías que le gusten |
| `GET`/`PATCH /user/diet-config` | Cliente | Comidas al día, momento de entreno, peri |
| `GET /macros` | Cliente | Sus macros. Con `?fecha=` devuelve **los que estaban vigentes ese día** |
| `PUT /macros` | Cliente | Guarda sus macros. **Recalcula en el servidor** si vienen respuestas del quiz. Crea entrada en el historial y avisa al coach si la dieta no cuadra |
| `GET`/`POST`/`DELETE /favorites` | Cliente | Favoritos de alimento (interfaz oculta hoy) |

## calculator · 29 endpoints

**Catálogo**

| Endpoint | Qué hace |
|---|---|
| `GET /calculator/foods` | Lista con filtro de texto y categoría |
| `GET /calculator/foods/count` | Cuántos alimentos hay |
| `GET /calculator/foods-listado` | El catálogo entero enriquecido: macros efectivos, cantidad mínima y por qué se sugeriría |
| `GET /calculator/categories` · `/count` | Las categorías |
| `GET /calculator/food-config/{id}` | Unidades, mínimos y pasos de un alimento |

**Búsqueda y sugerencia**

| Endpoint | Qué hace |
|---|---|
| `GET /calculator/search` | **El buscador principal.** Con macros restantes, ordena por lo que mejor cuadra y calcula la cantidad sugerida. En post-entreno restringe el universo a esa categoría. Devuelve además qué preparaciones existen |
| `GET /calculator/frequent-foods` | Los que más usa ese cliente |
| `POST /calculator/suggest` | Sugerencias para completar lo que falta. Acepta `excluir_ids` para pedir otras |
| `POST /calculator/adjust` | **Cuánto poner de un alimento** para lo que queda. Se repuso el 02-08-2026: no existía y el frontend lo llamaba, así que añadir un alimento desde el buscador estaba roto |

**Macros de alimentos**

| Endpoint | Qué hace |
|---|---|
| `POST /calculator/macros-efectivos` | Los macros de un alimento a una cantidad |
| `POST /calculator/macros-comida` | Los de una comida entera |
| `POST /calculator/calibrar-dia` | Recalcula el día aplicando la calibración progresiva |
| `POST /calculator/meal` | Suma simple (heredado) |

**Reparto y objetivos**

| Endpoint | Qué hace |
|---|---|
| `POST /calculator/distribute` | **El reparto del día entre comidas.** Resuelve los macros vigentes en esa fecha |
| `POST /calculator/targets` | **Calcula** macros. Con respuestas del quiz usa el motor v2 |
| `POST /calculator/targets/apply` | Calcula **y aplica** al perfil. Usa los ajustes ya guardados, no los del cuerpo. **No deja rastro en el historial** |
| `POST /calculator/refit-diet` | Reajusta las cantidades de un día a sus macros sin pasarse |

**Menús**

| Endpoint | Qué hace |
|---|---|
| `POST /calculator/library-menus` | **La biblioteca real** (266k comidas) con el ajuste por palancas |
| `POST /calculator/menu-options` | Opciones del recetario (y de la biblioteca, si lo pide el coach) |
| `GET /calculator/menu-catalog` | Listado del recetario |
| `POST /calculator/menu-apply` | Cuadra un menú concreto |
| `POST /calculator/library-search` | Busca menús que contengan ciertos alimentos |

**Sugerir alimentos**

| Endpoint | Qué hace |
|---|---|
| `POST /calculator/suggest-food` | El cliente propone uno, con 2 fotos. Máx. 2 por semana, 6 MB por foto |
| `GET /calculator/my-food-suggestions` | Las suyas y su estado |
| `GET /calculator/food-suggestions/{id}/photo/{kind}` | La foto. Solo el dueño o el equipo |

**Diagnóstico**: `GET /calculator/test-calma`, `/test-targets`, `/test-templates`.

## diets · 12 endpoints

| Endpoint | Qué hace |
|---|---|
| `GET /diets/{fecha}` | La dieta de un día. Añade el enlace de marca y los macros de etiqueta de cada alimento |
| `POST /diets` | Guarda el día |
| `DELETE /diets/{fecha}` | Borra el día |
| `GET /diets/{fecha}/pdf` | **El PDF.** Recalcula el objetivo con los macros vigentes esa fecha |
| `GET /diets/calendar/{año}/{mes}` | El estado de cada día del mes |
| `GET /diets/recent` | Los últimos días con dieta, para "Repetir" |
| `POST /diets/copy-day` | Copia un día entero |
| `POST /diets/copy` | Copia una comida |
| `GET`/`POST`/`DELETE /diets/favorites` | Plantillas de día con nombre |

## chatbot · 14 endpoints

| Endpoint | Qué hace |
|---|---|
| `POST /chatbot/start` | Arranca la conversación y devuelve sus macros |
| `POST /chatbot/message` | **El mensaje.** Router de intención + ejecución determinista |
| `POST /chatbot/configure` | Las respuestas de configuración del día |
| `POST /chatbot/complete-meal` | Cierra la comida y pasa a la siguiente |
| `POST /chatbot/save` | Vuelca la conversación a la dieta del día |
| `GET /chatbot/session` | Rehidrata la sesión (guardada en base de datos, caduca a 7 días) |
| `DELETE /chatbot/session` | La borra |
| *(y el resto de acciones: añadir por id, elegir opción, navegar entre comidas, resumen, PDF)* | |

## reports · 7 endpoints

| Endpoint | Qué hace |
|---|---|
| `POST /reports` | Envía el reporte. Valida plan y **ventana de envío**. Calcula el cumplimiento desde la confirmación de huecos |
| `GET /reports` | Su historial |
| `GET /reports/previous` | El anterior, como referencia |
| `GET /reports/confirmacion-huecos` | **Los huecos a confirmar**, con la pregunta ya redactada |
| `GET /reports/evolution` | Series de peso y medidas |
| `GET /reports/{id}/informe` | **El informe de 8 apartados.** Lo puede pedir el cliente o su coach |
| `PUT /reports/{id}/feedback` | El coach escribe su explicación. Avisa al cliente |

## report_cadence · 2 endpoints

| Endpoint | Qué hace |
|---|---|
| `GET /reports/due` | Qué reporte toca esta semana y su ventana. Crea el aviso al abrirse |
| `GET`/`POST /admin/report-cadence` | La cola de reportes del equipo (tarjeta oculta hoy) |

## checkins · 11 endpoints

| Endpoint | Qué hace |
|---|---|
| `POST /checkins` | Crea el check-in. **En el diario, rellena solo la dieta** con lo registrado |
| `GET /checkins` | Su historial |
| `GET /health-score` | Su semáforo |
| `GET /admin/clients/{id}/checkins` · `/health-score` | Los del cliente, para el coach |
| `POST /admin/clients/{id}/checkins/{id}/feedback` | El coach comenta |
| `POST`/`GET`/`DELETE /reports/photos` | Fotos de progreso (máx. 4 MB) |
| `GET /admin/clients/{id}/photos` | Las del cliente, para el coach |

## routines · 5 endpoints

| Endpoint | Qué hace |
|---|---|
| `GET /routines/current` · `/history` | Su rutina activa y las anteriores |
| `GET /admin/routines/overview` | Quién tiene rutina y quién no |
| `POST /admin/routines/generate` | Genera con IA. **No guarda**: es previsualización |
| `POST /admin/routines/save` | Guarda y desactiva la anterior. Avisa al cliente |

## supplements · 7 endpoints

| Endpoint | Qué hace |
|---|---|
| `GET /supplements/current` | Su protocolo |
| `GET`/`POST`/`PUT`/`DELETE /admin/supplements/catalog` | El catálogo. El borrado es lógico |
| `POST /admin/supplements/save` | Guarda el protocolo. Avisa al cliente |
| `POST /admin/supplements/suggest` | Propuesta por heurística (sexo y objetivo). No guarda |

## billing · 11 endpoints

| Endpoint | Qué hace |
|---|---|
| `POST /billing/checkout-session` | **El pago.** Ancla al lunes, congela el precio, descuenta la revisión suelta |
| `POST /billing/checkout-session/sync` | Confirma al volver. **Verifica que la sesión es suya** |
| `POST /billing/revision-suelta/checkout` | La revisión de 147 € |
| `GET /billing/renovacion` | El balance de la semana 12. No cobra |
| `POST /billing/portal` | El portal de Stripe. **Ninguna pantalla lo llama hoy** |
| `POST /stripe/webhooks` | Los eventos. Firma verificada e idempotencia por evento |
| `POST /admin/stripe/sync-client/{id}` · `/sync-pending` | Resincronizar |
| `GET /admin/stripe/upcoming-payments` · `/payment-issues` · `/alerts` | Cobros y alertas |

## leads · 13 endpoints

| Endpoint | Qué hace |
|---|---|
| `GET`/`POST`/`PUT`/`DELETE /leads` | El CRM. Deduplica por correo y teléfono |
| `GET /leads/llamadas-pendientes` | **Los del Nivel 3 que esperan llamada**, con días de espera |
| `POST /leads/{id}/llamada-atendida` | Los saca del aviso |
| `POST`/`DELETE /leads/{id}/activity` | Notas del historial |
| `POST /leads/{id}/convert` | Lo convierte en cliente. **No pasa por Stripe** |
| `GET /leads/stats/summary` · `/metrics` | El embudo |
| `POST /leads/webhook/ghl` | **Entrada desde GoHighLevel.** Protegido por secreto |

## messages · 6 endpoints

| Endpoint | Qué hace |
|---|---|
| `POST /messages` | Envía. Resuelve el destinatario si no se indica |
| `GET /messages` | La conversación |
| `GET /messages/conversations` | La bandeja del equipo |
| `PUT /messages/read-all` · `/{id}/read` | Marcar leído |
| `GET /messages/unread-count` | El contador |

## admin · 34 endpoints

**Clientes**: `GET /admin/clients`, `GET /admin/clients/{id}` (la ficha entera),
`PUT /admin/clients/{id}`, `PUT /admin/clients/{id}/trainer`,
`GET /admin/clients/{id}/diet`, `GET /admin/clients/{id}/calma-foto`.

**Macros**: `PUT /admin/clients/{id}/macros` (guarda y versiona),
`POST /admin/clients/{id}/sugerir-ajuste` (**el agente de IA**),
`POST /admin/clients/{id}/calculator/apply`,
`PUT`/`DELETE /admin/clients/{id}/macro-history/{entry}`,
`PUT .../macro-history/{entry}/evaluacion` (**cómo salió la fase**),
`GET`/`POST /admin/macro-revisiones`, `POST /admin/macro-casos/reconstruir` (solo admin).

**Panel**: `GET /admin/dashboard-stats`, `/upcoming-payments`, `/todo-semana`,
`/dashboard` (heredado), `/trainers`.

**Alimentos**: `GET`/`PUT`/`DELETE /admin/food-suggestions/{id}`,
`POST .../approve`, `POST .../reject`, `POST /admin/foods`,
`PUT`/`DELETE /admin/foods/{id}`.

**Usuarios (solo admin)**: `GET /admin/users`, `PUT /admin/users/{id}`,
`POST /admin/users/{id}/reset-password`, `DELETE /admin/users/{id}`,
`POST /admin/users/{id}/restore`.

## menu_templates · 5 endpoints

`GET`/`POST`/`PUT`/`DELETE /admin/menu-templates` — las plantillas del recetario. El detalle
viene enriquecido con los macros por 100 g de cada alimento, como ayuda visual.

## notifications · 3 · audit · 1 · payments · 1

| Endpoint | Qué hace |
|---|---|
| `GET /notifications` | Sus avisos. **Evalúa y crea los automáticos al vuelo** |
| `PUT /notifications/read-all` | Marcar leídos |
| `GET /admin/audit` | El registro de actividad |
| `GET /payments` | Su historial de pagos |

---

## Reglas transversales

**Versionado por fecha.** Los macros se guardan con una fecha de vigencia. Cualquier
endpoint que necesite "los macros de tal día" busca la entrada más reciente anterior a esa
fecha. Por eso una dieta de hace un mes conserva los macros de entonces.

**Un solo motor de conteo.** Desde el 31-07-2026 todo cuenta por el mismo módulo. Antes
convivían dos y una comida podía sumar distinto según por dónde se preguntara.

**El orden de las rutas importa.** En el CRM, `/leads/llamadas-pendientes` va declarada
antes que `/leads/{id}`: si no, esta se tragaría "llamadas-pendientes" como si fuera un
identificador.

**Auditoría silenciosa.** El registro de actividad nunca rompe la operación principal: si
falla al escribir, se ignora.

**Acceso a recursos.** Que un endpoint acepte al equipo no basta: los que operan sobre un
cliente concreto comprueban además el acceso a ese cliente.
