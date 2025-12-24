"""
Quick Validation Test for MemoryManager

Run with: python -m pytest tests/memory/test_manager_quick.py -v
Or directly: python tests/memory/test_manager_quick.py
"""

import tempfile
import os
import shutil
from datetime import datetime

from memory.manager import MemoryManager
from memory.config import MemoryConfig, MemoryScope, MemoryType

def test_manager_initialization():
    """Test that MemoryManager initializes correctly."""
    print("🧪 Testing MemoryManager initialization...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        config = MemoryConfig(storage_path=db_path)
        
        # Test basic initialization
        manager = MemoryManager.initialize(config=config)
        
        assert manager is not None
        assert manager.config == config
        assert manager.store is not None
        assert manager.safety is not None
        
        manager.close()
        print("✅ Basic initialization: PASSED")


def test_user_management():
    """Test user creation and retrieval."""
    print("\n🧪 Testing user management...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        config = MemoryConfig(storage_path=db_path)
        
        with MemoryManager.initialize(config=config) as manager:
            # Test explicit user creation
            user = manager.get_or_create_user("Nick")
            assert user.name == "Nick"
            assert user.id.startswith("usr_")
            
            # Test idempotent behavior
            same_user = manager.get_or_create_user("Nick")
            assert same_user.id == user.id
            
            # Test set_current_user
            manager.set_current_user(user)
            assert manager.current_user.id == user.id
            
            # Test lazy loading of default user
            manager2 = MemoryManager.initialize(config=config)
            default_user = manager2.current_user
            assert default_user.name == config.default_user_id
            manager2.close()
        
        print("✅ User management: PASSED")


def test_project_management():
    """Test project creation and retrieval."""
    print("\n🧪 Testing project management...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        config = MemoryConfig(storage_path=db_path)
        
        with MemoryManager.initialize(config=config) as manager:
            # Test project creation
            project = manager.get_or_create_project("/home/nick/test-project")
            assert project.name == "test-project"
            assert project.id.startswith("proj_")
            
            # Test idempotent behavior
            same_project = manager.get_or_create_project("/home/nick/test-project")
            assert same_project.id == project.id
            
            # Test set_current_project
            manager.set_current_project(project)
            assert manager.current_project.id == project.id
            
            # Test None project
            manager.set_current_project(None)
            assert manager.current_project is None
        
        print("✅ Project management: PASSED")


def test_conversation_flow():
    """Test storing conversations with different tags and scopes."""
    print("\n🧪 Testing conversation storage (Chat vs Tool Use)...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        config = MemoryConfig(storage_path=db_path)
        
        # Initialize with a User but NO Project initially
        manager = MemoryManager.initialize(
            config=config, 
            user_name="Tester"
        )
        
        try:
            # 1. Test USER Scope (No active project)
            print("  Testing User-scoped chat...")
            mem1 = manager.store_conversation(
                user_message="Hello",
                assistant_response="Hi there",
                tags=["chat"]
            )
            
            assert mem1.scope == MemoryScope.USER
            assert "chat" in mem1.tags
            assert mem1.user_id == manager.current_user.id
            assert mem1.project_id is None
            
            # 2. Test PROJECT Scope (Activate project)
            print("  Testing Project-scoped tool use...")
            project = manager.get_or_create_project("/tmp/test_project")
            manager.set_current_project(project)
            
            mem2 = manager.store_conversation(
                user_message="List files",
                assistant_response="Called Function: get_files_info",
                tags=["tool_use"]
            )
            
            assert mem2.scope == MemoryScope.PROJECT
            assert "tool_use" in mem2.tags
            assert mem2.project_id == project.id
            assert mem2.user_id == manager.current_user.id # Should still have user
            
            # 3. Test Retrieval
            print("  Testing Retrieval...")
            # Should find mem2 because we are in the project
            history = manager.get_recent_conversations(limit=5)
            assert len(history) == 2
            assert history[0].id == mem2.id  # Newest first
            assert history[1].id == mem1.id
            
        finally:
            manager.close()

    print("✅ Conversation flow: PASSED")


if __name__ == "__main__":
    print("🔬 Running MemoryManager Quick Validation Tests")
    print("=" * 60)
    
    try:
        test_manager_initialization()
        test_user_management()
        test_project_management()
        test_conversation_flow()
        
        print("\n" + "=" * 60)
        print("🎉 All quick validation tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()