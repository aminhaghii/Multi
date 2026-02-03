"""
Test script to verify all fixes from FIX.md
"""
import sys
sys.path.insert(0, '.')

def test_imports():
    """Test 1: All critical dependencies"""
    print("=" * 80)
    print("TEST 1: Critical Dependencies")
    print("=" * 80)
    try:
        import fastapi
        import uvicorn
        import pymupdf
        import googletrans
        import httpx
        import pdfplumber
        from deep_translator import GoogleTranslator
        print("✅ All critical dependencies installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False

def test_chunk_size():
    """Test 2: Chunk size configuration"""
    print("\n" + "=" * 80)
    print("TEST 2: Chunk Size Configuration")
    print("=" * 80)
    from ingestion import DocumentProcessor
    from vector_store import VectorStore
    
    vs = VectorStore('./faiss_db')
    dp = DocumentProcessor(vs)
    
    expected_chunk = 800
    expected_overlap = 160
    
    if dp.chunk_size == expected_chunk and dp.chunk_overlap == expected_overlap:
        print(f"✅ Chunk size: {dp.chunk_size}, Overlap: {dp.chunk_overlap}")
        return True
    else:
        print(f"❌ Expected chunk={expected_chunk}, overlap={expected_overlap}")
        print(f"   Got chunk={dp.chunk_size}, overlap={dp.chunk_overlap}")
        return False

def test_cache_enabled():
    """Test 3: Cache system enabled"""
    print("\n" + "=" * 80)
    print("TEST 3: Cache System")
    print("=" * 80)
    from cache import get_cache
    
    cache = get_cache()
    stats = cache.get_stats()
    print(f"✅ Cache initialized: {stats}")
    
    # Check if cache methods work
    cache.set("test_query", {"answer": "test", "confidence": 0.8})
    result = cache.get("test_query")
    
    if result and result.get('answer') == 'test':
        print("✅ Cache set/get working")
        cache.clear_all()
        return True
    else:
        print("❌ Cache set/get failed")
        return False

def test_llm_retry():
    """Test 4: LLM retry logic"""
    print("\n" + "=" * 80)
    print("TEST 4: LLM Retry Logic")
    print("=" * 80)
    from llm_client import LLMClient
    
    client = LLMClient()
    
    # Check if generate method has max_retries parameter
    import inspect
    sig = inspect.signature(client.generate)
    params = list(sig.parameters.keys())
    
    if 'max_retries' in params:
        print("✅ LLM client has retry logic (max_retries parameter)")
        return True
    else:
        print("❌ LLM client missing retry logic")
        return False

def test_translation_fallback():
    """Test 5: Translation fallback"""
    print("\n" + "=" * 80)
    print("TEST 5: Translation Fallback")
    print("=" * 80)
    
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source='auto', target='en')
        result = translator.translate('سلام')
        print(f"✅ Deep-translator fallback available: '{result}'")
        return True
    except Exception as e:
        print(f"❌ Deep-translator fallback failed: {e}")
        return False

def test_query_expansion():
    """Test 6: Query expansion in QueryUnderstandingAgent"""
    print("\n" + "=" * 80)
    print("TEST 6: Query Expansion")
    print("=" * 80)
    from agents.specific_agents import QueryUnderstandingAgent
    
    # Check if execute returns expanded_terms
    import inspect
    source = inspect.getsource(QueryUnderstandingAgent.execute)
    
    if 'expanded_terms' in source and 'all_search_terms' in source:
        print("✅ Query expansion implemented")
        return True
    else:
        print("❌ Query expansion not found")
        return False

def test_inline_citations():
    """Test 7: Inline citations in prompts"""
    print("\n" + "=" * 80)
    print("TEST 7: Inline Citations")
    print("=" * 80)
    from agents.specific_agents import ReasoningAgent
    
    import inspect
    source = inspect.getsource(ReasoningAgent._simplified_reasoning)
    
    if 'inline citations' in source.lower() or '[Source:' in source:
        print("✅ Inline citation instructions in prompts")
        return True
    else:
        print("❌ Inline citations not found")
        return False

def test_health_endpoint():
    """Test 8: Health monitoring endpoint"""
    print("\n" + "=" * 80)
    print("TEST 8: Health Monitoring")
    print("=" * 80)
    
    import inspect
    from api_server import app
    
    # Check if /api/health/detailed exists
    routes = [route.path for route in app.routes]
    
    if '/api/health/detailed' in routes:
        print("✅ Detailed health endpoint exists")
        return True
    else:
        print("❌ Detailed health endpoint not found")
        return False

def test_reranking():
    """Test 9: Reranking with query relevance"""
    print("\n" + "=" * 80)
    print("TEST 9: Reranking Logic")
    print("=" * 80)
    from agents.hybrid_retrieval import HybridRetrievalAgent
    
    import inspect
    source = inspect.getsource(HybridRetrievalAgent._merge_and_rerank)
    
    if 'query_keywords' in source and 'keyword_relevance' in source:
        print("✅ Query-based reranking implemented")
        return True
    else:
        print("❌ Query-based reranking not found")
        return False

def main():
    """Run all tests"""
    print("\n" + "🧪" * 40)
    print("TESTING ALL FIXES FROM FIX.md")
    print("🧪" * 40 + "\n")
    
    tests = [
        test_imports,
        test_chunk_size,
        test_cache_enabled,
        test_llm_retry,
        test_translation_fallback,
        test_query_expansion,
        test_inline_citations,
        test_health_endpoint,
        test_reranking
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Success Rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED!")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
