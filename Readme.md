# Drone MAVLink Dashboard

This project is a Flask-based web dashboard for monitoring MAVLink messages from a drone. It provides real-time data on
detected MAVLink systems, message frequencies, and REQUEST_DATA_STREAM messages.

## Features

- **Real-time MAVLink message monitoring**
- **Displays detected MAVLink systems**
- **Shows message frequencies with status indicators**
- **Captures REQUEST_DATA_STREAM messages**
- **Automatically reconnects to MAVLink on failure**
- **Provides a reset button to clear data**

## Requirements

- Python 3.x
- Flask
- pymavlink
- jQuery (for frontend updates)

## Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/yourusername/mavlink-dashboard.git
   cd mavlink-dashboard
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Configure the MAVLink connection in `config.py`:
   ```python
   DRONE_CONNECTION = 'udp:127.0.0.1:14550'  # Adjust as needed
   ```

## Running the Dashboard

Start the Flask server:

```sh
python main.py
```

Access the dashboard in your web browser at:

```
http://localhost:5001
```

## API Endpoints

- `/` - Main web dashboard
- `/drone_stats_data` - Returns real-time MAVLink stats as JSON
- `/reset` - Resets all stored data (POST request)

## Contributing

Pull requests are welcome! Please open an issue first to discuss any major changes.

## License

MIT License

