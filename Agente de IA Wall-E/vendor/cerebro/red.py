"""Red neuronal minima escrita a mano: sin torch, sin numpy.

Motivo: el repo tiene que correr en un Python limpio. Este modulo implementa
las dos capas densas del actor-critico, el softmax y la retropropagacion
completa (politica + valor) con Adam. El gradiente se verifica por
diferencias finitas en `pruebas.py`; si se toca una formula, ahi se rompe.

Convencion: `adelante` guarda activaciones y sumas ponderadas para que
`retropropagar` no las recalcule.
"""
from __future__ import annotations

import math
import random

TANH = math.tanh


class Lineal:
    """Capa densa con estado de Adam por parametro."""

    __slots__ = ("entradas", "salidas", "pesos", "sesgos", "m_w", "v_w", "m_b", "v_b")

    def __init__(self, entradas: int, salidas: int, rng: random.Random, ganancia: float = 1.0) -> None:
        self.entradas = entradas
        self.salidas = salidas
        limite = ganancia * math.sqrt(6.0 / (entradas + salidas))
        self.pesos = [[rng.uniform(-limite, limite) for _ in range(entradas)] for _ in range(salidas)]
        self.sesgos = [0.0] * salidas
        self.m_w = [[0.0] * entradas for _ in range(salidas)]
        self.v_w = [[0.0] * entradas for _ in range(salidas)]
        self.m_b = [0.0] * salidas
        self.v_b = [0.0] * salidas

    def adelante(self, x: list[float]) -> list[float]:
        pesos = self.pesos
        salida = []
        for fila, sesgo in zip(pesos, self.sesgos):
            acumulado = sesgo
            for w, v in zip(fila, x):
                acumulado += w * v
            salida.append(acumulado)
        return salida

    def gradientes(self, x: list[float], g_salida: list[float]) -> tuple[list[list[float]], list[float]]:
        g_pesos = [[g * v for v in x] for g in g_salida]
        return g_pesos, list(g_salida)

    def retro(self, g_salida: list[float]) -> list[float]:
        """Gradiente respecto a la entrada, dado el de la salida."""
        pesos = self.pesos
        return [sum(pesos[j][i] * g_salida[j] for j in range(self.salidas))
                for i in range(self.entradas)]


