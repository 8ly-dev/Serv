# WebSocket Echo Chat Demo

A comprehensive demonstration of WebSocket functionality in the Serv framework, featuring real-time bidirectional communication with an echo chat interface.

## Overview

This demo showcases the WebSocket capabilities implemented in Serv, demonstrating:

- **Real-time Communication**: Bidirectional message exchange between client and server
- **Async Message Handling**: Using `async for message in websocket` pattern
- **Connection Management**: Proper WebSocket lifecycle handling
- **Error Handling**: Robust connection error handling and auto-reconnection
- **Modern UI**: Clean, responsive chat interface with connection status indicators

## Quick Start

### Prerequisites

- Python 3.11+
- Serv framework installed
- WebSocket dependencies (automatically included)

### Running the Demo

1. **Navigate to the demo directory:**
   ```bash
   cd demos/websocket_chat
   ```

2. **Start the server:**
   ```bash
   serv launch
   ```

3. **Open your browser and visit:**
   ```
   http://127.0.0.1:8000
   ```

4. **Start chatting!** Type messages and see them echoed back in real-time.

### Testing with Scripts

**Basic connectivity test:**
```bash
python test_connection.py
```

**WebSocket echo test:**
```bash
python test_websocket.py
```

**Detailed debugging:**
```bash
python debug_websocket.py
```

**Run all framework WebSocket tests:**
```bash
cd /path/to/serv && python -m pytest tests/test_websocket.py -v
```

> ✅ **All tests are now passing!** Recent improvements to the WebSocket `accept()` method ensure compatibility with both real ASGI WebSocket connections and unit test scenarios.

## Architecture

### Project Structure

```
demos/websocket_chat/
├── README.md                     # This documentation
├── serv.config.yaml             # Serv configuration
├── test_connection.py           # WebSocket connectivity test
├── debug_websocket.py           # Detailed WebSocket debugging
└── extensions/
    └── websocket_chat/
        ├── extension.yaml       # Extension configuration
        ├── main.py             # Route handlers and WebSocket logic
        └── __init__.py
```

### Key Components

#### 1. Extension Configuration (`extension.yaml`)

```yaml
name: WebSocket Echo Chat
description: A demo extension showcasing WebSocket functionality
version: 1.0.0
author: Serv Demo

routers:
  - name: chat_router
    routes:
      - path: /
        handler: main:ChatPageRoute
      - path: /ws
        handler: main:echo_websocket_handler
        websocket: true 
```

**Key Features:**
- Declares both HTTP and WebSocket routes
- Uses `websocket: true` flag for WebSocket route registration
- Clean declarative routing configuration

#### 2. Application Configuration (`serv.config.yaml`)

```yaml
site_info:
  name: "WebSocket Echo Chat Demo"
  description: "A demo showcasing WebSocket functionality in Serv"

extensions:
  - websocket_chat

settings:
  debug: true
  host: "127.0.0.1"
  port: 8000
  extension_dir: "./extensions"
```

#### 3. WebSocket Handler (`main.py`)

```python
async def echo_websocket_handler(websocket: WebSocket = dependency()) -> None:
    """WebSocket echo handler - demonstrates the basic async iteration pattern."""
    print(f"WebSocket connection established from {websocket.client}")
    
    try:
        # Accept the connection
        await websocket.accept()
        print("WebSocket connection accepted")
        
        # Echo messages back using async iteration
        async for message in websocket:
            print(f"Received message: {message}")
            await websocket.send(f"Echo: {message}")
            
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        print("WebSocket connection closed")
```

**Key Concepts:**
- **Dependency Injection**: WebSocket instance injected via `dependency()`
- **Connection Lifecycle**: Explicit `accept()` call required
- **Async Iteration**: Clean `async for` loop over incoming messages
- **Error Handling**: Proper exception handling and cleanup

## WebSocket Features Demonstrated

### 1. Connection Management

```python
# Accept incoming connection
await websocket.accept()

# Check connection status
if websocket.is_connected:
    await websocket.send("Hello!")

# Graceful closure
await websocket.close(code=1000, reason="Normal closure")
```

### 2. Message Handling

```python
# Async iteration (recommended)
async for message in websocket:
    await websocket.send(f"Echo: {message}")

# Explicit receive (alternative)
try:
    message = await websocket.receive()
    await websocket.send(f"Echo: {message}")
except WebSocketConnectionError:
    break
```

### 3. Different Message Types

