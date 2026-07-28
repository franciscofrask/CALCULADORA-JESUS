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
    // En movil y tablet no hay raton, asi que el tooltip no se puede ver: la pill lleva
    // el nombre debajo del icono y se muestra siempre. A partir de lg vuelve al circulo
    // con tooltip, que es donde si hay hover.
    const btn = size === 'sm'
        ? 'w-[5.25rem] lg:w-8 lg:h-8'
        : 'w-[5.5rem] lg:w-9 lg:h-9';

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
    // La pill se mide en el DOM (w-8/w-9 son rem y el html usa font-size 17/18px,
    // así que hardcodear 32/36px cortaba el anillo de la seleccionada por abajo).
    const wrapRef = useRef(null);
    const [expanded, setExpanded] = useState(false);
    const [overflowing, setOverflowing] = useState(false);
    const fallbackBtnPx = size === 'sm' ? 36 : 41;
    // +8: deja aire para el anillo (ring) de la pill seleccionada, que se dibuja FUERA del
    // círculo; sin este margen el overflow:hidden del recorte lo cortaba por arriba/abajo.
    const [collapsedMaxH, setCollapsedMaxH] = useState(maxRows * fallbackBtnPx + (maxRows - 1) * 7 + 8);

    useEffect(() => {
        if (!collapsible) return;
        const el = wrapRef.current;
        if (!el) return;
        const check = () => {
            // Las pills ya no miden todas igual (en movil llevan el nombre debajo y
            // pueden ocupar una linea o tres), asi que la altura del recorte se mide
            // sobre las filas reales: se corta justo despues de la fila `maxRows`.
            const pills = [...el.querySelectorAll('button')];
            if (!pills.length) return;
            // Medidas relativas al propio contenedor (offsetTop lo es a otro ancestro).
            const base = el.getBoundingClientRect().top;
            const top = (p) => Math.round(p.getBoundingClientRect().top - base);
            const filas = [...new Set(pills.map(top))].sort((a, b) => a - b);
            if (filas.length <= maxRows) {
                setOverflowing(false);
                return;
            }
            const dentro = pills.filter((p) => filas.indexOf(top(p)) < maxRows);
            const abajo = Math.max(...dentro.map((p) => p.getBoundingClientRect().bottom - base));
            // +8 de aire para el anillo (ring) de la pill seleccionada, que se dibuja
            // fuera del boton, pero sin llegar a dejar asomar la fila siguiente.
            const maxH = Math.min(abajo + 8, filas[maxRows] - 2);
            setCollapsedMaxH(maxH);
            setOverflowing(true);
        };
        check();
        const ro = new ResizeObserver(check);
        ro.observe(el);
        return () => ro.disconnect();
    }, [collapsible, fallbackBtnPx, maxRows, categories]);

    const clampStyle = (collapsible && !expanded) ? { maxHeight: collapsedMaxH, overflow: 'hidden' } : undefined;

    const pills = (
        // items-stretch en movil: las pills de una misma fila igualan altura aunque el
        // nombre ocupe una linea o tres.
        <div ref={wrapRef} style={clampStyle} className="flex items-stretch lg:items-center gap-1.5 flex-wrap py-1">
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
                                    'flex flex-col lg:flex-row items-center justify-center gap-0.5 lg:gap-0 transition-all',
                                    // min-h para que todas las pills midan igual aunque el
                                    // nombre ocupe una linea o dos
                                    'px-1 py-1.5 lg:p-0 rounded-xl lg:rounded-full min-h-[3.4rem] lg:min-h-0',
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
                                {/* El nombre completo, siempre visible en movil y tablet */}
                                <span className="lg:hidden text-[10px] leading-tight text-center w-full px-0.5 break-words">
                                    {cat.label}
                                </span>
                            </button>
                        </TooltipTrigger>
                        <TooltipContent
                            side="top"
                            sideOffset={6}
                            className="hidden lg:block bg-gray-900 text-white text-xs font-semibold px-3 py-1.5 max-w-[260px] text-center"
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
