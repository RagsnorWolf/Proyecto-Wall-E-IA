import * as THREE from "three";

/**
 * Controlador de animación de WALL-E para walle_animated.glb.
 *
 * El GLB no trae esqueleto: son 43 mallas hermanas bajo RootNode. Para que los
 * gestos sean creíbles sin desarmar el modelo construimos una jerarquía virtual
 * de articulaciones y horneamos cada frame con cinemática directa:
 *
 *   torso ── cuello ── ojos
 *     ├── hombro izquierdo ── muñeca (garra)
 *     └── hombro derecho
 *
 * Cada pieza rota alrededor del pivote real de su articulación y las piezas
 * hijas heredan la rotación del padre. Las orugas usan únicamente los tracks
 * del clip original "Scene" (los 29 segmentos ruedan por el bucle) y el resto
 * del cuerpo se anima por separado con anticipación, solapamiento y
 * asentamiento para que los gestos se sientan mecánicos pero vivos.
 */

const TAU = Math.PI * 2;
const IDENTITY = new THREE.Quaternion();
// Centro local Z del cristal de los ojos (ya multiplicado por la escala 100
// del nodo). Se usa para que el parpadeo cierre sobre el centro del cristal.
const LENS_CENTER_OFFSET = 0.0955;

const clamp01 = (value) => Math.min(1, Math.max(0, value));

const smoothstep = (edge0, edge1, x) => {
  const t = clamp01((x - edge0) / (edge1 - edge0));
  return t * t * (3 - 2 * t);
};

// Ventana suave: 0 fuera de [a,d], 1 entre b y c.
const window01 = (x, a, b, c, d) =>
  smoothstep(a, b, x) * (1 - smoothstep(c, d, x));

const bell = (x, center, width) => {
  const z = (x - center) / width;
  return Math.exp(-z * z);
};

const _euler = new THREE.Euler(0, 0, 0, "YXZ");
const eulerQuat = (x = 0, y = 0, z = 0) =>
  new THREE.Quaternion().setFromEuler(_euler.set(x, y, z, "YXZ"));

export class WallEAnimationController {
  constructor(gltf, root, onActionComplete = () => {}) {
    this.root = root;
    this.onActionComplete = onActionComplete;

    if (!this.root.name) this.root.name = "WALLERoot";

    this.mixer = new THREE.AnimationMixer(this.root);
    this.nodes = this._findNodes(this.root);
    this.restPose = new Map();
    this._captureRestPose(this.root);
    this._buildRig();

    this.clips = {
      idle: this._buildBodyClip("WALLE_Idle", 8, (t) => this._idlePose(t), 24),
      wave: this._buildBodyClip("WALLE_Wave", 3.6, (t) => this._wavePose(t), 30),
      walk: this._buildBodyClip("WALLE_WalkBody", 1.2, (t) => this._walkPose(t), 30),
      dance: this._buildBodyClip("WALLE_Dance", 6.4, (t) => this._dancePose(t), 30),
    };

    this.bodyActions = new Map();
    for (const [name, clip] of Object.entries(this.clips)) {
      const action = this.mixer.clipAction(clip);
      const once = name === "wave";
      action.setLoop(
        once ? THREE.LoopOnce : THREE.LoopRepeat,
        once ? 1 : Infinity
      );
      action.clampWhenFinished = once;
      this.bodyActions.set(name, action);
    }

    // El clip de orugas se reproduce siempre con peso 1, pero su velocidad se
    // amortigua a 0 cuando WALL-E no camina. Así las orugas quedan congeladas
    // en una pose ensamblada en lugar de volver de golpe a la pose de reposo.
    this.treadClip = this._createTreadClip(gltf);
    this.treadAction = this.treadClip
      ? this.mixer.clipAction(this.treadClip)
      : null;
    if (this.treadAction) {
      this.treadAction.setLoop(THREE.LoopRepeat, Infinity);
      this.treadAction.setEffectiveWeight(1);
      this.treadAction.setEffectiveTimeScale(0);
      this.treadAction.play();
    }

    this.activeState = null;
    this.activeBodyAction = null;
    this.fadingActions = new Set();
    this.treadSpeed = 0;
    this.treadTarget = 0;

    this._onFinished = (event) => {
      if (
        this.activeState === "wave" &&
        event.action === this.activeBodyAction
      ) {
        this.setState("idle");
        this.onActionComplete?.();
      }
    };
    this.mixer.addEventListener("finished", this._onFinished);

    console.log("[WALL-E] Rig articulado:", {
      joints: Object.keys(this.pivots),
      bodyPieces: this.chains.reduce((n, chain) => n + chain.pieces.length, 0),
      clips: Object.keys(this.clips),
      treadTracks: this.treadClip?.tracks.length ?? 0,
    });

    this.setState("idle", { immediate: true });
  }

