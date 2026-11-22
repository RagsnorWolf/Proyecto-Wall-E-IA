"""
WALL-E · Fase 5 — Explorador Autónomo V5 (LiDAR a ras de suelo, obs 58D)

Entorno Gymnasium + PyBullet de nivel industrial para exploración autónoma.

Características V5:
- LiDAR 2D virtual: anillo de 72 rayos (cada 5°, 360°) para el entorno, más
  un abanico de 36 rayos para la política. Los dos en una sola llamada a
  rayTestBatch.
- El plano de escaneo va a 6 cm del SUELO local, no a una altura fija sobre
  el chasis. Antes quedaba a 0.21 m y un obstáculo de 12 cm era invisible.
- Las distancias se miden desde el PARAGOLPES: se descuenta el radio del
  chasis en la dirección del rayo. 0 significa "tocando".
- El abanico de 36 rayos es denso al frente (24 rayos en ±40°, uno cada 3,5°)
  y más abierto a los costados (6 por lado hasta ±90°). Un reparto uniforme
  gastaba 5° por rayo y dejaba el cono de decisión con muy poca resolución.
- Observación de 66 dimensiones:
    [x, y, qx, qy, qz, qw, vx, vy, vz, wx, wy, wz,
     goal, goal_bearing,
     s0..s35,            <- 36 rayos del abanico, normalizados [0,1]
     claridad_frontal,   <- 1 - min(cono ±35°)/alcance
     distancia_minima,   <- 1 - min(anillo 72)/alcance
     obst_sin, obst_cos, <- rumbo del obstáculo más cercano
     libre_sin, libre_cos, <- dirección del hueco más ancho (escape)
     contacto, atascado, <- banderas de resolución de problemas
     libre_izq, libre_der, <- despeje lateral derecho e izquierdo
     hueco_ancho,        <- ancho del hueco más ancho, en radianes/pi
     hueco_dist,         <- despeje en el centro de ese hueco
     goal_clear,         <- despeje en el rumbo al objetivo (±20°)
     trasero,            <- despeje detrás del robot
     vel_adelante,       <- velocidad real sobre el eje del chasis
     ratio_libre]        <- fracción del abanico despejada
- Obstáculos complejos: cajas de alturas variadas, cilindros (postes),
  rampas inclinadas y paredes en forma de "L" (callejones sin salida).
- Fricción variable: zona de césped (mu=2.0) y zona de baldosa (mu=0.5).
- ChunkMapper 1x1 m: 0=desconocido, 1=libre, 2=obstáculo.
- Chocar NO termina el episodio: se castiga el contacto y se premia salir.

Sistema de recompensas múltiple:
    +10 por descubrir un chunk nuevo.
    -5  por evento de colisión.
    -0.25 por paso en contacto con algo sólido.
    +3  por soltarse del obstáculo retrocediendo.
    +2  por ganar distancia libre cuando estaba pegado (<0.40 m).
    -0.30 por acercarse todavía más a algo que ya tenía encima.
    -5  por quedarse quieto más de 1 segundo.
    +2  por cada segundo de movimiento continuo.
    -15 por quedar atrapado (3+ obstáculos a menos de 30 cm).
"""

from __future__ import annotations

import math
from typing import Any, List, Tuple

import gymnasium as gym
import numpy as np
import pybullet as p

from chunk_mapper import ChunkMapper

# Importamos todo lo necesario desde V2 para reutilizar su infraestructura.
# No tocamos walle_env_v2.py: creamos un entorno independiente basado en él.
from walle_env_v2 import WallEEnvV2, wrap_angle  # noqa: F401


# --------------------------------------------------------------------- #
# Constantes V4
# --------------------------------------------------------------------- #
LIDAR_RAYS = 72                 # anillo completo 360°, cada 5° (para el entorno)
SENSOR_COUNT = 36               # rayos que entran en la observación
LIDAR_MAX_DIST = 6.0            # alcance máximo en metros

# --- Geometría del barrido --------------------------------------------- #
# El plano de escaneo va a la altura del PARAGOLPES, medido desde el suelo
# local del robot.
#
# Antes era SENSOR_HEIGHT=0.06 sumado a pos[2], y como la base está en 0.15 el
# plano quedaba a 0.21 m del piso: un objeto de 12 cm de alto era invisible
# para el LiDAR aunque el robot chocara contra él. Medido en esta máquina:
#   plano a 0.21 m -> caja de 12 cm a 0.75 m: lectura 6.000 m (no la ve)
#   plano a 0.06 m -> la misma caja: lectura correcta
SENSOR_FOOT_Z = 0.06
# Segundo plano de escaneo: por encima de esto hay techo. 34 cm es la
# altura del chasis, asi que un obstaculo que llega hasta aca bloquea
# de verdad y uno mas bajo se puede trepar.
HEADROOM_FOOT_Z = 0.34
# Semiejes del chasis (walle_env_v2: chassis_half = [0.175, 0.15, 0.14]).
# El LiDAR mide desde el CENTRO del robot, pero el choque ocurre en el borde.
# Restar este radio hace que 0 signifique "tocando", que es lo que asumen
# todos los umbrales de recompensa (NEAR_OBSTACLE_M, STOP, etc.).
BODY_HALF_X = 0.175
BODY_HALF_Y = 0.150
# Los rayos nacen en el centro del robot y se excluye el propio cuerpo con
# parentObjectUniqueId. Antes nacían a 30 cm: al tocar una pared el origen
# quedaba DENTRO del obstáculo y el sensor se quedaba ciego justo al chocar.
LIDAR_ORIGIN_OFFSET = 0.0

# --- Reparto del abanico de 36 rayos ----------------------------------- #
# Un abanico uniforme de ±90° gasta 5° por rayo y deja solo 13 rayos en el
# cono donde el robot decide. Se concentra la resolución al frente:
#   24 rayos de -40° a +40°  (3,5° de separación)  <- donde se decide
#   6 + 6 rayos de ±48° a ±90° (8,4°)              <- cobertura lateral
FAN_INNER_DEG = 40.0
FAN_INNER_RAYS = 24
FAN_OUTER_START_DEG = 48.0
FAN_OUTER_END_DEG = 90.0
FAN_OUTER_RAYS = 6
# Cono que cuenta como "tengo algo delante" para premios y castigos.
FRONT_CONE_DEG = 35.0

# Hilos del barrido de rayos.
#
# Medido en esta build (Nov 2026), 72 rayos, en régimen estable:
#   nt=0 -> 0.13 ms, nt=1 -> 0.002 ms, nt=4 -> 0.11 ms
#
# nt=0 NO significa "sin pool": pybullet toma el tamaño del pool del procesador
# de comandos, lo levanta en el primer barrido y en esta build se queda colgado
# ahí. Un barrido aislado con nt=0 no vuelve nunca; con nt=1 vuelve en 2 ms.
# Ese cuelgue fue el que parecía un access violation del entrenamiento.
#
# nt=1 es el único valor estable: no crea hilos propios, así que tampoco puede
# chocar con los de PyTorch ni provocar el access violation que aparecía dentro
# de SubprocVecEnv (que ya no se usa: un proceso por entorno se cuelga al
# levantar el segundo hijo en esta build).
LIDAR_THREADS = 1

# Recompensas V4 (sistema múltiple)
CHUNK_DISCOVERY_REWARD = 10.0   # por cada celda nueva descubierta
COLLISION_PENALTY = -5.0        # por evento de colisión
IDLE_PENALTY = -5.0             # por quedarse quieto más de 1 segundo
MOVE_STREAK_BONUS = 2.0         # por cada segundo de movimiento continuo
TRAP_PENALTY = -15.0            # atrapado: 3+ obstáculos a menos de 30 cm
EXPLORATION_BONUS = 0.3         # shaping adicional por explorar
OBSTACLE_AVOID_BONUS = 0.1      # shaping por mantener distancia