class RedActorCritica:
    """Tronco tanh + cabeza de politica (logits) + cabeza de valor (escalar)."""

    def __init__(self, tam_obs: int, n_acciones: int, ocultas: tuple[int, int] = (48, 48),
                 rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random(0)
        self.tam_obs = tam_obs
        self.n_acciones = n_acciones
        self.ocultas = ocultas
        capas: list[Lineal] = []
        anterior = tam_obs
        for ancho in ocultas:
            capas.append(Lineal(anterior, ancho, self.rng))
            anterior = ancho
        self.tronco = capas
        self.cabeza_politica = Lineal(anterior, n_acciones, self.rng, ganancia=0.1)
        self.cabeza_valor = Lineal(anterior, 1, self.rng)

    # --- forward ----------------------------------------------------------
    def adelante(self, obs: list[float]) -> tuple[list[float], float, tuple]:
        activaciones = [obs]
        sumas: list[list[float]] = []
        x = obs
        for capa in self.tronco:
            z = capa.adelante(x)
            sumas.append(z)
            x = [TANH(v) for v in z]
            activaciones.append(x)
        logits = self.cabeza_politica.adelante(x)
        valor = self.cabeza_valor.adelante(x)[0]
        return logits, valor, (activaciones, sumas)

    def logits_y_valor(self, obs: list[float]) -> tuple[list[float], float]:
        logits, valor, _ = self.adelante(obs)
        return logits, valor

    # --- backward ---------------------------------------------------------
    def retropropagar(self, cache, g_logits: list[float], g_valor: float) -> list[tuple]:
        """Devuelve [(g_pesos, g_sesgos), ...] en el orden de los parametros."""
        activaciones, _ = cache
        x_final = activaciones[-1]
        gradientes: list[tuple] = []

        g_pol_w, g_pol_b = self.cabeza_politica.gradientes(x_final, g_logits)
        g_val_w, g_val_b = self.cabeza_valor.gradientes(x_final, [g_valor])

        g_entrada = self.cabeza_politica.retro(g_logits)
        g_entrada_valor = self.cabeza_valor.retro([g_valor])
        g_entrada = [a + b for a, b in zip(g_entrada, g_entrada_valor)]

        gradientes_tronco: list[tuple] = []
        for idx in reversed(range(len(self.tronco))):
            activacion = activaciones[idx + 1]
            g_z = [g_entrada[i] * (1.0 - activacion[i] * activacion[i]) for i in range(len(g_entrada))]
            g_w, g_b = self.tronco[idx].gradientes(activaciones[idx], g_z)
            gradientes_tronco.append((g_w, g_b))
            g_entrada = self.tronco[idx].retro(g_z)
        gradientes_tronco.reverse()

        gradientes.extend(gradientes_tronco)
        gradientes.append((g_pol_w, g_pol_b))
        gradientes.append((g_val_w, g_val_b))
        return gradientes

    # --- utilidades -------------------------------------------------------
    def parametros(self):
        """Genera (objeto_lineal, matriz_w, vector_b) para Adam."""
        for capa in self.tronco:
            yield capa
        yield self.cabeza_politica
        yield self.cabeza_valor

    def norma_gradientes(self, gradientes: list[tuple]) -> float:
        total = 0.0
        for g_w, g_b in gradientes:
            for fila in g_w:
                for g in fila:
                    total += g * g
            for g in g_b:
                total += g * g
        return math.sqrt(total)

    def escalar_gradientes(self, gradientes: list[tuple], factor: float) -> list[tuple]:
        return [
            ([[g * factor for g in fila] for fila in g_w], [g * factor for g in g_b])
            for g_w, g_b in gradientes
        ]

    def sumar_gradientes(self, gradientes: list[tuple]) -> list[tuple]:
        """Reduce una lista de gradientes por parametro a su suma."""
        if not gradientes:
            raise ValueError("lista de gradientes vacia")
        acumulado = gradientes[0]
        for g_w, g_b in gradientes[1:]:
            for j, fila in enumerate(g_w):
                destino = acumulado[0][j]
                for i, g in enumerate(fila):
                    destino[i] += g
            for j, g in enumerate(g_b):
                acumulado[1][j] += g
        return acumulado

    def aplicar_adam(self, gradientes: list[tuple], lr: float, paso: int,
                     beta1: float = 0.9, beta2: float = 0.999, eps: float = 1e-8) -> None:
        """Un paso de Adam sobre todos los parametros de la red."""
        b1t = 1.0 - beta1 ** paso
        b2t = 1.0 - beta2 ** paso
        for capa, (g_w, g_b) in zip(self.parametros(), gradientes):
            for j in range(capa.salidas):
                fila_pesos = capa.pesos[j]
                fila_m = capa.m_w[j]
                fila_v = capa.v_w[j]
                fila_g = g_w[j]
                for i in range(capa.entradas):
                    g = fila_g[i]
                    fila_m[i] = beta1 * fila_m[i] + (1.0 - beta1) * g
                    fila_v[i] = beta2 * fila_v[i] + (1.0 - beta2) * g * g
                    m_hat = fila_m[i] / b1t
                    v_hat = fila_v[i] / b2t
                    fila_pesos[i] -= lr * m_hat / (math.sqrt(v_hat) + eps)
                g = g_b[j]
                capa.m_b[j] = beta1 * capa.m_b[j] + (1.0 - beta1) * g
                capa.v_b[j] = beta2 * capa.v_b[j] + (1.0 - beta2) * g * g
                m_hat = capa.m_b[j] / b1t
                v_hat = capa.v_b[j] / b2t
                capa.sesgos[j] -= lr * m_hat / (math.sqrt(v_hat) + eps)

    # --- serializacion ----------------------------------------------------
    def a_diccionario(self) -> dict:
        return {
            "tam_obs": self.tam_obs,
            "n_acciones": self.n_acciones,
            "ocultas": list(self.ocultas),
            "parametros": [
                {"pesos": capa.pesos, "sesgos": capa.sesgos} for capa in self.parametros()
            ],
        }

    @classmethod
    def desde_diccionario(cls, datos: dict) -> "RedActorCritica":
        red = cls(int(datos["tam_obs"]), int(datos["n_acciones"]), tuple(datos["ocultas"]))
        for capa, guardada in zip(red.parametros(), datos["parametros"]):
            capa.pesos = [[float(v) for v in fila] for fila in guardada["pesos"]]
            capa.sesgos = [float(v) for v in guardada["sesgos"]]
        return red


def softmax(logits: list[float]) -> list[float]:
    maximo = max(logits)
    exps = [math.exp(v - maximo) for v in logits]
    total = sum(exps)
    return [v / total for v in exps]


def log_softmax(logits: list[float]) -> list[float]:
    maximo = max(logits)
    desplazados = [v - maximo for v in logits]
    log_total = math.log(sum(math.exp(v) for v in desplazados))
    return [v - log_total for v in desplazados]