  // -----------------------------------------------------------------------
  // Búsqueda de nodos y construcción del rig virtual
  // -----------------------------------------------------------------------

  _findNodes(scene) {
    const nodes = { treads: [], gears: [] };

    scene.traverse((obj) => {
      if (!obj.isObject3D || !obj.name) return;
      const name = obj.name.toLowerCase();

      if (name === "body_low") nodes.body = obj;
      else if (name === "back_low") nodes.back = obj;
      else if (name === "base_low") nodes.base = obj;
      else if (name === "neck_low") nodes.neck = obj;
      else if (name === "eyes_low") nodes.eyes = obj;
      else if (name === "eyes_low001") nodes.eyesLens = obj;
      else if (name === "hand_low") nodes.armL = obj;
      else if (name === "hand_low001") nodes.armR = obj;
      else if (name === "hand_low002") nodes.clawL = obj;
      else if (/^track_low\d*$/.test(name)) nodes.treads.push(obj);
      else if (/^trackgears\d+_low$/.test(name)) nodes.gears.push(obj);
    });

    return nodes;
  }

  _captureRestPose(object) {
    object.traverse((node) => {
      this.restPose.set(node, {
        position: node.position.clone(),
        quaternion: node.quaternion.clone(),
        scale: node.scale.clone(),
      });
    });
  }

  _buildRig() {
    const rest = (node) => this.restPose.get(node);

    const required = [
      "body",
      "neck",
      "eyes",
      "eyesLens",
      "armL",
      "armR",
      "clawL",
    ];
    const missing = required.filter((key) => !this.nodes[key]);
    if (missing.length) {
      console.warn("[WALL-E] Faltan piezas del rig:", missing);
    }

    this.pivots = {
      // Bisagra del torso sobre la base: permite balanceo y giro sin separar
      // el cuerpo de las orugas.
      torso: new THREE.Vector3(0, 0.84, 0),
      neck: rest(this.nodes.neck)?.position.clone() ?? new THREE.Vector3(),
      eye: rest(this.nodes.eyes)?.position.clone() ?? new THREE.Vector3(),
      shoulderL: rest(this.nodes.armL)?.position.clone() ?? new THREE.Vector3(),
      wristL: rest(this.nodes.clawL)?.position.clone() ?? new THREE.Vector3(),
      shoulderR: rest(this.nodes.armR)?.position.clone() ?? new THREE.Vector3(),
    };

    this.chains = [
      {
        pieces: [this.nodes.body, this.nodes.back].filter(Boolean),
        joints: ["torso"],
      },
      {
        pieces: [this.nodes.neck].filter(Boolean),
        joints: ["torso", "neck"],
      },
      {
        pieces: [this.nodes.eyes].filter(Boolean),
        joints: ["torso", "neck", "eye"],
      },
      {
        pieces: [this.nodes.eyesLens].filter(Boolean),
        joints: ["torso", "neck", "eye"],
        lens: true,
      },
      {
        pieces: [this.nodes.armL].filter(Boolean),
        joints: ["torso", "shoulderL"],
      },
      {
        pieces: [this.nodes.clawL].filter(Boolean),
        joints: ["torso", "shoulderL", "wristL"],
      },
      {
        pieces: [this.nodes.armR].filter(Boolean),
        joints: ["torso", "shoulderR"],
      },
    ];
  }

  // -----------------------------------------------------------------------
  // Helpers de tracks
  // -----------------------------------------------------------------------

  _times(duration, fps = 30) {
    const count = Math.max(2, Math.round(duration * fps));
    const times = new Float32Array(count + 1);
    for (let i = 0; i <= count; i++) times[i] = (duration * i) / count;
    return times;
  }

  _createTreadClip(gltf) {
    const original =
      gltf.animations?.find((clip) => clip.name === "Scene") ||
      gltf.animations?.[0];
    if (!original) return null;

    const isTreadTrack = (track) => {
      const target = track.name.split(".")[0];
      return (
        /^track_low\d*$/i.test(target) || /^trackgears\d+_low$/i.test(target)
      );
    };

    const tracks = original.tracks
      .filter(isTreadTrack)
      .map((track) => track.clone());
    if (!tracks.length) return null;

    return new THREE.AnimationClip(
      "WALLE_TreadLoop",
      original.duration,
      tracks
    );
  }

