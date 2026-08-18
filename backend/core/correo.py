"""
Envío de correo.

Hasta hoy la app no mandaba ni un email: todos los avisos eran por la campanita, que
sirve para quien ya está dentro. La recuperación de contraseña no puede serlo -- si no
puedes entrar, no ves la campanita -- y por eso existe esto.

CÓMO SE CONFIGURA
Variables de entorno. Valen las de cualquier proveedor (el correo del propio dominio,
Postmark, Brevo, Resend, SendGrid...), porque esto habla SMTP a secas y no ata a ninguno:

    SMTP_HOST       smtp.tuproveedor.com
    SMTP_PORT       587 (STARTTLS) o 465 (SSL directo)
    SMTP_USER       usuario
    SMTP_PASSWORD   contraseña
    SMTP_FROM       "12EN12 <noreply@jesusgallegopt.com>"
    SMTP_REPLY_TO   a dónde contesta el cliente si le da a Responder (opcional)

POR QUÉ EL REMITENTE Y EL «RESPONDER A» SON DISTINTOS (13-08-2026)
Quien manda de verdad es el proveedor transaccional, y su dirección tiene que ser una
que el dominio tenga verificada con él: si no, el correo se firma mal y acaba en spam,
que en un aviso de recuperar contraseña es lo mismo que no mandarlo. Pero al cliente que
le da a Responder no se le puede tragar el mensaje un buzón que nadie lee. Así que el
sobre lo pone el proveedor y la respuesta va al buzón del negocio.

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
    responder_a = os.environ.get("SMTP_REPLY_TO")
    if responder_a:
        msg["Reply-To"] = responder_a
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


async def correo_del_cliente(db, user_id: str, de_acceso: str) -> str:
    """A qué correo se le escribe a este cliente.

    Son dos y no son intercambiables (bloque 6 del doc del 18-08). El de ACCESO es con el que
    entra y con el que cruzan los cobros de Stripe: ese no se cambia nunca. El de CONTACTO es
    el que dio en el alta, y es al que se le escribe salvo que en Mi perfil diga lo contrario.

    NO se usa para recuperar la contraseña: ese enlace va siempre al de acceso, porque es la
    llave de la cuenta y no un aviso. Mandarlo al de contacto dejaría a alguien fuera de su
    propia cuenta si escribió mal el correo en el alta.
    """
    perfil = await db.client_profiles.find_one(
        {"user_id": user_id}, {"_id": 0, "email_contacto": 1, "email_preferido": 1}) or {}
    if (perfil.get("email_preferido") or "contacto") == "contacto":
        return perfil.get("email_contacto") or de_acceso
    return de_acceso


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
