# JG12 - Mapa de Lógica de Negocio
## Plataforma de Entrenamiento Personal - Método 12en12 de Jesús Gallego

---

## 1. ARQUITECTURA GENERAL

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                            │
├─────────────────────────────────────────────────────────────────────┤
│  NutritionPage.jsx    │  ChatbotPage.jsx   │  Otros Paneles        │
│  (Manual de comidas)  │  (Asistente IA)    │  (Dashboard, Rutinas) │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                           │
├─────────────────────────────────────────────────────────────────────┤
│  routes/              │  Módulos Core       │  Base de Datos        │
│  ├── auth.py          │  ├── calma_engine   │  MongoDB              │
│  ├── calculator.py    │  ├── macro_distrib  │  ├── users            │
│  ├── chatbot.py       │  ├── meal_builder   │  ├── foods (800+)     │
│  ├── diets.py         │  ├── calculator     │  ├── food_categories  │
│  └── ...              │  └── chatbot        │  └── diets            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. MOTOR CALMA v2 (`calma_engine.py`)
### El corazón del sistema de cálculo de macros

### 2.1 ¿Qué es CALMA?
CALMA = **C**alculadora **A**vanzada de **L**ímites y **MA**cros

Es el motor que determina qué macros "cuentan" de cada alimento según su categoría.
**No todos los macros de un alimento se contabilizan igual.**

### 2.2 Regla Principal: Macros Efectivos vs Brutos

```
MACROS BRUTOS = Lo que dice la etiqueta nutricional
MACROS EFECTIVOS = Lo que realmente cuenta según el método 12en12
```

**Ejemplo:**
- Almendras (100g): P=21g, H=22g, G=49g (brutos)
- Almendras (100g): P=0g, H=0g, G=49g (efectivos) ← Solo cuenta la grasa

### 2.3 Categorías y Reglas

| Categoría | Alimentos | Cuenta P | Cuenta H | Cuenta G |
|-----------|-----------|----------|----------|----------|
| 1 | Huevos | ✅ 100% | ❌ | ✅ 100% |
| 2 | Carnes | ✅ 100% | ❌ | Regla 25* |
| 3 | Pescados | ✅ 100% | ❌ | Regla 25* |
| 4 | Proteína polvo | ✅ 100% | ❌ | ❌ |
| 5 | Lácteos | Regla 25* | Regla 25* | Regla 25* |
| 7 | Cereales | Calibración** | ✅ 100% | ❌ |
| 8 | Panes | Calibración** | ✅ 100% | ❌ |
| 9 | Tubérculos | ❌ | ✅ 100% | ❌ |
| 10 | Legumbres | ✅ 100% | ✅ 100% | ❌ |
| 11 | Frutas | ❌ | ✅ 100% | ❌ |
| 13 | Verduras | ❌ | ❌ | ❌ |
| 17 | Grasas | ❌ | ❌ | ✅ 100% |
| 17.2 | Frutos secos | Calibración*** | ❌ | ✅ 100% |

**Regla 25***: Cuenta si es ≥25% del macro predominante del alimento
**Calibración Cereales/Panes**: Primeros 60g cuentan 100%, después decrece
**Calibración Frutos Secos**: Primeros 30g cuentan P, después solo G

### 2.4 Funciones Principales

```python
# Función principal
calcular_macros_efectivos(P, H, G, categoria, cantidad_g) → {P, H, G}

# Determinar qué macros cuentan
que_macros_cuentan(alimento, cantidad) → {cuenta_P, cuenta_H, cuenta_G}

# Calcular cantidad óptima para un objetivo
calcular_cantidad_automatica(alimento, objetivo_macros) → cantidad_g

# Verificar si comida está "cuadrada" (±4g de cada macro)
comida_cuadrada(objetivo, consumido) → {cuadrada: bool, diferencias}
```

---

## 3. DISTRIBUCIÓN DE MACROS (`macro_distribution.py`)
### Cómo se reparten los macros del día entre las comidas

