from flask import Flask, render_template, url_for
import folium
import json
import os
import math
from folium.plugins import Fullscreen
from views import views_bp

app = Flask(__name__)
app.register_blueprint(views_bp)

def get_car_routes():
    """
    Return a list of route dictionaries.
    Each dictionary has: name, start, end, duration, icon_url
    """
    return [
        {
            "name": "Lincoln Tunnel",
            "start": [40.766708, -74.018524],
            "end": [40.760159, -74.002774],
            "duration": 4000,
            "icon_url": url_for('static', filename='vehicles/car_icon_135.png')
        },
        {
            "name": "Brooklyn Bridge",
            "start": [40.702210, -73.992004],
            "end": [40.708034, -73.999334],
            "duration": 4000,
            "icon_url": url_for('static', filename='vehicles/car_icon_315.png')
        },
        {
            "name": "Williamsburg Bridge",
            "start": [40.712044, -73.966979],
            "end": [40.714744, -73.976249],
            "duration": 4000,
            "icon_url": url_for('static', filename='vehicles/car_icon_315.png')
        },
        {
            "name": "Manhattan Bridge",
            "start": [40.702299, -73.987915],
            "end": [40.709581, -73.991853],
            "duration": 4000,
            "icon_url": url_for('static', filename='vehicles/car_icon_315.png')
        },
        {
            "name": "Holland Tunnel",
            "start": [40.728897, -74.031589],
            "end": [40.726183, -74.011329],
            "duration": 4000,
            "icon_url": url_for('static', filename='vehicles/car_icon_180.png')
        },
        {
            "name": "Hugh L. Carey Tunnel",
            "start": [40.685010, -74.007056],
            "end": [40.700987, -74.015532],
            "duration": 4000,
            "icon_url": url_for('static', filename='vehicles/car_icon_315.png')
        },
        {
            "name": "Queensboro Bridge",
            "start": [40.754783, -73.949994],
            "end": [40.758882, -73.959143],
            "duration": 4000,
            "icon_url": url_for('static', filename='vehicles/car_icon_0.png')
        },
        {
            "name": "Queens Midtown",
            "start": [40.74289229922877, -73.96082715665342],
            "end": [40.747834966345074, -73.96816127996215],
            "duration": 4000,
            "icon_url": url_for('static', filename='vehicles/car_icon_0.png')
        },
        {
            "name": "West 60th",
            "start": [40.77164541992876, -73.98306418072985],
            "end": [40.768193524649575, -73.98565628724995],
            "duration": 4000,
            "icon_url": url_for('static', filename='vehicles/car_icon_0.png')
        },
        {
            "name": "11th Ave and 60th",
            "start": [40.77326978935373, -73.98933771562456],
            "end": [40.768173333383125, -73.99302066958496],
            "duration": 4000,
            "icon_url": url_for('static', filename='vehicles/car_icon_0.png')
        },
        {
            "name": "East 60th",
            "start": [40.76328718520095, -73.96243948478009],
            "end": [40.75937598422883, -73.96541471379228],
            "duration": 4000,
            "icon_url": url_for('static', filename='vehicles/car_icon_0.png')
        },
        {
            "name": "60th and 1st",
            "start": [40.76444641664966, -73.95843436877433],
            "end": [40.76103366817469, -73.96405583512909],
            "duration": 4000,
            "icon_url": url_for('static', filename='vehicles/car_icon_0.png')
        }
    ]

def parse_info_json(json_path="info.json"):
    """
    Reads the JSON file (with multiple items representing time steps).
    We ignore the 'timestamp' field and just treat each item as:
       {
         "locations": {
           "Brooklyn Bridge": { "current": { "total_vehicles": ... } },
           ...
         },
         "scale": ... (maybe ignored)
       }
    We'll return a list of dicts of the form:
       {
         "index": i, # i is the iteration
         "locations": {
            "Brooklyn Bridge": 138,
            "East 60th St": 312,
            ...
         }
       }
    """
    with open(json_path, "r") as f:
        data = json.load(f)

    results = []
    for i, time_step in enumerate(data):
        # time_step["locations"] is a dict of location_name -> detail
        location_dict = time_step.get("locations", {})
        step_info = {"index": i, "locations": {}}

        for loc_name, loc_data in location_dict.items():
            # The "current" portion has "total_vehicles"
            vehicles_float = loc_data["current"]["total_vehicles"]
            # Round or floor the float
            vehicles_count = int(math.floor(vehicles_float)/10)
            step_info["locations"][loc_name] = vehicles_count

        results.append(step_info)
    return results

