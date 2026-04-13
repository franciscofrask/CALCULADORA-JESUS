# JG12 - Plataforma de Entrenamiento Personal

## Problema Original
Crear una plataforma de entrenamiento personal llamada "JG12" con múltiples paneles y funcionalidades avanzadas. La característica principal es una calculadora de macros y dietas altamente detallada llamada "CALMA", junto con un Chatbot conversacional que ayuda al cliente a montar su dieta del día usando Claude Sonnet 4.5.

## Requisitos del Producto
- 4 Paneles: Cliente, Operaciones, CEO y Entrenadores
- Calculadora de nutrición avanzada "CALMA"
- **Capa de Targets**: Cálculo automático de macros desde datos antropométricos
- Generación de 3 opciones de menú (A/B/C)
- **Chatbot conversacional con Claude** para montar dietas en lenguaje natural
- Branding "JG12" (modo oscuro, acentos naranjas)
- Integración de pagos con Stripe (actualmente MOCKED)

## Arquitectura del Código
```
/app/
├── backend/
│   ├── server.py              # Entrypoint (~90 líneas)
│   ├── core/                  # config.py, database.py, security.py
│   ├── models/                # user.py (body_fat, macros_periworkout, macros_source), diet.py, common.py
│   ├── routes/
│   │   ├── calculator.py      # /targets, /targets/apply, /distribute, /test-targets
│   │   ├── chatbot.py, diets.py, auth.py, users.py, admin.py
│   │   └── routines.py, reports.py, messages.py, payments.py
│   ├── target_calculator.py   # Motor de cálculo de targets (Capa A) + macros_tables.json
│   ├── calma_engine.py        # Motor CALMA v2 (Capa B)
│   ├── macro_distribution.py  # Distribución por comidas (16 escenarios)
│   ├── meal_builder.py        # Algoritmo de distribución de alimentos
│   ├── pdf_generator.py       # PDFs con reportlab
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── ClientDashboard.jsx  # Trackers circulares SVG
│   │   │   ├── ProfilePage.jsx      # Formulario datos corporales + targets
│   │   │   ├── NutritionPage.jsx    # ~1650 líneas (reducido de 1741)
│   │   │   └── ChatbotPage.jsx, AuthPage.jsx, ...
│   │   ├── components/
│   │   │   ├── nutrition/
│   │   │   │   ├── BuildMealModal.jsx
│   │   │   │   ├── RepeatMealModal.jsx    # Extraído de NutritionPage
│   │   │   │   ├── CopyDietModal.jsx      # Extraído de NutritionPage
│   │   │   │   └── ...
│   │   │   └── ui/
│   │   └── context/AuthContext.jsx
└── memory/
```

## Lo que está implementado

### Capa A: Motor de Targets (11/04/2026)
- 404 combinaciones del Excel de Jesús
- Endpoints: /targets, /targets/apply, /test-targets (22/22 tests)
- Auto-calcula al actualizar perfil, override manual del entrenador

### Frontend: Datos Corporales + Trackers (13/04/2026)
- **ProfilePage**: Formulario peso/sexo/%graso/objetivo → "Calcular mis macros"
- **ClientDashboard**: Trackers circulares SVG (P/H/G) con kcal
- **NutritionPage**: Modales RepeatMealModal y CopyDietModal extraídos
- **Distribute endpoint**: Migrado a routes/calculator.py

### Capa B: Motor CALMA v2
- Reglas de la Biblia de Alimentos v2, calibraciones, ±4g margen

### Backend completo
- Auth JWT, búsqueda alimentos, chatbot Claude 4.5, PDF, distribución macros

## Credenciales de Test
- **Cliente:** `clientedemo@test.com` / `demo123`
- **Admin:** `alvaro@test.com` / `Alvaro123`

## Tareas Pendientes

### P1 - Próximas
- Continuar reduciendo NutritionPage (1650 líneas aún)
- Pantalla Home con trackers de progreso diario (hoy se muestra target, falta progreso real del día)
- Pantalla "Mi Rutina" rediseñada

### P2 - Futuras
- Integración real de Stripe (actualmente MOCKED)
- Tracking Module con siluetas de evolución
- Badge "Made with Emergent" superpone menú móvil
- Ciclo de semanas automático
- Simulador visual de "qué pasa si bajo de peso"

## Integraciones
- **Claude Sonnet 4.5** — Emergent LLM Key (chatbot + rutinas)
- **Stripe** — MOCKED
- **ReportLab** — PDFs
