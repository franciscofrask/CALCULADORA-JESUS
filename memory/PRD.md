# JG12 - Plataforma de Entrenamiento Personal

## Problema Original
Crear una plataforma de entrenamiento personal llamada "JG12" con múltiples paneles y funcionalidades avanzadas. La característica principal es una calculadora de macros y dietas altamente detallada llamada "CALMA", junto con un Chatbot conversacional que ayuda al cliente a montar su dieta del día usando Claude Sonnet 4.5.

## Requisitos del Producto
- 4 Paneles: Cliente, Operaciones, CEO y Entrenadores
- Calculadora de nutrición avanzada "CALMA"
- **Capa de Targets**: Cálculo automático de macros objetivo desde datos antropométricos
- Generación de 3 opciones de menú (A/B/C)
- **Chatbot conversacional con Claude** para montar dietas en lenguaje natural
- Branding "JG12" (modo oscuro, acentos naranjas)
- Integración de pagos con Stripe (actualmente MOCKED)

## Arquitectura del Código
```
/app/
├── backend/
│   ├── server.py              # API principal (~90 líneas, refactorizado)
│   ├── core/                  # Módulos base
│   │   ├── config.py          # Configuración
│   │   ├── database.py        # MongoDB
│   │   └── security.py        # JWT, auth
│   ├── models/                # Pydantic models
│   │   ├── user.py            # Incluye body_fat, macros_periworkout, macros_source
│   │   ├── diet.py
│   │   └── common.py
│   ├── routes/                # API routers (~10 archivos)
│   │   ├── auth.py, users.py, admin.py
│   │   ├── calculator.py      # Incluye /targets, /targets/apply, /test-targets
│   │   ├── diets.py, chatbot.py
│   │   └── routines.py, reports.py, messages.py, payments.py
│   ├── target_calculator.py   # NUEVO: Motor de cálculo de targets (Capa A)
│   ├── macros_tables.json     # NUEVO: 404 combinaciones del Excel de Jesús
│   ├── chatbot.py             # Lógica del chatbot
│   ├── calculator.py          # Lógica de búsqueda
│   ├── calma_engine.py        # Motor de cálculo de macros (Capa B)
│   ├── meal_builder.py        # Algoritmo de distribución
│   ├── macro_distribution.py  # Distribución por comidas
│   ├── pdf_generator.py       # Generación de PDFs
│   └── tests/
│       ├── test_target_calculator.py  # Tests E2E del motor de targets
│       └── ...
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── NutritionPage.jsx   # Página de nutrición (aún grande ~1740 líneas)
│   │   │   ├── ChatbotPage.jsx     # UI del chatbot + PDF
│   │   │   └── AuthPage.jsx        # Login
│   │   ├── components/
│   │   │   ├── nutrition/          # Componentes extraídos
│   │   │   └── ui/
│   │   └── context/
│   └── tailwind.config.js
└── memory/
    ├── PRD.md
    ├── LOGICA_NEGOCIO.md
    └── test_credentials.md
```

## Lo que está implementado

### Capa A: Motor de Targets (NUEVO - 11/04/2026)
- **Motor `target_calculator.py`**: Calcula macros objetivo del cliente
- Inputs: peso, sexo, % graso, objetivo (volumen/definición)
- Fórmulas: masa_grasa, masa_magra, masa_trabajo = masa_magra / 0.85
- Lookup en tabla discreta de 404 combinaciones (macros_tables.json)
- Redondeo al escalón más cercano (peso cada 5kg, BF cada 5%)
- Clamping a extremos fuera de rango
- Endpoints: POST /api/calculator/targets, POST /api/calculator/targets/apply
- Auto-calcula macros al actualizar perfil del cliente
- Soporta override manual del entrenador (macros_source: "auto" vs "manual")
- 22 tests internos + 18 tests API (100% pass)

### Capa B: Motor CALMA v2 (calma_engine.py)
- Reglas estrictas de la "Biblia de Alimentos v2"
- Calibración progresiva cereales/panes y frutos secos
- Márgenes: ±4g general, ±2g intra

### Backend (FastAPI + MongoDB)
- Autenticación JWT
- Motor CALMA completo
- Búsqueda de alimentos con normalización de acentos
- **Chatbot con Claude Sonnet 4.5** (emergentintegrations)
- Endpoints de dietas: save, load, recent, calendar, copy
- Generación de PDF (reportlab)
- Distribución de macros por comidas (16 escenarios)

### Frontend (React + Tailwind + Shadcn)
- Login con mostrar/ocultar contraseña
- Dashboard del cliente
- Página de Nutrición manual completa
- Página de Chatbot con IA

## Credenciales de Test
- **Cliente:** `clientedemo@test.com` / `demo123`
- **Admin:** `alvaro@test.com` / `Alvaro123`

## Tareas Completadas

### Sesión 11/04/2026 - Capa de Targets
- **IMPLEMENTADO: Motor de cálculo de targets (`target_calculator.py`)**
  - Carga 404 combinaciones desde macros_tables.json
  - Calcula masa_trabajo = masa_magra / 0.85
  - Lookup por (sexo, peso, bf, objetivo) con snapping
  - Genera multiplicadores para override del coach
  - 22/22 tests internos pasan
- **IMPLEMENTADO: Endpoints de targets**
  - POST /api/calculator/targets — calcula sin guardar
  - POST /api/calculator/targets/apply — calcula y guarda en perfil
  - GET /api/calculator/test-targets — ejecuta tests internos
- **INTEGRADO: Auto-cálculo al actualizar perfil**
  - PUT /clients/profile detecta cambios en peso/sexo/bf/objetivo
  - Recalcula macros automáticamente (salvo override manual)
- **INTEGRADO: Chatbot lee macros auto-calculados**
  - Formato dual: protein/carbs/fat + proteinas/hidratos/grasas
  - Incluye periworkout calculado
- **ACTUALIZADO: Modelo ClientProfile**
  - Nuevos campos: body_fat, macros_periworkout, macros_source, macros_multiplicadores

### Sesiones anteriores
- Refactorización Backend: server.py dividido en módulos
- Refactorización Frontend: Extracción de BuildMealModal
- PDF export implementado
- Login fix (DB_NAME)
- Búsqueda de alimentos arreglada

## Tareas Pendientes

### P1 - Próximas
- Extraer `RepeatDayModal` y otros componentes de NutritionPage.jsx
- Implementar pantalla Home con trackers circulares
- Implementar pantalla "Mi Rutina"

### P2 - Futuras
- Integración real de Stripe (actualmente MOCKED)
- Tracking Module con siluetas
- Badge "Made with Emergent" superpone menú móvil
- Ciclo de semanas (incrementar week automáticamente)
- Renovación automática de pagos

## Integraciones de Terceros
- **Claude Sonnet 4.5** — Usa Emergent LLM Key (chatbot + rutinas)
- **Stripe** — MOCKED (pendiente integración real)
- **ReportLab** — Para generación de PDFs
