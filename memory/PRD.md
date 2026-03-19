# JG12 - Plataforma de Entrenamiento Personal

## Problema Original
Crear una plataforma de entrenamiento personal llamada "JG12" con múltiples paneles y funcionalidades avanzadas. La característica principal es una calculadora de macros y dietas altamente detallada llamada "CALMA".

## Requisitos del Producto
- 4 Paneles: Cliente, Operaciones, CEO y Entrenadores
- Calculadora de nutrición avanzada "CALMA"
- Generación de 3 opciones de menú (A/B/C)
- Branding "JG12" (modo oscuro, acentos naranjas)
- Integración de IA (Claude Sonnet 4.5) para generación de rutinas (futuro)
- Integración de pagos con Stripe (actualmente simulada)

## Arquitectura del Código
```
/app/
├── backend/
│   ├── server.py              # API principal FastAPI
│   ├── calculator.py          # Lógica de búsqueda, sugerencias y get_food_config()
│   ├── calma_engine.py        # Motor de cálculo de macros
│   └── meal_templates.py      # Generación de opciones de menú
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── AuthPage.jsx   # Login con ojo y copyright
│   │   │   └── NutritionPage.jsx # Página principal de nutrición (GRANDE - necesita refactor)
│   │   ├── components/
│   │   │   ├── nutrition/
│   │   │   │   └── PreferencesSetup.jsx # Configuración de preferencias
│   │   │   └── BottomNav.jsx
│   │   └── layouts/
│   │       └── ClientDashboard.jsx
│   └── tailwind.config.js
└── memory/
    └── PRD.md
```

## Lo que está implementado

### Backend (FastAPI + MongoDB)
- ✅ Autenticación JWT
- ✅ Calculadora CALMA v2 completa
- ✅ Búsqueda de alimentos con normalización de acentos
- ✅ Endpoints de dietas: save, load, recent
- ✅ Endpoint `/api/user/preferences` para preferencias de alimentos
- ✅ Endpoint `/api/calculator/foods-sorted` con lógica de categoría principal y config
- ✅ Función `get_food_config()` con incrementos y mínimos correctos

### Frontend (React + Tailwind + Shadcn)
- ✅ Login con botón mostrar/ocultar contraseña
- ✅ Dashboard del cliente
- ✅ Página de Nutrición completa:
  - Configuración del día (comidas, entreno, periworkout)
  - Resumen diario sticky con barras de progreso
  - Sistema de comidas en acordeón
  - Modal "Sugiéreme un menú" (opciones A/B/C)
  - Modal "Lo hago yo" (constructor de comidas en pasos)
  - Modal "Repetir de otro día"
  - Edición de ingredientes (+/- cantidad, eliminar)
  - Guardado/carga de dietas por fecha
- ✅ Pantalla de preferencias de alimentos obligatoria (primera vez)

## Credenciales de Prueba
- **Cliente:** `clientedemo@test.com` / `demo123`

## Última Sesión (Marzo 2026)

### Bugs Corregidos
1. **BUG 1 - MAX_FOODS not defined:** Eliminadas referencias a MAX_FOODS
2. **BUG 2 - Preferencias no aparecen:** Pantalla de configuración funciona correctamente
3. **BUG 3 - Incrementos incorrectos:** Creada `get_food_config()` con lógica correcta:
   - Incremento = 1g para peso (excepto verduras 50g, bebidas vegetales 50g, salsas zero 5g)
   - Mínimos según categoría (embutidos 25g, verduras 50g, etc.)

## Problemas Conocidos
- 🔴 Badge "Made with Emergent" tapa BottomNav en móvil

## Backlog Priorizado

### P0 - Crítico
- ✅ COMPLETADO - Bugs 1, 2 y 3 corregidos

### P1 - Alta Prioridad
- [ ] Arreglar badge de Emergent en móvil
- [ ] Implementar pantalla de inicio (Home) con macros circulares
- [ ] Implementar pantalla "Mi Rutina"
- [ ] Añadir calendario visual en Nutrición

### P2 - Media Prioridad
- [ ] Refactorizar `NutritionPage.jsx` (>2300 líneas)
- [ ] Refactorizar `server.py` en APIRouters
- [ ] Módulo de Tracking/Seguimiento
- [ ] Integración real con Stripe

### P3 - Baja Prioridad
- [ ] Integración Claude Sonnet 4.5 para rutinas
- [ ] Panel de operaciones
- [ ] Panel de CEO
- [ ] Panel de entrenadores

## Integraciones de Terceros
- **Claude Sonnet 4.5** — Emergent LLM Key (planeado, no implementado)
- **Stripe** — Simulado (pendiente integración real)

## Notas Técnicas
- El archivo `NutritionPage.jsx` es un monolito de >2300 líneas que necesita urgente refactorización
- Las preferencias de usuario se guardan en `client_profiles.food_preferences`
- El `_config` con `minimo`/`incremento` se calcula en el backend y se pasa al frontend
