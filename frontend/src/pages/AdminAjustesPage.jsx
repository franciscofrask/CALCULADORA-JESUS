/**
 * AJUSTES DE LA APP (punto 64 del panel).
 *
 * «Sacar los interruptores escondidos a una pantalla de ajustes: los correos y la frase del
 * día están dentro de Planes.»
 *
 * Y era verdad: para apagar una pantalla a todos los clientes, o para cambiar la frase del
 * día, había que entrar en «Planes» -- que es el catálogo de lo que se vende -- y bajar
 * hasta el final. Nada de esto es un plan. Ahora tienen su sitio y se llega por el menú.
 *
 * SE MUEVE LO GLOBAL, Y SOLO LO GLOBAL. «Mi modo pruebas» se queda en Planes a propósito:
 * no es un ajuste de la app sino de TU cuenta (te la cambia de estado y hay que restaurarla
 * después), y mezclarlo aquí invita justo al accidente que esta pantalla debe evitar --
 * creer que tocas lo tuyo cuando lo tocas para todos.
 */
import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { SlidersHorizontal, AlertTriangle } from 'lucide-react';
import { PANTALLAS_APP, MANDA_CORREOS } from '../lib/pantallasDeLaApp';
import PuntoEncendido from '../components/PuntoEncendido';
import HelpTooltip from '../components/HelpTooltip';

