#Scrapper to get the real time position of each time of the network every 30 seconds

import requests
import time
import json

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
        else:
            print("No train data found.")
        
        #ANOTTATE:
        #I noticed a problem, if the code is not executed at the start of the cycle, we my get a delay in the data fetching
        #We should search for a way to coordinate with the update cycle of Renfe
        time.sleep(30)
