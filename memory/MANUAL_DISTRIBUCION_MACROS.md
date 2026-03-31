# MANUAL COMPLETO: Distribución de Macros — Método Jesús Gallego

Este documento contiene TODAS las tablas y reglas de distribución de macros implementadas en `macro_distribution.py`.

---

## RESUMEN DE LA LÓGICA

```
Día de Entrenamiento:
├── Macros COMIDAS: p_entreno, h_entreno, g_entreno
├── Macros PERIWORKOUT: p_peri, h_peri (sin grasa)
│
├── 4 comidas → Usa escenarios de H (E1, E2, E3, E4)
│   └── Escenario depende de h_entreno (no h_peri)
│
└── 3 comidas → Reparto equitativo 33.3% (sin escenarios)

Día de Descanso:
├── Macros: p_descanso, h_descanso, g_descanso
├── SIN periworkout
└── Reparto equitativo entre todas las comidas
```

---

## 1. LOS 4 ESCENARIOS DE HIDRATOS (Solo día entrenamiento, 4 comidas)

| Escenario | Rango de H | Descripción |
|-----------|------------|-------------|
| **E1** | H > 150g | Muchos hidratos → reparto generoso |
| **E2** | 100-150g | Moderados → concentración cerca del entreno |
| **E3** | 50-100g | Pocos → 20g fijos lejos, resto 50/50 cerca |
| **E4** | H < 50g | Muy pocos → todo al post, 10g al pre |

---

### ESCENARIO 1: H > 150g

#### Tabla de Porcentajes (P%, H%, G%)

| Momento | C1 | C2 | C3 | C4 |
|---------|-----|-----|-----|-----|
| **0** (Ayunas) | 25/30/20 | 25/20/25 | 20/20/25 | 30/30/30 |
| **1** (Después C1) | 25/30/20 | 25/30/20 | 20/20/30 | 30/20/30 |
| **2** (Después C2) | 25/20/30 | 20/30/20 | 25/30/20 | 30/20/30 |
| **3** (Después C3) | 30/20/30 | 25/20/30 | 20/30/20 | 25/30/20 |

**Ejemplo E1:** P=180g, H=250g, G=65g, Momento=1 (entreno después de C1)

| Comida | P (%) | P (g) | H (%) | H (g) | G (%) | G (g) |
|--------|-------|-------|-------|-------|-------|-------|
| C1 | 25% | 45.0 | 30% | 75.0 | 20% | 13.0 |
| C2 | 25% | 45.0 | 30% | 75.0 | 20% | 13.0 |
| C3 | 20% | 36.0 | 20% | 50.0 | 30% | 19.5 |
| C4 | 30% | 54.0 | 20% | 50.0 | 30% | 19.5 |
| **TOTAL** | 100% | **180.0** | 100% | **250.0** | 100% | **65.0** |

---

### ESCENARIO 2: 100-150g H

#### Tabla de Porcentajes (P%, H%, G%)

| Momento | C1 | C2 | C3 | C4 |
|---------|-----|-----|-----|-----|
| **0** (Ayunas) | 25/36/20 | 25/18/25 | 20/10/25 | 30/36/30 |
| **1** (Después C1) | 25/36/20 | 25/36/20 | 20/18/30 | 30/10/30 |
| **2** (Después C2) | 25/18/30 | 20/36/20 | 25/36/20 | 30/10/30 |
| **3** (Después C3) | 30/10/30 | 25/18/30 | 20/36/20 | 25/36/20 |

**Ejemplo E2:** P=180g, H=120g, G=65g, Momento=0 (entreno en ayunas)

| Comida | P (%) | P (g) | H (%) | H (g) | G (%) | G (g) |
|--------|-------|-------|-------|-------|-------|-------|
| C1 | 25% | 45.0 | 36% | 43.2 | 20% | 13.0 |
| C2 | 25% | 45.0 | 18% | 21.6 | 25% | 16.25 |
| C3 | 20% | 36.0 | 10% | 12.0 | 25% | 16.25 |
| C4 | 30% | 54.0 | 36% | 43.2 | 30% | 19.5 |
| **TOTAL** | 100% | **180.0** | 100% | **120.0** | 100% | **65.0** |

---

### ESCENARIO 3: 50-100g H

