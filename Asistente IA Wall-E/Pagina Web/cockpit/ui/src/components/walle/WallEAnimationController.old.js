import * as THREE from "three";

/**
 * Controlador de animación de WALL-E para walle_animated.glb.
 *
 * El GLB no tiene un rig de huesos: son 43 mallas hermanas bajo RootNode.
 * Por eso cada animación se construye horneando la transformación de reposo
 * de cada pieza y rotándola alrededor del pivote correcto. Así el robot se
 * mantiene ensamblado mientras saluda, camina o baila.
 *
 * El clip original "Scene" (10.4 s) ya contiene el ciclo de las orugas
 * (los 29 segmentos de track_low ruedan por el bucle) y se usa para caminar.
 */

const X_AXIS = new THREE.Vector3(1, 0, 0);
const Y_AXIS = new THREE.Vector3(0, 1, 0);
const Z_AXIS = new THREE.Vector3(0, 0, 1);

const smoothstep = (edge0, edge1, x) => {
  const t = Math.min(Math.max((x - edge0) / (edge1 - edge0), 0), 1);
  return t * t * (3 - 2 * t);
};

export class WallEAnimationController {
  constructor(gltf, root, onActionComplete = () => {}) {
    this.root = root;
    this.onActionComplete = onActionComplete;

    if (!this.root.name) this.root.name = "WALLERoot";

    this.mixer = new THREE.AnimationMixer(this.root);
    this.nodes = this._findNodes(this.root);
    this.restPose = new Map();
    this._captureRestPose(this.root);

    console.log("[WALL-E] Nodos encontrados:", {
      body: !!this.nodes.body,
      neck: !!this.nodes.neck,
      eyes: !!this.nodes.eyes,
      armL: this.nodes.armL?.name,
      clawL: this.nodes.clawL?.name,
      armR: this.nodes.armR?.name,
      treads: this.nodes.treads.length,
      gears: this.nodes.gears.length,
      clips: gltf.animations?.map((c) => c.name),
    });

    this.clips = this._createClips(gltf);
    this.actions = new Map();

    for (const [name, clip] of Object.entries(this.clips)) {
      if (!clip) continue;
      const action = this.mixer.clipAction(clip);
      if (name === "wave") {
        action.setLoop(THREE.LoopOnce, 1);
        action.clampWhenFinished = true;
      } else {
        action.setLoop(THREE.LoopRepeat, Infinity);
      }
      this.actions.set(name, action);
    }

    this.activeActionName = null;
    this.activeAction = null;

    this._onFinished = (event) => {
      if (this.activeActionName === "wave" && event.action === this.activeAction) {
        this.setState("idle");
        this.onActionComplete?.();
      }
    };
    this.mixer.addEventListener("finished", this._onFinished);

    this.setState("idle");
  }

  // -----------------------------------------------------------------------
  // Búsqueda de nodos
  // -----------------------------------------------------------------------

