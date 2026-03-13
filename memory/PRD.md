# JG12↗ - Plataforma Jesús Gallego Trainer

## Documento de Requisitos del Producto (PRD)

### Fecha de creación: 6 de marzo de 2026
### Última actualización: 13 de marzo de 2026
### Estado: MVP Completado + CALMA v2 + Config Día (F1.1/F1.2) + Constructor (F1.3) + Edición/Repetir (F1.4)

---

## 1. Descripción General

**JG12↗** es una plataforma de gestión de entrenamiento personal online para Jesús Gallego Personal Trainer. Permite la gestión integral de clientes, rutinas, nutrición avanzada (CALMA), reportes y comunicación entre entrenadores y clientes.

---

## 2. User Personas

### Cliente
- Usuarios que contratan servicios de entrenamiento personal online
- Acceden a su rutina, macros, reportes y chat con entrenador
- Planes: Gold (149€), Silver (99€), Bronze (69€), ELM (39€)

### Operaciones/Admin
- Staff que gestiona clientes, pagos, rutinas y comunicaciones
- Acceso a dashboard de métricas y generador de rutinas con IA

### Entrenador
- Profesionales que diseñan rutinas y nutrición personalizada
- Interactúan con clientes via chat

---

## 3. Core Requirements

### Portal Cliente
- [x] Login/Registro con email y contraseña (JWT)
- [x] Home Dashboard con progreso del ciclo
- [x] Mi Rutina - Visualización de ejercicios por día
- [x] **Mi Nutrición - Calculadora CALMA v2 completa**
- [x] Mis Reportes - Formularios de seguimiento con evolución
- [x] Mensajes - Chat con entrenador
- [x] Mi Perfil - Datos personales y plan

### Panel Operaciones
- [x] Dashboard con métricas (MRR, clientes, pagos)
- [x] Listado de clientes con filtros
- [x] Ficha única de cliente (tabs múltiples)
- [x] Generador de rutinas con IA (Claude Sonnet 4.5)
- [x] Gestión de macros por cliente

---

## 4. CALMA v2 - Sistema de Nutrición Avanzado

### Motor de Macros Efectivos (calma_engine.py)
- Cálculo de "macros que cuentan" según categoría del alimento
- Reglas específicas por tipo: carnes (solo P), cereales (solo H), etc.
- Sistema de excepción para categoría 28 (YA) y 52 (vegano)
- 3110 alimentos en base de datos con 232 categorías

### Distribución de Macros (macro_distribution.py)
- 16 escenarios de distribución según:
  - Tipo de día (entrenamiento/descanso)
  - Número de comidas (3/4)
  - Momento de entreno (ayunas/después C1/C2/C3)
  - Opción periworkout (intra+post/solo post/solo intra/sin peri)

### Calculadora Interactiva (calculator.py)
- Ajuste automático de cantidad de alimentos
- Validación de comidas (cuadrada/falta/sobra)
- Sugerencias de alimentos según macros restantes

### Frontend NutritionPage.jsx
- [x] Calendario con navegación por fechas
- [x] Toggle tipo de día (Entreno/Descanso)
- [x] Acordeón de comidas con progress bars P/H/G
- [x] Modal de búsqueda de alimentos con filtros
- [x] Ajuste de cantidades (+/- 10g)
- [x] Guardado y carga de dietas
- [x] Copia de dietas entre fechas
- [x] **TAREA E12: Buscador mejorado con:**
  - Normalización de acentos (buscar "atun" → "Atún")
  - Macros efectivos CALMA en resultados
  - 23 categorías completas en chips
  - Ración correcta por alimento
  - Badges ocultos si macro = 0
- [x] **TAREA F1.1 + F1.2: Configuración del día y resumen sticky:**
  - Selector de número de comidas [3] [4]
  - Selector "¿Cuándo entrenas?" (En ayunas, Después de C1/C2/C3)
  - Selector periworkout (Intra+Post, Solo Post, Solo Intra, Sin periworkout)
  - Resumen sticky con barras de progreso P/H/G
  - Mini-estado de comidas (⚪ vacía, 🟡 falta, 🟢 cuadrada, 🔴 sobra)
  - Tabla expandible con desglose por comida
  - Barras de progreso dentro de cada comida
  - Estado dinámico de comidas (Cuadrada/Faltan/Sobran)
- [x] **TAREA F1.3: Constructor "Lo hago yo" en 2 pasos:**
  - Modal fullscreen con flujo guiado
  - PASO 1: Elegir proteína (categorías Carnes/Pescados/Huevos/Lácteos/Proteína/Vegetal/Soja)
  - PASO 2: Elegir acompañamiento (auto-avance cuando P>=80%)
  - Sugerencias automáticas ordenadas por mejor encaje
  - Buscador con filtro "Solo genéricos" (tag=GEN)
  - Micro-sugerencia de grasas cuando solo faltan G
  - Máximo 5 alimentos por comida
  - Banner "¡COMIDA CUADRADA!" cuando ±4g en todos los macros