  /**
   * Hornea un clip corporal completo. Cada pieza recibe posición y rotación
   * calculadas con la cadena de articulaciones que le corresponde, de la hija
   * a la padre, para que ninguna pieza se separe durante el gesto.
   */
  _buildBodyClip(name, duration, sample, fps = 30) {
    const times = this._times(duration, fps);
    const count = times.length;
    const pieceData = new Map();

    for (const chain of this.chains) {
      for (const piece of chain.pieces) {
        pieceData.set(piece, {
          chain,
          rest: this.restPose.get(piece),
          position: new Float32Array(count * 3),
          quaternion: new Float32Array(count * 4),
        });
      }
    }

    const rootRest = this.restPose.get(this.root);
    const rootPosition = new Float32Array(count * 3);
    const rootQuaternion = new Float32Array(count * 4);
    const lensData = this.nodes.eyesLens
      ? pieceData.get(this.nodes.eyesLens)
      : null;
    const lensScale = lensData ? new Float32Array(count * 3) : null;

    const tempPosition = new THREE.Vector3();
    const tempQuaternion = new THREE.Quaternion();
    const tempOffset = new THREE.Vector3();
    const jointQuaternions = {
      torso: IDENTITY,
      neck: IDENTITY,
      eye: IDENTITY,
      shoulderL: IDENTITY,
      wristL: IDENTITY,
      shoulderR: IDENTITY,
    };

    for (let frame = 0; frame < count; frame++) {
      const time = times[frame];
      const pose = sample(time, frame);

      jointQuaternions.torso = pose.torso || IDENTITY;
      jointQuaternions.neck = pose.neck || IDENTITY;
      jointQuaternions.eye = pose.eye || IDENTITY;
      jointQuaternions.shoulderL = pose.shoulderL || IDENTITY;
      jointQuaternions.wristL = pose.wristL || IDENTITY;
      jointQuaternions.shoulderR = pose.shoulderR || IDENTITY;

      const blink = pose.blink ?? 1;

      for (const [piece, data] of pieceData) {
        tempPosition.copy(data.rest.position);

        if (data.chain.lens) {
          tempOffset.set(0, 0, (1 - blink) * LENS_CENTER_OFFSET);
          tempPosition.add(
            tempOffset.applyQuaternion(data.rest.quaternion)
          );
        }

        tempQuaternion.copy(data.rest.quaternion);

        for (const jointName of data.chain.joints) {
          const rotation = jointQuaternions[jointName];
          const pivot = this.pivots[jointName];
          tempPosition.sub(pivot).applyQuaternion(rotation).add(pivot);
          tempQuaternion.premultiply(rotation);
        }

        const p = frame * 3;
        const q = frame * 4;
        data.position[p] = tempPosition.x;
        data.position[p + 1] = tempPosition.y;
        data.position[p + 2] = tempPosition.z;
        data.quaternion[q] = tempQuaternion.x;
        data.quaternion[q + 1] = tempQuaternion.y;
        data.quaternion[q + 2] = tempQuaternion.z;
        data.quaternion[q + 3] = tempQuaternion.w;
      }

      const offset = pose.rootOffset || { x: 0, y: 0, z: 0 };
      const p = frame * 3;
      rootPosition[p] = rootRest.position.x + (offset.x || 0);
      rootPosition[p + 1] = rootRest.position.y + (offset.y || 0);
      rootPosition[p + 2] = rootRest.position.z + (offset.z || 0);

      const delta = pose.rootYaw
        ? eulerQuat(0, pose.rootYaw, 0)
        : IDENTITY;
      tempQuaternion.copy(rootRest.quaternion).multiply(delta);
      const q = frame * 4;
      rootQuaternion[q] = tempQuaternion.x;
      rootQuaternion[q + 1] = tempQuaternion.y;
      rootQuaternion[q + 2] = tempQuaternion.z;
      rootQuaternion[q + 3] = tempQuaternion.w;

      if (lensScale) {
        const s = frame * 3;
        lensScale[s] = lensData.rest.scale.x;
        lensScale[s + 1] = lensData.rest.scale.y;
        lensScale[s + 2] = lensData.rest.scale.z * blink;
      }
    }

    const tracks = [];
    for (const [piece, data] of pieceData) {
      tracks.push(
        new THREE.VectorKeyframeTrack(
          `${piece.name}.position`,
          times,
          data.position
        )
      );
      tracks.push(
        new THREE.QuaternionKeyframeTrack(
          `${piece.name}.quaternion`,
          times,
          data.quaternion
        )
      );
    }

    if (lensScale) {
      tracks.push(
        new THREE.VectorKeyframeTrack(
          `${this.nodes.eyesLens.name}.scale`,
          times,
          lensScale
        )
      );
    }

    tracks.push(
      new THREE.VectorKeyframeTrack(
        `${this.root.name}.position`,
        times,
        rootPosition
      )
    );
    tracks.push(
      new THREE.QuaternionKeyframeTrack(
        `${this.root.name}.quaternion`,
        times,
        rootQuaternion
      )
    );

    return new THREE.AnimationClip(name, duration, tracks);
  }

