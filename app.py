from flask import Flask, render_template, request
import pandas as pd
import numpy as np
from sklearn.neighbors import BallTree
import webbrowser
import os

CITIES_FILE = 'uscities.csv'
HOSPITALS_FILE = 'us_hospital_locations.csv'
EARTH_RADIUS_MILES = 3958.8
DEFAULT_RADIUS_MILES = 0

def gmaps_route_url(lat1, lon1, lat2, lon2):
    return (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={lat1},{lon1}"
        f"&destination={lat2},{lon2}"
        f"&travelmode=driving"
    )

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def map_view():
    cities_df = pd.read_csv(CITIES_FILE).drop_duplicates()
    hospitals_df = pd.read_csv(HOSPITALS_FILE).drop_duplicates()
    
    all_cities = cities_df['city'].drop_duplicates().sort_values().tolist()
    searched_location = None
    nearby_hospitals = []
    error = None
    center_lat, center_lon = 39.0, -98.0

    radius_miles = DEFAULT_RADIUS_MILES
    if request.method == 'POST':
        input_city = request.form.get('location', '').strip().lower()
        try:
            radius_miles = float(request.form.get('radius_miles', DEFAULT_RADIUS_MILES))
        except (TypeError, ValueError):
            radius_miles = 10
            # error = "Invalid radius value. Using default."

        city_matches = cities_df[cities_df['city'].str.lower() == input_city]
        if city_matches.empty:
            error = f"City '{input_city}' not found in database."
        else:
            city_row = city_matches.iloc[0]
            searched_location = {
                'City': city_row['city'],
                'State': city_row.get('state_name', ''),
                'County': city_row.get('county_name', ''),
                'Population': city_row.get('population', ''),
                'Latitude': city_row['lat'],
                'Longitude': city_row['lng'],
            }
            center_lat, center_lon = city_row['lat'], city_row['lng']
            
            hospitals_coords = np.radians(hospitals_df[['LATITUDE', 'LONGITUDE']].to_numpy())
            tree = BallTree(hospitals_coords, metric='haversine')
            query_point = np.radians([center_lat, center_lon])
            radius_rad = radius_miles / EARTH_RADIUS_MILES
            idx = tree.query_radius([query_point], r=radius_rad)[0]
            nearby = hospitals_df.iloc[idx].copy()
            
            if not nearby.empty:
                nearby_coords = np.radians(nearby[['LATITUDE', 'LONGITUDE']].to_numpy())
                dists_rad = BallTree(np.array([query_point]), metric='haversine').query(nearby_coords, k=1)[0].flatten()
                nearby['Distance_miles'] = dists_rad * EARTH_RADIUS_MILES
                
                nearby['Route_URL'] = [
                    gmaps_route_url(center_lat, center_lon, row['LATITUDE'], row['LONGITUDE'])
                    for _, row in nearby.iterrows()
                ]
                nearby['Google_Maps_URL'] = [
                    f"https://www.google.com/maps/search/?api=1&query={row['LATITUDE']},{row['LONGITUDE']}"
                    for _, row in nearby.iterrows()
                ]
                
                hospital_records = []
                for _, row in nearby.sort_values('Distance_miles').iterrows():
                    hospital_records.append({
                        'Name': row['NAME'],
                        'Address': row.get('ADDRESS', ''),
                        'City': row.get('CITY', ''),
                        'State': row.get('STATE', ''),
                        'ZIP': row.get('ZIP', ''),
                        'Type': row.get('TYPE', ''),
                        'Status': row.get('STATUS', ''),
                        'Beds': row.get('BEDS', ''),
                        'Phone': row.get('TELEPHONE', ''),
                        'Website': row.get('WEBSITE', ''),
                        'Latitude': row['LATITUDE'],
                        'Longitude': row['LONGITUDE'],
                        'Distance_miles': row['Distance_miles'],
                        'Route_URL': row['Route_URL'],
                        'Google_Maps_URL': row['Google_Maps_URL']
                    })
                nearby_hospitals = hospital_records
            else:
                error = f"No hospitals found within {radius_miles} miles of {city_row['city']}, {city_row.get('state_name', '')}."

    return render_template(
        "index.html",
        searched_location = searched_location,
        nearby_hospitals  = nearby_hospitals,
        center_lat        = center_lat,
        center_lon        = center_lon,
        error             = error,
        all_cities        = all_cities,
        radius_miles      = radius_miles,
        default_radius    = DEFAULT_RADIUS_MILES
    )

if __name__ == "__main__":
    # if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    #     webbrowser.open(f"http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
