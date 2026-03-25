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
│   ├── calma_engine.py        # Motor de cálculo de macros (REESCRITO 25/03/2026)
│   ├── tests/
│   │   └── test_calma_engine.py  # 54 tests de verificación del motor CALMA
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
- ✅ **Motor CALMA v2 REESCRITO (25/03/2026)** - Basado en BIBLIA_ALIMENTOS_v2
- ✅ 54 tests de verificación que pasan al 100%
- ✅ Búsqueda de alimentos con normalización de acentos
- ✅ Endpoints de dietas: save, load, recent
- ✅ `GET/POST /api/user/preferences` - preferencias de alimentos
- ✅ `POST /api/calculator/foods-sorted` - alimentos ordenados por fit
- ✅ `get_food_config()` - configuración de unidades/incrementos por categoría
- ✅ `ajustar_por_unidades()` - redondeo a unidades enteras

### Motor CALMA - Reglas Implementadas (según Biblia v2)
- ✅ Regla base del 25% para categorías sin regla específica
- ✅ Categorías proteicas (1,2,3,4,40): P siempre, H≥2g, G≥3g
- ✅ Mariscos (3.9): H>3g (umbral estricto)
- ✅ Proteína en polvo (4): H/G >6g
- ✅ Lácteos (5) y Leche soja (6.1): P+H siempre, G>1g
- ✅ Cereales (7) y Panes (8): H siempre, P si >H/3 + calibración progresiva
- ✅ Excepciones cat 7.1.3 y 8.8: P siempre al 100% sin calibración
- ✅ Tubérculos (9), Frutas (11): Solo H
- ✅ Legumbres (10): P+H siempre, G≥8g
- ✅ Verduras (13): P nunca, H/G si >4g
- ✅ Salsas (16): Cualquier macro ≥6g
- ✅ Aceites/Aguacate (17.1, 17.6): Solo G
- ✅ Frutos secos naturales (17.2.1/3/4): G siempre, P/H si >G/3 + calibración
- ✅ Arroz (21): H siempre, P NUNCA
- ✅ Pasta (22): H siempre, P si >H/3
- ✅ Procesados (43-53): TODOS los macros
- ✅ Calibración progresiva cereales+panes (0-50g:0%, 50-100g:50%, >100g:100%)
- ✅ Calibración progresiva frutos secos (0-20g:0%, 20-40g:50%, >40g:100%)
- ✅ Regla doble categoría: la más permisiva gana
- ✅ Márgenes: ±4g general, ±2g intra
- ✅ Tolerancia postentreno: ≤2g proteína

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
- ✅ Pantalla de preferencias de alimentos (primera vez)

## Problemas Conocidos
- ⚠️ Badge "Made with Emergent" tapa BottomNav en móvil (P2)
- ⚠️ NutritionPage.jsx es un monolito (~2500 líneas) - necesita refactor

## Tareas Pendientes

### P1 - Próximas
- [ ] Refactor de NutritionPage.jsx en componentes pequeños
- [ ] Refactor de server.py en APIRouters
- [ ] Implementar pantalla Home con trackers circulares
- [ ] Implementar pantalla "Mi Rutina"
- [ ] Calendario visual de días

### P2 - Backlog
- [ ] Fix badge Emergent en móvil
- [ ] Integración real de Stripe
- [ ] Módulo de seguimiento/tracking
- [ ] Siluetas de evolución

## Credenciales de Test
- **Cliente**: clientedemo@test.com / demo123
- **Admin**: agutierrezp95@gmail.com / Alvaro123

## Documentos de Referencia
- `BIBLIA_ALIMENTOS_v2_PARTE1y2.md` - Reglas de conteo por categoría
- `BIBLIA_ALIMENTOS_PARTE3_4_5_6.md` - Flujo calculadora, cantidades mínimas, lista categorías

## Changelog

### 25/03/2026
- **REESCRITURA COMPLETA del motor CALMA** según BIBLIA_ALIMENTOS_v2
- Implementadas todas las reglas de conteo por categoría
- Implementada calibración progresiva para cereales/panes y frutos secos
- Implementada regla de doble categoría (la más permisiva gana)
- Creados 54 tests de verificación (35 originales + 19 auxiliares)
- **Resultado: 54/54 tests PASADOS**
- Backup del motor anterior en `calma_engine_backup_20260325_014039.py`
