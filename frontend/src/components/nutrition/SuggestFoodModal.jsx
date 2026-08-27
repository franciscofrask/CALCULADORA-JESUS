import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { useAuth } from '../../context/AuthContext';
import { toast } from 'sonner';
import { Camera, Check, Loader2 } from 'lucide-react';
import { mensajeDeError } from '../../lib/mensajeDeError';

/**
 * «SOLICITAR UN ALIMENTO» (puntos 161 a 169 del 27-08).
 *
 * CUATRO BLOQUES, Y CADA UNO MIRA A UN SITIO DEL ENVASE (punto 162):
 *
 *   Qué es      · el nombre y la foto frontal      -> los dos miran la cara del envase
 *   Los macros  · la foto del reverso, de qué son los números, y los números -> la tabla
 *   Cómo viene  · lata o conserva
 *   De dónde sale · el enlace
 *
 * Antes los números iban ANTES que las fotos, así que el cliente tenía que ir y venir: mirar
 * la tabla, escribir, volver a mirar. Con este orden hace la foto, la está viendo, y desde
 * ahí contesta lo demás sin cambiar de sitio.
 *
 * Y TODO ES OBLIGATORIO (punto 161). Se podía enviar con el nombre y nada más -- las fotos
 * salían como «opcionales, pero ayudan a la revisión» --, y una solicitud así no se puede dar
 * de alta: hay que escribirle, preguntarle y esperar. Era el cuello de botella entero.
 * Asterisco naranja en vez de escribir «obligatorio» siete veces, y el botón apagado hasta el
 * final con «Te faltan 3 campos por rellenar» debajo. El que está dispuesto a hacer dos fotos
 * y copiar tres números lo necesita de verdad.
 *
 * El servidor comprueba lo mismo (`POST /calculator/suggest-food`): el botón apagado evita el
 * descuido, no la pantalla vieja que se haya quedado en la caché de alguien.
 */

const EMPTY = {
    nombre: '',
    por_unidad: null,     // null = sin contestar; el botón no se enciende hasta que diga una
    racion: '',           // gramos de la unidad (sólo si por_unidad)
    es_conserva: null,    // null = sin contestar
    peso_tipo: '',        // 'escurrido' | 'neto', sólo si es conserva
    proteinas: '',
    hidratos: '',
    grasas: '',
    url: '',
    sin_web: false,
};

const Obligatorio = () => <span className="text-brand-orange ml-0.5">*</span>;

const Bloque = ({ titulo, children }) => (
    <section className="space-y-3">
        <p className="caption">{titulo}</p>
        {children}
    </section>
);

// LA FOTO, CON LO QUE TIENE QUE SALIR EN ELLA (punto 163). «O lateral» importa: en las latas,
// los briks y las botellas la tabla está en el lateral, no detrás, y si pone «la de detrás»
// el cliente duda o hace la foto equivocada. Y «valor nutricional» es lo que viene impreso en
// el envase: es lo que va a buscar con los ojos.
const CampoFoto = ({ etiqueta, ayuda, file, onChange }) => (
    <div>
        <label className="block text-xs font-semibold text-muted-foreground mb-1">
            {etiqueta}<Obligatorio />
        </label>
        <label className={`flex items-center gap-3 border rounded-lg p-3 cursor-pointer transition-colors ${
            file ? 'border-ok/60 bg-ok/5' : 'border-dashed border-input hover:border-brand-orange/60'}`}>
            <span className={`w-11 h-11 rounded flex items-center justify-center flex-shrink-0 ${
                file ? 'bg-ok/15' : 'bg-muted'}`}>
                {file ? <Check className="w-5 h-5 text-ok" /> : <Camera className="w-5 h-5 text-muted-foreground" />}
            </span>
            <span className="min-w-0">
                <span className="block text-sm font-medium text-foreground">{file ? 'Hecha' : 'Hacer foto'}</span>
                <span className="block text-xs text-muted-foreground">{ayuda}</span>
            </span>
            {/* `capture` no fuerza nada en el ordenador -- ahí abre el explorador de siempre --
                y en el móvil abre la cámara, que es donde se hace esto. */}
            <input type="file" accept="image/*" capture="environment" className="hidden"
                onChange={e => onChange(e.target.files?.[0] || null)} />
        </label>
    </div>
);

const CampoNumero = ({ etiqueta, valor, onChange }) => (
    <div>
        <label className="block text-xs font-semibold text-muted-foreground mb-1">{etiqueta}</label>
        <input type="number" min="0" step="0.1" inputMode="decimal" value={valor}
            onChange={e => onChange(e.target.value)}
            className="w-full border border-input rounded-lg px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-brand-orange/40" />
    </div>
);

