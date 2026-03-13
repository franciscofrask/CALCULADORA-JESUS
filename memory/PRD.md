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
- Category filtering (23 categories)
- Generic food tag filtering
- Effective macros calculation

### Meal Builder "Lo hago yo" (TAREA FIX-1 Complete)
- **Normal Mode:** 2-step guided builder (Protein → Accompaniment)
- **Intra Mode (FIX 5):** Single step, filtered to aminoacids/isotonic drinks, max 3 foods, yellow header
- **Post Mode (FIX 6):** 2-step flow with post-specific categories (Whey/Casein → Fruit/Rice cream), green header
- **Quantity Controls (FIX 8):** [-] [quantity] [+] buttons and separate AÑADIR button per suggestion
- **Backend Filter (FIX 7):** paso="proteina" strictly filters to pure protein categories only

### Diet Management
- Save daily diets to MongoDB
- Load saved diets by date
- Copy meals from previous days with macro scaling
- Menu suggestions (A/B/C options)

### UI Components
- Sticky daily summary with progress bars
- Expandable meal cards
- Inline ingredient editing
- Day navigation

## Architecture

```
/app/
├── backend/
│   ├── server.py         # FastAPI main server
│   ├── calculator.py     # CALMA calculation logic
│   ├── calma_engine.py   # Core macro calculations
│   └── meal_templates.py # Menu generation
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── AuthPage.jsx
│       │   └── NutritionPage.jsx  # Main nutrition page
│       └── components/
└── memory/
    └── PRD.md
```

## Database Collections
- `users`: User credentials, roles, macros
- `foods`: Food database with macros
- `food_categories`: Category definitions
- `diets`: Daily diet storage per user

## API Endpoints
- `POST /api/auth/login` - User authentication
- `GET /api/calculator/search` - Food search
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
  - FIX 1: Password show/hide toggle
  - FIX 2: Copyright 2026
  - FIX 3: Remove Kcal from sticky summary
  - FIX 4: Remove extra "Buscar alimento" button
  - FIX 5: Intra mode with filtered categories
  - FIX 6: Post mode with 2-step post-specific flow
  - FIX 7: Backend strict protein filter
  - FIX 8: Quantity controls in suggestions

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
- NutritionPage.jsx is monolithic (2000+ lines, needs refactoring)

## 3rd Party Integrations
- Claude Sonnet 4.5 (planned for routine generation)
- Stripe (mocked, real integration pending)