### 3.1 Escenarios según Hidratos Totales

| Escenario | Hidratos/día | Estrategia |
|-----------|--------------|------------|
| E1 | >150g | Distribución equilibrada (tablas %) |
| E2 | 100-150g | Distribución equilibrada (tablas %) |
| E3 | 50-99g | H concentrados pre/post entreno |
| E4 | <50g | H solo en periworkout |

### 3.2 Variables que afectan la distribución

```
1. TIPO DE DÍA
   ├── Entrenamiento → Usa escenarios E1-E4
   └── Descanso → Siempre 25%/25%/25%/25%

2. NÚMERO DE COMIDAS
   ├── 3 comidas
   └── 4 comidas (estándar)

3. MOMENTO DEL ENTRENO
   ├── 0 = En ayunas (antes de C1)
   ├── 1 = Después de C1 (estándar)
   ├── 2 = Después de C2
   └── 3 = Después de C3

4. TIPO DE PERIWORKOUT
   ├── intra_post → Intra + Post entreno
   ├── solo_post → Solo post entreno
   ├── solo_intra → Solo intra entreno
   └── sin_peri → Sin periworkout
```

### 3.3 Periworkout: Intra y Post

```
INTRA-ENTRENO (durante el entreno):
├── 20% de la Proteína del día
├── 30% de los Hidratos del día
├── 0% de la Grasa
└── Alimentos permitidos: Aminoácidos (cat 41), Isotónicas (cat 18.1)

POST-ENTRENO (después del entreno):
├── 80% restante de Proteína peri
├── 70% restante de Hidratos peri
├── 0% de la Grasa
└── Alimentos: Whey (cat 4.1-4.3), Frutas (cat 11), Crema arroz (21.3)
```

### 3.4 Ejemplo de Distribución

```
USUARIO: P=160g, H=50g, G=40g (Escenario 3)
DÍA: Entrenamiento, 4 comidas, entreno después de C1

RESULTADO:
┌─────────┬────────┬────────┬────────┐
│ Comida  │   P    │   H    │   G    │
├─────────┼────────┼────────┼────────┤
│ C1      │  40g   │  15g   │   8g   │
│ INTRA   │   7g   │  10g   │   0g   │
│ POST    │  28g   │  15g   │   0g   │
│ C2      │  40g   │   5g   │  16g   │
│ C3      │  45g   │   5g   │  16g   │
└─────────┴────────┴────────┴────────┘
```

---

## 4. CHATBOT DE NUTRICIÓN (`chatbot.py`)
### Asistente IA para crear comidas con lenguaje natural

### 4.1 Flujo del Chatbot

```
1. INICIO
   └── Usuario elige: Día de entrenamiento / Día de descanso

2. CONFIGURACIÓN
   ├── Número de comidas (3 o 4)
   ├── Momento del entreno
   └── Tipo de periworkout
   
3. CONSTRUCCIÓN DE COMIDAS (por cada comida)
   ├── Usuario escribe: "quiero huevos con pavo y tostadas"
   ├── Sistema busca alimentos en BD
   ├── Calcula cantidades óptimas con CALMA
   ├── Muestra resultado con macros
   └── Usuario confirma o modifica

4. RESUMEN FINAL
   └── Totales del día, diferencias vs objetivo
```

### 4.2 Proceso de un Mensaje

```python
async def process_message(user_input):
    # 1. Claude interpreta el mensaje
    claude_response = await llm.send_message(user_input)
    
    # 2. Extrae alimentos mencionados
    foods_requested = parse_foods_from_response(claude_response)
    
    # 3. Busca cada alimento en la BD
    for food_name in foods_requested:
        matches = await search_foods(food_name)
        
    # 4. Calcula cantidades óptimas
    for food in matched_foods:
        cantidad = calculate_food_amount(food, macros_restantes)
        
    # 5. Añade a la comida actual
    add_food_to_meal(food, cantidad)
    
    # 6. Retorna resumen con macros servidos vs objetivo
    return {alimentos, macros_servidos, macros_restantes}
```