**Regla especial:**
1. Restar 20g del total de H
2. Esos 20g → 10g + 10g a las 2 comidas MÁS LEJOS del entreno
3. El resto (h_total - 20) → 50/50 entre las 2 comidas MÁS CERCA del entreno
4. P y G usan los mismos % que Escenario 1

#### Tabla de distribución de H (en gramos, no porcentajes)

| Momento | Cerca entreno | Lejos entreno | C1 H | C2 H | C3 H | C4 H |
|---------|--------------|---------------|------|------|------|------|
| **0** (Ayunas) | C1, C4 | C2, C3 | (H-20)/2 | 10 | 10 | (H-20)/2 |
| **1** (Después C1) | C1, C2 | C3, C4 | (H-20)/2 | (H-20)/2 | 10 | 10 |
| **2** (Después C2) | C2, C3 | C1, C4 | 10 | (H-20)/2 | (H-20)/2 | 10 |
| **3** (Después C3) | C3, C4 | C1, C2 | 10 | 10 | (H-20)/2 | (H-20)/2 |

**Ejemplo E3:** P=180g, H=80g, G=65g, Momento=1 (entreno después de C1)

```
H restante = 80 - 20 = 60g
H por comida cercana = 60 / 2 = 30g
Comidas cercanas (momento 1): C1 y C2
Comidas lejanas: C3 y C4
```

| Comida | P (E1%) | P (g) | H | H (g) | G (E1%) | G (g) |
|--------|---------|-------|---|-------|---------|-------|
| C1 | 25% | 45.0 | cercana | 30.0 | 20% | 13.0 |
| C2 | 25% | 45.0 | cercana | 30.0 | 20% | 13.0 |
| C3 | 20% | 36.0 | lejana | 10.0 | 30% | 19.5 |
| C4 | 30% | 54.0 | lejana | 10.0 | 30% | 19.5 |
| **TOTAL** | 100% | **180.0** | — | **80.0** | 100% | **65.0** |

---

### ESCENARIO 4: H < 50g

**Regla especial:**
1. 10g van a la 2ª comida más importante (pre-entreno)
2. Todo el resto (h_total - 10) va a la comida principal (post-entreno)
3. Resto de comidas = 0g H
4. P y G usan los mismos % que Escenario 1

#### Tabla de distribución de H (en gramos)

| Momento | Principal (post) | Secundaria (pre) | C1 H | C2 H | C3 H | C4 H |
|---------|-----------------|------------------|------|------|------|------|
| **0** (Ayunas) | C1 | C4 | H-10 | 0 | 0 | 10 |
| **1** (Después C1) | C2 | C1 | 10 | H-10 | 0 | 0 |
| **2** (Después C2) | C3 | C2 | 0 | 10 | H-10 | 0 |
| **3** (Después C3) | C4 | C3 | 0 | 0 | 10 | H-10 |

**Ejemplo E4:** P=180g, H=40g, G=65g, Momento=2 (entreno después de C2)

```
Comida principal (post-entreno): C3 → recibe 40 - 10 = 30g H
Comida secundaria (pre-entreno): C2 → recibe 10g H
C1 y C4: 0g H
```

| Comida | P (E1%) | P (g) | H | H (g) | G (E1%) | G (g) |
|--------|---------|-------|---|-------|---------|-------|
| C1 | 25% | 45.0 | — | 0.0 | 30% | 19.5 |
| C2 | 20% | 36.0 | pre | 10.0 | 20% | 13.0 |
| C3 | 25% | 45.0 | post | 30.0 | 20% | 13.0 |
| C4 | 30% | 54.0 | — | 0.0 | 30% | 19.5 |
| **TOTAL** | 100% | **180.0** | — | **40.0** | 100% | **65.0** |

---

## 2. LAS 4 OPCIONES DE PERIWORKOUT

El periworkout usa macros SEPARADOS: `p_peri` y `h_peri` (sin grasa).

| Opción | Descripción | Intra | Post | Extra a comidas |
|--------|-------------|-------|------|-----------------|
| **intra_post** | Intra + Post entreno | 20%P, 30%H | 80%P, 70%H | 0 |
| **solo_post** | Solo shake post | — | 100%P, 100%H | 0 |
| **solo_intra** | Solo bebida intra | 25%P, 35%H | — | 75%P, 65%H |
| **sin_peri** | Sin periworkout | — | — | 100%P, 100%H |

### Detalle de cada opción:

#### INTRA_POST (opción por defecto)
```
Intra-entreno:
  P = p_peri × 20% 
  H = h_peri × 30%
  G = 0

Post-entreno:
  P = p_peri × 80%
  H = h_peri × 70%
  G = 0

Extra a comidas: 0
```

**Ejemplo:** p_peri=40g, h_peri=30g
| Momento | P | H | G |
|---------|---|---|---|
| Intra | 8.0g | 9.0g | 0 |
| Post | 32.0g | 21.0g | 0 |
| **Total peri** | **40.0g** | **30.0g** | **0** |

---

#### SOLO_POST
```
Post-entreno:
  P = p_peri × 100%
  H = h_peri × 100%
  G = 0

Intra: No existe
Extra a comidas: 0
```

**Ejemplo:** p_peri=40g, h_peri=30g
| Momento | P | H | G |
|---------|---|---|---|
| Post | 40.0g | 30.0g | 0 |
| **Total peri** | **40.0g** | **30.0g** | **0** |

---

#### SOLO_INTRA
```
Intra-entreno:
  P = p_peri × 25%
  H = h_peri × 35%
  G = 0

Post: No existe

Extra a comidas (se reparte equitativamente):
  P = p_peri × 75%
  H = h_peri × 65%
```

**Ejemplo:** p_peri=40g, h_peri=30g, 4 comidas
| Concepto | P | H |
|----------|---|---|
| Intra | 10.0g | 10.5g |
| Extra total | 30.0g | 19.5g |
| Extra por comida | 7.5g | 4.875g |

---

#### SIN_PERI
```
Intra: No existe
Post: No existe

Extra a comidas (se reparte equitativamente):
  P = p_peri × 100%
  H = h_peri × 100%
```

**Ejemplo:** p_peri=40g, h_peri=30g, 4 comidas
| Concepto | P | H |
|----------|---|---|
| Extra total | 40.0g | 30.0g |
| Extra por comida | 10.0g | 7.5g |

---

## 3. LOS 4 MOMENTOS DE ENTRENAMIENTO

| Valor | Descripción | Pre-entreno | Post-entreno |
|-------|-------------|-------------|--------------|
| **0** | En ayunas | (noche anterior) | C1 |
| **1** | Después de C1 | C1 | C2 |
| **2** | Después de C2 | C2 | C3 |
| **3** | Después de C3 | C3 | C4 |

**Cómo afecta al reparto:**
- Las comidas CERCA del entreno (pre y post) reciben MÁS hidratos
- Las comidas LEJOS del entreno reciben MENOS hidratos
- En E1 y E2: los % cambian según la tabla
- En E3: las 2 cercanas se llevan (H-20)/2 cada una, las lejanas 10g cada una
- En E4: el post se lleva todo menos 10g, el pre se lleva 10g

---

## 4. DÍA DE ENTRENAMIENTO vs DÍA DE DESCANSO

### Día de ENTRENAMIENTO
- Usa: `p_entreno`, `h_entreno`, `g_entreno` + `p_peri`, `h_peri`
- Aplica escenarios E1-E4 según hidratos
- Tiene periworkout (Intra/Post)
- Distribución variable según momento de entreno

### Día de DESCANSO
- Usa: `p_descanso`, `h_descanso`, `g_descanso`
- **SIN periworkout**
- **Reparto EQUITATIVO** entre todas las comidas
- No importa el momento de entreno (se ignora)

**Fórmula día descanso:**
```
Cada comida = Total / num_comidas

Con 4 comidas: cada una recibe 25% de P, H y G
Con 3 comidas: cada una recibe 33.3% de P, H y G
```

**Ejemplo:** p_descanso=180g, h_descanso=200g, g_descanso=65g, 4 comidas

| Comida | P (%) | P (g) | H (%) | H (g) | G (%) | G (g) |
|--------|-------|-------|-------|-------|-------|-------|
| C1 | 25% | 45.0 | 25% | 50.0 | 25% | 16.25 |
| C2 | 25% | 45.0 | 25% | 50.0 | 25% | 16.25 |
| C3 | 25% | 45.0 | 25% | 50.0 | 25% | 16.25 |
| C4 | 25% | 45.0 | 25% | 50.0 | 25% | 16.25 |
| **TOTAL** | 100% | **180.0** | 100% | **200.0** | 100% | **65.0** |

---

## 5. 3 COMIDAS vs 4 COMIDAS