  // -----------------------------------------------------------------------
  // Poses
  // -----------------------------------------------------------------------

  /**
   * Reposo vivo: respiración, cambio de peso, miradas y parpadeos. Los gestos
   * son pequeños para que el cuerpo no se separe de la base.
   */
  _idlePose(t) {
    const breath = Math.sin((TAU * t) / 4);
    const breath2 = Math.sin((TAU * t) / 4 + 1.1);
    const sway = Math.sin((TAU * t) / 8);
    const sway2 = Math.sin((TAU * t) / 8 + 0.8);

    const glance =
      -0.22 * window01(t, 1.0, 1.35, 2.05, 2.4) +
      0.26 * window01(t, 3.35, 3.7, 4.45, 4.8) +
      0.1 * window01(t, 5.9, 6.2, 6.7, 7.0);

    const lookUp = 0.1 * window01(t, 6.15, 6.45, 6.9, 7.2);

    const blink =
      1 -
      0.88 *
        Math.min(
          1,
          bell(t, 0.95, 0.055) +
            bell(t, 3.15, 0.055) +
            bell(t, 5.55, 0.055) +
            bell(t, 7.35, 0.055)
        );

    // Pequeño espasmo de la garra, como un servo que corrige posición.
    const clawTwitch =
      0.1 * (bell(t, 2.55, 0.12) - bell(t, 6.05, 0.12));

    return {
      torso: eulerQuat(
        0.01 * breath + 0.004 * sway,
        0.018 * sway2,
        0.016 * sway
      ),
      neck: eulerQuat(
        -0.012 * breath,
        0.55 * glance,
        -0.012 * sway + 0.03 * glance
      ),
      eye: eulerQuat(-0.5 * lookUp, 0.35 * glance, 0.01 * sway),
      shoulderL: eulerQuat(
        0.008 * breath2,
        0.006 * sway2,
        0.014 * sway2
      ),
      wristL: eulerQuat(clawTwitch, 0.01 * sway2, 0.018 * sway2),
      shoulderR: eulerQuat(
        0.014 * breath2,
        -0.006 * sway2,
        -0.01 * sway
      ),
      rootOffset: { x: 0, y: 0, z: 0 },
      rootYaw: 0,
      blink,
    };
  }

  /**
   * Saludo: anticipación, subida con overshoot, tres vaivenes con la garra
   * retrasada respecto del hombro, inclinación de cabeza y asentamiento.
   */
  _wavePose(t) {
    const raise = window01(t, 0.15, 0.55, 3.05, 3.5);
    const waveEnv = window01(t, 0.55, 0.85, 2.75, 3.15);
    const antic = window01(t, 0.0, 0.1, 0.24, 0.38);

    const phase = TAU * 2.8 * (t - 0.75);
    const wave = Math.sin(phase) * waveEnv;
    const waveLag = Math.sin(phase - 0.7) * waveEnv;
    const waveLag2 = Math.sin(phase - 1.25) * waveEnv;

    const blink =
      1 -
      0.88 *
        Math.min(1, bell(t, 0.55, 0.05) + bell(t, 3.05, 0.05));
    const squint = 0.16 * window01(t, 0.95, 1.15, 2.55, 2.75);
    const lens = blink * (1 - squint);

    return {
      torso: eulerQuat(
        0.015 * raise + 0.006 * Math.sin(phase - 0.5) * waveEnv,
        0.045 * raise + 0.012 * wave,
        -0.022 * antic + 0.03 * raise + 0.01 * wave
      ),
      neck: eulerQuat(
        -0.015 * raise + 0.01 * Math.sin(phase - 0.8) * waveEnv,
        0.12 * raise + 0.02 * wave,
        0.05 * raise + 0.015 * wave
      ),
      eye: eulerQuat(
        0.02 * raise + 0.01 * Math.sin(phase - 1.0) * waveEnv,
        0.05 * raise + 0.01 * wave,
        0.02 * raise
      ),
      shoulderL: eulerQuat(
        0.06 * raise + 0.03 * wave,
        0.05 * Math.sin(phase - 0.35) * waveEnv,
        0.12 * raise + 0.11 * wave
      ),
      wristL: eulerQuat(
        0.16 * waveLag2,
        0.14 * Math.sin(phase - 0.95) * waveEnv,
        -0.26 * waveLag
      ),
      shoulderR: eulerQuat(
        -0.035 * raise + 0.025 * wave,
        -0.02 * raise,
        -0.035 * raise
      ),
      rootOffset: { x: 0, y: 0, z: 0 },
      rootYaw: 0.018 * raise,
      blink: lens,
    };
  }

