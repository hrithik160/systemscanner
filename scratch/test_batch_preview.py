import urllib.request
import json

payload = {
    "pid": "demo",
    "new_node_name": "bill_calculator.py",
    "new_node_code": "def calculate_bill():\n    return 42\n",
    "new_node_lang": "py",
    "is_crown_jewel": False,
    "input_node_ids": ["app/cart.py"],
    "output_node_ids": ["app/redis_cache.py"]
}

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/sandbox/batch-wire-preview",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode("utf-8"))
    preview_id = data["preview_id"]
    print("PREVIEW STATUS 200, preview_id:", preview_id)

finalize_payload = {
    "pid": "demo",
    "preview_id": preview_id,
    "apply": True,
    "payload": data
}
req2 = urllib.request.Request(
    "http://127.0.0.1:8000/api/sandbox/batch-wire-finalize",
    data=json.dumps(finalize_payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req2) as resp2:
    data2 = json.loads(resp2.read().decode("utf-8"))
    print("FINALIZE STATUS 200, result:", data2)
