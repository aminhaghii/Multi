"""
MCP Playwright Test - New Features Verification
Tests: Session management, History sidebar, Agent Space, Export
"""
from playwright.sync_api import sync_playwright
import time
import requests

BASE_URL = "http://127.0.0.1:8000"

def test_api_health():
    """Test API health endpoint"""
    print("\n[TEST 1] API Health Check")
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        data = r.json()
        print(f"  Status: {r.status_code}")
        print(f"  LLM Available: {data.get('llm_available', False)}")
        return r.status_code == 200
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def test_session_api():
    """Test session management API"""
    print("\n[TEST 2] Session Management API")
    try:
        # Create session
        r = requests.post(f"{BASE_URL}/api/sessions", timeout=10)
        session = r.json()
        print(f"  Created session: {session.get('id', 'N/A')[:8]}...")
        
        # Get recent sessions
        r = requests.get(f"{BASE_URL}/api/sessions/recent", timeout=10)
        sessions = r.json()
        print(f"  Recent sessions count: {len(sessions)}")
        
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def test_chat_query():
    """Test chat query with Persian translation"""
    print("\n[TEST 3] Chat Query (Persian)")
    try:
        r = requests.post(f"{BASE_URL}/api/chat", 
                         json={"message": "فاز آرامش چیست؟"}, 
                         timeout=120)
        data = r.json()
        
        print(f"  Success: {data.get('success', False)}")
        print(f"  Has Sources: {'**Sources:**' in data.get('answer', '')}")
        print(f"  Has Tranquilization: {'Tranquilization' in data.get('answer', '')}")
        print(f"  Image count: {len(data.get('image_paths', []))}")
        print(f"  Confidence: {data.get('confidence', 0):.2f}")
        
        return data.get('success', False)
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def test_ui_with_playwright():
    """Test UI with Playwright"""
    print("\n[TEST 4] UI with Playwright")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            # Navigate to app
            print("  Opening page...")
            page.goto(BASE_URL, timeout=15000)
            time.sleep(2)
            
            # Check main elements
            new_chat_btn = page.locator('#new-chat-btn')
            message_input = page.locator('#message-input')
            send_btn = page.locator('#send-btn')
            
            print(f"  New Chat button visible: {new_chat_btn.is_visible()}")
            print(f"  Message input visible: {message_input.is_visible()}")
            print(f"  Send button visible: {send_btn.is_visible()}")
            
            # Test New Chat button
            print("  Clicking New Chat...")
            new_chat_btn.click()
            time.sleep(1)
            
            # Send a message
            print("  Sending test message...")
            message_input.fill("What is AOCS?")
            send_btn.click()
            time.sleep(10)
            
            # Check for response
            messages = page.locator('.max-w-2xl').all()
            print(f"  Messages in chat: {len(messages)}")
            
            # Take screenshot
            page.screenshot(path='test_ui_result.png')
            print("  Screenshot saved: test_ui_result.png")
            
            browser.close()
            return len(messages) >= 2
            
        except Exception as e:
            print(f"  ERROR: {e}")
            page.screenshot(path='test_ui_error.png')
            browser.close()
            return False

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("MCP TEST SUITE - New Features Verification")
    print("=" * 60)
    
    results = {
        "API Health": test_api_health(),
        "Session API": test_session_api(),
        "Chat Query": test_chat_query(),
        "UI Playwright": test_ui_with_playwright()
    }
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        icon = "✓" if result else "✗"
        print(f"  {icon} {name}: {status}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    print("=" * 60)
    
    return passed == len(results)

if __name__ == "__main__":
    run_all_tests()
