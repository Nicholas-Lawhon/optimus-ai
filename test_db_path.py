#!/usr/bin/env python3
"""
Database Path Resolution Test

This script tests the enhanced MemoryConfig's smart path resolution
to ensure databases are created in the correct locations.

Run this to verify the hybrid storage approach works correctly.
"""

import os
import tempfile
from pathlib import Path

# We'll need to update the import once you've replaced your config.py
# For now, I'm importing from the enhanced version
try:
    from memory.config import MemoryConfig
except ImportError:
    print("Note: Import the enhanced config.py first, then re-run this test")
    exit(1)


def test_default_path_resolution():
    """Test that default path goes to user data directory."""
    print("🧪 Testing default path resolution...")
    
    # Clear any environment override for clean test
    old_path = os.environ.pop('OPTIMUS_MEMORY_PATH', None)
    
    try:
        config = MemoryConfig()
        storage_info = config.get_storage_info()
        
        print(f"✅ Default database path: {storage_info['storage_path']}")
        print(f"✅ Storage directory: {storage_info['storage_dir']}")
        print(f"✅ Database name: {storage_info['database_name']}")
        print(f"✅ Directory exists: {storage_info['directory_exists']}")
        print(f"✅ Is override: {storage_info['is_override']}")
        
        # Verify it's in user directory (not project directory)
        if os.name == 'nt':  # Windows
            expected_in_path = '.optimus_ai'
        else:  # Linux/Mac
            expected_in_path = '.optimus_ai'
        
        assert expected_in_path in storage_info['storage_path'], f"Expected '{expected_in_path}' in path"
        assert storage_info['database_name'] == 'memory.db', "Expected database name to be 'memory.db'"
        
        print("✅ Default path resolution: PASSED\n")
        return storage_info['storage_path']
        
    finally:
        # Restore environment if it was set
        if old_path:
            os.environ['OPTIMUS_MEMORY_PATH'] = old_path


def test_environment_override():
    """Test that OPTIMUS_MEMORY_PATH environment variable works."""
    print("🧪 Testing environment variable override...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_db_path = Path(temp_dir) / "test_override.db"
        
        # Set environment variable
        os.environ['OPTIMUS_MEMORY_PATH'] = str(test_db_path)
        
        try:
            config = MemoryConfig()
            storage_info = config.get_storage_info()
            
            print(f"✅ Override database path: {storage_info['storage_path']}")
            print(f"✅ Is override: {storage_info['is_override']}")
            
            assert storage_info['storage_path'] == str(test_db_path), "Override path not applied"
            assert storage_info['is_override'] is True, "Override flag not set"
            assert 'test_override.db' in storage_info['storage_path'], "Override filename not found"
            
            print("✅ Environment override: PASSED\n")
            
        finally:
            # Clean up environment
            os.environ.pop('OPTIMUS_MEMORY_PATH', None)


def test_explicit_path():
    """Test explicit path setting."""
    print("🧪 Testing explicit path setting...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        explicit_path = Path(temp_dir) / "explicit.db"
        
        config = MemoryConfig(storage_path=str(explicit_path))
        storage_info = config.get_storage_info()
        
        print(f"✅ Explicit database path: {storage_info['storage_path']}")
        print(f"✅ Is override: {storage_info['is_override']}")
        
        assert storage_info['storage_path'] == str(explicit_path), "Explicit path not set"
        assert 'explicit.db' in storage_info['storage_path'], "Explicit filename not found"
        
        print("✅ Explicit path: PASSED\n")


def test_directory_creation():
    """Test that directories are created automatically."""
    print("🧪 Testing automatic directory creation...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a nested path that doesn't exist yet
        nested_path = Path(temp_dir) / "nested" / "directories" / "test.db"
        
        config = MemoryConfig(storage_path=str(nested_path))
        storage_info = config.get_storage_info()
        
        print(f"✅ Nested path: {storage_info['storage_path']}")
        print(f"✅ Directory exists: {storage_info['directory_exists']}")
        
        # The __post_init__ should have created the directory
        assert nested_path.parent.exists(), "Directory not created automatically"
        
        print("✅ Directory creation: PASSED\n")


def test_database_creation():
    """Test actual SQLite database creation."""
    print("🧪 Testing actual database creation...")
    
    # Clear any environment override
    old_path = os.environ.pop('OPTIMUS_MEMORY_PATH', None)
    
    try:
        # Import SQLite store
        from memory.stores.sqlite import SQLiteMemoryStore
        
        config = MemoryConfig()
        storage_info = config.get_storage_info()
        db_path = storage_info['storage_path']
        
        print(f"✅ Will create database at: {db_path}")
        
        # Create and initialize the store
        store = SQLiteMemoryStore(config, db_path)
        store.initialize()
        
        # Verify database file was created
        assert Path(db_path).exists(), f"Database file not created at {db_path}"
        print(f"✅ Database file created: {Path(db_path).exists()}")
        
        # Test basic operation
        stats = store.get_stats()
        print(f"✅ Database stats: {stats}")
        
        store.close()
        print("✅ Database creation: PASSED\n")
        
        return db_path
        
    finally:
        if old_path:
            os.environ['OPTIMUS_MEMORY_PATH'] = old_path


def main():
    """Run all path resolution tests."""
    print("🚀 Starting Database Path Resolution Tests")
    print("=" * 50)
    
    try:
        # Test path resolution
        default_path = test_default_path_resolution()
        test_environment_override()
        test_explicit_path()
        test_directory_creation()
        
        # Test actual database creation
        db_path = test_database_creation()
        
        print("🎉 All tests passed!")
        print("\n📍 Your production database will be at:")
        print(f"   {default_path}")
        print("\n💡 You can override this by setting:")
        print("   export OPTIMUS_MEMORY_PATH=/your/custom/path.db")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()