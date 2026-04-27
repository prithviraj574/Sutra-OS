import requests
from dotenv import load_dotenv
import os

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

def get_weather(lat: str, lon: str) -> str:
    url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}"
    response = requests.get(url)
    data = response.json()
    return data

from ..models import AgentTool
get_weather_tool = AgentTool(
    type="function",
    function={
        "name": "get_weather",
        "description": "Get weather for a given latitude and longitude",
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {
                    "type": "string",
                    "description": "Latitude"
                },
                "lon": {
                    "type": "string",
                    "description": "Longitude"
                }
            },
            "required": ["lat", "lon"]
        }
    }
)

if __name__ == "__main__":
    print(get_weather("28.6139", "77.2090"))
