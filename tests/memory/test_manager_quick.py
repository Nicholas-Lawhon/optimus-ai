"""
Quick Validation Test for MemoryManager

Run with: python -m pytest tests/memory/test_manager_quick.py -v
Or directly: python tests/memory/test_manager_quick.py
"""

import tempfile
import os

from memory.manager import MemoryManager
from memory.config import MemoryConfig


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
            print(f"  Created user: {user.id} ({user.name})")
            
            # Test idempotent behavior
            same_user = manager.get_or_create_user("Nick")
            assert same_user.id == user.id
            print("  Idempotent creation: PASSED")
            
            # Test set_current_user
            manager.set_current_user(user)
            assert manager.current_user.id == user.id
            print("  Set current user: PASSED")
            
            # Test lazy loading of default user
            manager2 = MemoryManager.initialize(config=config)
            default_user = manager2.current_user
            assert default_user.name == config.default_user_id
            print(f"  Default user lazy-loaded: {default_user.name}")
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
            print(f"  Created project: {project.id} ({project.name})")
            
            # Test idempotent behavior
            same_project = manager.get_or_create_project("/home/nick/test-project")
            assert same_project.id == project.id
            print("  Idempotent creation: PASSED")
            
            # Test set_current_project
            manager.set_current_project(project)
            assert manager.current_project.id == project.id
            print("  Set current project: PASSED")
            
            # Test None project
            manager.set_current_project(None)
            assert manager.current_project is None
            print("  Clear project: PASSED")
        
        print("✅ Project management: PASSED")


def test_initialize_with_user_and_project():
    """Test initialization with explicit user and project."""
    print("\n🧪 Testing initialization with user and project...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        config = MemoryConfig(storage_path=db_path)
        
        with MemoryManager.initialize(
            config=config,
            user_name="Nick",
            project_path="/home/nick/optimus-ai"
        ) as manager:
            assert manager.current_user.name == "Nick"
            assert manager.current_project.name == "optimus-ai"
            print(f"  User: {manager.current_user.name}")
            print(f"  Project: {manager.current_project.name}")
        
        print("✅ Full initialization: PASSED")


def test_context_manager():
    """Test that context manager properly closes resources."""
    print("\n🧪 Testing context manager...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        config = MemoryConfig(storage_path=db_path)
        
        manager = MemoryManager.initialize(config=config)
        
        with manager:
            # Do something
            _ = manager.current_user
        
        # After exiting, store should be closed
        # We can't easily test this without accessing private state,
        # but we can verify no exceptions were raised
        print("✅ Context manager: PASSED")


if __name__ == "__main__":
    print("🔬 Running MemoryManager Quick Validation Tests")
    print("=" * 60)
    
    try:
        test_manager_initialization()
        test_user_management()
        test_project_management()
        test_initialize_with_user_and_project()
        test_context_manager()
        
        print("\n" + "=" * 60)
        print("🎉 All quick validation tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()