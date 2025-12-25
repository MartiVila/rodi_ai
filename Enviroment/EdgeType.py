from enum import Enum

class EdgeType(Enum):
    """
    Enumeració que defineix els tipus de via possibles.
    
    Valors:
    - NORMAL (1): Via estàndard, velocitat nominal alta (ex: 120-160 km/h).
    - OBSTACLE (2): Via malmesa o amb incidència, velocitat molt reduïda (ex: 10 km/h).
    """
    NORMAL = 1
    OBSTACLE = 2
    # URBAN = 3  # Reservat per a futures expansions (trams urbans lents)