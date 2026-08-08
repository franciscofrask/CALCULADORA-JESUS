import os
import sys

backend_path = os.path.dirname(os.path.abspath(__file__))


def _arrancar():
    """El servidor de verdad, sin recarga (lo relanza watchfiles cuando toca)."""
    os.chdir(backend_path)
    sys.path.insert(0, backend_path)
    import uvicorn
    uvicorn.run('server:app', host='0.0.0.0', port=8000)


if __name__ == '__main__':
    os.chdir(backend_path)
    sys.path.insert(0, backend_path)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(backend_path, '.env'))

    # Auto-recarga en dev, SOLO si el .env lo pide (RELOAD=1). Va con
    # watchfiles.run_process (reinicia el proceso entero) y no con el reload de
    # uvicorn: el de uvicorn mata al worker con una señal de consola que en Windows
    # no llega si el server corre sin consola, y se quedaba "Reloading..." para
    # siempre sirviendo código viejo. En prod la variable no está y esto ni se toca.
    if (os.environ.get('RELOAD') or '').strip() in ('1', 'true', 'si'):
        from watchfiles import run_process, PythonFilter
        # flush: sin él, con la salida redirigida a un log este aviso se queda en el
        # búfer para siempre y parece que la recarga no está activa.
        print('[dev] auto-recarga activa (watchfiles): tocar un .py reinicia el servidor',
              flush=True)
        run_process(backend_path, target=_arrancar, watch_filter=PythonFilter())
    else:
        _arrancar()
