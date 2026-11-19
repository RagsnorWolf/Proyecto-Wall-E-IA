"""PPO en Python puro: muestreo, GAE(lambda), recorte de razon y Adam.

Formulas del gradiente (verificadas por diferencias finitas en `pruebas.py`):

  r        = exp(logpi(a) - logpi_viejo(a))
  perdida  = -min(r*A, recorte(r)*A) + c_v*(V - R)^2 - c_e*H
  d(lp)    = -A*r                 si gana el termino sin recortar
           = -A*r                 si gana el recortado y r esta dentro del rango
           =  0                   si gana el recortado y r esta fuera (gradiente 0)
  d(logits)= d(lp) * (1[a=j] - softmax_j) + c_e * p_j * (log p_j + H)
  d(V)     = 2*c_v*(V - R)

Todo se agrega por muestra: sumar gradientes de un minilote es el gradiente
de la media del minilote dividido por su tamano.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from .red import RedActorCritica, log_softmax, softmax


@dataclass
class Hiperparametros:
    gamma: float = 0.99
    lam: float = 0.95
    lr: float = 3e-4
    pasos_rollout: int = 1024
    epocas: int = 4
    mini_lote: int = 256
    recorte: float = 0.2
    coef_valor: float = 0.5
    coef_entropia: float = 0.01
    recorte_gradiente: float = 0.5
    ocultas: tuple[int, int] = (32, 32)


class AgentePPO:
    def __init__(self, tam_obs: int, n_acciones: int, hparams: Hiperparametros | None = None,
                 semilla: int = 0) -> None:
        self.hp = hparams or Hiperparametros()
        self.tam_obs = tam_obs
        self.n_acciones = n_acciones
        self.rng = random.Random(semilla)
        self.red = RedActorCritica(tam_obs, n_acciones, self.hp.ocultas, random.Random(semilla))
        self._buffer: list[tuple] = []
        self._paso_adam = 0
        self.pasos_entrenados = 0
        self.actualizaciones = 0

    # --- interaccion ------------------------------------------------------
    def actuar(self, obs, determinista: bool = False) -> tuple[int, float, float]:
        logits, valor, _ = self.red.adelante(list(obs))
        if determinista:
            accion = max(range(len(logits)), key=logits.__getitem__)
        else:
            probabilidades = softmax(logits)
            umbral = self.rng.random()
            acumulado = 0.0
            accion = len(probabilidades) - 1
            for i, p in enumerate(probabilidades):
                acumulado += p
                if umbral <= acumulado:
                    accion = i
                    break
        logprob = log_softmax(logits)[accion]
        return accion, logprob, valor

    def guardar_paso(self, obs, accion: int, logprob: float, valor: float,
                     recompensa: float, terminado: bool) -> None:
        self._buffer.append((list(obs), int(accion), float(logprob), float(valor),
                             float(recompensa), bool(terminado)))

    def lleno(self) -> bool:
        return len(self._buffer) >= self.hp.pasos_rollout

    # --- gradiente de una muestra ----------------------------------------
    def _gradiente_muestra(self, obs, accion: int, logprob_viejo: float,
                           ventaja: float, retorno: float) -> tuple[list[tuple], dict]:
        hp = self.hp
        logits, valor, cache = self.red.adelante(list(obs))
        lps = log_softmax(logits)
        probabilidades = softmax(logits)
        logprob = lps[accion]

        razon = math.exp(logprob - logprob_viejo)
        sin_recorte = razon * ventaja
        recortada = min(max(razon, 1.0 - hp.recorte), 1.0 + hp.recorte) * ventaja

        if sin_recorte <= recortada:
            g_logprob = -ventaja * razon
        elif 1.0 - hp.recorte < razon < 1.0 + hp.recorte:
            g_logprob = -ventaja * razon
        else:
            g_logprob = 0.0

        entropia = -sum(p * lp for p, lp in zip(probabilidades, lps))
        g_logits = [0.0] * self.n_acciones
        for j in range(self.n_acciones):
            indicador = 1.0 if j == accion else 0.0
            flujo_politica = g_logprob * (indicador - probabilidades[j])
            flujo_entropia = hp.coef_entropia * probabilidades[j] * (lps[j] + entropia)
            g_logits[j] = flujo_politica + flujo_entropia

        error_valor = valor - retorno
        g_valor = 2.0 * hp.coef_valor * error_valor

        gradientes = self.red.retropropagar(cache, g_logits, g_valor)
        estadisticas = {
            "perdida_politica": -min(sin_recorte, recortada),
            "perdida_valor": error_valor * error_valor,
            "entropia": entropia,
            "aprox_kl": (razon - 1.0) - (logprob - logprob_viejo),
        }
        return gradientes, estadisticas

    def _gradiente_minilote(self, indices: list[int], datos: list[tuple]) -> tuple[list[tuple], dict]:
        suma: list[tuple] | None = None
        acumulado = {"perdida_politica": 0.0, "perdida_valor": 0.0,
                     "entropia": 0.0, "aprox_kl": 0.0}
        for idx in indices:
            obs, accion, logprob, _, ventaja, retorno = datos[idx]
            gradientes, estadisticas = self._gradiente_muestra(obs, accion, logprob, ventaja, retorno)
            suma = gradientes if suma is None else _sumar(suma, gradientes)
            for clave in acumulado:
                acumulado[clave] += estadisticas[clave]
        n = max(len(indices), 1)
        suma = [( [[g / n for g in fila] for fila in g_w], [g / n for g in g_b]) for g_w, g_b in suma]
        for clave in acumulado:
            acumulado[clave] /= n
        return suma, acumulado

    # --- aprendizaje ------------------------------------------------------
    def actualizar(self, obs_final) -> dict:
        if not self._buffer:
            return {"perdida_politica": 0.0, "perdida_valor": 0.0, "entropia": 0.0, "aprox_kl": 0.0}
        hp = self.hp
        observaciones = [b[0] for b in self._buffer]
        acciones = [b[1] for b in self._buffer]
        logprobs = [b[2] for b in self._buffer]
        valores = [b[3] for b in self._buffer]
        recompensas = [b[4] for b in self._buffer]
        terminados = [b[5] for b in self._buffer]
        self.pasos_entrenados += len(self._buffer)

        _, valor_final = self.red.logits_y_valor(list(obs_final))
        ventajas = [0.0] * len(recompensas)
        gae = 0.0
        for i in reversed(range(len(recompensas))):
            siguiente = valor_final if i == len(recompensas) - 1 else valores[i + 1]
            no_terminal = 0.0 if terminados[i] else 1.0
            delta = recompensas[i] + hp.gamma * siguiente * no_terminal - valores[i]
            gae = delta + hp.gamma * hp.lam * no_terminal * gae
            ventajas[i] = gae
        retornos = [v + a for v, a in zip(valores, ventajas)]

        media = sum(ventajas) / len(ventajas)
        desviacion = math.sqrt(sum((a - media) ** 2 for a in ventajas) / len(ventajas)) + 1e-8
        ventajas = [(a - media) / desviacion for a in ventajas]

        datos = list(zip(observaciones, acciones, logprobs, valores, ventajas, retornos))
        indices = list(range(len(datos)))
        resumen = {"perdida_politica": 0.0, "perdida_valor": 0.0, "entropia": 0.0, "aprox_kl": 0.0}
        minilotes = 0

        for _ in range(hp.epocas):
            self.rng.shuffle(indices)
            for inicio in range(0, len(indices), hp.mini_lote):
                trozo = indices[inicio:inicio + hp.mini_lote]
                if len(trozo) < 2:
                    continue
                gradientes, estadisticas = self._gradiente_minilote(trozo, datos)
                norma = self.red.norma_gradientes(gradientes)
                if norma > hp.recorte_gradiente:
                    gradientes = self.red.escalar_gradientes(gradientes, hp.recorte_gradiente / norma)
                self._paso_adam += 1
                self.red.aplicar_adam(gradientes, hp.lr, self._paso_adam)
                for clave in resumen:
                    resumen[clave] += estadisticas[clave]
                minilotes += 1

        self._buffer.clear()
        self.actualizaciones += 1
        if minilotes:
            for clave in resumen:
                resumen[clave] /= minilotes
        return resumen

    # --- persistencia -----------------------------------------------------
    def guardar(self, ruta: str | Path) -> None:
        destino = Path(ruta)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_suffix(destino.suffix + ".tmp")
        datos = self.red.a_diccionario()
        datos["pasos_entrenados"] = self.pasos_entrenados
        datos["actualizaciones"] = self.actualizaciones
        with temporal.open("w", encoding="utf-8") as f:
            json.dump(datos, f)
        temporal.replace(destino)

    @classmethod
    def cargar(cls, ruta: str | Path) -> "AgentePPO":
        with Path(ruta).open("r", encoding="utf-8") as f:
            datos = json.load(f)
        red = RedActorCritica.desde_diccionario(datos)
        agente = cls(red.tam_obs, red.n_acciones, Hiperparametros(ocultas=red.ocultas))
        agente.red = red
        agente.pasos_entrenados = int(datos.get("pasos_entrenados", 0))
        agente.actualizaciones = int(datos.get("actualizaciones", 0))
        return agente


def _sumar(a: list[tuple], b: list[tuple]) -> list[tuple]:
    for (a_w, a_b), (b_w, b_b) in zip(a, b):
        for fila_a, fila_b in zip(a_w, b_w):
            for i, g in enumerate(fila_b):
                fila_a[i] += g
        for i, g in enumerate(b_b):
            a_b[i] += g
    return a
