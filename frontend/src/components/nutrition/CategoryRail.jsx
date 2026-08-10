import React, { useState, useRef, useEffect } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { cn } from '../../lib/utils';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';

const renderIcon = (icon, className) => {
    if (!icon) return null;
    if (typeof icon === 'object' && (icon.iconName || icon.prefix)) {
        return <FontAwesomeIcon icon={icon} className={className} />;
    }
    const C = icon;
    return <C className={className} strokeWidth={2.2} />;
};

/**
 * Filtro de categorías/preparaciones en forma de pills con icono y nombre.
 * value string  -> single-select (click activo = deselecciona)
 * value array   -> multi-select  (click toggle in/out)
 * Cada entry: { value, label, short? (nombre corto visible), icon? (FA/Lucide), emoji? }
 *
 * collapsible: si hay más categorías de las que caben en `maxRows` filas, se recortan
 * y aparece un botón "Mostrar más / Mostrar menos".
 */
const CategoryRail = ({
    label,
    categories,
    value,
    onChange,
    className,
    size = 'md',
    collapsible = false,
    maxRows = 2,
}) => {
    // Alto fijo (36/41 px) para conservar el area de toque que tenian los iconos solos;
    // el ancho lo marca el nombre, que ya no cabe en un circulo.
    const btn = size === 'sm' ? 'h-8 pl-2 pr-2.5 gap-1.5' : 'h-9 pl-2.5 pr-3 gap-1.5';

    const isArray = Array.isArray(value);
    const isSelected = (catValue) =>
        isArray ? value.includes(catValue) : value === catValue;

    const handleClick = (catValue) => {
        if (isArray) {
            if (catValue === '' || catValue == null) { onChange?.([]); return; }
            const next = value.includes(catValue)
                ? value.filter((v) => v !== catValue)
                : [...value, catValue];
            onChange?.(next);
        } else {
            onChange?.(value === catValue ? '' : catValue);
        }
    };

    // Recorte a `maxRows` filas: altura = filas*altoPill + (filas-1)*gap.
    // La pill se mide en el DOM (h-8/h-9 son rem y el html usa font-size 17/18px,
    // así que hardcodear 32/36px cortaba el anillo de la seleccionada por abajo).
    const wrapRef = useRef(null);
    const [expanded, setExpanded] = useState(false);
    const [overflowing, setOverflowing] = useState(false);
    const fallbackBtnPx = size === 'sm' ? 36 : 41;
    // +8: deja aire para el anillo (ring) de la pill seleccionada, que se dibuja FUERA del
    // borde; sin este margen el overflow:hidden del recorte lo cortaba por arriba/abajo.
    const [collapsedMaxH, setCollapsedMaxH] = useState(maxRows * fallbackBtnPx + (maxRows - 1) * 7 + 8);

    useEffect(() => {
        if (!collapsible) return;
        const el = wrapRef.current;
        if (!el) return;
        const check = () => {
            const pill = el.querySelector('button');
            const btnPx = pill ? pill.offsetHeight : fallbackBtnPx;
            const gap = parseFloat(getComputedStyle(el).rowGap) || 7;
            const maxH = maxRows * btnPx + (maxRows - 1) * gap + 8;
            setCollapsedMaxH(maxH);
            setOverflowing(el.scrollHeight > maxH + 2);
        };
        check();
        const ro = new ResizeObserver(check);
        ro.observe(el);
        return () => ro.disconnect();
    }, [collapsible, fallbackBtnPx, maxRows, categories]);

    const clampStyle = (collapsible && !expanded) ? { maxHeight: collapsedMaxH, overflow: 'hidden' } : undefined;

    const pills = (
        <div ref={wrapRef} style={clampStyle} className="flex items-center gap-1.5 flex-wrap py-1">
            {categories.map((cat) => {
                const selected = isSelected(cat.value);
                const iconNode = renderIcon(cat.icon, 'w-4 h-4 flex-shrink-0');
                return (
                    <Tooltip key={cat.value || '__all__'}>
                        <TooltipTrigger asChild>
                            <button
                                type="button"
                                onClick={() => handleClick(cat.value)}
                                aria-label={cat.label}
                                aria-pressed={selected}
                                className={cn(
                                    'inline-flex items-center justify-center rounded-full transition-all max-w-full',
                                    btn,
                                    selected
                                        ? 'bg-brand-orange/10 text-brand-orange ring-2 ring-brand-orange shadow-sm'
                                        : 'bg-card text-muted-foreground border border-border hover:border-brand-orange/40 hover:text-brand-orange'
                                )}
                            >
                                {iconNode || (
                                    <span className="text-base leading-none flex-shrink-0" aria-hidden>
                                        {cat.emoji || '·'}
                                    </span>
                                )}
                                {/* Nombre siempre visible: en móvil no hay hover, así que el tooltip
                                    no servía para saber qué es cada icono. 11px fijos (no rem) para
                                    que la tipografía base de 18px no dispare el ancho de la pill. */}
                                <span className="text-[11px] font-semibold leading-none whitespace-nowrap">
                                    {cat.short || cat.label}
                                </span>
                            </button>
                        </TooltipTrigger>
                        {/* El tooltip ya solo amplía el nombre completo con el ratón; la información
                            imprescindible está en la propia pill. */}
                        <TooltipContent
                            side="top"
                            sideOffset={6}
                            className="bg-gray-900 text-white text-xs font-semibold px-3 py-1.5 max-w-[260px] text-center"
                        >
                            {cat.label}
                        </TooltipContent>
                    </Tooltip>
                );
            })}
        </div>
    );

    return (
        <TooltipProvider delayDuration={120} skipDelayDuration={120}>
            {/* El rótulo va encima y no al lado: con el nombre dentro de cada pill, los 70 px
                que ocupaba a la izquierda le hacían falta a las pills en pantallas de 390 px. */}
            <div className={cn('min-w-0', className)}>
                {label && (
                    <span className="block text-xs font-bold text-muted-foreground">
                        {label}
                    </span>
                )}
                {pills}
                {collapsible && overflowing && (
                    <button
                        type="button"
                        onClick={() => setExpanded((e) => !e)}
                        className="mt-1 text-xs font-semibold text-brand-orange hover:underline"
                    >
                        {/* Con el número delante se sabe que hay más debajo: en móvil solo caben
                            unas seis pills en las dos filas visibles. */}
                        {expanded ? 'Ver menos' : `Ver todas (${categories.length})`}
                    </button>
                )}
            </div>
        </TooltipProvider>
    );
};

export default CategoryRail;
