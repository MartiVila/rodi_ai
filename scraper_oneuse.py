#One use scrapper to get  connections and links between stations
import requests
from bs4 import BeautifulSoup #Using this library cause the stations are impregentated in the structure of the website

# URL of the R3 line (Vic, Torelló, Centelles, etc.)
url = "http://www.trenscat.com/renfe/r3_ct.html"

# Make the request
response = requests.get(url)
soup = BeautifulSoup(response.content, "html.parser")

# Find stations by looking for <div> elements with a specific class
stations = []
station_divs = soup.find_all("div", class_="ctnEstacions")
for div in station_divs:
    station_name = div.get_text(strip=True)
    if station_name:  # Ensure the name is not empty
        stations.append(station_name)

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