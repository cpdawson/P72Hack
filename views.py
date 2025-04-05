from flask import Flask, Blueprint, render_template_string
import folium
import json
from folium.plugins import Fullscreen

views_bp = Blueprint('views', __name__)


@views_bp.route('/lincoln_tunnel')
def bridge(): 
    location_coords = {
        "Brooklyn Bridge": [40.7061, -73.9969],
        "West Side Highway at 60th St": [40.7713, -73.9902],
        "West 60th St": [40.7700, -73.9836],
        "Queensboro Bridge": [40.7570, -73.9544],
        "Queens Midtown Tunnel": [40.7433, -73.9698],
        "Lincoln Tunnel": [40.7600, -74.0030],
        "Holland Tunnel": [40.7260, -74.0086],
        "FDR Drive at 60th St": [40.7626, -73.9585],
        "East 60th St": [40.7616, -73.9641],
        "Williamsburg Bridge": [40.7132, -73.9712],
        "Manhattan Bridge": [40.7075, -73.9903],
        "Hugh L. Carey Tunnel": [40.7003, -74.0132]
    }
    m = folium.Map(location=location_coords["Lincoln Tunnel"], zoom_start=18, tiles='CartoDB positron')
    map_name = m.get_name()
    
    m.add_child(
        folium.LatLngPopup()
    )
    map_html = m.get_root().render()
    while True:
        map_html = m.get_root().render()
        # print("hi")
    
    
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
      </body>
    </html>
    """

    return html_template