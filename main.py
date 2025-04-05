from flask import Flask, render_template, url_for, request, jsonify
import folium
import json
import requests
from sqlalchemy import func
import csv
from datetime import datetime, timedelta
from collections import defaultdict
import os
from models import db, TrafficEntry
import math
from folium.plugins import Fullscreen
from views import views_bp

app = Flask(__name__)
app.register_blueprint(views_bp)
DB_PATH = 'instance/traffic.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///traffic.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

PRICING = {
    ('Car', 0): 2.25,
    ('Car', 1): 9,
    ('Buses', 0): 3.6,
    ('Buses', 1): 14.4,
    ('Motorcycles', 0): 1.05,
    ('Motorcycles', 1): 4.5,
    ('Taxi', 0): 0.75,
    ('Taxi', 1): 0.75,
    ('Single Unit Trucks', 0): 3.6,
    ('Single Unit Trucks', 1): 14.4,
    ('Multi Unit Trucks', 0): 5.40,
    ('Multi Unit Trucks', 1): 21.60
}

def load_data_from_csv(filepath):
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            entry = TrafficEntry(
                id=int(row['Index']),
                datetime=row['Datetime'],
                is_peak=row['Is Peak'],
                vehicle_class=row['Vehicle Class'],
                detection_group=row['Detection Group'],
                crz_entries=int(row['CRZ Entries']),
                excluded_roadway_entries=int(row['Excluded Roadway Entries'])
            )
            db.session.add(entry)
        db.session.commit()
        print("CSV data loaded into database.")

@app.route('/data', methods=['GET'])
def get_traffic_data():
    entries = TrafficEntry.query.limit(12).all()
    return jsonify([{
        'id': e.id,
        'datetime': e.datetime,
        'is_peak': e.is_peak,
        'vehicle_class': e.vehicle_class,
        'detection_group': e.detection_group,
        'crz_entries': e.crz_entries,
        'excluded_roadway_entries': e.excluded_roadway_entries
    } for e in entries])


@app.route("/get_updated_spawns", methods=["GET"])
def get_updated_spawns():
    # Re-parse info.json so we see the updated data
    # Then build the same JS lines that spawn cars.
    # For example, if you already have parse_info_json() and build_spawn_js_from_timestepdata() used by index():

    # re-parse the info.json
    all_timestep_data = parse_info_json("info.json")  # only SELECTED_CLASS vehicles
    # build new JavaScript lines
    spawn_js = build_spawn_js_from_timestepdata(
        timestep_data=all_timestep_data,
        speed=4000,
        spawn_window=20000,
        step_delay=2000
    )

    # Return it as JSON:
    return jsonify({"spawn_js": spawn_js})

@app.route('/filter', methods=['GET'])
def get_filtered_data():
    datetime_start = request.args.get('datetime_start')
    datetime_end = request.args.get('datetime_end')
    detection_group = request.args.get('detection_group')
    vehicle_class_filter = request.args.get('vehicle_class')

    if not datetime_start or not datetime_end:
        return jsonify({'error': 'datetime_start and datetime_end are required'}), 400

    # Base query
    query = db.session.query(
        TrafficEntry.vehicle_class,
        TrafficEntry.is_peak,
        func.sum(TrafficEntry.crz_entries)
    ).filter(
        TrafficEntry.datetime >= datetime_start,
        TrafficEntry.datetime < datetime_end
    )

    if detection_group:
        query = query.filter(TrafficEntry.detection_group == detection_group)

    if vehicle_class_filter:
        query = query.filter(TrafficEntry.vehicle_class == vehicle_class_filter)

    query = query.group_by(TrafficEntry.vehicle_class, TrafficEntry.is_peak)

    results = query.all()

    vehicle_counts = {}
    revenue_per_class = {}
    total_vehicles = 0
    total_revenue = 0

    for vehicle_class, is_peak, entry_sum in results:
        price_per = PRICING.get((vehicle_class, is_peak), 0)
        revenue = entry_sum * price_per

        # Update per-class stats
        vehicle_counts[vehicle_class] = vehicle_counts.get(vehicle_class, 0) + entry_sum
        revenue_per_class[vehicle_class] = revenue_per_class.get(vehicle_class, 0) + revenue

        total_vehicles += entry_sum
        total_revenue += revenue

    return jsonify({
        "vehicle_counts": vehicle_counts,
        "total_vehicles": total_vehicles,
        "revenue_per_class": revenue_per_class,
        "total_revenue": total_revenue
    })