const AdminAjustesPage = () => {
    const { api } = useAuth();
    const [ajustes, setAjustes] = useState(null);
    const [frase, setFrase] = useState('');
    const [fechaFrase, setFechaFrase] = useState('');
    const [guardandoFrase, setGuardandoFrase] = useState(false);

    useEffect(() => {
        api.get('/admin/settings')
            .then((res) => setAjustes(res.data || null))
            .catch(() => toast.error('No se pudieron cargar los ajustes de la app'));
        // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al entrar
    }, []);

    const alternar = async (clave) => {
        const nuevo = !ajustes?.pantallas?.[clave];
        try {
            const res = await api.put('/admin/settings', { pantallas: { [clave]: nuevo } });
            setAjustes(res.data);
        } catch (e) {
            toast.error('No se pudo guardar el cambio');
        }
    };

    const guardarFrase = async () => {
        if (!frase.trim()) return;
        setGuardandoFrase(true);
        try {
            const res = await api.put('/admin/settings', {
                frase_del_dia: { texto: frase.trim(), ...(fechaFrase ? { fecha: fechaFrase } : {}) },
            });
            setAjustes(res.data);
            setFrase('');
            setFechaFrase('');
            toast.success(fechaFrase ? 'Frase programada' : 'Frase del día guardada');
        } catch (e) {
            toast.error('No se pudo guardar la frase');
        } finally {
            setGuardandoFrase(false);
        }
    };

    return (
        <div className="space-y-4" data-testid="admin-ajustes">
            <div className="flex items-center gap-3">
                <SlidersHorizontal className="w-6 h-6 text-[#FF671F]" />
                <div>
                    <h1 className="text-xl font-bold text-white">Ajustes de la app</h1>
                    <p className="text-xs text-white/50">Lo que vale para todos los clientes a la vez. Los planes están en «Planes» y las pruebas de tu propia cuenta, dentro de esa misma pantalla.</p>
                </div>
            </div>

            {!ajustes ? (
                <p className="text-sm text-white/40">Cargando los ajustes...</p>
            ) : (
                <>
                    <Card className="bg-[#111] border-[#2a2a2a]">
                        <CardContent className="p-4 space-y-4">
                            <div>
                                <h2 className="text-base font-bold text-white">Pantallas de la app</h2>
                                <p className="text-xs text-white/50">Apagar aquí quita la pantalla a todos los clientes al momento, sin desplegar.</p>
                            </div>
                            {/* La ayuda de cada interruptor SE VE. Estaba escrita desde el
                                principio pero solo la enseñaba «Mi modo pruebas»: aquí, que
                                es donde se enciende para todo el mundo, salía a ciegas. */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
                                {PANTALLAS_APP.map(({ clave, label, ayuda }) => {
                                    const on = !!ajustes.pantallas?.[clave];
                                    return (
                                        <div key={clave} className="flex items-center gap-1">
                                            <button
                                                type="button"
                                                onClick={() => alternar(clave)}
                                                data-testid={`ajuste-${clave}`}
                                                className={`flex-1 min-w-0 flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-xs transition-colors ${on ? 'border-green-500/40 bg-green-500/10 text-white' : 'border-[#333] bg-black/30 text-white/60'}`}
                                            >
                                                <span>{label}</span>
                                                <PuntoEncendido on={on} />
                                            </button>
                                            <HelpTooltip text={ayuda} className="shrink-0" />
                                        </div>
                                    );
                                })}
                            </div>
                            {/* EL ÚNICO QUE SALE DE LA APP. Los demás encienden o apagan una
                                pantalla; este manda correos de verdad a gente de verdad, y
                                no hay forma de recogerlos. Que se lea antes de pulsarlo. */}
                            <div className="flex gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-3 py-2">
                                <AlertTriangle className="w-4 h-4 text-yellow-400 shrink-0 mt-0.5" />
                                <p className="text-xs text-white/70">
                                    «Los avisos del reporte, por correo» es el único de esta lista que sale de la app: al encenderlo
                                    <span className="text-white/90 font-semibold"> se mandan correos de verdad</span> a todos los clientes con un reporte pendiente,
                                    entren o no. Un aviso, un correo: nunca se repite.
                                    {ajustes.pantallas?.[MANDA_CORREOS] ? ' Ahora mismo está encendido.' : ' Ahora mismo está apagado.'}
                                </p>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="bg-[#111] border-[#2a2a2a]">
                        <CardContent className="p-4 space-y-1">
                            <Label className="text-xs text-white/60">
                                Frase del día
                                {ajustes.frase_del_dia?.texto ? (
                                    <span className="ml-2 text-white/40 normal-case">ahora: «{ajustes.frase_del_dia.texto}» ({ajustes.frase_del_dia.fecha})</span>
                                ) : (
                                    <span className="ml-2 text-white/40">todavía no hay ninguna</span>
                                )}
                            </Label>
                            <div className="flex gap-2">
                                <Input
                                    value={frase}
                                    onChange={(e) => setFrase(e.target.value)}
                                    placeholder="El único secreto que tiene esto es no dejarlo."
                                    className="bg-black/30 border-[#333] text-white text-sm"
                                />
                                {/* PROGRAMABLE CON UNA SEMANA (doc 19-08): sin fecha entra hoy;
                                    con fecha se queda en la cola y sale su día sola. */}
                                <Input
                                    type="date"
                                    value={fechaFrase}
                                    onChange={(e) => setFechaFrase(e.target.value)}
                                    min={new Date().toLocaleDateString('en-CA')}
                                    max={new Date(Date.now() + 7 * 864e5).toLocaleDateString('en-CA')}
                                    className="bg-black/30 border-[#333] text-white text-sm w-40 shrink-0"
                                />
                                <Button onClick={guardarFrase} disabled={guardandoFrase || !frase.trim()} className="bg-[#FF671F] hover:bg-[#e55b1a] text-white">
                                    {fechaFrase ? 'Programar' : 'Guardar'}
                                </Button>
                            </div>
                            {/* LA PROMESA DE ESTA LÍNEA HAY QUE CUMPLIRLA (punto 103 del 25-08):
                                se leyó como un contrato y el Inicio no la cumplía. Si se cambia
                                el orden de mando de la frase, se cambia también aquí. */}
                            <p className="text-[11px] text-white/40">
                                {ajustes.frases_en_rotacion > 0
                                    ? `Hay ${ajustes.frases_en_rotacion} frases rotando, una por día, sin agotarse. Lo que pongas aquí manda solo el día que le toque.`
                                    : 'Si un día no hay frase nueva, el cliente sigue viendo la última.'}
                                {' '}Con fecha, la frase se programa (hasta una semana) y entra sola su día.
                            </p>
                            {(ajustes.frases_programadas || []).length > 0 && (
                                <div className="space-y-0.5 pt-1">
                                    {ajustes.frases_programadas.map((f) => (
                                        <p key={f.fecha} className="text-[11px] text-white/50">
                                            {f.fecha} · «{f.texto}»
                                        </p>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </>
            )}
        </div>
    );
};

export default AdminAjustesPage;
