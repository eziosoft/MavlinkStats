from threading import Thread
from time import time, sleep

from flask import Flask, render_template_string, redirect, url_for
from pymavlink import mavutil

from config import DRONE_CONNECTION

app = Flask(__name__)

mav_connection = None
mavlink_data = {}
message_timestamps = {}
detected_systems = set()
STALE_TIME = 5  # Time in seconds before a MAVLink message is considered stale

request_data_streams = []  # Stores received REQUEST_DATA_STREAM messages

# Expected message and frequency
expected_messages = {
    # "HEARTBEAT": 1,
    "GLOBAL_POSITION_INT": 1,
    "SYS_STATUS": 1,
    "BATTERY_STATUS": 1,
    "GPS_RAW_INT": 1,
    "VIBRATION": 2,
    "ATTITUDE": 4,
    "MISSION_CURRENT": 0.5,
    "FENCE_STATUS": 1,
    # "STATUSTEXT": 0,  # No fixed frequency (event-based)
    "RANGEFINDER": 1,
    "LANDING_TARGET": 16,
}


def connect_to_mavlink():
    """Establishes connection to MAVLink and waits for a heartbeat."""
    global mav_connection
    while True:
        try:
            print("Connecting to MAVLink system...")
            mav_connection = mavutil.mavlink_connection(DRONE_CONNECTION,
                                                        autoreconnect=True,
                                                        source_system=0,
                                                        source_component=0)
            print("Connected!")
            print("Waiting for heartbeat...")
            mav_connection.wait_heartbeat(timeout=10)
            print("Heartbeat received!")

            # Send initial heartbeat
            mav_connection.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                0, 0, 0
            )
            return  # Exit loop on successful connection
        except Exception as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            sleep(5)


def get_command_name(command_id):
    commands_names = {
        33: "GLOBAL_POSITION_INT",
        42: "MISSION_CURRENT",
        162: "FENCE_STATUS",
        173: "RANGEFINDER"
    }
    return commands_names.get(command_id, command_id)


def handle_mavlink_messages():
    global mavlink_data, message_timestamps, detected_systems, request_data_streams
    while True:
        try:
            msg = mav_connection.recv_match(blocking=False)
            if not msg:
                continue

            system_id = msg.get_srcSystem()
            component_id = msg.get_srcComponent()
            detected_systems.add((system_id, component_id))

            message_type = msg.get_type()
            message_fields = msg.to_dict()

            if message_type == "COMMAND_LONG" and message_fields['command'] == 511:
                print(msg)

            # Capture REQUEST_DATA_STREAM messages
            if message_type == "COMMAND_LONG" and message_fields['command'] == 511:
                # mavutil.mavlink.MAV_CMD_REQUEST_DATA_STREAM:
                print("Received REQUEST_DATA_STREAM message:", message_fields)
                request_data_streams.append({
                    "requesting_system": system_id,
                    "requesting_component": component_id,
                    "target_system": message_fields.get("target_system", "N/A"),
                    "target_component": message_fields.get("target_component", "N/A"),
                    "command": get_command_name(message_fields.get("param1")),
                    "frequency": 1e6 / message_fields.get("param2", "Unknown"),
                })

            # Store message data
            mavlink_data[message_type] = {
                "fields": message_fields,
                "source_system": system_id,
                "source_component": component_id,
            }

            # Calculate frequency
            current_time = time()
            if message_type in message_timestamps:
                delta_time = current_time - message_timestamps[message_type]['last_time']
                message_timestamps[message_type]['frequency'] = 1 / delta_time if delta_time > 0 else 0
            else:
                message_timestamps[message_type] = {'last_time': current_time, 'frequency': 0}

            message_timestamps[message_type]['last_time'] = current_time

            # Remove stale messages
            stale_messages = [msg for msg, data in message_timestamps.items() if
                              current_time - data['last_time'] > STALE_TIME]
            for stale_msg in stale_messages:
                del mavlink_data[stale_msg]
                del message_timestamps[stale_msg]
        except Exception as e:
            print(f"Lost connection: {e}. Attempting to reconnect...")
            connect_to_mavlink()


mavlink_thread = Thread(target=handle_mavlink_messages)
mavlink_thread.daemon = True
mavlink_thread.start()


@app.route('/reset', methods=['POST'])
def reset_data():
    global mavlink_data, message_timestamps, detected_systems

    # Reset the MAVLink data, timestamps, and detected systems
    mavlink_data = {}
    message_timestamps = {}
    detected_systems = set()
    request_data_streams.clear()

    # Redirect back to the /drone_stats page
    return redirect(url_for('get_drone_stats'))


