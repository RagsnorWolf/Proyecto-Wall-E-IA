import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Music2, Power } from "lucide-react";
import { WallE } from "./components/walle/WallE";
import { api } from "./lib/api";
import { sfx } from "./lib/sfx";
import "./styles/companion.css";

const MOOD_LABEL = {
  tranquilo: "en reposo",
  curioso: "curioso",
  contento: "contento",
  pensando: "concentrado",
  atento: "atento",
  asustado: "alerta",
  aburrido: "aburrido",
  cansado: "cansado",
};

const SUGGESTIONS = [
  "¿Qué podés hacer?",
  "Ayudame a organizar el día",
  "Explicame algo difícil",
];

const WELCOME = {
  id: "welcome",
  role: "assistant",
  text: "Hola. Soy WALL·E. Decime qué necesitás y lo resolvemos.",
  time: "",
};

function nowLabel() {
  try {
    return new Date().toLocaleTimeString("es-AR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function makeMessage(role, text, extra = {}) {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    role,
    text,
    time: nowLabel(),
    ...extra,
  };
}

export function App() {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [mood, setMood] = useState("tranquilo");
  const [energy, setEnergy] = useState(78);
  const [music, setMusic] = useState(() => {
    try {
      return localStorage.getItem("walle.music") !== "off";
    } catch {
      return true;
    }
  });
  const [shuttingDown, setShuttingDown] = useState(false);
  const [sound, setSound] = useState(() => {
    try {
      return localStorage.getItem("walle.sound") !== "off";
    } catch {
      return true;
    }
  });
  const [online, setOnline] = useState(true);
  const [ready, setReady] = useState(false);
  const [booting, setBooting] = useState(true);
  const [notice, setNotice] = useState(null);

  const threadRef = useRef(null);
  const composerRef = useRef(null);
  const thinkingRef = useRef(false);
  const soundRef = useRef(sound);
  const musicRef = useRef(music);
  const bootedRef = useRef(false);
  const draftRef = useRef("");
  const voiceRef = useRef(null);
  const audioRef = useRef(null);
  const speakSeq = useRef(0);
  const recognitionRef = useRef(null);
  const sendRef = useRef(null);

  const micSupported = useMemo(() => {
    if (typeof window === "undefined") return false;
    return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
  }, []);

  const stopVoice = useCallback(() => {
    speakSeq.current += 1;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = "";
      audioRef.current = null;
    }
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, []);

  const ensureAudio = useCallback(() => {
    sfx.unlock();
    if (!bootedRef.current) {
      bootedRef.current = true;
      sfx.play("boot");
    }
    if (soundRef.current && musicRef.current) sfx.startAmbient();
  }, []);

  useEffect(() => {
    soundRef.current = sound;
    try {
      localStorage.setItem("walle.sound", sound ? "on" : "off");
    } catch {
      /* almacenamiento bloqueado */
    }
    sfx.setEnabled(sound);
    if (!sound) {
      sfx.stopAmbient();
      stopVoice();
    }
  }, [sound, stopVoice]);

  useEffect(() => {
    musicRef.current = music;
    try {
      localStorage.setItem("walle.music", music ? "on" : "off");
    } catch {
      /* almacenamiento bloqueado */
    }
  }, [music]);

  useEffect(() => {
    const onFirstGesture = () => {
      ensureAudio();
      window.removeEventListener("pointerdown", onFirstGesture);
    };
    window.addEventListener("pointerdown", onFirstGesture);
    return () => window.removeEventListener("pointerdown", onFirstGesture);
  }, [ensureAudio]);

  useEffect(() => {
    if (!("speechSynthesis" in window)) return undefined;
    const synth = window.speechSynthesis;
    const pickVoice = () => {
      const voices = synth.getVoices();
      voiceRef.current =
        voices.find((item) => /es[-_]AR/i.test(item.lang)) ||
        voices.find((item) => /es[-_]MX/i.test(item.lang)) ||
        voices.find((item) => /es[-_]US/i.test(item.lang)) ||
        voices.find((item) => item.lang?.toLowerCase().startsWith("es")) ||
        voices.find((item) => /david|mark|jorge|diego|carlos/i.test(item.name)) ||
        null;
    };
    pickVoice();
    synth.addEventListener?.("voiceschanged", pickVoice);
    return () => synth.removeEventListener?.("voiceschanged", pickVoice);
  }, []);

  useEffect(
    () => () => {
      if (audioRef.current) audioRef.current.pause();
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    },
    []
  );

  const speakFallback = useCallback((text) => {
    if (!soundRef.current || !("speechSynthesis" in window)) return;
    const synth = window.speechSynthesis;
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "es-AR";
    utterance.rate = 0.98;
    utterance.pitch = 0.82;
    if (voiceRef.current) utterance.voice = voiceRef.current;
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    synth.speak(utterance);
  }, []);

  const speak = useCallback(
    async (text) => {
      if (!soundRef.current) return;
      const clean = String(text ?? "").trim();
      if (!clean) return;
      const seq = ++speakSeq.current;
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = "";
        audioRef.current = null;
      }
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
      try {
        const response = await fetch("/api/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: clean }),
        });
        if (!response.ok) throw new Error("tts no disponible");
        const blob = await response.blob();
        if (seq !== speakSeq.current || !soundRef.current) return;
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audioRef.current = audio;
        audio.onplay = () => setSpeaking(true);
        audio.onended = () => {
          if (audioRef.current === audio) {
            audioRef.current = null;
            setSpeaking(false);
          }
          URL.revokeObjectURL(url);
        };
        audio.onerror = () => {
          if (audioRef.current === audio) {
            audioRef.current = null;
            setSpeaking(false);
          }
          URL.revokeObjectURL(url);
        };
        await audio.play();
      } catch {
        if (seq === speakSeq.current) speakFallback(clean);
      }
    },
    [speakFallback]
  );

  const send = useCallback(
    async (raw) => {
      const text = String(raw ?? draftRef.current ?? "").trim();
      if (!text || thinkingRef.current) return;
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          /* ya estaba detenido */
        }
        recognitionRef.current = null;
      }
      thinkingRef.current = true;
      draftRef.current = "";
      setDraft("");
      setInterim("");
      setNotice(null);
      setThinking(true);
      stopVoice();
      const wasBooted = bootedRef.current;
      ensureAudio();
      if (wasBooted) sfx.play("curious");
      setMessages((current) => [...current, makeMessage("user", text)]);
      if (composerRef.current) composerRef.current.style.height = "auto";

      try {
        const data = await api.chat(text);
        const reply = data.reply || "Mmm. No sé qué decir.";
        setMessages((current) => [
          ...current,
          makeMessage("assistant", reply, { error: false }),
        ]);
        const nextMood = data.mood?.mood || data.state?.emotion?.mood;
        if (nextMood) setMood(nextMood);
        if (typeof data.mood?.energy === "number") setEnergy(data.mood.energy);
        setOnline(true);
        speak(reply);
      } catch {
        setMessages((current) => [
          ...current,
          makeMessage(
            "assistant",
            "Se me cortó la voz un segundo. ¿Me lo repetís?",
            { error: true }
          ),
        ]);
        setNotice("No pude hablar con WALL-E. Revisá que el servidor esté abierto.");
        setOnline(false);
      } finally {
        thinkingRef.current = false;
        setThinking(false);
      }
    },
    [ensureAudio, speak, stopVoice]
  );

  sendRef.current = send;

  useEffect(() => {
    let alive = true;
    api
      .companion()
      .then((data) => {
        if (!alive) return;
        setOnline(true);
        setReady(Boolean(data.ready));
        if (data.mood?.mood) setMood(data.mood.mood);
        if (typeof data.mood?.energy === "number") setEnergy(data.mood.energy);
        const history = (data.history || [])
          .filter((turn) => turn && turn.content)
          .map((turn, index) => ({
            id: `h-${index}`,
            role: turn.role === "user" ? "user" : "assistant",
            text: turn.content,
            time: "",
          }));
        setMessages(history.length ? history : [WELCOME]);
      })
      .catch(() => {
        if (!alive) return;
        setOnline(false);
        setMessages([WELCOME]);
      })
      .finally(() => {
        if (alive) setBooting(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      api
        .companion()
        .then((data) => {
          setOnline(true);
          setReady(Boolean(data.ready));
          if (data.mood?.mood) setMood(data.mood.mood);
          if (typeof data.mood?.energy === "number") setEnergy(data.mood.energy);
        })
        .catch(() => setOnline(false));
    }, 10000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const thread = threadRef.current;
    if (!thread) return;
    thread.scrollTo({ top: thread.scrollHeight, behavior: "smooth" });
  }, [messages, thinking]);

  useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(null), 6500);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(
    () => () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          /* nada */
        }
      }
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    },
    []
  );

  const updateDraft = useCallback((value) => {
    draftRef.current = value;
    setDraft(value);
  }, []);

  const handleDraft = useCallback(
    (event) => {
      updateDraft(event.target.value);
      const element = event.target;
      element.style.height = "auto";
      element.style.height = `${Math.min(element.scrollHeight, 132)}px`;
    },
    [updateDraft]
  );

  const submit = useCallback(
    (event) => {
      event?.preventDefault();
      send();
    },
    [send]
  );

  const handleKeyDown = useCallback(
    (event) => {
      if (event.key !== "Enter" || event.shiftKey || event.nativeEvent?.isComposing) {
        return;
      }
      event.preventDefault();
      send();
    },
    [send]
  );

  const toggleSound = useCallback(() => {
    const next = !soundRef.current;
    soundRef.current = next;
    setSound(next);
    sfx.setEnabled(next);
    if (!next) {
      sfx.stopAmbient();
      stopVoice();
    } else {
      ensureAudio();
      if (musicRef.current) sfx.startAmbient();
    }
  }, [ensureAudio, stopVoice]);

  const toggleMusic = useCallback(() => {
    const next = !musicRef.current;
    musicRef.current = next;
    setMusic(next);
    try {
      localStorage.setItem("walle.music", next ? "on" : "off");
    } catch {
      /* almacenamiento bloqueado */
    }
    if (!next) {
      sfx.stopAmbient();
      return;
    }
    ensureAudio();
    if (soundRef.current) sfx.startAmbient();
  }, [ensureAudio]);

  const handleShutdown = useCallback(async () => {
    if (shuttingDown) return;
    const ok = window.confirm(
      "¿Apagar WALL·E y cerrar el servidor local? La pestaña va a dejar de responder."
    );
    if (!ok) return;
    setShuttingDown(true);
    sfx.play("sad");
    stopVoice();
    sfx.stopAmbient();
    sfx.stopTread();
    try {
      await api.shutdown();
    } catch {
      /* el servidor puede cerrarse antes de responder */
    }
    setOnline(false);
    setNotice("WALL·E se apagó. Podés cerrar esta pestaña.");
  }, [shuttingDown, stopVoice]);

  const toggleMic = useCallback(() => {
    if (listening) {
      try {
        recognitionRef.current?.stop();
      } catch {
        /* nada */
      }
      return;
    }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setNotice("Este navegador no tiene dictado. Probá con Chrome o Edge.");
      return;
    }
    const recognition = new Recognition();
    recognition.lang = "es-AR";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      let finalText = "";
      let partial = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const transcript = result[0]?.transcript || "";
        if (result.isFinal) finalText += transcript;
        else partial += transcript;
      }
      if (finalText.trim()) {
        updateDraft(finalText.trim());
        setInterim("");
        window.setTimeout(() => sendRef.current?.(finalText.trim()), 220);
      } else {
        setInterim(partial);
      }
    };
    recognition.onerror = (event) => {
      if (event.error !== "aborted" && event.error !== "no-speech") {
        setNotice("No te escuché bien. Probá otra vez.");
      }
      setListening(false);
      setInterim("");
      recognitionRef.current = null;
    };
    recognition.onend = () => {
      setListening(false);
      setInterim("");
      recognitionRef.current = null;
    };
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
    }
    try {
      recognition.start();
      recognitionRef.current = recognition;
      setListening(true);
      setNotice(null);
    } catch {
      setNotice("No pude abrir el micrófono.");
    }
  }, [listening, updateDraft]);

  const hasUserTurn = messages.some((message) => message.role === "user");
  const moodLabel = MOOD_LABEL[mood] || mood;

  const statusText = !online
    ? "sin conexión"
    : listening
      ? "te escucha"
      : thinking
        ? "pensando"
        : speaking
          ? "hablando"
          : booting || !ready
            ? "despertando"
            : "en línea";

  return (
    <div className="companion">
      <div className="companion__aurora" aria-hidden="true" />
      <div className="companion__window">
        <aside className="companion__side">
          <div className="companion__stage">
            <WallE mood={mood} thinking={thinking} speaking={speaking} />
          </div>

          <div className="companion__identity">
            <span className={`companion__pulse ${online ? "is-on" : "is-off"}`} />
            <div className="companion__who">
              <strong>WALL·E</strong>
              <span>{statusText}</span>
            </div>
            <span className="companion__mood">{moodLabel}</span>
            <span
              className="companion__solar"
              title={`Carga solar ${Math.round(energy)}%`}
            >
              <span className="companion__solar-label">SOL</span>
              <i>
                <b
                  style={{
                    width: `${Math.max(3, Math.min(100, energy))}%`,
                  }}
                />
              </i>
              <span className="companion__solar-value">
                {Math.round(energy)}%
              </span>
            </span>
          </div>
        </aside>

        <section className="companion__chat">
          <header className="companion__head">
            <div className="companion__brand">
              <span className="companion__brand-face" aria-hidden="true">
                <i className="companion__brand-eye companion__brand-eye--l" />
                <i className="companion__brand-eye companion__brand-eye--r" />
              </span>
              <div>
                <strong>WALL·E</strong>
                <span>asistente de a bordo · BnL 4360</span>
              </div>
            </div>
            <div className="companion__head-actions">
              <span className={`companion__live ${online ? "is-on" : "is-off"}`}>
                {online ? "local" : "sin servidor"}
              </span>
              <button
                type="button"
                className={`companion__icon ${music ? "is-active" : ""}`}
                onClick={toggleMusic}
                disabled={!sound}
                title={music ? "Apagar la música ambiental" : "Encender la música ambiental"}
                aria-label={music ? "Apagar la música ambiental" : "Encender la música ambiental"}
                aria-pressed={music}
              >
                <Music2 size={16} strokeWidth={1.8} />
              </button>
              <button
                type="button"
                className={`companion__icon ${sound ? "is-active" : ""}`}
                onClick={toggleSound}
                title={sound ? "Silenciar la voz y los sonidos" : "Activar la voz y los sonidos"}
                aria-label={sound ? "Silenciar la voz y los sonidos" : "Activar la voz y los sonidos"}
                aria-pressed={sound}
              >
                {sound ? <SpeakerIcon /> : <MutedIcon />}
              </button>
              <button
                type="button"
                className="companion__icon companion__icon--power"
                onClick={handleShutdown}
                disabled={shuttingDown}
                title="Apagar WALL·E"
                aria-label="Apagar WALL·E"
              >
                <Power size={16} strokeWidth={1.8} />
              </button>
            </div>
          </header>

          <div className="companion__thread" ref={threadRef}>
            <AnimatePresence initial={false}>
              {messages.map((message) => (
                <motion.div
                  key={message.id}
                  className={`bubble-row bubble-row--${message.role}`}
                  initial={{ opacity: 0, y: 8, scale: 0.985 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                >
                  {message.role === "assistant" ? (
                    <span className="bubble-avatar" aria-hidden="true">
                      W
                    </span>
                  ) : null}
                  <div
                    className={`bubble bubble--${message.role} ${
                      message.error ? "bubble--error" : ""
                    }`}
                  >
                    <p>{message.text}</p>
                    {message.time ? (
                      <span className="bubble__meta">{message.time}</span>
                    ) : null}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {thinking ? (
              <motion.div
                className="bubble-row bubble-row--assistant"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <span className="bubble-avatar" aria-hidden="true">
                  W
                </span>
                <div className="bubble bubble--assistant bubble--typing">
                  <span className="typing" aria-hidden="true">
                    <i />
                    <i />
                    <i />
                  </span>
                  <span className="bubble__meta">WALL·E está pensando</span>
                </div>
              </motion.div>
            ) : null}
          </div>

          <div className="companion__composer-wrap">
            {!hasUserTurn ? (
              <div className="companion__suggestions">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => send(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            ) : null}

            {notice ? (
              <div className="companion__notice" role="alert">
                {notice}
              </div>
            ) : null}

            <form className="composer" onSubmit={submit}>
              <textarea
                ref={composerRef}
                className="composer__input"
                value={draft}
                onChange={handleDraft}
                onKeyDown={handleKeyDown}
                rows={1}
                placeholder="Escribile a WALL·E…"
                aria-label="Mensaje para WALL·E"
              />
              <div className="composer__actions">
                <button
                  type="button"
                  className={`composer__mic ${listening ? "is-listening" : ""}`}
                  onClick={toggleMic}
                  disabled={!micSupported}
                  title={
                    micSupported
                      ? listening
                        ? "Detener el dictado"
                        : "Hablar con WALL·E"
                      : "Este navegador no tiene dictado"
                  }
                  aria-label={
                    listening ? "Detener el dictado" : "Hablar con WALL·E"
                  }
                  aria-pressed={listening}
                >
                  <MicIcon />
                </button>
                <button
                  type="submit"
                  className="composer__send"
                  disabled={!draft.trim() || thinking}
                  title="Enviar"
                  aria-label="Enviar mensaje"
                >
                  <SendIcon />
                </button>
              </div>
            </form>

            <p className="companion__hint">
              {listening
                ? interim || "Te escucho…"
                : "Enter para enviar · Shift + Enter para otra línea"}
            </p>
          </div>
        </section>
      </div>

      {shuttingDown ? (
        <div className="companion__blackout" role="status">
          <span className="companion__blackout-eye" aria-hidden="true" />
          <strong>WALL·E</strong>
          <span>sistemas apagados · BnL 4360</span>
        </div>
      ) : null}
    </div>
  );
}

function SpeakerIcon() {
  return (
    <svg viewBox="0 0 24 24" width="17" height="17" fill="none" aria-hidden="true">
      <path
        d="M4 9.5v5h3l4 3v-11l-4 3H4Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M15 9.2a4 4 0 0 1 0 5.6M17.6 6.8a7.4 7.4 0 0 1 0 10.4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MutedIcon() {
  return (
    <svg viewBox="0 0 24 24" width="17" height="17" fill="none" aria-hidden="true">
      <path
        d="M4 9.5v5h3l4 3v-11l-4 3H4Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="m15.5 9.5 4 5m0-5-4 5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" width="17" height="17" fill="none" aria-hidden="true">
      <rect
        x="9"
        y="4"
        width="6"
        height="10"
        rx="3"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M6.5 11.5a5.5 5.5 0 0 0 11 0M12 17v3"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
      <path
        d="M5 12.2 19 5l-3.2 14-4.3-5.1L5 12.2Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="m11.5 13.9 3.6-3.6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}
