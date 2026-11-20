"""Bot de referencia Easy: reactivo, sigue la ordenada de la bola.

Enunciado de la práctica, apartado 3.5.

Es el único bot de referencia con código fuente en la plantilla. Ganarle
certifica que tu bot funciona: está donde llega la bola.
"""


class Easy:
    """Mueve la raqueta hacia ``ball_y`` con una zona muerta de 4 px."""

    DEAD_ZONE = 4.0

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def decide(self, state: dict) -> str:
        diff = state["ball_y"] - state["my_paddle_y"]
        if diff > self.DEAD_ZONE:
            return "DOWN"
        if diff < -self.DEAD_ZONE:
            return "UP"
        return "STAY"
