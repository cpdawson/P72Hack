from flask import Flask, jsonify, request
from models import db, TrafficEntry
from sqlalchemy import func
from datetime import datetime, timedelta
from collections import defaultdict
import csv
import os

app = Flask(__name__)
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



# mapping interval keys to number of 10-min blocks and animation duration in seconds
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

    # query 10-minute blocks in range
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
        # always pull the block the frame overlaps with
        block_index = int(i * blocks_per_frame)
        if block_index < len(all_block_times):
            block_time = all_block_times[block_index]
            portion = blocks_per_frame
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

        # finalize cumulative and round values after updating all data
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


if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists(DB_PATH):
            print("Database not found. Creating and loading data...")
            db.create_all()
            load_data_from_csv('cleaned_data.csv')
        else:
            print("Database exists. Skipping CSV import.")
    app.run(debug=True)