# Real-time Chat Application Demo (MVP)

A simple real-time chat application built with Serv showcasing WebSocket support and basic real-time messaging.

## Features

- Real-time messaging with WebSockets
- Simple chat room interface
- In-memory message storage
- Basic user identification
- Live user list

## MVP TODO List

### Core WebSocket Setup
- [ ] Create WebSocket route handler in Serv
- [ ] Implement WebSocket connection management
- [ ] Add basic message broadcasting to all connected clients
- [ ] Create connection storage (simple in-memory dict)
- [ ] Handle WebSocket disconnections gracefully

### Basic Chat Features
- [ ] Create simple HTML chat interface
- [ ] Add JavaScript WebSocket client code
- [ ] Implement message sending from frontend
- [ ] Display incoming messages in real-time
- [ ] Add basic username assignment (session-based)
- [ ] Show online user count

### Message Handling
- [ ] Create simple message format (JSON with username, message, timestamp)
- [ ] Add message broadcasting to all connected users
- [ ] Store last 50 messages in memory for new users
- [ ] Add basic input validation (non-empty messages)
- [ ] Handle special commands (like /name to change username)

### Frontend Interface
- [ ] Create single HTML page with chat interface
- [ ] Add CSS for basic styling
- [ ] Implement message input form
- [ ] Create message display area with auto-scroll
- [ ] Add user list sidebar
- [ ] Show connection status indicator

### Extensions Integration
- [ ] Create ChatExtension for route registration
- [ ] Add WebSocket middleware for connection handling
- [ ] Create simple logging for chat events

## Running the Demo

```bash
cd demos/realtime_chat
pip install -r requirements.txt  # Only needs uvicorn
serv launch
```

Visit http://localhost:8000 to start chatting!

## File Structure

```
demos/realtime_chat/
├── README.md
├── requirements.txt              # uvicorn only
├── serv.config.yaml             # Basic config
├── extensions/
│   └── chat_extension.py        # Chat routes and WebSocket handling
├── templates/
│   └── chat.html               # Single-page chat interface
└── static/
    ├── chat.js                 # WebSocket client code
    └── style.css               # Basic styling
```

## MVP Scope

- **In-memory storage only** (no database)
- **Single chat room** (no multiple rooms)
- **Basic usernames** (no authentication)
- **Simple HTML/CSS/JS** (no fancy UI frameworks)
- **Local development only** (no production concerns)

## Demo Flow

1. User visits the page and gets assigned a random username
2. User can change username with `/name NewName` command
3. User can send messages that appear for all connected users
4. User can see who else is online
5. Messages are lost when server restarts (in-memory only)

This MVP demonstrates Serv's WebSocket capabilities with minimal setup! 