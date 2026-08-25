"""
Configuración centralizada de la aplicación.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

# Database
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']

# JWT
JWT_SECRET = os.environ.get('JWT_SECRET', '12en12-secret-key')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

if JWT_SECRET in ('12en12-secret-key', '12en12-super-secret-jwt-key-2024') or len(JWT_SECRET) < 32:
    import logging
    logging.getLogger("uvicorn.error").warning(
        "JWT_SECRET debil o por defecto: configura una clave aleatoria de 32+ caracteres en el .env / variables de Render"
    )

# CORS
#
# El navegador compara el origen LETRA POR LETRA, asi que un espacio detras de la coma o una
# barra al final dejan fuera a un dominio que parece estar en la lista. Y cuando eso pasa, lo
# que ve el usuario no es "CORS mal configurado": es que no puede iniciar sesion, porque la
# peticion ni sale. Paso el 09-08-2026 con el entorno de Vercel + Render, donde NINGUN origen
# pasaba -- ni siquiera localhost:3000 --, y desde fuera parecia un fallo de contraseña.
#
# Por eso se limpia lo que venga: espacios, barras finales y entradas vacias. Escribir
# "https://a.com, https://b.com/" en el panel de Render tiene que funcionar.
def _origenes(crudo: str):
    lista = [o.strip().rstrip('/') for o in (crudo or '').split(',')]
    return [o for o in lista if o] or ['*']


CORS_ORIGINS = _origenes(os.environ.get('CORS_ORIGINS', '*'))

# Stripe (billing). Test mode by default: STRIPE_SECRET_KEY must be sk_test_...
STRIPE_API_VERSION = "2026-02-25.clover"
STRIPE_ALLOW_LIVE_MODE = os.environ.get('STRIPE_ALLOW_LIVE_MODE', 'false').strip().lower() == 'true'
# Frontend base URL for Stripe success/cancel redirects. Falls back to first CORS origin, else localhost:3000.
FRONTEND_URL = (os.environ.get('FRONTEND_URL') or os.environ.get('APP_BASE_URL') or '').strip()

# LAS VENTANAS DE REPORTE, ABIERTAS SIEMPRE (SOLO EN EL CLON DE PRUEBAS).
#
# El quincenal se rellena el miercoles y el jueves, el mensual de viernes a lunes y el
# semanal de viernes a sabado. Para probarlos hay que esperar a que caiga el dia, y en el
# clon de dev eso no tiene sentido: se prueba cuando se prueba.
#
# Con esto encendido la ventana se da por abierta siempre que ESA SEMANA le toque un
# reporte -- no se inventa uno donde no lo hay --, y la respuesta dice `abierta_por_pruebas`
# con las fechas de verdad al lado, para que en pantalla se lea cuando abre y cierra de
# verdad y nadie confunda el clon con lo que hara un cliente.
#
# Apagado de fabrica: en produccion la variable no existe y todo sigue igual.
VENTANAS_SIEMPRE_ABIERTAS = os.environ.get(
    'VENTANAS_SIEMPRE_ABIERTAS', '').strip().lower() in ('1', 'true', 'si', 'sí')

# Billing cycle (matches calmajp: 12 weeks = 84 days). Change here if cobro mensual.
DEFAULT_BILLING_CYCLE_WEEKS = 12
DEFAULT_BILLING_CYCLE_DAYS = DEFAULT_BILLING_CYCLE_WEEKS * 7

# Cuentas que reciben el chat de "Soporte" (clientes sin entrenador asignado),
# en orden de preferencia. Si ninguna existe se cae al primer admin que no sea uno mismo.
SUPPORT_EMAILS = [
    e.strip().lower()
    for e in os.environ.get(
        'SUPPORT_EMAILS', 'hola@jesusgallegopt.com,admin@jesusgallegopt.com'
    ).split(',')
    if e.strip()
]
