"""LLM connection diagnostic script.
Run: python debug_llm.py
"""
import os
import time

api_key = os.environ.get("BREVIEW_LLM_API_KEY", "")
base_url = "https://api.deepseek.com"
model = "deepseek-v4-flash"

print(f"API key: {'SET (' + api_key[:8] + '...)' if api_key else 'NOT SET'}")
print(f"Base URL: {base_url}")
print(f"Model: {model}")
print()

# Test 1: httpx direct GET (no SDK)
print("=" * 50)
print("Test 1: httpx direct GET to base_url")
print("=" * 50)
try:
    import httpx
    print(f"  httpx version: {httpx.__version__}")
    r = httpx.get(base_url, timeout=10)
    print(f"  Status: {r.status_code}")
    print(f"  OK!")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
print()

# Test 2: httpx direct POST to chat completions (no SDK)
print("=" * 50)
print("Test 2: httpx direct POST to /chat/completions")
print("=" * 50)
try:
    import httpx
    r = httpx.post(
        f"{base_url}/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Say OK"}],
            "max_tokens": 10,
        },
        timeout=30,
    )
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        print(f"  Response: {r.json()['choices'][0]['message']['content']}")
    else:
        print(f"  Body: {r.text[:200]}")
    print(f"  OK!")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
print()

# Test 3: OpenAI sync SDK
print("=" * 50)
print("Test 3: OpenAI sync SDK")
print("=" * 50)
try:
    import openai
    print(f"  openai version: {openai.__version__}")
    client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=30)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=10,
    )
    print(f"  Response: {resp.choices[0].message.content}")
    print(f"  OK!")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
print()

# Test 4: OpenAI async SDK
print("=" * 50)
print("Test 4: OpenAI async SDK")
print("=" * 50)
try:
    import asyncio
    import openai

    async def test_async():
        client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=30)
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=10,
        )
        await client.close()
        return resp

    resp = asyncio.run(test_async())
    print(f"  Response: {resp.choices[0].message.content}")
    print(f"  OK!")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
print()

# Test 5: Sync in thread pool (what breview does as fallback)
print("=" * 50)
print("Test 5: Sync in asyncio.to_thread")
print("=" * 50)
try:
    import asyncio
    import openai

    def sync_call():
        client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=30)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=10,
        )
        return resp

    resp = asyncio.run(asyncio.to_thread(sync_call))
    print(f"  Response: {resp.choices[0].message.content}")
    print(f"  OK!")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")

print()
print("=" * 50)
print("Done. Check which tests passed/failed above.")
print("=" * 50)
