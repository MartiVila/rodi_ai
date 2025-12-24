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
        3: "CANVI" 
    }