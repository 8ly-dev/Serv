# Server-Sent Events Dashboard Demo ✅

A simple real-time dashboard built with Serv showcasing Server-Sent Events for live data streaming and dynamic updates.

## Features

- Real-time metrics streaming via SSE
- Live charts and gauges
- Simulated system data
- Multiple data streams
- Auto-refreshing dashboard
- Connection status indicator

## ✅ IMPLEMENTED FEATURES

### SSE Core Implementation
- ✅ Create SSE endpoint with proper headers
- ✅ Implement event formatting (data, event, id fields)
- ✅ Add client connection management
- ✅ Handle client disconnections gracefully
- ✅ Create event broadcasting system

### Simulated Metrics
- ✅ Generate fake CPU usage data
- ✅ Create memory usage simulation
- ✅ Add network traffic simulation
- ✅ Generate random system events
- ✅ Create temperature and load metrics

### Dashboard Frontend
- ✅ Create responsive HTML dashboard layout
- ✅ Implement JavaScript SSE client
- ✅ Add real-time chart rendering (custom canvas-based charts)
- ✅ Create metric cards and gauges
- ✅ Add connection status indicator
- ✅ Implement auto-reconnection logic

### Data Streaming
- ✅ Create periodic data generation (asyncio tasks)
- ✅ Implement different event types (metrics, alerts, status)
- ✅ Add data formatting for frontend consumption
- ✅ Create event filtering and routing
- ✅ Handle multiple concurrent connections

### Visual Components
- ✅ CPU usage gauge/chart
- ✅ Memory usage progress bar
- ✅ Network activity graph
- ✅ System alerts feed
- ✅ Uptime counter
- ✅ Active connections counter

### Extensions Integration
- ✅ Create DashboardExtension
- ✅ Add SSE middleware for connection handling
- ✅ Create metrics generation extension

## Running the Demo

### Quick Start
```bash
cd demos/sse_dashboard
python run_demo.py
```

### Using Serv CLI
```bash
cd demos/sse_dashboard
serv launch --dev
```

### Manual Start
```bash
cd demos/sse_dashboard
python -c "
import sys
sys.path.insert(0, '../..')
from serv import App
import uvicorn

app = App(config='./serv.config.yaml', extension_dir='./extensions', dev_mode=True)
uvicorn.run(app, host='127.0.0.1', port=8000)
"
```

Visit **http://localhost:8000** to view the real-time dashboard! 🚀

## File Structure

```
demos/sse_dashboard/
├── README.md                           # This file
├── requirements.txt                    # No extra deps needed
├── serv.config.yaml                   # Basic config
├── run_demo.py                        # Quick start script
├── extensions/
│   └── dashboard/
│       ├── __init__.py
│       ├── extension.yaml             # Extension config with declarative routers
│       └── main.py                    # SSE routes and metrics
└── static/
    ├── dashboard.js                   # SSE client and charts
    └── style.css                      # Dashboard styling
```

## Implementation Details

### Backend Architecture
- **Extension-based**: Uses Serv's extension system with declarative routing
- **Response Types**: Leverages `ServerSentEventsResponse` from `serv.routes`
- **Dependency Injection**: Uses Bevy DI for managing extension state
- **Background Tasks**: Asyncio tasks for metrics and alerts generation
- **Connection Management**: Queue-based connection handling for SSE streams

### Frontend Features
- **Pure JavaScript**: No external dependencies 
- **Custom Charts**: Canvas-based real-time charting
- **Responsive Design**: Works on desktop and mobile
- **Auto-reconnection**: Handles connection drops gracefully
- **Real-time Updates**: Live metrics with smooth animations

## SSE Endpoints

- `GET /` - Dashboard interface
- `GET /api/events/metrics` - System metrics stream
- `GET /api/events/alerts` - Alert notifications stream  
- `GET /api/events/all` - Combined event stream
- `GET /static/{filename}` - Static file serving

## Event Types

### Metrics Event
```json
{
  "type": "metric",
  "timestamp": "2024-01-01T12:00:00Z",
  "cpu": {"usage": 45.2, "history": [...]},
  "memory": {"usage": 67.5, "total": 16384, "used": 11059},
  "network": {"in": 125.3, "out": 89.1},
  "disk": {"usage": 67.5, "total": 512, "free": 166.4},
  "temperature": 47.8,
  "uptime": 86400,
  "connections": 3
}
```

### Alert Event
```json
{
  "type": "alert",
  "level": "warning", 
  "message": "High CPU usage detected",
  "timestamp": "2024-01-01T12:00:00Z",
  "source": "system"
}
```

## Dashboard Features

- **Real-time Metrics**: CPU, Memory, Network, Disk usage with live updates
- **Live Charts**: Canvas-based line charts showing metric history
- **System Alerts**: Categorized warning and info notifications
- **Connection Status**: Visual indicator of SSE connection health  
- **Auto-reconnect**: Exponential backoff reconnection strategy
- **Responsive Design**: Works on all screen sizes
- **Performance**: Optimized for smooth real-time updates

## Demo Data

The dashboard generates realistic but simulated data:
- **CPU usage**: 0-100% with realistic fluctuations using normal distribution
- **Memory usage**: Gradual changes with occasional spikes
- **Network traffic**: Random bursts of activity with baseline noise
- **System alerts**: Periodic warnings and status messages every 30-120 seconds
- **Temperature**: Correlated with CPU usage + ambient variation
- **Uptime**: Simulated system uptime counter

## Technical Highlights

- ✅ **Zero Dependencies**: No external libraries needed beyond Serv
- ✅ **Proper SSE Format**: Correct event-stream formatting with id/event/data fields
- ✅ **Connection Management**: Queue-based broadcasting to multiple clients
- ✅ **Error Handling**: Graceful degradation and reconnection
- ✅ **Resource Cleanup**: Proper cleanup of connections and background tasks
- ✅ **Performance**: Efficient real-time data streaming
- ✅ **Responsive UI**: Modern design that works on all devices

This demo showcases Serv's excellent SSE capabilities for real-time web applications! 🌟 