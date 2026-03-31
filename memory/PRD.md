# JG12 - Plataforma de Entrenamiento Personal

## Problema Original
Crear una plataforma de entrenamiento personal llamada "JG12" con múltiples paneles y funcionalidades avanzadas. La característica principal es una calculadora de macros y dietas altamente detallada llamada "CALMA", junto con un Chatbot conversacional que ayuda al cliente a montar su dieta del día usando Claude Sonnet 4.5.

## Requisitos del Producto
- 4 Paneles: Cliente, Operaciones, CEO y Entrenadores
- Calculadora de nutrición avanzada "CALMA"
- Generación de 3 opciones de menú (A/B/C)
- **Chatbot conversacional con Claude** para montar dietas en lenguaje natural
- Branding "JG12" (modo oscuro, acentos naranjas)
- Integración de pagos con Stripe (actualmente MOCKED)

## Arquitectura del Código
```
/app/
├── backend/
│   ├── server.py              # API principal FastAPI
│   ├── chatbot.py             # Chatbot con Claude Sonnet 4.5 + distribución inteligente
│   ├── calculator.py          # Lógica de búsqueda, get_food_config()
│   ├── calma_engine.py        # Motor de cálculo de macros (57 tests)
│   ├── macro_distribution.py  # Distribución de macros (16 escenarios)
│   ├── tests/
│   │   └── test_calma_engine.py  # 57 tests de verificación
│   └── meal_templates.py      # Generación de opciones de menú
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── NutritionPage.jsx   # Página manual de nutrición
│   │   │   ├── ChatbotPage.jsx     # UI del chatbot
│   │   │   └── AuthPage.jsx        # Login
│   │   ├── components/
│   │   │   └── BottomNav.jsx
│   │   └── layouts/
│   │       └── ClientDashboard.jsx
│   └── tailwind.config.js
└── memory/
    └── PRD.md
```

## Lo que está implementado

### Motor CALMA v2 (57/57 tests)
- Reglas estrictas de la "Biblia de Alimentos v2"
- Calibración progresiva cereales/panes y frutos secos
- Regla doble categoría
- Márgenes: ±4g general, ±2g intra

### Backend (FastAPI + MongoDB)
- Autenticación JWT
- Motor CALMA completo
- Búsqueda de alimentos con normalización de acentos
- **Chatbot con Claude Sonnet 4.5** (emergentintegrations)
  - Endpoint: `POST /api/chatbot/start`
  - Endpoint: `POST /api/chatbot/configure`
  - Endpoint: `POST /api/chatbot/message`
  - Endpoint: `POST /api/chatbot/complete-meal`
  - Endpoint: `POST /api/chatbot/reset`
- Endpoints de dietas: save, load, recent

### Chatbot - Funcionalidades (actualizado 26/03/2026)
- Configuración del día (entrenamiento/descanso)
- Búsqueda de alimentos con normalización de acentos
- **Límites máximos razonables** por categoría
- **Alimentos por unidad** se muestran correctamente
- **DISTRIBUCIÓN INTELIGENTE DE MACROS:**
  - Reparte la proteína entre TODAS las fuentes de P equitativamente
  - Considera la P secundaria de alimentos mixtos (ej: garbanzos)
  - Las fuentes con límites bajos (huevos) se procesan primero
  - Las demás fuentes compensan para llegar al objetivo
  - Casos de prueba verificados:
    - "huevos, pan, claras y pavo" → P=40g/40g, H=15g/15g
    - "pechuga, garbanzos, aguacate, calabacín" → P=40g/40g, H=15g/15g, G=8g/8g

### Frontend (React + Tailwind + Shadcn)
- Login con mostrar/ocultar contraseña
- Dashboard del cliente
- Página de Nutrición manual completa
- **Página de Chatbot** (`/dashboard/chatbot`)
  - UI conversacional funcionando
  - Botones de configuración del día
  - Input de chat con Enter para enviar
  - Badge de Emergent no tapa botones

## Credenciales de Test
- **Cliente:** `clientedemo@test.com` / `demo123`

## Tareas Completadas Esta Sesión (26-27/03/2026)
- Arreglado: Chatbot mostraba pantalla en blanco (error de estados frontend)
- Arreglado: Chatbot asignaba cantidades absurdas (266g de claras)
- Arreglado: Huevos no se mostraban en unidades
- Arreglado: Búsqueda no encontraba alimentos con tildes (calabacín)
- Arreglado: Badge de Emergent tapaba botón de enviar
- **IMPLEMENTADO: Distribución inteligente de macros entre alimentos**
  - Ya no asigna toda la P al primer alimento
  - Reparte equitativamente entre fuentes de P
  - Considera P secundaria de alimentos mixtos (legumbres)
  - Compensación automática cuando una fuente tiene límite

### Sesión 27/03/2026 - REGLA CALMA de Mínimos
- **ARREGLADO: Algoritmo de macros respeta regla fundamental CALMA**
  - NUNCA se reduce cantidad por debajo del mínimo de un alimento
  - Si el mínimo excede los macros restantes (+4g margen), el alimento SE RECHAZA
  - Se muestra mensaje explicativo: "La cantidad mínima (Xg) excede los macros: mín Xg = Yg H, pero solo quedan Zg H"
  - Se sugieren alternativas cuando un alimento no cabe
  
