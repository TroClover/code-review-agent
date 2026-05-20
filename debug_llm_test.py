"""Test LLM API connection."""
import os
import sys
from pathlib import Path

# Check environment variables
api_key = os.environ.get('BREVIEW_LLM_API_KEY', '')
openai_key = os.environ.get('OPENAI_API_KEY', '')

print("=" * 50)
print("API Key Check")
print("=" * 50)
print(f"BREVIEW_LLM_API_KEY: {'SET (' + api_key[:10] + '...)' if api_key else 'NOT SET'}")
print(f"OPENAI_API_KEY: {'SET (' + openai_key[:10] + '...)' if openai_key else 'NOT SET'}")
print()

# Try to load config
sys.path.insert(0, os.path.dirname(__file__))
from breview.config.loader import load_config
from breview.llm.client import create_llm_client

print("=" * 50)
print("Config Loading Test")
print("=" * 50)

# Load config from current directory
repo_path = Path(__file__).parent / ".breview.yml"
print(f"Looking for config at: {repo_path}")
print(f"Config file exists: {repo_path.exists()}")

try:
    config = load_config(repo_path=repo_path)
    print(f"Config loaded successfully")
    print(f"Provider: {config.llm.provider}")
    print(f"Model: {config.llm.model}")
    print(f"Base URL: {config.llm.base_url}")

    # Check if API key is in config
    if config.llm.api_key and "set via" not in str(config.llm.api_key):
        print(f"API Key from config: {config.llm.api_key[:10]}...")
    else:
        print("API Key from config: Using environment variable")
except Exception as e:
    print(f"Config loading failed: {e}")
    sys.exit(1)

print()
print("=" * 50)
print("LLM Client Creation Test")
print("=" * 50)

try:
    llm_client = create_llm_client(config)
    print(f"LLM client created successfully")
    print(f"Provider: {llm_client.provider.__class__.__name__}")
except Exception as e:
    print(f"LLM client creation failed: {e}")
    sys.exit(1)

print()
print("=" * 50)
print("LLM API Call Test")
print("=" * 50)

import asyncio

async def test_llm_call():
    try:
        response = await llm_client.complete(
            messages=[{"role": "user", "content": "Say 'Hello, I am working!' in one sentence."}],
            model=config.llm.model,
            temperature=0.1,
            max_tokens=100,
        )
        print(f"LLM call successful!")
        print(f"Response content: '{response.content}'")
        print(f"Response content length: {len(response.content)}")
        print(f"Model: {response.model}")
        print(f"Input tokens: {response.input_tokens}")
        print(f"Output tokens: {response.output_tokens}")
        print(f"Cost: ${response.cost_usd:.6f}")

        # Debug: print raw response if empty
        if not response.content.strip():
            print("\nWARNING: Response content is empty!")
            print("This might be a DeepSeek API response format issue.")

        return True
    except Exception as e:
        print(f"LLM call failed: {e}")
        import traceback
        traceback.print_exc()
        return False

result = asyncio.run(test_llm_call())

print()
print("=" * 50)
print("Summary")
print("=" * 50)
if result:
    print("SUCCESS: LLM API is working correctly!")
else:
    print("FAILED: LLM API call failed. Check your API key and network connection.")
