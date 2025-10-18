import requests
from bs4 import BeautifulSoup
import unicodedata

def normalize_station_name(name):
    # Remove accents
    name = unicodedata.normalize('NFD', name)
    name = name.encode('ascii', 'ignore').decode('utf-8')
    # Uppercase everything
    name = name.upper()
    return name

def scrape_rodalies_line_stations(url):

    url = "https://cercanias.info/en/rodalies-catalunya/lines/r1-molins-de-rei-macanet-massanes-by-mataro"

    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    station_elements = soup.find_all("p", class_="text-xl font-medium leading-6")

    stations = []
    for name_element in station_elements:
        station_name = name_element.get_text(strip=True)
        station_name = normalize_station_name(station_name)
        stations.append(station_name)

    print("Stations found by the scrapper:", stations)

    #We have to fill a list of tuples with the connections between stations
    #This way the model will be able to create the graph
    connections = []
    for i in range(len(stations) - 1):
        connections.append((stations[i], stations[i + 1]))

    for connection in connections:
        print(f"{connection[0]} - {connection[1]}")

    print("Scraping completed.", url)

    return connections

