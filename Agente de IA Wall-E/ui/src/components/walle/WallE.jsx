import { useCallback, useEffect, useRef, useState } from "react";
import { Footprints, Hand, Music2 } from "lucide-react";
import cityPhoto from "../../assets/walle/walle-city.jpg";
import { sfx } from "../../lib/sfx";
import { DEFAULT_WALLE_MODEL, WallE3D } from "./WallE3D";
import "./WallE.css";

const DUST = [
  [8, 18, 2.2, 0], [22, 42, 1.4, 1.2], [12, 68, 1.8, 2.4], [30, 12, 1.2, 0.8],
  [78, 22, 1.6, 1.8], [88, 54, 2.4, 0.4], [70, 74, 1.2, 2.8], [92, 80, 1.8, 1.6],
  [44, 6, 1.4, 3.2], [58, 88, 2.0, 0.2], [6, 84, 1.6, 2.2], [96, 8, 1.2, 3.6],
];

const ACTIONS = [
  { id: "wave", label: "Saludar", icon: Hand },
  { id: "walk", label: "Caminar", icon: Footprints },
  { id: "dance", label: "Bailar", icon: Music2 },
];

export function WallE({
  mood = "tranquilo",
  thinking = false,
  speaking = false,
  bubble = null,
}) {
  const [action, setAction] = useState("idle");
  const actionRef = useRef("idle");
  const [actionSignal, setActionSignal] = useState(0);
  const [assetFile, setAssetFile] = useState(null);

  const play = useCallback((id) => {
    sfx.unlock();
    const previousAction = actionRef.current;
    const nextAction = previousAction === id ? "idle" : id;
    actionRef.current = nextAction;

    sfx.stopTread();
    if (nextAction === "wave") sfx.play("happy");
    if (nextAction === "walk") {
      sfx.play("servo");
      sfx.startTread();
    }
    if (nextAction === "dance") sfx.play("charge");

    setAction(nextAction);
    setActionSignal((value) => value + 1);
  }, []);

  const handleActionComplete = useCallback(() => {
    actionRef.current = "idle";
    setAction("idle");
    sfx.stopTread();
  }, []);

  useEffect(() => () => sfx.stopTread(), []);

  return (
    <div
      className={`walle-stage ${thinking ? "is-thinking" : ""} ${speaking ? "is-speaking" : ""}`}
      data-mood={mood}
      data-action={action}
      role="group"
      aria-label="WALL-E, unidad de compactación BnL 4360. Arrastrá para girarlo y usá los botones para saludar, caminar o bailar."
    >
      <div
        className="walle-stage__backdrop"
        style={{ backgroundImage: `url(${cityPhoto})` }}
        aria-hidden="true"
      />
      <div className="walle-stage__vignette" aria-hidden="true" />
      <div className="walle-stage__grid" aria-hidden="true" />
      <div className="walle-stage__glow" aria-hidden="true" />
      <div className="walle-stage__scan" aria-hidden="true" />

      <div className="walle-dust" aria-hidden="true">
        {DUST.map(([x, y, size, delay], index) => (
          <i
            key={index}
            style={{
              left: `${x}%`,
              top: `${y}%`,
              width: `${size}px`,
              height: `${size}px`,
              animationDelay: `${delay}s`,
            }}
          />
        ))}
      </div>

      <div className="walle-avatar">
        <WallE3D
          mood={mood}
          thinking={thinking}
          speaking={speaking}
          action={action}
          actionSignal={actionSignal}
          onActionComplete={handleActionComplete}
          model={DEFAULT_WALLE_MODEL}
          onModelLoaded={setAssetFile}
        />

        {bubble ? (
          <div className="walle-bubble" role="status">
            {bubble}
            <i aria-hidden="true" />
          </div>
        ) : null}
      </div>

      <div className="walle-controls" role="group" aria-label="Acciones de WALL-E">
        {ACTIONS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            className={`walle-controls__button ${action === id ? "is-active" : ""}`}
            onClick={() => play(id)}
            aria-pressed={action === id}
          >
            <Icon size={13} strokeWidth={2.2} aria-hidden="true" />
            <span>{label}</span>
          </button>
        ))}
        <span className="walle-controls__hint">
          Arrastrá para girar · scroll para acercar · doble clic para centrar
        </span>
      </div>

      <span className="walle-stage__tag">WALL·E · unidad 01</span>

      {assetFile === "walle_animated.glb" ? (
        <a
          className="walle-stage__credit"
          href="https://sketchfab.com/3d-models/wall-eanimated-a6758de2e5a04f9e821596592ef4279c"
          target="_blank"
          rel="noreferrer"
          title="Wall-E(Animated) por Zeps3D, licencia CC BY 4.0"
        >
          Modelo 3D: Zeps3D · CC BY 4.0
        </a>
      ) : null}
    </div>
  );
}
