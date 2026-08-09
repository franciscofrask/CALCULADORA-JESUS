# Tocar los datos de producción desde local

Hasta ahora, cada vez que había que mirar o arreglar algo de los datos de producción, el
camino era: escribir un script, `scp` al VPS, `kubectl cp` al pod, ejecutarlo dentro y
borrarlo. Tres saltos, dos minutos por vuelta y ningún sitio donde ver el resultado más que
la salida del terminal.

Mongo de producción vive **en el host del VPS**, no en k3s, y solo escucha en local:

```
127.0.0.1:27017     mongod
 10.0.0.1:27017     mongod    (el puente de k3s, para los pods)
```

Es decir: no está expuesto a internet -- bien -- y por eso hace falta un túnel.

## El túnel

```bash
ssh -i ~/.ssh/id_ed25519_jg12 -N -L 27018:127.0.0.1:27017 root@s1.jesusgallegopt.com
```

Se deja corriendo en una terminal aparte. Mientras esté abierto, `localhost:27018` **es**
Mongo de producción.

**El puerto local es el 27018 a propósito, no el 27017.** Cualquier cosa que se conecte al
puerto de siempre sin pensar -- Compass, un script con la URL por defecto, el backend local
si alguien le quita el `.env` -- se encuentra con que ahí no hay nada, en vez de encontrarse
con la base de producción. Es la diferencia entre un error y un desastre.

## Usarlo

Nada lee este túnel por su cuenta: hay que pasarle la URL a mano, y esa es la segunda red de
seguridad.

```bash
cd backend
MONGO_URL="mongodb://localhost:27018" DB_NAME=jg12_restored \
  ./venv/Scripts/python.exe _lo_que_sea.py
```

Comprobación de que estás donde crees (producción tiene 188 clientes y 3.211 alimentos; dev
en Atlas tiene otros números):

```bash
MONGO_URL="mongodb://localhost:27018" DB_NAME=jg12_restored \
  ./venv/Scripts/python.exe -c "
import asyncio, os
from motor.motor_asyncio import AsyncIOMotorClient
async def m():
    db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    print('clientes:', await db.client_profiles.count_documents({}))
asyncio.run(m())"
```

## Las reglas, que no cambian

Esto acorta el camino; **no cambia lo que se puede hacer**.

1. **El código viaja, los datos no.** Nunca volcar Atlas (dev) encima de producción. Son dos
   bases distintas con el mismo nombre, y esa es justo la trampa.
2. **Backup antes de escribir.** Leer, todo lo que haga falta. Escribir, con copia previa.
3. **Ensayo primero.** Los scripts de datos de este repo (`_limpiar_historial_macros.py`,
   `_duplicados_catalogo.py`) van en modo ensayo por defecto y solo tocan algo con `--hazlo`.
   Si escribes uno nuevo, que sea igual.
4. **Cerrar el túnel al terminar.** Un `Ctrl+C` en su terminal. Un túnel abierto a la base de
   los clientes que paga la gente no es algo que se deje puesto de fondo.

## Lo que NO hay que hacer con esto

Los scripts de limpieza son **de una sola vez**. `_limpiar_historial_macros.py` corrió en
producción el 09-08-2026 y dejó la base así:

```
3.596 filas  ->  3.500      (50 huérfanas + 46 duplicadas, archivadas en macro_history_auditoria)
índice único (cliente, fecha de vigencia): creado
```

A partir de ahí no hace nada: el upsert de `core/historial_macros.py` impide que se vuelvan a
crear duplicados y el índice único es el cinturón. Una segunda pasada dice «0 huérfanas, 0
duplicadas» y se va. **No hay que meterlo en ningún cron ni en el arranque**: si algún día
vuelve a encontrar duplicados, eso no es rutina, es un aviso de que algo se ha roto.
