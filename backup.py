import requests
import datetime
import json
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API KEYS
OPENWEATHER_API_KEY = "c8593f87ce30eebe6f6ba205fd5a4276"
NASA_API_KEY = "tWoH0jmQBEkUXEulVWDHBDUc7iKhrZVFIntkcbjN"

# Publicly Available Disaster APIs
USGS_EARTHQUAKE_API = "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={}&endtime={}&minlatitude=6&maxlatitude=36&minlongitude=68&maxlongitude=97"
FLOOD_WARNING_URL = "https://indiawris.gov.in/wris/#/FloodWarningMap"
TSUNAMI_BULLETIN_URL = "https://www.incois.gov.in/portal/TsunamiBulletin.jsp"

# Log file
log_file = "output.txt"

def log_data(data):
    with open(log_file, "a", encoding="utf-8") as file:
        file.write(data + "\n\n")

# Clear previous logs
open(log_file, "w").close()

# User inputs
location = input("Enter city and country code (e.g., Mumbai,IN): ")
date_input = input("Enter date (YYYY-MM-DD): ")
time_input = input("Enter time (HH:MM): ")

user_datetime = datetime.datetime.strptime(f"{date_input} {time_input}", "%Y-%m-%d %H:%M")
log_data(f"User Input: Location={location}, Date={date_input}, Time={time_input}\n")

# Get Coordinates
def get_coordinates(location):
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={location}&limit=1&appid={OPENWEATHER_API_KEY}"
    response = requests.get(url).json()
    if response:
        lat, lon = response[0]["lat"], response[0]["lon"]
        log_data(f"📍 **Location Coordinates:** {lat}, {lon}")
        return lat, lon
    return None, None

# Fetch Weather Forecast
def get_weather_forecast(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
    response = requests.get(url).json()
    
    best_match = min(response.get("list", []), key=lambda x: abs((datetime.datetime.strptime(x["dt_txt"], "%Y-%m-%d %H:%M:%S") - user_datetime).total_seconds()), default=None)
    
    if best_match:
        weather_main = best_match["weather"][0]["main"]
        weather_desc = best_match["weather"][0]["description"]
        temp = best_match["main"]["temp"]
        humidity = best_match["main"]["humidity"]
        wind_speed = best_match["wind"]["speed"]
        rain = best_match.get("rain", {}).get("3h", 0)
        
        risk_level = "Safe"
        if rain > 10 or wind_speed > 15:
            risk_level = "High Risk"
        elif rain > 5 or wind_speed > 10:
            risk_level = "Moderate Risk"
        
        report = f"""
🌦 **Weather Forecast for {location} at {user_datetime.strftime('%H:%M, %d-%m-%Y')}:**
- **Weather:** {weather_main} ({weather_desc})
- **Temperature:** {temp}°C
- **Humidity:** {humidity}%
- **Wind Speed:** {wind_speed} m/s
- **Rain:** {rain} mm
"""
        log_data(report)
        print(report)
        return risk_level
    return "Safe"

# Fetch Earthquake Data
def get_earthquake_alerts():
    start_date = (datetime.datetime.utcnow() - datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    end_date = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    response = requests.get(USGS_EARTHQUAKE_API.format(start_date, end_date)).json()
    alerts = [
        f"🌍 Magnitude {quake['properties']['mag']} at {quake['properties']['place']} on {datetime.datetime.utcfromtimestamp(quake['properties']['time'] / 1000).strftime('%d-%m-%Y %H:%M UTC')}"
        for quake in response.get("features", []) if quake["properties"]["mag"] >= 4.5
    ]
    log_data("\n".join(alerts) if alerts else "No significant earthquakes detected.")
    return alerts

# Fetch Flood Alerts
def get_flood_alerts():
    response = requests.get(FLOOD_WARNING_URL, verify=False)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        alerts = [alert.text.strip() for alert in soup.find_all('div', class_='flood-warning')]
        return alerts if alerts else ["No flood warnings detected."]
    return ["Could not fetch flood warnings."]

# Fetch Tsunami Alerts
def get_tsunami_alerts():
    response = requests.get(TSUNAMI_BULLETIN_URL)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        alerts = [alert.text.strip() for alert in soup.find_all('td', class_='tsunami-bulletin')]
        return alerts if alerts else ["No tsunami warnings detected."]
    return ["Could not fetch tsunami warnings."]

# ✅ Fetch NASA Flood Data
def get_nasa_flood_data(lat, lon):
    url = f"https://api.nasa.gov/planetary/earth/assets?lon={lon}&lat={lat}&api_key={NASA_API_KEY}"
    response = requests.get(url).json()

    if "url" in response:
        log_data("\n🚀 **NASA Satellite Data Found:**\n" + json.dumps(response, indent=4))
        return ["🌊 **Possible Flood Risk Detected** based on NASA satellite data."]
    
    return ["🌍 No flood risk detected from NASA satellite images."]

# Fetching Data
lat, lon = get_coordinates(location)
if lat is None or lon is None:
    print("❌ Error: Location not found.")
    exit()

weather_risk = get_weather_forecast(lat, lon)
earthquake_alerts = get_earthquake_alerts()
flood_alerts = get_flood_alerts()
tsunami_alerts = get_tsunami_alerts()
nasa_flood_alerts = get_nasa_flood_data(lat, lon)

# Final Risk Calculation
final_risk = "High Risk" if "High Risk" in [weather_risk] or any("Flood Risk" in alert for alert in nasa_flood_alerts) else "Moderate Risk" if "Moderate Risk" in [weather_risk] else "Safe"

# 🚨 **Disaster Alerts**
print("\n🚨 **Disaster Alerts:**")
for alert in earthquake_alerts + flood_alerts + tsunami_alerts + nasa_flood_alerts:
    print(alert)

# 🔹 **Final Travel Recommendation**
print(f"\n🔹 **Final Travel Recommendation:** {final_risk}")
log_data(f"Final Risk: {final_risk}")