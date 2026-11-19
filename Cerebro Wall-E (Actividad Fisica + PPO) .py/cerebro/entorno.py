"""Entorno de actividad: el Simulador mas la recompensa del Cerebro.

API propia (reset/step), no Gymnasium: el repo no depende de numpy, y
gymnasium lo arrastra. Misma forma de siempre:
    obs, info = entorno.reset()
    obs, recompensa, terminado, truncado, info = entorno.step(accion)
"""
from __future__ import annotations

from .rutas import conectar_simulador

conectar_simulador()

from simulador.entorno import TAM_OBSERVACION, Escena  # noqa: E402
from simulador.fisica import N_ACCIONES  # noqa: E402

from .recompensa import CalculadoraRecompensa, PesosRecompensa  # noqa: E402


class EntornoActividad:
    """Observacion: TAM_OBSERVACION flotantes. Acciones: N_ACCIONES discretas."""

    def __init__(self, escenario: str = "chatarreria", semilla: int | None = None,
                 pesos: PesosRecompensa | None = None, render_mode: str | None = None) -> None:
        self.escenario = escenario
        self.semilla = semilla
        self.render_mode = render_mode
        self.escena = Escena(escenario, semilla=semilla)
        self.recompensa = CalculadoraRecompensa(pesos)
        self.tam_observacion = TAM_OBSERVACION
        self.n_acciones = N_ACCIONES
        self.episodios = 0
        self._dibujante = None
        self._pantalla = None
        self._reloj = None

    # --- API --------------------------------------------------------------
    def reset(self, semilla: int | None = None):
        if semilla is not None and semilla != self.semilla:
            self.semilla = semilla
            self.escena = Escena(self.escenario, semilla=semilla)
            self._dibujante = None
        self.escena.reiniciar()
        self.recompensa.reiniciar()
        return self.escena.observacion(), self._info()

    def step(self, accion: int):
        eventos, terminado, truncado = self.escena.paso(int(accion))
        recompensa = self.recompensa.evaluar(eventos, self.escena.mundo, terminado)
        obs = self.escena.observacion()
        if terminado or truncado:
            self.episodios += 1
        if self.render_mode == "human":
            self.render()
        return obs, float(recompensa), bool(terminado), bool(truncado), self._info(eventos)

    def _info(self, eventos: dict | None = None) -> dict:
        estado = self.escena.mundo.estado()
        info = {
            "bateria": estado["bateria"],
            "recogidas": estado["recogidas"],
            "entregadas": estado["entregadas"],
            "distancia": estado["distancia"],
            "calorias": estado["calorias"],
            "cobertura": estado["cobertura"],
            "colisiones": estado["colisiones"],
            "pasos": estado["pasos"],
        }
        if eventos:
            info["entregado"] = eventos["entregado"]
            info["recogido"] = eventos["recogido"]
        return info

    # --- visor opcional (pygame) -----------------------------------------
    def render(self) -> None:
        import pygame

        from simulador.render import Dibujante, tamano_ventana

        if self._dibujante is None or self._pantalla is None:
            pygame.init()
            pygame.display.init()
            pygame.display.set_caption("Cerebro WALL-E - PPO")
            ancho, alto = tamano_ventana(self.escena)
            self._pantalla = pygame.display.set_mode((ancho, alto))
            self._dibujante = Dibujante(self.escena, ancho, alto)
            self._reloj = pygame.time.Clock()
        pygame.event.pump()
        self._pantalla.blit(self._dibujante.dibujar("politica PPO en vivo"), (0, 0))
        pygame.display.flip()
        self._reloj.tick(30)

    def close(self) -> None:
        if self._dibujante is not None:
            import pygame

            pygame.display.quit()
            pygame.quit()
            self._dibujante = None
            self._pantalla = None


__all__ = ["EntornoActividad", "TAM_OBSERVACION", "N_ACCIONES"]
