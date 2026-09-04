/**
 * EL SELECTOR DE TOMAS: «Elige la foto» · «Con qué la comparas» (doc de Jesús del 2-09,
 * «Y la comparativa de fotos»; hecho el 4-09 a petición de Francisco, fase 3).
 *
 * Es el panel que abre «Elegir otra foto» en la comparativa y «Elegir otra toma» en las
 * medidas. Arriba los cuatro atajos con nombre y debajo las tomas por ciclo, que es lo que
 * pinta `ListaPorCiclo`; aquí solo se monta el panel y se traduce lo que devuelve
 * /reports/puntos a esa lista (`prepararSelector`, en lib/comparativaFotos.js).
 *
 * Se abre encima, como el visor de fotos: en el móvil sube desde abajo (una hoja) y en el
 * ordenador va centrado, igual que el recorrido de la primera vez. Se cierra con la X,
 * tocando el fondo y con Escape, y NO toca el historial (la lección del visor: un
 * pushState propio dejaba a React Router sin su índice y la app se iba al inicio).
 *
 * Al elegir se llama a `onElegir(id, detalle)`: `id` es la foto (o la toma de medidas)
 * elegida y `detalle` lo que ya sabe el selector de ella (rótulo, nota, aviso del ángulo),
 * por si quien llama no quiere volver a calcularlo. Y se cierra solo.
 *
 * @param tipo        'fotos' | 'medidas'
 * @param datos       lo de GET /reports/puntos (puede ser null mientras llega)
 * @param angulo      la pose de la foto de hoy: se prefiere esa al elegir una toma
 * @param seleccionado  la toma que hay ahora a la izquierda, para verla marcada
 * @param derechaId   la toma que ya está a la derecha (se apaga: no se compara consigo misma)
 * @param aviso       texto que sustituye a la lista cuando no hay nada que enseñar todavía
 *                    («Cargando tu histórico…», o que no se pudo cargar)
 */
import React, { useEffect, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import ListaPorCiclo from './ListaPorCiclo';
import { prepararSelector } from '../../lib/comparativaFotos';

const TEXTOS = {
    fotos: { titulo: 'Elige la foto', lead: 'Con qué la comparas:', cerrar: 'Cerrar el selector de fotos' },
    medidas: { titulo: 'Elige la toma', lead: 'Con qué la comparas:', cerrar: 'Cerrar el selector de medidas' },
};

const SelectorDeTomas = ({ tipo = 'fotos', datos = null, angulo = null, seleccionado = null, derechaId = null, aviso = null, onElegir, onCerrar }) => {
    // `onCerrar` llega nueva en cada render del padre; el efecto se ata a una ref para no
    // montarse y desmontarse en cada repintado (lo mismo que hace VisorDeFoto).
    const cerrar = useRef(onCerrar);
    cerrar.current = onCerrar;
    const t = TEXTOS[tipo] || TEXTOS.fotos;

    useEffect(() => {
        // El fondo se queda quieto mientras el selector está delante.
        const overflowPrevio = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        const conTecla = (e) => { if (e.key === 'Escape') cerrar.current?.(); };
        window.addEventListener('keydown', conTecla);
        return () => {
            document.body.style.overflow = overflowPrevio;
            window.removeEventListener('keydown', conTecla);
        };
    }, []);

    const modelo = useMemo(
        () => (datos ? prepararSelector({ tipo, datos, angulo, derechaId }) : null),
        [tipo, datos, angulo, derechaId],
    );

    const elegir = (id) => {
        onElegir?.(id, modelo ? modelo.buscar(id) : null);
        cerrar.current?.();
    };

    return createPortal(
        <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center sm:p-6"
            onClick={() => cerrar.current?.()} role="dialog" aria-modal="true" aria-label={t.titulo}
            data-testid={`selector-de-tomas-${tipo}`}>
            <div className="w-full sm:max-w-md max-h-[92dvh] overflow-y-auto bg-card border-t sm:border border-border rounded-t-3xl sm:rounded-3xl p-5 pb-7 animate-fade-in"
                onClick={(e) => e.stopPropagation()}>
                <div className="flex items-start justify-between gap-3 mb-4">
                    <div>
                        <h2 className="font-heading font-bold text-2xl uppercase tracking-tight text-foreground leading-none" data-testid="selector-titulo">
                            {t.titulo}
                        </h2>
                        <p className="text-sm text-muted-foreground mt-1.5">{t.lead}</p>
                    </div>
                    {/* 44 px de zona para el dedo, como la X del visor. */}
                    <button type="button" onClick={() => cerrar.current?.()} aria-label={t.cerrar} data-testid="selector-cerrar"
                        className="w-11 h-11 -mr-2 -mt-2 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0">
                        <X className="w-5 h-5" />
                    </button>
                </div>
                {aviso || !modelo ? (
                    <p className="text-sm text-muted-foreground" data-testid="selector-aviso">
                        {aviso || 'Todavía no hay nada que elegir.'}
                    </p>
                ) : (
                    <ListaPorCiclo atajos={modelo.atajos} grupos={modelo.grupos} seleccionado={seleccionado} onElegir={elegir} />
                )}
            </div>
        </div>,
        document.body,
    );
};

export default SelectorDeTomas;
