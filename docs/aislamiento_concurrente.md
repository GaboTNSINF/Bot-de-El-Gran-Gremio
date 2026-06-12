# Plan de Aislamiento Concurrente en Capa de Datos

Este documento define la arquitectura técnica estandarizada para prevenir condiciones de carrera (*race conditions*) y asegurar la consistencia transaccional (ACID) en entornos de alta concurrencia asíncrona dentro del bot, con un enfoque particular en los módulos críticos financieros y de inventario (`economia.py`, `tienda.py`).

## 1. El Antipatrón Descartado: Conexión Única y Bloqueos de Nivel de Aplicación

En iteraciones previas del sistema, el diseño empleaba una única instancia global de conexión a la base de datos (`_connection`) acoplada a un semáforo de Python (`asyncio.Lock()`). Este diseño fue rechazado por constituir un riesgo crítico en producción:

1.  **Bloqueo de I/O y Degradación de Rendimiento (Task Starvation):** Un único `Lock` convierte un sistema concurrente basado en corrutinas en un embudo secuencial síncrono. Mientras una operación de escritura larga monopoliza el `Lock`, las lecturas y otras transacciones colapsan por inactividad de evento, derivando en tiempos de espera prolongados en la API de Discord.
2.  **Contaminación de Transacciones y Ruptura de Aislamiento:** En SQLite, una transacción (por ejemplo, `BEGIN TRANSACTION;`) pertenece al manejador de la conexión. Si múltiples corrutinas asíncronas envían comandos `INSERT` o `UPDATE` simultáneamente a través del **mismo** descriptor global, SQLite las fusiona indiscriminadamente en el mismo contexto de la transacción abierta. Si una de las corrutinas falla y ejecuta un `ROLLBACK`, destruye el progreso de las corrutinas adyacentes. Si otra ejecuta un `COMMIT` prematuro, rompe la atomicidad del bloque originario, produciendo errores `OperationalError: transaction within a transaction`.

## 2. Implementación Correcta: Aislamiento por Descriptor de Conexión Efímera

Para alcanzar verdadera concurrencia y seguridad relacional bajo un servidor asíncrono, la capa de persistencia (`database.py`) debe gestionar ciclos de vida cortos (*ephemeral connection lifecycles*). En este diseño:

1.  **Ciclo de vida local:** Cada función de negocio que implique una transacción en la base de datos (por ejemplo, `procesar_compra_gremial` o `transferir_fondos`) no reutiliza una tubería global; instancia localmente su propia conexión, encapsulada mediante manejadores de contexto (`async with aiosqlite.connect(DB_PATH) as db:`).
2.  **Aislamiento:** Esto garantiza que cada transacción opere de manera aislada con su propio descriptor de archivo a nivel del sistema operativo. Un `ROLLBACK` o un `COMMIT` en la Operación A jamás contamina la memoria de estado de la Operación B.

## 3. Delegación de la Concurrencia al Motor de la Base de Datos (WAL & File Locking)

Eliminar los `asyncio.Lock` en Python implica transferir la responsabilidad de gestionar las colisiones directamente al núcleo de SQLite. Esto se logra ejecutando los siguientes pragmas nativos inmediatamente al instanciar cada conexión:

*   `PRAGMA journal_mode = WAL;`
*   `PRAGMA busy_timeout = 5000;`

### La Mecánica del WAL (*Write-Ahead Logging*)

En el modo de bitácora clásico (`DELETE`), una transacción de modificación de datos debe adquirir un candado exclusivo que congela todo el archivo de base de datos, impidiendo no solo otras escrituras, sino también bloqueando a los lectores (e.g., consultar el saldo o invocar un perfil) y provocando cuellos de botella críticos de latencia.

Al habilitar `WAL`, el motor no altera el archivo primario (`.db`) durante las escrituras, sino que concatena los cambios de manera secuencial a un diario auxiliar (`.db-wal`).
*   **Lectura y Escritura Simultánea:** Múltiples corrutinas pueden ejecutar comandos `SELECT` (lecturas) de forma ininterrumpida mientras una corrutina simultánea se encuentra consolidando modificaciones (escrituras) en una tabla.

### Prevención de Deadlocks con `busy_timeout`

Al suprimir el semáforo de exclusión mutua de Python, es imperativo gestionar los conflictos de escritura nativos. Si el Usuario A (Conexión 1) y el Usuario B (Conexión 2) intentan insertar datos al mismo milisegundo, SQLite debe resolver quién adquiere el candado de escritura exclusivo a nivel de disco.
El `PRAGMA busy_timeout = 5000;` instruye al sistema operativo y a SQLite a que, en caso de colisión de bloqueos, no se levante instantáneamente un error `sqlite3.OperationalError: database is locked`. En su lugar, el motor de SQLite reintenta internamente adquirir el candado iterando (*sleeping/polling*) durante un máximo de 5000 milisegundos. Esta configuración asegura de forma pasiva la integridad referencial sin saturar la aplicación.

## 4. Consistencia Transaccional: Actualizaciones Delta (*Atomic Delta Updates*)

El aspecto más crítico de la prevención de condiciones de carrera lógicas es abandonar el antipatrón *read-modify-write* gestionado desde la memoria de la aplicación (e.g., leer el saldo del usuario con un `SELECT`, restar la cantidad en Python, y emitir un `UPDATE` del valor resultante).

Toda transacción monetaria y de consumo de inventario operará bajo delegación de validación nativa al motor. La instrucción de decremento financiero se redacta así:

```sql
UPDATE economia_billetera
SET balance_pc = balance_pc - ?
WHERE user_id = ? AND balance_pc >= ?
```

**Mecanismo de Prevención:**
Esta instrucción es intrínsecamente atómica a nivel de CPU. Si dos compras simultáneas para el mismo usuario se validan, se evalúa la condición `WHERE` localmente durante la escritura de bloqueo exclusivo.
Al evaluar programáticamente la respuesta de la instrucción con `cursor.rowcount`, la función detecta el resultado de la validación sin incurrir en lecturas previas sucias:
*   `rowcount == 0`: Fallo de verificación; saldo insuficiente; el usuario es insolvente en el transcurso de ejecución. Se acciona un `ROLLBACK`.
*   `rowcount > 0`: Verificación validada; el saldo es reducido. Se procede con la inclusión en el inventario y se acciona el `COMMIT`.