### 4.3 Reglas de Cantidades

| Alimento | Mínimo | Máximo | Paso |
|----------|--------|--------|------|
| Huevos | 1 ud | 6 ud | 1 ud |
| Claras | 30g | 200g | 10g |
| Carnes | 50g | 300g | 10g |
| Pescados | 50g | 250g | 10g |
| Arroz (crudo) | 25g | 150g | 5g |
| Pan | 20g | 100g | 10g |
| Fruta | 80g | 300g | 20g |
| Frutos secos | 5g | 50g | 5g |
| Aceite | 5g | 30g | 5g |

---

## 5. CONSTRUCTOR DE COMIDAS (`meal_builder.py`)
### Algoritmo de distribución inteligente de macros

### 5.1 Problema que resuelve

```
ENTRADA:
- Macros objetivo: P=40g, H=15g, G=8g
- Alimentos pedidos: "huevos, claras, pavo, avena"

SALIDA:
- Huevos enteros L: 1 ud → P=8g, H=0g, G=6g
- Claras: 100g → P=10g, H=0g, G=0g
- Pavo: 120g → P=19g, H=2g, G=1g
- Avena: 20g → P=3g, H=13g, G=1g
- TOTAL: P=40g, H=15g, G=8g ✓
```

### 5.2 Algoritmo de Distribución

```
1. CLASIFICAR ALIMENTOS
   ├── Por unidad (huevos, tortitas) → Procesar primero
   └── A granel (carnes, cereales) → Procesar después

2. PROCESAR ALIMENTOS POR UNIDAD
   └── Asignar cantidad mínima (1-2 uds)

3. REPARTIR MACROS ENTRE ALIMENTOS A GRANEL
   ├── Identificar rol de cada alimento:
   │   ├── Fuente de P (carne, pescado, lácteos)
   │   ├── Fuente de H (arroz, pan, fruta)
   │   └── Fuente de G (aceite, frutos secos)
   │
   ├── Asignar proporcionalmente según macros restantes
   └── Respetar mínimos y máximos de cada alimento

4. AJUSTE FINAL
   └── Si no cuadra, ajustar alimento más flexible
```

### 5.3 Roles de Alimentos

```python
def classify_food_role(alimento, macros_efectivos):
    P, H, G = macros_efectivos
    total = P + H + G
    
    if P/total > 0.5:
        return "PROTEINA"
    elif H/total > 0.5:
        return "HIDRATO"
    elif G/total > 0.5:
        return "GRASA"
    else:
        return "MIXTO"
```

---

## 6. BÚSQUEDA DE ALIMENTOS (`calculator.py`)
### Motor de búsqueda y sugerencias

### 6.1 Búsqueda Inteligente

```python
async def buscar_alimentos(db, query, categoria, limit):
    # 1. Normalizar texto (quitar acentos, minúsculas)
    query_norm = normalize_text(query)  # "pollo" → "pollo"
    
    # 2. Mapear sinónimos
    # "queso batido" → buscar "queso" + "batido"
    # "tortas" → buscar "tortita de arroz"
    
    # 3. Buscar con regex
    regex = {"$regex": query_norm, "$options": "i"}
    
    # 4. Filtrar por categoría si aplica
    if categoria:
        filtro["categorias"] = {"$regex": f"^{categoria}"}
    
    # 5. Ordenar por relevancia
    # Prioridad: nombre exacto > nombre contiene > similar
```

### 6.2 Configuración por Alimento

```python
def get_food_config(alimento):
    """
    Devuelve: {minimo, maximo, paso, por_unidad}
    """
    categoria = get_categoria_principal(alimento)
    
    # Reglas por categoría
    if categoria.startswith("1"):  # Huevos
        if "clara" in nombre.lower():
            return {"min": 30, "max": 200, "paso": 10, "unidad": "g"}
        return {"min": 1, "max": 6, "paso": 1, "unidad": "ud"}
    
    if categoria.startswith("2"):  # Carnes
        return {"min": 50, "max": 300, "paso": 10, "unidad": "g"}
    
    # ... más reglas
```