// Dos botones en vez de una casilla: una casilla marcada o sin marcar no dice si la ha visto
// o si la ha dejado como estaba, y aquí hace falta que CONTESTE.
const DosBotones = ({ etiqueta, ayuda, valor, opciones, onChange, testId }) => (
    <div>
        <label className="block text-xs font-semibold text-muted-foreground mb-1">
            {etiqueta}<Obligatorio />
        </label>
        <div className="grid grid-cols-2 gap-2" data-testid={testId}>
            {opciones.map(([v, texto]) => (
                <button key={String(v)} type="button" role="radio" aria-checked={valor === v}
                    onClick={() => onChange(v)}
                    className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                        valor === v
                            ? 'border-brand-orange bg-brand-orange text-white'
                            : 'border-input bg-card text-muted-foreground hover:text-foreground'}`}>
                    {texto}
                </button>
            ))}
        </div>
        {ayuda && <p className="text-xs text-muted-foreground mt-1">{ayuda}</p>}
    </div>
);

const SuggestFoodModal = ({ open, onClose, onSubmitted }) => {
    const { api } = useAuth();
    const [form, setForm] = useState(EMPTY);
    const [frontal, setFrontal] = useState(null);
    const [reverso, setReverso] = useState(null);
    const [saving, setSaving] = useState(false);
    const [restantes, setRestantes] = useState(null);

    const set = (k, v) => setForm(prev => ({ ...prev, [k]: v }));
    const reset = () => { setForm(EMPTY); setFrontal(null); setReverso(null); };
    const close = () => { if (!saving) { reset(); onClose(); } };

    // Cuántas le quedan esta semana. Se pide al abrir: enterarse del límite DESPUÉS de hacer
    // dos fotos y copiar tres números es la peor forma posible de enterarse.
    useEffect(() => {
        if (!open) return;
        let vivo = true;
        api.get('/calculator/food-suggestions/restantes')
            .then(r => { if (vivo) setRestantes(r.data?.restantes ?? null); })
            .catch(() => { /* si no se sabe, no se dice: mejor callar que dar un número falso */ });
        return () => { vivo = false; };
    }, [open, api]);

    // LO QUE FALTA, CONTADO (punto 161). El botón dice el número, no cuál: el que va por el
    // formulario de arriba abajo ya ve dónde está el hueco, y una lista de nombres de campo
    // debajo del botón es ruido.
    const loQueFalta = [
        !form.nombre.trim(),
        !frontal,
        !reverso,
        form.por_unidad === null,
        form.por_unidad === true && !(Number(form.racion) > 0),
        !['proteinas', 'hidratos', 'grasas'].some(k => Number(form[k]) > 0),
        form.es_conserva === null,
        // Si es lata y ya dio un peso por unidad, hay que saber si ese peso es el escurrido.
        form.es_conserva === true && !form.peso_tipo,
        !form.url.trim() && !form.sin_web,
    ].filter(Boolean).length;

    const submit = async () => {
        if (loQueFalta || saving) return;
        const fd = new FormData();
        fd.append('nombre', form.nombre.trim());
        fd.append('por_unidad', form.por_unidad ? 'true' : 'false');
        fd.append('racion', form.por_unidad ? String(form.racion) : '100');
        fd.append('es_conserva', form.es_conserva ? 'true' : 'false');
        fd.append('peso_tipo', form.peso_tipo || 'neto');
        fd.append('proteinas', String(form.proteinas || 0));
        fd.append('hidratos', String(form.hidratos || 0));
        fd.append('grasas', String(form.grasas || 0));
        fd.append('sin_web', form.sin_web ? 'true' : 'false');
        if (form.url.trim()) fd.append('url', form.url.trim());
        fd.append('foto_frontal', frontal);
        fd.append('foto_reverso', reverso);

        setSaving(true);
        try {
            await api.post('/calculator/suggest-food', fd);
            toast.success('Pedido. Entra en el listado del próximo viernes a las 10.');
            reset();
            onClose();
            onSubmitted?.();
        } catch (e) {
            toast.error(mensajeDeError(e, 'No se pudo mandar la solicitud'));
        } finally {
            setSaving(false);
        }
    };

    // El peso que ya ha escrito, para repetírselo donde hace falta (puntos 164 y 165).
    const peso = Number(form.racion) > 0 ? `${form.racion} g` : 'esa unidad';

    return (
        <Dialog open={open} onOpenChange={(o) => !o && close()}>
            <DialogContent className="max-w-lg max-h-[90vh] flex flex-col p-0 gap-0 overflow-hidden">
                <DialogHeader className="bg-bg-dark p-4 flex-shrink-0">
                    <DialogTitle className="text-white">Solicitar un alimento</DialogTitle>
                    {/* EL AVISO DE ARRIBA, CON LOS PLAZOS (punto 168). Antes no decía ni cuándo
                        lo iba a tener ni que le fueran a avisar, así que preguntaba por el chat
                        a los dos días. Y el corte del martes es lo que hace que la promesa se
                        pueda cumplir: sin corte, lo que entra el jueves por la noche tendría
                        que estar el viernes a las 10.
                        Aquí iba «El equipo lo revisará y, si procede, lo añadirá a la
                        calculadora» (punto 169): esto dice lo mismo mejor y además dice cuándo,
                        y de paso desaparece una de las frases en tercera persona. */}
                    <DialogDescription className="text-white/70 text-sm">
                        Antes de pedirlo, búscalo bien: prueba también con el nombre sin la marca.
                        <br />
                        Si definitivamente no está, rellena el formulario y lo damos de alta.
                        Actualizamos el listado todos los viernes a las 10 con las nuevas peticiones.
                        Recogemos las solicitudes hasta el martes: si mandas la tuya después, entra
                        la semana siguiente.
                    </DialogDescription>
                </DialogHeader>

                <div className="p-4 overflow-y-auto space-y-5 bg-card">
                    <Bloque titulo="Qué es">
                        <div>
                            <label className="block text-xs font-semibold text-muted-foreground mb-1">
                                ¿Qué es?<Obligatorio />
                            </label>
                            <input type="text" value={form.nombre} data-testid="solicitar-nombre"
                                onChange={e => set('nombre', e.target.value)}
                                placeholder="Nombre exacto. Si tiene marca, entre paréntesis"
                                className="w-full border border-input rounded-lg px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-brand-orange/40" />
                            {/* «Del envase» y no «de la etiqueta» (punto 169): un genérico no
                                tiene etiqueta, que es lo mismo que se corrigió en el buscador. */}
                            <p className="text-xs text-muted-foreground mt-1">
                                Ej.: «Yogur proteico (Hacendado)». Si no tiene marca, sólo el nombre: «Almendras».
                            </p>
                        </div>
                        <CampoFoto etiqueta="Foto frontal" ayuda="Que se vea el nombre del alimento"
                            file={frontal} onChange={setFrontal} />
                    </Bloque>

                    <Bloque titulo="Los macros">
                        <CampoFoto etiqueta="Foto del reverso o lateral" ayuda="Que se vea el valor nutricional"
                            file={reverso} onChange={setReverso} />

                        {/* VA JUSTO DEBAJO DE LAS FOTOS (punto 164): acaba de hacer la de la
                            tabla, la está mirando, y es justo donde se ve. */}
                        <DosBotones etiqueta="¿Los macros salen por 100 g o por unidad?"
                            testId="solicitar-por-unidad" valor={form.por_unidad}
                            opciones={[[false, 'Por 100 g'], [true, 'Por unidad']]}
                            onChange={v => set('por_unidad', v)} />

                        {form.por_unidad === true && (
                            <div>
                                <label className="block text-xs font-semibold text-muted-foreground mb-1">
                                    Anota el peso de la unidad<Obligatorio />
                                </label>
                                <input type="number" min="1" step="1" inputMode="numeric" value={form.racion}
                                    data-testid="solicitar-racion"
                                    onChange={e => set('racion', e.target.value)} placeholder="125 g"
                                    className="w-full border border-input rounded-lg px-3 py-2 text-sm bg-card focus:outline-none focus:ring-2 focus:ring-brand-orange/40" />
                            </div>
                        )}

                        <div>
                            {/* EL TÍTULO REPITE EL PESO QUE ACABA DE ESCRIBIR (punto 164): está
                                leyendo su propio número de hace dos segundos, así que es difícil
                                que ponga los de 100 g por error. */}
                            <label className="block text-xs font-semibold text-muted-foreground mb-1">
                                {form.por_unidad === true
                                    ? `Anota los macros de esa unidad de ${peso}`
                                    : 'Anota los macros por 100 g'}<Obligatorio />
                            </label>
                            <div className="grid grid-cols-3 gap-2" data-testid="solicitar-macros">
                                <CampoNumero etiqueta="Proteína" valor={form.proteinas} onChange={v => set('proteinas', v)} />
                                <CampoNumero etiqueta="Hidratos" valor={form.hidratos} onChange={v => set('hidratos', v)} />
                                <CampoNumero etiqueta="Grasa" valor={form.grasas} onChange={v => set('grasas', v)} />
                            </div>
                            <p className="text-xs text-muted-foreground mt-1">
                                {form.por_unidad === true
                                    ? 'En la tabla suelen venir dos columnas. Coge la del envase - no la de 100 g.'
                                    : 'Cópialos del envase tal cual.'}
                            </p>
                        </div>
                    </Bloque>

                    <Bloque titulo="Cómo viene">
                        <DosBotones etiqueta="¿Viene en lata o en conserva?"
                            testId="solicitar-conserva" valor={form.es_conserva}
                            opciones={[[false, 'No'], [true, 'Sí']]}
                            onChange={v => set('es_conserva', v)}
                            ayuda={form.es_conserva === null && form.por_unidad === true
                                ? 'Si es que sí, te preguntamos si el peso que has puesto es el escurrido o el neto.'
                                : null} />

                        {/* LAS LATAS: EL PESO NO SE PIDE DOS VECES (punto 165). Una lata es las
                            dos cosas a la vez -- va por unidad y es conserva --, así que si ya
                            ha dado el peso de la unidad, pedirle además el escurrido es pedirle
                            dos veces lo mismo, y ahí es donde uno de los dos sale mal. Un toque
                            en vez de un campo. Y si dice que es el neto, ahí sí se le pide el
                            escurrido, que es el que vale. */}
                        {form.es_conserva === true && form.por_unidad === true && (
                            <DosBotones etiqueta={`¿Esos ${peso} son el peso escurrido?`}
                                testId="solicitar-escurrido" valor={form.peso_tipo}
                                opciones={[['escurrido', 'Sí, el escurrido'], ['neto', 'No, el peso neto']]}
                                onChange={v => set('peso_tipo', v)}
                                ayuda="El que pone en el bote como peso neto escurrido." />
                        )}
                        {form.es_conserva === true && form.por_unidad !== true && (
                            <DosBotones etiqueta="¿El peso del bote es el escurrido o el neto?"
                                testId="solicitar-escurrido" valor={form.peso_tipo}
                                opciones={[['escurrido', 'El escurrido'], ['neto', 'El neto']]}
                                onChange={v => set('peso_tipo', v)} />
                        )}
                    </Bloque>

                    <Bloque titulo="De dónde sale">
                        {/* EL ENLACE SIRVE PARA DOS COSAS (punto 166): verificar los números y
                            alimentar el botón «Ver web ↗» de la ficha del alimento. Son el mismo
                            dato en dos sitios, y sin él ese botón no puede existir. */}
                        <div>
                            <label className="block text-xs font-semibold text-muted-foreground mb-1">
                                Enlace de la fuente<Obligatorio />
                            </label>
                            <input type="url" value={form.url} data-testid="solicitar-url"
                                onChange={e => set('url', e.target.value)}
                                disabled={form.sin_web} placeholder="https://…"
                                className="w-full border border-input rounded-lg px-3 py-2 text-sm bg-card disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-brand-orange/40" />
                            <p className="text-xs text-muted-foreground mt-1">
                                De dónde has sacado los números. Si no lo encuentras, búscalo en OpenFoodFacts.
                            </p>
                            {/* La salida: un genérico no tiene web. Si alguien pide carne de
                                potro no hay enlace que pegar, y sin esto se queda atascado. */}
                            <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer mt-2">
                                <input type="checkbox" checked={form.sin_web} data-testid="solicitar-sin-web"
                                    onChange={e => set('sin_web', e.target.checked)}
                                    className="w-4 h-4 accent-brand-orange" />
                                No tiene web
                            </label>
                        </div>
                    </Bloque>
                </div>

                <div className="p-4 border-t border-border bg-card flex-shrink-0">
                    {/* EL BOTÓN (punto 167). Era «Enviar sugerencia» y salía en VERDE, y en esta
                        app el verde significa «ese macro ya está resuelto»: era el tercer color
                        de fuera de sistema de este circuito, con el amarillo del botón de arriba
                        y el azul de los hidratos. Naranja, y apagado hasta el final. */}
                    <button onClick={submit} disabled={saving || loQueFalta > 0}
                        data-testid="solicitar-enviar"
                        className={`w-full font-semibold rounded-lg py-2.5 text-sm flex items-center justify-center gap-2 transition-colors ${
                            loQueFalta > 0 || saving
                                ? 'bg-muted text-muted-foreground cursor-not-allowed'
                                : 'bg-brand-orange hover:bg-brand-orange/90 text-white'}`}>
                        {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                        Solicitarlo
                    </button>
                    {loQueFalta > 0 && (
                        <p className="text-xs text-muted-foreground text-center mt-2" data-testid="solicitar-faltan">
                            Te {loQueFalta === 1 ? 'falta 1 campo' : `faltan ${loQueFalta} campos`} por rellenar
                        </p>
                    )}
                    {restantes != null && (
                        <p className="text-xs text-muted-foreground text-center mt-2" data-testid="solicitar-restantes">
                            {/* «petición» pierde la tilde en plural: pegarle «es» daba
                                «peticiónes». Las dos formas escritas enteras y sin montarlas
                                con trozos, que es donde se cuela la falta. */}
                            {restantes === 0
                                ? 'Ya has gastado tus peticiones de esta semana'
                                : restantes === 1
                                    ? 'Te queda 1 petición esta semana'
                                    : `Te quedan ${restantes} peticiones esta semana`}
                        </p>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default SuggestFoodModal;
