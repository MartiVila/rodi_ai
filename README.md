# RODI_AI

Simulador i entorn d'aprenentatge per reforç (Q-learning) orientat a la gestió/simulació de trànsit ferroviari tipus Rodalies. El projecte inclou:

- Un entorn de simulació (nodes, arestes, trens i un gestor de trànsit)
- Un agent de Q-learning amb taules Q
- Scripts de simulació/entrenament
- Eines de scraping i un petit servidor web per visualitzar trens en temps real (si s'utilitzen les dades corresponents)

## Requisits

- Python 3.10+ (recomanat)
- Dependències Python: vegeu [requirements.txt](requirements.txt)

## Instal·lació

Opció recomanada amb entorn virtual:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Si tens problemes amb `pygame` a Linux, pot ser necessari instal·lar paquets del sistema (SDL, etc.) segons la teva distribució.

## Com executar

### Simulació / UI (pygame)

Executa l'aplicació principal (interfície i simulació):

```bash
python RodaliesAI_Refactor.py
```

### Entrenament (Q-learning)

Script d'entrenament i generació de resultats:

```bash
python Rodalies_training.py
```

Nota: l'entrenament pot crear/actualitzar fitxers a `Agent/Qtables/` i informes/plots en carpetes com `Agent/Plots_Exhaustius/` o `Enviroment/informe_exhaustiu/`.

### Scraping i mapa en temps real

- Scraper (petició i persistència de dades):

```bash
python Scrapers/scraper_directe.py
```

- Servidor web per visualitzar dades (Flask):

```bash
python Scrapers/realtime_trains_map.py
```

Per defecte, aquests scripts treballen amb fitxers JSON a `Scrapers/data/`.

## Estructura del repositori

- `Agent/`
	- `QlearningAgent.py`: implementació de l'agent
	- `Qtables/`: taules Q serialitzades (`.json`, `.pkl`)
	- `Plots_Exhaustius/`: gràfiques/figures generades
- `Enviroment/`
	- `TrafficManager.py`, `Train.py`, `Node.py`, `Edge.py`, `EdgeType.py`: lògica de l'entorn
	- `data/`: dades de suport (p. ex. coordenades d'estacions)
	- `informe_exhaustiu/`: informes i resultats d'experiments
- `Scrapers/`
	- `scraper_directe.py`: obtenció de dades
	- `realtime_trains_map.py`: visualització via web
	- `data/`: cache/últimes dades descarregades
- `RodaliesAI_Refactor.py`: entrada principal (simulació amb `pygame`)
- `Rodalies_training.py`: script d'entrenament

## Notes

- El projecte inclou fitxers de dades i resultats (CSV/JSON/PNG) dins del repositori.
- Si vols reduir la mida del repo, es poden ignorar plots i artefactes d'entrenament i regenerar-los quan calgui.

## Llicència

Aquest projecte està destinat a finalitats acadèmiques i de recerca.
Per a altres usos, contactar amb els autors.
