import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import {
  EffectComposer,
} from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { WallEAnimationController } from "./WallEAnimationController";

export const WALLE_MODELS = [
  {
    id: "animado",
    label: "WALL·E animado",
    files: ["walle_animated.glb"],
  },
];

export const DEFAULT_WALLE_MODEL = "animado";

const MODEL_BASE = `${import.meta.env.BASE_URL}models/`;
const MODEL_HEIGHT = 2.4;
const MODEL_YAW = 0;

const MOOD_STYLES = {
  tranquilo: { accent: 0xb3d9ff, glow: 1.0, exposure: 1.0 },
  curioso: { accent: 0x7ef0e2, glow: 1.2, exposure: 1.05 },
  contento: { accent: 0xffd166, glow: 1.35, exposure: 1.1 },
  pensando: { accent: 0xb388ff, glow: 0.9, exposure: 0.95 },
  atento: { accent: 0x4fd1c5, glow: 1.25, exposure: 1.02 },
  asustado: { accent: 0xff6b6b, glow: 1.4, exposure: 1.1 },
  aburrido: { accent: 0x8da0a4, glow: 0.6, exposure: 0.9 },
  cansado: { accent: 0x7f8f8c, glow: 0.55, exposure: 0.85 },
};

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const damp = (current, target, lambda, dt) =>
  THREE.MathUtils.damp(current, target, lambda, dt);

function createDustTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const context = canvas.getContext("2d");
  if (!context) return null;

  const gradient = context.createRadialGradient(32, 32, 0, 32, 32, 32);
  gradient.addColorStop(0, "rgba(255, 236, 200, 0.95)");
  gradient.addColorStop(0.35, "rgba(255, 205, 130, 0.45)");
  gradient.addColorStop(1, "rgba(255, 190, 90, 0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, 64, 64);

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  return texture;
}

function createContactShadowTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const context = canvas.getContext("2d");
  if (!context) return null;

  const gradient = context.createRadialGradient(64, 64, 4, 64, 64, 64);
  gradient.addColorStop(0, "rgba(0, 0, 0, 0.82)");
  gradient.addColorStop(0.42, "rgba(0, 0, 0, 0.38)");
  gradient.addColorStop(0.78, "rgba(0, 0, 0, 0.1)");
  gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, 128, 128);

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  return texture;
}

function disposeObject3D(root) {
  if (!root) return;
  root.removeFromParent();
  const materials = new Set();
  const textures = new Set();
  root.traverse((object) => {
    if (object.geometry) object.geometry.dispose();
    if (!object.material) return;
    const list = Array.isArray(object.material)
      ? object.material
      : [object.material];
    list.forEach((material) => materials.add(material));
  });
  materials.forEach((material) => {
    Object.values(material).forEach((value) => {
      if (value && value.isTexture) textures.add(value);
    });
    material.dispose?.();
  });
  textures.forEach((texture) => texture.dispose());
}

// glTF-Transform agrega sufijos ".001"/".002" a nombres duplicados. Three.js
// interpreta el punto como separador de propiedades y rompe los tracks de
// animación y los lookups por nombre. Los normalizamos al cargar.
function sanitizeDuplicateNodeNames(gltf) {
  const renames = new Map();
  gltf.scene.traverse((node) => {
    if (!node.name) return;
    const match = /^(.*)\.(\d{3})$/.exec(node.name);
    if (!match) return;
    const newName = `${match[1]}${match[2]}`;
    renames.set(node.name, newName);
    node.name = newName;
  });

  if (!renames.size) return;

  gltf.animations.forEach((clip) => {
    clip.tracks.forEach((track) => {
      for (const [oldName, newName] of renames) {
        if (track.name.startsWith(`${oldName}.`)) {
          track.name = `${newName}${track.name.slice(oldName.length)}`;
          break;
        }
      }
    });
  });
}

