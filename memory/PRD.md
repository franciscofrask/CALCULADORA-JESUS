# JG12 - Plataforma de Entrenamiento Personal

## Problema Original
Plataforma de entrenamiento personal "JG12" con calculadora de macros CALMA, chatbot con IA, capa de targets automática y paneles multirol.

## Arquitectura
```
/app/
├── backend/
│   ├── server.py, core/, models/, routes/
│   ├── target_calculator.py + macros_tables.json  (Capa A: Targets)
│   ├── calma_engine.py                            (Capa B: Macros efectivos)
│   ├── macro_distribution.py                      (Distribución por comidas)
│   ├── meal_builder.py, chatbot.py, pdf_generator.py
│   └── tests/
├── frontend/src/
│   ├── pages/ (ClientDashboard, ProfilePage, NutritionPage, RoutinePage, ChatbotPage, ...)
│   ├── components/nutrition/ (BuildMealModal, RepeatMealModal, CopyDietModal, ...)
│   └── context/AuthContext.jsx
```

## Implementado
- Capa A Targets: 404 combinaciones Excel Jesús, auto-cálculo, override manual
- Capa B CALMA v2: Macros efectivos por categoría, calibraciones
- Distribución por comidas: 16 escenarios E1-E4
- Chatbot IA con Claude Sonnet 4.5
- Dashboard con trackers circulares SVG (consumido real vs objetivo)
- ProfilePage con formulario datos corporales → targets/apply
- RoutinePage rediseñada (grid días, stats, ejercicios expandibles)
- NutritionPage modularizada (RepeatMealModal, CopyDietModal extraídos)
- PDF export, búsqueda alimentos, auth JWT

## Credenciales
- Cliente: `clientedemo@test.com` / `demo123`
- Admin: `alvaro@test.com` / `Alvaro123`

## Pendiente
### P1
- Seguir reduciendo NutritionPage (~1650 líneas)
- Asignar rutina demo para probar RoutinePage con datos

### P2
- Integración real Stripe
- Tracking Module con siluetas
- Simulador visual peso/BF → macros
- Ciclo de semanas automático

## Integraciones
- Claude Sonnet 4.5 (Emergent LLM Key)
- Stripe (MOCKED)
- ReportLab (PDFs)
