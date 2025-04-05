from flask import Blueprint, Flask, render_template_string
import folium
import json
from folium.plugins import Fullscreen
from views import views_bp

app = Flask(__name__)
app.register_blueprint(views_bp)

@app.route('/')
def index():
    manhattan_coords = [40.7831, -73.9712]

    m = folium.Map(location=manhattan_coords, zoom_start=13, tiles='CartoDB positron')

    # Add some controls
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
        {"name": name, "lat": coords[0], "lon": coords[1]}
        for name, coords in location_coords.items()
    ]
    marker_data_json = json.dumps(marker_data)

    map_name = m.get_name()

    map_html = m.get_root().render()

    custom_js = f"""
    <script>
      // Get the map instance using its variable name from the global window object
      var map_instance = window["{map_name}"];
      var markerData = {marker_data_json};
      for (var i = 0; i < markerData.length; i++) {{
          var data = markerData[i];
          var marker = L.marker([data.lat, data.lon]).addTo(map_instance);
          marker.bindPopup(data.name);
          marker.on('click', function(e) {{
              // When clicked, zoom in on the marker's location (zoom level 16)
              map_instance.setView(e.latlng, 16);
          }});
      }}
    </script>
    """

    html_template = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <title>Zoomable Manhattan Map</title>
        <style>
            body {{ margin: 0; padding: 0; }}
            #map {{ height: 100vh; width: 100%; }}
        </style>
      </head>
      <body>
        {map_html}
        {custom_js}
      </body>
    </html>
    """

    return html_template

if __name__ == '__main__':
    app.run(debug=True)