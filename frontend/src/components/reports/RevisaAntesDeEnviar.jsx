/**
 * "REVISA ANTES DE ENVIAR" (T9 del doc 16-08).
 *
 * "Todo lo que ha contestado, en una pantalla. Si algo está mal lo ve aquí y vuelve, no
 * después, cuando ya no se puede tocar."
 *
 * Un reporte mensual son once o trece bloques: quien lo rellena en dos ratos no se
 * acuerda de lo que puso arriba, y hasta ahora la única forma de comprobarlo era subir a
 * mirar. Aquí se resume en renglones cortos -- lo contestado, no las preguntas -- y se
 * vuelve atrás con un botón, sin perder nada de lo escrito.
 *
 * Un renglón sin contestar NO se esconde: sale en gris y dice que está sin poner. Es
 * justo lo que ha venido a comprobar.
 */
import React from 'react';
import { ChevronLeft, Send } from 'lucide-react';
import { MEDIDAS } from '../../lib/medidas';
import { enumerar, kg } from './piezas';

const ORANGE = '#FF671F';

const DIFICULTAD = {
    nada: 'nada, la llevo bien', algun_dia: 'algún día suelto',
    bastante: 'bastante', no_he_podido: 'no he podido',
};
const AJUSTE = {
    me_adapto: 'me adapto', necesito_mas: 'necesito comer más', necesito_menos: 'necesito comer menos',
};
const CARDIO = { mismas: 'las mismas sesiones', mas: 'más sesiones', menos: 'menos sesiones' };
const SUPLEMENTOS = { todos: 'todos', alguno_no: 'alguno no', ninguno: 'ninguno' };
const ENERGIA = {
    duermo_poco: 'duermo poco', estres_trabajo: 'estrés del trabajo',
    como_poco: 'como poco', no_lo_se: 'no lo sé',
};
const OBJETIVO = { definicion: 'definición', volumen: 'volumen', mantenimiento: 'mantenimiento' };
const REGULARIDAD = {
    a_mi_manera_sigo: 'a mi manera, sigo así',
    a_mi_manera_quiero_rutina: 'a mi manera, quiero probar tu rutina',
    con_tu_rutina_sigo: 'con tu rutina, sigo así',
};
const RUTINA_MES = { basica: 'la quiero, básica', avanzada: 'la quiero, avanzada', ahora_no: 'ahora no' };

const estrellas = (n) => (n ? `${n} ${n === 1 ? 'estrella' : 'estrellas'}` : null);

/** Un renglón del resumen: qué es, qué puso y, si la hay, la diferencia. */
const Renglon = ({ que, valor, extra, testid }) => (
    <div className="flex items-baseline justify-between gap-3 py-2 border-b border-border last:border-0"
        data-testid={testid}>
        <span className="text-sm text-muted-foreground flex-shrink-0">{que}</span>
        <span className="text-sm text-right">
            {valor
                ? <span className="text-foreground font-semibold">{valor}</span>
                : <span className="text-foreground/30">sin poner</span>}
            {extra && <span className="text-muted-foreground ml-2">{extra}</span>}
        </span>
    </div>
);

