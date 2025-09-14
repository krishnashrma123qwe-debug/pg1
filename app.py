from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import random
import pyttsx3
import threading

# ========== FLASK SETUP ==========
app = Flask(__name__)
app.secret_key = "supersecretkey"  # change this to a strong random string

# ========== LOGIN CREDENTIALS ==========
USERNAME = "admin"
PASSWORD = "raspberry"

# ========== DEVICE & SYSTEM STATES ==========
devices = {"light": False, "fan": False, "ac": False}
fan_speed = 50  # Default fan speed (0-100)
emergency_active = {"status": False, "message": "✅ No emergency."}
notifications = []


# ========== SENSOR SIMULATION ==========
def read_sensors():
    temperature = round(random.uniform(20.0, 30.0), 1)
    humidity = round(random.uniform(40.0, 60.0), 1)
    return {"temperature": temperature, "humidity": humidity}


def read_door_sensors():
    main_door_open = random.choice([True, False])
    window_open = random.choice([True, False])
    return {"main_door_open": main_door_open, "window_open": window_open}


# ========== SPEECH ==========
def speak(text):
    def run():
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print("Speech error:", e)

    threading.Thread(target=run).start()


# ========== NOTIFICATIONS ==========
def add_notification(message):
    notifications.append(message)
    if len(notifications) > 10:
        notifications.pop(0)


# ========== AUTOMATION RULES ==========
def automation_rules():
    sensor_data = read_sensors()
    temperature = sensor_data["temperature"]
    humidity = sensor_data["humidity"]

    if temperature > 28 and not devices["ac"]:
        devices["ac"] = True
        msg = "🌡️ Temperature is high. Turning on the AC."
        speak(msg)
        add_notification(msg)
    elif temperature < 24 and devices["ac"]:
        devices["ac"] = False
        msg = "🌡️ Temperature is comfortable. Turning off the AC."
        speak(msg)
        add_notification(msg)

    if humidity > 65 and not devices["fan"]:
        devices["fan"] = True
        msg = "💧 Humidity is high. Turning on the fan."
        speak(msg)
        add_notification(msg)
    elif humidity < 50 and devices["fan"]:
        devices["fan"] = False
        msg = "💧 Humidity is low. Turning off the fan."
        speak(msg)
        add_notification(msg)


# ========== AUTH ROUTES ==========
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uname = request.form["username"]
        pword = request.form["password"]

        if uname == USERNAME and pword == PASSWORD:
            session["user"] = uname
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="❌ Invalid credentials")

    return render_template("login.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


# ========== MAIN ROUTES ==========
@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))

    sensor_data = read_sensors()
    door_data = read_door_sensors()
    return render_template(
        "index.html",
        devices=devices,
        fan_speed=fan_speed,
        sensor_data=sensor_data,
        door_data=door_data,
    )


@app.route("/toggle_device", methods=["POST"])
def toggle_device():
    if "user" not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    device = request.json.get("device")
    if device in devices:
        devices[device] = not devices[device]
        state = "ON" if devices[device] else "OFF"
        msg = f"💡 The {device} has been turned {state}."
        speak(msg)
        add_notification(msg)
        return jsonify({"status": "success", "state": state})
    return jsonify({"status": "error", "message": "Invalid device"})


# ========== FAN SPEED ==========
@app.route("/set_fan_speed")
def set_fan_speed():
    global fan_speed
    if "user" not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    value = request.args.get("value", type=int)
    if value is None or not (0 <= value <= 100):
        return jsonify({"status": "error", "message": "Invalid speed value"})

    fan_speed = value
    msg = f"🌀 Fan speed set to {fan_speed}%"
    speak(msg)
    add_notification(msg)
    print(f"Fan PWM set to {fan_speed}%")  # Later, connect to GPIO PWM here
    return jsonify({"status": "success", "fan_speed": fan_speed})


# ========== OTHER ROUTES ==========
@app.route("/get_sensor_data")
def get_sensor_data():
    return jsonify(read_sensors())


@app.route("/get_door_sensors")
def get_door_sensors():
    return jsonify(read_door_sensors())


@app.route("/run_automation", methods=["POST"])
def run_automation():
    if "user" not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    automation_rules()
    return jsonify({"status": "success", "devices": devices, "fan_speed": fan_speed})


@app.route("/voice_command", methods=["POST"])
def voice_command():
    if "user" not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    command = request.json.get("command", "").lower()
    message, device, state = "Command not understood.", "", ""

    if "light" in command:
        if "on" in command:
            devices["light"] = True; state = "ON"; message = "Turning on the light."
        elif "off" in command:
            devices["light"] = False; state = "OFF"; message = "Turning off the light."
        device = "light"

    elif "fan" in command:
        if "on" in command:
            devices["fan"] = True; state = "ON"; message = "Turning on the fan."
        elif "off" in command:
            devices["fan"] = False; state = "OFF"; message = "Turning off the fan."
        device = "fan"

    elif "ac" in command:
        if "on" in command:
            devices["ac"] = True; state = "ON"; message = "Turning on the AC."
        elif "off" in command:
            devices["ac"] = False; state = "OFF"; message = "Turning off the AC."
        device = "ac"

    if device:
        speak(message)
        add_notification(f"🎙️ Voice command: {message}")
        return jsonify(
            {"status": "success", "message": message, "device": device, "state": state}
        )
    else:
        return jsonify({"status": "error", "message": "Could not understand command."})


@app.route("/get_emergency_status")
def get_emergency_status():
    global emergency_active

    detected = random.choice([True, False, False, False])  # ~25% chance
    if detected:
        for dev in devices:
            devices[dev] = False
        emergency_active["status"] = True
        emergency_active[
            "message"
        ] = "🔥 Fire/Gas detected! All devices OFF. Alerting Fire Department!"
        speak("Emergency detected! Alerting Fire Department!")
        add_notification(emergency_active["message"])
    else:
        emergency_active["status"] = False
        emergency_active["message"] = "✅ No emergency."

    return jsonify(emergency_active)


@app.route("/get_notifications")
def get_notifications():
    return jsonify({"notifications": notifications})


# ========== RUN APP ==========
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
