# JG12 - Plataforma de Entrenamiento Personal

## Problema Original
Plataforma "JG12" con calculadora CALMA, chatbot IA, capa de targets, paneles multirol.

## Implementado
- Capa A Targets: 404 combinaciones, auto-cálculo, override manual
- Capa B CALMA v2: Macros efectivos, calibraciones, 16 escenarios distribución
- Dashboard: trackers circulares SVG consumido real vs objetivo, detección entreno/descanso
- ProfilePage: formulario datos corporales → auto-targets
- RoutinePage: grid 7 días, stats, ejercicios expandibles, cardio, historial
- NutritionPage: refactorizado a 950 líneas (7 componentes extraídos)
- Chatbot con Claude Sonnet 4.5, PDF export, auth JWT
- Flujo E2E verificado: búsqueda → añadir alimentos → guardar → dashboard refleja macros

## Bug Fixes (sesión actual)
- /api/calculator/search: corregido para devolver `alimentos` con `macros_efectivos` (CALMA)
- BuildMealModal.jsx: corregido `result.results` → `result.alimentos`

## Credenciales
- Cliente: `clientedemo@test.com` / `demo123` (hombre 80kg 20%BF volumen, rutina 5 días)
- Admin: `alvaro@test.com` / `Alvaro123`

## Pendiente
### P2
- Integración real Stripe
- Tracking Module con siluetas
- Simulador visual peso/BF → macros
- Ciclo de semanas automático

## Integraciones
- Claude Sonnet 4.5 (Emergent LLM Key) | Stripe (MOCKED) | ReportLab (PDFs)
