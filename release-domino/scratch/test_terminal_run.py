import asyncio
import json
import websockets
import urllib.request

async def test_run_demo():
    print("Testing WebSocket terminal run for 'demo'...")
    uri = "ws://127.0.0.1:8000/ws/terminal/demo"
    async with websockets.connect(uri) as ws:
        banner = await ws.recv()
        print("Connected! Banner received:", banner[:80])
        
        await ws.send(json.dumps({
            "cmd": "run",
            "strict_docker": False,
            "keep_alive_sec": 0,
            "allow_network": True,
        }))
        
        live_url = None
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=6.0)
                data = json.loads(msg)
                text = data.get("data", "")
                print(f"[{data.get('stream')}] {text.strip()}")
                if "[LIVE_PREVIEW_URL]" in text or "http://127.0.0.1:505" in text:
                    for word in text.split():
                        if word.startswith("http"):
                            live_url = word.strip()
                            break
                if live_url:
                    break
            except asyncio.TimeoutError:
                print("No message received in 6 seconds.")
                break
        
        if live_url:
            print("Live URL successfully detected:", live_url)
            await asyncio.sleep(1)
            try:
                req = urllib.request.Request(live_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    body = resp.read(500)
                    print(f"HTTP {resp.status} from {live_url}! Body preview:", body[:120])
            except Exception as e:
                print("Failed to fetch live URL:", e)

if __name__ == "__main__":
    asyncio.run(test_run_demo())
