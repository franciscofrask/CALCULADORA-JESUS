# JG12 - Plataforma de Entrenamiento Personal

## Original Problem Statement
El usuario quiere crear una plataforma de entrenamiento personal llamada "JG12". La plataforma incluye múltiples paneles y funcionalidades avanzadas como generación de rutinas por IA. La característica principal es una calculadora de macros y dietas altamente detallada llamada "CALMA".

## Product Requirements
- 4 Paneles: Cliente, Operaciones, CEO y Entrenadores
- Calculadora de nutrición avanzada "CALMA"
- Generación de 3 opciones de menú (A/B/C)
- Múltiples diseños de pantalla específicos
- Branding "JG12" (modo oscuro, acentos naranjas)
- Integración de IA (Claude Sonnet 4.5) para generación de rutinas (futuro)
- Integración de pagos (Stripe, actualmente simulada)

## Core Features Implemented

### Authentication & Users
- JWT-based authentication
- Client login/logout
- User roles (client, trainer, admin)

### Nutrition Calculator (CALMA v2)
- Macro distribution based on day type (training/rest)
- Configurable meals (3 or 4)
- Periworkout timing (before/after which meal)
- Periworkout options (Intra+Post, Solo Post, Solo Intra, Sin peri)

### Food Search & Management
- Text search with accent normalization
- Category filtering (supports pipe-separated categories like "2.1 | YA | 2.4.3")
- Generic food tag filtering
- Effective macros calculation

### Build Meal Modal "Lo hago yo" (REESCRITO - 18 Mar 2026)
**Comportamiento correcto implementado:**
1. **Estado inicial:** Solo botones de categoría, NO se muestra ningún alimento
2. **Al pinchar categoría:** Se cargan alimentos de ESA categoría ordenados por mejor fit
3. **"← Volver a categorías":** Limpia la lista y vuelve a mostrar botones
4. **Añadir alimento:** Click en botón + naranja añade DIRECTO
5. **Consistencia:** Vaciar y recargar = mismos alimentos, mismo orden
6. **Scroll infinito:** Todos los alimentos accesibles (194 aves, 126 embutidos, etc.)
7. **Hipervínculos:** Nombres con enlace aparecen en azul subrayado
8. **Transición de pasos:** >80% P → paso 2, >80% H → paso 3
9. **Búsqueda:** Funciona correctamente (salmón, lechuga, aguacate)

**Modos especiales:**
- **Intra-entreno:** Cabecera amarilla, categorías aminoácidos/isotónicas, máx 3 alimentos
- **Post-entreno:** Cabecera verde, flujo 2 pasos (whey/caseína → fruta/crema arroz)

### Backend Endpoints Añadidos
- `POST /api/calculator/foods-sorted`: Devuelve alimentos de categorías ordenados por mejor ajuste
  - Recibe: `{ category_prefixes: ["2.2"], macros_restantes: {P, H, G} }`
  - Devuelve: Alimentos con `_cantidad_sugerida`, `_macros_sugeridos`, `_formatted_qty`, `_score`

### Diet Management
- Save daily diets to MongoDB
- Load saved diets by date
- Copy meals from previous days with macro scaling
- Menu suggestions (A/B/C options)

## Architecture

```
/app/
├── backend/
│   ├── server.py         # FastAPI main server (añadido foods-sorted endpoint)
│   ├── calculator.py     # CALMA calculation logic (arreglado filtro de categorías)
│   ├── calma_engine.py   # Core macro calculations
│   └── meal_templates.py # Menu generation
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── AuthPage.jsx
│       │   └── NutritionPage.jsx  # BuildMealModal REESCRITO
│       └── components/
└── memory/
    └── PRD.md
```

## Database Collections
- `users`: User credentials, roles, macros
- `foods`: Food database with macros (3,110 alimentos)
- `food_categories`: Category definitions (232 categorías)
- `diets`: Daily diet storage per user

## API Endpoints
- `POST /api/auth/login` - User authentication
- `GET /api/calculator/search` - Food search
- `POST /api/calculator/foods-sorted` - **NUEVO** Foods sorted by fit
- `POST /api/calculator/suggest` - AI suggestions
- `POST /api/calculator/adjust` - Calculate optimal quantity
- `POST /api/calculator/distribute` - Macro distribution
- `POST /api/calculator/menu-options` - Generate menu A/B/C
- `POST /api/diets` - Save daily diet
- `GET /api/diets/{fecha}` - Load diet by date
- `GET /api/diets/recent` - Recent diets for repeat

## Test Credentials
- Client: `clientedemo@test.com` / `demo123`

## Completed Tasks
- [x] TAREA E12: Fixed food search (accents, effective macros)
- [x] TAREA F1.1 & F1.2: Day configuration + sticky summary
- [x] TAREA F1.3: "Lo hago yo" 2-step builder
- [x] TAREA F1.4: Ingredient editing, save, repeat from day
- [x] Full diagnostic (100 points)
- [x] TAREA FIX-1: All 8 fixes completed
- [x] **REESCRITURA CRÍTICA BuildMealModal** (18 Mar 2026)
  - Arreglado filtro de categorías (pipe-separated)
  - Creado endpoint foods-sorted
  - Estado inicial sin alimentos
  - Click en categoría → carga alimentos filtrados
  - Botón + para añadir
  - 12/12 tests de verificación pasados

## Upcoming Tasks (P1)
- [ ] Home Screen Redesign (Pantalla 10) with circular macro trackers
- [ ] Routine Screen Redesign ("Mi Rutina")
- [ ] Visual Calendar in NutritionPage

## Backlog (P2)
- [ ] Tracking Module (evolution silhouettes)
- [ ] Real Stripe Integration
- [ ] Refactor server.py into APIRouters
- [ ] Refactor NutritionPage.jsx into sub-components
- [ ] Fix "Made with Emergent" badge overlap on mobile

## Known Issues
- Badge "Made with Emergent" overlaps bottom nav on mobile (P2)
- NutritionPage.jsx is still large (needs further refactoring)

## 3rd Party Integrations
- Claude Sonnet 4.5 (planned for routine generation)
- Stripe (mocked, real integration pending)