function frameModel(camera, controls, dimensions = { width: 1.65, height: MODEL_HEIGHT }) {
  const fov = THREE.MathUtils.degToRad(camera.fov);
  const halfHeight = dimensions.height * 0.56;
  const halfWidth = dimensions.width * 0.62;
  const aspect = Math.max(camera.aspect, 0.55);
  const distanceForHeight = halfHeight / Math.tan(fov / 2);
  const distanceForWidth = halfWidth / (Math.tan(fov / 2) * aspect);
  const distance = Math.max(distanceForHeight, distanceForWidth) * 1.22;

  const azimuth = 0.42;
  const elevation = 0.16;
  const target = new THREE.Vector3(0, dimensions.height * 0.5, 0);

  camera.position.set(
    Math.sin(azimuth) * Math.cos(elevation) * distance,
    target.y + Math.sin(elevation) * distance,
    Math.cos(azimuth) * Math.cos(elevation) * distance
  );

  controls.target.copy(target);
  controls.minDistance = distance * 0.52;
  controls.maxDistance = distance * 1.8;
  controls.update();
  controls.saveState();
}

export function WallE3D({
  mood = "tranquilo",
  thinking = false,
  speaking = false,
  action = "idle",
  actionSignal = 0,
  onActionComplete,
  model = DEFAULT_WALLE_MODEL,
  onModelLoaded,
}) {
  const hostRef = useRef(null);
  const controllerRef = useRef(null);
  const lastSignalRef = useRef(0);
  const actionRequestRef = useRef({ action, actionSignal });
  actionRequestRef.current = { action, actionSignal };
  const presentationRef = useRef({ mood, thinking, speaking });
  presentationRef.current = { mood, thinking, speaking };
  const onModelLoadedRef = useRef(onModelLoaded);
  onModelLoadedRef.current = onModelLoaded;
  const onActionCompleteRef = useRef(onActionComplete);
  onActionCompleteRef.current = onActionComplete;
  const [status, setStatus] = useState({
    state: "loading",
    file: null,
    progress: 0,
  });

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
        powerPreference: "high-performance",
      });
    } catch {
      host.classList.add("walle-3d--unsupported");
      setStatus({ state: "error", file: null });
      return undefined;
    }

    let disposed = false;
    let frame = 0;
    let modelRoot = null;
    let emissiveMaterials = [];
    let modelDimensions = { width: 1.65, height: MODEL_HEIGHT };
    let userAdjusted = false;

    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.domElement.setAttribute("aria-hidden", "true");
    renderer.domElement.style.display = "block";
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 80);
    const composer = new EffectComposer(renderer);
    composer.setSize(host.clientWidth || 1, host.clientHeight || 1);
    const renderPass = new RenderPass(scene, camera);
    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(host.clientWidth || 1, host.clientHeight || 1),
      0.32,
      0.35,
      0.9
    );
    // Solo los reflejos muy brillantes (ojos/aristas) florecen; el cuerpo
    // amarillo queda nítido en lugar de convertirse en un blob blanco.
    bloomPass.threshold = 0.9;
    bloomPass.strength = 0.32;
    bloomPass.radius = 0.35;
    composer.addPass(renderPass);
    composer.addPass(bloomPass);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.enablePan = false;
    controls.rotateSpeed = 0.72;
    controls.zoomSpeed = 0.85;
    controls.minPolarAngle = 0.32;
    controls.maxPolarAngle = Math.PI * 0.52;
    controls.target.set(0, MODEL_HEIGHT * 0.48, 0);

    const pmrem = new THREE.PMREMGenerator(renderer);
    const room = new RoomEnvironment();
    const environment = pmrem.fromScene(room, 0.04);
    scene.environment = environment.texture;
    scene.environmentIntensity = 0.35;

    // Luces: clave cálida desde arriba-luz, rim frío para separar del fondo,
    // relleno suave y acento de color por mood.
    const hemisphere = new THREE.HemisphereLight(0xcfe8ff, 0x4a2a18, 0.3);
    scene.add(hemisphere);

    const ambient = new THREE.AmbientLight(0xffffff, 0.04);
    scene.add(ambient);

    const keyLight = new THREE.DirectionalLight(0xffe8d0, 1.7);
    keyLight.position.set(5.0, 8.0, 6.0);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(2048, 2048);
    keyLight.shadow.camera.near = 0.5;
    keyLight.shadow.camera.far = 28;
    keyLight.shadow.camera.left = -4.0;
    keyLight.shadow.camera.right = 4.0;
    keyLight.shadow.camera.top = 5.0;
    keyLight.shadow.camera.bottom = -1.6;
    keyLight.shadow.bias = -0.0003;
    keyLight.shadow.normalBias = 0.02;
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0x8fd8ff, 0.7);
    rimLight.position.set(-6.0, 4.0, -5.0);
    scene.add(rimLight);

    const fillLight = new THREE.DirectionalLight(0xffb86b, 0.25);
    fillLight.position.set(-2.2, 1.6, 6.0);
    scene.add(fillLight);

    const accentLight = new THREE.PointLight(0xb3d9ff, 0.7, 0, 2);
    accentLight.position.set(2.8, 2.4, -1.8);
    scene.add(accentLight);

    const ground = new THREE.Mesh(
      new THREE.CircleGeometry(2.1, 72),
      new THREE.ShadowMaterial({ color: 0x000000, opacity: 0.46 })
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = 0.005;
    ground.receiveShadow = true;
    scene.add(ground);

    // Sombra de contacto difusa que asienta las orugas sobre el piso.
    const contactShadow = new THREE.Mesh(
      new THREE.PlaneGeometry(2.8, 2.0),
      new THREE.MeshBasicMaterial({
        map: createContactShadowTexture(),
        color: 0x000000,
        transparent: true,
        opacity: 0.5,
        depthWrite: false,
      })
    );
    contactShadow.rotation.x = -Math.PI / 2;
    contactShadow.position.y = 0.002;
    scene.add(contactShadow);

    // Polvo
    const dustCount = 74;
    const dustPositions = new Float32Array(dustCount * 3);
    const dustSpeeds = new Float32Array(dustCount);
    const dustPhases = new Float32Array(dustCount);

    for (let index = 0; index < dustCount; index += 1) {
      const offset = index * 3;
      dustPositions[offset] = (Math.random() - 0.5) * 4.4;
      dustPositions[offset + 1] = Math.random() * 3.2;
      dustPositions[offset + 2] = -1.35 + Math.random() * 2.7;
      dustSpeeds[index] = 0.035 + Math.random() * 0.11;
      dustPhases[index] = Math.random() * Math.PI * 2;
    }

    const dustGeometry = new THREE.BufferGeometry();
    dustGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(dustPositions, 3)
    );
    const dustTexture = createDustTexture();
    const dustMaterial = new THREE.PointsMaterial({
      color: 0xffc98a,
      map: dustTexture,
      size: 0.038,
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    });
    const dust = new THREE.Points(dustGeometry, dustMaterial);
    dust.frustumCulled = false;
    scene.add(dust);

    const resize = () => {
      const width = host.clientWidth || 1;
      const height = host.clientHeight || 1;
      renderer.setSize(width, height, false);
      composer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      if (modelRoot && !userAdjusted) {
        frameModel(camera, controls, modelDimensions);
      }
    };

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(host);
    resize();
    frameModel(camera, controls);

    const onDragStart = () => {
      userAdjusted = true;
      host.classList.add("is-dragging");
    };
    const onDragEnd = () => host.classList.remove("is-dragging");
    const onDoubleClick = () => controls.reset();

    controls.addEventListener("start", onDragStart);
    controls.addEventListener("end", onDragEnd);
    renderer.domElement.addEventListener("dblclick", onDoubleClick);

    const clock = new THREE.Clock();
    const accentTarget = new THREE.Color();

    const installModel = (gltf, usedFile) => {
      const object = gltf.scene;

      const nextEmissive = new Set();
      const anisotropy = Math.min(
        renderer.capabilities.getMaxAnisotropy(),
        8
      );

      // 1) Preparar los mapas originales (sRGB, anisotropía) antes de clonar.
      object.traverse((child) => {
        if (!child.isMesh) return;
        child.castShadow = true;
        child.receiveShadow = true;
        child.frustumCulled = true;

        const list = Array.isArray(child.material)
          ? child.material
          : [child.material];
        list.forEach((material) => {
          if (!material) return;

          if (material.map) {
            material.map.colorSpace = THREE.SRGBColorSpace;
            material.map.anisotropy = anisotropy;
          }
          if (material.emissiveMap) {
            material.emissiveMap.colorSpace = THREE.SRGBColorSpace;
            material.emissiveMap.anisotropy = anisotropy;
          }
          ["normalMap", "roughnessMap", "metalnessMap", "aoMap"].forEach(
            (key) => {
              if (!material[key]) return;
              material[key].colorSpace = THREE.NoColorSpace;
              material[key].anisotropy = anisotropy;
            }
          );
          material.needsUpdate = true;
        });
      });

      // 2) El GLB comparte un único material PBR entre 42 mallas. Se separa en
      // familias para que pintura, orugas y metal respondan distinto a la luz.
      let sourceWall = null;
      object.traverse((child) => {
        if (!child.isMesh) return;
        const list = Array.isArray(child.material)
          ? child.material
          : [child.material];
        list.forEach((material) => {
          if (material?.name === "wall_e") sourceWall = material;
        });
      });

      let materialSets = null;
      if (sourceWall) {
        const paint = sourceWall.clone();
        paint.name = "wall_e_paint";
        paint.color.setHex(0xecd18a); // amarillo WALL·E sucio/usado
        paint.metalnessMap = null;
        paint.metalness = 0.04;
        paint.roughness = 0.92;
        paint.envMapIntensity = 0.75;
        paint.needsUpdate = true;

        const tread = sourceWall.clone();
        tread.name = "wall_e_tread";
        tread.color.setHex(0x3a3a3c);
        tread.metalnessMap = null;
        tread.metalness = 0.08;
        tread.roughness = 1.15;
        tread.envMapIntensity = 0.45;
        tread.needsUpdate = true;

        const metal = sourceWall.clone();
        metal.name = "wall_e_metal";
        metal.color.setHex(0xcfb37a);
        metal.metalnessMap = null;
        metal.metalness = 0.85;
        metal.roughness = 0.3;
        metal.envMapIntensity = 1.0;
        metal.needsUpdate = true;

        const glass = new THREE.MeshPhysicalMaterial({
          name: "eyes_glass",
          color: 0x0a0c12,
          metalness: 0,
          roughness: 0.04,
          clearcoat: 1,
          clearcoatRoughness: 0.02,
          envMapIntensity: 1.4,
          ior: 1.45,
          reflectivity: 1,
          emissive: new THREE.Color(0x000000),
          emissiveIntensity: 0.15,
        });

        materialSets = { paint, tread, metal, glass };
      }

      // 3) Asignar la familia correcta a cada malla.
      object.traverse((child) => {
        if (!child.isMesh) return;

        if (materialSets) {
          const isLens =
            child.name === "eyes_low001" || child.material?.name === "eyes";
          if (isLens) {
            child.material = materialSets.glass;
          } else if (
            /^(body_low|back_low|hand_low(001|002)?)$/.test(child.name)
          ) {
            child.material = materialSets.paint;
          } else if (/^(neck_low|eyes_low)$/.test(child.name)) {
            child.material = materialSets.metal;
          } else {
            child.material = materialSets.tread;
          }
        }

        const list = Array.isArray(child.material)
          ? child.material
          : [child.material];
        list.forEach((material) => {
          if (!material) return;
          if (material.emissive && material.emissive.getHex() !== 0x000000) {
            nextEmissive.add(material);
          }
        });
      });

      // Encajar el modelo en la escena. Se escala y centra el grupo
      // contenedor, nunca los nodos animados que vienen dentro del GLB.
      const nextRoot = new THREE.Group();
      nextRoot.rotation.y = MODEL_YAW;
      nextRoot.add(object);

      const initialBox = new THREE.Box3().setFromObject(object);
      const size = initialBox.getSize(new THREE.Vector3());
      const scale = Math.min(Math.max(MODEL_HEIGHT / Math.max(size.y, 0.001), 0.1), 5.0);
      nextRoot.scale.setScalar(scale);
      nextRoot.updateMatrixWorld(true);

      const box = new THREE.Box3().setFromObject(nextRoot);
      const base = object.getObjectByName("base_low");
      const centerBox = base ? new THREE.Box3().setFromObject(base) : box;
      const center = centerBox.getCenter(new THREE.Vector3());
      nextRoot.position.x -= center.x;
      nextRoot.position.y -= box.min.y;
      nextRoot.position.z -= center.z;
      nextRoot.updateMatrixWorld(true);

      modelDimensions = {
        width: Math.max(size.x, size.z) * scale,
        height: MODEL_HEIGHT,
      };

      if (modelRoot) disposeObject3D(modelRoot);
      scene.add(nextRoot);
      modelRoot = nextRoot;
      emissiveMaterials = [...nextEmissive];

      // El modelo ya está visible: quitamos el overlay de carga antes de crear
      // el controlador para que nunca quede en "Cargando modelo... 100%".
      userAdjusted = false;
      frameModel(camera, controls, modelDimensions);
      setStatus({ state: "ready", file: usedFile });

      // El controlador usa solo el clip original y nunca modifica huesos.
      try {
        controllerRef.current?.dispose();
        controllerRef.current = new WallEAnimationController(
          gltf,
          nextRoot,
          () => {
            onActionCompleteRef.current?.();
          }
        );

        // Aplica el estado actual (incluida una acción solicitada mientras cargaba).
        const queuedRequest = actionRequestRef.current;
        lastSignalRef.current = queuedRequest.actionSignal;
        controllerRef.current.setState(queuedRequest.action);
      } catch (error) {
        console.error("[WALL-E] No se pudo inicializar la animación:", error);
        controllerRef.current = null;
      }

      onModelLoadedRef.current?.(usedFile);
    };

    // Carga un GLTF con reporte de progreso (para no dejar "Cargando modelo..."
    // quieto mientras baja el archivo pesado).
    const loadGLTF = (url, onProgress) =>
      new Promise((resolve, reject) => {
        const loader = new GLTFLoader();
        loader.load(
          url,
          resolve,
          (event) => {
            if (onProgress && event.total > 0) {
              onProgress(event.loaded / event.total);
            }
          },
          reject
        );
      });

    const loadModel = async (modelId) => {
      const option =
        WALLE_MODELS.find((entry) => entry.id === modelId) ||
        WALLE_MODELS[0];
      setStatus({ state: "loading", file: null, progress: 0 });

      let gltf = null;
      let usedFile = null;

      for (const file of option.files) {
        try {
          gltf = await loadGLTF(`${MODEL_BASE}${file}`, (p) => {
            if (!disposed) {
              setStatus({ state: "loading", file: null, progress: p });
            }
          });
          usedFile = file;
          break;
        } catch {
          // siguiente archivo
        }
        if (disposed) return;
      }

      if (!gltf) {
        if (!disposed) {
          setStatus({ state: "error", file: null });
        }
        return;
      }

      if (disposed) {
        disposeObject3D(gltf.scene);
        return;
      }

      sanitizeDuplicateNodeNames(gltf);

      // NOTA: no tocar position/scale de los nodos del GLB. El modelo ya viene
      // ensamblado (bbox ~4.6 unidades de alto); installModel lo escala entero
      // como grupo contenedor. Modificar nodos individuales lo desarma.
      installModel(gltf, usedFile);
    };

    const animate = () => {
      frame = window.requestAnimationFrame(animate);
      const dt = Math.min(clock.getDelta(), 0.05);
      const elapsed = clock.elapsedTime;
      const presentation = presentationRef.current;
      const moodStyle = MOOD_STYLES[presentation.mood] || MOOD_STYLES.tranquilo;
      const reduced = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
      ).matches;

      // Actualiza animación del controlador
      if (controllerRef.current) {
        controllerRef.current.update(dt);
      }

      // Brillo emissivo según estado
      const glowTarget = presentation.thinking
        ? 0.72 + Math.sin(elapsed * 2.2) * 0.16
        : presentation.speaking
          ? 1.14 + Math.sin(elapsed * 9) * 0.2
          : moodStyle.glow;

      emissiveMaterials.forEach((material) => {
        material.emissiveIntensity = damp(
          material.emissiveIntensity,
          glowTarget,
          3.4,
          dt
        );
      });

      accentTarget.setHex(moodStyle.accent);
      accentLight.color.lerp(accentTarget, 1 - Math.exp(-3.2 * dt));
      const accentPulse = presentation.speaking
        ? 1.2 + Math.sin(elapsed * 8) * 0.22
        : presentation.thinking
          ? 0.82 + Math.sin(elapsed * 2.4) * 0.16
          : 1;
      accentLight.intensity = damp(
        accentLight.intensity,
        0.7 * accentPulse,
        3.2,
        dt
      );

      renderer.toneMappingExposure = damp(
        renderer.toneMappingExposure,
        presentation.speaking ? moodStyle.exposure + 0.04 : moodStyle.exposure,
        2.4,
        dt
      );

      // Polvo
      if (!reduced) {
        const positions = dustGeometry.attributes.position.array;
        for (let index = 0; index < dustCount; index += 1) {
          const offset = index * 3;
          positions[offset + 1] += dustSpeeds[index] * dt;
          positions[offset] +=
            Math.sin(elapsed * 0.55 + dustPhases[index]) * dt * 0.012;
          positions[offset + 2] +=
            Math.cos(elapsed * 0.4 + dustPhases[index]) * dt * 0.008;
          if (positions[offset + 1] > 3.3) {
            positions[offset + 1] = -0.15;
            positions[offset] = (Math.random() - 0.5) * 4.4;
            positions[offset + 2] = -1.35 + Math.random() * 2.7;
          }
        }
        dustGeometry.attributes.position.needsUpdate = true;
      }

      dustMaterial.opacity = 0.46 + Math.sin(elapsed * 0.8) * 0.08;

      controls.update();
      composer.render();
    };

    const onVisibility = () => {
      if (document.hidden) {
        window.cancelAnimationFrame(frame);
        frame = 0;
      } else if (!frame && !disposed) {
        clock.getDelta();
        frame = window.requestAnimationFrame(animate);
      }
    };

    document.addEventListener("visibilitychange", onVisibility);
    frame = window.requestAnimationFrame(animate);
    loadModel(model);

    return () => {
      disposed = true;
      window.cancelAnimationFrame(frame);
      document.removeEventListener("visibilitychange", onVisibility);
      controls.removeEventListener("start", onDragStart);
      controls.removeEventListener("end", onDragEnd);
      renderer.domElement.removeEventListener("dblclick", onDoubleClick);
      resizeObserver.disconnect();
      if (modelRoot) disposeObject3D(modelRoot);
      if (controllerRef.current) {
        controllerRef.current.dispose();
      }
      composer.dispose();
      renderer.dispose();
      host.removeChild(renderer.domElement);
    };
  }, [model]);

  // Maneja solicitudes de acción. Si el GLB sigue cargando, se procesa al instalarlo.
  useEffect(() => {
    const controller = controllerRef.current;
    if (!controller) return;
    lastSignalRef.current = actionSignal;
    controller.setState(action);
  }, [action, actionSignal]);

  return (
    <div
      className="walle-3d"
      ref={hostRef}
      role="region"
      aria-label="Visualización 3D de WALL-E"
    >
      {status.state !== "ready" && (
        <div className="walle-3d__status" role="status">
          {status.state === "loading" && (
            <>
              Cargando modelo...
              {status.progress > 0 ? ` ${Math.round(status.progress * 100)}%` : ""}
            </>
          )}
          {status.state === "error" && "Error cargando el modelo"}
        </div>
      )}
    </div>
  );
}