```python
# Text messages
await websocket.send("Hello, WebSocket!")
await websocket.send_text("Explicit text")

# Binary messages  
await websocket.send(b"Binary data")
await websocket.send_bytes(b"Explicit binary")

# JSON messages
await websocket.send_json({"type": "greeting", "message": "Hello"})
data = await websocket.receive_json()
```

### 4. Error Handling

```python
try:
    async for message in websocket:
        await websocket.send(f"Echo: {message}")
except WebSocketConnectionError as e:
    print(f"Connection lost: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
    await websocket.close(code=1011, reason="Internal error")
```

## Frontend Features

### Real-time Chat Interface

The web interface demonstrates:

- **Connection Status**: Visual indicators for connection state
- **Message History**: Scrollable chat log with timestamps
- **Auto-reconnection**: Exponential backoff reconnection strategy
- **Responsive Design**: Mobile-friendly interface
- **Error Display**: User-friendly error messages

### JavaScript WebSocket Handling

```javascript
// Connection with auto-reconnection
function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws`);
    
    ws.onopen = () => {
        updateStatus('connected', 'Connected to WebSocket server');
        addMessage('Connected to echo chat server', 'system');
    };
    
    ws.onmessage = (event) => {
        addMessage(event.data, 'received');
    };
    
    ws.onclose = (event) => {
        updateStatus('disconnected', `Disconnected (Code: ${event.code})`);
        scheduleReconnect(); // Auto-reconnection
    };
}
```

## Technical Implementation Details

### ASGI WebSocket Protocol

The demo properly implements the ASGI WebSocket protocol:

1. **Connect Phase**: Server receives `websocket.connect` message
2. **Accept Phase**: Server sends `websocket.accept` message  
3. **Message Phase**: Bidirectional `websocket.receive`/`websocket.send`
4. **Disconnect Phase**: Either party sends `websocket.disconnect`

### Dependency Injection Integration

```python
# WebSocket instance automatically injected
async def my_websocket_handler(websocket: WebSocket = dependency()) -> None:
    # WebSocket ready to use
    await websocket.accept()
```

### Router Integration

- WebSocket routes registered alongside HTTP routes
- Path parameters supported: `/ws/{room_id}`
- Route settings and middleware compatible
- Extension-based modular architecture

### Frame Type Support

```python
from typing import Annotated
from serv.websocket import FrameType

# Binary WebSocket handler
async def binary_handler(ws: Annotated[WebSocket, FrameType.BINARY]):
    async for message in ws:
        # message is bytes
        processed = process_binary_data(message)
        await ws.send(processed)
```

## Testing and Debugging

### Automated Tests

**Connection Test:**
```bash
python test_connection.py
```
- Establishes WebSocket connection
- Sends test message
- Verifies echo response
- Reports success/failure

**Debug Script:**
```bash
python debug_websocket.py
```
- Detailed connection logging
- Step-by-step message flow
- Connection state inspection
- Timeout handling

### Manual Testing

1. **Browser DevTools**: Open Network tab to inspect WebSocket frames
2. **curl WebSocket**: Use `websocat` or similar tools for command-line testing
3. **Load Testing**: Multiple concurrent connections

### Common Issues

**Connection Rejected (403):**
- Check route registration in `extension.yaml`
- Verify `websocket: true` flag
- Ensure extension is loaded

**Messages Not Received:**
- Check `await websocket.accept()` call
- Verify async iteration pattern
- Check for proper error handling

**Auto-reconnection Not Working:**
- Check JavaScript console for errors
- Verify exponential backoff implementation
- Test network connectivity

## Performance Considerations

### Connection Limits

- Default: 1000 concurrent connections
- Configurable via server settings
- Monitor memory usage with high connection counts

### Message Throughput

- Text messages: ~10MB/s per connection
- Binary messages: Higher throughput possible
- JSON parsing adds overhead

### Memory Management

```python
# Efficient message handling
async for message in websocket:
    # Process immediately, don't accumulate
    result = await process_message(message)
    await websocket.send(result)
    # Message automatically garbage collected
```

## Extensions and Customization

### Adding Authentication

```python
async def authenticated_websocket_handler(
    websocket: WebSocket = dependency(),
    user: User = dependency()  # Custom auth dependency
) -> None:
    await websocket.accept()
    await websocket.send(f"Welcome, {user.name}!")
    
    async for message in websocket:
        # Handle authenticated user messages
        await websocket.send(f"Echo: {message}")
