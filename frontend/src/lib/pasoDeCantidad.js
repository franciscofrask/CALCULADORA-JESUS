/**
 * DE CUÁNTO EN CUÁNTO SE MUEVEN LOS GRAMOS con los botones − y + de un ingrediente.
 *
 * EL FALLO (Francisco, 27-08): «al crear el intra, los gramos se mueven de a 1 y debería ser
 * de a 5». Y no era sólo el intra.
 *
 * Aquí había una tabla propia que decía: verduras 50, bebidas vegetales 50, salsas zero 5, y
 * **todo lo demás 1**. Pero el servidor tiene la suya (`backend/redondeo_salida.paso_en_gramos`)
 * y dice otra cosa: verduras, bebidas vegetales y konjac 50, y **todo lo demás 5**. Medido
 * contra producción, en los típicos del intra:
 *
 *     Ciclodextrina (FullGas)   cat 18.3   el botón movía 1   el servidor redondea a 5
 *     Amilopectina              cat 18.3   el botón movía 1   el servidor redondea a 5
 *     Aquarius                  cat 18.1.1 el botón movía 1   el servidor redondea a 5
 *     Palatinosa · Dextrosa     cat 18.3   el botón movía 1   el servidor redondea a 5
 *
 * O sea que el cliente subía de gramo en gramo y en cuanto la app tocaba esa cantidad -- al
 * cuadrar, al sugerir, al recalcular -- se la dejaba en un múltiplo de 5. En el intra se nota
 * más que en ningún sitio porque son polvos que se dosifican de cinco en cinco, pero pasaba en
 * la carne, en el arroz y en todo lo que no fuera verdura.
 *
 * Es la regla de Jesús del 15-08: «que todo acabe en 0 o en 5». La tenía el servidor y no la
 * tenía el botón.
 *
 * LO QUE NO SE TOCA AQUÍ: los alimentos por unidades. El servidor se mueve en MEDIAS unidades
 * -- de ahí el «desde media hamburguesa» del punto 149 -- y el botón sigue moviendo unidades
 * enteras. Cambiarlo significa poder poner medio huevo con dos toques, y eso es una decisión
 * de producto, no un arreglo. Queda dicho aquí para que no parezca un olvido.
 */

//: Se manejan en cantidades grandes, así que 50 g. El konjac (16.4) va con ellas por lo mismo,
//: no porque sea una salsa. Mismos códigos que `PASO_50` del servidor.
const PASO_50 = ['13', '24', '16.4'];

//: Salsas, polvos, carne, arroz... todo lo demás. Es `PASO_GENERAL` del servidor.
const PASO_GENERAL = 5;

const categoriasDe = (food) => {
    const crudo = food?.categorias || '';
    if (Array.isArray(crudo)) return crudo.map((c) => String(c).trim());
    return String(crudo).split('|').map((c) => c.trim());
};

// En alguno de esos códigos o en una subcategoría suya: «16.4.2» cuenta como «16.4», pero
// «16.1» no cuenta como «16» (mismo criterio que `_en_alguna` del servidor).
const enAlguna = (food, codigos) => categoriasDe(food)
    .some((token) => codigos.some((c) => token === c || token.startsWith(`${c}.`)));

/**
 * @param food        el alimento
 * @param esPorUnidad si se cuenta por unidades (lo sabe la pantalla: el campo se llama de
 *                    tres maneras distintas según por dónde haya entrado)
 * @param pesoUnidad  lo que pesa una unidad, en gramos
 */
export const pasoDeCantidad = (food, esPorUnidad, pesoUnidad) => {
    if (esPorUnidad) return pesoUnidad || PASO_GENERAL;
    if (enAlguna(food, PASO_50)) return 50;
    return PASO_GENERAL;
};
