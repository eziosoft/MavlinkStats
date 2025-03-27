# MAVLink Drone Monitoring System

## Overview

This project provides a real-time MAVLink-based drone monitoring system using Flask and pymavlink. It establishes a
connection with a MAVLink-enabled drone, listens for messages, and visualizes data such as message frequencies, detected
systems, and requested data streams via a web interface.

## Features

- **MAVLink Connection:** Automatically connects to a MAVLink system and listens for messages.
- **Live Data Display:** Displays detected MAVLink systems and components.
- **Message Frequency Monitoring:** Tracks expected vs. actual frequencies of MAVLink messages.
- **REQUEST_DATA_STREAM Capturing:** Logs data stream requests from the drone.
- **Web Interface:** Provides a real-time dashboard for monitoring.
- **Reset Functionality:** Allows resetting the collected MAVLink data.

## Installation

### Prerequisites

Ensure you have the following installed:

- Python 3.8+
- pip
- MAVProxy or any MAVLink-compatible communication method

### Dependencies

Install the required Python packages:

```sh
pip install -r requirements.txt
```

## Configuration

Modify the `config.py` file to set the correct drone connection string:

```python
DRONE_CONNECTION = "udp:127.0.0.1:14550"  # Adjust as needed
```

## Running the Application

Run the Flask server with:

```sh
python main.py
```

This will start a web server on `http://localhost:5001/`.

## Web Interface

- **`/drone_stats`**: Displays real-time MAVLink message frequencies, detected systems, and data stream requests.
- **`/reset`** (POST): Resets stored MAVLink data.

## License

This project is released under the MIT License.

