#One use scrapper to get  connections and links between stations
import requests
from bs4 import BeautifulSoup #Using this library cause the stations are impregentated in the structure of the website

# URL of the R3 line (Vic, Torelló, Centelles, etc.)
url = "https://cercanias.info/en/rodalies-catalunya/lines/r1-molins-de-rei-macanet-massanes-by-mataro"

# Make the request, wich returns the web page
response = requests.get(url)
# sort by just the HTML content of the page
soup = BeautifulSoup(response.content, "html.parser")

# Find stations by looking for <div> elements with a specific class
stations = []
station_lis = soup.find_all("li", class_="group relative min-h-28 pb-3 pl-8")
for li in station_lis.strings:
    print(li)
    station_name = li.get_text(strip=True)
    if station_name:  # Ensure the name is not empty
        stations.append(station_name)

print("Stations found:", stations)
# Build consecutive connections
connections = []
for i in range(len(stations) - 1):
    connections.append({
        "from": stations[i],
        "to": stations[i + 1]
    })

# Display connections
for conn in connections:
    print(f"{conn['from']} ↔ {conn['to']}")