---

## 7. FLUJOS DE USUARIO

### 7.1 Flujo: Crear Dieta Manual (NutritionPage)

```
┌────────────────────────────────────────────────────────────────┐
│ 1. SELECCIONAR DÍA                                             │
│    Usuario elige fecha (hoy, ayer, mañana...)                  │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 2. CONFIGURAR DÍA                                              │
│    ├── Tipo: Entrenamiento / Descanso                          │
│    ├── Nº comidas: 3 / 4                                       │
│    ├── Momento entreno: Antes C1 / Después C1 / C2 / C3        │
│    └── Periworkout: Intra+Post / Solo Post / Sin peri          │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 3. SISTEMA CALCULA DISTRIBUCIÓN                                │
│    Usa macro_distribution.py para repartir P/H/G por comida    │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 4. RELLENAR CADA COMIDA                                        │
│    Para cada comida, el usuario puede:                         │
│    ├── "Sugiéreme menú" → Opciones A/B/C automáticas           │
│    ├── "Lo hago yo" → Modal paso a paso (proteína → acomp.)    │
│    └── "Repetir" → Copiar de otro día                          │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 5. EDITAR ALIMENTOS                                            │
│    ├── Ajustar cantidad con [+] [-]                            │
│    ├── Eliminar alimentos                                      │
│    └── Ver macros en tiempo real                               │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 6. GUARDAR DÍA                                                 │
│    Guarda en MongoDB → colección "diets"                       │
└────────────────────────────────────────────────────────────────┘
```

### 7.2 Flujo: Crear Dieta con IA (ChatbotPage)

```
┌────────────────────────────────────────────────────────────────┐
│ 1. INICIAR SESIÓN DE CHAT                                      │
│    POST /api/chatbot/start → session_id                        │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 2. CONFIGURAR DÍA                                              │
│    POST /api/chatbot/configure                                 │
│    → Sistema calcula distribución de macros                    │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 3. CONVERSACIÓN PARA CADA COMIDA                               │
│                                                                │
│    Usuario: "quiero huevos con pavo"                           │
│                    │                                           │
│                    ▼                                           │
│    Claude interpreta → extrae ["huevos", "pavo"]               │
│                    │                                           │
│                    ▼                                           │
│    Sistema busca en BD → encuentra matches                     │
│                    │                                           │
│                    ▼                                           │
│    CALMA calcula cantidades óptimas                            │
│                    │                                           │
│                    ▼                                           │
│    Chatbot: "He añadido:                                       │
│              - Huevos enteros L: 2 ud (P=16g)                  │
│              - Pavo: 150g (P=24g)                              │
│              Total: P=40g/40g ✓"                               │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 4. COMPLETAR COMIDA                                            │
│    POST /api/chatbot/complete-meal                             │
│    → Pasa a siguiente comida                                   │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│ 5. RESUMEN FINAL                                               │
│    Cuando todas las comidas están completas:                   │
│    ├── Mostrar totales del día                                 │
│    ├── Diferencias vs objetivo                                 │
│    └── Botón "Exportar PDF"                                    │
└────────────────────────────────────────────────────────────────┘
```

---

## 8. MODELOS DE DATOS

### 8.1 Usuario

```javascript
{
  id: "uuid",
  email: "cliente@test.com",
  name: "Nombre",
  password: "hash",
  role: "client" | "trainer" | "admin" | "ceo" | "operations",
  plan: "gold" | "silver" | "bronze" | "elm",
  trainer_id: "uuid del entrenador",
  created_at: "2026-01-01T00:00:00Z"
}
```

### 8.2 Perfil de Cliente

```javascript
{
  id: "uuid",
  user_id: "uuid",
  plan: "gold",
  week: 4,
  status: "activo",
  macros_training: { protein: 160, carbs: 50, fat: 40 },
  macros_rest: { protein: 140, carbs: 40, fat: 40 },
  weight: 80,
  height: 175,
  age: 30,
  sex: "M",
  goal: "recomposición",
  food_preferences: ["huevos", "carnes", "pescados"]
}
```