# --- Presupuesto de recompensa ----------------------------------------- #
# Todo lo que sigue está calibrado contra el avance, que rinde ~+4/s a tope
# (0.0036 m por paso × 20 × 60 pasos/s). Antes el castigo por proximidad era
# un escalón de -1.0 POR PASO = -60/s: catorce veces el premio por avanzar.
# Con esa relación la política aprende exactamente una cosa: quedarse quieta
# lejos de todo, que es el "frena en seco en mitad de la nada" reportado.
# Ahora la proximidad es gradual y siempre menor que tocar:
#   avanzar libre        +4/s
#   acercarse a 0.8 m     0
#   acercarse a 0.1 m    -7/s
#   tocando             -15/s
CLOSE_OBSTACLE_M = 0.80         # desde acá empieza a descontar
CLOSE_OBSTACLE_PENALTY = -0.12  # por paso PEGADO (se escala por cercanía)

# Umbrales de detección
TRAP_RADIUS = 0.30              # metros
TRAP_MIN_OBSTACLES = 3          # obstáculos cercanos para considerar trampa
TRAP_COOLDOWN_STEPS = 120       # 2 s de enfriamiento tras castigar
IDLE_STEPS_THRESHOLD = 60       # 1 s a 60 Hz
MOVE_STREAK_THRESHOLD = 60      # 1 s de movimiento continuo
MOVE_EPS_M = 0.002              # desplazamiento mínimo por paso para "moverse"

# --- Resolución de problemas (prioridad del cerebro) -------------------- #
# Chocar ya NO termina el episodio: el robot tiene que aprender a salir.
CONTACT_PENALTY = -0.25         # por paso en contacto con algo sólido
ESCAPE_BONUS = 3.0              # por soltarse de un obstáculo retrocediendo
CLEARANCE_REWARD = 2.0          # por ganar distancia libre cuando estaba pegado
APPROACH_PENALTY = -0.05        # por acercarse a <0.40 m teniendo el frente libre
NEAR_OBSTACLE_M = 0.40          # "pegado": por debajo de esto hay que maniobrar
FREE_RAY_M = 1.20               # rayo que cuenta como espacio libre transitable
STUCK_SPEED = 0.03              # m/s por debajo de esto el robot está atascado
STUCK_STEPS = 45                # 0.75 s sin moverse = bandera de atascado

# --- Sentidos laterales y de rumbo (V6) -------------------------------- #
# Los 36 rayos del abanico son simétricos alrededor del frente, pero la
# política no tenía una lectura compacta de "por dónde me puedo escapar".
# Estos umbrales definen los tres sectores que sí importan:
SIDE_MIN_DEG = 35.0             # desde acá hacia el costado = sector lateral
GOAL_CONE_DEG = 20.0            # cono alrededor del rumbo al objetivo
REAR_DEG = 140.0                # a partir de acá = detrás del robot

# Umbral de contacto real. PyBullet mantiene en getContactPoints los pares de
# broadphase con normalForce=0 y sin penetración: contarlos como choque hacía
# que WALL-E se declarara bloqueado en mitad de la nada.
COLLISION_MIN_FORCE = 0.02      # N de fuerza normal mínima para contar
COLLISION_MIN_PENETRATION_M = 0.001  # 1 mm de penetración mínima

# Observación extendida: 14 base + 36 LiDAR + 16 de resolución de problemas.
# Los primeros 8 extras son los del V5; los 8 nuevos van al final para no
# mover ninguna columna existente.
OBS_EXTRAS = 24
OBS_DIM = 14 + SENSOR_COUNT + OBS_EXTRAS

if SENSOR_COUNT != FAN_INNER_RAYS + 2 * FAN_OUTER_RAYS:  # falla ruidoso
    raise RuntimeError(
        f"el abanico no cierra: {FAN_INNER_RAYS} + 2x{FAN_OUTER_RAYS} "
        f"!= SENSOR_COUNT={SENSOR_COUNT}"
    )


def build_fan_angles() -> np.ndarray:
    """Ángulos del abanico de la observación, en radianes, de -90° a +90°.

    Denso al frente (donde el robot decide) y más abierto a los costados
    (donde solo necesita saber si hay algo pegado).
    """
    inner = np.linspace(-FAN_INNER_DEG, FAN_INNER_DEG, FAN_INNER_RAYS)
    outer = np.linspace(
        FAN_OUTER_START_DEG, FAN_OUTER_END_DEG, FAN_OUTER_RAYS
    )
    degrees = np.concatenate([inner, outer, -outer])
    return np.sort(np.radians(degrees)).astype(np.float32)


