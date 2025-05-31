#!/usr/bin/env python3
"""Simple WebSocket test script for the demo."""

import asyncio
import sys

try:
    import websockets
except ImportError:
    print("❌ websockets module not found. Install with: pip install websockets")
    sys.exit(1)

async def test_websocket():
    """Test the WebSocket echo functionality."""
    try:
        uri = 'ws://127.0.0.1:8000/ws'
        print(f"🔗 Connecting to {uri}...")
        
        async with websockets.connect(uri) as websocket:
            print("✅ Connected successfully!")
            
            # Send test messages
            test_messages = ['Hello WebSocket!', 'Testing 123', '🚀 Serv rocks!']
            
            for message in test_messages:
                print(f"📤 Sending: {message}")
                await websocket.send(message)
                
                response = await websocket.recv()
                print(f"📥 Received: {response}")
                
                # Verify it's an echo
                if message in response:
                    print("✅ Echo working correctly!")
                else:
                    print("❌ Echo not working as expected")
                print()
            
        print("🎉 WebSocket test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_websocket())
    sys.exit(0 if result else 1) 