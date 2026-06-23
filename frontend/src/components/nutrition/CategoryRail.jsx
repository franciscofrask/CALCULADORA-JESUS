import React from 'react';
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
 * value string  → single-select (click activo = deselecciona)
 * value array   → multi-select  (click toggle in/out)
 * Cada entry: { value, label, icon? (FA/Lucide), emoji? }
 */
const CategoryRail = ({
    label,
    categories,
    value,
    onChange,
    className,
    size = 'md',
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

    return (
        <TooltipProvider delayDuration={120} skipDelayDuration={120}>
            <div className={cn('flex items-center gap-2 flex-wrap', className)}>
                {label && (
                    <span className="text-xs font-bold text-muted-foreground mr-1 flex-shrink-0">
                        {label}
                    </span>
                )}
                <div className="flex items-center gap-1.5 flex-wrap">
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
            </div>
        </TooltipProvider>
    );
};

export default CategoryRail;
