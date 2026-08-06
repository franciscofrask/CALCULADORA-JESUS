"""
Envío de correo.

Hasta hoy la app no mandaba ni un email: todos los avisos eran por la campanita, que
sirve para quien ya está dentro. La recuperación de contraseña no puede serlo -- si no
puedes entrar, no ves la campanita -- y por eso existe esto.

CÓMO SE CONFIGURA
Cinco variables de entorno. Valen las de cualquier proveedor (el correo del propio
dominio, Brevo, Resend, SendGrid...), porque esto habla SMTP a secas y no ata a ninguno:

    SMTP_HOST       smtp.tuproveedor.com
    SMTP_PORT       587 (STARTTLS) o 465 (SSL directo)
    SMTP_USER       usuario
    SMTP_PASSWORD   contraseña
    SMTP_FROM       "12EN12 <hola@jesusgallegopt.com>"

SIN CONFIGURAR NO SE ENVÍA NADA, y es a propósito: en vez de fallar en silencio, el
correo se guarda en `db.correos_pendientes` con su cuerpo entero. Así se ve qué se habría
mandado, no se pierde ninguna petición, y el día que haya credenciales se puede reenviar
lo que quedó atrás. Lo que NUNCA hace es tragarse el error y decir que sí.
"""
import os
import smtplib
import ssl
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional


def configurado() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_FROM"))


def _enviar_sincrono(destinatario: str, asunto: str, cuerpo: str) -> None:
    """Manda el correo. Bloquea, así que se llama desde un hilo (ver `enviar`)."""
    host = os.environ["SMTP_HOST"]
    puerto = int(os.environ.get("SMTP_PORT") or 587)
    usuario = os.environ.get("SMTP_USER") or ""
    clave = os.environ.get("SMTP_PASSWORD") or ""

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = destinatario
    msg.set_content(cuerpo)

    contexto = ssl.create_default_context()
    if puerto == 465:
        with smtplib.SMTP_SSL(host, puerto, context=contexto, timeout=20) as s:
            if usuario:
                s.login(usuario, clave)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, puerto, timeout=20) as s:
            s.starttls(context=contexto)
            if usuario:
                s.login(usuario, clave)
            s.send_message(msg)


async def enviar(db, destinatario: str, asunto: str, cuerpo: str,
                 tipo: str = "generico") -> bool:
    """Manda un correo. Devuelve si salió de verdad.

    Guarda SIEMPRE una copia en `db.correos_pendientes`: si no hay SMTP queda como
    'sin_enviar' con su cuerpo, y si lo hay queda como 'enviado'. Un correo que no se
    manda tiene que poder verse; si no, la única señal es un usuario que no puede entrar.
    """
    import asyncio

    registro = {
        "id": str(uuid.uuid4()),
        "para": destinatario,
        "asunto": asunto,
        "cuerpo": cuerpo,
        "tipo": tipo,
        "estado": "sin_enviar",
        "error": None,
        "creado_en": datetime.now(timezone.utc).isoformat(),
    }

    if not configurado():
        registro["error"] = "SMTP sin configurar (faltan SMTP_HOST / SMTP_FROM)"
        await db.correos_pendientes.insert_one(dict(registro))
        return False

    try:
        # smtplib es bloqueante: fuera del bucle de eventos para no parar el servidor.
        await asyncio.to_thread(_enviar_sincrono, destinatario, asunto, cuerpo)
        registro["estado"] = "enviado"
    except Exception as e:                                   # noqa: BLE001
        registro["error"] = f"{type(e).__name__}: {e}"[:300]

    await db.correos_pendientes.insert_one(dict(registro))
    return registro["estado"] == "enviado"


def texto_recuperar(nombre: Optional[str], enlace: str, horas: int) -> str:
    """El correo de recuperar contraseña. En su tono: corto y sin florituras."""
    saludo = f"Hola {nombre.split()[0]}," if nombre else "Hola,"
    return (
        f"{saludo}\n\n"
        "Has pedido cambiar tu contraseña de 12EN12. Entra aquí y eliges una nueva:\n\n"
        f"{enlace}\n\n"
        f"El enlace vale {horas} horas y solo se puede usar una vez.\n\n"
        "Si no has sido tú, no hace falta que hagas nada: tu contraseña sigue como estaba.\n\n"
        "12EN12"
    )