SUMMARY_FILE = "summary_stats.json"

def read_summary_stats():
    """Load summary_stats.json and return as dict. If file doesn't exist, return {}."""
    if not os.path.exists(SUMMARY_FILE):
        return {}
    with open(SUMMARY_FILE, "r") as f:
        return json.load(f)

def write_summary_stats(stats_dict):
    """Overwrite summary_stats.json with stats_dict."""
    with open(SUMMARY_FILE, "w") as f:
        json.dump(stats_dict, f, indent=2)

def compute_summary_for_info(json_path="info.json"):
    """
    Example: parse the final frame of info.json
    and sum up vehicles/revenue by class.
    """
    if not os.path.exists(json_path):
        return {}

    with open(json_path, "r") as f:
        data = json.load(f)

    if not data:
        return {}

    # Let's pick the final frame
    final_frame = data[-1]  # or data[0], whichever is correct
    locations = final_frame.get("locations", {})
    totals_by_class = {}

    for loc_name, loc_info in locations.items():
        by_class = loc_info["cumulative"]["by_class"]
        for vclass, stats in by_class.items():
            vehicles = stats.get("vehicles", 0)
            revenue = stats.get("revenue", 0)
            if vclass not in totals_by_class:
                totals_by_class[vclass] = {"vehicles": 0, "revenue": 0.0}
            totals_by_class[vclass]["vehicles"] += vehicles
            totals_by_class[vclass]["revenue"] += revenue

    return totals_by_class



# Mapping interval keys to number of 10-min blocks and animation duration in seconds
INTERVAL_CONFIG = {
    "10min":   {"blocks": 1, "duration": 3},
    "30min":   {"blocks": 3, "duration": 6},
    "1hr":     {"blocks": 6, "duration": 12},
    "3hr":     {"blocks": 18, "duration": 18},
    "6hr":     {"blocks": 36, "duration": 18},
    "1day":    {"blocks": 144, "duration": 20},
    "1week":   {"blocks": 1008, "duration": 30},
    "2week":   {"blocks": 2016, "duration": 60},
    "1month":  {"blocks": 4320, "duration": 120},
    "3month":  {"blocks": 12960, "duration": 180},
}

