/**
 * TU COMPARATIVA. La comparativa de fotos del panel, traída al lado del cliente.
 *
 * DOS FOTOS Y YA (doc de Jesús del 2-09, «Y la comparativa de fotos»). Abrió «+ La del
 * medio», vio que metía una tercera foto en el centro con un rótulo fijo que no decía de
 * qué, y lo dejó escrito: «Dos fotos, siempre. Inicio del ciclo contra hoy, las dos con su
 * peso». Así que aquí van dos, izquierda y derecha, y nada más:
 *
 *   - IZQUIERDA: la del INICIO DEL CICLO, la más cercana a `cycle_start`. Si en ese ciclo no
 *     subió fotos «ese hito no existe»: se coge la más cercana y se dice debajo de la fecha
 *     («la más próxima al inicio del ciclo»). Sin ciclo o sin con qué elegir, la primera de
 *     la historia con el rótulo «Mi primera foto», que nunca miente.
 *   - DERECHA: la de HOY, la más reciente. Debajo, sus medidas.
 *   - MISMO ÁNGULO: si la de hoy es de frente, la del inicio es de frente. «Comparar un
 *     frente con un perfil no dice nada.» Si no hay foto de ese ángulo se avisa.
 *   - Las dos con su fecha y su peso. La de hoy no se queda sin él: si no hay pesaje cerca
 *     de la foto, va el último peso conocido diciendo de qué día es.
 *
 * La regla de elegir vive en `lib/comparativaFotos.elegirDosFotos`; el panel del entrenador
 * y el informe siguen con sus cuatro fotos de siempre (`construirComparativa`), que son
 * otra pantalla y otro documento.
 *
 * FUERA EL % GRASO: lo estima Jesús mirando las fotos, y el cliente no lo toca.
 *
 * Las fotos van con la sesión, así que se piden con el token y se pintan desde el blob (el
 * mismo camino que `TresFotos`): el token no viaja nunca en una URL de imagen.
 *
 * La lista de /reports/photos viene FUNDIDA (tarea 1.1): las de la app y las importadas de
 * Calma, cada una con su `ref`, su fecha y su `pose` (frente | perfil | espalda, o nada si
 * la de Calma no la trae en el nombre). Aquí no se distingue nada: se pide cada foto por
 * su ref a /reports/foto/{ref} y se ordena todo junto, que es justo lo que el cliente
 * espera ver (su histórico entero, no solo lo subido en la app nueva).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import VisorDeFoto from './ui/VisorDeFoto';
import { Camera } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { elegirDosFotos, ordenarPorPose, ROTULO_DOS_FOTOS } from '../lib/comparativaFotos';
import { MEDIDAS, valorAnterior } from '../lib/medidas';

// Con el año cuando no es el de ahora: «Mi primera foto» puede ser de hace dos años y un
// «3 may» a secas mentiría con la fecha, que es justo lo que Jesús pide que no pase.
const _fecha = (f) => {
    if (!f) return '';
    const d = new Date(`${f}T12:00:00`);
    if (isNaN(d)) return f;
    const conAnyo = d.getFullYear() !== new Date().getFullYear();
    return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', ...(conAnyo ? { year: 'numeric' } : {}) });
};

const _kilos = (v) => `${String(v).replace('.', ',')} kg`;

// Hasta cuántos días de la foto vale un pesaje para decir «este es el peso de esa foto».
// Es el mismo criterio que en la ficha del panel: tres semanas.
const DIAS_DE_PESAJE_VALIDO = 21;

// El pesaje más cercano a una fecha, con su día, o null si no hay ninguno a menos de tres
// semanas. La foto se anota con el peso de ese momento, no con el de hoy.
const _pesajeCercano = (pesos, fecha) => {
    if (!fecha || !pesos?.length) return null;
    const objetivo = new Date(`${fecha}T12:00:00`).getTime();
    let mejor = null, distancia = Infinity;
    for (const p of pesos) {
        const d = Math.abs(new Date(`${p.fecha}T12:00:00`).getTime() - objetivo);
        if (d < distancia) { distancia = d; mejor = p; }
    }
    return distancia <= DIAS_DE_PESAJE_VALIDO * 864e5 ? mejor : null;
};

// El peso que va debajo de una foto. La de hoy no se queda sin él (Jesús, 2-09: «la de hoy
// no lleva su peso; la otra sí»): si el último pesaje queda a más de tres semanas de la
// foto, se enseña el último peso conocido y se dice de qué día es. La del inicio no: un
// peso de meses después no es «su peso», y mejor callar que mentir.
const _pesoDeLaFoto = (pesos, fecha, esLaDeHoy) => {
    const cerca = _pesajeCercano(pesos, fecha);
    if (cerca) return { peso: cerca.peso, deOtroDia: null };
    if (!esLaDeHoy || !pesos?.length) return null;
    const ultimo = pesos[pesos.length - 1];
    return { peso: ultimo.peso, deOtroDia: ultimo.fecha };
};

/** Una foto del cliente, descargada con su sesión. La ref de las de Calma lleva una
 *  barra (calma/carpeta/fichero), así que se codifica tramo a tramo.
 *
 *  SE TOCA Y SE VE ENTERA (Francisco, 26-08). El hueco es de 3/4 con `object-cover`, o sea
 *  que la foto va recortada: en un teléfono la cabeza y los pies se quedan fuera, y estas
 *  fotos están justo para comparar dos meses. El visor la enseña completa y con su fecha,
 *  que es el dato que hay que tener delante mientras se mira. */
