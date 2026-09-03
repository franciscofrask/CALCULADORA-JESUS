/**
 * TUS FOTOS Y TUS MÉTRICAS (doc del 19-08, «Lo que falta en Seguimiento»).
 *
 *     «Subir fotos · Cuando quieras / Añadir medidas · Cuando quieras / Actualizar mi %
 *      de grasa · Abre el carrusel. Estos tres botones hoy no existen. Si puede subirlas
 *      cuando quiera, tiene que haber por dónde.»
 *
 * En los planes de autogestión no se piden: se recomiendan (cada 4 semanas las fotos y
 * las medidas, cada 12 el porcentaje), y esta es la puerta que siempre está abierta.
 */
import React, { useState } from 'react';
import { toast } from 'sonner';
import { Camera, Ruler, Percent } from 'lucide-react';
import TresFotos from './reports/TresFotos';
import BodyFatSlider from './SelectorGrasa';
import { MEDIDAS } from '../lib/medidas';
import { mensajeDeError } from '../lib/mensajeDeError';

const Boton = ({ icon: Icon, titulo, sub, abierto, onClick, testid }) => (
    <button type="button" onClick={onClick} data-testid={testid}
        className={`flex-1 min-w-[140px] text-left rounded-xl border p-3 transition-colors ${
            abierto ? 'border-brand bg-brand/10' : 'border-border bg-card hover:border-foreground/30'}`}>
        <Icon className="w-4 h-4 text-brand mb-1.5" />
        <p className="text-sm font-bold text-foreground leading-tight">{titulo}</p>
        <p className="text-[11px] text-muted-foreground">{sub}</p>
    </button>
);

const TusFotosYMetricas = ({ api, token, profile, onGuardado }) => {
    const [abierto, setAbierto] = useState(null);   // fotos | medidas | grasa | null
    const [medidas, setMedidas] = useState({});
    const [grasa, setGrasa] = useState(profile?.grasa?.valor ?? profile?.body_fat ?? null);
    const [guardando, setGuardando] = useState(false);

    const alternar = (cual) => setAbierto(a => (a === cual ? null : cual));

    const guardarMedidas = async () => {
        setGuardando(true);
        try {
            await api.post('/clients/me/medidas', { medidas });
            toast.success('Medidas guardadas');
            setMedidas({});
            setAbierto(null);
            onGuardado?.();
        } catch (e) {
            toast.error(mensajeDeError(e, 'No se pudieron guardar'));
        } finally {
            setGuardando(false);
        }
    };

    const guardarGrasa = async () => {
        setGuardando(true);
        try {
            await api.post('/clients/me/grasa', { valor: grasa });
            toast.success('Porcentaje actualizado');
            setAbierto(null);
            onGuardado?.();
        } catch (e) {
            toast.error(mensajeDeError(e, 'No se pudo guardar'));
        } finally {
            setGuardando(false);
        }
    };

    return (
        <div className="bg-card border border-border rounded-2xl p-4 space-y-3"
            data-testid="tus-fotos-y-metricas">
            <div className="flex flex-wrap gap-2">
                <Boton icon={Camera} titulo="Subir fotos" sub="Cuando quieras"
                    abierto={abierto === 'fotos'} onClick={() => alternar('fotos')}
                    testid="btn-subir-fotos" />
                <Boton icon={Ruler} titulo="Añadir medidas" sub="Cuando quieras"
                    abierto={abierto === 'medidas'} onClick={() => alternar('medidas')}
                    testid="btn-anadir-medidas" />
                {/* «Carrusel» era jerga nuestra (doc 23-08, bloque 10): se dice lo que
                    va a hacer, con las palabras del doc.
                    Y CADA CUÁNTO, que es opcional (punto 10.2 del 2-09): el subtítulo decía
                    cómo se elige, no cuándo conviene hacerlo, y el informe por su lado decía
                    «se mide al final de cada ciclo, cada 12 semanas», que sonaba a obligación.
                    Los dos sitios dicen ya lo mismo. */}
                <Boton icon={Percent} titulo="Actualizar mi % de grasa" sub="Opcional · mejor uno de cada 3 reportes"
                    abierto={abierto === 'grasa'} onClick={() => alternar('grasa')}
                    testid="btn-actualizar-grasa" />
            </div>

            {abierto === 'fotos' && (
                <div className="pt-1">
                    <p className="text-xs text-muted-foreground mb-2">
                        Frente, espaldas y perfil. Con buena luz y siempre en el mismo sitio: solo
                        así podrás ser objetivo al comparar.
                    </p>
                    <TresFotos api={api} token={token} esMensual={false} />
                </div>
            )}

            {abierto === 'medidas' && (
                <div className="pt-1 space-y-2">
                    <p className="text-xs text-muted-foreground">
                        Si te puede medir alguien, y siempre el mismo, mejor. En cm.
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                        {MEDIDAS.map(({ key, label }) => (
                            <label key={key} className="text-xs text-muted-foreground">
                                {label}
                                <input type="number" inputMode="decimal" step="0.5"
                                    value={medidas[key] ?? ''} data-testid={`medida-${key}`}
                                    onChange={e => setMedidas(m => ({ ...m, [key]: e.target.value }))}
                                    className="mt-0.5 w-full bg-muted border border-border rounded-lg px-2 py-1.5 text-sm text-foreground" />
                            </label>
                        ))}
                    </div>
                    <button onClick={guardarMedidas} disabled={guardando}
                        data-testid="guardar-medidas"
                        className="btn-brand disabled:opacity-60">
                        {guardando ? 'Guardando…' : 'Guardar medidas'}
                    </button>
                </div>
            )}

            {abierto === 'grasa' && (
                <div className="pt-1 space-y-3">
                    {/* Su texto entero, dentro. Aquí es donde va a decidir si lo hace hoy. */}
                    <p className="text-xs text-muted-foreground">
                        Registrarlo es opcional, lo puedes hacer si quieres, pero para poder
                        sacar conclusiones es mejor hacerlo uno de cada 3 reportes (12 semanas):
                        así comparas el inicio y el final de cada ciclo.
                    </p>
                    <BodyFatSlider value={grasa} onChange={setGrasa}
                        sexo={profile?.sex || 'hombre'} />
                    <button onClick={guardarGrasa} disabled={guardando || grasa == null}
                        data-testid="guardar-grasa"
                        className="btn-brand disabled:opacity-60">
                        {guardando ? 'Guardando…' : 'Guardar mi porcentaje'}
                    </button>
                </div>
            )}
        </div>
    );
};

export default TusFotosYMetricas;
