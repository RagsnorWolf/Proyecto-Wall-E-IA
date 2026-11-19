/* Motor de sonido de la cabina.
   Sonidos originales inspirados en el diseño sonoro de WALL·E: chirridos
   filtrados, servos, orugas y un loop ambiente. Se activa con un gesto del
   usuario para respetar las políticas de reproducción de los navegadores. */

const BASE = "/sounds";

const ONE_SHOTS = {
  happy: { file: "expression-happy.wav", volume: 0.32 },
  curious: { file: "expression-curious.wav", volume: 0.26 },
  sad: { file: "expression-sad.wav", volume: 0.24 },
  alert: { file: "expression-alert.wav", volume: 0.3 },
  servo: { file: "servo.wav", volume: 0.18 },
  charge: { file: "charge.wav", volume: 0.22 },
  boot: { file: "boot.wav", volume: 0.3 },
};

class SfxEngine {
  constructor() {
    this.enabled = true;
    this.loops = new Map();
    this.ambient = null;
    this.tread = null;
    this.unlocked = false;
  }

  setEnabled(value) {
    this.enabled = Boolean(value);
    if (!this.enabled) {
      this.stopAmbient();
      this.stopTread();
      this.loops.forEach((audio) => {
        try {
          audio.pause();
        } catch {
          /* nada */
        }
      });
      this.loops.clear();
    }
  }

  /** Llamar en el primer gesto del usuario. */
  unlock() {
    this.unlocked = true;
  }

  play(name) {
    if (!this.enabled) return null;
    this.unlocked = true;
    const item = ONE_SHOTS[name];
    if (!item) return null;
    try {
      const audio = new Audio(`${BASE}/${item.file}`);
      audio.volume = item.volume;
      audio.preload = "auto";
      const promise = audio.play();
      if (promise && typeof promise.catch === "function") {
        promise.catch(() => {});
      }
      audio.addEventListener("ended", () => {
        audio.src = "";
      });
      return audio;
    } catch {
      return null;
    }
  }

  startLoop(key, file, volume, { fade = 0 } = {}) {
    if (!this.enabled) return null;
    this.unlocked = true;
    const current = this.loops.get(key);
    if (current) {
      if (!current.paused) return current;
      current.play().catch(() => {});
      return current;
    }
    try {
      const audio = new Audio(`${BASE}/${file}`);
      audio.loop = true;
      audio.volume = 0;
      audio.preload = "auto";
      this.loops.set(key, audio);
      audio.play().catch(() => {});
      const target = volume;
      if (fade > 0) {
        const steps = 18;
        let step = 0;
        const timer = window.setInterval(() => {
          step += 1;
          audio.volume = Math.min(target, (target * step) / steps);
          if (step >= steps) window.clearInterval(timer);
        }, (fade * 1000) / steps);
      } else {
        audio.volume = target;
      }
      return audio;
    } catch {
      return null;
    }
  }

  stopLoop(key) {
    const audio = this.loops.get(key);
    if (!audio) return;
    try {
      audio.pause();
      audio.currentTime = 0;
      audio.src = "";
    } catch {
      /* nada */
    }
    this.loops.delete(key);
  }

  startTread() {
    this.tread = this.startLoop("tread", "tread-loop.wav", 0.22, { fade: 0.2 });
  }

  stopTread() {
    this.stopLoop("tread");
    this.tread = null;
  }

  startAmbient() {
    if (!this.enabled) return;
    this.ambient = this.startLoop("ambient", "ambient-loop.wav", 0.16, {
      fade: 1.6,
    });
  }

  stopAmbient() {
    this.stopLoop("ambient");
    this.ambient = null;
  }

  get ambientPlaying() {
    const audio = this.loops.get("ambient");
    return Boolean(audio && !audio.paused);
  }
}

export const sfx = new SfxEngine();
