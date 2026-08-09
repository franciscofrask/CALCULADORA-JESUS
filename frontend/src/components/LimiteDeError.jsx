import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

/**
 * Corta un fallo de una pantalla para que no se lleve por delante la aplicación entera.
 *
 * El 09-08-2026 `/admin/clients` reventó con «planCatalog is not defined» y la pantalla se
 * quedó COMPLETAMENTE en blanco: sin barra lateral, sin menú, sin nada. React desmonta todo
 * el árbol cuando una excepción sube sin que nadie la recoja, y en la app no había ni un
 * solo `componentDidCatch`. Un error de una variable en una tabla de clientes dejaba al
 * coach sin poder ni volver al panel.
 *
 * Va por DENTRO del layout, envolviendo el `<Outlet />`: si una sección se rompe, el resto
 * de la app -- la navegación, el menú, el resto de pantallas -- sigue en pie, y el usuario
 * puede irse a otro sitio en vez de recargar a ciegas.
 *
 * Se reinicia solo al cambiar de ruta (`clave`): sin eso, una vez roto te quedabas con el
 * cartel de error puesto aunque navegaras a una pantalla que funciona.
 */
class LimiteDeError extends React.Component {
    constructor(props) {
        super(props);
        this.state = { error: null };
    }

    static getDerivedStateFromError(error) {
        return { error };
    }

    componentDidUpdate(prevProps) {
        // Cambió la ruta: se limpia el error y se vuelve a intentar pintar.
        if (prevProps.clave !== this.props.clave && this.state.error) {
            this.setState({ error: null });
        }
    }

    componentDidCatch(error, info) {
        // A la consola con la pila de componentes: es lo que hace falta para localizarlo,
        // y en producción es lo único que va a quedar del fallo.
        console.error('[pantalla rota]', this.props.clave, error, info?.componentStack);
    }

    render() {
        if (!this.state.error) return this.props.children;
        return (
            <div className="p-6 flex items-start justify-center">
                <div className="max-w-lg w-full rounded-xl border border-red-500/30 bg-red-500/5 p-6 space-y-4">
                    <div className="flex items-center gap-3">
                        <AlertTriangle className="w-6 h-6 text-red-400 shrink-0" />
                        <h2 className="text-lg font-semibold">Esta sección ha fallado</h2>
                    </div>
                    <p className="text-sm text-muted-foreground">
                        El resto de la aplicación sigue funcionando: puedes seguir navegando
                        por el menú. Si vuelve a pasar, avísanos y dinos qué estabas haciendo.
                    </p>
                    <p className="text-xs font-mono text-red-300/80 break-all">
                        {String(this.state.error?.message || this.state.error)}
                    </p>
                    <button
                        type="button"
                        onClick={() => this.setState({ error: null })}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm"
                    >
                        <RefreshCw className="w-4 h-4" />
                        Volver a intentarlo
                    </button>
                </div>
            </div>
        );
    }
}

export default LimiteDeError;
