"""Tu bot: la clase ``Bot``.

Es el fichero que juega las partidas. Se entrega junto con tus tests y el
notebook (enunciado de la práctica, «Qué entregas»).

El motor crea el bot una vez por partida con ``Bot(seed)`` y llama a
``decide(state)`` una vez por tick. ``state`` es un diccionario normalizado:
tu raqueta está siempre a la izquierda (cara frontal en x = 30) y la bola se acerca
cuando ``ball_x`` decrece. Las constantes del campo están en ``state["field"]``.

El estado no incluye la velocidad ni el efecto: tienes que estimarlos a partir
de posiciones sucesivas, guardándolas en atributos de la instancia (enunciado,
apartado 3.3, «Estimación cinemática»).

Este punto de partida solo sigue la ordenada de la bola, como el bot de
referencia Easy. Pierde contra Medium y Hard: tu trabajo es mejorarlo.
"""

from __future__ import annotations


class Bot:
    """Bot de Pong."""

    def __init__(self, seed: int) -> None:
        """Inicializa el bot.

        Args:
            seed: semilla para un ``random.Random`` propio, si tu bot usa azar.
        """
        self.seed = seed

    def decide(self, state: dict) -> str:
        """Devuelve ``"UP"``, ``"DOWN"`` o ``"STAY"`` para este tick.

        Args:
            state: estado normalizado de la partida (enunciado, apartado 3.2).

        Returns:
            El comando de la raqueta. Cualquier otro valor, o una excepción,
            cuenta como ``"STAY"``.
        """
        diff = state["ball_y"] - state["my_paddle_y"]
        if diff > 4.0:
            return "DOWN"
        if diff < -4.0:
            return "UP"
        return "STAY"
