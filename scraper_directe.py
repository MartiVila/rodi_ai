#Scrapper to get the real time position of each time of the network every 30 seconds

import requests
import time
import json
import os
import math

# path where scraper will dump latest trains for other processes to consume
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LATEST_TRAINS_FILE = os.path.join(DATA_DIR, "latest_trains.json")

#The fucntion of this script will be to get all the train infomration every 30 seconds, 
#and be able to provide the AI model object trains with their position and between which stations they are

#Train class
class Train:
    def __init__(self, id, trip, origin, destination, lat, lon, speed, status):
        self.id = id
        self.trip = trip
        #Origin and Destination refear to the ID of the stations the trian is between.
        self.origin = origin
        self.destination = destination
        self.lat = lat
        self.lon = lon
        #The AI must calculate the speed by now will be inf
        self.speed = speed
        self.status = status

    def __repr__(self):
        return (f"Train(ID: {self.id}, Trip: {self.trip}, "
                f"Position: ({self.lat}, {self.lon}), Status: {self.status})")
    #Every time the object is created it will print its information

def get_train_data(url):
    try:
        #By now we won't stablish any timeout time
        response = requests.get(url)
        response.raise_for_status()
        #The document downloaded
        data = response.json()

        trains = [] #List of train objects
        #Knowing th estructure of the Json we can extract the information we want
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

            #logic to determine origin and destination based on stop_id
            if current_status == "STOPPED_AT":
                #When the train is stopped at a station, both origin and destination are the same
                origin = stop_id
                destination = stop_id
            elif current_status == "IN_TRANSIT_TO":
                origin = "unknown"  #We don't have this information here, but the model will fix it.
                destination = stop_id
            #The last case is status = "INCOMING_AT" that means the station showd is the destination, but is coming from another station
            else:
                origin = "unknown"
                destination = stop_id
            # Create a Train object if all key data exists
            #The speed will be stabblished at infinit for now
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
    """Write list of Train objects to JSON file as simple dicts.
    This is intended for local IPC: other processes (map server) can read this file
    instead of calling the remote API again.
    """
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        serial = []
        for t in trains:
            try:
                # sanitize numeric fields: allow commas as decimal separators
                lat_raw = t.lat
                lon_raw = t.lon
                if isinstance(lat_raw, str):
                    lat_raw = lat_raw.replace(',', '.')
                if isinstance(lon_raw, str):
                    lon_raw = lon_raw.replace(',', '.')
                lat = float(lat_raw)
                lon = float(lon_raw)
                # validate lat/lon are finite
                if not (math.isfinite(lat) and math.isfinite(lon)):
                    continue

                # sanitize speed: replace infinities/NaN with None
                raw_speed = t.speed
                try:
                    # some code sets speed to float('inf') or a non-numeric
                    speed = float(raw_speed)
                    if not math.isfinite(speed):
                        speed = None
                except Exception:
                    # if cannot coerce to float, set None
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
                # skip malformed entries
                continue

        # atomic write: write to tmp then replace
        tmp_path = path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as fh:
            json.dump({'timestamp': int(time.time()), 'trains': serial}, fh, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception as e:
        print(f"Error writing latest trains to file: {e}")

#Example Main, usually and in proprer use the AI will have to properly use the function get_train_data
#so the AI wil get a list of object every 30 seconds
if __name__ == "__main__":
    renfe_url = "https://gtfsrt.renfe.com/vehicle_positions.json"

    while True:
        print("Getting renfe data...")
        train_list = get_train_data(renfe_url)
        
        if train_list:
            print(f"Found {len(train_list)} trains.")
            for train in train_list:
                #Pito to know the information of each train
                print(train)
            # write the latest trains to disk so other processes (map server) can use them
            try:
                write_trains_to_file(train_list)
            except Exception as e:
                print(f"Error saving latest trains: {e}")
        else:
            print("No train data found.")
        
        #ANOTTATE:
        #I noticed a problem, if the code is not executed at the start of the cycle, we my get a delay in the data fetching
        #We should search for a way to coordinate with the update cycle of Renfe
        time.sleep(30)
