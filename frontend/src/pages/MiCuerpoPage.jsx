/**
 * MiCuerpoPage - El regalo del acceso gratis.
 *
 * "Antes de irte, te digo cuánto músculo tienes. Gratis."
 *
 * Tres datos -- peso, altura y el carrusel de grasa -- y a cambio recibe algo suyo: su
 * índice de muscularidad con su lectura, cuántos kilos lleva de músculo y cuántos de
 * grasa, y cuánto pesaría definido. Esto último no es una promesa: es una resta con sus
 * propios números, y así se dice.
 *
 * El sexo y el objetivo NO se vuelven a preguntar: vienen del test. Preguntar dos veces
 * lo mismo es la forma más rápida de que alguien cierre la pestaña.
 *
 * Y debajo, el momento mágico: "estas son comidas que puedes comer hoy", con recetas
 * cuadradas a sus macros. Ya estaba construido, pero detrás del pago; aquí va delante,
 * que es el único sitio donde sirve para convencer.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import { ArrowRight, Loader2 } from 'lucide-react';
import Logo12EN12 from '../components/Logo12EN12';
import SelectorGrasa from '../components/SelectorGrasa';
import { mensajeDeError } from '../lib/mensajeDeError';

const MiCuerpoPage = () => {
    const navigate = useNavigate();
    const { api, profile } = useAuth();

    const [peso, setPeso] = useState('');
    const [altura, setAltura] = useState('');
    const [grasa, setGrasa] = useState(20);
    const [cargando, setCargando] = useState(false);
    const [ficha, setFicha] = useState(null);
    const [menus, setMenus] = useState(null);

    // Si ya los dio alguna vez, se rellenan: que no vuelva a escribir lo que ya sabemos.
    useEffect(() => {
        if (profile?.weight) setPeso(String(profile.weight));
        if (profile?.height) setAltura(String(profile.height));
        if (profile?.body_fat) setGrasa(Number(profile.body_fat));
    }, [profile]);

    const calcular = async (e) => {
        e.preventDefault();
        if (!peso) { toast.error('Dinos cuánto pesas'); return; }
        setCargando(true);
        try {
            const r = await api.post('/clients/mi-cuerpo', {
                peso: Number(peso),
                altura: altura ? Number(altura) : null,
                porcentaje_graso: grasa,
            });
            setFicha(r.data);
            cargarMenus();
        } catch (err) {
            toast.error(mensajeDeError(err, 'No hemos podido calcularlo'));
        } finally {
            setCargando(false);
        }
    };

    // El momento mágico: tres recetas cuadradas a sus macros. Se piden aparte y sin
    // bloquear: si fallan, el regalo principal ya está en pantalla.
    const cargarMenus = async () => {
        try {
            const cat = await api.get('/calculator/menu-catalog');
            const todas = (cat.data?.menus || []).filter(m => (m.momentos || []).includes('comida'));
            const elegidas = todas.slice(0, 6);
            const hechas = await Promise.all(elegidas.map(r =>
                api.post('/calculator/menu-apply', { plantilla_id: r.id, mealKey: 'C1', macros_objetivo: {} })
                    .then(res => res.data).catch(() => null)
            ));
            setMenus(hechas.filter(Boolean).sort((a, b) => (a.err ?? 999) - (b.err ?? 999)).slice(0, 3));
        } catch {
            setMenus([]);
        }
    };

    const Dato = ({ valor, unidad, etiqueta }) => (
        <div className="rounded-2xl border-2 border-border bg-card p-4 text-center">
            <p className="font-heading font-extrabold text-3xl text-brand leading-none">
                {valor}<span className="text-base text-foreground/40 ml-0.5">{unidad}</span>
            </p>
            <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-bold mt-2">{etiqueta}</p>
        </div>
    );

    // ── El resultado ──────────────────────────────────────────────────────────
    if (ficha) {
        const c = ficha.composicion;
        return (
            <div className="min-h-screen bg-background text-foreground px-4 py-10">
                <div className="max-w-2xl mx-auto">
                    <div className="flex justify-center mb-8"><Logo12EN12 size="md" /></div>

                    <p className="caption text-brand text-center mb-2">De qué estás hecho</p>
                    <h1 className="font-heading text-3xl sm:text-4xl font-bold uppercase text-center mb-8 leading-tight">
                        Esto es lo que llevas encima
                    </h1>

                    <div className="grid grid-cols-2 gap-3 mb-4">
                        <Dato valor={c.masa_magra} unidad="kg" etiqueta="De músculo" />
                        <Dato valor={c.masa_grasa} unidad="kg" etiqueta="De grasa" />
                    </div>

                    {c.indice_muscular != null ? (
                        <div className="rounded-2xl border-2 border-brand/40 bg-brand/5 p-5 mb-4" data-testid="mi-cuerpo-indice">
                            <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-bold">
                                Tu índice de muscularidad
                            </p>
                            <p className="font-heading font-extrabold text-4xl text-brand mt-1">{c.indice_muscular}</p>
                            <p className="text-foreground/80 mt-1">
                                Estás <span className="font-bold text-foreground">{c.indice_muscular_lectura}</span> para tu altura.
                            </p>
                        </div>
                    ) : (
                        <p className="text-sm text-muted-foreground mb-4">
                            Con tu altura te diría además cuánto músculo llevas para lo que mides.
                        </p>
                    )}

                    {ficha.definido && (
                        <div className="rounded-2xl border-2 border-border bg-card p-5 mb-4" data-testid="mi-cuerpo-definido">
                            <p className="text-[15px] leading-relaxed">
                                Si mantienes tu músculo y bajas al{' '}
                                <span className="font-bold">{ficha.definido.grasa_objetivo} %</span> de grasa,
                                pesarías <span className="font-heading font-extrabold text-2xl text-brand">{ficha.definido.peso} kg</span>.
                            </p>
                            <p className="text-xs text-muted-foreground mt-2">
                                No es una promesa: es una resta con tus propios números.
                            </p>
                        </div>
                    )}

                    {/* El momento mágico, delante del pago y no detrás. */}
                    <h2 className="font-heading text-xl font-bold uppercase mt-10 mb-1">
                        Y esto puedes comértelo hoy
                    </h2>
                    <p className="text-sm text-muted-foreground mb-4">
                        Recetas con las cantidades ya puestas para lo que te toca a ti.
                    </p>

                    {menus === null ? (
                        <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-brand" /></div>
                    ) : menus.length === 0 ? (
                        <p className="text-sm text-muted-foreground">Los tienes en Nutrición, en "Sugiéreme un menú".</p>
                    ) : (
                        <div className="space-y-3" data-testid="mi-cuerpo-menus">
                            {menus.map((m, i) => (
                                <div key={m.plantilla_id || i} className="rounded-xl border-2 border-[#222222] bg-card p-4">
                                    <p className="font-black text-foreground mb-1">{m.nombre}</p>
                                    <p className="text-sm font-black text-brand mb-1.5">
                                        {Math.round(m.macros_totales?.P || 0)}P · {Math.round(m.macros_totales?.H || 0)}H · {Math.round(m.macros_totales?.G || 0)}G
                                    </p>
                                    <ul className="space-y-0.5">
                                        {(m.items || []).map((it, j) => (
                                            <li key={j} className="text-sm text-foreground/80">
                                                <span className="font-bold text-brand">{it.cantidad_display}</span> {it.nombre}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ))}
                        </div>
                    )}

                    <button onClick={() => navigate('/planes')} data-testid="mi-cuerpo-planes"
                        className="w-full mt-10 h-14 rounded-2xl bg-brand hover:bg-brand/90 text-white font-bold text-lg inline-flex items-center justify-center gap-2 transition-colors">
                        Quiero hacerlo en serio <ArrowRight className="w-5 h-5" />
                    </button>
                    <button onClick={() => navigate('/dashboard')}
                        className="w-full mt-3 h-12 text-muted-foreground hover:text-foreground text-sm transition-colors">
                        Ahora no, quiero mirar la app
                    </button>
                </div>
            </div>
        );
    }

    // ── Los tres datos ────────────────────────────────────────────────────────
    return (
        <div className="min-h-screen bg-background text-foreground px-4 py-10">
            <div className="max-w-xl mx-auto">
                <div className="flex justify-center mb-8"><Logo12EN12 size="md" /></div>

                <h1 className="font-heading text-3xl sm:text-4xl font-bold uppercase leading-tight mb-2">
                    Cuánto músculo tienes
                </h1>
                <p className="text-muted-foreground mb-8">
                    Tres datos y te lo decimos. Nada más.
                </p>

                <form onSubmit={calcular} className="space-y-6">
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="block text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1.5">
                                Peso (kg)
                            </label>
                            <input type="number" min="30" max="300" step="0.1" value={peso} required
                                onChange={e => setPeso(e.target.value)} placeholder="80" data-testid="mi-cuerpo-peso"
                                className="w-full h-14 px-4 rounded-xl bg-muted text-lg font-bold outline-none focus:ring-2 focus:ring-brand" />
                        </div>
                        <div>
                            <label className="block text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1.5">
                                Altura (cm)
                            </label>
                            <input type="number" min="120" max="230" value={altura}
                                onChange={e => setAltura(e.target.value)} placeholder="178" data-testid="mi-cuerpo-altura"
                                className="w-full h-14 px-4 rounded-xl bg-muted text-lg font-bold outline-none focus:ring-2 focus:ring-brand" />
                        </div>
                    </div>
                    <p className="text-xs text-muted-foreground -mt-3">
                        Pésate siempre igual: en ayunas, sin ropa y después de ir al baño.
                    </p>

                    <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">
                            ¿Cuál dirías que es tu % de grasa?
                        </label>
                        <SelectorGrasa value={grasa} onChange={setGrasa} />
                    </div>

                    <button type="submit" disabled={cargando} data-testid="mi-cuerpo-calcular"
                        className="w-full h-14 rounded-2xl bg-brand hover:bg-brand/90 text-white font-bold text-lg disabled:opacity-60 inline-flex items-center justify-center gap-2">
                        {cargando ? <><Loader2 className="w-5 h-5 animate-spin" /> Calculando...</> : <>Verlo <ArrowRight className="w-5 h-5" /></>}
                    </button>
                </form>
            </div>
        </div>
    );
};

export default MiCuerpoPage;
