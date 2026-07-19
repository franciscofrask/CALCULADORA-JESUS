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
    farmacologia: () => '+10% proteína en descanso',
    dieta_reportada: (d) => d.rama === 'volumen' ? 'Dieta reportada: mismos hidratos, repartidos'
        : d.rama === 'def_ultimas' ? 'Llegas en las últimas: arranque mínimo'
        : 'Dieta reportada: primer recorte ~13%',
    suelos: (d) => `Suelos aplicados: ${(d.activados || []).join(', ')}`,
    historial_dietas: () => 'Historial guardado (aún no mueve macros)',
};

const DesgloseChips = ({ desglose }) => {
    const chips = (desglose || []).filter(d => d.paso !== 'tabla' && CHIP_LABELS[d.paso]);
    if (!chips.length) return null;
    return (
        <div className="flex flex-wrap gap-1.5">
            {chips.map((d, i) => (
                <span key={i} title={d.detalle || ''}
                    className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border ${d.estado === 'vetado' || d.paso === 'veto_engorda_enseguida' ? 'bg-red-500/10 text-red-600 border-red-500/30' : d.estado?.startsWith('no_aplica') || d.estado === 'no_aplicado' ? 'bg-muted text-muted-foreground border-border' : 'bg-brand/10 text-brand border-brand/30'}`}>
                    {CHIP_LABELS[d.paso](d)}
                </span>
            ))}
        </div>
    );
};

export default DesgloseChips;
