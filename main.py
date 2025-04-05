from flask import Flask, render_template, url_for
import folium
import json
import os
from folium.plugins import Fullscreen
from views import views_bp

app = Flask(__name__)
app.register_blueprint(views_bp)

def get_image_url(name):
    folder = "entry_images"  # This folder should be in your "static" directory
    file_path = os.path.join(app.static_folder, folder, f"{name}.jpg")
    if os.path.exists(file_path):
        return url_for('static', filename=f"{folder}/{name}.jpg")
    return url_for('static', filename="images/location.png")

def get_car_routes():
    # Return the car route parameters along with a full icon URL.
    return [
        {
            "start": [40.766708, -74.018524],
            "end": [40.760159, -74.002774],
            "duration": 10000,
            "rotation": 0,
            "icon_url": url_for('static', filename='vehicles/car_icon.png')
        },
        {
            "start": [40.702210, -73.992004],
            "end": [40.708034, -73.999334],
            "duration": 10000,
            "rotation": 0,
            "icon_url": url_for('static', filename='vehicles/car_icon_45.png')
        }
    ]

@app.route('/')
def index():
    manhattan_coords = [40.7831, -73.9712]

    # Create the base map using Folium
    m = folium.Map(location=manhattan_coords, zoom_start=13, tiles='CartoDB positron')
    Fullscreen(position='topright').add_to(m)
    folium.LayerControl().add_to(m)

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

    marker_data = [
        {
            "name": name,
            "lat": coords[0],
            "lon": coords[1],
            "img_url": get_image_url(name)
        }
        for name, coords in location_coords.items()
    ]
    marker_data_json = json.dumps(marker_data)
    map_name = m.get_name()
    map_html = m.get_root().render()

    car_routes = get_car_routes()
    car_routes_json = json.dumps(car_routes)

    return render_template(
        'index.html',
        map_html=map_html,
        map_name=map_name,
        marker_data_json=marker_data_json,
        car_routes_json=car_routes_json
    )

if __name__ == '__main__':
    app.run(debug=True)