const FotoDelCliente = ({ api, foto, pie }) => {
    const [url, setUrl] = useState(null);
    const [ampliada, setAmpliada] = useState(false);
    const ref = foto.ref || foto.id;
    useEffect(() => {
        let vivo = true;
        const camino = String(ref).split('/').map(encodeURIComponent).join('/');
        api.get(`/reports/foto/${camino}`, { responseType: 'blob' })
            .then(r => { if (vivo) setUrl(URL.createObjectURL(r.data)); })
            .catch((e) => { console.error('No se pudo cargar una foto de la comparativa:', e); });
        return () => { vivo = false; };
    }, [api, ref]);

    if (!url) return <div className="aspect-[3/4] rounded-xl overflow-hidden bg-muted" />;

    return (
        <>
            <button type="button" onClick={() => setAmpliada(true)}
                aria-label={pie ? `Ver la foto de ${pie} en grande` : 'Ver la foto en grande'}
                data-testid="foto-comparativa"
                className="aspect-[3/4] w-full rounded-xl overflow-hidden bg-muted block active:opacity-80 transition-opacity">
                <img src={url} alt="" className="w-full h-full object-cover" />
            </button>
            {ampliada && (
                <VisorDeFoto url={url} alt={pie ? `Tu foto de ${pie}` : 'Tu foto'} pie={pie}
                    alCerrar={() => setAmpliada(false)} />
            )}
        </>
    );
};

/** «Cintura 84 · y 9 medidas más», debajo de la foto de hoy. */
const MedidasDeLaFoto = ({ medidas }) => {
    const conValor = MEDIDAS
        .map(({ key, label }) => ({ key, label, valor: valorAnterior(medidas, key) }))
        .filter(m => m.valor != null);
    if (!conValor.length) return null;
    const primera = conValor.find(m => m.key === 'cintura') || conValor[0];
    const resto = conValor.length - 1;
    const alPasar = conValor.filter(m => m.key !== primera.key).map(m => `${m.label}: ${m.valor} cm`).join('\n');
    return (
        <p className="text-[11px] text-muted-foreground leading-tight" title={alPasar || undefined}>
            {primera.label} <b className="text-foreground">{primera.valor}</b>
            {resto > 0 && ` · y ${resto} ${resto === 1 ? 'medida más' : 'medidas más'}`}
        </p>
    );
};

/** Un lado de la comparativa: la foto, su rótulo, su fecha (con lo que haya que decir de
 *  ella), su peso y, en la de hoy, sus medidas. */
