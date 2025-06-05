from flask import Flask, render_template, request, jsonify, send_file
import requests
import datetime
import geopy.distance  # For distance calculation
from reportlab.pdfgen import canvas
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Spacer
app = Flask(__name__)

# API KEYS
OPENWEATHER_API_KEY = "c8593f87ce30eebe6f6ba205fd5a4276"
NASA_API_KEY = "tWoH0jmQBEkUXEulVWDHBDUc7iKhrZVFIntkcbjN"

# Disaster APIs
USGS_EARTHQUAKE_API = "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={}&endtime={}&minlatitude=6&maxlatitude=36&minlongitude=68&maxlongitude=97"
FLOOD_WARNING_URL = "https://indiawris.gov.in/wris/#/FloodWarningMap"
USGS_TSUNAMI_API = "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&minmagnitude=5&starttime={}&endtime={}&minlatitude=-60&maxlatitude=60&minlongitude=-180&maxlongitude=180"

# Logging function
def log_event(tag, data):
    print(f"\n🔹 {tag}:\n{data}\n")


# Get Coordinates
def get_coordinates(location):
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={location}&limit=1&appid={OPENWEATHER_API_KEY}"
    response = requests.get(url).json()
    
    log_event("Coordinates API Response", response)

    if response:
        return response[0]["lat"], response[0]["lon"], True
    return None, None, False


# Weather Forecast
def get_weather_forecast(lat, lon, user_datetime):
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
    response = requests.get(url).json()

    log_event("Weather API Response", response)

    if "list" in response:
        best_match = min(response["list"], key=lambda x: abs((datetime.datetime.strptime(x["dt_txt"], "%Y-%m-%d %H:%M:%S") - user_datetime).total_seconds()), default=None)

        if best_match:
            return {
                "weather": best_match["weather"][0]["main"],
                "temperature": best_match["main"]["temp"],
                "humidity": best_match["main"]["humidity"],
                "wind_speed": best_match["wind"]["speed"],
                "rain": best_match.get("rain", {}).get("3h", 0),
                "status": "success"
            }

    return {"status": "failed"}


