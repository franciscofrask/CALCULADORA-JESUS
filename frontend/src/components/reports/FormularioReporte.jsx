/**
 * EL FORMULARIO DEL REPORTE: el quincenal y el mensual, que ya no son el mismo.
 *
 * Hasta el doc del 16-08 había UN formulario y lo único que cambiaba entre uno y otro
 * eran las medidas. Son dos cuestionarios distintos (T7 y T8) y el mensual además no es
 * igual para los tres planes, así que aquí solo vive lo común: traer lo que la app ya
 * sabe, guardar lo que el cliente contesta, revisarlo antes de mandarlo y decirle qué
 * pasa ahora.
 *
 * Qué bloques lleva cada uno NO se decide aquí: lo dice el servidor en
 * `GET /reports/formulario`, leyendo las habilitaciones de su plan. El plan es un dato,
 * nunca un nombre.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Send } from 'lucide-react';
import ReporteQuincenal from './ReporteQuincenal';
import ReporteMensual from './ReporteMensual';
import RevisaAntesDeEnviar from './RevisaAntesDeEnviar';
import { MEDIDAS } from '../../lib/medidas';
import { revisarPeso } from '../../lib/pesoValido';
import { useConfirm } from '../ui/confirm';
import { mensajeDeError } from '../../lib/mensajeDeError';

const ORANGE = '#FF671F';

const valoresIniciales = (objetivoActual) => ({
    weight: '',
    // El % de grasa solo sale en el reporte que toca, cada 12 semanas.
    body_fat: '',
    measurements: Object.fromEntries(MEDIDAS.map(m => [m.key, ''])),
    // Quincenal
    entreno_huecos: '',
    molestias: '',
    sensaciones: null,
    // Mensual
    dieta_dificultad: '',
    viabilidad_ajuste: '',
    entreno: { confirmacion: {}, estrellas: null, nota: '', regularidad: '',
               rutina_del_mes: '', quiere_saber_del_silver: null },
    lesiones: [],
    lesion_nueva_hay: '',
    lesion_nueva: '',
    cardio_proximo_mes: '',
    suplementacion: { respuesta: '', detalle: '' },
    energia_motivo: '',
    valoracion_resultado: null,
    motivacion: null,
    proximo_objetivo: '',
    notes: '',
    sugerencias: '',
    // Para el resumen: cuántas fotos hay subidas y con qué objetivo venía, para poder
    // decir "no cambia" sin preguntárselo otra vez.
    fotos_puestas: 0,
    objetivo_actual: objetivoActual || '',
});

const FormularioReporte = ({ api, token, tipoRevision, windowState, prev, perfilCliente,
                            onEnviado }) => {
    const { confirm } = useConfirm();
    const [cargando, setCargando] = useState(true);
    const [ficha, setFicha] = useState(null);          // lo que manda el servidor
    const [valores, setValores] = useState(() => valoresIniciales(perfilCliente?.goal));
    const [paso, setPaso] = useState('form');          // form | resumen | enviado
    const [enviando, setEnviando] = useState(false);
    const [aplazado, setAplazado] = useState(false);
    const [mensajeFinal, setMensajeFinal] = useState('');

    const set = (campo, valor) => setValores(v => ({ ...v, [campo]: valor }));
    const setEntreno = (campo, valor) => setValores(v => ({ ...v, entreno: { ...v.entreno, [campo]: valor } }));

    const cargar = useCallback(async () => {
        try {
            const r = await api.get('/reports/formulario', {
                params: tipoRevision ? { tipo: tipoRevision } : {},
            });
            setFicha(r.data);
            setAplazado(!!r.data?.aplazado_hasta);
            // Las lesiones abiertas entran ya en el estado: lo que se contesta es su
            // estado de este mes, no volver a escribirlas.
            const abiertas = (r.data?.datos?.lesiones || []).map(l => ({
                zona: l.zona, desde: l.desde, estado_mes: '',
                ejercicios: l.ejercicios_vetados || [],
            }));
            setValores(v => ({ ...v, lesiones: abiertas }));
        } catch (e) {
            console.error('No se pudo cargar el formulario del reporte', e);
            toast.error('No hemos podido preparar tu reporte. Inténtalo en un momento.');
        } finally {
            setCargando(false);
        }
    }, [api, tipoRevision]);

    useEffect(() => { cargar(); }, [cargar]);

    const esMensual = ficha?.tipo === 'mensual';
    const bloques = ficha?.bloques || [];

    // El plazo, en hora de España y con lo que queda. Lo calcula quien nos llama
    // (la pantalla ya lo tenía resuelto) y aquí solo se pinta.
    const plazo = {
        semana: windowState?.cycle?.week ?? windowState?.semana ?? null,
        cierre: windowState?.plazoLabel || null,
        queda: windowState?.quedaLabel || null,
    };

    const aplazar = async () => {
        try {
            const r = await api.post('/reports/aplazar');
            setAplazado(true);
            toast.success(r.data?.titulo || 'Te lo he aplazado 7 días', {
                description: r.data?.mensaje, duration: 8000,
            });
        } catch (e) {
            console.error('No se pudo aplazar el reporte', e);
            toast.error(mensajeDeError(e, 'No hemos podido aplazártelo. Inténtalo en un momento.'));
        }
    };

    /** Lo que no se puede mandar a medias. Devuelve true si se puede seguir. */
    const revisar = async () => {
        if (!valores.weight) { toast.error('El peso es obligatorio'); return false; }
        const chequeo = revisarPeso(valores.weight, prev?.weight);
        if (!chequeo.ok) { toast.error(chequeo.error); return false; }
        if (chequeo.confirmar && !await confirm({
            title: 'Confírmame el peso',
            description: chequeo.confirmar,
            confirmLabel: 'Sí, es correcto', cancelLabel: 'Lo corrijo',
        })) return false;
        if (esMensual) {
            const faltan = MEDIDAS.filter(m => !valores.measurements[m.key]);
            if (faltan.length) {
                toast.error(faltan.length === 1
                    ? `Te falta una medida: ${faltan[0].label.toLowerCase()}`
                    : `Te faltan ${faltan.length} medidas, y van todas: empieza por ${faltan[0].label.toLowerCase()}`);
                return false;
            }
        }
        return true;
    };

    /** Del formulario al resumen: se cuentan las fotos para poder decir "las tres". */
    const irAlResumen = async () => {
        if (!await revisar()) return;
        try {
            const r = await api.get('/reports/photos');
            const desde = ficha?.datos?.periodo?.desde || '';
            const poses = new Set((r.data?.photos || [])
                .filter(f => String(f.taken_at || '').slice(0, 10) >= desde)
                .map(f => f.pose));
            set('fotos_puestas', poses.size);
        } catch { /* si no se pueden contar, el resumen lo dice como "sin poner" */ }
        setPaso('resumen');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const enviar = async () => {
        if (paso === 'form' && !await revisar()) return;
        setEnviando(true);
        try {
            const payload = {
                tipo: ficha?.tipo,
                weight: parseFloat(String(valores.weight).replace(',', '.')),
                // Solo viaja el mes que toca (cada 12 semanas): el resto no se le pregunta,
                // así que va a null y el servidor no toca su serie.
                body_fat: valores.body_fat
                    ? parseFloat(String(valores.body_fat).replace(',', '.')) : null,
                measurements: Object.fromEntries(
                    Object.entries(valores.measurements).filter(([, v]) => v)
                        .map(([k, v]) => [k, parseFloat(String(v).replace(',', '.'))])),
                // El cumplimiento del entreno lo sigue calculando el servidor con esto:
                // la diferencia entre no entrenar y entrenar sin apuntarlo.
                huecos: huecosParaElServidor(ficha, valores),
                molestias: valores.molestias || null,
                sensaciones: valores.sensaciones,
                dieta_dificultad: valores.dieta_dificultad || null,
                viabilidad_ajuste: valores.viabilidad_ajuste || null,
                entreno: esMensual ? limpiarEntreno(valores.entreno) : null,
                lesiones: bloques.includes('lesiones')
                    ? valores.lesiones.filter(l => l.zona).map(l => ({
                        zona: l.zona, desde: l.desde || null,
                        estado_mes: l.estado_mes || null, ejercicios: l.ejercicios || [] }))
                    : null,
                lesion_nueva: valores.lesion_nueva_hay === 'si' ? (valores.lesion_nueva || null) : null,
                cardio_proximo_mes: valores.cardio_proximo_mes || null,
                suplementacion: valores.suplementacion.respuesta
                    ? { respuesta: valores.suplementacion.respuesta,
                        detalle: valores.suplementacion.detalle || null }
                    : null,
                energia_motivo: valores.energia_motivo || null,
                valoracion_resultado: valores.valoracion_resultado,
                motivacion: valores.motivacion,
                proximo_objetivo: valores.proximo_objetivo || null,
                notes: valores.notes || null,
                sugerencias: valores.sugerencias || null,
            };
            const r = await api.post('/reports', payload);
            setMensajeFinal(r.data?.mensaje_envio
                || 'Antes del viernes tienes tus ajustes nuevos. Te aviso por aquí.');
            setPaso('enviado');
            window.scrollTo({ top: 0, behavior: 'smooth' });
            if (onEnviado) onEnviado();
        } catch (error) {
            console.error('Error al enviar el reporte', error);
            toast.error(mensajeDeError(error, 'No hemos podido enviar tu reporte. Inténtalo en un momento.'));
        } finally {
            setEnviando(false);
        }
    };

    if (cargando) {
        return (
            <div className="animate-pulse space-y-3">
                <div className="h-6 bg-muted rounded w-1/2" />
                <div className="h-40 bg-card rounded-2xl" />
                <div className="h-40 bg-card rounded-2xl" />
            </div>
        );
    }
    if (!ficha) return null;

    // ── Enviado. Lo que pasa ahora, con fecha: "antes del viernes", no "en breve" ──
    if (paso === 'enviado') {
        return (
            <div className="bg-card border border-border rounded-2xl p-6 text-center space-y-2"
                data-testid="reporte-enviado">
                <p className="text-lg font-bold text-foreground">Reporte enviado.</p>
                <p className="text-[15px] text-muted-foreground">{mensajeFinal}</p>
            </div>
        );
    }

    if (paso === 'resumen') {
        return (
            <RevisaAntesDeEnviar
                valores={valores} datos={ficha.datos} bloques={bloques} perfil={ficha.perfil}
                prev={prev} enviando={enviando}
                onVolver={() => { setPaso('form'); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
                onEnviar={enviar} />
        );
    }

    return (
        <div className="space-y-4">
            {esMensual ? (
                <ReporteMensual
                    datos={ficha.datos} perfil={ficha.perfil} bloques={bloques}
                    valores={valores} set={set} setEntreno={setEntreno} plazo={plazo}
                    api={api} token={token} prev={prev}
                    aplazado={aplazado} onAplazar={aplazar} />
            ) : (
                <ReporteQuincenal datos={ficha.datos} valores={valores} set={set} plazo={plazo} />
            )}

            {/* El mensual pasa por el resumen; el quincenal son cuatro preguntas que caben
                en una pantalla y se manda directo (T7 acaba en «Enviar reporte»). */}
            <button type="button" onClick={esMensual ? irAlResumen : enviar} disabled={enviando}
                data-testid={esMensual ? 'revisar-y-enviar' : 'submit-report-btn'}
                className="w-full py-3 rounded-xl font-bold text-sm uppercase tracking-wider text-white flex items-center justify-center gap-2 transition-all disabled:opacity-40"
                style={{ backgroundColor: ORANGE }}>
                <Send className="w-4 h-4" />
                {enviando ? 'Enviando...' : esMensual ? 'Revisar y enviar' : 'Enviar reporte'}
            </button>
        </div>
    );
};

/**
 * Los huecos, como los entiende el servidor.
 *
 * En el quincenal es una respuesta sola. En el mensual del que confirma día a día se
 * resume: si dice que entrenó aunque sea un día sin apuntarlo, cuenta como registro que
 * faltaba; si dice que no entrenó ninguno, cuenta como no hecho. El detalle día a día no
 * se pierde -- va en `entreno.confirmacion` --, esto es solo para el porcentaje.
 */
const huecosParaElServidor = (ficha, valores) => {
    if (ficha?.tipo !== 'mensual') {
        if (!valores.entreno_huecos) return {};
        return { entrenamiento: valores.entreno_huecos === 'si_no_lo_apunte'
            ? 'si_pero_no_apunte' : 'no_lo_hice' };
    }
    const respuestas = Object.values(valores.entreno?.confirmacion || {}).filter(Boolean);
    if (!respuestas.length) return {};
    return { entrenamiento: respuestas.includes('si_no_lo_apunte')
        ? 'si_pero_no_apunte' : 'no_lo_hice' };
};

/** Solo lo que se le ha llegado a preguntar: un plan sin rutina no manda estrellas. */
const limpiarEntreno = (entreno) => ({
    confirmacion: Object.fromEntries(
        Object.entries(entreno.confirmacion || {}).filter(([, v]) => v)),
    estrellas: entreno.estrellas ?? null,
    nota: entreno.nota || null,
    regularidad: entreno.regularidad || null,
    rutina_del_mes: entreno.rutina_del_mes || null,
    quiere_saber_del_silver: entreno.quiere_saber_del_silver,
});

export default FormularioReporte;