- **TEST COMPLETO DE 4 COMIDAS PASADO ✅:**
  - C1: huevos, pan, claras y pavo → P=40g, H=15g, G=6g ✅
  - C2: pechuga de pollo, garbanzos, tomate, cebolla, aguacate y calabacín → P=40g, H=18.9g, G=8g ✅
  - C3: lomo embuchado bajo en grasa, queso havarti light, tomate rallado, pan tostado y aceite de oliva → P=32g, H=6.6g, G=15.7g ✅
  - C4: huevos, sepia, tomate frito, pan tostado y berenjena → P=48g, H=11.6g, G=12g ✅
  - Todas dentro del margen de ±4g

- **Resumen del día implementado:**
  - Cuando se completan todas las comidas, se muestra resumen total de P/H/G vs objetivos

### Sesión 29/03/2026 - Mejoras de Búsqueda y Mínimos
- **ARREGLADO: Búsqueda parcial funciona correctamente**
  - "queso batido" → encuentra "Queso fresco batido 0%"
  - Mejorado el algoritmo de búsqueda con text search de MongoDB
  - Búsqueda de múltiples palabras funciona correctamente

- **ARREGLADO: Mínimos de frutos secos (cat 17.2)**
  - Nueces ahora tienen mínimo=5g (antes incorrectamente 50g)
  - Corregido bug en `get_food_config()` donde categorías como "38.2" matcheaban con "3."
  - Cambiado `has_cat('3')` a `has_cat('3.')`, `has_cat('4')` a `has_cat('4.')`, etc.

- **IMPLEMENTADO: Mensaje de macros faltantes**
  - Cuando quedan macros sin cubrir, el chatbot sugiere qué añadir
  - Ejemplo: "Te faltan 20g de proteína y 8g de grasa. ¿Quieres añadir algún alimento más? Por ejemplo: claras de huevo o pechuga de pollo para la proteína o aceite de oliva (8ml) para la grasa."

### Sesión 31/03/2026 - Búsqueda "tortas" y alimentos por unidad
- **ARREGLADO: Búsqueda "tortas" → "Tortita de arroz"**
  - Añadido mapeo: "tortas", "torta", "tortitas", "tortita" → "tortita de arroz"
  - Antes encontraba "Tortilla de maíz" incorrectamente

- **ARREGLADO: Alimentos con unidades=True en BD usan config correcta**
  - Modificado `get_food_config()` para verificar PRIMERO el campo `unidades` de la BD
  - Si `unidades=True`, el mínimo es 1 unidad (peso = racion)
  - Tortitas de arroz ahora: mínimo=8g (1 ud), incremento=8g, por_unidad=True
  - Antes incorrectamente: mínimo=25g, por_unidad=False

### Sesión 31/03/2026 - REESCRITURA COMPLETA del algoritmo de macros
- **CREADO: `/app/backend/meal_builder.py`** - Nuevo módulo con algoritmo de distribución de macros
- **REGLAS IMPLEMENTADAS:**
  1. **MÍNIMOS:** Nunca poner un alimento por debajo de su mínimo (carnes 50g, embutidos 25g, huevos 1 ud, whey 5g, cereales 10g, frutos secos 5g, aceites 5g)
  2. **MÁXIMOS:** Claras 200g, huevos 3 ud, carnes 250g, queso batido 300g, frutos secos 25g, aceite 10g (1 cucharada)
  3. **DISTRIBUCIÓN INTELIGENTE:**
     - Primero alimentos PG (huevos) - limitar si hay otras fuentes de P
     - Luego H mixtos (lácteos PH)
     - Luego H fijos (frutas por unidad)
     - Luego H por peso (cereales, tubérculos) - ajustar para cubrir resto
     - Luego P puras (carnes, claras)
     - Finalmente G puras (aceites, frutos secos) - SOLO si faltan >2g
  4. **CALMA:** Usa macros EFECTIVOS según categoría

- **4 CASOS DE PRUEBA PASAN ✅:**
  - C1: huevos, claras, avena, frambuesas → P=32.5, H=32.5, G=12 ✅
  - C2: pechuga, boniato, calabacín, aceite, almendras → P=35.7, H=10, G=17.5 ✅
  - C3: whey, queso batido, crema cacahuete, nueces → P=35.1, H=8, G=15 ✅
  - C4: dorada, patata, lechuga, pepino, aceite → P=32.5, H=32.5, G=11.4 ✅
  
- **MEJORAS EN BÚSQUEDA:**
  - "queso batido" → "Queso fresco batido 0%"
  - "crema de cacahuete" → "Crema de cacahuete natural"
  - Priorización de regex para términos específicos (>2 palabras)

## Tareas Pendientes

### P1 - Próximas
- Refactor de NutritionPage.jsx en componentes pequeños
- Refactor de server.py en APIRouters
- Refactor de chatbot.py (_process_build_meal tiene muchos patches)

### P2 - Futuras
- Implementar pantalla Home con trackers circulares
- Implementar pantalla "Mi Rutina"
- Calendario visual de días
- Integración real de Stripe (actualmente MOCKED)

## Integraciones de Terceros
- **Claude Sonnet 4.5** — Usa Emergent LLM Key (implementado en chatbot.py)
- **Stripe** — MOCKED (pendiente integración real)
