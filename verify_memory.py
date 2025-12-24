"""
Verification Script for Memory Manager
Run this to see your memory system in action!
"""
import os
import shutil
from memory.manager import MemoryManager
from memory.config import MemoryConfig

def verify_full_flow():
    print("🔬 Starting Memory Manager Verification...")
    print("=" * 60)
    
    # 1. Setup a clean test environment
    db_path = "./data/test_memory.db"
    if os.path.exists("./data"):
        shutil.rmtree("./data")
    os.makedirs("./data", exist_ok=True)
    
    # 2. Initialize Manager
    config = MemoryConfig(storage_path=db_path)
    print(f"📁 Database: {db_path}")
    
    # Initialize with a specific user and project
    manager = MemoryManager.initialize(
        config=config,
        user_name="Nick",
        project_path="/home/nick/optimus-ai"
    )
    print("✅ Initialization complete")

    # 3. Store some "Static" Context
    print("\n📝 Storing Context & Preferences...")
    manager.store_user_preference("I prefer concise Python code.")
    manager.store_project_context("This project uses SQLite for storage.")
    manager.store_learned_correction(
        original_response="os.system('rm -rf /')", 
        correction="NEVER run destructive commands!"
    )
    print("✅ Static memories stored")

    # 4. Simulate a Conversation (store enough to trigger the 'Squeeze')
    print("\n💬 Simulating Conversation...")
    for i in range(1, 6):
        manager.store_conversation(
            user_message=f"Question {i}",
            assistant_response=f"Answer {i} - This is a bit of history content."
        )
    print("✅ 5 conversation turns stored")

    # 5. Build Context (The Big Test)
    print("\n🏗️  Building Context String...")
    # We use a small limit to force the 'Squeeze' logic to work
    context = manager.build_context_string(max_chars=600)
    
    print("-" * 20 + " CONTEXT START " + "-" * 20)
    print(context)
    print("-" * 20 + "  CONTEXT END  " + "-" * 20)
    
    # Verification checks
    if "concise Python" in context:
        print("\n✅ User Preference found")
    else:
        print("\n❌ User Preference MISSING")
        
    if "Question 5" in context:
        print("✅ Most recent history found (Squeeze worked!)")
    else:
        print("❌ Most recent history MISSING (Squeeze failed)")
        
    manager.close()

if __name__ == "__main__":
    verify_full_flow()