@app.route('/realtime_series', methods=['GET'])
def realtime_series():
    interval_key = request.args.get("interval", "1hr")
    start_str = request.args.get("datetime_start")

    if not start_str or interval_key not in INTERVAL_CONFIG:
        return jsonify({"error": "Missing or invalid datetime_start or interval"}), 400

    try:
        start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return jsonify({"error": "datetime_start must be in format YYYY-MM-DD HH:MM:SS"}), 400

    config = INTERVAL_CONFIG[interval_key]
    num_blocks = config["blocks"]
    num_frames = config["duration"]
    block_duration = timedelta(minutes=10)
    interval_duration = block_duration * num_blocks
    end_time = start_time + interval_duration

    # Query 10-minute blocks in range
    rows = db.session.query(
        TrafficEntry.vehicle_class,
        TrafficEntry.is_peak,
        TrafficEntry.datetime,
        TrafficEntry.detection_group,
        func.sum(TrafficEntry.crz_entries).label("vehicle_count")
    ).filter(
        TrafficEntry.datetime >= start_time.strftime("%Y-%m-%d %H:%M:%S"),
        TrafficEntry.datetime < end_time.strftime("%Y-%m-%d %H:%M:%S")
    ).group_by(
        TrafficEntry.vehicle_class,
        TrafficEntry.is_peak,
        TrafficEntry.datetime,
        TrafficEntry.detection_group
    ).all()

    block_map = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"vehicles": 0, "revenue": 0})))
    all_block_times = set()

    for vclass, is_peak, dt, location, count in rows:
        key = (vclass, is_peak)
        price = PRICING.get(key, 0)
        block_map[dt][location][vclass]["vehicles"] += count
        block_map[dt][location][vclass]["revenue"] += count * price
        all_block_times.add(dt)

    all_block_times = sorted(all_block_times)
    blocks_per_frame = num_blocks / num_frames
    frames = []

    cumulative = defaultdict(lambda: defaultdict(lambda: {"vehicles": 0, "revenue": 0}))
    cumulative_total = defaultdict(lambda: {"vehicles": 0, "revenue": 0})

    for i in range(num_frames):
        frame_duration = interval_duration.total_seconds() / num_frames
        frame_start = start_time + timedelta(seconds=(i * frame_duration))
        frame_data = {
            "timestamp": frame_start.strftime("%Y-%m-%d %H:%M:%S"),
            "scale": 1,
            "locations": {}
        }

        # Always pull the block the frame overlaps with
        block_index = int(i * blocks_per_frame)

        if block_index < len(all_block_times):
            block_time = all_block_times[block_index]
            portion = blocks_per_frame  # portion of block assigned to each frame
            frame_fraction = portion

            for location, classes in block_map[block_time].items():
                if location not in frame_data["locations"]:
                    frame_data["locations"][location] = {
                        "current": {
                            "total_vehicles": 0,
                            "total_revenue": 0,
                            "by_class": {}
                        }
                    }

                for vclass, data in classes.items():
                    vcount = data["vehicles"] * frame_fraction
                    vrevenue = data["revenue"] * frame_fraction

                    frame_data["locations"][location]["current"]["total_vehicles"] += vcount
                    frame_data["locations"][location]["current"]["total_revenue"] += vrevenue

                    if vclass not in frame_data["locations"][location]["current"]["by_class"]:
                        frame_data["locations"][location]["current"]["by_class"][vclass] = {"vehicles": 0, "revenue": 0}
                    frame_data["locations"][location]["current"]["by_class"][vclass]["vehicles"] += vcount
                    frame_data["locations"][location]["current"]["by_class"][vclass]["revenue"] += vrevenue

                    cumulative[location][vclass]["vehicles"] += vcount
                    cumulative[location][vclass]["revenue"] += vrevenue
                    cumulative_total[location]["vehicles"] += vcount
                    cumulative_total[location]["revenue"] += vrevenue

        # Finalize cumulative and round values after updating all data
        for location in frame_data["locations"]:
            cumulative_by_class = {
                vclass: {
                    "vehicles": round(cumulative[location][vclass]["vehicles"], 2),
                    "revenue": round(cumulative[location][vclass]["revenue"], 2)
                } for vclass in cumulative[location]
            }

            frame_data["locations"][location]["cumulative"] = {
                "vehicles": round(cumulative_total[location]["vehicles"], 2),
                "revenue": round(cumulative_total[location]["revenue"], 2),
                "by_class": cumulative_by_class
            }

            # Round current
            curr = frame_data["locations"][location]["current"]
            curr["total_vehicles"] = round(curr["total_vehicles"], 2)
            curr["total_revenue"] = round(curr["total_revenue"], 2)
            for vclass in curr["by_class"]:
                curr["by_class"][vclass]["vehicles"] = round(curr["by_class"][vclass]["vehicles"], 2)
                curr["by_class"][vclass]["revenue"] = round(curr["by_class"][vclass]["revenue"], 2)

        frames.append(frame_data)

    return jsonify(frames)

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


@app.route("/save_timestep", methods=["POST"])
def save_timestep():
    data = request.get_json()

    # 1) Write frames_data to info.json
    frames_data = data.get("frames_data", [])
    with open("info.json", "w") as f:
        json.dump(frames_data, f, indent=2)

    chosen_vehicle = data.get("chosen_vehicle", "Car")
    global SELECTED_CLASS
    SELECTED_CLASS = chosen_vehicle

    # 2) Now that info.json is updated, compute new summary
    new_summary = compute_summary_for_info("info.json")

    # 3) Save that summary to summary_stats.json
    write_summary_stats(new_summary)

    return jsonify({"status": "success", "message": "Data saved"}), 200


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
        step_info = {"index": i, "vehicles": [],"timestep": time_step["timestamp"]}
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
                    f"updateTimestep('{step_info['timestep']}');"
                    f"}}, {spawn_time});"
                )
                lines.append(line)
                # lines.append(f"updateTimestep('{step_info['timestep']}');")
                
                # lines.append(f"updateTimestep('2025-03-05 00:00:00');")

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

@app.route('/')
def index():
    # 1) read summary
    summary_data = read_summary_stats()

    # 2) Create the Folium map, parse info.json, build spawns, etc.
    manhattan_coords = [40.7381, -73.9712]
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
        selected_car_js=selected_car_js,
        summary_data=summary_data
    )

if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists(DB_PATH):
            print("Database not found. Creating and loading data...")
            db.create_all()
            load_data_from_csv('cleaned_data.csv')
        else:
            print("Database exists. Skipping CSV import.")
    app.run(debug=True)