- [x] **TAREA F1.4: Edición de ingredientes + Guardar día + Repetir:**
  - Botones [-] [+] con incrementos por categoría (carne ±25g, aceite ±1g, huevos ±55g, etc.)
  - Click en cantidad abre input editable para cantidad exacta
  - Macros del ingrediente recalculados en tiempo real
  - Botón "🗑️ Vaciar comida" con confirmación
  - Máximo 5 alimentos por comida (3 para peri)
  - Modal "Repetir de otro día" con lista de días recientes
  - Copiar comidas con escalado proporcional (basado en P)
  - Endpoint GET /api/diets/recent

---

## 5. Implementación Completada

### Backend (FastAPI + MongoDB)
- Autenticación JWT completa
- CRUD de usuarios, perfiles, rutinas, reportes
- Sistema de mensajería
- **Motor CALMA v2 completo con endpoints:**
  - `/api/calculator/search` - Búsqueda de alimentos (con normalización acentos, macros efectivos)
  - `/api/calculator/distribute` - Distribución de macros
  - `/api/calculator/adjust` - Ajuste automático
  - `/api/calculator/macros-efectivos` - Cálculo individual
  - `/api/calculator/validate-meal` - Validación de comidas
  - `/api/calculator/menu-options` - Generación de menús A/B/C
  - `/api/calculator/suggest` - Sugerencias de alimentos con parámetro "paso"
  - `/api/diets` - CRUD de dietas diarias
- Integración Claude Sonnet 4.5 para generación de rutinas
- Pagos simulados (mockeados)

### Frontend (React + Tailwind + Shadcn)
- 18+ pantallas implementadas
- Diseño responsive mobile-first
- **NutritionPage completamente funcional**
- Badges de planes (Gold, Silver, Bronze, ELM)
- Charts de evolución con Recharts
- Sistema de notificaciones con Sonner

### Integraciones
- Claude Sonnet 4.5 via emergentintegrations (Emergent LLM Key)

---

## 6. Backlog Priorizado

### P0 (Crítico)
- [ ] Integración real de Stripe para pagos
- [ ] Sistema de recordatorios automáticos (semana 3 = reporte)

### P1 (Alta prioridad)
- [ ] Home Screen Redesign (Pantalla 10) con trackers circulares
- [ ] Pantalla "Mi Rutina" (Pantalla 30) con estados de color
- [ ] Módulo de Seguimiento (Pantalla 47) siluetas de evolución
- [ ] Módulo de Suplementos (Pantallas 34-39)
- [ ] Subida de fotos en reportes
- [ ] Videos de ejercicios embebidos

### P2 (Media prioridad)
- [ ] Enhanced Onboarding (Pantallas 6, 8, 9)
- [ ] Panel de Estadísticas (Pantalla 50)
- [ ] Navegación inferior en portal cliente
- [ ] Exportación de rutinas a PDF

### P3 (Futuro)
- [ ] App móvil nativa
- [ ] Notificaciones push/email
- [ ] Gamificación (badges, streaks)

---

## 7. Stack Técnico

- **Frontend**: React 18, Tailwind CSS, Shadcn UI, Recharts
- **Backend**: FastAPI, Motor (MongoDB async)
- **Base de datos**: MongoDB
- **IA**: Claude Sonnet 4.5 (emergentintegrations)
- **Pagos**: Stripe (pendiente - actualmente MOCKEADO)

### Branding JG12
- **Color Primario**: #FF671F (Naranja)
- **Color Secundario**: #000000 (Negro)
- **Fuente Principal**: Bebas Neue (headings)
- **Fuente Secundaria**: Inter (body)
- **Logo**: JG12↗ con flecha naranja

---

## 8. URLs y Credenciales de Test

### Credenciales Admin
- Email: admin@12en12.com
- Password: admin123

### Credenciales Cliente Test
- Email: clientedemo@test.com  
- Password: demo123

---

## 9. Notas de Implementación

- Pagos están **MOCKEADOS** - todos retornan success
- La generación de rutinas con IA puede tardar 5-10 segundos
- El sistema usa ciclos de 4 semanas
- Los planes Gold incluyen cardio personalizado
- **CALMA v2 está 100% funcional** - motor backend y frontend completos

---

## 10. Archivos Clave

- `/app/backend/calma_engine.py` - Motor de macros efectivos
- `/app/backend/macro_distribution.py` - Distribución por comidas
- `/app/backend/calculator.py` - Lógica de ajuste y validación
- `/app/backend/server.py` - Todos los endpoints API
- `/app/frontend/src/pages/NutritionPage.jsx` - UI de calculadora
