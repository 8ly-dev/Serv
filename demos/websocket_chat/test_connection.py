#!/usr/bin/env python3

import asyncio
import sys

import websockets


async def test_websocket():
    uri = "ws://127.0.0.1:8000/ws"
    print(f"Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connection established!")

            # Send a test message
            test_message = "Hello, WebSocket!"
            print(f"📤 Sending: {test_message}")
            await websocket.send(test_message)

            # Wait for echo response with timeout
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 Received: {response}")

                if "Echo:" in response and test_message in response:
                    print("✅ Echo functionality working correctly!")
                    return True
                else:
                    print("❌ Echo response not as expected")
                    return False

            except TimeoutError:
                print("❌ Timeout waiting for echo response")
                return False

    except websockets.exceptions.ConnectionClosedError as e:
        print(f"❌ WebSocket connection closed unexpectedly: {e}")
        return False
    except websockets.exceptions.ConnectionClosedOK:
        print("❌ WebSocket connection closed normally (but prematurely)")
        return False
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Testing WebSocket echo functionality...")
    success = asyncio.run(test_websocket())
    sys.exit(0 if success else 1)
