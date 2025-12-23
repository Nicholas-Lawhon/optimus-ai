"""
Quick Validation Test for SQLite Implementation

This test checks for specific issues I noticed while reviewing the code.
Run this first to identify any immediate problems that need fixing.

Run with: python quick_validation.py
"""

import tempfile
import os
from datetime import datetime, timezone

from memory.stores.sqlite import SQLiteMemoryStore
from memory.config import MemoryConfig, MemoryType, MemoryScope
from memory.models import Memory, User, Project, MemoryQuery


def test_basic_functionality():
    """Quick test to validate basic CRUD operations work."""
    
    # Setup
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        config = MemoryConfig()
        store = SQLiteMemoryStore(config, db_path)
        store.initialize()
        
        print("✅ Store initialization successful")
        
        # Test user operations
        user = User.create("Test User")
        stored_user = store.store_user(user)
        retrieved_user = store.get_user(user.id)
        
        assert retrieved_user.id == user.id
        assert retrieved_user.name == user.name
        print("✅ User CRUD operations successful")
        
        # Test project operations
        project = Project.from_path("/test/project")
        stored_project = store.store_project(project)
        retrieved_project = store.get_project(project.id)
        
        assert retrieved_project.id == project.id
        assert retrieved_project.name == project.name
        print("✅ Project CRUD operations successful")
        
        # Test memory operations
        memory = Memory.create(
            content="Test memory content",
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.USER,
            user_id=user.id,
            tags=["test", "validation"],
            metadata={"test": True}
        )
        
        stored_memory = store.store(memory)
        retrieved_memory = store.get(memory.id)
        
        assert retrieved_memory.id == memory.id
        assert retrieved_memory.content == memory.content
        assert retrieved_memory.tags == ["test", "validation"]
        assert retrieved_memory.metadata == {"test": True}
        print("✅ Memory CRUD operations successful")
        
        # Test query operations
        query = MemoryQuery(user_id=user.id)
        results = store.query(query)
        assert len(results) == 1
        assert results[0].id == memory.id
        print("✅ Query operations successful")
        
        # Test count operations
        count = store.count()
        assert count == 1
        print("✅ Count operations successful")
        
        # Test delete operations
        deleted = store.delete(memory.id)
        assert deleted is True
        assert store.get(memory.id) is None
        print("✅ Delete operations successful")
        
        store.close()
        print("\n🎉 All basic functionality tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass


def test_potential_issues():
    """Test for specific issues I noticed in the code."""
    
    print("\n🔍 Testing for potential issues...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        config = MemoryConfig()
        store = SQLiteMemoryStore(config, db_path)
        store.initialize()
        
        # Issue 1: Check if table column names match what's expected
        # Your code uses "display_name" but calls it "name" in user retrieval
        user = User.create("Test User")
        store.store_user(user)
        
        # This should work - if it fails, there's a column name mismatch
        retrieved = store.get_user(user.id)
        assert retrieved.name == user.name
        print("✅ User table column names are correct")
        
        # Issue 2: Check JSON serialization/deserialization
        memory = Memory.create(
            content="Test",
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.USER,
            user_id=user.id,
            tags=["tag1", "tag2"],
            metadata={"key": "value", "number": 42}
        )
        store.store(memory)
        retrieved = store.get(memory.id)
        
        assert retrieved.tags == ["tag1", "tag2"]
        assert retrieved.metadata == {"key": "value", "number": 42}
        print("✅ JSON serialization/deserialization works correctly")
        
        # Issue 3: Check datetime handling
        assert isinstance(retrieved.created_at, datetime)
        print("✅ Datetime handling works correctly")
        
        # Issue 4: Check enum handling
        assert retrieved.memory_type == MemoryType.CONVERSATION
        assert retrieved.scope == MemoryScope.USER
        print("✅ Enum serialization works correctly")
        
        store.close()
        print("\n🎉 All potential issue tests passed!")
        
    except Exception as e:
        print(f"\n❌ Potential issue found: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    print("🔬 Running Quick Validation Tests for SQLite Memory Store")
    print("=" * 60)
    
    test_basic_functionality()
    test_potential_issues()
    
    print("\n✨ Validation complete!")