"""
Verification Script for Memory Manager
Run this to see your memory system in action!
"""
import os
import shutil
from memory.manager import MemoryManager
from memory.config import MemoryConfig, RetentionPolicy

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

    # --- NEW: Verify User Tagging (Immutable Copy-on-Write) ---
    print("\n🏷️  Testing User Tagging...")
    manager.add_user_tag("power_user")
    
    if "power_user" in manager.current_user.tags:
        print(f"✅ User tag 'power_user' added successfully. Tags: {manager.current_user.tags}")
    else:
        print("❌ User tag FAILED to add.")

    # --- NEW: Verify Project Tagging (Mutable) ---
    print("\n🏷️  Testing Project Tagging...")
    # Access the project directly since it's now mutable (unfrozen)
    manager.current_project.tags.append("active_development")
    manager.current_project.tags.append("python_v3")
    
    # Save the update
    manager.store.store_project(manager.current_project)
    
    # Reload to verify persistence
    reloaded_project = manager.store.get_project(manager.current_project.id)
    if "active_development" in reloaded_project.tags:
        print(f"✅ Project tags saved successfully. Tags: {reloaded_project.tags}")
    else:
        print("❌ Project tags FAILED to save.")

    # 3. Store Context & Preferences
    print("\n📝 Storing Context & Preferences...")
    
    # --- NEW: Verify Retention Policy ---
    pref_memory = manager.store_user_preference("I prefer concise Python code.")
    
    if pref_memory.retention_policy == RetentionPolicy.LONG_TERM:
        print(f"✅ User Preference correctly set to LONG_TERM retention.")
    else:
        print(f"❌ User Preference has wrong policy: {pref_memory.retention_policy}")

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