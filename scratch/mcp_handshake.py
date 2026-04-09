
import httpx
import json
import asyncio

async def handshake():
    url = "http://127.0.0.1:8000/health"
    print(f"Connecting to {url}...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                print("Handshake successful! Server is healthy.")
                print(json.dumps(response.json(), indent=2))
                
                # Try to list tools if possible via API
                # Note: SSE initialization is more complex, but let's check tools via health if provided
                # the health endpoint we saw earlier:
                # {"status":"healthy","service":"mcp-unified","version":"1.0.0","transport":"SSE","host":"127.0.0.1","port":8000,"tools_available":80}
            else:
                print(f"Handshake failed with status code: {response.status_code}")
    except Exception as e:
        print(f"Handshake failed: {e}")

if __name__ == "__main__":
    asyncio.run(handshake())
