from flask import Flask, render_template, url_for
import folium
import json
import os
import math
from folium.plugins import Fullscreen
from views import views_bp

app = Flask(__name__)
app.register_blueprint(views_bp)

###############################################################
# 1) Hardcode which vehicle class to show, e.g. "Car" or "Taxi"
###############################################################
SELECTED_CLASS = "Car"  # e.g. "Car", "Taxi", "Buses", etc.

#####################################
# 2) Define route definitions
#    but route icons depend on SELECTED_CLASS.
#####################################
def get_car_routes():
    """
    Each route uses the SELECTED_CLASS to pick its icon filename.
    Make sure you actually have, e.g. car_icon_135.png, taxi_icon_135.png, etc.
    """
    class_lower = SELECTED_CLASS.lower()
    return [
        {
            "name": "Lincoln Tunnel",
            "start": [40.766708, -74.018524],
            "end": [40.760159, -74.002774],
            "duration": 4000,
            "icon_url": url_for('static', filename=f'vehicles/{class_lower}_icon_135.png')
        },
        {
            "name": "Brooklyn Bridge",
            "start": [40.702210, -73.992004],
            "end": [40.708034, -73.999334],
            "duration": 4000,
            "icon_url": url_for('static', filename=f'vehicles/{class_lower}_icon_315.png')
        },
        {
            "name": "Williamsburg Bridge",
            "start": [40.712044, -73.966979],
            "end": [40.714744, -73.976249],
            "duration": 4000,
            "icon_url": url_for('static', filename=f'vehicles/{class_lower}_icon_337.png')
        },
        {
            "name": "Manhattan Bridge",
            "start": [40.702299, -73.987915],
            "end": [40.709581, -73.991853],
            "duration": 4000,
            "icon_url": url_for('static', filename=f'vehicles/{class_lower}_icon_292.png')
        },
        {
            "name": "Holland Tunnel",
            "start": [40.728897, -74.031589],
            "end": [40.726183, -74.011329],
            "duration": 4000,
            "icon_url": url_for('static', filename=f'vehicles/{class_lower}_icon_180.png')
        },
        {
            "name": "Hugh L. Carey Tunnel",
            "start": [40.685010, -74.007056],
            "end": [40.700987, -74.015532],
            "duration": 4000,
            "icon_url": url_for('static', filename=f'vehicles/{class_lower}_icon_292.png')
        },
        {
            "name": "Queensboro Bridge",
            "start": [40.754783, -73.949994],
            "end": [40.758882, -73.959143],
            "duration": 4000,
            "icon_url": url_for('static', filename=f'vehicles/{class_lower}_icon_337.png')
        },
        {
            "name": "Queens Midtown Tunnel",
            "start": [40.74289229922877, -73.96082715665342],
            "end": [40.747834966345074, -73.96816127996215],
            "duration": 4000,
            "icon_url": url_for('static', filename=f'vehicles/{class_lower}_icon_337.png')
        },
        {
            "name": "West 60th St",
            "start": [40.77164541992876, -73.98306418072985],
            "end": [40.768193524649575, -73.98565628724995],
            "duration": 4000,
            "icon_url": url_for('static', filename=f'vehicles/{class_lower}_icon_45.png')
        },
        {
            "name": "FDR Drive at 60th St",
            "start": [40.765785223608674, -73.95748405831618],
            "end": [40.76275029301429, -73.95971426811401],
            "duration": 4000,
            "icon_url": url_for('static', filename=f'vehicles/{class_lower}_icon_45.png')
        },
        {
            "name": "East 60th St",
            "start": [40.76328718520095, -73.96243948478009],
            "end": [40.75937598422883, -73.96541471379228],
            "duration": 4000,
            "icon_url": url_for('static', filename=f'vehicles/{class_lower}_icon_45.png')
        },
        {
            "name": "West Side Highway at 60th St",
            "start": [40.77321742695657, -73.98939439202347],
            "end": [40.77019877213487, -73.99163134442664],
            "duration": 4000,
            "icon_url": url_for('static', filename=f'vehicles/{class_lower}_icon_45.png')
        }
    ]

