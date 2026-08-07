# Mínimos por categoría - para repasar con Jesús

Punto 5 del documento del 7 de agosto.

El mapa ya existe en la app (`backend/calma_suggest.py`, `Z_MIN`): son 56 categorías
portadas de la calculadora antigua. Lo que falta es que Jesús revise los valores, que
es lo que él mismo calcula en media hora.

Cada número es la cantidad más pequeña que se le puede poner a un cliente de esa
categoría. Por debajo de ahí el alimento se descarta, ya no se queda a cero.

El ejemplo que pone en el documento son los copos de avena: salen a 10 g, que es una
cucharada, porque la categoría 7 tiene ese mínimo. De los cuatro valores que nombra,
tres ya coincidían (aceites 5 g, verduras 50 g, bebidas vegetales 100 g) y el de los
frutos secos ya está corregido de 5 a 10 g.

La última columna es para que apunte el valor nuevo donde quiera cambiarlo.

| Categoría | Qué es | Mínimo hoy | Lo cambio a |
|---|---|---|---|
| 1.1 | Claras de huevo y derivados | 25 g | |
| 2 | Carnes | 50 g | |
| 2.1 | Embutidos | 25 g | |
| 3 | Pescados y mariscos | 50 g | |
| 4 | Proteínas en polvo | 5 g | |
| 5.1 | Leche | 20 g | |
| 5.2 | Yogures y derivados | 50 g | |
| 5.3 | Quesos | 20 g | |
| 5.6 | Batidos comerciales | 100 g | |
| 6.1 | Leche de Soja | 20 g | |
| 6.2 | Otros derivados de la soja | 50 g | |
| 7 | Cereales (excepto arroz) | 10 g | |
| 7.2 | Harinas de cereales | 25 g | |
| 7.3 | Maíz, espelta y otros cereales (no harinas ni tortitas) | 25 g | |
| 7.6 | Tortillas de maíz y otros cereales (excepto trigo) | 10 g | |
| 8 | Panes y tortillas de trigo | 25 g | |
| 8.4 | Picatostes y pan tostado normal | 15 g | |
| 9 | Tubérculos y derivados | 25 g | |
| 10.2 | Legumbres crudas | 25 g | |
| 10.3 | Legumbres | 25 g | |
| 11 | Fruta, zumo, potitos y mermeladas | 50 g | |
| 11.3 | Fruta, zumo, potitos y mermeladas | 10 g | |
| 11.5 | Zumos y derivados | 100 g | |
| 11.7 | Frutas secas | 25 g | |
| 11.9 | Mermeladas | 10 g | |
| 13 | Verduras y hortalizas | 50 g | |
| 15 | - | 5 g | |
| 16 | Salsas, siropes y konjac | 5 g | |
| 16.1 | Salsas o siropes zero o muy bajas en kcal | 10 g | |
| 16.4 | Konjac y derivados | 50 g | |
| 17 | Alimentos ricos en grasas de todo tipo | 5 g | |
| 17.1.2 | Aceitunas | 25 g | |
| 17.2 | Frutos secos (naturales o cremas) y semillas | 10 g (ya corregido) | |
| 17.6 | Aguacate y derivados | 25 g | |
| 17.7 | Cremas vegetales | 25 g | |
| 17.9 | Croquetas | 50 g | |
| 18 | Intraentrenamiento | 100 g | |
| 18.3 | Hidratos de carbono en polvo para entrenar | 5 g | |
| 18.4 | Intraentrenamiento | 5 g | |
| 19 | Bebidas energéticas, refrescos y cafés | 100 g | |
| 19.3.3 | Café en polvo | 5 g | |
| 21 | Arroces y derivados | 25 g | |
| 21.3 | Cremas de arroz y harinas de arroz | 10 g | |
| 22 | Pasta, quinoa y derivados | 25 g | |
| 24 | Bebidas vegetales | 100 g | |
| 25 | Postentreno | 5 g | |
| 27 | Sustitutivos de comidas | 10 g | |
| 28 | Proteína vegetal | 50 g | |
| 32 | Pizza, lasaña, empanadas y empanadillas | 50 g | |
| 34 | Chocolates y chocolatinas | 20 g | |
| 35 | Helados | 20 g | |
| 36 | Postres | 50 g | |
| 37 | Cacao en polvo y azúcares de todo tipo, chucherías y miel | 5 g | |
| 38 | Aperitivos | 25 g | |
| 39 | Cocina tradicional española | 50 g | |
| 41 | Aminoacidos para entrenar | 5 g | |
| 43 | Bollería, galletas, barritas energéticas, chocolate y chocolatinas | 20 g | |
| *(las demás)* | lo que no está en esta lista | 5 g | |