def get_route_for_location(loc_name):
    """
    Match the location name to a route from get_car_routes().
    Return None if not found.
    """
    for r in get_car_routes():
        if r["name"] == loc_name:
            return r
    return None

def build_spawn_js_from_timestepdata(timestep_data, speed=2000, spawn_window=5000, step_delay=2000):
    """
    Spawns each time step's cars over 'spawn_window' ms (e.g. 5000 = 5s),
    then waits 'step_delay' ms before starting the next time step.

    So the total time between step i and step i+1 = spawn_window + step_delay.

    :param timestep_data: [
      { "index": 0, "locations": {"Brooklyn Bridge": 20, ...} },
      { "index": 1, "locations": {...} },
      ...
    ]
    :param speed: ms each car takes to traverse its route
    :param spawn_window: ms to spread out the spawns in a single time step
    :param step_delay: ms to wait *after* finishing a step's spawns, before next step starts
    """

    lines = []
    # total real-time length per step
    total_step_time = spawn_window + step_delay

    for step_info in timestep_data:
        step_index = step_info["index"]
        locations = step_info["locations"]
        # Offset for this step in real-time
        # e.g. if step_index=0 => offset=0, step_index=1 => offset=1*(spawn_window+step_delay)=7000, etc.
        offset_for_step = step_index * total_step_time

        for loc_name, vehicle_count in locations.items():
            route = get_route_for_location(loc_name)
            if not route or vehicle_count <= 0:
                continue

            # Spread out spawns in this step over 'spawn_window'
            # If multiple cars, each is spaced: spawn_window/(vehicle_count - 1) if >1
            if vehicle_count > 1:
                delay_per_car = float(spawn_window) / (vehicle_count - 1)
            else:
                delay_per_car = 0

            for c in range(vehicle_count):
                # each car spawns between offset_for_step and offset_for_step+spawn_window
                spawn_time = int(offset_for_step + c * delay_per_car)

                line = (
                    f"setTimeout(function() {{ "
                    f"addCar([{route['start'][0]}, {route['start'][1]}], "
                    f"[{route['end'][0]}, {route['end'][1]}], "
                    f"{speed}, "
                    f"'{route['icon_url']}'); "
                    f"}}, {spawn_time});"
                )
                lines.append(line)

    return "\n".join(lines)



def get_image_url(name):
    folder = "entry_images"
    file_path = os.path.join(app.static_folder, folder, f"{name}.jpg")
    if os.path.exists(file_path):
        return url_for('static', filename=f"{folder}/{name}.jpg")
    return url_for('static', filename="images/location.png")

@app.route('/')
def index():
    # 1) Create your base map
    manhattan_coords = [40.7831, -73.9712]
    m = folium.Map(location=manhattan_coords, zoom_start=13, tiles='CartoDB positron')
    Fullscreen(position='topright').add_to(m)
    folium.LayerControl().add_to(m)

    # 2) Add static location markers
    location_coords = {
        "Brooklyn Bridge": [40.7061, -73.9969],
        "West Side Highway at 60th St": [40.7713, -73.9902],
        "West 60th St": [40.7700, -73.9836],
        "Queensboro Bridge": [40.7570, -73.9544],
        "Queens Midtown Tunnel": [40.7433, -73.9698],
        "Lincoln Tunnel": [40.7608, -74.0021],
        "Holland Tunnel": [40.7260, -74.0086],
        "FDR Drive at 60th St": [40.7626, -73.9585],
        "East 60th St": [40.7616, -73.9641],
        "Williamsburg Bridge": [40.7132, -73.9712],
        "Manhattan Bridge": [40.7075, -73.9903],
        "Hugh L. Carey Tunnel": [40.7003, -74.0132]
    }
    marker_data = []
    for name, coords in location_coords.items():
        marker_data.append({
            "name": name,
            "lat": coords[0],
            "lon": coords[1],
            "img_url": get_image_url(name)
        })
    marker_data_json = json.dumps(marker_data)

    # 3) Read info.json without caring about 'timestamp'
    all_timestep_data = parse_info_json("info.json")

    # 4) Build the spawning snippet
    # For example, each time step is spaced by 1000ms in real time, each car route moves at speed=2000ms
    selected_car_js = build_spawn_js_from_timestepdata(
        all_timestep_data,
        speed=4000,
        step_delay=1000
    )

    # 5) Render the template
    map_name = m.get_name()
    map_html = m.get_root().render()
    return render_template(
        'index.html',
        map_html=map_html,
        map_name=map_name,
        marker_data_json=marker_data_json,
        selected_car_js=selected_car_js
    )

if __name__ == '__main__':
    app.run(debug=True)
