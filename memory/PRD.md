# JG12 - Plataforma de Entrenamiento Personal

## Implementado
- Capa A Targets + Capa B CALMA v2 + 16 escenarios distribución
- Dashboard cliente: trackers circulares consumido vs objetivo
- ProfilePage: datos corporales → auto-targets
- RoutinePage: grid 7 días, stats, ejercicios expandibles
- NutritionPage: calendario, PDF, auto-detección, favoritos, bloqueo macros, flujo guiado
- AdminDashboard: 5 KPIs, distribución plan, próximos cobros
- ClientDetailPage: 8 pestañas (Resumen, Macros, Membresía, Reportes, Cuestionario, Entrenamiento, Nutrición, Seguimiento)
- LeadsPage: Kanban + Tabla, CRUD leads, webhook GoHighLevel, conversión automática a cliente
- Chatbot Claude 4.5, auth JWT, 3110 alimentos, 12 colecciones MongoDB

## Credenciales
- Cliente: `clientedemo@test.com` / `demo123`
- Cliente test: `cliente@test.com` / `Cliente123`
- Cliente convertido: `maria@gmail.com` / `maria@gmail.com` (gold)
- Admin: `alvaro@test.com` / `Alvaro123`
- Admin: `agutierrezp95@gmail.com` / `agutierrezp95@gmail.com`

## Webhook GHL
- URL: `POST {APP_URL}/api/leads/webhook/ghl`
- Body: `{"full_name":"...", "email":"...", "phone":"..."}`
- Sin autenticación requerida

## Pendiente
- Integración real Stripe | Tracking Module | Simulador peso/BF

## Integraciones
- Claude Sonnet 4.5 (Emergent LLM Key) | Stripe (MOCKED) | ReportLab (PDFs) | GoHighLevel webhook
