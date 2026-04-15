# JG12 - Plataforma de Entrenamiento Personal

## Problema Original
Plataforma "JG12" con calculadora CALMA, chatbot IA, capa de targets, paneles multirol.

## Arquitectura
```
/app/backend/
  server.py, core/, models/, routes/ (auth, admin, calculator, chatbot, diets, messages, payments, reports, routines, users)
  target_calculator.py + macros_tables.json (Capa A)
  calma_engine.py (Capa B), macro_distribution.py, meal_builder.py, chatbot.py, pdf_generator.py
/app/frontend/src/
  pages/ (ClientDashboard, ProfilePage, NutritionPage[950 lines], RoutinePage, ChatbotPage, AuthPage, ...)
  components/nutrition/ (BuildMealModal, MealCard, DaySummary, ConfigSection, SearchFoodModal, MenuOptionsModal, RepeatMealModal, CopyDietModal, PreferencesSetup)
  components/ui/ (shadcn), context/AuthContext.jsx
```

## Implementado
- Capa A Targets: 404 combinaciones, auto-cálculo, override manual
- Capa B CALMA v2: Macros efectivos, calibraciones
- 16 escenarios distribución, PDF export, chatbot Claude 4.5
- Dashboard: trackers circulares SVG consumido vs objetivo, detección día entreno/descanso
- ProfilePage: formulario datos corporales → auto-targets
- RoutinePage: grid 7 días, stats, ejercicios expandibles, cardio, historial
- NutritionPage: refactorizado a 950 líneas (7 componentes extraídos)

## Credenciales
- Cliente: `clientedemo@test.com` / `demo123` (hombre 80kg 20%BF volumen, rutina 5 días)
- Admin: `alvaro@test.com` / `Alvaro123`

## Pendiente
### P1
- Probar flujo E2E completo: añadir alimentos → guardar dieta → ver progreso en dashboard

### P2
- Integración real Stripe
- Tracking Module con siluetas
- Simulador visual peso/BF → macros
- Ciclo de semanas automático

## Integraciones
- Claude Sonnet 4.5 (Emergent LLM Key) | Stripe (MOCKED) | ReportLab (PDFs)
