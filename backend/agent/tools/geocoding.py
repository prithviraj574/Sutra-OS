import requests
from dotenv import load_dotenv
import os

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

def get_coordinates(city: str = None, state_code: str = None, country_code: str = None) -> str:
    if city is None and state_code is None and country_code is None:
        return "Please provide at least one of city, state_code, or country_code"
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={city},{state_code},{country_code}&appid={OPENWEATHER_API_KEY}"
    response = requests.get(url)
    data = response.json()
    return data



from ..models import AgentTool
get_coordinates_tool = AgentTool(
    type="function",
    function={
        "name": "get_coordinates",
        "description": "Get coordinates for a given city, state_code, and country_code",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Optional. City name"
                },
                "state_code": {
                    "type": "string",
                    "description": "Optional. State code"
                },
                "country_code": {
                    "type": "string",
                    "description": "Optional. Country code"
                }
            },
            "required": []
        }
    }
)

if __name__ == "__main__":
    print(get_coordinates("Delhi", "DL", "IN"))
