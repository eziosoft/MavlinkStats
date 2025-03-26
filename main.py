from threading import Thread
from time import time, sleep
from flask import Flask, render_template, jsonify, request
from pymavlink import mavutil
from config import DRONE_CONNECTION

app = Flask(__name__)

mav_connection = None
mavlink_data = {}
message_timestamps = {}
detected_systems = set()
STALE_TIME = 5  # Time in seconds before a MAVLink message is considered stale
request_data_streams = []  # Stores received REQUEST_DATA_STREAM messages

expected_messages = {
    "GLOBAL_POSITION_INT": 1,
    "SYS_STATUS": 1,
    "BATTERY_STATUS": 1,
    "GPS_RAW_INT": 1,
    "VIBRATION": 2,
    "ATTITUDE": 4,
    "MISSION_CURRENT": 0.5,
    "FENCE_STATUS": 1,
    "RANGEFINDER": 1,
    "LANDING_TARGET": 16,
}


def connect_to_mavlink():
    """Continuously attempts to establish connection to MAVLink"""
    global mav_connection
    while True:
        try:
            print("Connecting to MAVLink system...")
            mav_connection = mavutil.mavlink_connection(DRONE_CONNECTION, autoreconnect=True,
                                                        source_system=1,
                                                        source_component=0)
            print("Connected! Waiting for heartbeat...")
            mav_connection.wait_heartbeat(timeout=10)
            print("Heartbeat received!")
            send_heartbeat()
            print("HEARTBEAT sent!")
            return
        except Exception as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            sleep(5)


def send_heartbeat():
    """Sends a HEARTBEAT message to the connected MAVLink system"""
    mav_connection.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_GCS,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        0, 0, 0
    )


def get_command_name(param1):
    """Returns a human-readable name for a MAV_CMD_REQUEST_DATA_STREAM command."""
    stream_types = {
        0: "ALL",
        1: "RAW_SENSORS",
        2: "EXTENDED_STATUS",
        3: "RC_CHANNELS",
        4: "RAW_CONTROLLER",
        6: "POSITION",
        10: "EXTRA1",
        11: "EXTRA2",
        12: "EXTRA3",
    }
    return stream_types.get(int(param1), "UNKNOWN")


def handle_mavlink_messages():
    global mavlink_data, message_timestamps, detected_systems, request_data_streams
    while True:
        try:
            msg = mav_connection.recv_match(blocking=False)
            if not msg:
                continue

            # print(f"Received message: {msg.get_type()}")

            system_id = msg.get_srcSystem()
            component_id = msg.get_srcComponent()
            detected_systems.add((system_id, component_id))

            message_type = msg.get_type()
            message_fields = msg.to_dict()

            # Store message data
            mavlink_data[message_type] = {
                "fields": message_fields,
                "source_system": system_id,
                "source_component": component_id,
            }

            # Handle REQUEST_DATA_STREAM messages
            if message_type == "COMMAND_LONG":  # and message_fields.get('command') == 511:
                print(msg)
                # MAV_CMD_REQUEST_DATA_STREAM
                request_data_streams.append({
                    "requesting_system": system_id,
                    "requesting_component": component_id,
                    "target_system": message_fields.get("target_system", "N/A"),
                    "target_component": message_fields.get("target_component", "N/A"),
                    "command": f"Stream {int(message_fields.get('param1', -1))}",
                    "frequency": round(1e6 / message_fields.get("param2", 1), 2)
                })
                print(f"Received REQUEST_DATA_STREAM: {get_command_name(message_fields.get('param1', -1))}")

            # Calculate frequency
            current_time = time()
            if message_type in message_timestamps:
                delta_time = current_time - message_timestamps[message_type]['last_time']
                frequency = 1 / delta_time if delta_time > 0 else 0
                message_timestamps[message_type]['frequency'] = frequency
            else:
                message_timestamps[message_type] = {'last_time': current_time, 'frequency': 0}

            # Store source system/component
            message_timestamps[message_type]['source_system'] = system_id
            message_timestamps[message_type]['source_component'] = component_id
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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/drone_stats_data')
def drone_stats_data():
    """Returns MAVLink stats as JSON for AJAX updates"""
    missing_messages = [msg for msg in expected_messages if msg not in mavlink_data]

    message_data = {}
    for msg, timestamp in message_timestamps.items():
        source_system = mavlink_data[msg]["source_system"] if msg in mavlink_data else "N/A"
        source_component = mavlink_data[msg]["source_component"] if msg in mavlink_data else "N/A"

        message_data[msg] = {
            "last_time": timestamp["last_time"],
            "frequency": timestamp["frequency"],
            "source_system": source_system,
            "source_component": source_component,
        }

    return jsonify({
        "detected_systems": list(detected_systems),
        "mavlink_data": mavlink_data,
        "message_timestamps": message_data,  # Now includes system and component IDs
        "expected_frequencies": expected_messages,
        "request_data_streams": request_data_streams,
        "missing_messages": missing_messages
    })


@app.route('/reset', methods=['POST'])
def reset_data():
    """Resets stored MAVLink data"""
    global mavlink_data, message_timestamps, detected_systems, request_data_streams

    mavlink_data = {}
    message_timestamps = {}
    detected_systems = set()
    request_data_streams.clear()

    return jsonify({"status": "success"})


if __name__ == '__main__':
    print("Starting API server...")
    app.run(host='0.0.0.0', port=5001, debug=True)