  /**
   * Caminar: las orugas las mueve el clip original; acá va el balanceo del
   * torso, el contragolpe de brazos, el rebote y la cabeza estabilizada.
   */
  _walkPose(t) {
    const phase = (TAU * t) / 1.2;
    const step = Math.sin(phase);
    const stepLag = Math.sin(phase - 0.55);
    const double = Math.sin(2 * phase);

    return {
      torso: eulerQuat(
        0.018 + 0.008 * double,
        0.045 * Math.sin(phase + 0.45),
        0.028 * step
      ),
      neck: eulerQuat(
        -0.014 - 0.006 * double,
        -0.03 * Math.sin(phase + 0.45),
        -0.018 * step
      ),
      eye: eulerQuat(
        0.01 * double,
        0.025 * Math.sin(phase + 0.9),
        0.008 * step
      ),
      shoulderL: eulerQuat(
        0.065 * Math.sin(phase + 0.25),
        0.015 * stepLag,
        0.035 * step
      ),
      wristL: eulerQuat(
        -0.055 * Math.sin(phase + 0.75),
        0.015 * stepLag,
        -0.045 * stepLag
      ),
      shoulderR: eulerQuat(
        -0.15 * step,
        -0.02 * step,
        -0.02 * step
      ),
      rootOffset: { x: 0, y: 0, z: 0 },
      rootYaw: 0,
      blink: 1,
    };
  }

  /**
   * Baile en cuatro frases de dos beats: balanceo lateral, bombeo de brazos,
   * giro de torso y final con ambos brazos arriba. Las frases empiezan y
   * terminan en cero para que el loop sea continuo.
   */
  _dancePose(t) {
    const u1 = clamp01(t / 1.6);
    const u2 = clamp01((t - 1.6) / 1.6);
    const u3 = clamp01((t - 3.2) / 1.6);
    const u4 = clamp01((t - 4.8) / 1.6);

    const e1 = window01(t, 0.0, 0.22, 1.38, 1.6);
    const e2 = window01(t, 1.6, 1.82, 2.98, 3.2);
    const e3 = window01(t, 3.2, 3.42, 4.58, 4.8);
    const e4 = window01(t, 4.8, 5.02, 6.18, 6.4);

    const s1 = Math.sin(TAU * 2 * u1) * e1;
    const s2 = Math.sin(TAU * 3 * u2) * e2;
    const s2b = Math.sin(TAU * 3 * u2 - 0.7) * e2;
    const s3 = Math.sin(TAU * 2 * u3) * e3;
    const s4 = Math.sin(TAU * 3 * u4) * e4;
    const s4b = Math.sin(TAU * 3 * u4 - 0.7) * e4;

    const bounce = 0.5 - 0.5 * Math.cos((TAU * 4 * t) / 6.4);

    const blink =
      1 -
      0.88 * Math.min(1, bell(t, 1.5, 0.05) + bell(t, 4.7, 0.05));

    return {
      torso: eulerQuat(
        0.01 * s1 - 0.012 * s2 + 0.006 * s3 - 0.012 * s4 + 0.008 * bounce,
        0.04 * s1 + 0.03 * s2 + 0.08 * s3 + 0.04 * s4,
        0.012 * s1 + 0.008 * s2 + 0.01 * s3 + 0.008 * s4
      ),
      neck: eulerQuat(
        0.015 * s2 - 0.02 * s4 + 0.006 * bounce,
        -0.05 * s1 - 0.16 * s3 + 0.04 * s4,
        -0.02 * s1 + 0.03 * s3 + 0.02 * s4
      ),
      eye: eulerQuat(
        -0.03 * s2 + 0.02 * s4,
        0.05 * s1 + 0.08 * s3,
        -0.01 * s1
      ),
      shoulderL: eulerQuat(
        -0.04 * s1 - 0.2 * s2 - 0.06 * s3 - 0.12 * e4 + 0.04 * s4,
        0.04 * s1 + 0.06 * s3 + 0.04 * s4,
        0.08 * s1 + 0.05 * s2 + 0.14 * s3 + 0.2 * e4 + 0.05 * s4
      ),
      wristL: eulerQuat(
        0.1 * s2b + 0.08 * s4b,
        0.05 * s1 + 0.08 * s3 + 0.05 * s4,
        -0.18 * s2b + 0.1 * s4b
      ),
      shoulderR: eulerQuat(
        0.04 * s1 + 0.18 * s2 + 0.05 * s3 + 0.1 * e4 - 0.03 * s4,
        -0.04 * s1 - 0.06 * s3,
        -0.06 * s1 - 0.04 * s2 - 0.13 * s3 - 0.18 * e4 - 0.04 * s4
      ),
      rootOffset: {
        x: 0.07 * s1 + 0.03 * s3,
        y: 0,
        z: 0,
      },
      rootYaw: 0.16 * s1 + 0.1 * s2 + 0.22 * s3 + 0.12 * s4,
      blink,
    };
  }

