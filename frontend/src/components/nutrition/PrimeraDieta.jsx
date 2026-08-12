import React from 'react';
import { Button } from '../ui/button';
import { ArrowRight, Clock, Utensils } from 'lucide-react';

/**
 * Paso 4 del doc del 29-07, la parte que faltaba: enseñarle su configuracion de entrenamiento
 * antes de su primera dieta.
 *
 * Las preferencias de alimentos ya se le piden aqui (PreferencesSetup a pantalla completa la
 * primera vez), que es justo donde el doc las quiere: no sirven para calcular macros, sirven
 * para generar comida.
 *
 * Lo que no se le decia es como esta repartido su dia. Sus comidas vienen colocadas para un
 * momento de entreno concreto, y si el entrena a otra hora tiene que saber que puede cambiarlo:
 * cambia el reparto, nunca los totales.
 */
const PrimeraDieta = ({ momentoEntreno, numComidas, onIrAConfig, onListo }) => {
    const COMO_ENTRENA = {
        0: 'en ayunas, antes de desayunar',
        1: 'después de la primera comida',
        2: 'después de la segunda comida',
        3: 'después de la tercera comida',
    };
    const comoEntrena = COMO_ENTRENA[momentoEntreno] ?? COMO_ENTRENA[1];

    return (
        // EN EL ORDENADOR NO TAPA LA PANTALLA (Jesus, 12-08-2026: «que la bienvenida no salga
        // tapando la pantalla»). En el movil sigue siendo lo que era -- alli no cabe otra cosa
        // y lo que hay detras no se lee igual --, pero a partir de xl se aparta a un lado, sin
        // fondo negro: se lee lo que le cuenta Y se ve la dieta de la que le esta hablando.
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4
                        xl:left-auto xl:w-[27rem] xl:justify-end xl:p-6"
            data-testid="primera-dieta">
            <div className="absolute inset-0 bg-black/70 backdrop-blur-sm xl:hidden" />
            <div className="relative bg-card rounded-2xl shadow-xl max-w-lg w-full max-h-[92vh] overflow-y-auto p-6
                            xl:border xl:border-border">
                <p className="caption text-brand mb-1">Antes de tu primera dieta</p>
                <h2 className="font-heading text-2xl font-bold uppercase text-foreground leading-tight mb-4">
                    Así está repartido tu día
                </h2>

                <div className="space-y-3 mb-6">
                    <div className="flex items-start gap-3 p-4 rounded-xl bg-muted/40 border border-border">
                        <Clock className="w-5 h-5 text-brand flex-shrink-0 mt-0.5" />
                        <div>
                            <p className="text-foreground font-semibold text-sm">Entrenas {comoEntrena}</p>
                            <p className="text-muted-foreground text-sm">
                                Tus comidas y tu perientreno están colocados para eso.
                                <strong className="text-foreground"> Si tú entrenas en otro momento, cámbialo</strong> y
                                se recoloca todo. Tus totales del día no cambian.
                            </p>
                        </div>
                    </div>
                    <div className="flex items-start gap-3 p-4 rounded-xl bg-muted/40 border border-border">
                        <Utensils className="w-5 h-5 text-brand flex-shrink-0 mt-0.5" />
                        <div>
                            <p className="text-foreground font-semibold text-sm">{numComidas || 4} comidas al día</p>
                            <p className="text-muted-foreground text-sm">
                                Sin contar el perientreno. También se cambia cuando quieras, aquí mismo.
                            </p>
                        </div>
                    </div>
                </div>

                <div className="flex flex-col sm:flex-row gap-2">
                    <Button onClick={onListo}
                        className="bg-brand hover:bg-brand/90 text-white font-bold flex-1 py-6">
                        Ver mi primera dieta <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                    <Button variant="outline" onClick={onIrAConfig} className="border-border text-foreground py-6">
                        Quiero cambiarlo
                    </Button>
                </div>
            </div>
        </div>
    );
};

export default PrimeraDieta;
