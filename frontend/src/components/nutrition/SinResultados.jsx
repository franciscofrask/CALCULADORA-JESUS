import React from 'react';

/**
 * CUANDO NO ENCUENTRA EL ALIMENTO (punto 144 del 27-08).
 *
 * Había dos textos distintos para lo mismo: «Sin resultados» en la pantalla de Alimentos y
 * «No se encontraron alimentos» dentro de una comida. Ninguno de los dos decía que se pueda
 * pedir, y los dos suenan a que ha buscado mal.
 *
 * «No lo tenemos» dice de quién es el problema, y le da las dos salidas que existen -- buscar
 * distinto o coger otro -- antes de mencionar pedirlo. Y lo de pedirlo va el último y en
 * gris: que se pueda, pero que no sea lo primero que se le ocurra.
 *
 * VIVE AQUÍ Y NO EN CADA PANTALLA porque el punto dice «igual en los dos sitios»: con el
 * texto escrito dos veces, el día que se cambie uno se quedará el otro. Lo usan
 * `pages/FoodSearchPage` y `components/nutrition/BuildMealModal`.
 */
const SinResultados = () => (
    <div className="text-center py-12 px-4" data-testid="sin-resultados">
        <p className="text-sm text-foreground font-medium">No lo tenemos.</p>
        <p className="text-sm text-muted-foreground mt-1">
            Prueba con otro nombre, o coge uno parecido de la lista.
        </p>
        <p className="text-xs text-muted-foreground mt-3">
            ¿Sigue sin estar? Puedes pedirlo desde Alimentos.
        </p>
    </div>
);

export default SinResultados;
