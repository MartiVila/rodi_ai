from enum import Enum

class Datas:
    """
    Base de dades estàtica (Configuració).
    Conté la definició de la línia R1, estacions, connexions i temps de parada.
    """

    # Temps (minuts) que un tren ha d'esperar obligatòriament a cada estació
    STOP_STA_TIME = 0.5  # 30 segons de parada tècnica

    # Llista ordenada d'estacions (R1 Nord)
    R1_STA = [
        "L'HOSPITALET DE LLOBREGAT", "BARCELONA-SANTS", "PLACA DE CATALUNYA",
        "ARC DE TRIOMF", "BARCELONA-CLOT-ARAGO", "SANT ADRIA DE BESOS",
        "BADALONA", "MONTGAT", "MONTGAT-NORD", "EL MASNOU", "OCATA",
        "PREMIA DE MAR", "VILASSAR DE MAR", "CABRERA DE MAR-VILASSAR DE MAR",
        "MATARO", "SANT ANDREU DE LLAVANERES", "ARENYS DE MAR", "CANET DE MAR",
        "SANT POL DE MAR", "CALELLA", "PINEDA DE MAR", "SANTA SUSANNA",
        "MALGRAT DE MAR", "BLANES", "TORDERA"
    ]

    R1_SIDING_STA = {
        "BARCELONA-SANTS", "ARC DE TRIOMF", "BADALONA", "MATARO",
        "ARENYS DE MAR", "CALELLA", "BLANES"
    }

    R1_CONNECTIONS = [
        ("L'HOSPITALET DE LLOBREGAT", "BARCELONA-SANTS"),
        ("BARCELONA-SANTS", "PLACA DE CATALUNYA"),
        ("PLACA DE CATALUNYA", "ARC DE TRIOMF"),
        ("ARC DE TRIOMF", "BARCELONA-CLOT-ARAGO"),
        ("BARCELONA-CLOT-ARAGO", "SANT ADRIA DE BESOS"),
        ("SANT ADRIA DE BESOS", "BADALONA"),
        ("BADALONA", "MONTGAT"),
        ("MONTGAT", "MONTGAT-NORD"),
        ("MONTGAT-NORD", "EL MASNOU"),
        ("EL MASNOU", "OCATA"),
        ("OCATA", "PREMIA DE MAR"),
        ("PREMIA DE MAR", "VILASSAR DE MAR"),
        ("VILASSAR DE MAR", "CABRERA DE MAR-VILASSAR DE MAR"),
        ("CABRERA DE MAR-VILASSAR DE MAR", "MATARO"),
        ("MATARO", "SANT ANDREU DE LLAVANERES"),
        ("SANT ANDREU DE LLAVANERES", "ARENYS DE MAR"),
        ("ARENYS DE MAR", "CANET DE MAR"),
        ("CANET DE MAR", "SANT POL DE MAR"),
        ("SANT POL DE MAR", "CALELLA"),
        ("CALELLA", "PINEDA DE MAR"),
        ("PINEDA DE MAR", "SANTA SUSANNA"),
        ("SANTA SUSANNA", "MALGRAT DE MAR"),
        ("MALGRAT DE MAR", "BLANES"),
        ("BLANES", "TORDERA"),
    ]

    AGENT_ACTIONS = {
        0: "ACELERAR",
        1: "MANTENER",
        2: "FRENAR",
        3: "CANVI" 
    }

    # [NOU] TEMPS REALS EXTRETS DE L'HORARI (PDF R1 2025) [cite: 40, 41, 46, 51]
    # Format: (Origen, Desti): Minuts
    R1_SEGMENT_TIMES = {
        ("L'HOSPITALET DE LLOBREGAT", "BARCELONA-SANTS"): 5,
        ("BARCELONA-SANTS", "PLACA DE CATALUNYA"): 4,
        ("PLACA DE CATALUNYA", "ARC DE TRIOMF"): 3,
        ("ARC DE TRIOMF", "BARCELONA-CLOT-ARAGO"): 4,
        ("BARCELONA-CLOT-ARAGO", "SANT ADRIA DE BESOS"): 5,
        ("SANT ADRIA DE BESOS", "BADALONA"): 3,
        ("BADALONA", "MONTGAT"): 3,
        ("MONTGAT", "MONTGAT-NORD"): 2,
        ("MONTGAT-NORD", "EL MASNOU"): 3,
        ("EL MASNOU", "OCATA"): 2,
        ("OCATA", "PREMIA DE MAR"): 3,
        ("PREMIA DE MAR", "VILASSAR DE MAR"): 3,
        ("VILASSAR DE MAR", "CABRERA DE MAR-VILASSAR DE MAR"): 3,
        ("CABRERA DE MAR-VILASSAR DE MAR", "MATARO"): 4,
        ("MATARO", "SANT ANDREU DE LLAVANERES"): 5,
        ("SANT ANDREU DE LLAVANERES", "ARENYS DE MAR"): 5,
        ("ARENYS DE MAR", "CANET DE MAR"): 5,
        ("CANET DE MAR", "SANT POL DE MAR"): 4,
        ("SANT POL DE MAR", "CALELLA"): 4,
        ("CALELLA", "PINEDA DE MAR"): 4,
        ("PINEDA DE MAR", "SANTA SUSANNA"): 3,
        ("SANTA SUSANNA", "MALGRAT DE MAR"): 3,
        ("MALGRAT DE MAR", "BLANES"): 6,
        ("BLANES", "TORDERA"): 6
    }

    @staticmethod
    def get_travel_time(station_a, station_b):
        """Retorna el temps oficial entre dues estacions (bidireccional)."""
        # Intentem buscar la parella directa
        t = Datas.R1_SEGMENT_TIMES.get((station_a, station_b))
        if t is not None: return t
        
        # Intentem buscar la inversa (tornada)
        t = Datas.R1_SEGMENT_TIMES.get((station_b, station_a))
        if t is not None: return t
        
        return 4.0 # Fallback per defecte