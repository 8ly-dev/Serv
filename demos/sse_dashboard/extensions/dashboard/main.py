"""
SSE Dashboard Extension

Provides real-time dashboard with Server-Sent Events for live data streaming.
"""

import asyncio
import json
import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from bevy import dependency

from serv import handle
from serv.extensions import Listener, on
from serv.routes import (
    FileResponse,
    HtmlResponse,
    Route,
    ServerSentEventsResponse,
)

logger = logging.getLogger(__name__)


class DashboardExtension(Listener):
    """Main dashboard extension for managing SSE connections and metrics."""

    def __init__(self):
        self.connections: dict[str, set] = {
            "metrics": set(),
            "alerts": set(),
            "all": set(),
        }
        self.metrics_task = None
        self.alerts_task = None
        self.shutdown_event = None

    @on("app.startup")
    async def start_background_tasks(self):
        """Start background tasks for generating metrics and alerts."""
        logger.info("Starting SSE dashboard background tasks")
        self.shutdown_event = asyncio.Event()
        self.shutdown_event.clear()
        self.metrics_task = asyncio.create_task(self._generate_metrics())
        self.alerts_task = asyncio.create_task(self._generate_alerts())

    @on("app.shutdown")
    async def stop_background_tasks(self):
        """Stop background tasks."""
        logger.info("Stopping SSE dashboard background tasks")
        if self.shutdown_event:
            self.shutdown_event.set()

        # Immediately cancel tasks without waiting
        if self.metrics_task and not self.metrics_task.done():
            self.metrics_task.cancel()

        if self.alerts_task and not self.alerts_task.done():
            self.alerts_task.cancel()

        # Clear all connections immediately
        for stream_type in self.connections:
            connections_copy = self.connections[stream_type].copy()
            self.connections[stream_type].clear()
            for connection in connections_copy:
                try:
                    connection.put_nowait(None)  # Non-blocking sentinel
                except Exception:
                    pass

        # Give tasks a brief moment to cancel, then move on
        if self.metrics_task:
            try:
                await asyncio.wait_for(self.metrics_task, timeout=0.5)
            except (TimeoutError, asyncio.CancelledError):
                pass

        if self.alerts_task:
            try:
                await asyncio.wait_for(self.alerts_task, timeout=0.5)
            except (TimeoutError, asyncio.CancelledError):
                pass

    def add_connection(self, stream_type: str, connection):
        """Add a new SSE connection."""
        self.connections[stream_type].add(connection)
        logger.info(
            f"Added {stream_type} connection. Total: {len(self.connections[stream_type])}"
        )

    def remove_connection(self, stream_type: str, connection):
        """Remove an SSE connection."""
        self.connections[stream_type].discard(connection)
        logger.info(
            f"Removed {stream_type} connection. Total: {len(self.connections[stream_type])}"
        )

    async def broadcast_event(self, stream_type: str, event_data: dict):
        """Broadcast an event to all connections of a specific type."""
        connections_to_remove = set()

        for connection in self.connections[stream_type].copy():
            try:
                formatted_event = self._format_sse_event(event_data)
                await connection.put(formatted_event)
            except Exception as e:
                logger.warning(f"Failed to send to connection: {e}")
                connections_to_remove.add(connection)

        # Remove failed connections
        for connection in connections_to_remove:
            self.connections[stream_type].discard(connection)

    def _format_sse_event(self, data: dict) -> str:
        """Format data as SSE event."""
        event_lines = []

        if "id" in data:
            event_lines.append(f"id: {data['id']}")

        if "event" in data:
            event_lines.append(f"event: {data['event']}")

        if "data" in data:
            if isinstance(data["data"], dict | list):
                json_data = json.dumps(data["data"])
                event_lines.append(f"data: {json_data}")
            else:
                event_lines.append(f"data: {data['data']}")

        # Use CRLF line endings and double newline to end event
        return "\r\n".join(event_lines) + "\r\n\r\n"

    async def _generate_metrics(self):
        """Generate simulated system metrics."""
        cpu_history = []
        memory_base = 60.0
        network_base = 100.0

        while True:
            try:
                # Check for shutdown more frequently
                if self.shutdown_event and self.shutdown_event.is_set():
                    break

                timestamp = datetime.now().isoformat()

                # Generate CPU usage with realistic fluctuations
                cpu_usage = max(0, min(100, random.normalvariate(45, 15)))
                cpu_history.append(cpu_usage)
                if len(cpu_history) > 60:  # Keep last 60 readings
                    cpu_history.pop(0)

                # Generate memory usage with gradual changes
                memory_base += random.normalvariate(0, 2)
                memory_base = max(30, min(90, memory_base))
                memory_usage = memory_base + random.normalvariate(0, 5)
                memory_usage = max(0, min(100, memory_usage))

                # Generate network traffic with bursts
                network_base += random.normalvariate(0, 20)
                network_base = max(0, min(1000, network_base))
                network_in = network_base + random.normalvariate(0, 50)
                network_out = network_base * 0.3 + random.normalvariate(0, 20)

                # Generate disk usage (slowly changing)
                disk_usage = 67.5 + random.normalvariate(0, 1)

                # Generate temperature
                temp = 42 + cpu_usage * 0.3 + random.normalvariate(0, 3)

                # Check for shutdown before broadcasting
                if self.shutdown_event and self.shutdown_event.is_set():
                    break

                metrics_data = {
                    "id": str(int(time.time() * 1000)),
                    "event": "metrics",
                    "data": {
                        "timestamp": timestamp,
                        "cpu": {
                            "usage": round(cpu_usage, 1),
                            "history": [round(x, 1) for x in cpu_history[-20:]],
                        },
                        "memory": {
                            "usage": round(memory_usage, 1),
                            "total": 16384,
                            "used": round(memory_usage * 163.84, 0),
                        },
                        "network": {
                            "in": round(max(0, network_in), 1),
                            "out": round(max(0, network_out), 1),
                        },
                        "disk": {
                            "usage": round(disk_usage, 1),
                            "total": 512,
                            "free": round(512 * (100 - disk_usage) / 100, 1),
                        },
                        "temperature": round(temp, 1),
                        "uptime": int(time.time()) % 86400,  # Simulated uptime
                        "connections": sum(
                            len(conns) for conns in self.connections.values()
                        ),
                    },
                }

                # Broadcast to metrics and all streams
                try:
                    await self.broadcast_event("metrics", metrics_data)
                    await self.broadcast_event("all", metrics_data)
                except Exception:
                    # If broadcasting fails during shutdown, just exit
                    break

                # Sleep with more frequent cancellation checks
                for _ in range(20):  # Check 20 times over 2 seconds
                    if self.shutdown_event and self.shutdown_event.is_set():
                        return
                    await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error generating metrics: {e}")
                # During shutdown, don't retry
                if self.shutdown_event and self.shutdown_event.is_set():
                    break
                await asyncio.sleep(1)

    async def _generate_alerts(self):
        """Generate simulated system alerts."""
        alert_messages = [
            "System backup completed successfully",
            "High CPU usage detected",
            "Memory usage approaching limit",
            "Network connection restored",
            "Disk cleanup completed",
            "Security scan finished",
            "Service restarted automatically",
            "Performance optimization applied",
            "Cache cleared successfully",
            "System update available",
        ]

        alert_levels = ["info", "warning", "error", "success"]

        while True:
            try:
                # Generate alerts at random intervals (30-120 seconds)
                await asyncio.sleep(random.randint(30, 120))

                timestamp = datetime.now().isoformat()
                message = random.choice(alert_messages)
                level = random.choice(alert_levels)

                # Adjust level based on message content
                if "error" in message.lower() or "failed" in message.lower():
                    level = "error"
                elif "warning" in message.lower() or "high" in message.lower():
                    level = "warning"
                elif "completed" in message.lower() or "success" in message.lower():
                    level = "success"

                alert_data = {
                    "id": str(int(time.time() * 1000)),
                    "event": "alert",
                    "data": {
                        "timestamp": timestamp,
                        "level": level,
                        "message": message,
                        "source": "system",
                    },
                }

                # Broadcast to alerts and all streams
                await self.broadcast_event("alerts", alert_data)
                await self.broadcast_event("all", alert_data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error generating alerts: {e}")
                await asyncio.sleep(10)


class DashboardHomeRoute(Route):
    """Home route serving the dashboard interface."""

    @handle.GET
    async def show_dashboard(self) -> Annotated[str, HtmlResponse]:
        """Serve the main dashboard page."""
        dashboard_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSE Dashboard Demo</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 Real-time SSE Dashboard</h1>
            <div class="connection-status" id="connectionStatus">
                <span class="status-dot connecting"></span>
                <span class="status-text">Connecting...</span>
            </div>
        </header>

        <div class="metrics-grid">
            <div class="metric-card">
                <h3>CPU Usage</h3>
                <div class="gauge" id="cpuGauge">
                    <div class="gauge-value" id="cpuValue">0%</div>
                </div>
                <canvas id="cpuChart" width="200" height="100"></canvas>
            </div>

            <div class="metric-card">
                <h3>Memory Usage</h3>
                <div class="progress-bar">
                    <div class="progress-fill" id="memoryProgress"></div>
                    <div class="progress-text" id="memoryText">0% (0 MB)</div>
                </div>
                <div class="metric-details" id="memoryDetails">Total: 16,384 MB</div>
            </div>

            <div class="metric-card">
                <h3>Network Activity</h3>
                <div class="network-stats">
                    <div class="stat">
                        <span class="label">↓ In:</span>
                        <span class="value" id="networkIn">0 KB/s</span>
                    </div>
                    <div class="stat">
                        <span class="label">↑ Out:</span>
                        <span class="value" id="networkOut">0 KB/s</span>
                    </div>
                </div>
                <canvas id="networkChart" width="200" height="100"></canvas>
            </div>

            <div class="metric-card">
                <h3>Disk Usage</h3>
                <div class="disk-info">
                    <div class="disk-percentage" id="diskPercentage">0%</div>
                    <div class="disk-details" id="diskDetails">0 GB free of 512 GB</div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" id="diskProgress"></div>
                </div>
            </div>

            <div class="metric-card">
                <h3>System Status</h3>
                <div class="system-stats">
                    <div class="stat">
                        <span class="label">Temperature:</span>
                        <span class="value" id="temperature">0°C</span>
                    </div>
                    <div class="stat">
                        <span class="label">Uptime:</span>
                        <span class="value" id="uptime">0s</span>
                    </div>
                    <div class="stat">
                        <span class="label">Connections:</span>
                        <span class="value" id="connections">0</span>
                    </div>
                </div>
            </div>

            <div class="metric-card alerts-card">
                <h3>System Alerts</h3>
                <div class="alerts-container" id="alertsContainer">
                    <div class="alert-item info">
                        <span class="alert-time">Loading...</span>
                        <span class="alert-message">Connecting to event stream...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="/static/dashboard.js"></script>
</body>
</html>"""
        return dashboard_html


class MetricsSSERoute(Route):
    """SSE route for metrics data stream."""

    @handle.GET
    async def stream_metrics(
        self,
        dashboard: DashboardExtension = dependency(),
    ) -> Annotated[Any, ServerSentEventsResponse]:
        """Stream real-time metrics via SSE."""

        async def metrics_generator():
            # Create a queue for this connection
            queue = asyncio.Queue()
            dashboard.add_connection("metrics", queue)

            try:
                # Send initial connection event
                initial_event = dashboard._format_sse_event(
                    {
                        "event": "connected",
                        "data": {
                            "type": "metrics",
                            "message": "Connected to metrics stream",
                        },
                    }
                )
                yield initial_event

                # Simple loop that exits fast
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=0.5)
                        if event is None:  # Shutdown sentinel
                            return
                        yield event
                    except TimeoutError:
                        # Just send heartbeat and continue
                        yield dashboard._format_sse_event(
                            {
                                "event": "heartbeat",
                                "data": {"timestamp": datetime.now().isoformat()},
                            }
                        )
                    except Exception:
                        # Exit on any other exception
                        return

            except Exception:
                # Exit on any exception
                return
            finally:
                dashboard.remove_connection("metrics", queue)

        return metrics_generator()


class AlertsSSERoute(Route):
    """SSE route for alerts data stream."""

    @handle.GET
    async def stream_alerts(
        self, dashboard: DashboardExtension = dependency()
    ) -> Annotated[Any, ServerSentEventsResponse]:
        """Stream real-time alerts via SSE."""

        async def alerts_generator():
            # Create a queue for this connection
            queue = asyncio.Queue()
            dashboard.add_connection("alerts", queue)

            try:
                # Send initial connection event
                initial_event = dashboard._format_sse_event(
                    {
                        "event": "connected",
                        "data": {
                            "type": "alerts",
                            "message": "Connected to alerts stream",
                        },
                    }
                )
                yield initial_event

                # Stream events from the queue
                while not (
                    dashboard.shutdown_event and dashboard.shutdown_event.is_set()
                ):
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=5.0)
                        # Check for shutdown sentinel
                        if event is None:
                            break
                        yield event
                    except TimeoutError:
                        # Send heartbeat
                        if not (
                            dashboard.shutdown_event
                            and dashboard.shutdown_event.is_set()
                        ):
                            heartbeat = dashboard._format_sse_event(
                                {
                                    "event": "heartbeat",
                                    "data": {"timestamp": datetime.now().isoformat()},
                                }
                            )
                            yield heartbeat

            except asyncio.CancelledError:
                pass
            finally:
                dashboard.remove_connection("alerts", queue)

        return alerts_generator()


class AllEventsSSERoute(Route):
    """SSE route for combined events stream."""

    @handle.GET
    async def stream_all_events(
        self, dashboard: DashboardExtension = dependency()
    ) -> Annotated[Any, ServerSentEventsResponse]:
        """Stream all real-time events via SSE."""

        async def all_events_generator():
            # Create a queue for this connection
            queue = asyncio.Queue()
            dashboard.add_connection("all", queue)

            try:
                # Send initial connection event
                initial_event = dashboard._format_sse_event(
                    {
                        "event": "connected",
                        "data": {
                            "type": "all",
                            "message": "Connected to all events stream",
                        },
                    }
                )
                yield initial_event

                # Simple loop that exits fast
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=0.5)
                        if event is None:  # Shutdown sentinel
                            return
                        yield event
                    except TimeoutError:
                        # Just send heartbeat and continue
                        yield dashboard._format_sse_event(
                            {
                                "event": "heartbeat",
                                "data": {"timestamp": datetime.now().isoformat()},
                            }
                        )
                    except Exception:
                        # Exit on any other exception
                        return

            except Exception:
                # Exit on any exception
                return
            finally:
                dashboard.remove_connection("all", queue)

        return all_events_generator()


class StaticFileRoute(Route):
    """Route for serving static files."""

    @handle.GET
    async def serve_static(self, filename: str) -> FileResponse:
        """Serve static files (CSS, JS, etc.)."""
        # Get filename from path parameters
        if not filename:
            raise FileNotFoundError("Filename not provided")

        static_dir = Path(__file__).parent.parent.parent / "static"
        file_path = static_dir / filename

        # Security: ensure the file is within the static directory
        try:
            file_path = file_path.resolve()
            static_dir = static_dir.resolve()

            if not file_path.is_relative_to(static_dir):
                raise FileNotFoundError("File not found")

            if not file_path.exists():
                raise FileNotFoundError("File not found")

            # Read the file content
            with open(file_path, "rb") as f:
                file_content = f.read()

            # Determine content type based on file extension
            import mimetypes

            content_type, _ = mimetypes.guess_type(str(file_path))
            if content_type is None:
                content_type = "application/octet-stream"

            return FileResponse(
                file=file_content, filename=file_path.name, content_type=content_type
            )

        except Exception as e:
            logger.error(f"Error serving static file {filename}: {e}")
            raise FileNotFoundError(f"File not found: {file_path}") from e
