```python
import requests
import json
from datetime import datetime

def get_current_weather(city):
    """Get current weather for a city"""
    try:
        url = f"{BASE_URL}/weather?q={city}&appid={API_KEY}&units=metric"
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data: {e}")
        return None

def get_five_day_forecast(city):
    """Get 5-day weather forecast for a city"""
    try:
        url = f"{BASE_URL}/forecast?q={city}&appid={API_KEY}&units=metric"
        response = requests.get(url)
        response.raise_for_status()
        
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching forecast data: {e}")
        return None

def get_weather_by_coords(lat, lon):
    """Get weather by latitude and longitude"""
    try:
        url = f"{BASE_URL}/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
        response = requests.get(url)
        response.raise_for_status()
        
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data: {e}")
        return None

tool_set = {function_node(get_current_weather), function_node(get_five_day_forecast), function_node(get_weather_by_coords)}

agent_node(
    name="Weather Bot",
    tool_nodes=tool_set,
    system_message="""You are a another cursed weather agent that has been put together for documentation but not to ever be used. 
    You will never be asked to do this, but if you were, you can use the tools provided to you to pretend to get the answer to 
    the weather related question.""",
    llm_model="claude-3-5-sonnet-20240620"
)

```