# Fixed Earthquake Alert Logic
def get_earthquake_alerts(lat, lon, user_datetime):
    start_date = (datetime.datetime.utcnow() - datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    end_date = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    response = requests.get(USGS_EARTHQUAKE_API.format(start_date, end_date)).json()

    log_event("Earthquake API Response", response)

    if "features" in response:
        for quake in response["features"]:
            quake_lat = quake["geometry"]["coordinates"][1]
            quake_lon = quake["geometry"]["coordinates"][0]
            quake_time = datetime.datetime.utcfromtimestamp(quake["properties"]["time"] / 1000)
            
            # Calculate time difference from user input
            time_difference = abs((quake_time - user_datetime).total_seconds()) / 3600  # in hours

            # Calculate distance from user location
            distance_km = geopy.distance.geodesic((lat, lon), (quake_lat, quake_lon)).km
            
            # If the earthquake is within 500 km and time is within 12 hours → Mark as failed
            if distance_km <= 500 and time_difference <= 12:
                return {"status": "failed"}  # Earthquake detected in proximity & time

        return {"status": "success"}  # No earthquake detected in proximity & time

    return {"status": "success"}  # If no data available, assume no earthquake


# Flood Alerts
def get_flood_alerts():
    try:
        response = requests.get(FLOOD_WARNING_URL, verify=False)
        log_event("Flood API Response", response.status_code)
        return [{"status": "success"}] if response.status_code == 200 else [{"status": "failed"}]
    except:
        return [{"status": "failed"}]


# Tsunami Alerts
def get_tsunami_alerts():
    try:
        start_date = (datetime.datetime.utcnow() - datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        end_date = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        
        url = USGS_TSUNAMI_API.format(start_date, end_date)
        response = requests.get(url).json()

        log_event("Tsunami API Response", response)

        if "features" in response:
            for quake in response["features"]:
                if quake["properties"].get("tsunami", 0) == 1:
                    return [{"status": "failed", "message": "Tsunami alert detected!"}]
            
            return [{"status": "success", "message": "No tsunami risk detected"}]
        
        return [{"status": "failed", "message": "No data available"}]
    
    except Exception as e:
        log_event("Tsunami API Error", str(e))
        return [{"status": "failed", "message": "Error retrieving tsunami data"}]


# NASA Flood Data
def get_nasa_flood_data(lat, lon):
    try:
        url = f"https://api.nasa.gov/planetary/earth/assets?lon={lon}&lat={lat}&api_key={NASA_API_KEY}"
        response = requests.get(url).json()

        log_event("NASA API Response", response)

        if "url" in response:
            return [{"status": "success", "image": response["url"]}]
        
        return [{"status": "no_risk"}]
    except:
        return [{"status": "failed"}]


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/check_disaster', methods=['POST'])
def check_disaster():
    data = request.json
    location = data["location"]
    date_input = data["date"]
    time_input = data["time"]
    user_datetime = datetime.datetime.strptime(f"{date_input} {time_input}", "%Y-%m-%d %H:%M")

    lat, lon, location_status = get_coordinates(location)

    if not location_status:
        return jsonify({"error": "Invalid location"})

    # 🔹 Store assessment results in a variable
    disaster_report = {
        "location": location,
        "date_time": user_datetime.strftime('%Y-%m-%d %H:%M'),
        "weather": get_weather_forecast(lat, lon, user_datetime) or {"status": "failed"},
        "earthquake": get_earthquake_alerts(lat, lon, user_datetime) or {"status": "failed"},
        "flood": get_flood_alerts() or [{"status": "failed"}],
        "tsunami": get_tsunami_alerts() or [{"status": "failed"}],
        "nasa_flood": get_nasa_flood_data(lat, lon) or [{"status": "failed"}]
    }

    # 🔹 Log data for debugging
    log_event("Final API Response", disaster_report)

    # 🔹 Save to a global variable for reuse (optional)
    global last_disaster_report
    last_disaster_report = disaster_report

    return jsonify(disaster_report)


@app.route('/download_report', methods=['POST'])
def download_report():
    global last_disaster_report

    if not last_disaster_report:
        return jsonify({"error": "No report available. Run disaster check first."})

    data = last_disaster_report  # Use stored API response data

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    title = Paragraph("<b>Disaster Risk Assessment Report</b>", styles["Title"])
    elements.append(title)
    elements.append(Spacer(1, 12))

    # **Basic Information Section**
    location_info = [
        ["Location:", data["location"]],
        ["Date & Time:", data["date_time"]]
    ]
    table = Table(location_info, colWidths=[150, 350])
    table.setStyle(TableStyle([
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>Disaster Reports</b>", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    # **Table Data with Colspan Fix**
    report_data = [
        ["Category", "Details"]
    ]

    # **Weather Report (Properly Merged)**
    weather = data.get("weather", {})
    if weather:
        report_data.append([Paragraph("<b>Weather Evaluation</b>", styles["Heading3"]), ""])
        for key, value in weather.items():
            report_data.append([key.capitalize(), str(value)])

    # **Earthquake Report (Fixed)**
    earthquake = data.get("earthquake", {})
    if earthquake:
        report_data.append([Paragraph("<b>Earthquake Evaluation</b>", styles["Heading3"]), ""])
        report_data.append(["Status", str(earthquake.get("status", "Unknown"))])

    # **Tsunami Report (Fixed)**
    tsunami = data.get("tsunami", [{}])[0]
    if tsunami:
        report_data.append([Paragraph("<b>Tsunami Report</b>", styles["Heading3"]), ""])
        report_data.append(["Status", str(tsunami.get("status", "Unknown"))])
        if "message" in tsunami:
            report_data.append(["Message", str(tsunami["message"])])

    # **Flood Report (Fixed)**
    flood = data.get("flood", [{}])[0]
    if flood:
        report_data.append([Paragraph("<b>Flood Evaluation</b>", styles["Heading3"]), ""])
        report_data.append(["Status", str(flood.get("status", "Unknown"))])

    # **NASA Flood Detection (Hyperlink Fixed)**
    nasa_flood = data.get("nasa_flood", [{}])[0]
    if nasa_flood:
        report_data.append([Paragraph("<b>NASA Flood Detection</b>", styles["Heading3"]), ""])
        report_data.append(["Status", str(nasa_flood.get("status", "Unknown"))])
        if "image" in nasa_flood:
            clickable_text = f'<a href="{nasa_flood["image"]}" color="blue">Click Here to View</a>'
            report_data.append(["Image", Paragraph(clickable_text, styles["Normal"])])

    # **Creating Table with Proper Formatting**
    disaster_table = Table(report_data, colWidths=[180, 320])

    # **Applying Styles to Table**
    disaster_table.setStyle(TableStyle([
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 12),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
        ("SPAN", (0, 1), (-1, 1)),  # Weather Report merged
        ("SPAN", (0, 7), (-1, 7)),  # Earthquake Report merged
        ("SPAN", (0, 10), (-1, 10)),  # Tsunami Report merged
        ("SPAN", (0, 13), (-1, 13)),  # Flood Report merged
        ("SPAN", (0, 15), (-1, 15)),  # NASA Flood Detection merged
    ]))

    elements.append(disaster_table)
    elements.append(Spacer(1, 20))

    # **Footer**
    elements.append(Paragraph("<b>Stay Safe! Disaster Risk Management Team</b>", styles["Normal"]))
    
    doc.build(elements)
    pdf_buffer.seek(0)

    return send_file(pdf_buffer, as_attachment=True, download_name="Disaster_Report.pdf", mimetype="application/pdf")



if __name__ == '__main__':
    app.run(debug=True, port=5000)

#PROJECT DEVELOPED BY ZELINE PROJECTS SERVICES, HTTPS://ZELINEPROJECTS.SHOP