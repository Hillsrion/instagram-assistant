import sys
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.audio.audio_cache import AudioCache

def test_cache():
    # Setup temp cache
    test_cache_path = Path("test_audio_cache.json")
    if test_cache_path.exists():
        test_cache_path.unlink()
        
    print("🔹 Testing Cache Creation...")
    cache = AudioCache(cache_path=test_cache_path)
    
    # Create dummy file
    dummy_audio = Path("test_audio.mp4")
    with open(dummy_audio, "w") as f:
        f.write("fake audio content")
        
    print("🔹 Testing Set/Get...")
    cache.set(dummy_audio, "This is a transcript", model="test_model")
    
    # Verify in memory
    res = cache.get(dummy_audio)
    assert res == "This is a transcript"
    print("   ✅ In-memory Get worked")
    
    # Verify save
    cache.save()
    assert test_cache_path.exists()
    print("   ✅ Save to disk worked")
    
    # Verify persistence
    print("🔹 Testing Persistence...")
    cache2 = AudioCache(cache_path=test_cache_path)
    res2 = cache2.get(dummy_audio)
    assert res2 == "This is a transcript"
    print("   ✅ Persistence worked")
    
    # Cleanup
    dummy_audio.unlink()
    test_cache_path.unlink()
    print("🎉 All AudioCache tests passed!")

if __name__ == "__main__":
    test_cache()
