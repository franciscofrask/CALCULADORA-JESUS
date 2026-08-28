/**
 * Adjuntar y ver imágenes en el chat (Francisco, 25-08: «ambos chats deben permitir la
 * carga de imágenes adjuntas»).
 *
 * Vive aquí y no dentro de una de las dos pantallas porque las DOS lo usan -- la del
 * cliente (MessagesPage) y la del equipo (AdminMessagesPage) --, y un chat en el que solo
 * un lado puede mandar fotos no sirve para lo que se pide: el cliente enseña la báscula o
 * la etiqueta de un bote, y el entrenador le devuelve una captura.
 *
 * La imagen se sube ANTES de mandar el mensaje y se engancha por id. Así el que escribe ve
 * la miniatura y puede quitarla antes de enviar, y el mensaje sigue viajando como JSON.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Image as ImageIcon, X } from 'lucide-react';
import { toast } from 'sonner';

import { mensajeDeError } from '../../lib/mensajeDeError';
import { encogerImagen } from '../../lib/encogerImagen';
import VisorDeFoto from '../ui/VisorDeFoto';

export const TIPOS_ACEPTADOS = 'image/jpeg,image/png,image/webp,image/heic,image/heif';
const MAX_BYTES = 4 * 1024 * 1024;

/**
 * El binario está detrás de la sesión, así que un <img src="/api/..."> saldría roto: el
 * navegador pide esa URL sin la cabecera de autorización. Se baja con el cliente de la
 * app y se pinta desde un object URL, que además se revoca al desmontar para no dejar
 * memoria colgando en una conversación larga.
 */
export const ImagenDelMensaje = ({ api, adjunto, propio }) => {
    const [url, setUrl] = useState(null);
    const [roto, setRoto] = useState(false);
    const [ampliada, setAmpliada] = useState(false);

    useEffect(() => {
        let vivo = true;
        let creada = null;
        (async () => {
            try {
                const r = await api.get(`/messages/adjunto/${adjunto.id}`, { responseType: 'blob' });
                if (!vivo) return;
                creada = URL.createObjectURL(r.data);
                setUrl(creada);
            } catch {
                if (vivo) setRoto(true);
            }
        })();
        return () => {
            vivo = false;
            if (creada) URL.revokeObjectURL(creada);
        };
    }, [api, adjunto.id]);

    if (roto) {
        return (
            <p className={`text-xs ${propio ? 'text-white/70' : 'text-muted-foreground'}`}>
                No se pudo cargar la imagen.
            </p>
        );
    }
    if (!url) {
        return (
            <div className="w-40 h-32 rounded-lg bg-black/20 animate-pulse"
                data-testid="adjunto-cargando" />
        );
    }
    return (
        // Se abre a tamaño completo AQUÍ: dentro de la burbuja no se lee una etiqueta de
        // suplemento ni un número de báscula. Antes se abría en otra pestaña, y en el móvil
        // eso te saca de la app -- y de la conversación -- para ver una foto (Francisco,
        // 26-08). El visor la enseña encima y se cierra con el gesto de atrás.
        <>
            <button type="button" onClick={() => setAmpliada(true)} data-testid="adjunto-imagen"
                aria-label="Ver la imagen en grande" className="block active:opacity-80 transition-opacity">
                <img src={url} alt={adjunto.filename || 'Imagen adjunta'}
                    className="max-w-[240px] max-h-64 rounded-lg object-cover" />
            </button>
            {ampliada && (
                <VisorDeFoto url={url} alt={adjunto.filename || 'Imagen adjunta'}
                    pie={adjunto.filename || null} alCerrar={() => setAmpliada(false)} />
            )}
        </>
    );
};

/** El botón de clip + la miniatura de lo que se va a mandar. */
export const AdjuntarImagen = ({ api, adjunto, onAdjunto, deshabilitado }) => {
    const inputRef = useRef(null);
    const [subiendo, setSubiendo] = useState(false);

    const elegida = async (e) => {
        const original = e.target.files?.[0];
        e.target.value = '';           // que se pueda volver a elegir la misma
        if (!original) return;
        setSubiendo(true);
        try {
            // SE ENCOGE ANTES DE MIRAR EL TOPE (Francisco, 27-08: «no se pueden cargar
            // imágenes desde escritorio, sale error»). Una captura o una foto de cámara
            // guardada en el ordenador pasa de 4 MB sin esfuerzo, y se rechazaba aunque el
            // servidor fuese a dejarla en 250 KB. Ahora llega ya encogida y el tope solo
            // salta con lo que no se ha podido tocar.
            const file = await encogerImagen(original);
            if (file.size > MAX_BYTES) {
                toast.error(`La imagen pesa ${Math.round(file.size / 1024 / 1024)} MB y el máximo son 4 MB.`);
                return;
            }
            const datos = new FormData();
            datos.append('file', file);
            const r = await api.post('/messages/adjunto', datos,
                { headers: { 'Content-Type': 'multipart/form-data' } });
            onAdjunto({ ...r.data, previa: URL.createObjectURL(file) });
        } catch (error) {
            toast.error(mensajeDeError(error, 'No se pudo subir la imagen.'));
        } finally {
            setSubiendo(false);
        }
    };

    return (
        <>
            <input ref={inputRef} type="file" accept={TIPOS_ACEPTADOS} className="hidden"
                onChange={elegida} data-testid="adjunto-input" />
            <button type="button" onClick={() => inputRef.current?.click()}
                disabled={deshabilitado || subiendo || !!adjunto}
                title={adjunto ? 'Ya has adjuntado una imagen' : 'Adjuntar una imagen'}
                data-testid="adjuntar-btn"
                className="p-2 rounded-lg text-muted-foreground hover:text-brand hover:bg-brand/10 disabled:opacity-40 transition-colors">
                <ImageIcon className="w-5 h-5" />
            </button>
        </>
    );
};

/** La miniatura de lo que se va a mandar, con su aspa para quitarla. */
export const PreviaDelAdjunto = ({ adjunto, onQuitar }) => {
    useEffect(() => () => { if (adjunto?.previa) URL.revokeObjectURL(adjunto.previa); },
        [adjunto?.previa]);
    if (!adjunto) return null;
    return (
        <div className="mb-2 flex items-center gap-2" data-testid="adjunto-previa">
            <img src={adjunto.previa} alt="" className="w-14 h-14 rounded-lg object-cover" />
            <span className="text-xs text-muted-foreground truncate max-w-[160px]">
                {adjunto.filename}
            </span>
            <button type="button" onClick={onQuitar} data-testid="adjunto-quitar"
                className="p-1 rounded-md text-muted-foreground hover:text-foreground">
                <X className="w-4 h-4" />
            </button>
        </div>
    );
};
