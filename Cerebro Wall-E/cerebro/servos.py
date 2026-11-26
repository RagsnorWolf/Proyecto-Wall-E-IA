"""
cerebro/servos.py -- todo lo que mueve servomotores, en un solo archivo.

Cadena:  PC  --UDP-->  ESP32  --serial-->  UNO  --PWM-->  servo

Este modulo es la unica puerta de la PC hacia esa cadena. No habla con el UNO:
habla con WalleLink, que ya resuelve ACK, reintentos y timeout. Aca solo se
decide QUE angulo, en QUE canal, y con QUE suavidad.

Uso como libreria:

    from servos import Servos

    with Servos.conectar("192.168.4.1") as s:
        s.mover("sonar", 90)
        s.mover_suave("cuello", 120)
        s.guardar_pose("saludo")
        s.ir_a("saludo")

Uso desde la consola, sin tocar el resto del cerebro:

    python servos.py --host 192.168.4.1 probar
    python servos.py --host 192.168.4.1 mover sonar 45
    python servos.py --host 192.168.4.1 barrido sonar
    python servos.py --host 192.168.4.1 poses
    python servos.py --host 192.168.4.1 pose saludo
    python servos.py --host 192.168.4.1 guardar saludo --angulos "sonar=90,cuello=120"
    python servos.py --host 192.168.4.1 interactivo
    python servos.py --dry probar          # sin robot, imprime lo que haria

Para posar a mano: `interactivo`, mover con `m <canal> <grados>`, y ahi mismo
`guardar <nombre>`. El comando `guardar` suelto guarda el estado del proceso,
que arranca siempre en los centros; con --angulos mueve primero y guarda
despues, que es lo que se quiere casi siempre.

LIMITE CONOCIDO DEL PROTOCOLO
    El UNO no devuelve en que angulo esta un servo. posicion() devuelve el
    ultimo angulo que se MANDO, no una lectura real. Si alguien mueve un servo
    con la mano, este modulo no se entera.

LIMITE MECANICO
    El protocolo acepta 0..180. El servo no. Los topes de la tabla CANALES son
    los que protegen la mecanica: se miden con el robot armado, servo por servo,
    hasta que la pieza toca algo. Ajustar ahi, no en el .ino.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # consolas viejas de Windows
    pass

from walle_link import (
    DEFAULT_PORT,
    SERVO_CHANNELS,
    Ack,
    LinkError,
    WalleLink,
)

# --------------------------------------------------------------------------
# CANALES
# --------------------------------------------------------------------------

# El .ino fija los pines; aca solo se reflejan para que el cableado este a mano
# en un solo lugar. Si se cambia un pin, se cambia en walle_motors.ino y aca.
PIN_SERVO = (5, 6, 9, 10)

# Tiempo que tarda un servo en llegar y quedarse quieto. El sonar lo necesita
# antes de pedir una lectura nueva; un brazo lo necesita antes de agarrar algo.
SERVO_SETTLE_S = 0.30

# Suavizado por defecto: cuantos pasos y cuanto entre paso.
SUAVE_PASOS = 8
SUAVE_PAUSA_S = 0.04

POSES_FILE = "servos_poses.json"


@dataclass(frozen=True)
class Canal:
    """Un servo con su nombre, su pin y sus topes mecanicos."""

    nombre: str
    indice: int
    pin: int
    centro: int = 90
    minimo: int = 20
    maximo: int = 160
    invertido: bool = False

    def limitar(self, grados: float) -> int:
        """Lleva el angulo logico al rango mecanico del servo."""
        valor = int(round(grados))
        if valor < self.minimo:
            valor = self.minimo
        elif valor > self.maximo:
            valor = self.maximo
        return valor

    def fisico(self, grados: int) -> int:
        """Angulo que hay que mandar al UNO (aplica la inversion del montaje)."""
        return self.centro * 2 - grados if self.invertido else grados


# Tabla de canales. El 0 es el sonar y ya esta en uso por autonomo.py.
# Los otros tres estan cableados pero sin mecanica asignada: renombrar cuando
# se sepa que mueven (cuello, brazo, pinza) y ajustar topes.
CANALES: dict[str, Canal] = {
    "sonar": Canal("sonar", 0, PIN_SERVO[0], centro=90, minimo=35, maximo=145),
    "cuello": Canal("cuello", 1, PIN_SERVO[1], centro=90, minimo=45, maximo=135),
    "brazo_izq": Canal("brazo_izq", 2, PIN_SERVO[2], centro=90, minimo=20, maximo=160),
    "brazo_der": Canal("brazo_der", 3, PIN_SERVO[3], centro=90, minimo=20, maximo=160, invertido=True),
}

POR_INDICE: dict[int, Canal] = {c.indice: c for c in CANALES.values()}


class ServoError(RuntimeError):
    """El canal pedido no existe o el angulo no se pudo mandar."""


# --------------------------------------------------------------------------
# ENLACE NULO -- para probar sin robot
# --------------------------------------------------------------------------


class LinkNulo:
    """Misma interfaz que WalleLink, sin hardware. Guarda lo que se habria mandado."""

    def __init__(self, logger=None) -> None:
        self._log = logger or (lambda _msg: None)
        self.history: list[tuple[float, int, int]] = []
        self.closed = False

    def servo(self, channel: int, degrees: int) -> Ack:
        self.history.append((time.monotonic(), int(channel), int(degrees)))
        self._log(f"[dry] servo {channel} -> {degrees} grados")
        return Ack(0, int(channel), int(degrees), 0)

    def stop(self) -> Ack:
        self._log("[dry] motores detenidos")
        return Ack(0, 0, 0, 0)

    def close(self) -> None:
        self.closed = True
        self._log("[dry] cerrado")


# --------------------------------------------------------------------------
# SERVOS
# --------------------------------------------------------------------------


class Servos:
    """Mueve servos por nombre, con topes mecanicos, suavizado y poses."""

    def __init__(
        self,
        link,
        *,
        poses_path: Optional[Path] = None,
        logger=None,
    ) -> None:
        self._link = link
        self._log = logger or (lambda _msg: None)
        self._poses_path = Path(poses_path) if poses_path else (
            Path(__file__).resolve().parent / POSES_FILE
        )
        self._pos: dict[str, int] = {c.nombre: c.centro for c in CANALES.values()}
        self.errores = 0

    # -- construccion ------------------------------------------------------

    @classmethod
    def conectar(
        cls,
        host: Optional[str] = None,
        port: int = DEFAULT_PORT,
        *,
        dry_run: bool = False,
        poses_path: Optional[Path] = None,
        logger=None,
    ) -> "Servos":
        """Abre el enlace real, o el nulo si no hay host o dry_run."""
        if dry_run or not host:
            return cls(LinkNulo(logger=logger), poses_path=poses_path, logger=logger)
        return cls(
            WalleLink(host, port, logger=logger).open(),
            poses_path=poses_path,
            logger=logger,
        )

    def cerrar(self) -> None:
        try:
            self._link.close()
        except Exception as exc:  # nunca tapar el cierre por un error de red
            self._log(f"cierre con error: {exc}")

    def __enter__(self) -> "Servos":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cerrar()

    # -- canales -----------------------------------------------------------

    @staticmethod
    def canal(ref) -> Canal:
        """Acepta 'sonar', 0, o '0'."""
        if isinstance(ref, Canal):
            return ref
        if isinstance(ref, int):
            if ref not in POR_INDICE:
                raise ServoError(f"no hay servo en el canal {ref} (0..{SERVO_CHANNELS - 1})")
            return POR_INDICE[ref]
        texto = str(ref).strip().lower()
        if texto in CANALES:
            return CANALES[texto]
        if texto.isdigit():
            return Servos.canal(int(texto))
        raise ServoError(f"canal desconocido: {ref!r}. Hay: {', '.join(CANALES)}")

    # -- movimiento --------------------------------------------------------

    def mover(self, ref, grados: float) -> Ack:
        """Mueve un servo y espera el ACK. Clampea a los topes mecanicos.

        El angulo que se recuerda es el logico (el que pediste), no el fisico
        que sale por el cable: si el canal esta invertido, aca no se nota.
        """
        canal = self.canal(ref)
        destino = canal.limitar(grados)
        if int(round(grados)) != destino:
            self._log(
                f"{canal.nombre}: {grados:.0f} fuera de "
                f"[{canal.minimo}, {canal.maximo}] -> {destino}"
            )
        try:
            ack = self._link.servo(canal.indice, canal.fisico(destino))
        except LinkError as exc:
            self.errores += 1
            raise ServoError(f"{canal.nombre}: la orden no se confirmo ({exc})") from exc
        self._pos[canal.nombre] = destino
        return ack

    def mover_suave(
        self,
        ref,
        grados: float,
        *,
        pasos: int = SUAVE_PASOS,
        pausa: float = SUAVE_PAUSA_S,
    ) -> int:
        """Rampa hasta el destino. Devuelve el angulo final.

        Cada paso es un ida y vuelta por UDP con ACK, asi que la rampa esta
        limitada por el enlace: con pausa 0.04 s y 8 pasos son ~0.3 s minimo.
        """
        canal = self.canal(ref)
        destino = canal.limitar(grados)
        origen = self._pos[canal.nombre]
        pasos = max(1, int(pasos))
        if destino == origen:
            return destino

        for i in range(1, pasos + 1):
            intermedio = origen + (destino - origen) * i / pasos
            self.mover(canal, intermedio)
            if i < pasos and pausa > 0:
                time.sleep(pausa)
        return destino

    def centrar(self, ref=None) -> dict[str, int]:
        """Manda al centro uno o todos los canales."""
        canales = [self.canal(ref)] if ref is not None else list(CANALES.values())
        for canal in canales:
            self.mover(canal, canal.centro)
        return {c.nombre: self._pos[c.nombre] for c in canales}

    def barrido(
        self,
        ref,
        desde: Optional[float] = None,
        hasta: Optional[float] = None,
        *,
        paso: float = 10.0,
        pausa: float = SERVO_SETTLE_S,
        ida_y_vuelta: bool = True,
    ) -> list[int]:
        """Barrido continuo entre dos angulos. Devuelve los angulos visitados.

        Pensado para el sonar: cada paso espera `pausa` antes de devolver el
        control, que es el tiempo que el servo tarda en asentarse.
        """
        canal = self.canal(ref)
        desde = canal.minimo if desde is None else canal.limitar(desde)
        hasta = canal.maximo if hasta is None else canal.limitar(hasta)
        paso = abs(float(paso)) or 10.0

        ida = _rampa(desde, hasta, paso)
        camino = ida + list(reversed(ida[:-1])) if ida_y_vuelta else ida

        visitados: list[int] = []
        for i, angulo in enumerate(camino):
            self.mover(canal, angulo)
            visitados.append(self._pos[canal.nombre])
            if i < len(camino) - 1 and pausa > 0:
                time.sleep(pausa)
        return visitados

    def asentar(self, segundos: float = SERVO_SETTLE_S) -> None:
        """Espera a que el servo termine de llegar. Para sensores montados encima."""
        if segundos > 0:
            time.sleep(segundos)

    # -- estado ------------------------------------------------------------

    def posicion(self, ref) -> int:
        """Ultimo angulo MANDADO, no una lectura real (el UNO no informa)."""
        return self._pos[self.canal(ref).nombre]

    def estado(self) -> dict:
        """Foto completa: canales, topes, ultimo angulo mandado y errores."""
        return {
            "errores": self.errores,
            "canales": {
                c.nombre: {
                    "indice": c.indice,
                    "pin": c.pin,
                    "minimo": c.minimo,
                    "maximo": c.maximo,
                    "centro": c.centro,
                    "invertido": c.invertido,
                    "angulo": self._pos[c.nombre],
                }
                for c in CANALES.values()
            },
        }

    # -- poses -------------------------------------------------------------

    @property
    def poses_path(self) -> Path:
        return self._poses_path

    def poses(self) -> dict[str, dict[str, int]]:
        return _leer_json(self._poses_path)

    def guardar_pose(self, nombre: str) -> dict[str, int]:
        """Guarda los ultimos angulos mandados como pose con nombre."""
        nombre = _nombre_pose(nombre)
        poses = self.poses()
        poses[nombre] = dict(self._pos)
        _escribir_json(self._poses_path, poses)
        return poses[nombre]

    def borrar_pose(self, nombre: str) -> bool:
        poses = self.poses()
        if poses.pop(nombre, None) is None:
            return False
        _escribir_json(self._poses_path, poses)
        return True

    def ir_a(self, nombre: str, *, suave: bool = True, pausa: float = 0.08) -> dict[str, int]:
        """Lleva todos los canales a la pose guardada."""
        poses = self.poses()
        if nombre not in poses:
            disponibles = ", ".join(sorted(poses)) or "ninguna"
            raise ServoError(f"pose desconocida: {nombre!r}. Hay: {disponibles}")

        for canal_nombre, grados in poses[nombre].items():
            if canal_nombre not in CANALES:
                self._log(f"pose {nombre}: canal {canal_nombre} ya no existe, se salta")
                continue
            if suave:
                self.mover_suave(canal_nombre, grados)
            else:
                self.mover(canal_nombre, grados)
            if pausa > 0:
                time.sleep(pausa)
        return {c: self._pos[c] for c in poses[nombre] if c in CANALES}

    # -- utilidades --------------------------------------------------------

    def parar_motores(self) -> None:
        """Frena las orugas. Los servos quedan donde estan."""
        try:
            self._link.stop()
        except LinkError as exc:
            self.errores += 1
            self._log(f"parada de motores no confirmada: {exc}")

    def probar(self, *, amplitud: int = 20, pausa: float = SERVO_SETTLE_S) -> None:
        """Menea cada canal alrededor de su centro. Sirve para descubrir cableado.

        OJO: mueve los cuatro canales. Despejar la mecanica antes de correrlo.
        """
        for canal in CANALES.values():
            self._log(f"probando {canal.nombre} (canal {canal.indice}, pin {canal.pin})")
            self.mover(canal, canal.centro)
            self.asentar(pausa)
            self.mover(canal, canal.centro + amplitud)
            self.asentar(pausa)
            self.mover(canal, canal.centro - amplitud)
            self.asentar(pausa)
            self.mover(canal, canal.centro)
        self.asentar(pausa)


# --------------------------------------------------------------------------
# INTERNO
# --------------------------------------------------------------------------


def _rampa(desde: int, hasta: int, paso: float) -> list[int]:
    """Angulos de desde a hasta, ambos incluidos."""
    if desde == hasta:
        return [desde]
    signo = 1 if hasta > desde else -1
    actual = desde
    salida = [desde]
    while (hasta - actual) * signo > paso:
        actual += int(round(paso)) * signo
        salida.append(actual)
    if salida[-1] != hasta:
        salida.append(hasta)
    return salida


def _nombre_pose(nombre: str) -> str:
    limpio = str(nombre).strip()
    if not limpio:
        raise ServoError("la pose necesita un nombre")
    return limpio


def _leer_json(ruta: Path) -> dict:
    if not ruta.exists():
        return {}
    try:
        with ruta.open("r", encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ServoError(f"no se pudo leer {ruta.name}: {exc}") from exc
    return datos if isinstance(datos, dict) else {}


def _escribir_json(ruta: Path, datos: dict) -> None:
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    try:
        with temporal.open("w", encoding="utf-8") as fh:
            json.dump(datos, fh, indent=2, ensure_ascii=False, sort_keys=True)
            fh.write("\n")
        temporal.replace(ruta)
    except OSError as exc:
        raise ServoError(f"no se pudo escribir {ruta.name}: {exc}") from exc


# --------------------------------------------------------------------------
# CONSOLA
# --------------------------------------------------------------------------


def _imprimir_estado(servos: Servos) -> None:
    estado = servos.estado()
    print(f"{'canal':<10} {'idx':>3} {'pin':>4} {'min':>4} {'max':>4} {'ang':>4}")
    for nombre, datos in estado["canales"].items():
        print(
            f"{nombre:<10} {datos['indice']:>3} {datos['pin']:>4} "
            f"{datos['minimo']:>4} {datos['maximo']:>4} {datos['angulo']:>4}"
        )
    if estado["errores"]:
        print(f"errores de enlace: {estado['errores']}")


def _repl(servos: Servos) -> None:
    print("comandos: m <canal> <grados> | s <canal> <grados> | c [canal] |")
    print("          b <canal> | p | pose <nombre> | guardar <nombre> | q")
    while True:
        try:
            linea = input("servo> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not linea:
            continue
        partes = linea.split()
        orden = partes[0].lower()
        args = partes[1:]
        try:
            if orden in ("q", "quit", "salir"):
                return
            elif orden in ("m", "mover") and len(args) == 2:
                ack = servos.mover(args[0], float(args[1]))
                print(f"  {args[0]} -> {servos.posicion(args[0])} grados ({ack.rtt_ms} ms)")
            elif orden in ("s", "suave") and len(args) == 2:
                final = servos.mover_suave(args[0], float(args[1]))
                print(f"  {args[0]} -> {final} grados")
            elif orden in ("c", "centrar"):
                hechos = servos.centrar(args[0] if args else None)
                print("  " + ", ".join(f"{k}={v}" for k, v in hechos.items()))
            elif orden in ("b", "barrido") and len(args) == 1:
                visitados = servos.barrido(args[0])
                print(f"  {len(visitados)} posiciones: {visitados[0]}..{visitados[-1]}")
            elif orden in ("p", "estado"):
                _imprimir_estado(servos)
            elif orden == "pose" and len(args) == 1:
                hechos = servos.ir_a(args[0])
                print("  " + ", ".join(f"{k}={v}" for k, v in hechos.items()))
            elif orden == "guardar" and len(args) == 1:
                guardada = servos.guardar_pose(args[0])
                print(f"  pose {args[0]}: " + ", ".join(f"{k}={v}" for k, v in guardada.items()))
            else:
                print("  no entendi. m <canal> <grados>, c, p, q")
        except (ServoError, ValueError) as exc:
            print(f"  {exc}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mueve los servomotores de WALL-E por el ESP32.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "ejemplos:\n"
            "  python servos.py --host 192.168.4.1 probar\n"
            "  python servos.py --host 192.168.4.1 mover sonar 45\n"
            "  python servos.py --host 192.168.4.1 barrido sonar\n"
            "  python servos.py --dry interactivo\n"
        ),
    )
    parser.add_argument("--host", help="IP del ESP32 puente")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--dry", action="store_true", help="sin robot: imprime lo que haria")
    parser.add_argument("--poses", help=f"ruta del JSON de poses (default: {POSES_FILE})")

    sub = parser.add_subparsers(dest="orden", required=True)

    sub.add_parser("estado", help="tabla de canales y ultimo angulo mandado")

    p_mover = sub.add_parser("mover", help="mueve un servo")
    p_mover.add_argument("canal")
    p_mover.add_argument("grados", type=float)
    p_mover.add_argument("--suave", action="store_true", help="rampa en vez de salto")
    p_mover.add_argument("--pasos", type=int, default=SUAVE_PASOS)

    p_centrar = sub.add_parser("centrar", help="centra uno o todos")
    p_centrar.add_argument("canal", nargs="?")

    p_barrido = sub.add_parser("barrido", help="recorre el rango del canal")
    p_barrido.add_argument("canal")
    p_barrido.add_argument("--desde", type=float)
    p_barrido.add_argument("--hasta", type=float)
    p_barrido.add_argument("--paso", type=float, default=10.0)
    p_barrido.add_argument("--pausa", type=float, default=SERVO_SETTLE_S)
    p_barrido.add_argument("--una-ida", action="store_true")

    p_probar = sub.add_parser("probar", help="menea los cuatro canales")
    p_probar.add_argument("--amplitud", type=int, default=20)

    sub.add_parser("poses", help="lista las poses guardadas")

    p_pose = sub.add_parser("pose", help="lleva el robot a una pose")
    p_pose.add_argument("nombre")
    p_pose.add_argument("--duro", action="store_true", help="sin rampa")

    p_guardar = sub.add_parser("guardar", help="guarda los angulos actuales como pose")
    p_guardar.add_argument("nombre")
    p_guardar.add_argument(
        "--angulos",
        help="lista canal=grados separada por comas; mueve y despues guarda "
        "(ej: 'sonar=90,cuello=120,brazo_izq=45')",
    )

    p_borrar = sub.add_parser("borrar", help="borra una pose")
    p_borrar.add_argument("nombre")

    sub.add_parser("interactivo", help="REPL para mover a mano")

    args = parser.parse_args(argv)

    if not args.host and not args.dry:
        parser.error("falta --host (o --dry para probar sin robot)")

    poses_path = Path(args.poses) if args.poses else None
    servos = Servos.conectar(
        args.host,
        args.port,
        dry_run=args.dry,
        poses_path=poses_path,
        logger=print if args.dry else None,
    )

    try:
        if args.orden == "estado":
            _imprimir_estado(servos)
        elif args.orden == "mover":
            if args.suave:
                final = servos.mover_suave(args.canal, args.grados, pasos=args.pasos)
                print(f"{args.canal} -> {final} grados")
            else:
                ack = servos.mover(args.canal, args.grados)
                print(f"{args.canal} -> {servos.posicion(args.canal)} grados ({ack.rtt_ms} ms)")
        elif args.orden == "centrar":
            hechos = servos.centrar(args.canal)
            print(", ".join(f"{k}={v}" for k, v in hechos.items()))
        elif args.orden == "barrido":
            visitados = servos.barrido(
                args.canal,
                args.desde,
                args.hasta,
                paso=args.paso,
                pausa=args.pausa,
                ida_y_vuelta=not args.una_ida,
            )
            print(f"{len(visitados)} posiciones: {' '.join(str(v) for v in visitados)}")
        elif args.orden == "probar":
            servos.probar(amplitud=args.amplitud)
            print("listo")
        elif args.orden == "poses":
            guardadas = servos.poses()
            if not guardadas:
                print(f"no hay poses en {servos.poses_path.name}")
            for nombre in sorted(guardadas):
                valores = ", ".join(f"{k}={v}" for k, v in sorted(guardadas[nombre].items()))
                print(f"{nombre}: {valores}")
        elif args.orden == "pose":
            hechos = servos.ir_a(args.nombre, suave=not args.duro)
            print(", ".join(f"{k}={v}" for k, v in hechos.items()))
        elif args.orden == "guardar":
            if args.angulos:
                for par in args.angulos.split(","):
                    canal, _, valor = par.partition("=")
                    if not valor.strip():
                        raise ServoError(f"angulo mal escrito: {par!r} (usar canal=grados)")
                    servos.mover(canal.strip(), float(valor))
            guardada = servos.guardar_pose(args.nombre)
            print(f"pose {args.nombre}: " + ", ".join(f"{k}={v}" for k, v in guardada.items()))
        elif args.orden == "borrar":
            print("borrada" if servos.borrar_pose(args.nombre) else "no existia")
        elif args.orden == "interactivo":
            _repl(servos)
    except ServoError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        servos.cerrar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
