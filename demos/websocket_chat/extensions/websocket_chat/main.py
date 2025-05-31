"""WebSocket Echo Chat Extension

A demo extension showcasing WebSocket functionality with an echo chat interface.
"""

from typing import Annotated
from bevy import dependency

from serv import WebSocket, handle
from serv.routes import Route, GetRequest, HtmlResponse


class ChatPageRoute(Route):
    """Serve the chat page."""
    
    @handle.GET
    async def handle_get(self, request: GetRequest) -> Annotated[str, HtmlResponse]:
        """Return the chat interface HTML."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebSocket Echo Chat Demo</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .chat-container {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
        }
        .status {
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            font-weight: bold;
        }
        .status.connected {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .status.disconnected {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .status.connecting {
            background-color: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }
        #messages {
            height: 400px;
            border: 1px solid #ddd;
            padding: 15px;
            overflow-y: auto;
            background-color: #fafafa;
            border-radius: 5px;
            margin-bottom: 20px;
            font-family: monospace;
        }
        .message {
            margin-bottom: 10px;
            padding: 8px;
            border-radius: 5px;
        }
        .message.sent {
            background-color: #007bff;
            color: white;
            text-align: right;
        }
        .message.received {
            background-color: #e9ecef;
            color: #333;
        }
        .message.system {
            background-color: #ffc107;
            color: #212529;
            text-align: center;
            font-style: italic;
        }
        .input-container {
            display: flex;
            gap: 10px;
        }
        #messageInput {
            flex: 1;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        #sendButton {
            padding: 12px 24px;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        #sendButton:hover {
            background-color: #0056b3;
        }
        #sendButton:disabled {
            background-color: #6c757d;
            cursor: not-allowed;
        }
        .info {
            background-color: #e7f3ff;
            border: 1px solid #b8daff;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .info h3 {
            margin-top: 0;
            color: #004085;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <h1>🚀 WebSocket Echo Chat Demo</h1>
        
        <div class="info">
            <h3>About This Demo</h3>
            <p>This demo showcases the WebSocket functionality implemented in the Serv framework. Type a message and send it - the server will echo it back to you immediately!</p>
            <p><strong>Features demonstrated:</strong></p>
            <ul>
                <li>Real-time WebSocket communication</li>
                <li>Async message handling with <code>async for message in websocket</code></li>
                <li>Connection state management</li>
                <li>Error handling and reconnection</li>
            </ul>
        </div>
        
        <div id="status" class="status connecting">Connecting to WebSocket...</div>
        
        <div id="messages"></div>
        
        <div class="input-container">
            <input type="text" id="messageInput" placeholder="Type your message here..." disabled>
            <button id="sendButton" disabled>Send</button>
        </div>
    </div>

    <script>
        let ws = null;
        let reconnectTimeout = null;
        const maxReconnectDelay = 30000; // 30 seconds
        let reconnectDelay = 1000; // Start with 1 second

        const statusEl = document.getElementById('status');
        const messagesEl = document.getElementById('messages');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');

        function updateStatus(status, message) {
            statusEl.className = `status ${status}`;
            statusEl.textContent = message;
            
            const isConnected = status === 'connected';
            messageInput.disabled = !isConnected;
            sendButton.disabled = !isConnected;
            
            if (isConnected) {
                messageInput.focus();
            }
        }

        function addMessage(content, type = 'received') {
            const div = document.createElement('div');
            div.className = `message ${type}`;
            
            const timestamp = new Date().toLocaleTimeString();
            
            if (type === 'system') {
                div.textContent = `[${timestamp}] ${content}`;
            } else if (type === 'sent') {
                div.textContent = `[${timestamp}] You: ${content}`;
            } else {
                div.textContent = `[${timestamp}] Echo: ${content}`;
            }
            
            messagesEl.appendChild(div);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        function connect() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${location.host}/ws`);
            
            ws.onopen = () => {
                updateStatus('connected', 'Connected to WebSocket server');
                addMessage('Connected to echo chat server', 'system');
                
                // Reset reconnect delay on successful connection
                reconnectDelay = 1000;
                
                // Clear any pending reconnect
                if (reconnectTimeout) {
                    clearTimeout(reconnectTimeout);
                    reconnectTimeout = null;
                }
            };
            
            ws.onmessage = (event) => {
                console.log('Received message:', event.data);
                addMessage(event.data, 'received');
            };
            
            ws.onclose = (event) => {
                console.log('WebSocket closed:', event.code, event.reason);
                updateStatus('disconnected', `Disconnected (Code: ${event.code})`);
                addMessage(`Connection closed (${event.code}): ${event.reason || 'No reason provided'}`, 'system');
                
                // Attempt to reconnect
                scheduleReconnect();
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                updateStatus('disconnected', 'Connection error occurred');
                addMessage('Connection error occurred', 'system');
            };
        }

        function scheduleReconnect() {
            if (reconnectTimeout) return; // Already scheduled
            
            addMessage(`Attempting to reconnect in ${reconnectDelay / 1000} seconds...`, 'system');
            
            reconnectTimeout = setTimeout(() => {
                reconnectTimeout = null;
                connect();
                
                // Exponential backoff, but cap at maxReconnectDelay
                reconnectDelay = Math.min(reconnectDelay * 2, maxReconnectDelay);
            }, reconnectDelay);
        }

        function sendMessage() {
            const message = messageInput.value.trim();
            if (!message || !ws || ws.readyState !== WebSocket.OPEN) return;
            
            console.log('Sending message:', message);
            ws.send(message);
            addMessage(message, 'sent');
            messageInput.value = '';
        }

        // Event listeners
        sendButton.addEventListener('click', sendMessage);
        
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // Start the connection
        connect();
    </script>
</body>
</html>"""


async def echo_websocket_handler(websocket: WebSocket = dependency()) -> None:
    """WebSocket echo handler - demonstrates the basic async iteration pattern."""
    print(f"WebSocket connection established from {websocket.client}")
    
    try:
        # Accept the connection
        await websocket.accept()
        print("WebSocket connection accepted")
        
        # Echo messages back using async iteration
        print("Starting message iteration...")
        message_count = 0
        async for message in websocket:
            message_count += 1
            print(f"Received message {message_count}: {message}")
            echo_response = f"Echo: {message}"
            await websocket.send(echo_response)
            print(f"Sent echo response: {echo_response}")
            
    except Exception as e:
        print(f"WebSocket error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"WebSocket connection closed (processed {message_count if 'message_count' in locals() else 0} messages)")
