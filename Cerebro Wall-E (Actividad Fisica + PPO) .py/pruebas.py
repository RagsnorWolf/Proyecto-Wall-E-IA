"""Pruebas del Cerebro: gradiente por diferencias finitas y contrato del entorno.

    python -m unittest -v pruebas

La prueba del gradiente es la que importa: si alguien toca `_gradiente_muestra`
o `retropropagar` y el signo se va, aqui truena antes de entrenar 60.000 pasos
para nada.
"""
from __future__ import annotations

import math
import random
import unittest

from cerebro import EntornoActividad, Hiperparametros
from cerebro.ppo import AgentePPO
from cerebro.red import RedActorCritica, log_softmax, softmax


def _perdida(red: RedActorCritica, obs, accion: int, logprob_viejo: float,
             ventaja: float, retorno: float, hp: Hiperparametros) -> float:
    """La misma perdida PPO escrita de forma independiente para el test."""
    logits, valor, _ = red.adelante(list(obs))
    lps = log_softmax(logits)
    probabilidades = softmax(logits)
    razon = math.exp(lps[accion] - logprob_viejo)
    sin_recorte = razon * ventaja
    recortada = min(max(razon, 1.0 - hp.recorte), 1.0 + hp.recorte) * ventaja
    entropia = -sum(p * lp for p, lp in zip(probabilidades, lps))
    return (
        -min(sin_recorte, recortada)
        + hp.coef_valor * (valor - retorno) ** 2
        - hp.coef_entropia * entropia
    )


class PruebaGradiente(unittest.TestCase):
    def setUp(self) -> None:
        self.hp = Hiperparametros(ocultas=(4, 3), coef_entropia=0.05)
        self.agente = AgentePPO(3, 3, self.hp, semilla=11)
        self.obs = [0.3, -0.7, 0.55]
        self.accion = 1
        self.logprob_viejo = -1.05
        self.ventaja = 0.8
        self.retorno = 0.4

    def test_gradiente_coincide_con_diferencias_finitas(self) -> None:
        agente = self.agente
        gradientes, _ = agente._gradiente_muestra(
            self.obs, self.accion, self.logprob_viejo, self.ventaja, self.retorno
        )
        eps = 1e-6
        peor = 0.0
        for capa, (g_w, g_b) in zip(agente.red.parametros(), gradientes):
            for j in range(capa.salidas):
                for i in range(capa.entradas):
                    original = capa.pesos[j][i]
                    capa.pesos[j][i] = original + eps
                    alta = _perdida(agente.red, self.obs, self.accion,
                                    self.logprob_viejo, self.ventaja, self.retorno, self.hp)
                    capa.pesos[j][i] = original - eps
                    baja = _perdida(agente.red, self.obs, self.accion,
                                    self.logprob_viejo, self.ventaja, self.retorno, self.hp)
                    capa.pesos[j][i] = original
                    numerico = (alta - baja) / (2 * eps)
                    peor = max(peor, abs(numerico - g_w[j][i]))
                original_sesgo = capa.sesgos[j]
                capa.sesgos[j] = original_sesgo + eps
                alta = _perdida(agente.red, self.obs, self.accion,
                                self.logprob_viejo, self.ventaja, self.retorno, self.hp)
                capa.sesgos[j] = original_sesgo - eps
                baja = _perdida(agente.red, self.obs, self.accion,
                                self.logprob_viejo, self.ventaja, self.retorno, self.hp)
                capa.sesgos[j] = original_sesgo
                numerico = (alta - baja) / (2 * eps)
                peor = max(peor, abs(numerico - g_b[j]))
        self.assertLess(peor, 1e-4, f"error maximo del gradiente: {peor:.3e}")

    def test_softmax_suma_uno(self) -> None:
        logits = [0.4, -1.2, 2.1, 0.0]
        self.assertAlmostEqual(sum(softmax(logits)), 1.0, places=12)
        lps = log_softmax(logits)
        for p, lp in zip(softmax(logits), lps):
            self.assertAlmostEqual(math.log(p), lp, places=10)

    def test_muestreo_respeta_el_rango(self) -> None:
        agente = AgentePPO(3, 3, self.hp, semilla=3)
        obs = [0.0, 0.0, 0.0]
        for _ in range(200):
            accion, logprob, valor = agente.actuar(obs)
            self.assertIn(accion, (0, 1, 2))
            self.assertLessEqual(logprob, 0.01)
            self.assertTrue(math.isfinite(valor))


class PruebaEntorno(unittest.TestCase):
    def test_contrato_de_episodio(self) -> None:
        entorno = EntornoActividad("chatarreria", semilla=5)
        obs, info = entorno.reset()
        self.assertEqual(len(obs), entorno.tam_observacion)
        self.assertIn("bateria", info)
        terminado = truncado = False
        pasos = 0
        while not (terminado or truncado) and pasos < 3000:
            obs, recompensa, terminado, truncado, info = entorno.step(pasos % entorno.n_acciones)
            self.assertEqual(len(obs), entorno.tam_observacion)
            self.assertTrue(math.isfinite(recompensa))
            pasos += 1
        self.assertLess(pasos, 3000, "el episodio no termino nunca")
        entorno.close()

    def test_rodar_en_el_sitio_no_paga(self) -> None:
        """El giro no produce cobertura ni distancia: no puede haber premio."""
        entorno = EntornoActividad("patio", semilla=9)
        entorno.reset()
        total = 0.0
        for _ in range(80):
            _, recompensa, terminado, truncado, _ = entorno.step(1)  # girar izquierda
            total += recompensa
            if terminado or truncado:
                break
        self.assertLess(total, 0.0, "girar en el sitio no debe dar recompensa positiva")
        entorno.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
