# weather_helper.py

import requests

OPENCAGE_API_KEY = 'd88c9bf77f934a8f8dc334ed61a5f8d3'
OPENWEATHER_API_KEY = '5c1fa4fe1d7ddff11ae456702cc3186a'

def get_lat_lon_from_pincode(pincode):
    url = f"https://api.opencagedata.com/geocode/v1/json?q={pincode}&key={OPENCAGE_API_KEY}"
    response = requests.get(url)
    data = response.json()

    if data.get("results"):
        geometry = data["results"][0]["geometry"]
        return geometry["lat"], geometry["lng"]
    else:
        raise Exception("Pincode not found or invalid")

def get_weather_by_pincode(pincode):
    try:
        lat, lon = get_lat_lon_from_pincode(pincode)
        weather_url = (
            f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
        )
        response = requests.get(weather_url)
        data = response.json()

        if "weather" in data and "main" in data:
            weather_desc = data["weather"][0]["description"]
            icon = data["weather"][0]["icon"]
            temp = data["main"]["temp"]
            city = data["name"]
            rain = data.get("rain", {})
            is_raining = "rain" in weather_desc.lower() or rain != {}

            alert_msg = f"⚠ Rain predicted: {weather_desc}" if is_raining else f"✅ Weather is clear: {weather_desc}"
            weather_info = {
                "temp": temp,
                "feels_like": data["main"]["feels_like"],
                "humidity": data["main"]["humidity"],
                "wind_speed": data["wind"]["speed"],
                "description": weather_desc,
                "icon": icon,
                "city": city
            }

            return alert_msg, weather_info
        else:
            return "⚠ Weather data incomplete.", None
    except Exception as e:
        print("Weather error:", e)
        return "⚠ Weather data could not be fetched.", None


def get_city_from_address(pincode=None, address=None):
    query = None
    if pincode:  # ✅ Prefer pincode if available
        query = str(pincode)
    elif address:
        query = address

    if not query:
        return None

    url = f"https://api.opencagedata.com/geocode/v1/json?q={query}&key={OPENCAGE_API_KEY}"
    response = requests.get(url)
    data = response.json()

    if data.get("results"):
        components = data["results"][0]["components"]
        city = (
            components.get("city")
            or components.get("town")
            or components.get("village")
            or components.get("municipality")
            or components.get("state_district")
        )
        if city and "taluk" in city.lower():
            city = city.replace("taluk", "").strip()
        return city
    return None