### Con 4 COMIDAS (día entrenamiento)
- Se aplican los escenarios E1-E4 según hidratos
- Distribución variable según momento de entreno
- Tablas completas de porcentajes

### Con 3 COMIDAS (día entrenamiento)
- **NO se aplican escenarios de H**
- Reparto EQUITATIVO 33.3% cada comida
- El periworkout SÍ se aplica (Intra/Post)

**Fórmula 3 comidas entrenamiento:**
```
C1 = C2 = C3 = Total / 3

P: 33.3% cada comida
H: 33.3% cada comida
G: 33.3% cada comida
```

**Ejemplo:** p_entreno=180g, h_entreno=250g, g_entreno=65g, 3 comidas, intra_post

| Comida | P | H | G |
|--------|---|---|---|
| C1 | 60.0g | 83.3g | 21.7g |
| C2 | 60.0g | 83.3g | 21.7g |
| C3 | 60.0g | 83.3g | 21.7g |
| **Total comidas** | 180.0g | 250.0g | 65.0g |
| Intra | 8.0g | 9.0g | 0 |
| Post | 32.0g | 21.0g | 0 |
| **TOTAL DÍA** | **220.0g** | **280.0g** | **65.0g** |

---

## 6. EJEMPLOS RESUELTOS COMPLETOS

### Ejemplo 1: E1, Momento 1, 4 comidas, intra_post
```
Macros: p_entreno=180, h_entreno=250, g_entreno=65, p_peri=40, h_peri=30
Escenario: E1 (H > 150g)
Momento: 1 (entreno después de C1)
```

**Resultado:**
| Comida | P | H | G |
|--------|---|---|---|
| C1 | 45.0g | 75.0g | 13.0g |
| C2 | 45.0g | 75.0g | 13.0g |
| C3 | 36.0g | 50.0g | 19.5g |
| C4 | 54.0g | 50.0g | 19.5g |
| Intra | 8.0g | 9.0g | 0g |
| Post | 32.0g | 21.0g | 0g |
| **TOTAL** | **220.0g** | **280.0g** | **65.0g** |

---

### Ejemplo 2: E2, Momento 0, 4 comidas, solo_post
```
Macros: p_entreno=180, h_entreno=120, g_entreno=65, p_peri=40, h_peri=30
Escenario: E2 (100-150g H)
Momento: 0 (entreno en ayunas)
```

**Resultado:**
| Comida | P | H | G |
|--------|---|---|---|
| C1 | 45.0g | 43.2g | 13.0g |
| C2 | 45.0g | 21.6g | 16.25g |
| C3 | 36.0g | 12.0g | 16.25g |
| C4 | 54.0g | 43.2g | 19.5g |
| Post | 40.0g | 30.0g | 0g |
| **TOTAL** | **220.0g** | **150.0g** | **65.0g** |

---

### Ejemplo 3: E3, Momento 2, 4 comidas, intra_post
```
Macros: p_entreno=180, h_entreno=80, g_entreno=65, p_peri=40, h_peri=30
Escenario: E3 (50-100g H)
Momento: 2 (entreno después de C2)
Comidas cercanas: C2, C3 → (80-20)/2 = 30g cada una
Comidas lejanas: C1, C4 → 10g cada una
```

**Resultado:**
| Comida | P | H | G |
|--------|---|---|---|
| C1 | 45.0g | 10.0g | 19.5g |
| C2 | 36.0g | 30.0g | 13.0g |
| C3 | 45.0g | 30.0g | 13.0g |
| C4 | 54.0g | 10.0g | 19.5g |
| Intra | 8.0g | 9.0g | 0g |
| Post | 32.0g | 21.0g | 0g |
| **TOTAL** | **220.0g** | **110.0g** | **65.0g** |

---

### Ejemplo 4: E4, Momento 3, 4 comidas, solo_intra
```
Macros: p_entreno=180, h_entreno=40, g_entreno=65, p_peri=40, h_peri=30
Escenario: E4 (H < 50g)
Momento: 3 (entreno después de C3)
Comida principal (post): C4 → 40-10 = 30g H
Comida secundaria (pre): C3 → 10g H
Solo_intra: Intra=25%/35%, resto a comidas (75%/65%)
  Extra por comida: 30/4=7.5P, 19.5/4=4.875H
```