const LadoDeLaComparativa = ({ api, lado, pesos, esLaDeHoy, testid }) => {
    const { sesion, foto, rotulo, nota, aviso } = lado;
    const peso = _pesoDeLaFoto(pesos, sesion.fecha, esLaDeHoy);
    return (
        <div className="space-y-1" data-testid={testid}>
            <FotoDelCliente api={api} foto={foto} pie={_fecha(sesion.fecha)} />
            <p className="text-[10px] font-bold uppercase tracking-wider text-brand leading-tight">
                {ROTULO_DOS_FOTOS[rotulo] || rotulo}
            </p>
            <p className="text-[11px] text-muted-foreground leading-tight">
                {_fecha(sesion.fecha)}
                {/* Lo que no es exacto se dice debajo de la fecha, en pequeño: «nunca enseñar
                    un hueco ni mentir con la fecha» (doc de Jesús del 2-09). */}
                {nota && <span className="block text-[10px]">{nota}</span>}
                {aviso && <span className="block text-[10px]">{aviso}</span>}
                {peso && <span className="block font-bold text-foreground">{_kilos(peso.peso)}</span>}
                {peso?.deOtroDia && <span className="block text-[10px]">tu último peso, del {_fecha(peso.deOtroDia)}</span>}
            </p>
            {/* Las medidas van con la de hoy: es la que se mira para saber dónde está, y
                debajo de la del inicio no dicen nada que la tabla de aquí abajo no cuente
                mejor. */}
            {esLaDeHoy && sesion.medidas && <MedidasDeLaFoto medidas={sesion.medidas} />}
        </div>
    );
};

/**
 * @param desdeElCiclo  Día en que arrancó el ciclo (perfil.cycle_start). Si no llega por
 *                      prop se lee del perfil de la sesión, que es el mismo dato.
 * @param serieDePeso   La curva de peso, [{fecha, peso}], la misma que pinta la gráfica de
 *                      arriba. Si no llega por prop se pide a /reports/evolution, para que
 *                      la foto y la gráfica digan el mismo peso.
 */
