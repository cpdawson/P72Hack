from flask import Flask, render_template_string, url_for
import folium
import json
import os
from folium.plugins import Fullscreen

app = Flask(__name__)

def get_image_url(name):
    folder = "entry_images"  # Make sure this folder is in your "static" directory
    file_path = os.path.join(app.static_folder, folder, f"{name}.jpg")
    if os.path.exists(file_path):
        return url_for('static', filename=f"{folder}/{name}.jpg")
    else:
        pass
    return url_for('static', filename="images/location.png")

@app.route('/')
def index():
    manhattan_coords = [40.7831, -73.9712]

    # Create the base map using Folium
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

    custom_js = f"""
    <script>
      var map_instance = window["{map_name}"];
      var markerData = {marker_data_json};

      for (var i = 0; i < markerData.length; i++) {{
          var data = markerData[i];
          var customIcon = L.icon({{
              iconUrl: data.img_url,
              iconSize: [50, 50],
                className: 'circular-marker'
          }});
          var marker = L.marker([data.lat, data.lon], {{icon: customIcon}}).addTo(map_instance);
          marker.bindPopup(data.name);
          marker.on('click', function(e) {{
              map_instance.flyTo(e.latlng, 16, {{
                  animate: true,
                  duration: 1.5,
                  easeLinearity: 0.25
              }});
          }});
      }}
    </script>
    """

    html_template = f"""
    <!doctype html>
    <html>
      <head>
      
              <style>
            .circular-marker {{
                border: 2px solid white;
                border-radius: 50%;
                box-sizing: border-box; /* ensures the border is included in the dimensions */
            }}
        </style>


        <meta charset="utf-8">
        <title>Zoomable Manhattan Map with Custom Icons</title>
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
