#Scrapper per obtenir dades en temps real dels trens de Renfe cada 30s
import requests
import time
import json
import os
import math

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LATEST_TRAINS_FILE = os.path.join(DATA_DIR, "latest_trains.json")

class Train:
    def __init__(self, id, trip, origin, destination, lat, lon, speed, status):
        self.id = id
        self.trip = trip
        self.origin = origin
        self.destination = destination
        self.lat = lat
        self.lon = lon
        self.speed = speed
        self.status = status

    def __repr__(self):
        return (f"Train(ID: {self.id}, Trip: {self.trip}, "
                f"Position: ({self.lat}, {self.lon}), Status: {self.status})")

def get_train_data(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        trains = []
        
        for entity in data.get('entity', []):
            vehicle_data = entity.get('vehicle', {})
            position = vehicle_data.get('position', {})
            trip = vehicle_data.get('trip', {})

            train_id = vehicle_data.get('vehicle', {}).get('id')
            trip_id = trip.get('tripId')
            latitude = position.get('latitude')
            longitude = position.get('longitude')
            current_status = vehicle_data.get('currentStatus')
            stop_id = vehicle_data.get('stopId')

            if current_status == "STOPPED_AT":
                origin = stop_id
                destination = stop_id
            elif current_status == "IN_TRANSIT_TO":
                origin = "unknown" 
                destination = stop_id
            else:
                origin = "unknown"
                destination = stop_id

            speed = float('inf')
            if all([train_id, latitude, longitude, trip_id]):
                trains.append(Train(train_id, trip_id, origin, destination, latitude, longitude, speed, current_status))
                
        return trains

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return []


def write_trains_to_file(trains, path=LATEST_TRAINS_FILE):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        serial = []
        for t in trains:
            try:
                lat_raw = t.lat
                lon_raw = t.lon
                if isinstance(lat_raw, str):
                    lat_raw = lat_raw.replace(',', '.')
                if isinstance(lon_raw, str):
                    lon_raw = lon_raw.replace(',', '.')
                lat = float(lat_raw)
                lon = float(lon_raw)

                if not (math.isfinite(lat) and math.isfinite(lon)):
                    continue

                
                raw_speed = t.speed
                try:
                    speed = float(raw_speed)
                    if not math.isfinite(speed):
                        speed = None
                except Exception:
                    speed = None

                serial.append({
                    'id': str(t.id),
                    'trip': t.trip,
                    'origin': t.origin,
                    'destination': t.destination,
                    'lat': lat,
                    'lon': lon,
                    'speed': speed,
                    'status': t.status,
                })
            except Exception:

                continue

        tmp_path = path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as fh:
            json.dump({'timestamp': int(time.time()), 'trains': serial}, fh, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception as e:
        print(f"Error writing latest trains to file: {e}")


if __name__ == "__main__":
    renfe_url = "https://gtfsrt.renfe.com/vehicle_positions.json"

    while True:
        print("Getting renfe data...")
        train_list = get_train_data(renfe_url)
        
        if train_list:
            print(f"Found {len(train_list)} trains.")
            for train in train_list:
                print(train)
            try:
                write_trains_to_file(train_list)
            except Exception as e:
                print(f"Error saving latest trains: {e}")
        else:
            print("No train data found.")
        
        time.sleep(30)