const ComparativaCliente = ({ api, reports, desdeElCiclo = null, serieDePeso = null }) => {
    const { profile } = useAuth();
    const [fotos, setFotos] = useState([]);
    const [verTodas, setVerTodas] = useState(false);
    const [serieCargada, setSerieCargada] = useState(null);

    const cargar = useCallback(() => {
        api.get('/reports/photos')
            .then(r => setFotos(r.data?.photos || []))
            .catch((e) => { console.error('No se pudieron cargar las fotos:', e); });
    }, [api]);
    useEffect(() => { cargar(); }, [cargar]);

    // EL PESO SALE DE LA CURVA, NO DE LOS REPORTES. Los reportes son uno al mes; la curva
    // lleva también los pesajes semanales y los importados. Con solo los reportes, la foto
    // de hoy se quedaba sin peso en cuanto el reporte caía a más de tres semanas de ella,
    // que es lo que vio Jesús el 2-09.
    useEffect(() => {
        if (serieDePeso) return undefined;
        let vivo = true;
        api.get('/reports/evolution')
            .then(r => {
                if (!vivo) return;
                setSerieCargada((r.data?.weight || []).map(w => ({ fecha: w.date, peso: w.value })));
            })
            .catch((e) => { console.error('No se pudo cargar la curva de peso para la comparativa:', e); });
        return () => { vivo = false; };
    }, [api, serieDePeso]);

    const pesos = useMemo(() => {
        // Si la curva no ha llegado (o falló), los reportes siguen valiendo: es la serie
        // que había hasta ahora.
        const fuente = serieDePeso || serieCargada || (reports || [])
            .filter(r => r?.weight != null && r?.created_at)
            .map(r => ({ fecha: r.created_at, peso: r.weight }));
        return fuente
            .filter(p => p?.peso != null && p?.fecha)
            .map(p => ({ fecha: String(p.fecha).slice(0, 10), peso: p.peso }))
            .sort((a, b) => a.fecha.localeCompare(b.fecha));
    }, [serieDePeso, serieCargada, reports]);

    const medidasPorFecha = useMemo(() => {
        const m = {};
        (reports || []).forEach(r => {
            const f = String(r.created_at || '').slice(0, 10);
            if (f && r.measurements && Object.keys(r.measurements).length) m[f] = r.measurements;
        });
        return m;
    }, [reports]);

    // Un día con fotos es una sesión: es lo que se compara, no cada foto suelta.
    const sesiones = useMemo(() => {
        const porDia = new Map();
        for (const f of fotos) {
            const dia = String(f.taken_at || f.uploaded_at || '').slice(0, 10);
            if (!dia) continue;
            if (!porDia.has(dia)) porDia.set(dia, []);
            porDia.get(dia).push(f);
        }
        return [...porDia.entries()].map(([fecha, suyas]) => ({
            fecha,
            medidas: medidasPorFecha[fecha] || null,
            fotos: ordenarPorPose(suyas),
        }));
    }, [fotos, medidasPorFecha]);

    const inicioCiclo = desdeElCiclo || profile?.cycle_start || null;
    const dos = useMemo(() => elegirDosFotos(sesiones, inicioCiclo), [sesiones, inicioCiclo]);

    if (!fotos.length || !dos) {
        return (
            <div className="bg-card border border-border rounded-2xl p-5 flex items-start gap-3" data-testid="comparativa-sin-fotos">
                <Camera className="w-5 h-5 text-foreground/25 shrink-0 mt-0.5" />
                <div>
                    <p className="text-sm font-bold text-foreground">Tu comparativa</p>
                    {/* Ya no es un callejón: los botones de arriba dejan subirlas cuando
                        quiera (doc 19-08, «Lo que falta en Seguimiento»). */}
                    <p className="text-xs text-muted-foreground mt-0.5">
                        Todavía no has subido fotos. Puedes subirlas cuando quieras con el botón
                        de arriba; te las recomendamos cada 4 semanas.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="bg-card border border-border rounded-2xl p-4 space-y-3" data-testid="comparativa-cliente">
            <div className="flex items-center gap-2">
                <Camera className="w-4 h-4 text-brand" />
                <p className="text-xs font-bold text-foreground/40 uppercase tracking-wider">Tu comparativa</p>
            </div>

            {verTodas ? (
                <div className="grid grid-cols-3 gap-2">
                    {[...sesiones].sort((a, b) => b.fecha.localeCompare(a.fecha)).map(s => s.fotos.map(f => (
                        <div key={f.id}>
                            <FotoDelCliente api={api} foto={f} pie={_fecha(s.fecha)} />
                            <p className="text-[10px] text-muted-foreground text-center mt-0.5">{_fecha(s.fecha)}</p>
                        </div>
                    )))}
                </div>
            ) : (
                /* DOS COLUMNAS FIJAS, aunque solo haya una foto. Con el reparto automático,
                   el cliente que solo tiene una sesión -- o sea, todo el que empieza -- se
                   encontraba la foto a pantalla completa y había que hacer scroll para
                   pasar de ella. La del inicio a la izquierda y la de hoy a la derecha,
                   que es la regla de Jesús; y con una sola, esa a la izquierda y al lado
                   lo que falta. */
                <div className="grid grid-cols-2 gap-3">
                    {dos.inicio ? (
                        <>
                            <LadoDeLaComparativa api={api} lado={dos.inicio} pesos={pesos} esLaDeHoy={false} testid="comparativa-inicio" />
                            <LadoDeLaComparativa api={api} lado={dos.hoy} pesos={pesos} esLaDeHoy testid="comparativa-hoy" />
                        </>
                    ) : (
                        <>
                            <LadoDeLaComparativa api={api} lado={dos.hoy} pesos={pesos} esLaDeHoy testid="comparativa-hoy" />
                            <p className="text-xs text-muted-foreground self-center leading-snug" data-testid="comparativa-falta-una">
                                Con dos fotos te enseñamos la comparativa. Te falta una.
                            </p>
                        </>
                    )}
                </div>
            )}

            {/* «Elegir otra foto» y «Generar comparación» (doc de Jesús del 2-09) van con el
                selector de fotos, que es de otra fase: hasta entonces no se pinta ningún
                botón que no haga nada. «Mostrar todas» se queda porque hoy es la única
                forma de ver el histórico entero. */}
            <button type="button" onClick={() => setVerTodas(!verTodas)} data-testid="mostrar-todas-fotos"
                className="w-full py-2 text-xs font-bold text-muted-foreground hover:text-brand border border-border rounded-xl transition-colors">
                {verTodas ? 'Volver a la comparativa' : 'Mostrar todas'}
            </button>
        </div>
    );
};

export default ComparativaCliente;