  _findNodes(scene) {
    const nodes = { treads: [], gears: [], headParts: [] };

    scene.traverse((obj) => {
      if (!obj.isObject3D || !obj.name) return;
      const n = obj.name.toLowerCase();

      if (n === "body_low") nodes.body = obj;
      else if (n === "neck_low") nodes.neck = obj;
      else if (n === "eyes_low") nodes.eyes = obj;
      else if (n === "eyes_low001") nodes.eyesLens = obj;
      else if (n === "hand_low") nodes.armL = obj; // brazo levantado (x negativa)
      else if (n === "hand_low001") nodes.armR = obj; // brazo bajo (x positiva)
      else if (n === "hand_low002") nodes.clawL = obj; // garra del brazo levantado
      else if (/^track_low\d*$/.test(n)) nodes.treads.push(obj);
      else if (/^trackgears\d+_low$/.test(n)) nodes.gears.push(obj);
    });

    nodes.headParts = [nodes.neck, nodes.eyes, nodes.eyesLens].filter(Boolean);
    nodes.leftArmParts = [nodes.armL, nodes.clawL].filter(Boolean);
    nodes.rightArmParts = [nodes.armR].filter(Boolean);

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

  _resetPose() {
    for (const [node, rest] of this.restPose) {
      node.position.copy(rest.position);
      node.quaternion.copy(rest.quaternion);
      node.scale.copy(rest.scale);
    }
    this.root.updateMatrixWorld(true);
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

  /**
   * Rota un grupo de piezas rígidamente alrededor del pivote de `pivotNode`.
   * `getParentQuat(t)` debe devolver la rotación en espacio del padre común
   * (RootNode). Así la garra, la cabeza, etc. acompañan al brazo sin separarse.
   */
  _groupRotationTracks(pieces, pivotNode, times, getParentQuat) {
    const tracks = [];
    const pivotRest = this.restPose.get(pivotNode);
    if (!pivotRest || pieces.length === 0) return tracks;

    const pivotPos = pivotRest.position;
    const v = new THREE.Vector3();
    const q = new THREE.Quaternion();

    for (const piece of pieces) {
      const rest = this.restPose.get(piece);
      if (!rest) continue;

      const posValues = new Float32Array(times.length * 3);
      const quatValues = new Float32Array(times.length * 4);

      for (let i = 0; i < times.length; i++) {
        const R = getParentQuat(times[i], i);

        v.copy(rest.position).sub(pivotPos).applyQuaternion(R).add(pivotPos);
        posValues[i * 3] = v.x;
        posValues[i * 3 + 1] = v.y;
        posValues[i * 3 + 2] = v.z;

        q.copy(R).multiply(rest.quaternion);
        quatValues[i * 4] = q.x;
        quatValues[i * 4 + 1] = q.y;
        quatValues[i * 4 + 2] = q.z;
        quatValues[i * 4 + 3] = q.w;
      }

      tracks.push(
        new THREE.VectorKeyframeTrack(`${piece.name}.position`, times, posValues)
      );
      tracks.push(
        new THREE.QuaternionKeyframeTrack(
          `${piece.name}.quaternion`,
          times,
          quatValues
        )
      );
    }

    return tracks;
  }

  _rootPositionTrack(times, getOffset) {
    const rest = this.restPose.get(this.root);
    if (!rest) return null;
    const values = new Float32Array(times.length * 3);
    for (let i = 0; i < times.length; i++) {
      const off = getOffset(times[i], i);
      values[i * 3] = rest.position.x + off.x;
      values[i * 3 + 1] = rest.position.y + off.y;
      values[i * 3 + 2] = rest.position.z + off.z;
    }
    return new THREE.VectorKeyframeTrack(
      `${this.root.name}.position`,
      times,
      values
    );
  }

  _rootQuaternionTrack(times, getDeltaQuat) {
    const rest = this.restPose.get(this.root);
    if (!rest) return null;
    const values = new Float32Array(times.length * 4);
    const q = new THREE.Quaternion();
    for (let i = 0; i < times.length; i++) {
      q.copy(rest.quaternion).multiply(getDeltaQuat(times[i], i));
      values[i * 4] = q.x;
      values[i * 4 + 1] = q.y;
      values[i * 4 + 2] = q.z;
      values[i * 4 + 3] = q.w;
    }
    return new THREE.QuaternionKeyframeTrack(
      `${this.root.name}.quaternion`,
      times,
      values
    );
  }

  // -----------------------------------------------------------------------
  // Clips programáticos
  // -----------------------------------------------------------------------

  _createClips(gltf) {
    const clips = {};

    // ---- IDLE: respiración muy leve de todo el robot -------------------
    {
      const duration = 4;
      const times = this._times(duration, 20);
      const tracks = [];
      const pos = this._rootPositionTrack(times, (t) => ({
        x: 0,
        y: Math.sin((Math.PI * 2 * t) / duration) * 0.012,
        z: 0,
      }));
      if (pos) tracks.push(pos);
      clips.idle = new THREE.AnimationClip("WALLE_Idle", duration, tracks);
    }

    // ---- WAVE: brazo izquierdo (el que está levantado) saluda ----------
    {
      const duration = 3;
      const times = this._times(duration, 30);
      const tracks = [];

      const getRotation = (t) => {
        const raise =
          smoothstep(0, 0.45, t) * (1 - smoothstep(2.35, 2.95, t));
        const waveEnv =
          smoothstep(0.4, 0.75, t) * (1 - smoothstep(2.15, 2.55, t));
        // El brazo ya descansa levantado; un levante suave + vaivén lateral
        // amplio se lee como saludo sin salirse del encuadre.
        const lift = -0.15 * raise;
        const side =
          Math.sin((t - 0.4) * Math.PI * 2 * 2.2) * 0.46 * waveEnv;

        const qx = new THREE.Quaternion().setFromAxisAngle(X_AXIS, lift);
        const qy = new THREE.Quaternion().setFromAxisAngle(Y_AXIS, side);
        return qy.multiply(qx);
      };

      tracks.push(
        ...this._groupRotationTracks(
          this.nodes.leftArmParts,
          this.nodes.armL,
          times,
          getRotation
        )
      );

      // Inclinación amable de la cabeza hacia el brazo que saluda.
      if (this.nodes.headParts.length) {
        const headTimes = this._times(duration, 20);
        tracks.push(
          ...this._groupRotationTracks(
            this.nodes.headParts,
            this.nodes.neck,
            headTimes,
            (t) => {
              const env =
                smoothstep(0.2, 0.8, t) * (1 - smoothstep(2.2, 2.8, t));
              return new THREE.Quaternion().setFromAxisAngle(
                Z_AXIS,
                0.08 * env
              );
            }
          )
        );
      }

      clips.wave = new THREE.AnimationClip("WALLE_Wave", duration, tracks);
    }

    // ---- WALK: clip original "Scene" (orugas rodando) ------------------
    {
      const original =
        gltf.animations?.find((clip) => clip.name === "Scene") ||
        gltf.animations?.[0];

      if (original) {
        clips.walk = original;
      } else {
        // Respaldo: balanceo suave si el GLB no trae clip.
        const duration = 4;
        const times = this._times(duration, 20);
        const tracks = [];
        const pos = this._rootPositionTrack(times, (t) => ({
          x: 0,
          y: Math.abs(Math.sin((Math.PI * 2 * t) / duration)) * 0.02,
          z: 0,
        }));
        if (pos) tracks.push(pos);
        clips.walk = new THREE.AnimationClip("WALLE_Walk", duration, tracks);
      }
    }

    // ---- DANCE: giro del cuerpo, brazos alternos y cabeza --------------
    {
      const duration = 5;
      const times = this._times(duration, 30);
      const tracks = [];

      const pos = this._rootPositionTrack(times, (t) => ({
        x: 0,
        y: Math.abs(Math.sin((Math.PI * 4 * t) / duration)) * 0.05,
        z: 0,
      }));
      if (pos) tracks.push(pos);

      const quat = this._rootQuaternionTrack(times, (t) =>
        new THREE.Quaternion().setFromAxisAngle(
          Y_AXIS,
          Math.sin((Math.PI * 2 * t) / duration) * 0.38
        )
      );
      if (quat) tracks.push(quat);

      const swing = (t) => Math.sin((Math.PI * 4 * t) / duration);

      if (this.nodes.leftArmParts.length) {
        tracks.push(
          ...this._groupRotationTracks(
            this.nodes.leftArmParts,
            this.nodes.armL,
            times,
            (t) => {
              const qx = new THREE.Quaternion().setFromAxisAngle(
                X_AXIS,
                -0.25 + swing(t) * 0.4
              );
              const qy = new THREE.Quaternion().setFromAxisAngle(
                Y_AXIS,
                swing(t) * 0.12
              );
              return qy.multiply(qx);
            }
          )
        );
      }

      if (this.nodes.rightArmParts.length) {
        tracks.push(
          ...this._groupRotationTracks(
            this.nodes.rightArmParts,
            this.nodes.armR,
            times,
            (t) => {
              const qx = new THREE.Quaternion().setFromAxisAngle(
                X_AXIS,
                -0.25 - swing(t) * 0.4
              );
              const qy = new THREE.Quaternion().setFromAxisAngle(
                Y_AXIS,
                -swing(t) * 0.12
              );
              return qy.multiply(qx);
            }
          )
        );
      }

      if (this.nodes.headParts.length) {
        tracks.push(
          ...this._groupRotationTracks(
            this.nodes.headParts,
            this.nodes.neck,
            times,
            (t) => {
              const qz = new THREE.Quaternion().setFromAxisAngle(
                Z_AXIS,
                Math.sin((Math.PI * 4 * t) / duration) * 0.12
              );
              const qy = new THREE.Quaternion().setFromAxisAngle(
                Y_AXIS,
                Math.sin((Math.PI * 2 * t) / duration) * 0.15
              );
              return qy.multiply(qz);
            }
          )
        );
      }

      clips.dance = new THREE.AnimationClip("WALLE_Dance", duration, tracks);
    }

    return clips;
  }

  // -----------------------------------------------------------------------
  // API pública
  // -----------------------------------------------------------------------

  setState(name) {
    const key = String(name ?? "").toLowerCase();
    const action = this.actions.get(key);
    if (!action) {
      console.warn(
        `[WALL-E] Acción '${name}' no encontrada. Disponibles:`,
        [...this.actions.keys()]
      );
      return false;
    }

    this.mixer.stopAllAction();
    this._resetPose();

    this.activeActionName = key;
    this.activeAction = action;

    action.reset();
    action.setEffectiveWeight(1);
    action.setEffectiveTimeScale(1);
    action.play();

    return true;
  }

  update(deltaTime) {
    const dt = Math.min(Math.max(deltaTime, 0), 0.05);
    this.mixer.update(dt);
  }

  dispose() {
    this.mixer.removeEventListener("finished", this._onFinished);
    this.mixer.stopAllAction();
    this.actions.clear();
    this._resetPose();
  }
}
