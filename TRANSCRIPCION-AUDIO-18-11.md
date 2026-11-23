# Transcripción del audio del 18/11

Fuente: `WhatsApp Ptt 2026-11-18 at 23.11.43.ogg`
Duración: 119.5 s · Idioma: español (confianza 1.00)
Transcrito con `faster_whisper` (modelo `small`, int8, CPU).

Es el asesor explicando la arquitectura del robot: dónde vive el cerebro, qué
hace cada microcontrolador y por qué hace falta una confirmación de vuelta.
Se guarda como referencia para que quien abra el proyecto entienda de dónde
sale la división PC / ESP32 / UNO.

---

## Transcripción literal

> Whisper escribe mal varios términos técnicos. La lectura corregida está
> abajo; esta versión se deja tal cual salió, sin retocar, para que se pueda
> comparar.

```
[00:00] Hola, Gonz, ¿cómo estás? Acá el AU, me había comentado que ustedes iban a utilizar un Arduino 1 y un SCP-32 agorote
[00:07] que por cada microcontralador, vos tendrías que poner un código nomás entre cada uno.
[00:11] Fíjate si con el mismo lenguaje que vos tenés, puedes hacer una acción indelámbrica, depende de la ancho de banda,
[00:18] pero yo creo que vas a poder mandar la información entre una computadora y el Wally, así él genera acciones.
[00:26] Es decir, que no vas a cargar el modelo de IAN y los archivos dentro del SEP o el Arduino
[00:30] 1, ya que correte que el Arduino 1 maneja una cierta cantidad de bits y el SEP 22 no puede
[00:35] almacenar tanto, no tiene almacenamiento de interno grande, entonces lo que puedes hacer
[00:41] es agarrar, hacer una comunicación que se conecte inelámbricamente con el SEP que
[00:47] va a hacer el cerebro y que mande órdenes que se llaman funciones llamadas dentro
[00:54] decir más más a la aplicación web o lo que hayas creado como cerebro interno de la computadora.
[00:58] O sea que el cerebro interno, el cerebro original sea la computadora y el SP eso lo recibe y da órdenes
[01:05] al Arduino 1 con los motores o él también recibe órdenes o sea y hace lo que tienen que hacer.
[01:10] No vi bien el diagrama pero seguro va a ser, calculo que el Arduino 1 con los motores y los
[01:15] servos y el SP capaz que maneje, no sé, no sé si ya tiene camanas pero bueno, que el cerebro
[01:23] a hacer al final la computadora y que tenga una combinación lineal con el... Bueno, va a
[01:29] hacer lineal porque ahorita hay que para que se confirme, el cerebro tiene que mandárselo
[01:35] al SCP y el SCP tiene que poner una respuesta, así sabemos que realmente funciona, porque
[01:40] si no, te vas a atacar todo el tiempo. Así que si haces eso es mucho más fácil y rápido,
[01:45] ya que solamente va a tener un código ese, con todas las funciones va a tener el cerebro
[01:50] del modelo o guía o lo que hayas hecho y el Arduino solamente recibe las órdenes mandadas
[01:57] por el DCF.
```

## Lectura corregida

```
[00:00] Hola Gonz, ¿cómo estás? Acá el asesor. Me había comentado que ustedes
        iban a utilizar un Arduino UNO y un ESP32. Ahora, entre cada
[00:07] microcontrolador vos tenés que poner un código entre cada uno.
[00:11] Fíjate si con el mismo lenguaje que vos tenés podés hacer una acción
        inalámbrica; depende del ancho de banda,
[00:18] pero yo creo que vas a poder mandar la información entre una computadora
        y el WALL-E, así él genera acciones.
[00:26] Es decir, no vas a cargar el modelo de IA y los archivos dentro del ESP
        o el Arduino
[00:30] UNO, ya que el Arduino UNO maneja una cierta cantidad de bits y el ESP32
        no puede
[00:35] almacenar tanto, no tiene almacenamiento interno grande. Entonces lo que
        puedes hacer
[00:41] es hacer una comunicación que se conecte inalámbricamente con el ESP,
        que
[00:47] va a hacer de cerebro, y que mande órdenes —lo que se llaman funciones—
        llamadas dentro de
[00:54] la aplicación web o lo que hayas creado como cerebro interno de la
        computadora.
[00:58] O sea, el cerebro interno, el cerebro original, es la computadora; el ESP
        recibe y da órdenes
[01:05] al Arduino UNO con los motores. O él también recibe órdenes y hace lo que
        tenga que hacer.
[01:10] No vi bien el diagrama, pero seguro va a ser: el Arduino UNO con los
        motores y los
[01:15] servos, y el ESP capaz que maneje... no sé, no sé si ya tiene cámaras.
        Pero bueno, el cerebro
[01:23] al final lo hace la computadora, y que tenga una comunicación lineal.
        Va a
[01:29] ser lineal porque, para que se confirme, el cerebro tiene que mandárselo
[01:35] al ESP y el ESP tiene que devolver una respuesta; así sabemos que
        realmente funciona, porque
[01:40] si no, te vas a atascar todo el tiempo. Así que si haces eso es mucho más
        fácil y rápido,
[01:45] ya que el ESP va a tener un solo código con todas las funciones y va a
        tener el cerebro
[01:50] del modelo, o la guía, o lo que hayas hecho; y el Arduino solamente recibe
        las órdenes mandadas
[01:57] por el ESP.
```

---

## Contraste con lo que está construido

| El asesor pide | Dónde está |
|---|---|
| El cerebro es la computadora | `Cerebro Wall-E\cerebro\` corre en la PC |
| Comunicación inalámbrica con el ESP | UDP 4210, `WALLE/1 <id> <op> <a> <b>` |
| El ESP recibe y manda órdenes al UNO | serie 57600 8N1, `<id>,<op>,<a>,<b>` |
| El UNO solo mueve motores y servos | `arduino_uno\` no decide nada |
| No cargar el modelo en el micro | `models\` vive en la PC; el micro recibe texto |
| El ESP tiene que devolver una respuesta | ACK real: PC espera 400 ms, ESP32 espera al UNO 120 ms |
| Confirmar que funciona antes de seguir | `WALLE/1 <id> OK <v1> <v2> <rtt_ms>` / `ER <codigo>` |

El único punto que el audio deja abierto es si el ESP32 lleva cámaras. Lo dice
como duda («no sé si ya tiene cámaras»), no como requisito.
