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

    Dades PER A CADA VIA, amb aquest Ordre:
        - *linia*_STA --> Llista de parades (nodes) de cada linia. ex. R1_STA
        - *linia*_SIDING_STA --> Llista de parades (nodes) de cada linia AMB APARTADEROS. 
        - *linia*_ROUTES --> Llista de Les diferents RUTES de cada linia. 
        - *linia*_TIME --> Temps que hi ha entre estació i estació
        

    ############################################################################################
    ############################################################################################
    
    """

    R1_STA = [
        "L'Hospitalet de Llobregat",
        "Barcelona - Sants",
        "Barcelona - Pl. Catalunya",
        "Barcelona - Arc de Triomf",
        "Barcelona - El Clot",
        "St. Adrià de Besòs",
        "Badalona",
        "Montgat",
        "Montgat Nord",
        "El Masnou",
        "Ocata",
        "Premià de Mar",
        "Vilassar de Mar",
        "Cabrera de Mar - Vilassar de Mar",
        "Mataró",
        "St. Andreu de Llavaneres",
        "Arenys de Mar",
        "Canet de Mar",
        "St. Pol de Mar",
        "Calella",
        "Pineda de Mar",
        "Santa Susanna",
        "Malgrat de Mar",
        "Blanes",
        "Tordera"
    ]

    # Estaciones con apartadero disponibles (configurable) - principales de R1
    R1_SIDING_STA = {
        "Barcelona - Sants",
        "Barcelona - Arc de Triomf",
        "Badalona",
        "Mataró",
        "Arenys de Mar",
        "Calella",
        "Blanes",
    }

    # Cada ruta es una lista de estaciones consecutivas en la línea R1
    R1_ROUTES = [
        # Ruta 0: Completa (L'Hospitalet - Tordera)
        R1_STA.copy(),
        # Ruta 1: Desde Barcelona - Sants
        R1_STA[1:],
        # Ruta 2: Desde Badalona
        R1_STA[6:],
        # Ruta 3: Desde Mataró
        R1_STA[14:],
        # Ruta 4: Desde Arenys de Mar
        R1_STA[16:],
        # Ruta 5: Desde Calella
        R1_STA[19:],
    ]


    R1_TIME = {
        ("L'Hospitalet de Llobregat", "Barcelona - Sants"): 3,
        ("Barcelona - Sants", "Barcelona - Pl. Catalunya"): 3,
        ("Barcelona - Pl. Catalunya", "Barcelona - Arc de Triomf"): 3,
        ("Barcelona - Arc de Triomf", "Barcelona - El Clot"): 3,
        ("Barcelona - El Clot", "St. Adrià de Besòs"): 4,
        ("St. Adrià de Besòs", "Badalona"): 5,
        ("Badalona", "Montgat"): 4,
        ("Montgat", "Montgat Nord"): 2,
        ("Montgat Nord", "El Masnou"): 3,
        ("El Masnou", "Ocata"): 3,
        ("Ocata", "Premià de Mar"): 3,
        ("Premià de Mar", "Vilassar de Mar"): 3,
        ("Vilassar de Mar", "Cabrera de Mar - Vilassar de Mar"): 2,
        ("Cabrera de Mar - Vilassar de Mar", "Mataró"): 3,
        ("Mataró", "St. Andreu de Llavaneres"): 4,
        ("St. Andreu de Llavaneres", "Arenys de Mar"): 4,
        ("Arenys de Mar", "Canet de Mar"): 3,
        ("Canet de Mar", "St. Pol de Mar"): 3,
        ("St. Pol de Mar", "Calella"): 3,
        ("Calella", "Pineda de Mar"): 3,
        ("Pineda de Mar", "Santa Susanna"): 3,
        ("Santa Susanna", "Malgrat de Mar"): 3,
        ("Malgrat de Mar", "Blanes"): 3,
        ("Blanes", "Tordera"): 5,
    }



    """
    ############################################################################################
    ############################################################################################

    Dades PER Al agent:
        - AGENT_ACTIONS: Dict amb les accions del agent
        

    ############################################################################################
    ############################################################################################
    
    """
    AGENT_ACTIONS = {
        0: "ACELERAR",
        1: "MANTENER",
        2: "FRENAR",
        3: "APARTAR (Apartadero)"
        }
    
