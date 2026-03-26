# JG12 - Plataforma de Entrenamiento Personal

## Problema Original
Crear una plataforma de entrenamiento personal llamada "JG12" con múltiples paneles y funcionalidades avanzadas. La característica principal es una calculadora de macros y dietas altamente detallada llamada "CALMA", junto con un Chatbot conversacional que ayuda al cliente a montar su dieta del día usando Claude Sonnet 4.5.

## Requisitos del Producto
- 4 Paneles: Cliente, Operaciones, CEO y Entrenadores
- Calculadora de nutrición avanzada "CALMA"
- Generación de 3 opciones de menú (A/B/C)
- **Chatbot conversacional con Claude** para montar dietas en lenguaje natural
- Branding "JG12" (modo oscuro, acentos naranjas)
- Integración de pagos con Stripe (actualmente MOCKED)

## Arquitectura del Código
```
/app/
├── backend/
│   ├── server.py              # API principal FastAPI
│   ├── chatbot.py             # Chatbot con Claude Sonnet 4.5 + distribución inteligente
│   ├── calculator.py          # Lógica de búsqueda, get_food_config()
│   ├── calma_engine.py        # Motor de cálculo de macros (57 tests)
│   ├── macro_distribution.py  # Distribución de macros (16 escenarios)
│   ├── tests/
│   │   └── test_calma_engine.py  # 57 tests de verificación
│   └── meal_templates.py      # Generación de opciones de menú
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── NutritionPage.jsx   # Página manual de nutrición
│   │   │   ├── ChatbotPage.jsx     # UI del chatbot
│   │   │   └── AuthPage.jsx        # Login
│   │   ├── components/
│   │   │   └── BottomNav.jsx
│   │   └── layouts/
│   │       └── ClientDashboard.jsx
│   └── tailwind.config.js
└── memory/
    └── PRD.md
```

## Lo que está implementado

### Motor CALMA v2 (57/57 tests)
- Reglas estrictas de la "Biblia de Alimentos v2"
- Calibración progresiva cereales/panes y frutos secos
- Regla doble categoría
- Márgenes: ±4g general, ±2g intra

### Backend (FastAPI + MongoDB)
- Autenticación JWT
- Motor CALMA completo
- Búsqueda de alimentos con normalización de acentos
- **Chatbot con Claude Sonnet 4.5** (emergentintegrations)
  - Endpoint: `POST /api/chatbot/start`
  - Endpoint: `POST /api/chatbot/configure`
  - Endpoint: `POST /api/chatbot/message`
  - Endpoint: `POST /api/chatbot/complete-meal`
  - Endpoint: `POST /api/chatbot/reset`
- Endpoints de dietas: save, load, recent

### Chatbot - Funcionalidades (actualizado 26/03/2026)
- Configuración del día (entrenamiento/descanso)
- Búsqueda de alimentos con normalización de acentos
- **Límites máximos razonables** por categoría
- **Alimentos por unidad** se muestran correctamente
- **DISTRIBUCIÓN INTELIGENTE DE MACROS:**
  - Reparte la proteína entre TODAS las fuentes de P equitativamente
  - Considera la P secundaria de alimentos mixtos (ej: garbanzos)
  - Las fuentes con límites bajos (huevos) se procesan primero
  - Las demás fuentes compensan para llegar al objetivo
  - Casos de prueba verificados:
    - "huevos, pan, claras y pavo" → P=40g/40g, H=15g/15g
    - "pechuga, garbanzos, aguacate, calabacín" → P=40g/40g, H=15g/15g, G=8g/8g

### Frontend (React + Tailwind + Shadcn)
- Login con mostrar/ocultar contraseña
- Dashboard del cliente
- Página de Nutrición manual completa
- **Página de Chatbot** (`/dashboard/chatbot`)
  - UI conversacional funcionando
  - Botones de configuración del día
  - Input de chat con Enter para enviar
  - Badge de Emergent no tapa botones

## Credenciales de Test
- **Cliente:** `clientedemo@test.com` / `demo123`

## Tareas Completadas Esta Sesión (26/03/2026)
- Arreglado: Chatbot mostraba pantalla en blanco (error de estados frontend)
- Arreglado: Chatbot asignaba cantidades absurdas (266g de claras)
- Arreglado: Huevos no se mostraban en unidades
- Arreglado: Búsqueda no encontraba alimentos con tildes (calabacín)
- Arreglado: Badge de Emergent tapaba botón de enviar
- **IMPLEMENTADO: Distribución inteligente de macros entre alimentos**
  - Ya no asigna toda la P al primer alimento
  - Reparte equitativamente entre fuentes de P
  - Considera P secundaria de alimentos mixtos (legumbres)
  - Compensación automática cuando una fuente tiene límite

## Tareas Pendientes

### P1 - Próximas
- Resumen del día cuando todas las comidas estén montadas
- Refactor de NutritionPage.jsx en componentes pequeños
- Refactor de server.py en APIRouters

### P2 - Futuras
- Implementar pantalla Home con trackers circulares
- Implementar pantalla "Mi Rutina"
- Calendario visual de días
- Integración real de Stripe (actualmente MOCKED)

## Integraciones de Terceros
- **Claude Sonnet 4.5** — Usa Emergent LLM Key (implementado en chatbot.py)
- **Stripe** — MOCKED (pendiente integración real)