  // -----------------------------------------------------------------------
  // API pública
  // -----------------------------------------------------------------------

  setState(name, { immediate = false } = {}) {
    const key = String(name ?? "").toLowerCase();
    const nextAction = this.bodyActions.get(key);

    if (!nextAction) {
      console.warn(
        `[WALL-E] Acción '${name}' no encontrada. Disponibles:`,
        [...this.bodyActions.keys()]
      );
      return false;
    }

    const oneShot = key === "wave";

    if (this.activeState === key && !oneShot) {
      this.treadTarget = key === "walk" ? 1 : 0;
      return true;
    }

    const fade = immediate ? 0 : 0.3;
    const previous = this.activeBodyAction;

    if (previous && previous !== nextAction) {
      if (fade > 0) {
        previous.fadeOut(fade);
        this.fadingActions.add(previous);
      } else {
        previous.stop();
      }
    }

    // Si la acción estaba desvaneciéndose, vuelve a ser la activa.
    this.fadingActions.delete(nextAction);

    nextAction.reset();
    nextAction.setLoop(
      oneShot ? THREE.LoopOnce : THREE.LoopRepeat,
      oneShot ? 1 : Infinity
    );
    nextAction.clampWhenFinished = oneShot;
    nextAction.setEffectiveTimeScale(1);
    nextAction.setEffectiveWeight(1);
    if (fade > 0) nextAction.fadeIn(fade);
    nextAction.play();

    this.activeBodyAction = nextAction;
    this.activeState = key;
    this.treadTarget = key === "walk" ? 1 : 0;

    return true;
  }

  update(deltaTime) {
    const dt = Math.min(Math.max(deltaTime, 0), 0.05);

    // Las orugas aceleran y frenan con inercia en lugar de cortar en seco.
    this.treadSpeed = THREE.MathUtils.damp(
      this.treadSpeed,
      this.treadTarget,
      5,
      dt
    );
    if (this.treadAction) {
      this.treadAction.setEffectiveTimeScale(this.treadSpeed);
    }

    this.mixer.update(dt);

    for (const action of this.fadingActions) {
      if (action.getEffectiveWeight() <= 0.001) {
        action.stop();
        this.fadingActions.delete(action);
      }
    }
  }

  _resetPose() {
    for (const [node, rest] of this.restPose) {
      node.position.copy(rest.position);
      node.quaternion.copy(rest.quaternion);
      node.scale.copy(rest.scale);
    }
    this.root.updateMatrixWorld(true);
  }

  dispose() {
    this.mixer.removeEventListener("finished", this._onFinished);
    this.mixer.stopAllAction();
    this.bodyActions.clear();
    this.fadingActions.clear();
    this.treadAction = null;
    this._resetPose();
  }
}
