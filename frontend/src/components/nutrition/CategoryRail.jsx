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

    // Cuando se pueden marcar varias categorias, tener el nombre abierto en todas las marcadas
    // llenaba la pantalla de cajitas superpuestas. Solo se queda abierta la ultima que has tocado.
    const [ultima, setUltima] = useState(null);

    const handleClick = (catValue) => {
        if (isArray) {
            if (catValue === '' || catValue == null) { onChange?.([]); setUltima(null); return; }
            const quitando = value.includes(catValue);
            const next = quitando
                ? value.filter((v) => v !== catValue)
                : [...value, catValue];
            setUltima(quitando ? null : catValue);
            onChange?.(next);
        } else {
            onChange?.(value === catValue ? '' : catValue);
        }
    };

    // Cual lleva el nombre visible. En seleccion simple, la unica marcada (como hasta ahora).
    // En multiple, la ultima tocada; si se quito, la ultima que quede marcada, para que al
    // volver a la pantalla con filtros ya puestos siga viendose uno.
    const destacada = !isArray
        ? (value || null)
        : (ultima && value.includes(ultima)
            ? ultima
            : (value.length ? value[value.length - 1] : null));

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

    // El nombre de la categoría marcada se queda visible: en tablet y móvil no hay ratón, así
    // que sin esto no se puede saber qué categoría está aplicada. El resto se abren y cierran
    // con el ratón como siempre (`abierta` guarda cuál lo está).
    const [abierta, setAbierta] = useState(null);

    const pills = (
        <div ref={wrapRef} style={clampStyle} className="flex items-center gap-1.5 flex-wrap py-1">
            {categories.map((cat) => {
                const selected = isSelected(cat.value);
                const iconNode = renderIcon(cat.icon, 'w-4 h-4');
                return (
                    <Tooltip
                        key={cat.value || '__all__'}
                        open={destacada === cat.value || abierta === cat.value}
                        onOpenChange={(o) => setAbierta(o ? cat.value : null)}
                    >
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
