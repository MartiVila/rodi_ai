import requests
from bs4 import BeautifulSoup
import re

url = "https://cercanias.info/en/rodalies-catalunya/lines/r1-molins-de-rei-macanet-massanes-by-mataro"

response = requests.get(url)
soup = BeautifulSoup(response.content, "html.parser")

station_elements = soup.find_all("p", class_="text-xl font-medium leading-6")

stations = []
for name_element in station_elements:
    station_name = name_element.get_text(strip=True)
    stations.append(station_name)

print("Stations found:", stations)


connections = []
for i in range(len(stations) - 1):
    connections.append((stations[i], stations[i + 1]))

for conn in connections:
    print(f"{conn[0]} - {conn[1]}")

#Ficar el reutnr quan def