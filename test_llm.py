import requests
import time
import json

print("Testing LLM server...")
print("="*50)

# Test 1: Health check
try:
    r = requests.get("http://127.0.0.1:8080/health", timeout=5)
    print(f"Health check: {r.status_code}")
except Exception as e:
    print(f"Health check failed: {e}")

# Test 2: Simple completion
body = {
    "prompt": "What is 2+2? Answer with just the number.",
    "max_tokens": 20,
    "temperature": 0.1
}

print("\nSending test query...")
start = time.time()
resp = requests.post("http://127.0.0.1:8080/completion", json=body, timeout=120)
elapsed = time.time() - start

result = resp.json()
content = result.get("content", "")

print(f"\nTime: {elapsed:.2f} seconds")
print(f"Response: {content.strip()}")
print(f"Generated tokens: {result.get('tokens_evaluated', 0)}")