def get_route_for_location(loc_name):
    for r in get_car_routes():
        if r["name"] == loc_name:
            return r
    return None

#########################################################
# 3) Parse JSON but only keep the selected vehicle class
#########################################################
def parse_info_json(json_path="info.json"):
    """
    We'll read each time step's 'by_class', but only keep SELECTED_CLASS vehicles.
    e.g. "Car" => read by_class["Car"]["vehicles"] -> spawn that many
    """
    with open(json_path, "r") as f:
        data = json.load(f)

    results = []
    for i, time_step in enumerate(data):
        step_info = {"index": i, "vehicles": []}
        locations = time_step.get("locations", {})

        for loc_name, loc_data in locations.items():
            by_class = loc_data["current"].get("by_class", {})
            # If the selected class is in by_class for that location:
            if SELECTED_CLASS in by_class:
                vehicles_float = by_class[SELECTED_CLASS]["vehicles"]
                vehicle_count = int(math.floor(vehicles_float))  # or round
                if vehicle_count > 0:
                    step_info["vehicles"].append({
                        "location": loc_name,
                        "count": vehicle_count
                    })
        results.append(step_info)
    return results

###############################################################
# 4) Build JS spawns, ignoring other classes
###############################################################
def build_spawn_js_from_timestepdata(timestep_data, speed=2000, spawn_window=20000, step_delay=2000):
    """
    We'll spawn only SELECTED_CLASS vehicles (already filtered in parse_info_json).
    Each step spawns them over 'spawn_window' ms,
    then we wait 'step_delay' before the next step.
    """
    lines = []
    total_step_time = spawn_window + step_delay

    for step_info in timestep_data:
        step_index = step_info["index"]
        offset_for_step = step_index * total_step_time
        vehicles_list = step_info["vehicles"]  # each item: { "location", "count" }

        for item in vehicles_list:
            loc_name = item["location"]
            count = item["count"]
            route = get_route_for_location(loc_name)
            if not route or count <= 0:
                continue

            # route["icon_url"] was built from SELECTED_CLASS, so let's just use that
            icon_path = route["icon_url"]

            # Spread out spawns in spawn_window
            if count > 1:
                delay_per_car = float(spawn_window) / (count - 1)
            else:
                delay_per_car = 0

            for c in range(count):
                spawn_time = int(offset_for_step + c * delay_per_car)
                line = (
                    f"setTimeout(function() {{ "
                    f"addCar([{route['start'][0]}, {route['start'][1]}], "
                    f"[{route['end'][0]}, {route['end'][1]}], "
                    f"{speed}, "
                    f"'{icon_path}'); "
                    f"}}, {spawn_time});"
                )
                lines.append(line)

    return "\n".join(lines)

###############################################################
# 5) get_image_url for static location markers
###############################################################
def get_image_url(name):
    folder = "entry_images"
    file_path = os.path.join(app.static_folder, folder, f"{name}.jpg")
    if os.path.exists(file_path):
        return url_for('static', filename=f"{folder}/{name}.jpg")
    return url_for('static', filename="images/location.png")

###############################################################
# 6) Flask route
###############################################################
@app.route('/')
def index():
    # Create the base map
    manhattan_coords = [40.7831, -73.9712]
    m = folium.Map(location=manhattan_coords, zoom_start=13, tiles='CartoDB positron')
    Fullscreen(position='topright').add_to(m)
    folium.LayerControl().add_to(m)

    # Location marker data
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

    # Parse the JSON to get only SELECTED_CLASS
    all_timestep_data = parse_info_json("info.json")

    # Build the JS snippet
    selected_car_js = build_spawn_js_from_timestepdata(
        timestep_data=all_timestep_data,
        speed=4000,
        spawn_window=20000,
        step_delay=2000
    )

    # Render
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
