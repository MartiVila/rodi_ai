from enum import Enum

class EdgeType(Enum):
    """
    Es un enum que definiexi el tipus de via
    
    1  normal
    2 vermella dolenta mes lent
    """
    NORMAL = 1
    OBSTACLE = 2