@app.route('/drone_stats', methods=['GET'])
def get_drone_stats():
    global message_timestamps, detected_systems, expected_messages, mavlink_data

    missing_messages = [msg for msg in expected_messages if msg not in mavlink_data]

    # Allow ±20% deviation for "good" frequency
    def get_row_class(message, actual_freq):
        if message not in expected_messages:
            return ""  # Not in the list → No color

        expected_freq = expected_messages[message]
        if expected_freq == 0:
            return ""  # No expected frequency (e.g., event-based messages)

        lower_bound = expected_freq * 0.8
        upper_bound = expected_freq * 1.2

        if lower_bound <= actual_freq <= upper_bound:
            return "good"  # Green for good frequency
        else:
            return "bad"  # Red for out-of-range frequency

    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Drone MAVLink Stats</title>
    <meta http-equiv="refresh" content="1">
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; font-size: 12px; }
        .container { display: flex; width: 100vw; height: 100vh; }
        .left, .right { padding: 20px; flex: 1; overflow: auto; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 12px; }
        th, td { border: 1px solid black; padding: 8px; text-align: left; }
        th { background-color: #ddd; }
        .good { background-color: lightgreen; }  
        .bad { background-color: lightcoral; }  
        .legend { margin-top: 5px; padding: 5px; display: inline-block; }
        .legend span { display: inline-block; width: 20px; height: 20px; margin-right: 5px; border: 1px solid #000; }
        button { margin-top: 10px; padding: 10px; background-color: red; color: white; border: none; cursor: pointer; font-size: 16px; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="left">
            <h2>Detected Systems</h2>
            <table>
                <tr>
                    <th>System ID</th>
                    <th>Component ID</th>
                </tr>
                {% for system, component in detected_systems %}
                <tr>
                    <td>{{ system }}</td>
                    <td>{{ component }}</td>
                </tr>
                {% endfor %}
            </table>

            <h2>REQUEST_DATA_STREAM Messages</h2>
            <table>
                <tr>
                    <th>Requesting System</th>
                    <th>Requesting Component</th>
                    <th>Target System</th>
                    <th>Target Component</th>
                    <th>Command</th>
                    <th>Requested Frequency (Hz)</th>
                </tr>
                {% for request in request_data_streams %}
                <tr>
                    <td>{{ request.requesting_system }}</td>
                    <td>{{ request.requesting_component }}</td>
                    <td>{{ request.target_system }}</td>
                    <td>{{ request.target_component }}</td>
                    <td>{{ request.command }}</td>
                    <td>{{ request.frequency }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        <div class="right">
            <form action="/reset" method="post">
                <button type="submit">Reset Data</button>
            </form>

            <h2>MAVLink Message Frequencies</h2>
            <div class="legend">
                <p><span class="good"></span> Frequency is within range (±20%)  <span class="bad"></span> Frequency is out of range</p>
            </div>

            <p style="color: red;"><b>Missing messages: {{ missing_messages }}</b></p>
            <table>
                <tr>
                    <th>Message Type</th>
                    <th>Source System</th>
                    <th>Source Component</th>
                    <th>Target System</th>
                    <th>Target Component</th>
                    <th>Expected Frequency (Hz)</th>
                    <th>Actual Frequency (Hz)</th>
                </tr>
                {% for message, data in message_timestamps.items() %}
                {% set actual_freq = data['frequency'] %}
                {% set message_data = mavlink_data.get(message, {}) %}
                <tr class="{{ get_row_class(message, actual_freq) }}">
                    <td>{{ message }}</td>
                    <td>{{ message_data.get("source_system", "N/A") }}</td>
                    <td>{{ message_data.get("source_component", "N/A") }}</td>
                    <td>{{ message_data.get("target_system", "N/A") }}</td>
                    <td>{{ message_data.get("target_component", "N/A") }}</td>
                    <td>{{ expected_frequencies.get(message, 'N/A') }}</td>
                    <td>{{ '%.2f'|format(actual_freq) }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </div>
</body>
</html>
    """

    return render_template_string(html_template,
                                  message_timestamps=message_timestamps,
                                  detected_systems=detected_systems,
                                  expected_frequencies=expected_messages,
                                  get_row_class=get_row_class,
                                  mavlink_data=mavlink_data,
                                  request_data_streams=request_data_streams,
                                  missing_messages=missing_messages)


if __name__ == '__main__':
    print("Starting API server...")
    app.run(host='0.0.0.0', port=5001)
