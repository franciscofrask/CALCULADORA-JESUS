# JG12 - Plataforma de Entrenamiento Personal

## Implementado
- **Capa A Targets**: 404 combinaciones, auto-cálculo, override manual
- **Capa B CALMA v2**: Macros efectivos, calibraciones, 16 escenarios
- **Dashboard**: trackers circulares consumido vs objetivo, detección entreno/descanso
- **ProfilePage**: formulario datos corporales → auto-targets
- **RoutinePage**: grid 7 días, stats, ejercicios expandibles, cardio, historial
- **NutritionPage** (950 líneas, 7 componentes extraídos):
  - Calendario visual de dietas (completa/parcial/vacía)
  - Exportar dieta a PDF
  - Auto-detección tipo día desde rutina
  - Búsqueda con CALMA, sugerencias menú A/B/C
- Chatbot Claude 4.5, auth JWT, PDF export

## Credenciales
- Cliente: `clientedemo@test.com` / `demo123`
- Cliente test: `cliente@test.com` / `Cliente123`
- Admin: `alvaro@test.com` / `Alvaro123`
- Admin: `agutierrezp95@gmail.com` / `agutierrezp95@gmail.com`

## Pendiente
### P2
- Integración real Stripe
- Tracking Module con siluetas
- Simulador visual peso/BF → macros

## Integraciones
- Claude Sonnet 4.5 (Emergent LLM Key) | Stripe (MOCKED) | ReportLab (PDFs)
