import React from 'react';

// Chips legibles del desglose del motor de macros v2 (que el cliente entienda
// qué ha pasado con su cálculo). Se usan en Ajustar macros y en el quiz inicial.
const CHIP_LABELS = {
    muy_activo: () => 'Muy activo: +10% hidratos',
    deporte_extra: () => 'Otro deporte: +10% hidratos en descanso',
    casi_no_engorda: (d) => d.estado === 'aplicado' ? 'No engordas fácil: +20% hidratos'
        : d.estado === 'no_aplica_bf' ? 'Sin +20%: requiere % graso <= 20'
        : 'El +20% aún no se aplica en mujeres (guardado)',
    veto_engorda_enseguida: () => 'Engordas enseguida: sin subidas de hidratos',
    tope: () => 'Tope de subida aplicado (+30% entreno / +40% descanso)',
    farmacologia: (d) => d.estado === 'aplicado' ? '+10 g de proteína en descanso'
        : 'Farmacología guardada (aún no mueve macros)',
    farmacologia_nivelar_entreno: () => '+10 g también en entreno, para que entreno + peri siga por encima del descanso',
    dieta_reportada: (d) => d.rama === 'volumen' ? 'Dieta reportada: mismos hidratos, repartidos'
        : d.rama === 'def_ultimas' ? 'Llegas en las últimas: arranque mínimo'
        : 'Dieta reportada: primer recorte ~13%',
    suelos: (d) => `Suelos aplicados: ${(d.activados || []).join(', ')}`,
    historial_dietas: () => 'Historial guardado (aún no mueve macros)',
    // La tabla se acaba en 120 kg y 45 % (115 y 50 en mujeres). Al que se sale se le da la
    // fila del extremo, y hasta hoy pasaba en silencio. El avatar más numeroso es justo el
    // que llega gordo, así que esto se ve de verdad.
    fuera_de_tabla: (d) => d.detalle || 'Fuera de la tabla: se usa la fila del extremo',
};

const DesgloseChips = ({ desglose }) => {
    const chips = (desglose || []).filter(d => d.paso !== 'tabla' && CHIP_LABELS[d.paso]);
    if (!chips.length) return null;
    return (
        <div className="flex flex-wrap gap-1.5">
            {chips.map((d, i) => (
                <span key={i} title={d.detalle || ''}
                    className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border ${
                        d.estado === 'vetado' || d.paso === 'veto_engorda_enseguida'
                            ? 'bg-red-500/10 text-red-600 border-red-500/30'
                        /* El tope de tabla en ámbar: no es un modificador que se aplicó,
                           es un aviso de que el número se apoya en el extremo. */
                        : d.paso === 'fuera_de_tabla'
                            ? 'bg-amber-500/10 text-amber-600 border-amber-500/30'
                        : d.estado?.startsWith('no_aplica') || d.estado === 'no_aplicado'
                            ? 'bg-muted text-muted-foreground border-border'
                            : 'bg-brand/10 text-brand border-brand/30'}`}>
                    {CHIP_LABELS[d.paso](d)}
                </span>
            ))}
        </div>
    );
};

export default DesgloseChips;