class WallEEnvV3(WallEEnvV2):
    """Entorno V4: LiDAR 72 + obstáculos complejos + recompensas múltiples."""

    # ------------------------------------------------------------------ #
    # Constructor
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        render_mode: str | None = None,
        stage: int = 3,
        max_episode_steps: int | None = None,
        max_wheel_speed: float = 2.5,
        max_force: float = 0.5,
        arena_half_size: float = 12.0,
        visual_mesh_path: str | None = None,
        show_proxy_visuals: bool = True,
        randomize_mass: bool = True,
        total_mass_range: tuple[float, float] = (3.0, 6.0),
        wheel_mass: float = 0.45,
        wheel_friction_range: tuple[float, float] = (1.6, 2.1),
        obstacle_count: int = 6,
        stage3_min_obstacle_distance: float = 2.5,
        obstacle_max_distance: float = 10.0,
        obstacle_min_separation: float = 1.5,
        tilt_limit_deg: float = 15.0,
        tilt_grace_steps: int = 3,
        tilt_penalty: float = 1.0,
        flip_penalty: float = 10.0,
        crash_penalty: float = 10.0,
        time_penalty: float = 0.01,
        forward_reward_scale: float = 20.0,
        # V4-specific
        enable_sensors: bool = True,
        sensor_noise_std: float = 0.0,
        connect_options: str | None = None,
        # Resolución de problemas: chocar no termina el episodio.
        collision_terminates: bool = False,
        # Destino opcional de las velocidades de oruga (robot real).
        wheel_sink: Any = None,
    ) -> None:
        # ── Inicializar atributos V4 ANTES de super().__init__ (que llama a reset) ──
        self._enable_sensors = enable_sensors
        self._sensor_noise_std = sensor_noise_std
        self._collision_terminates = bool(collision_terminates)

        # LiDAR: anillo de 72 para el entorno + abanico de 36 para la política.
        self.lidar_rays = LIDAR_RAYS
        self.lidar_max_dist = LIDAR_MAX_DIST
        self.lidar_meters = np.full(
            LIDAR_RAYS, LIDAR_MAX_DIST, dtype=np.float32
        )
        self.lidar_norm = np.ones(LIDAR_RAYS, dtype=np.float32)

        # Abanico de la observación: denso al frente, abierto a los costados.
        self.fan_angles = build_fan_angles()
        self.fan_meters = np.full(SENSOR_COUNT, LIDAR_MAX_DIST, dtype=np.float32)
        # Segundo plano de escaneo, a la altura del techo del chasis.
        # Con el plano bajo solo se sabe que hay algo; comparando los dos
        # se sabe si ese algo es una pared (bloquea) o una caja baja.
        self.headroom_meters = np.full(
            SENSOR_COUNT, LIDAR_MAX_DIST, dtype=np.float32
        )
        self.headroom_norm = np.ones(SENSOR_COUNT, dtype=np.float32)
        self.fan_norm = np.ones(SENSOR_COUNT, dtype=np.float32)
        # Máscara del cono frontal: los rayos que cuentan como "al frente".
        self._fan_front_mask = np.abs(self.fan_angles) <= math.radians(
            FRONT_CONE_DEG
        )
        # Compatibilidad: índices del anillo de 72 más cercanos a cada rayo del
        # abanico. Los scripts viejos que hacían lidar_meters[_front_indices]
        # siguen devolviendo 36 números coherentes.
        step_ring = 2.0 * math.pi / LIDAR_RAYS
        self._front_indices: List[int] = [
            int(round(float(a) / step_ring)) % LIDAR_RAYS
            for a in self.fan_angles
        ]

        # Chunk mapper
        self.chunk_mapper = ChunkMapper(cell_size=1.0)
        self._chunks_discovered_before_reset: int = 0

        # Estado interno de recompensas V4
        self._idle_steps = 0
        self._move_streak = 0
        self._idle_penalized = False
        self._trap_cooldown = 0
        self._last_pos: tuple[float, float] | None = None
        self._prev_collision = False

        # Estado de resolución de problemas
        self._contact_flag = False
        self._contact_points: list[tuple[float, float, float]] = []
        self._contact_normals: list[tuple[float, float, float]] = []
        self._was_in_contact = False
        self._escape_pending = 0
        self._escape_moved = 0.0
        self._contact_distance: float | None = None
        self._escaped_awarded = False
        self._stuck_steps = 0
        self._prev_nearest = LIDAR_MAX_DIST
        self._prev_front_min = LIDAR_MAX_DIST

        # Obstáculos extra V4 (se llenan en _build_obstacles)
        self.cylinder_ids: List[int] = []
        self.cylinder_radii: List[float] = []
        self.cylinder_positions: List[Tuple[float, float]] = []
        self.long_wall_ids: List[int] = []
        self.long_wall_positions: List[Tuple[float, float]] = []
        self.ramp_ids: List[int] = []
        self.ramp_positions: List[Tuple[float, float]] = []
        self.l_wall_ids: List[int] = []
        self.l_wall_positions: List[Tuple[float, float]] = []
        self.friction_zone_ids: List[int] = []

        super().__init__(
            render_mode=render_mode,
            stage=stage,
            max_episode_steps=max_episode_steps,
            max_wheel_speed=max_wheel_speed,
            max_force=max_force,
            arena_half_size=arena_half_size,
            visual_mesh_path=visual_mesh_path,
            show_proxy_visuals=show_proxy_visuals,
            randomize_mass=randomize_mass,
            total_mass_range=total_mass_range,
            wheel_mass=wheel_mass,
            wheel_friction_range=wheel_friction_range,
            obstacle_count=obstacle_count,
            stage12_min_obstacle_distance=8.0,
            stage3_min_obstacle_distance=stage3_min_obstacle_distance,
            obstacle_max_distance=obstacle_max_distance,
            obstacle_min_separation=obstacle_min_separation,
            tilt_limit_deg=tilt_limit_deg,
            tilt_grace_steps=tilt_grace_steps,
            tilt_penalty=tilt_penalty,
            flip_penalty=flip_penalty,
            crash_penalty=crash_penalty,
            time_penalty=time_penalty,
            forward_reward_scale=forward_reward_scale,
            connect_options=connect_options,
            collision_terminates=self._collision_terminates,
            wheel_sink=wheel_sink,
        )

        self.reference_yaw = 0.0

        # Espacio de observación V5 (58D = 14 base + 36 frontales + 8 extras).
        # Los tres bloques se declaran explícitamente: antes la lista de bounds
        # sólo cubría 14 + SENSOR_COUNT y el espacio quedaba en 50D mientras
        # _get_obs devolvía 58D, lo que rompía el LSTM de RecurrentPPO con
        # "shape [1, -1, 50] is invalid for input of size 58".
        base_low = [
            -self.arena_half_size,   # x
            -self.arena_half_size,   # y
            -1.0, -1.0, -1.0, -1.0,  # orientación (sin/cos)
            -10.0, -10.0, -10.0,     # velocidad lineal
            -20.0, -20.0, -20.0,     # velocidad angular
            -1.0,                    # heading normalizado
            -math.pi,                # error de rumbo
        ]
        sensor_low = [0.0] * SENSOR_COUNT
        # 50..57: claridad frontal, distancia mínima, seno y coseno del rumbo
        # al obstáculo, seno y coseno del hueco libre, contacto y atascado.
        # 58..65: despeje lateral izquierdo y derecho, ancho del hueco, despeje
        # en su centro, despeje hacia el objetivo, despeje detrás, velocidad
        # de avance (único extra con signo) y fracción del abanico libre.
        extras_low = [
            # V5: frente, cercania, rumbo al obstaculo, rumbo libre,
            # contacto y atasco.
            0.0, 0.0, -1.0, -1.0, -1.0, -1.0, 0.0, 0.0,
            # V6: costados, hueco, objetivo, detras, velocidad y abanico libre.
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0,
            # V7: derrape, tiempo al impacto, techo (frente/izq/der), tipos de
            # obstaculo y costado libre.
            -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0,
        ]

        obs_low = np.array(
            base_low + sensor_low + extras_low, dtype=np.float32
        )
        obs_high = np.array(
            [
                self.arena_half_size,
                self.arena_half_size,
                1.0, 1.0, 1.0, 1.0,
                10.0, 10.0, 10.0,
                20.0, 20.0, 20.0,
                1.0,
                math.pi,
            ]
            + [1.0] * SENSOR_COUNT
            + [1.0] * OBS_EXTRAS,
            dtype=np.float32,
        )

        if obs_low.size != OBS_DIM:  # nunca debe dispararse: falla ruidoso
            raise RuntimeError(
                f"observation_space mal dimensionado: {obs_low.size} != {OBS_DIM}"
            )

        self.observation_space = gym.spaces.Box(
            low=obs_low, high=obs_high, dtype=np.float32
        )

    # ------------------------------------------------------------------ #
    # Construcción de obstáculos V4
    # ------------------------------------------------------------------ #
    def _build_obstacles(self) -> None:
        super()._build_obstacles()  # cajas de alturas variadas (V2)

        # Cilindros (postes)
        self.cylinder_ids = []
        self.cylinder_radii = []
        for i in range(max(2, self.obstacle_count // 2)):
            radius = float(self.np_random.uniform(0.15, 0.40))
            height = float(self.np_random.uniform(0.6, 2.0))
            collision = self.p.createCollisionShape(
                self.p.GEOM_CYLINDER, radius=radius, height=height
            )
            visual = self.p.createVisualShape(
                self.p.GEOM_CYLINDER,
                radius=radius,
                length=height,
                rgbaColor=[0.6, 0.6, 0.62, 1.0],
            )
            body = self.p.createMultiBody(
                baseMass=0.0,
                baseCollisionShapeIndex=collision,
                baseVisualShapeIndex=visual,
                basePosition=[0.0, 14.0 + i * 2.5, height / 2.0],
            )
            self.p.changeDynamics(body, -1, lateralFriction=0.9, restitution=0.0)
            self.cylinder_ids.append(body)
            self.cylinder_radii.append(radius)

        # Paredes largas que bordean la arena
        self._build_long_walls()
        # Rampas inclinadas
        self._build_ramps()
        # Paredes en forma de L (callejones sin salida)
        self._build_l_walls()
        # Zonas de fricción variable
        self._build_friction_zones()

        # Sombras en la GUI (entorno más realista)
        try:
            info = self.p.getConnectionInfo()
            if int(info.get("connectionMethod", -1)) == int(self.p.GUI):
                self.p.configureDebugVisualizer(self.p.COV_ENABLE_SHADOWS, 1)
        except Exception:
            pass

        # Estética neutral: blanco / gris claro / negro para que el
        # láser azul del LiDAR destaque sobre los obstáculos.
        neutral_palette = [
            (0.92, 0.92, 0.92, 1.0),  # blanco
            (0.60, 0.60, 0.62, 1.0),  # gris claro
            (0.10, 0.10, 0.12, 1.0),  # negro
        ]
        all_bodies = (
            self.obstacle_ids
            + self.cylinder_ids
            + self.long_wall_ids
            + self.ramp_ids
            + self.l_wall_ids
        )
        for index, body in enumerate(all_bodies):
            try:
                self.p.changeVisualShape(
                    body, -1, rgbaColor=list(neutral_palette[index % 3])
                )
            except Exception:
                pass

    def _build_long_walls(self) -> None:
        """Paredes largas que bordean el área de exploración."""
        half = self.arena_half_size
        length = 2.0 * half + 2.0
        half_len = length / 2.0
        wall_thickness = 0.3
        wall_half_height = 0.8
        wall_color = [0.30, 0.30, 0.33, 1.0]

        self.long_wall_positions = []
        for pos, half_extents in [
            ([half + wall_thickness, 0.0, wall_half_height],
             [wall_thickness, half_len, wall_half_height]),
            ([-half - wall_thickness, 0.0, wall_half_height],
             [wall_thickness, half_len, wall_half_height]),
            ([0.0, half + wall_thickness, wall_half_height],
             [half_len, wall_thickness, wall_half_height]),
            ([0.0, -half - wall_thickness, wall_half_height],
             [half_len, wall_thickness, wall_half_height]),
        ]:
            collision = self.p.createCollisionShape(
                self.p.GEOM_BOX, halfExtents=half_extents
            )
            visual = self.p.createVisualShape(
                self.p.GEOM_BOX, halfExtents=half_extents,
                rgbaColor=wall_color,
            )
            body = self.p.createMultiBody(
                baseMass=0.0,
                baseCollisionShapeIndex=collision,
                baseVisualShapeIndex=visual,
                basePosition=pos,
            )
            self.p.changeDynamics(body, -1, lateralFriction=0.9, restitution=0.0)
            self.long_wall_ids.append(body)
            self.long_wall_positions.append((pos[0], pos[1]))

    def _build_ramps(self) -> None:
        """Rampas inclinadas (pendientes) para física compleja.

        Antes eran cajas de 6 cm flotando a z=0.22 con 18°: el borde bajo
        quedaba a 12 cm del suelo y el alto a 0.56 m, así que para WALL-E
        (0.35 m de largo, ruedas de 9 cm) eran un escalón, no una rampa. Se
        subía de lado, patinaba y se quedaba clavado. Ahora el borde bajo
        queda enrasado con el suelo y la pendiente es de 10°.
        """
        self.ramp_ids = []
        self.ramp_positions = []
        half_len = 1.1
        thickness = 0.06
        specs = [
            (4.5, -3.5, math.radians(10.0)),
            (-4.0, 4.5, math.radians(-10.0)),
        ]
        for x, y, pitch in specs:
            half_extents = [half_len, 0.9, thickness]
            # Centro a media altura del plano inclinado, hundido medio grosor
            # para que la cara superior del borde bajo toque el suelo.
            z = half_len * abs(math.sin(pitch)) - thickness * 0.5
            collision = self.p.createCollisionShape(
                self.p.GEOM_BOX, halfExtents=half_extents
            )
            visual = self.p.createVisualShape(
                self.p.GEOM_BOX,
                halfExtents=half_extents,
                rgbaColor=[0.55, 0.55, 0.58, 1.0],
            )
            quat = self.p.getQuaternionFromEuler([0.0, pitch, 0.0])
            body = self.p.createMultiBody(
                baseMass=0.0,
                baseCollisionShapeIndex=collision,
                baseVisualShapeIndex=visual,
                basePosition=[x, y, z],
                baseOrientation=quat,
            )
            self.p.changeDynamics(body, -1, lateralFriction=1.0, restitution=0.0)
            self.ramp_ids.append(body)
            self.ramp_positions.append((x, y))

    def _build_l_walls(self) -> None:
        """Paredes en forma de L que crean callejones sin salida."""
        self.l_wall_ids = []
        self.l_wall_positions = []
        length = 2.2
        height = 0.9
        thickness = 0.15
        for cx, cy in [(4.0, 3.0), (-4.5, -3.5)]:
            # Pared A: a lo largo del eje X, centrada en (cx, cy)
            half_a = [length / 2.0, thickness / 2.0, height / 2.0]
            # Pared B: a lo largo del eje Y, arranca en el extremo de A
            half_b = [thickness / 2.0, length / 2.0, height / 2.0]
            pos_b = [cx + length / 2.0, cy + length / 2.0, height / 2.0]
            for half_extents, position in [
                (half_a, [cx, cy, height / 2.0]),
                (half_b, pos_b),
            ]:
                collision = self.p.createCollisionShape(
                    self.p.GEOM_BOX, halfExtents=half_extents
                )
                visual = self.p.createVisualShape(
                    self.p.GEOM_BOX,
                    halfExtents=half_extents,
                    rgbaColor=[0.35, 0.35, 0.38, 1.0],
                )
                body = self.p.createMultiBody(
                    baseMass=0.0,
                    baseCollisionShapeIndex=collision,
                    baseVisualShapeIndex=visual,
                    basePosition=position,
                )
                self.p.changeDynamics(
                    body, -1, lateralFriction=0.9, restitution=0.0
                )
                self.l_wall_ids.append(body)
                self.l_wall_positions.append((position[0], position[1]))

    def _build_friction_zones(self) -> None:
        """Zonas de fricción variable: césped (2.0) y baldosa (0.5).

        Solo existen como colisión: no llevan forma visual para que el suelo
        del estudio se vea uniforme, sin parches de color ni cajas negras.
        """
        self.friction_zone_ids = []
        zones = [
            # (posición, semiejes, fricción)
            ([3.5, 3.5, 0.006], [3.0, 3.0, 0.006], 2.0),   # césped
            ([-3.5, -3.5, 0.006], [3.0, 3.0, 0.006], 0.5),  # baldosa
        ]
        # PyBullet dibuja los cuerpos sin forma visual con colores por
        # defecto (amarillo/verde). Por eso cada zona lleva una losa visual
        # fina, del color del suelo y a ras del piso: invisible en la escena.
        zone_color = [0.26, 0.26, 0.28, 1.0]
        for position, half_extents, mu in zones:
            collision = self.p.createCollisionShape(
                self.p.GEOM_BOX, halfExtents=half_extents
            )
            visual = self.p.createVisualShape(
                self.p.GEOM_BOX,
                halfExtents=[half_extents[0], half_extents[1], 0.001],
                rgbaColor=zone_color,
                visualFramePosition=[0.0, 0.0, -0.005],
            )
            body = self.p.createMultiBody(
                baseMass=0.0,
                baseCollisionShapeIndex=collision,
                baseVisualShapeIndex=visual,
                basePosition=position,
            )
            self.p.changeDynamics(body, -1, lateralFriction=mu, restitution=0.0)
            self.friction_zone_ids.append(body)

    def _place_obstacles(self) -> None:
        """Coloca cajas y cilindros lejos del robot, con separación mínima."""
        super()._place_obstacles()  # coloca las cajas de V2

        # Coloca cilindros también lejos del robot
        min_dist = self.stage3_min_obstacle_distance
        max_dist = min(
            self.obstacle_max_distance,
            self.arena_half_size - 2.0,
        )
        positions: List[Tuple[float, float]] = list(self.obstacle_positions)

        for body, radius in zip(self.cylinder_ids, self.cylinder_radii):
            chosen = None
            for _attempt in range(120):
                angle = float(self.np_random.uniform(0.0, 2.0 * math.pi))
                r = float(self.np_random.uniform(min_dist, max_dist))
                x = r * math.cos(angle)
                y = r * math.sin(angle)
                ok = all(
                    math.hypot(x - px, y - py)
                    >= self.obstacle_min_separation + radius
                    for px, py in positions
                )
                if ok:
                    chosen = (x, y)
                    break
            if chosen is None:
                chosen = (
                    float(self.np_random.uniform(-max_dist, max_dist)),
                    float(self.np_random.uniform(-max_dist, max_dist)),
                )
            positions.append(chosen)
            self.p.resetBasePositionAndOrientation(
                body, [chosen[0], chosen[1], 0.0], [0.0, 0.0, 0.0, 1.0]
            )

        self.cylinder_positions = [
            tuple(self.p.getBasePositionAndOrientation(body)[0][:2])
            for body in self.cylinder_ids
        ]

    # ------------------------------------------------------------------ #
    # LiDAR: anillo de 72 + abanico de 36 (una sola llamada por paso)
    # ------------------------------------------------------------------ #
    def _body_radius(self, theta: float) -> float:
        """Distancia del centro del chasis a su borde en la dirección `theta`.

        El LiDAR mide desde el centro del robot, pero el choque ocurre en el
        paragolpes. Restar este radio convierte la lectura en "metros hasta
        tocar", que es lo que asumen los umbrales de recompensa.

        Caja de semiejes (BODY_HALF_X, BODY_HALF_Y): la salida del rayo por la
        cara correspondiente es min(hx/|cos|, hy/|sin|).
        """
        c = abs(math.cos(theta))
        s = abs(math.sin(theta))
        limite_x = BODY_HALF_X / c if c > 1e-6 else math.inf
        limite_y = BODY_HALF_Y / s if s > 1e-6 else math.inf
        return min(limite_x, limite_y)

    def _scan_lidar(self) -> None:
        """Escanea dos planos en una sola pasada: suelo y altura de techo.

        Plano bajo (SENSOR_FOOT_Z, 6 cm): que hay delante.
        Plano alto (HEADROOM_FOOT_Z, 34 cm): que hay a la altura del chasis.

        Con un solo plano, una pared de 2 m y una caja de 12 cm se leen igual:
        las dos son "obstaculo a 1.4 m". Comparando los dos planos aparece la
        diferencia que importa para decidir:

            bajo si, alto si   -> pared o bloque alto: no se pasa.
            bajo si, alto no   -> caja baja: se puede trepar o pasar por encima.
            bajo no, alto si   -> voladizo: se pasa por debajo.
            ninguno            -> libre.

        El plano alto se lanza aparte y solo para las direcciones donde el
        plano bajo choco: sin impacto abajo no hay nada que comparar, y
        lanzar los 36 rayos altos siempre costaba 1.3 ms por paso, que es
        justo el presupuesto de un tick a 60 Hz en la GUI.

        Las distancias se devuelven desde el borde del robot: 0 = tocando.
        """
        pos, quat = self.p.getBasePositionAndOrientation(self.robot)
        yaw = float(self.p.getEulerFromQuaternion(quat)[2])
        # Altura sobre el suelo local: en llano da la constante exacta; sobre
        # una rampa sube con el robot, porque el sensor esta atornillado a el.
        z_low = max(0.02, pos[2] - self.BASE_Z + SENSOR_FOOT_Z)
        z_high = max(z_low + 0.05, pos[2] - self.BASE_Z + HEADROOM_FOOT_Z)

        n_ring = LIDAR_RAYS
        n_fan = int(self.fan_angles.size)
        total = n_ring + n_fan

        froms: list[list[float]] = []
        tos: list[list[float]] = []
        thetas = np.empty(total, dtype=np.float64)

        def add_ray(theta: float, z: float) -> None:
            angle = yaw + theta
            dx, dy = math.cos(angle), math.sin(angle)
            froms.append(
                [
                    pos[0] + dx * LIDAR_ORIGIN_OFFSET,
                    pos[1] + dy * LIDAR_ORIGIN_OFFSET,
                    z,
                ]
            )
            tos.append(
                [
                    pos[0] + dx * LIDAR_MAX_DIST,
                    pos[1] + dy * LIDAR_MAX_DIST,
                    z,
                ]
            )

        for i in range(n_ring):
            theta = 2.0 * math.pi * i / n_ring
            thetas[i] = theta
            add_ray(theta, z_low)

        for j in range(n_fan):
            theta = float(self.fan_angles[j])
            thetas[n_ring + j] = theta
            add_ray(theta, z_low)

        # La exclusion por parentObjectUniqueId NO sirve en esta build. Medido:
        #   parentLinkIndex=-1 (u omitido) -> el lote entero devuelve (-1, 1.0)
        #   parentLinkIndex=0 o 1         -> excluye el cuerpo, pero depende de
        #                                    que el robot tenga al menos un link
        # Un lote vacio se lee como "todo libre a 6 m" y WALL-E se come la pared.
        # Se saca al robot del broadphase mientras dura el barrido, que es
        # determinista y no depende de la cantidad de links. No hay step de
        # simulacion entre el apagado y el encendido, asi que la fisica no ve
        # nada raro. Grupo 1 / mascara 0xFFFF es el valor por defecto de
        # createMultiBody en pybullet 3.2.7.
        self.p.setCollisionFilterGroupMask(self.robot, -1, 0, 0)
        try:
            results = self.p.rayTestBatch(froms, tos, numThreads=LIDAR_THREADS)
        finally:
            self.p.setCollisionFilterGroupMask(self.robot, -1, 1, 0xFFFF)

        meters = np.empty(total, dtype=np.float32)
        for i in range(total):
            hit = results[i]
            # Cinturon y tirantes: si alguna build vuelve a ignorar la
            # exclusion, un impacto contra el propio cuerpo no es distancia.
            if int(hit[0]) == self.robot:
                meters[i] = LIDAR_MAX_DIST
                continue

            frac = float(hit[2])
            if frac >= 1.0:
                # Sin impacto: espacio libre hasta el alcance maximo. No se le
                # resta el radio del chasis para que "libre" valga exactamente
                # LIDAR_MAX_DIST y los umbrales de hueco libre sigan claros.
                meters[i] = LIDAR_MAX_DIST
                continue

            # Distancia al obstaculo medida desde el paragolpes, no desde el
            # centro. Por debajo de 0 el robot ya esta penetrando: 0 = tocando.
            dist = frac * LIDAR_MAX_DIST - self._body_radius(float(thetas[i]))
            if self._sensor_noise_std > 0.0:
                dist += float(
                    self.np_random.normal(0.0, self._sensor_noise_std)
                )
            meters[i] = min(max(dist, 0.0), LIDAR_MAX_DIST)

        low = meters[: n_ring + n_fan]
        self.lidar_meters = low[:n_ring]
        self.lidar_norm = np.clip(
            1.0 - self.lidar_meters / LIDAR_MAX_DIST, 0.0, 1.0
        ).astype(np.float32)
        self.fan_meters = low[n_ring:]
        self.fan_norm = np.clip(
            1.0 - self.fan_meters / LIDAR_MAX_DIST, 0.0, 1.0
        ).astype(np.float32)
        self.fan_low_hit = self.fan_meters < LIDAR_MAX_DIST * 0.995

        # --- plano alto, solo donde el bajo encontro algo ---------------- #
        # Un rayo alto solo aporta informacion si el rayo bajo de esa misma
        # direccion choco: hace falta comparar dos lecturas. Si el bajo esta
        # limpio no hay nada que comparar (o no hay obstaculo, o hay un
        # voladizo que el robot pasa por debajo igual). Con los 36 rayos
        # lanzados siempre el barrido costaba 1.3 ms mas y la GUI perdia el
        # presupuesto de 16.6 ms por tick; con esto, en una arena despejada el
        # segundo barrido no se hace.
        self.headroom_meters = np.full(SENSOR_COUNT, LIDAR_MAX_DIST, np.float32)
        alto_idx = np.nonzero(self.fan_low_hit)[0]
        if alto_idx.size:
            froms_alto: list[list[float]] = []
            tos_alto: list[list[float]] = []
            for j in alto_idx:
                angle = yaw + float(self.fan_angles[j])
                dx, dy = math.cos(angle), math.sin(angle)
                froms_alto.append(
                    [
                        pos[0] + dx * LIDAR_ORIGIN_OFFSET,
                        pos[1] + dy * LIDAR_ORIGIN_OFFSET,
                        z_high,
                    ]
                )
                tos_alto.append(
                    [
                        pos[0] + dx * LIDAR_MAX_DIST,
                        pos[1] + dy * LIDAR_MAX_DIST,
                        z_high,
                    ]
                )
            self.p.setCollisionFilterGroupMask(self.robot, -1, 0, 0)
            try:
                alto = self.p.rayTestBatch(
                    froms_alto, tos_alto, numThreads=LIDAR_THREADS
                )
            finally:
                self.p.setCollisionFilterGroupMask(self.robot, -1, 1, 0xFFFF)
            for k, j in enumerate(alto_idx):
                hit = alto[k]
                if int(hit[0]) == self.robot:
                    continue
                frac = float(hit[2])
                if frac >= 1.0:
                    continue
                dist = frac * LIDAR_MAX_DIST - self._body_radius(
                    float(self.fan_angles[j])
                )
                if self._sensor_noise_std > 0.0:
                    dist += float(
                        self.np_random.normal(0.0, self._sensor_noise_std)
                    )
                self.headroom_meters[j] = min(max(dist, 0.0), LIDAR_MAX_DIST)

        self.headroom_norm = np.clip(
            1.0 - self.headroom_meters / LIDAR_MAX_DIST, 0.0, 1.0
        ).astype(np.float32)

        # Semantica por rayo del abanico. Un rayo que toca abajo y no toca
        # arriba es un obstaculo bajo: se puede trepar.
        self.fan_high_hit = self.headroom_meters < LIDAR_MAX_DIST * 0.995
        self.fan_climbable = self.fan_low_hit & ~self.fan_high_hit
        self.fan_blocking = self.fan_low_hit & self.fan_high_hit

    def _nearest_ray(self) -> tuple[int, float]:
        """Rayo (índice) y distancia del obstáculo más cercano de los 72."""
        if self.lidar_meters.size == 0:
            return 0, LIDAR_MAX_DIST
        index = int(np.argmin(self.lidar_meters))
        return index, float(self.lidar_meters[index])

    def _free_direction(self) -> tuple[float, float]:
        """Dirección (sin, cos) del hueco libre más ancho, relativa al frente.

        Recorre el anillo de rayos y busca la tirada contigua más larga de
        rayos con distancia > FREE_RAY_M. Devuelve el centro angular de ese
        hueco: es la ruta de escape natural cuando está pegado a algo.
        """
        n = int(self.lidar_meters.size)
        if n == 0:
            return 0.0, 0.0
        free = self.lidar_meters > FREE_RAY_M
        if not free.any():
            return 0.0, 0.0
        if free.all():
            return 0.0, 1.0
        # Empezar en un rayo bloqueado rompe la circularidad.
        start = int(np.argmin(free))
        best_len = 0
        best_start = 0
        run_len = 0
        run_start = 0
        for k in range(n):
            idx = (start + k) % n
            if free[idx]:
                if run_len == 0:
                    run_start = k
                run_len += 1
                if run_len > best_len:
                    best_len = run_len
                    best_start = run_start
            else:
                run_len = 0
        step = 2.0 * math.pi / n
        mid = best_start + (best_len - 1) * 0.5
        angle = ((start + mid) * step + math.pi) % (2.0 * math.pi) - math.pi
        return math.sin(angle), math.cos(angle)

    def _widest_gap(self) -> tuple[float, float]:
        """Hueco libre más ancho: (ancho en radianes, distancia en su centro).

        `_free_direction` devuelve hacia dónde está el hueco; esto devuelve
        además CUÁNTO mide. Un hueco de 20° no es una salida, uno de 120° sí,
        y con solo la dirección la política no podía distinguirlos.
        """
        n = int(self.lidar_meters.size)
        if n == 0:
            return 0.0, float(self.lidar_max_dist)
        free = self.lidar_meters > FREE_RAY_M
        if not free.any():
            return 0.0, float(self.lidar_meters.min())
        if free.all():
            return math.pi, float(self.lidar_max_dist)
        start = int(np.argmin(free))
        best_len = 0
        best_start = 0
        run_len = 0
        run_start = 0
        for k in range(n):
            idx = (start + k) % n
            if free[idx]:
                if run_len == 0:
                    run_start = k
                run_len += 1
                if run_len > best_len:
                    best_len = run_len
                    best_start = run_start
            else:
                run_len = 0
        step = 2.0 * math.pi / n
        mid = (start + best_start + (best_len - 1) * 0.5) % n
        ancho = max(0, best_len - 1) * step
        return ancho, float(self.lidar_meters[int(mid)])

    def _fan_sector_min(self, lo_deg: float, hi_deg: float) -> float:
        """Distancia mínima del abanico entre dos ángulos, en grados."""
        lo = math.radians(min(lo_deg, hi_deg))
        hi = math.radians(max(lo_deg, hi_deg))
        mask = (self.fan_angles >= lo) & (self.fan_angles <= hi)
        if not mask.any():
            return float(self.lidar_max_dist)
        return float(self.fan_meters[mask].min())

    def _head_sector_min(self, lo_deg: float, hi_deg: float) -> float:
        """Distancia libre minima del plano alto en un sector del abanico."""
        mask = (self.fan_angles >= math.radians(lo_deg)) & (
            self.fan_angles <= math.radians(hi_deg)
        )
        if not mask.any():
            return float(self.lidar_max_dist)
        return float(self.headroom_meters[mask].min())

    def _problem_obs(self) -> np.ndarray:
        """24 valores que describen el problema inmediato del robot.

        Los 8 primeros son los del V5 y los 8 siguientes los del V6, en el
        mismo orden: los tres bloques se pueden leer por separado. Los 8
        ultimos son del V7 y describen lo que el robot necesita para entender
        el entorno en vez de solo reaccionar:

            16 derrape          velocidad lateral en el eje del chasis
            17 tiempo_impacto   segundos hasta tocar, normalizado a 2 s
            18-20 techo         despeje del plano alto: frente, izquierda, derecha
            21 ratio_bajo       fraccion del frente con obstaculo trepable
            22 ratio_alto       fraccion del frente con obstaculo que bloquea
            23 costado_libre    -1 = conviene ir a la izquierda, +1 a la derecha
        """
        meters = self.lidar_meters
        max_d = float(self.lidar_max_dist)
        # "Al frente" es el cono de decision, no el semicirculo entero: con
        # +-90 grados una pared al costado contaba como obstaculo frontal y el
        # robot frenaba en mitad de la nada.
        front = self.fan_meters[self._fan_front_mask]
        front_min = float(front.min()) if front.size else max_d
        index, nearest = self._nearest_ray()
        step = 2.0 * math.pi / max(1, int(meters.size))
        bearing = index * step
        bearing = (bearing + math.pi) % (2.0 * math.pi) - math.pi
        free_sin, free_cos = self._free_direction()

        # --- costados: por donde se puede escapar ------------------------
        libre_izq = self._fan_sector_min(SIDE_MIN_DEG, 90.0)
        libre_der = self._fan_sector_min(-90.0, -SIDE_MIN_DEG)

        # --- hueco mas ancho ---------------------------------------------
        hueco_ancho, hueco_dist = self._widest_gap()

        # --- rumbo al objetivo: que hay justo en esa direccion -----------
        pos, quat = self.p.getBasePositionAndOrientation(self.robot)
        yaw = float(self.p.getEulerFromQuaternion(quat)[2])
        goal_bearing = wrap_angle(float(self.goal_angle) - yaw)
        goal_deg = math.degrees(goal_bearing)
        goal_clear = self._fan_sector_min(
            goal_deg - GOAL_CONE_DEG, goal_deg + GOAL_CONE_DEG
        )

        # --- detras: el anillo si llega, el abanico no -------------------
        angulos = np.arange(meters.size) * step
        angulos = (angulos + math.pi) % (2.0 * math.pi) - math.pi
        detras_mask = np.abs(angulos) > math.radians(REAR_DEG)
        trasero = (
            float(meters[detras_mask].min()) if detras_mask.any() else max_d
        )

        # --- velocidad real en el eje del chasis -------------------------
        lin_vel, _ = self.p.getBaseVelocity(self.robot)
        vel_adelante = (
            float(lin_vel[0]) * math.cos(yaw) + float(lin_vel[1]) * math.sin(yaw)
        )
        vel_max = self.max_wheel_speed * 0.09  # rueda de 9 cm
        vel_norm = float(np.clip(vel_adelante / max(vel_max, 1e-6), -1.0, 1.0))

        # --- proporcion del abanico que esta despejada -------------------
        ratio_libre = float(np.mean(self.fan_meters > FREE_RAY_M))

        # --- segundo plano: que es alto y que se puede pasar -------------
        head = self.headroom_meters
        head_front = (
            float(head[self._fan_front_mask].min())
            if self._fan_front_mask.any()
            else max_d
        )
        head_izq = self._head_sector_min(SIDE_MIN_DEG, 90.0)
        head_der = self._head_sector_min(-90.0, -SIDE_MIN_DEG)

        # Fraccion del frente ocupada por cada tipo de obstaculo. Con estos
        # dos numeros la politica sabe si lo que tiene delante es una pared o
        # una caja que puede trepar.
        front_mask = self._fan_front_mask
        if front_mask.any():
            total_frente = float(front_mask.sum())
            ratio_bajo = float(self.fan_climbable[front_mask].sum()) / total_frente
            ratio_alto = float(self.fan_blocking[front_mask].sum()) / total_frente
        else:
            ratio_bajo = 0.0
            ratio_alto = 0.0

        # --- derrape: velocidad lateral en el eje del chasis -------------
        vel_lateral = -float(lin_vel[0]) * math.sin(yaw) + float(
            lin_vel[1]
        ) * math.cos(yaw)
        vel_lat_norm = float(
            np.clip(vel_lateral / max(vel_max, 1e-6), -1.0, 1.0)
        )

        # --- tiempo hasta el impacto -------------------------------------
        # front_min en metros, vel_adelante en m/s. Se normaliza a 2 s de
        # horizonte: 1.0 = sin riesgo, 0.0 = se lo come en el proximo paso.
        # Es lo que permite frenar progresivo en vez de dar un volantazo.
        velocidad = abs(float(vel_adelante))
        if velocidad > 0.02:
            segundos = max(0.0, float(front_min)) / velocidad
            tiempo_impacto = float(np.clip(segundos / 2.0, 0.0, 1.0))
        else:
            tiempo_impacto = 1.0

        # --- costado mas libre -------------------------------------------
        diferencia = float(np.clip((libre_der - libre_izq) / max_d, -1.0, 1.0))

        return np.array(
            [
                # --- 8 del V5, mismo orden ------------------------------
                float(np.clip(1.0 - front_min / max_d, 0.0, 1.0)),
                float(np.clip(1.0 - nearest / max_d, 0.0, 1.0)),
                math.sin(bearing),
                math.cos(bearing),
                free_sin,
                free_cos,
                1.0 if self._contact_flag else 0.0,
                1.0 if self._stuck_steps >= STUCK_STEPS else 0.0,
                # --- 8 del V6 -------------------------------------------
                float(np.clip(1.0 - libre_izq / max_d, 0.0, 1.0)),
                float(np.clip(1.0 - libre_der / max_d, 0.0, 1.0)),
                float(np.clip(hueco_ancho / math.pi, 0.0, 1.0)),
                float(np.clip(1.0 - hueco_dist / max_d, 0.0, 1.0)),
                float(np.clip(1.0 - goal_clear / max_d, 0.0, 1.0)),
                float(np.clip(1.0 - trasero / max_d, 0.0, 1.0)),
                vel_norm,
                ratio_libre,
                # --- 8 del V7: entender el entorno ----------------------
                vel_lat_norm,
                tiempo_impacto,
                float(np.clip(1.0 - head_front / max_d, 0.0, 1.0)),
                float(np.clip(1.0 - head_izq / max_d, 0.0, 1.0)),
                float(np.clip(1.0 - head_der / max_d, 0.0, 1.0)),
                ratio_bajo,
                ratio_alto,
                diferencia,
            ],
            dtype=np.float32,
        )

    def _get_obs(self) -> np.ndarray:
        base_obs = super()._get_obs()  # 14D de V2
        if self._enable_sensors:
            self._scan_lidar()
            front = self.fan_norm
            extras = self._problem_obs()
        else:
            front = np.ones(SENSOR_COUNT, dtype=np.float32)
            extras = np.zeros(OBS_EXTRAS, dtype=np.float32)
        return np.concatenate(
            [
                base_obs,
                np.asarray(front, dtype=np.float32),
                np.asarray(extras, dtype=np.float32),
            ],
            dtype=np.float32,
        )

    # ------------------------------------------------------------------ #
    # Chunk mapper - optimizado para rendimiento
    # ------------------------------------------------------------------ #
    def _update_chunk_mapper(self) -> None:
        """Actualiza el mapa de chunks con la posición actual y obstáculos."""
        pos = self._pose().pos if hasattr(self, "_pose") else None
        if pos is None:
            pos, _ = self.p.getBasePositionAndOrientation(self.robot)
        # Marcar celda actual como libre
        self.chunk_mapper.update_position(float(pos[0]), float(pos[1]))

        # Marcar celdas ocupadas solo por obstáculos cercanos (dentro de 8m)
        # para reducir carga computacional
        bodies = (
            self.obstacle_ids
            + self.cylinder_ids
            + self.long_wall_ids
            + self.l_wall_ids
            + self.ramp_ids
        )
        cx, cy = pos[0], pos[1]
        cell_size = self.chunk_mapper.cell_size
        for body in bodies:
            bpos, _ = self.p.getBasePositionAndOrientation(body)
            # Solo procesar obstáculos cerca del robot (rendimiento)
            if math.hypot(bpos[0] - cx, bpos[1] - cy) > 8.0:
                continue
            if body in self.cylinder_ids:
                idx = self.cylinder_ids.index(body)
                radius = self.cylinder_radii[idx]
            else:
                radius = 0.45
            bx, by = bpos[0], bpos[1]
            min_ix = int(math.floor((bx - radius) / cell_size))
            max_ix = int(math.floor((bx + radius) / cell_size))
            min_iy = int(math.floor((by - radius) / cell_size))
            max_iy = int(math.floor((by + radius) / cell_size))
            for ix in range(min_ix, max_ix + 1):
                for iy in range(min_iy, max_iy + 1):
                    cx_cell, cy_cell = self.chunk_mapper.cell_to_world(ix, iy)
                    if math.hypot(cx_cell - bx, cy_cell - by) <= radius:
                        self.chunk_mapper.cells[
                            (ix, iy)
                        ] = self.chunk_mapper.OBSTACLE

    def _count_new_discovered(self) -> int:
        """Devuelve cuántas celdas han cambiado de estado desde el último conteo."""
        current = len(self.chunk_mapper.cells)
        new_count = current - self._chunks_discovered_before_reset
        self._chunks_discovered_before_reset = current
        return max(0, new_count)

    def set_reference_yaw(self, yaw: float) -> None:
        """Fija el rumbo de referencia para la recompensa de avance."""
        self.reference_yaw = float(yaw)

    # ------------------------------------------------------------------ #
    # Detección de colisiones con TODOS los obstáculos V4
    # ------------------------------------------------------------------ #
    def _has_collision(self) -> bool:
        bodies = (
            self.wall_ids
            + self.obstacle_ids
            + self.cylinder_ids
            + self.long_wall_ids
            + self.ramp_ids
            + self.l_wall_ids
        )
        points: list[tuple[float, float, float]] = []
        normals: list[tuple[float, float, float]] = []
        for body_id in bodies:
            contacts = self.p.getContactPoints(bodyA=self.robot, bodyB=body_id)
            for contact in contacts:
                # Un punto de contacto NO es un choque. PyBullet deja pares
                # "fantasma" en la lista con normalForce=0 y sin penetración:
                # son candidatos de colisión de broadphase, no contacto real.
                # Contarlos hacía que WALL-E se declarara chocado en mitad de
                # la nada, se despegara y abandonara la orden.
                force = float(contact[9])
                penetration = float(contact[8])
                if force < COLLISION_MIN_FORCE and penetration > -COLLISION_MIN_PENETRATION_M:
                    continue
                # contact[5] = punto de contacto en el mundo.
                # contact[7] = normal en el cuerpo B.
                point = contact[5]
                normal = contact[7]
                points.append((float(point[0]), float(point[1]), float(point[2])))
                normals.append(
                    (float(normal[0]), float(normal[1]), float(normal[2]))
                )
        self._contact_points = points
        self._contact_normals = normals
        self._contact_flag = bool(points)
        return self._contact_flag

    def front_clearance(self, half_angle_deg: float = 30.0) -> float:
        """Distancia (m) al obstáculo más cercano del cono frontal.

        Se mide sobre el abanico de 36 rayos, que está denso al frente: en el
        cono de ±30° hay 17 rayos separados 3,5°, contra 13 separados 5° del
        anillo uniforme. La distancia viene desde el paragolpes.

        Devuelve `LIDAR_MAX_DIST` si el cono está despejado.
        """
        if not self.fan_meters.size:
            return float(LIDAR_MAX_DIST)
        limit = math.radians(float(half_angle_deg))
        mask = np.abs(self.fan_angles) <= limit
        if not mask.any():
            return float(LIDAR_MAX_DIST)
        return float(self.fan_meters[mask].min())

    def contact_info(self) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
        """Puntos y normales de contacto del último paso (para la GUI)."""
        return list(zip(self._contact_points, self._contact_normals))

    def _count_close_sectors(self, radius: float) -> int:
        """Cuenta cuántos lados distintos están bloqueados a menos de `radius`.

        Usa el LiDAR de 72 rayos ya escaneado: agrupa los rayos consecutivos
        que detectan un obstáculo cercano en sectores angulares. Un callejón
        sin salida típico bloquea 3 sectores (frente, izquierda, derecha).
        """
        close = [float(d) <= radius for d in self.lidar_meters]
        n = len(close)
        if n == 0 or not any(close):
            return 0
        if all(close):
            return 4  # rodeado por completo
        # Romper la circularidad buscando un rayo libre.
        start = close.index(False)
        sectors = 0
        previous = False
        for k in range(n):
            current = close[(start + k) % n]
            if current and not previous:
                sectors += 1
            previous = current
        return sectors

    # ------------------------------------------------------------------ #
    # Reset y step con recompensas múltiples V4
    # ------------------------------------------------------------------ #
    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        self.chunk_mapper = ChunkMapper(cell_size=1.0)
        self._chunks_discovered_before_reset = 0
        # Estado de recompensas V4
        self._idle_steps = 0
        self._move_streak = 0
        self._idle_penalized = False
        self._trap_cooldown = 0
        self._last_pos = None
        self._prev_collision = False
        # Estado de resolución de problemas
        self._contact_flag = False
        self._contact_points = []
        self._contact_normals = []
        self._was_in_contact = False
        self._escape_pending = 0
        self._escape_moved = 0.0
        self._contact_distance = None
        self._escaped_awarded = False
        self._stuck_steps = 0
        self._prev_nearest = LIDAR_MAX_DIST
        self._prev_front_min = LIDAR_MAX_DIST
        obs, info = super().reset(seed=seed, options=options)
        # El reset ya barrió el LiDAR al construir la observación: se deja el
        # abanico en info para que la GUI y los diagnósticos lo vean sin tener
        # que volver a escanear.
        if self._enable_sensors:
            info["fan_meters"] = self.fan_meters.tolist()
            info["front_clearance_m"] = self.front_clearance(FRONT_CONE_DEG)
        return obs, info

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        obs, reward, terminated, truncated, info = super().step(action)
        self._update_chunk_mapper()

        # ── 1) +10 por descubrir chunks nuevos ──
        new_chunks = self._count_new_discovered()
        if new_chunks > 0:
            reward += CHUNK_DISCOVERY_REWARD * new_chunks
            reward += EXPLORATION_BONUS * new_chunks

        # ── 2) -5 por colisión (una vez por evento) ──
        collided = bool(info.get("collision"))
        if collided and not self._prev_collision:
            reward += COLLISION_PENALTY
        self._prev_collision = collided

        # ── 3) Movimiento continuo / quieto ──
        pos, _ = self.p.getBasePositionAndOrientation(self.robot)
        moved = 0.0
        if self._last_pos is not None:
            moved = math.hypot(
                pos[0] - self._last_pos[0], pos[1] - self._last_pos[1]
            )
        self._last_pos = (float(pos[0]), float(pos[1]))

        if moved > MOVE_EPS_M:
            self._idle_steps = 0
            self._idle_penalized = False
            self._stuck_steps = 0
            self._move_streak += 1
            if self._move_streak >= MOVE_STREAK_THRESHOLD:
                reward += MOVE_STREAK_BONUS
                self._move_streak = 0
        else:
            self._move_streak = 0
            self._idle_steps += 1
            self._stuck_steps += 1
            if (
                self._idle_steps >= IDLE_STEPS_THRESHOLD
                and not self._idle_penalized
            ):
                reward += IDLE_PENALTY
                self._idle_penalized = True

        # ── 4) -15 por quedar atrapado (3+ lados bloqueados a <30 cm) ──
        if self._trap_cooldown > 0:
            self._trap_cooldown -= 1
        else:
            sectors = self._count_close_sectors(TRAP_RADIUS)
            if sectors >= TRAP_MIN_OBSTACLES:
                reward += TRAP_PENALTY
                self._trap_cooldown = TRAP_COOLDOWN_STEPS
                info["trapped"] = True
                info["trap_sectors"] = sectors

        # ── 5) Shaping de proximidad, gradual ──
        # Antes era un escalón: -1.0 por paso en cuanto un rayo del cono veía
        # algo a menos de 0.9 m, contra +0.07 por avanzar. La política
        # aprendía a no acercarse a nada. Ahora descuenta proporcional a lo
        # cerca que está, con techo en CLOSE_OBSTACLE_PENALTY.
        sensor_slice = obs[14 : 14 + SENSOR_COUNT]
        if self._enable_sensors:
            front_norms = sensor_slice[self._fan_front_mask]
            max_sensor = float(np.max(front_norms)) if front_norms.size else 0.0
            front_now = self.front_clearance(FRONT_CONE_DEG)
        else:
            max_sensor = 0.0
            front_now = float(self.lidar_max_dist)
        if front_now < CLOSE_OBSTACLE_M:
            closeness = 1.0 - front_now / CLOSE_OBSTACLE_M
            reward += CLOSE_OBSTACLE_PENALTY * closeness
        elif max_sensor < 0.50:
            # Todo el frente está despejado a más de 3 m.
            reward += OBSTACLE_AVOID_BONUS

        # ── 6) Resolución de problemas: contacto, escape y distancia ──
        # Chocar ya no termina el episodio (collision_terminates=False): lo
        # que se premia es salir del atasco, no morir en él.
        contact = self._contact_flag
        nearest = (
            float(self.lidar_meters.min())
            if self._enable_sensors
            else LIDAR_MAX_DIST
        )
        front_min = (
            self.front_clearance(FRONT_CONE_DEG)
            if self._enable_sensors
            else LIDAR_MAX_DIST
        )
        if contact:
            reward += CONTACT_PENALTY

        # Escapar: se recuerda la distancia al obstáculo en el momento del
        # contacto y se premia cuando el robot consigue 8 cm de holgura real.
        if contact:
            if not self._was_in_contact:
                self._contact_distance = nearest
                self._escaped_awarded = False
        elif (
            self._contact_distance is not None
            and not self._escaped_awarded
            and nearest > self._contact_distance + 0.08
        ):
            reward += ESCAPE_BONUS
            self._escaped_awarded = True
            self._contact_distance = None

        if self._enable_sensors:
            if self._prev_nearest < NEAR_OBSTACLE_M:
                if nearest > self._prev_nearest + 0.005:
                    # Ganó distancia libre estando pegado: buena maniobra.
                    reward += CLEARANCE_REWARD * min(
                        1.0, (nearest - self._prev_nearest) / 0.20
                    )
                elif nearest < self._prev_nearest - 0.005:
                    # Se acercó aún más a algo que ya tenía encima.
                    reward += APPROACH_PENALTY
            self._prev_nearest = nearest
            self._prev_front_min = front_min

        self._was_in_contact = contact

        info["chunks_discovered"] = new_chunks
        info["max_sensor"] = max_sensor
        info["sensor_readings"] = (
            sensor_slice.tolist() if self._enable_sensors else []
        )
        info["nearest_obstacle_m"] = nearest
        info["front_clearance_m"] = front_min
        info["fan_meters"] = (
            self.fan_meters.tolist() if self._enable_sensors else []
        )
        info["contact"] = contact
        info["stuck"] = self._stuck_steps >= STUCK_STEPS
        info["free_direction"] = (
            self._free_direction() if self._enable_sensors else (0.0, 0.0)
        )
        return obs, float(reward), bool(terminated), bool(truncated), info

    def _pose(self):
        pos, quat = self.p.getBasePositionAndOrientation(self.robot)
        yaw = float(self.p.getEulerFromQuaternion(quat)[2])
        return type("Pose", (), {"pos": pos, "yaw": yaw})()


# ---------------------------------------------------------------------- #
# Prueba rápida
# ---------------------------------------------------------------------- #
def _quick_test(render_mode: str | None = None) -> None:
    env = WallEEnvV3(render_mode=render_mode, stage=3, obstacle_count=6)
    obs, info = env.reset()
    print("Observación inicial (58D):", np.round(obs, 3), "shape:", obs.shape)
    print("LiDAR 72:", np.round(env.lidar_meters[:8], 2), "...")
    print("Frontales 36:", np.round(obs[14:50], 3))
    print("Resolución:", np.round(obs[50:], 3))
    for _ in range(10):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            break
    env.close()


if __name__ == "__main__":
    _quick_test()