**Resultado:**
| Comida | P base | P extra | P total | H base | H extra | H total | G |
|--------|--------|---------|---------|--------|---------|---------|---|
| C1 | 54.0g | 7.5g | 61.5g | 0g | 4.875g | 4.875g | 19.5g |
| C2 | 45.0g | 7.5g | 52.5g | 0g | 4.875g | 4.875g | 19.5g |
| C3 | 36.0g | 7.5g | 43.5g | 10g | 4.875g | 14.875g | 13.0g |
| C4 | 45.0g | 7.5g | 52.5g | 30g | 4.875g | 34.875g | 13.0g |
| Intra | — | — | 10.0g | — | — | 10.5g | 0g |
| **TOTAL** | — | — | **220.0g** | — | — | **70.0g** | **65.0g** |

---

### Ejemplo 5: Día descanso, 4 comidas
```
Macros: p_descanso=180, h_descanso=200, g_descanso=65
Sin periworkout
Reparto equitativo: 25% cada comida
```

**Resultado:**
| Comida | P | H | G |
|--------|---|---|---|
| C1 | 45.0g | 50.0g | 16.25g |
| C2 | 45.0g | 50.0g | 16.25g |
| C3 | 45.0g | 50.0g | 16.25g |
| C4 | 45.0g | 50.0g | 16.25g |
| **TOTAL** | **180.0g** | **200.0g** | **65.0g** |

---

### Ejemplo 6: Día descanso, 3 comidas
```
Macros: p_descanso=180, h_descanso=150, g_descanso=60
Sin periworkout
Reparto equitativo: 33.3% cada comida
```

**Resultado:**
| Comida | P | H | G |
|--------|---|---|---|
| C1 | 60.0g | 50.0g | 20.0g |
| C2 | 60.0g | 50.0g | 20.0g |
| C3 | 60.0g | 50.0g | 20.0g |
| **TOTAL** | **180.0g** | **150.0g** | **60.0g** |

---

### Ejemplo 7: 3 comidas entrenamiento, sin_peri
```
Macros: p_entreno=180, h_entreno=250, g_entreno=65, p_peri=40, h_peri=30
3 comidas: reparto equitativo 33.3%
sin_peri: todo el peri va a comidas (40P/30H repartido entre 3)
  Extra por comida: 40/3=13.3P, 30/3=10H
```

**Resultado:**
| Comida | P base | P extra | P total | H base | H extra | H total | G |
|--------|--------|---------|---------|--------|---------|---------|---|
| C1 | 60.0g | 13.3g | 73.3g | 83.3g | 10.0g | 93.3g | 21.7g |
| C2 | 60.0g | 13.3g | 73.3g | 83.3g | 10.0g | 93.3g | 21.7g |
| C3 | 60.0g | 13.3g | 73.3g | 83.3g | 10.0g | 93.3g | 21.7g |
| **TOTAL** | — | — | **220.0g** | — | — | **280.0g** | **65.0g** |

---

## 7. VERIFICACIÓN AUTOMÁTICA

Ejecutar los tests:
```bash
cd /app/backend && python macro_distribution.py
```

Esto ejecuta 10 tests que verifican:
1. Escenario 1 con todas las opciones
2. Día de descanso equitativo
3. 3 comidas equitativo
4. Solo post
5. Sin periworkout
6. Solo intra
7. Escenario 3 (50-100H)
8. Escenario 4 (<50H)
9. Escenario 2 (100-150H)
10. Totales cuadran correctamente

---

## 8. CÓDIGO RELEVANTE

### Función principal: `distribuir_macros()`
```python
def distribuir_macros(
    p_entreno, h_entreno, g_entreno,    # Macros día entreno
    p_peri, h_peri,                      # Macros periworkout
    p_descanso, h_descanso, g_descanso,  # Macros día descanso
    tipo_dia,         # "entrenamiento" o "descanso"
    num_comidas,      # 3 o 4
    momento_entreno,  # 0, 1, 2, 3
    opcion_peri       # "intra_post", "solo_post", "solo_intra", "sin_peri"
) -> Dict
```

### Diccionarios de distribución:
- `DIST_E1`: Tablas para H > 150g
- `DIST_E2`: Tablas para 100-150g H
- `_distribuir_escenario_3()`: Lógica especial para 50-100g H
- `_distribuir_escenario_4()`: Lógica especial para <50g H

---

*Documento generado el 31/03/2026*
