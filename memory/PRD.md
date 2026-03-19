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
│   ├── calculator.py          # Lógica de búsqueda, get_food_config(), ajustar_por_unidades()
│   ├── calma_engine.py        # Motor de cálculo de macros
│   └── meal_templates.py      # Generación de opciones de menú
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   └── NutritionPage.jsx # Página principal (MONOLITO - necesita refactor)
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
- ✅ `GET/POST /api/user/preferences` - preferencias de alimentos
- ✅ `POST /api/calculator/foods-sorted` - alimentos ordenados por fit
- ✅ `get_food_config()` - configuración de unidades/incrementos por categoría
- ✅ `ajustar_por_unidades()` - redondeo a unidades enteras

### Frontend (React + Tailwind + Shadcn)
- ✅ Login con botón mostrar/ocultar contraseña
- ✅ Dashboard del cliente
- ✅ Página de Nutrición completa con:
  - Configuración del día (comidas, entreno, periworkout)
  - Resumen diario sticky con barras de progreso
  - Sistema de comidas en acordeón
  - Modal "Sugiéreme un menú" (opciones A/B/C)
  - Modal "Lo hago yo" (constructor en 3 pasos)
  - Modal "Repetir de otro día"
  - Edición de ingredientes (+/- cantidad, eliminar)
  - Guardado/carga de dietas por fecha
- ✅ Pantalla de preferencias obligatoria (primera vez)
- ✅ Huevos/alimentos por unidad muestran "X ud (Yg)" NO decimales

## Credenciales de Prueba
- **Cliente:** `clientedemo@test.com` / `demo123`

## Última Sesión (Marzo 2026)

### Bugs Corregidos
1. **BUG 1 - Preferencias:** Pantalla aparece correctamente al primer uso
2. **BUG 2 - Huevos decimales:** Muestra "2 ud (126g)" no "3.1 unidades"
3. **BUG 3 - Categorías:** Reescrita `get_food_config()` con categorías reales
4. **BUG 4 - Cantidad excede:** Comportamiento CALMA correcto (P no cuenta para cereales)
5. **BUG 5 - Grasas paso 3:** Se añade "Grasas de buena calidad" si queda grasa

### Cambios Técnicos
- Nueva función `ajustar_por_unidades()` en calculator.py
- `get_food_config()` ahora devuelve: minimo, incremento, defecto, por_unidad, permite_media, peso_unidad
- Separada categoría "Huevos" (1.2) de "Claras" (1.1) en frontend

## Problemas Conocidos
- 🔴 Badge "Made with Emergent" tapa BottomNav en móvil

## Backlog Priorizado

### P1 - Alta Prioridad
- [ ] Arreglar badge de Emergent en móvil
- [ ] Implementar pantalla de inicio (Home) con macros circulares
- [ ] Implementar pantalla "Mi Rutina"
- [ ] Añadir calendario visual en Nutrición

### P2 - Media Prioridad
- [ ] Refactorizar `NutritionPage.jsx` (>2500 líneas)
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
- El archivo `NutritionPage.jsx` es un monolito de >2500 líneas
- Las preferencias de usuario se guardan en `client_profiles.food_preferences`
- El `_config` con `minimo`/`incremento`/`peso_unidad` se calcula en el backend
- CALMA: la proteína de cereales (cat 7) NO cuenta como proteína efectiva
