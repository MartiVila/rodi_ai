
from bs4 import BeautifulSoup
import requests
import time
import random
import unicodedata
import re
import pathlib

def normalize_station_name(name):
    # Remove accents
    name = unicodedata.normalize('NFD', name)
    name = name.encode('ascii', 'ignore').decode('utf-8')
    # Uppercase everything
    name = name.upper()
    return name

def scrape_rodalies_line_stations(url):
    # Set headers to look like a standard browser request
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    # Introduce a small, mandatory random delay before fetching
    time.sleep(random.uniform(1, 3)) 
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Catches 4xx, 5xx errors like 503
        soup = BeautifulSoup(response.content, 'html.parser')
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching {url}: {e}")
        return [] # Return empty list on server error
    except requests.exceptions.RequestException as e:
        print(f"Connection Error fetching {url}: {e}")
        return []

    # 1. Try multiple strategies to locate station name elements. The site may change
    # structure or block requests; we try robust fallbacks.
    stations = []

    # Primary: ordered list with recognizable class
    station_list_ol = soup.find('ol', class_=lambda c: c and 'train-line-space' in c)
    if station_list_ol:
        elems = station_list_ol.select('li p.text-xl') or station_list_ol.select('li p')
    else:
        elems = []

    # Fallback 1: any <p class="text-xl"> anywhere
    if not elems:
        elems = soup.select('p.text-xl')

    # Fallback 2: any list items with a paragraph inside
    if not elems:
        elems = soup.select('li p')

    # Fallback 3: any anchor texts inside list items (some pages use <a>)
    if not elems:
        elems = soup.select('li a')

    # If still empty, save debug HTML and warn
    if not elems:
        try:
            safe_name = pathlib.Path(url).name or 'page'
            debug_path = f"data/debug_{safe_name}.html"
            pathlib.Path('data').mkdir(parents=True, exist_ok=True)
            with open(debug_path, 'wb') as fh:
                fh.write(response.content)
            print(f"Warning: Could not find the main station list container on {url}; saved page to {debug_path}")
        except Exception:
            print(f"Warning: Could not find the main station list container on {url}")
        return []

    for el in elems:
        raw = el.get_text(separator=' ', strip=True)
        if not raw:
            continue
        name = normalize_station_name(raw)
        # basic filters
        if len(name) < 2:
            continue
        if 'PARKING' in name or re.search(r'\bR\d+\b', name) or 'WC' in name:
            continue
        stations.append(name)

    # 3. Generate connections: Adjacent pairs (Station A, Station B)
    connections = []
    for i in range(len(stations) - 1):
        connections.append((stations[i], stations[i+1]))
    
    if connections:
        print(f"Scraping completed. Found {len(connections)} connections.")
        # Print first few connections for verification
        for s1, s2 in connections[:3]:
            print(f"{s1} - {s2}")
    else:
        print("Scraping completed. Found 0 connections.")
        
    return connections