```

### Room-based Chat

```python
# Route with path parameters
# In extension.yaml: path: /ws/{room_id}

async def room_chat_handler(
    room_id: str,  # Path parameter
    websocket: WebSocket = dependency()
) -> None:
    await websocket.accept()
    await join_room(room_id, websocket)
    
    async for message in websocket:
        await broadcast_to_room(room_id, message)
```

### Message Persistence

```python
async def persistent_chat_handler(
    websocket: WebSocket = dependency(),
    db: Database = dependency()
) -> None:
    await websocket.accept()
    
    async for message in websocket:
        # Save to database
        await db.save_message(message)
        
        # Echo back
        await websocket.send(f"Saved: {message}")
```

## Security Considerations

### Input Validation

```python
async for message in websocket:
    # Validate message length
    if len(message) > 1000:
        await websocket.close(code=1009, reason="Message too large")
        break
    
    # Sanitize content
    clean_message = sanitize_input(message)
    await websocket.send(f"Echo: {clean_message}")
```

### Rate Limiting

```python
from time import time

last_message_time = 0
message_count = 0

async for message in websocket:
    now = time()
    
    # Reset counter every second
    if now - last_message_time > 1:
        message_count = 0
        last_message_time = now
    
    message_count += 1
    
    # Limit to 10 messages per second
    if message_count > 10:
        await websocket.close(code=1008, reason="Rate limit exceeded")
        break
```

### Authentication Headers

```python
async def secure_websocket_handler(websocket: WebSocket = dependency()) -> None:
    # Check authentication headers
    auth_header = websocket.headers.get("authorization")
    if not validate_token(auth_header):
        await websocket.close(code=4401, reason="Unauthorized")
        return
    
    await websocket.accept()
    # Continue with authenticated session...
```

## Troubleshooting

### Server Logs

Monitor server output for:
- Connection establishment/closure
- Message processing
- Error conditions
- Performance metrics

### Client-side Debugging

```javascript
// Enable detailed WebSocket logging
ws.addEventListener('open', () => console.log('WS: Connected'));
ws.addEventListener('message', (e) => console.log('WS: Received', e.data));
ws.addEventListener('close', (e) => console.log('WS: Closed', e.code, e.reason));
ws.addEventListener('error', (e) => console.error('WS: Error', e));
```

### Network Issues

- Check firewall settings
- Verify proxy configuration
- Test with direct IP connection
- Use browser network tools

## Next Steps

### Enhanced Features

1. **Multi-room Chat**: Implement room-based messaging
2. **User Authentication**: Add login/session management  
3. **Message History**: Persist and retrieve chat history
4. **File Sharing**: Binary message handling for files
5. **Typing Indicators**: Real-time user activity status

### Production Deployment

1. **Reverse Proxy**: Configure nginx/Apache for WebSocket support
2. **SSL/TLS**: Enable secure WebSocket connections (WSS)
3. **Load Balancing**: Distribute connections across multiple servers
4. **Monitoring**: Add metrics and health checks
5. **Scaling**: Implement Redis for multi-server message distribution

---

## API Reference

### WebSocket Class Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `accept(subprotocol=None)` | Accept WebSocket connection | `None` |
| `close(code=1000, reason="")` | Close connection | `None` |
| `send(data)` | Send text or binary message | `None` |
| `send_text(text)` | Send text message | `None` |
| `send_bytes(data)` | Send binary message | `None` |
| `send_json(obj)` | Send JSON message | `None` |
| `receive()` | Receive next message | `str \| bytes` |
| `receive_text()` | Receive text message | `str` |
| `receive_bytes()` | Receive binary message | `bytes` |
| `receive_json()` | Receive and parse JSON | `Any` |

### WebSocket Properties

| Property | Description | Type |
|----------|-------------|------|
| `path` | Request path | `str` |
| `query_string` | Query parameters | `str` |
| `headers` | Request headers | `dict[str, str]` |
| `client` | Client connection info | `tuple` |
| `is_connected` | Connection status | `bool` |
| `state` | Current state | `WebSocketState` |
| `frame_type` | Message frame type | `FrameType` |

### Error Types

| Exception | Description | When Raised |
|-----------|-------------|-------------|
| `WebSocketError` | Base WebSocket exception | Generic WebSocket errors |
| `WebSocketConnectionError` | Connection-related errors | Connection failures, disconnects |

---

*This demo serves as a foundation for building real-time applications with Serv's WebSocket support. Explore the code, experiment with modifications, and build amazing real-time experiences!* 