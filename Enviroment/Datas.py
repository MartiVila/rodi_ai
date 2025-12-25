from enum import Enum

class Datas:
    """
    Base de dades estàtica (Configuració).
    Conté la definició de la línia R1, estacions, connexions i temps de parada.
    """

    # Temps (minuts) que un tren ha d'esperar obligatòriament a cada estació
    STOP_STA_TIME = 0.5  # Ex: 30 segons

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

    # Estacions amb capacitat d'apartador (on es poden fer avançaments teòrics)
    R1_SIDING_STA = {
        "BARCELONA-SANTS", "ARC DE TRIOMF", "BADALONA", "MATARO",
        "ARENYS DE MAR", "CALELLA", "BLANES"
    }

    # Definició de parelles de connexió (Topologia)
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

    # Mapeig d'accions per debug
    AGENT_ACTIONS = {
        0: "ACELERAR",
        1: "MANTENER",
        2: "FRENAR",
        3: "CANVI" 
    }