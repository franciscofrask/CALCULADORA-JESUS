# JG12 - Plataforma de Entrenamiento Personal

## Implementado
- Capa A Targets: 404 combinaciones, auto-cálculo, override manual
- Capa B CALMA v2: Macros efectivos, calibraciones, 16 escenarios
- Dashboard: trackers circulares consumido vs objetivo, detección entreno/descanso
- ProfilePage: formulario datos corporales → auto-targets
- RoutinePage: grid 7 días, stats, ejercicios expandibles, cardio, historial
- NutritionPage: calendario visual, PDF export, auto-detección día, búsqueda frecuencia+favoritos
- BuildMealModal: flujo guiado (P→H→G), bloqueo macro cubierto, favoritos con estrella
- SearchFoodModal: favoritos con estrella, ordenación favoritos>frecuencia>alfabético
- Chatbot Claude 4.5, auth JWT, PDF export, 3110 alimentos

## Credenciales
- Cliente: `clientedemo@test.com` / `demo123`
- Cliente test: `cliente@test.com` / `Cliente123`
- Admin: `alvaro@test.com` / `Alvaro123`
- Admin: `agutierrezp95@gmail.com` / `agutierrezp95@gmail.com`

## Pendiente
### P2
- Integración real Stripe
- Tracking Module
- Simulador visual peso/BF

## Integraciones
- Claude Sonnet 4.5 (Emergent LLM Key) | Stripe (MOCKED) | ReportLab (PDFs)

## Colecciones MongoDB (11)
- foods (3110), food_categories (232), users (11), diets (6), payments (6)
- client_profiles (4), macro_history (2), messages (2), reports (2), routines (1)
- food_favorites (NEW)