### 8.3 Alimento (Food)

```javascript
{
  id: 123,
  nombre: "Pechuga de pollo",
  categorias: "2.2 | Aves",
  racion: 150,           // Ración estándar en gramos
  proteinas: 31,         // Por 100g
  hidratos: 0,           // Por 100g
  grasas: 3.6,           // Por 100g
  calorias: 165,         // Por 100g
  fibra: 0,
  sal: 0.1,
  unidades: false        // true si se cuenta por unidades
}
```

### 8.4 Dieta Diaria

```javascript
{
  id: "uuid",
  user_id: "uuid",
  fecha: "2026-04-11",
  tipo_dia: "entrenamiento",
  num_comidas: 4,
  momento_entreno: 1,
  opcion_peri: "intra_post",
  comidas: {
    "C1": {
      alimentos: [
        {
          alimento_id: 123,
          nombre: "Huevos enteros L",
          cantidad: 2,
          unidad: "ud",
          macros: { P: 16, H: 0, G: 12 }
        }
      ],
      macros: { P: 40, H: 15, G: 8 }
    },
    "INTRA": {...},
    "POST": {...},
    "C2": {...},
    "C3": {...}
  },
  updated_at: "2026-04-11T10:30:00Z"
}
```

---

## 9. ENDPOINTS PRINCIPALES

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login de usuario |
| POST | `/api/auth/register` | Registro |
| GET | `/api/auth/me` | Usuario actual |
| GET | `/api/calculator/search?q=pollo` | Buscar alimentos |
| POST | `/api/calculator/suggest` | Sugerir alimentos |
| GET | `/api/macros` | Macros del usuario |
| PUT | `/api/macros` | Actualizar macros |
| POST | `/api/diets` | Guardar dieta |
| GET | `/api/diets/{fecha}` | Obtener dieta de un día |
| GET | `/api/diets/recent` | Últimas 14 dietas |
| POST | `/api/chatbot/start` | Iniciar sesión chat |
| POST | `/api/chatbot/configure` | Configurar día |
| POST | `/api/chatbot/message` | Enviar mensaje |
| POST | `/api/chatbot/complete-meal` | Completar comida |
| GET | `/api/chatbot/summary` | Resumen del día |
| GET | `/api/chatbot/export-pdf` | Descargar PDF |

---

## 10. INTEGRACIONES

| Servicio | Uso | Estado |
|----------|-----|--------|
| Claude Sonnet 4.5 | Chatbot de nutrición | ✅ Activo |
| MongoDB | Base de datos | ✅ Activo |
| ReportLab | Generación de PDFs | ✅ Activo |
| Stripe | Pagos | 🔶 MOCKED |

---

## 11. REGLAS DE NEGOCIO CRÍTICAS

### 11.1 Tolerancia de Macros
- Una comida está **"cuadrada"** si cada macro está dentro de **±4g** del objetivo
- Excepción: Periworkout (Intra/Post) no cuenta grasa

### 11.2 Prioridad de Macros
1. **Proteína** → Se cubre primero (fuentes de proteína)
2. **Hidratos** → Se cubre segundo (acompañamientos)
3. **Grasa** → Se ajusta al final (aceites, frutos secos)

### 11.3 Restricciones de Alimentos
- **Periworkout Intra**: Solo aminoácidos (cat 41) e isotónicas (cat 18.1)
- **Periworkout Post**: Solo proteína polvo (cat 4), frutas (cat 11), lácteos (cat 5)
- **Frutos secos**: Máximo 30g antes de perder la proteína

### 11.4 Calibraciones
- **Cereales/Panes**: Primeros 60g cuentan P al 100%, después decrece
- **Frutos secos**: Primeros 30g cuentan P, después solo G

---

*Documento generado: Abril 2026*
*Versión: 2.0*
