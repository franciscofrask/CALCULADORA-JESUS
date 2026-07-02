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
 * Filtro de categorías/preparaciones en forma de pills con iconos.
 * value string  -> single-select (click activo = deselecciona)
 * value array   -> multi-select  (click toggle in/out)
 * Cada entry: { value, label, icon? (FA/Lucide), emoji? }
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
    const btn = size === 'sm' ? 'w-8 h-8' : 'w-9 h-9';

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

    // Recorte a `maxRows` filas: altura = filas*altoPill + (filas-1)*gap (gap-1.5 = 6px).
    const wrapRef = useRef(null);
    const [expanded, setExpanded] = useState(false);
    const [overflowing, setOverflowing] = useState(false);
    const btnPx = size === 'sm' ? 32 : 36;
    const collapsedMaxH = maxRows * btnPx + (maxRows - 1) * 6;

    useEffect(() => {
        if (!collapsible) return;
        const el = wrapRef.current;
        if (!el) return;
        const check = () => setOverflowing(el.scrollHeight > collapsedMaxH + 2);
        check();
        const ro = new ResizeObserver(check);
        ro.observe(el);
        return () => ro.disconnect();
    }, [collapsible, collapsedMaxH, categories]);

    const clampStyle = (collapsible && !expanded) ? { maxHeight: collapsedMaxH, overflow: 'hidden' } : undefined;

    const pills = (
        <div ref={wrapRef} style={clampStyle} className="flex items-center gap-1.5 flex-wrap">
            {categories.map((cat) => {
                const selected = isSelected(cat.value);
                const iconNode = renderIcon(cat.icon, 'w-4 h-4');
                return (
                    <Tooltip key={cat.value || '__all__'}>
                        <TooltipTrigger asChild>
                            <button
                                type="button"
                                onClick={() => handleClick(cat.value)}
                                aria-label={cat.label}
                                aria-pressed={selected}
                                className={cn(
                                    'flex items-center justify-center rounded-full transition-all',
                                    btn,
                                    selected
                                        ? 'bg-brand-orange/10 text-brand-orange ring-2 ring-brand-orange shadow-sm'
                                        : 'bg-card text-muted-foreground border border-border hover:border-brand-orange/40 hover:text-brand-orange'
                                )}
                            >
                                {iconNode || (
                                    <span className="text-base leading-none" aria-hidden>
                                        {cat.emoji || '·'}
                                    </span>
                                )}
                            </button>
                        </TooltipTrigger>
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
            {collapsible ? (
                <div className={cn('flex items-start gap-2', className)}>
                    {label && (
                        <span className="text-xs font-bold text-muted-foreground mr-1 flex-shrink-0 mt-1.5">
                            {label}
                        </span>
                    )}
                    <div className="flex-1 min-w-0">
                        {pills}
                        {overflowing && (
                            <button
                                type="button"
                                onClick={() => setExpanded((e) => !e)}
                                className="mt-1.5 text-xs font-semibold text-brand-orange hover:underline"
                            >
                                {expanded ? 'Mostrar menos' : 'Mostrar más'}
                            </button>
                        )}
                    </div>
                </div>
            ) : (
                <div className={cn('flex items-center gap-2 flex-wrap', className)}>
                    {label && (
                        <span className="text-xs font-bold text-muted-foreground mr-1 flex-shrink-0">
                            {label}
                        </span>
                    )}
                    {pills}
                </div>
            )}
        </TooltipProvider>
    );
};

export default CategoryRail;