const RevisaAntesDeEnviar = ({ valores, datos, bloques, perfil, prev, enviando, onVolver, onEnviar }) => {
    const lleva = (c) => (bloques || []).includes(c);
    const dieta = datos?.dieta || {};
    const entreno = datos?.entreno || {};
    const cardio = entreno.cardio || {};

    // El peso, con lo que ha cambiado desde el reporte anterior: es el número por el que
    // vuelve la gente a mirar dos veces.
    const peso = parseFloat(String(valores.weight).replace(',', '.'));
    const difPeso = (!isNaN(peso) && prev?.weight != null)
        ? Math.round((peso - prev.weight) * 10) / 10 : null;

    const cintura = valores.measurements?.cintura;
    const cinturaAntes = prev?.measurements?.cintura ?? prev?.measurements?.waist;
    const difCintura = (cintura && cinturaAntes != null)
        ? Math.round((parseFloat(cintura) - cinturaAntes) * 10) / 10 : null;
    const otrasPuestas = MEDIDAS.filter(m => m.key !== 'cintura' && valores.measurements?.[m.key]).length;

    const lesionesPuestas = (valores.lesiones || [])
        .filter(l => l.estado_mes)
        .map(l => `${String(l.zona || '').toLowerCase()}: ${l.estado_mes}`);

    const conf = valores.entreno?.confirmacion || {};
    const confirmados = Object.keys(conf).filter(k => conf[k]).length;

    return (
        <div className="space-y-4" data-testid="revisa-antes-de-enviar">
            <div>
                <h2 className="text-xl font-bold text-foreground" style={{ fontFamily: 'Barlow Condensed', letterSpacing: '0.03em' }}>
                    Revisa antes de enviar
                </h2>
                <p className="text-[15px] text-muted-foreground">Si algo no está bien, vuelve atrás y lo cambias.</p>
            </div>

            <div className="bg-card border border-border rounded-2xl px-4 py-1">
                <Renglon testid="rev-peso" que="Peso" valor={valores.weight ? kg(String(valores.weight).replace('.', ',')) : null}
                    extra={difPeso != null ? `${difPeso > 0 ? '+' : ''}${String(difPeso).replace('.', ',')}` : null} />

                {lleva('medidas') && (
                    <>
                        <Renglon testid="rev-cintura" que="Cintura" valor={cintura ? `${String(cintura).replace('.', ',')} cm` : null}
                            extra={difCintura != null ? `${difCintura > 0 ? '+' : ''}${String(difCintura).replace('.', ',')}` : null} />
                        <Renglon testid="rev-medidas" que="Las otras 9 medidas"
                            valor={otrasPuestas === 9 ? 'puestas' : otrasPuestas ? `${otrasPuestas} de 9` : null} />
                        <Renglon testid="rev-fotos" que="Fotos"
                            valor={valores.fotos_puestas === 3 ? 'las tres'
                                : valores.fotos_puestas ? `${valores.fotos_puestas} de 3` : null} />
                    </>
                )}

                {lleva('dieta') && (
                    <>
                        <Renglon testid="rev-dieta" que="Dieta"
                            valor={dieta.dias_periodo ? `${dieta.dias_registrados} de ${dieta.dias_periodo} días` : null}
                            extra={DIFICULTAD[valores.dieta_dificultad]} />
                        <Renglon testid="rev-ajuste" que="Ajuste nuevo" valor={AJUSTE[valores.viabilidad_ajuste]} />
                    </>
                )}

                {/* El entreno se resume distinto según lo que le hayan preguntado, y no se
                    resume nada si no le llegaron a preguntar (sin rutina cargada, el
                    bloque no sale: ver `bloques`). */}
                {perfil === 'sin_rutina' ? (
                    <>
                        <Renglon testid="rev-entreno" que="Entreno" valor={REGULARIDAD[valores.entreno?.regularidad]} />
                        <Renglon testid="rev-rutina-mes" que="La rutina del mes" valor={RUTINA_MES[valores.entreno?.rutina_del_mes]} />
                    </>
                ) : lleva('entreno') ? (
                    <Renglon testid="rev-entreno" que="Entreno"
                        valor={entreno.previstos ? `${entreno.hechos} de ${entreno.previstos}` : null}
                        extra={perfil === 'completo'
                            ? (entreno.media_estrellas ? estrellas(Math.round(entreno.media_estrellas)) : null)
                            : [estrellas(valores.entreno?.estrellas),
                               confirmados ? `${confirmados} confirmados` : null].filter(Boolean).join(' · ')} />
                ) : null}

                {lleva('lesiones') && (
                    <Renglon testid="rev-lesiones" que="Lesiones"
                        valor={lesionesPuestas.length ? enumerar(lesionesPuestas)
                            : valores.lesion_nueva_hay === 'no' ? 'nada nuevo' : null} />
                )}
                {/* Sin sesiones de cardio en su rutina no hay "9 de 16" que enseñar: lo
                    que contestó pasa a ser el valor, en vez de dejar un "sin poner" al
                    lado de una respuesta que sí está puesta. */}
                {lleva('cardio') && (
                    <Renglon testid="rev-cardio" que="Cardio"
                        valor={cardio.previstas
                            ? `${cardio.hechas} de ${cardio.previstas}`
                            : CARDIO[valores.cardio_proximo_mes]}
                        extra={cardio.previstas ? CARDIO[valores.cardio_proximo_mes] : null} />
                )}

                <Renglon testid="rev-suplementacion" que="Suplementación"
                    valor={SUPLEMENTOS[valores.suplementacion?.respuesta]}
                    extra={valores.suplementacion?.detalle ? valores.suplementacion.detalle.trim().slice(0, 40) : null} />

                {/* La energía solo se resume si se le llegó a preguntar. */}
                {lleva('energia') && (
                    <Renglon testid="rev-energia" que="Energía" valor="baja" extra={ENERGIA[valores.energia_motivo]} />
                )}

                <Renglon testid="rev-valoracion" que="Cómo lo valoras" valor={estrellas(valores.valoracion_resultado)} />
                <Renglon testid="rev-motivacion" que="Motivación" valor={estrellas(valores.motivacion)} />
                <Renglon testid="rev-objetivo" que="Próximo objetivo"
                    valor={OBJETIVO[valores.proximo_objetivo]}
                    extra={valores.proximo_objetivo && valores.proximo_objetivo === valores.objetivo_actual ? 'no cambia' : null} />
                <Renglon testid="rev-notas" que="Notas" valor={(valores.notes || '').trim() ? 'escritas' : null} />
            </div>

            <div className="flex gap-2">
                <button type="button" onClick={onVolver} data-testid="volver-al-formulario"
                    className="flex items-center justify-center gap-1.5 px-4 py-3 rounded-xl border border-border text-sm font-bold text-foreground/70 hover:text-foreground">
                    <ChevronLeft className="w-4 h-4" /> Volver
                </button>
                <button type="button" onClick={onEnviar} disabled={enviando} data-testid="submit-report-btn"
                    className="flex-1 py-3 rounded-xl font-bold text-sm uppercase tracking-wider text-white flex items-center justify-center gap-2 transition-all disabled:opacity-40"
                    style={{ backgroundColor: ORANGE }}>
                    <Send className="w-4 h-4" />
                    {enviando ? 'Enviando...' : 'Enviar reporte'}
                </button>
            </div>
        </div>
    );
};

export default RevisaAntesDeEnviar;
