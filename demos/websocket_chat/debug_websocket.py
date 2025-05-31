#!/usr/bin/env python3

import asyncio
import websockets
import sys

async def debug_websocket():
    uri = "ws://127.0.0.1:8000/ws"
    print(f"Connecting to {uri}...")
    
    try:
        websocket = await websockets.connect(uri)
        print("✅ WebSocket connection established!")
        
        # Send a test message
        test_message = "Hello, WebSocket!"
        print(f"📤 Sending: {test_message}")
        await websocket.send(test_message)
        print("✅ Message sent successfully")
        
        # Try to receive with a longer timeout
        print("⏳ Waiting for response...")
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            print(f"📥 Received: {response}")
            
            if "Echo:" in response and test_message in response:
                print("✅ Echo functionality working correctly!")
                return True
            else:
                print("❌ Echo response not as expected")
                return False
                
        except asyncio.TimeoutError:
            print("❌ Timeout waiting for echo response")
            print("🔍 Checking connection state...")
            print(f"WebSocket state: {websocket.state}")
            return False
        
        finally:
            await websocket.close()
            print("🔌 WebSocket connection closed")
                
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Debugging WebSocket echo functionality...")
    success = asyncio.run(debug_websocket())
    sys.exit(0 if success else 1) 