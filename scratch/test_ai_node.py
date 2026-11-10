import os
import sys
import json
import asyncio
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "release-domino" / "backend"
sys.path.insert(0, str(backend_dir))

from app.llm import client as llm_client

async def main():
    prompt = "Build a Redis rate limiter that blocks brute-force login attempts"
    nvidia_key = llm_client.get_nvidia_api_key()
    print("NVIDIA Key:", nvidia_key[:10] + "...")
    print("NVIDIA Model:", llm_client.get_nvidia_model())
    
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert software engineer. Respond with a JSON object conforming to:\n"
                "{\n"
                '  "name": "app/rate_limiter.py",\n'
                '  "code": "complete working code",\n'
                '  "lang": "py",\n'
                '  "is_crown_jewel": true,\n'
                '  "suggested_inputs": ["app/auth.py"],\n'
                '  "suggested_outputs": ["app/redis_cache.py"],\n'
                '  "explanation": "summary"\n'
                "}"
            ),
        },
        {"role": "user", "content": prompt},
    ]
    
    res = await llm_client.chat(messages, timeout=20.0)
    print("Result keys:", list(res.keys()) if isinstance(res, dict) else res)
    print("Result JSON:", json.dumps(res, indent=2)[:400])

if __name__ == "__main__":
    asyncio.run(main())
