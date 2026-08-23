/**
 * Las tres fotos del reporte: frente, espalda y perfil, relajado.
 *
 * Se subían en los check-ins, que es donde se VEN, no donde se piden. Ahora hay un solo
 * sitio para subirlas -- el reporte -- y la rejilla de check-ins se queda para mirarlas.
 *
 * Debajo de cada hueco va la del mes pasado en pequeño. No es decoración: es para que se
 * coloque igual (misma distancia, misma luz, mismo sitio), que es lo único que hace que
 * dos fotos de meses distintos se puedan comparar.
 *
 * Y las indicaciones escritas, siempre a la vista. OJO: los textos de abajo son un
 * resumen mío. Los buenos están en el Typeform y en el Google Form del reporte, en la
 * descripción de cada campo, y NO están en los .docx exportados: hay que sacarlos del
 * formulario en vivo. Cuando lleguen, se cambian aquí y ya.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Camera, Loader2, Check } from 'lucide-react';
import { mensajeDeError } from '../../lib/mensajeDeError';

const POSES = [
    { key: 'frente', label: 'De frente', ayuda: 'Brazos relajados a los lados, de pie y recto. Sin meter tripa.' },
    { key: 'espalda', label: 'De espaldas', ayuda: 'La misma postura, dándole la espalda a la cámara.' },
    { key: 'perfil', label: 'De perfil', ayuda: 'De lado, brazos relajados, sin girar el cuerpo hacia la cámara.' },
];

// `onSubida` es opcional: avisa a la pantalla de fuera de que hay una foto nueva, para
// que su propia lista (la rejilla de fotos de progreso) no se quede desfasada.
const TresFotos = ({ api, token, esMensual = true, onSubida }) => {
    const [fotos, setFotos] = useState([]);
    const [subiendo, setSubiendo] = useState(null);
    const [urls, setUrls] = useState({});

    const cargar = useCallback(() => {
        api.get('/reports/photos').then(r => setFotos(r.data?.photos || [])).catch(() => {});
    }, [api]);
    useEffect(() => { cargar(); }, [cargar]);

    // La última de cada pose: es la referencia contra la que se coloca hoy.
    const ultimaDe = (pose) => (fotos || [])
        .filter(f => f.pose === pose)
        .sort((a, b) => String(b.taken_at).localeCompare(String(a.taken_at)))[0];

    // Las fotos van con la sesión, así que se piden con el token y se pintan desde el blob.
    useEffect(() => {
        let vivo = true;
        const base = process.env.REACT_APP_BACKEND_URL || '';
        POSES.forEach(({ key }) => {
            const f = ultimaDe(key);
            if (!f || urls[f.id]) return;
            fetch(`${base}/api/reports/photos/${f.id}`, { headers: { Authorization: `Bearer ${token}` } })
                .then(r => (r.ok ? r.blob() : Promise.reject()))
                .then(b => { if (vivo) setUrls(u => ({ ...u, [f.id]: URL.createObjectURL(b) })); })
                .catch(() => {});
        });
        return () => { vivo = false; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [fotos, token]);

    const subir = async (pose, e) => {
        const file = e.target.files?.[0];
        e.target.value = '';
        if (!file) return;
        setSubiendo(pose);
        try {
            const fd = new FormData();
            fd.append('file', file);
            await api.post(`/reports/photos?pose=${pose}`, fd);
            toast.success('Foto subida');
            cargar();
            onSubida?.();
        } catch (err) {
            toast.error(mensajeDeError(err, 'No hemos podido subirla'));
        } finally {
            setSubiendo(null);
        }
    };

    // El dia LOCAL del cliente, no el UTC (bloque F, 23-08).
    const hoy = new Date().toLocaleDateString('en-CA');
    const subidaHoy = (pose) => {
        const f = ultimaDe(pose);
        return f && String(f.taken_at).slice(0, 10) === hoy;
    };

    return (
        <div className="bg-card border border-border rounded-2xl p-4" data-testid="tres-fotos">
            <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-xl bg-muted flex items-center justify-center">
                    <Camera className="w-4 h-4 text-foreground/40" />
                </div>
                <div>
                    <p className="text-sm font-bold text-foreground">Tus tres fotos</p>
                    <p className="text-xs text-foreground/30">Frente, espaldas y perfil. Relajado.</p>
                </div>
            </div>

            <p className="text-xs text-foreground/50 mb-4 leading-relaxed">
                {/* En una semana que no es la del mensual esto sigue estando, pero dicho de
                    otra manera: no se le pide nada, se le deja subirlas. Antes el bloque
                    entero desaparecía y el cliente venía aquí desde Check-ins a buscar algo
                    que no estaba (punto 21). */}
                {esMensual
                    ? <>Colócate como en la foto del mes pasado: misma distancia, misma luz y mismo
                        sitio. Es lo que permite comparar una con otra.</>
                    : <>Las fotos se piden en el reporte mensual, así que hoy no hacen falta. Si ya
                        las tienes hechas, súbelas y quedan guardadas: mismo sitio, misma luz y
                        misma distancia que la del mes pasado.</>}
            </p>

            <div className="grid grid-cols-3 gap-3">
                {POSES.map(({ key, label, ayuda }) => {
                    const anterior = ultimaDe(key);
                    const url = anterior && urls[anterior.id];
                    const ya = subidaHoy(key);
                    return (
                        <div key={key}>
                            <label className={`block cursor-pointer rounded-xl border-2 border-dashed transition-colors ${ya ? 'border-emerald-500/50 bg-emerald-500/5' : 'border-border hover:border-brand/50'}`}>
                                <div className="aspect-[3/4] flex flex-col items-center justify-center gap-1.5 p-2 text-center">
                                    {subiendo === key ? <Loader2 className="w-5 h-5 animate-spin text-brand" />
                                        : ya ? <Check className="w-5 h-5 text-emerald-500" />
                                        : <Camera className="w-5 h-5 text-foreground/30" />}
                                    <span className={`text-[11px] font-bold ${ya ? 'text-emerald-500' : 'text-foreground/60'}`}>{label}</span>
                                    {ya && <span className="text-[9px] text-foreground/40">subida</span>}
                                </div>
                                <input type="file" accept="image/*" className="hidden"
                                    data-testid={`foto-${key}`}
                                    onChange={(e) => subir(key, e)} disabled={subiendo !== null} />
                            </label>

                            <p className="text-[10px] text-foreground/40 mt-1.5 leading-snug">{ayuda}</p>

                            {/* La del mes pasado, para colocarse igual */}
                            {url && (
                                <div className="mt-2">
                                    <p className="text-[9px] text-foreground/30 uppercase tracking-wider mb-1">Mes pasado</p>
                                    <img src={url} alt={`${label}, mes pasado`}
                                        className="w-full rounded-lg opacity-60" />
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default TresFotos;
