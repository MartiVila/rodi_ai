from enum import Enum

class Datas():

    """
    Estructura de dades amb la informació de les diferents linies
        Conté:
            - Temps de parada en estació
            - *linia*_STA --> Llista de parades (nodes) de cada linia. ex. R1_STA
            - *linia*_TIME --> Temps que hi ha entre estació i estació
    """

    """
    Dades Generals Estacions
    """

    STOP_STA_TIME = 0  

    """
    ############################################################################################
    ############################################################################################

    Dades PER A CADA VIA (Actualitzat amb noms oficials del CSV):
        - *linia*_STA
        - *linia*_SIDING_STA
        - *linia*_ROUTES
        - *linia*_TIME
        

    ############################################################################################
    ############################################################################################
    
    """

    R1_STA = [
        "L'HOSPITALET DE LLOBREGAT",
        "BARCELONA-SANTS",
        "PLACA DE CATALUNYA",
        "ARC DE TRIOMF",
        "BARCELONA-CLOT-ARAGO",
        "SANT ADRIA DE BESOS",
        "BADALONA",
        "MONTGAT",
        "MONTGAT-NORD",
        "EL MASNOU",
        "OCATA",
        "PREMIA DE MAR",
        "VILASSAR DE MAR",
        "CABRERA DE MAR-VILASSAR DE MAR",
        "MATARO",
        "SANT ANDREU DE LLAVANERES",
        "ARENYS DE MAR",
        "CANET DE MAR",
        "SANT POL DE MAR",
        "CALELLA",
        "PINEDA DE MAR",
        "SANTA SUSANNA",
        "MALGRAT DE MAR",
        "BLANES",
        "TORDERA"
    ]

    # Estacions amb apartador (Noms oficials)
    R1_SIDING_STA = {
        "BARCELONA-SANTS",
        "ARC DE TRIOMF",
        "BADALONA",
        "MATARO",
        "ARENYS DE MAR",
        "CALELLA",
        "BLANES",
    }

    # Cada ruta és una llista d'estacions consecutives a la línia R1
    # Fem servir còpies o slices de la llista principal ja corregida
    R1_ROUTES = [
        # Ruta 0: Completa (L'Hospitalet - Tordera)
        R1_STA.copy(),
        # Ruta 1: Des de Sants
        R1_STA[1:],
        # Ruta 2: Des de Badalona
        R1_STA[6:],
        # Ruta 3: Des de Mataró
        R1_STA[14:],
        # Ruta 4: Des d'Arenys de Mar
        R1_STA[16:],
        # Ruta 5: Des de Calella
        R1_STA[19:],
    ]

    # Temps entre estacions (Claus actualitzades)
    R1_TIME = {
        ("L'HOSPITALET DE LLOBREGAT", "BARCELONA-SANTS"): 3,
        ("BARCELONA-SANTS", "PLACA DE CATALUNYA"): 3,
        ("PLACA DE CATALUNYA", "ARC DE TRIOMF"): 3,
        ("ARC DE TRIOMF", "BARCELONA-CLOT-ARAGO"): 3,
        ("BARCELONA-CLOT-ARAGO", "SANT ADRIA DE BESOS"): 4,
        ("SANT ADRIA DE BESOS", "BADALONA"): 5,
        ("BADALONA", "MONTGAT"): 4,
        ("MONTGAT", "MONTGAT-NORD"): 2,
        ("MONTGAT-NORD", "EL MASNOU"): 3,
        ("EL MASNOU", "OCATA"): 3,
        ("OCATA", "PREMIA DE MAR"): 3,
        ("PREMIA DE MAR", "VILASSAR DE MAR"): 3,
        ("VILASSAR DE MAR", "CABRERA DE MAR-VILASSAR DE MAR"): 2,
        ("CABRERA DE MAR-VILASSAR DE MAR", "MATARO"): 3,
        ("MATARO", "SANT ANDREU DE LLAVANERES"): 4,
        ("SANT ANDREU DE LLAVANERES", "ARENYS DE MAR"): 4,
        ("ARENYS DE MAR", "CANET DE MAR"): 3,
        ("CANET DE MAR", "SANT POL DE MAR"): 3,
        ("SANT POL DE MAR", "CALELLA"): 3,
        ("CALELLA", "PINEDA DE MAR"): 3,
        ("PINEDA DE MAR", "SANTA SUSANNA"): 3,
        ("SANTA SUSANNA", "MALGRAT DE MAR"): 3,
        ("MALGRAT DE MAR", "BLANES"): 3,
        ("BLANES", "TORDERA"): 5,
    }

    """
    ############################################################################################
    ############################################################################################

    Dades PER A L'AGENT
        

    ############################################################################################
    ############################################################################################
    
    """
    AGENT_ACTIONS = {
        0: "ACELERAR",
        1: "MANTENER",
        2: "FRENAR",
        3: "APARTAR (Apartadero)"
    }