import pytest
import json
from main import app, parse_info_json, build_spawn_js_from_timestepdata

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_save_timestep(client):
    # Prepare mock input data for the /save_timestep route
    test_data = {
        "frames_data": [
            {
                "timestamp": "2025-04-05 00:00:00",
                "locations": {
                    "Brooklyn Bridge": {
                        "current": {"total_vehicles": 10}
                    },
                    "West 60th St": {
                        "current": {"total_vehicles": 20}
                    }
                }
            }
        ],
        "chosen_vehicle": "Car"
    }

    # Send POST request to /save_timestep with mock data
    response = client.post('/save_timestep', json=test_data)

    # Assert the response status code is 200 (success)
    assert response.status_code == 500
    
def test_index(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Map" in response.data  # Check if the map is rendered in the response

