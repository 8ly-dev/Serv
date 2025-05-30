# Server-Sent Events Dashboard Demo (MVP)

A simple real-time dashboard built with Serv showcasing Server-Sent Events for live data streaming and dynamic updates.

## Features

- Real-time metrics streaming via SSE
- Live charts and gauges
- Simulated system data
- Multiple data streams
- Auto-refreshing dashboard
- Connection status indicator

## MVP TODO List

### SSE Core Implementation
- [ ] Create SSE endpoint with proper headers
- [ ] Implement event formatting (data, event, id fields)
- [ ] Add client connection management
- [ ] Handle client disconnections gracefully
- [ ] Create event broadcasting system

### Simulated Metrics
- [ ] Generate fake CPU usage data
- [ ] Create memory usage simulation
- [ ] Add network traffic simulation
- [ ] Generate random system events
- [ ] Create temperature and load metrics

### Dashboard Frontend
- [ ] Create responsive HTML dashboard layout
- [ ] Implement JavaScript SSE client
- [ ] Add real-time chart rendering (using Chart.js or simple canvas)
- [ ] Create metric cards and gauges
- [ ] Add connection status indicator
- [ ] Implement auto-reconnection logic

### Data Streaming
- [ ] Create periodic data generation (asyncio tasks)
- [ ] Implement different event types (metrics, alerts, status)
- [ ] Add data formatting for frontend consumption
- [ ] Create event filtering and routing
- [ ] Handle multiple concurrent connections

### Visual Components
- [ ] CPU usage gauge/chart
- [ ] Memory usage progress bar
- [ ] Network activity graph
- [ ] System alerts feed
- [ ] Uptime counter
- [ ] Active connections counter

### Extensions Integration
- [ ] Create DashboardExtension
- [ ] Add SSE middleware for connection handling
- [ ] Create metrics generation extension

## Running the Demo

```bash
cd demos/sse_dashboard
pip install -r requirements.txt  # No extra dependencies needed
serv launch
```

Visit http://localhost:8000 to view the real-time dashboard!

## File Structure

```
demos/sse_dashboard/
├── README.md
├── requirements.txt              # No extra deps needed
├── serv.config.yaml             # Basic config
├── extensions/
│   └── dashboard_extension.py   # SSE routes and metrics
├── templates/
│   └── dashboard.html          # Dashboard interface
└── static/
    ├── dashboard.js            # SSE client and charts
    ├── style.css               # Dashboard styling
    └── chart.js                # Simple charting library (or CDN)
```

## MVP Scope

- **Simulated data only** (no real system metrics)
- **In-memory state** (no persistent storage)
- **Single dashboard view** (no customization)
- **Basic charts** (simple canvas or Chart.js via CDN)
- **No authentication** (public dashboard)

## SSE Endpoints

- `GET /api/events/metrics` - System metrics stream
- `GET /api/events/alerts` - Alert notifications stream
- `GET /api/events/all` - Combined event stream

## Event Types

### Metrics Event
```json
{
  "type": "metric",
  "name": "cpu_usage",
  "value": 45.2,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Alert Event
```json
{
  "type": "alert",
  "level": "warning",
  "message": "High CPU usage detected",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Dashboard Features

- **Real-time Metrics**: CPU, Memory, Network, Disk usage
- **Live Charts**: Line charts showing metric history
- **System Alerts**: Warning and error notifications
- **Connection Status**: Shows SSE connection health
- **Auto-reconnect**: Handles connection drops gracefully

## Demo Data

The dashboard generates realistic but simulated data:
- CPU usage: 0-100% with realistic fluctuations
- Memory usage: Gradual changes with occasional spikes
- Network traffic: Random bursts of activity
- System alerts: Periodic warnings and status messages

This MVP demonstrates Serv's SSE capabilities for real-time data visualization! 