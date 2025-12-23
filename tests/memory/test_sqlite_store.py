"""
Tests for SQLite Memory Store Implementation

These tests verify that the SQLite backend correctly:
1. Implements all abstract base class methods
2. Handles CRUD operations for Users, Projects, and Memories
3. Properly filters and queries data
4. Maintains data consistency and foreign key relationships
5. Handles edge cases and errors gracefully

Run with: pytest tests/memory/test_sqlite_store.py -v
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from memory.stores.sqlite import SQLiteMemoryStore
from memory.config import MemoryConfig, MemoryType, MemoryScope, RetentionPolicy
from memory.models import Memory, User, Project, MemoryQuery
from memory.stores.base import MemoryStoreError, MemoryNotFoundError


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_db():
    """Create a temporary database file that gets cleaned up after tests."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    yield db_path
    
    # Cleanup
    try:
        os.unlink(db_path)
    except FileNotFoundError:
        pass


@pytest.fixture
def config():
    """Create a test configuration."""
    return MemoryConfig()


@pytest.fixture
def store(config, temp_db):
    """Create an initialized store for testing."""
    store = SQLiteMemoryStore(config, temp_db)
    store.initialize()
    yield store
    store.close()


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return User.create("Test User")


@pytest.fixture
def sample_project():
    """Create a sample project for testing."""
    return Project.from_path("/test/project/path")


@pytest.fixture
def sample_memory(sample_user):
    """Create a sample memory for testing."""
    return Memory.create(
        content="This is a test memory",
        memory_type=MemoryType.CONVERSATION,
        scope=MemoryScope.USER,
        user_id=sample_user.id,
        tags=["test", "sample"],
        metadata={"source": "unittest"}
    )


# =============================================================================
# Database Initialization Tests
# =============================================================================

class TestDatabaseInitialization:
    """Tests for database setup and schema creation."""
    
    def test_store_initializes_successfully(self, config, temp_db):
        """Store should initialize without errors."""
        store = SQLiteMemoryStore(config, temp_db)
        store.initialize()
        
        # Should be able to execute queries
        result = store.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [row[0] for row in result]
        
        expected_tables = ["users", "projects", "memories"]
        for table in expected_tables:
            assert table in table_names
        
        store.close()
    
    def test_foreign_keys_enabled(self, store):
        """Foreign key constraints should be enabled."""
        result = store.conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1  # 1 means enabled
    
    def test_indexes_created(self, store):
        """Important indexes should be created for performance."""
        result = store.conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        index_names = [row[0] for row in result]
        
        expected_indexes = ["idx_memories_user", "idx_memories_project", "idx_memories_type"]
        for index in expected_indexes:
            assert index in index_names
    
    def test_connection_property_fails_when_not_initialized(self, config, temp_db):
        """Accessing conn property should fail if not initialized."""
        store = SQLiteMemoryStore(config, temp_db)
        
        with pytest.raises(RuntimeError, match="not been initialized"):
            _ = store.conn


# =============================================================================
# User Operations Tests
# =============================================================================

class TestUserOperations:
    """Tests for user CRUD operations."""
    
    def test_store_user_success(self, store, sample_user):
        """Should successfully store a new user."""
        result = store.store_user(sample_user)
        
        assert result.id == sample_user.id
        assert result.name == sample_user.name
        assert result.created_at == sample_user.created_at
    
    def test_store_user_replaces_existing(self, store):
        """Storing user with same ID should update existing."""
        # Create and store original user
        user1 = User.create("Original Name")
        store.store_user(user1)
        
        # Create user with same ID but different name
        user2 = User(
            id=user1.id,
            name="Updated Name",
            created_at=user1.created_at
        )
        store.store_user(user2)
        
        # Retrieve should get updated version
        retrieved = store.get_user(user1.id)
        assert retrieved.name == "Updated Name"
    
    def test_get_user_by_id_success(self, store, sample_user):
        """Should retrieve user by ID."""
        store.store_user(sample_user)
        
        retrieved = store.get_user(sample_user.id)
        
        assert retrieved is not None
        assert retrieved.id == sample_user.id
        assert retrieved.name == sample_user.name
    
    def test_get_user_by_id_not_found(self, store):
        """Should return None for non-existent user."""
        result = store.get_user("usr_nonexistent")
        assert result is None
    
    def test_get_user_by_name_success(self, store, sample_user):
        """Should retrieve user by name."""
        store.store_user(sample_user)
        
        retrieved = store.get_user_by_name(sample_user.name)
        
        assert retrieved is not None
        assert retrieved.id == sample_user.id
        assert retrieved.name == sample_user.name
    
    def test_get_user_by_name_not_found(self, store):
        """Should return None for non-existent name."""
        result = store.get_user_by_name("Nonexistent User")
        assert result is None
    
    def test_user_datetime_serialization(self, store):
        """User created_at should be properly serialized/deserialized."""
        user = User.create("Time Test")
        original_time = user.created_at
        
        store.store_user(user)
        retrieved = store.get_user(user.id)
        
        assert retrieved.created_at == original_time
        assert isinstance(retrieved.created_at, datetime)


# =============================================================================
# Project Operations Tests
# =============================================================================

class TestProjectOperations:
    """Tests for project CRUD operations."""
    
    def test_store_project_success(self, store, sample_project):
        """Should successfully store a new project."""
        result = store.store_project(sample_project)
        
        assert result.id == sample_project.id
        assert result.name == sample_project.name
        assert result.path_hash == sample_project.path_hash
    
    def test_get_project_by_id_success(self, store, sample_project):
        """Should retrieve project by ID."""
        store.store_project(sample_project)
        
        retrieved = store.get_project(sample_project.id)
        
        assert retrieved is not None
        assert retrieved.id == sample_project.id
        assert retrieved.name == sample_project.name
        assert retrieved.path_hash == sample_project.path_hash
    
    def test_get_project_by_id_not_found(self, store):
        """Should return None for non-existent project."""
        result = store.get_project("proj_nonexistent")
        assert result is None
    
    def test_get_project_by_path_success(self, store, sample_project):
        """Should retrieve project by path."""
        store.store_project(sample_project)
        
        retrieved = store.get_project_by_path(sample_project.last_known_path)
        
        assert retrieved is not None
        assert retrieved.id == sample_project.id
        assert retrieved.path_hash == sample_project.path_hash
    
    def test_get_project_by_path_not_found(self, store):
        """Should return None for non-existent path."""
        result = store.get_project_by_path("/nonexistent/path")
        assert result is None
    
    def test_project_path_hash_consistency(self, store):
        """Same path should always produce same hash."""
        path = "/consistent/test/path"
        
        project1 = Project.from_path(path)
        project2 = Project.from_path(path)
        
        store.store_project(project1)
        retrieved = store.get_project_by_path(path)
        
        assert retrieved.path_hash == project1.path_hash
        assert retrieved.path_hash == project2.path_hash


# =============================================================================
# Memory Operations Tests
# =============================================================================

class TestMemoryOperations:
    """Tests for memory CRUD operations."""
    
    def test_store_memory_success(self, store, sample_user, sample_memory):
        """Should successfully store a memory."""
        # Store the user first (foreign key requirement)
        store.store_user(sample_user)
        
        result = store.store(sample_memory)
        
        assert result.id == sample_memory.id
        assert result.content == sample_memory.content
    
    def test_store_memory_with_project(self, store, sample_user, sample_project):
        """Should store project-scoped memory."""
        store.store_user(sample_user)
        store.store_project(sample_project)
        
        memory = Memory.create(
            content="Project context memory",
            memory_type=MemoryType.PROJECT_CONTEXT,
            scope=MemoryScope.PROJECT,
            user_id=sample_user.id,
            project_id=sample_project.id
        )
        
        stored = store.store(memory)
        assert stored.project_id == sample_project.id
    
    def test_get_memory_success(self, store, sample_user, sample_memory):
        """Should retrieve memory by ID."""
        store.store_user(sample_user)
        store.store(sample_memory)
        
        retrieved = store.get(sample_memory.id)
        
        assert retrieved is not None
        assert retrieved.id == sample_memory.id
        assert retrieved.content == sample_memory.content
        assert retrieved.memory_type == sample_memory.memory_type
        assert retrieved.scope == sample_memory.scope
    
    def test_get_memory_not_found(self, store):
        """Should return None for non-existent memory."""
        result = store.get("mem_nonexistent123")
        assert result is None
    
    def test_memory_json_fields_serialization(self, store, sample_user):
        """Tags and metadata should be properly serialized."""
        store.store_user(sample_user)
        
        memory = Memory.create(
            content="JSON test",
            memory_type=MemoryType.USER_PREFERENCE,
            scope=MemoryScope.USER,
            user_id=sample_user.id,
            tags=["json", "serialization", "test"],
            metadata={"nested": {"data": True}, "count": 42}
        )
        
        store.store(memory)
        retrieved = store.get(memory.id)
        
        assert retrieved.tags == ["json", "serialization", "test"]
        assert retrieved.metadata == {"nested": {"data": True}, "count": 42}
    
    def test_memory_datetime_fields(self, store, sample_user):
        """DateTime fields should be properly handled."""
        store.store_user(sample_user)
        
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        memory = Memory.create(
            content="DateTime test",
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.USER,
            user_id=sample_user.id,
            expires_at=expires_at
        )
        
        # Access the memory to set last_accessed_at
        memory.mark_accessed()
        
        store.store(memory)
        retrieved = store.get(memory.id)
        
        assert retrieved.expires_at == expires_at
        assert retrieved.last_accessed_at == memory.last_accessed_at
        assert retrieved.access_count == 1
    
    def test_memory_enum_serialization(self, store, sample_user):
        """Enum fields should be properly serialized."""
        store.store_user(sample_user)
        
        memory = Memory.create(
            content="Enum test",
            memory_type=MemoryType.LEARNED_CORRECTION,
            scope=MemoryScope.USER,
            user_id=sample_user.id
        )
        
        store.store(memory)
        retrieved = store.get(memory.id)
        
        assert retrieved.memory_type == MemoryType.LEARNED_CORRECTION
        assert retrieved.scope == MemoryScope.USER
    
    def test_delete_memory_success(self, store, sample_user, sample_memory):
        """Should successfully delete a memory."""
        store.store_user(sample_user)
        store.store(sample_memory)
        
        # Verify it exists
        assert store.get(sample_memory.id) is not None
        
        # Delete it
        result = store.delete(sample_memory.id)
        assert result is True
        
        # Verify it's gone
        assert store.get(sample_memory.id) is None
    
    def test_delete_memory_not_found(self, store):
        """Should return False when deleting non-existent memory."""
        result = store.delete("mem_nonexistent123")
        assert result is False


# =============================================================================
# Query Operations Tests
# =============================================================================

class TestQueryOperations:
    """Tests for memory query functionality."""
    
    def test_query_empty_database(self, store):
        """Query on empty database should return empty list."""
        query = MemoryQuery()
        results = store.query(query)
        assert results == []
    
    def test_query_by_user_id(self, store, sample_user):
        """Should filter memories by user ID."""
        store.store_user(sample_user)
        
        # Create user memory
        user_memory = Memory.create(
            content="User memory",
            memory_type=MemoryType.USER_PREFERENCE,
            scope=MemoryScope.USER,
            user_id=sample_user.id
        )
        store.store(user_memory)
        
        # Create global memory (different user scope)
        global_memory = Memory.create(
            content="Global memory",
            memory_type=MemoryType.TOOL_PATTERN,
            scope=MemoryScope.GLOBAL
        )
        store.store(global_memory)
        
        # Query for user memories
        query = MemoryQuery(user_id=sample_user.id)
        results = store.query(query)
        
        assert len(results) == 1
        assert results[0].id == user_memory.id
    
    def test_query_by_project_id(self, store, sample_user, sample_project):
        """Should filter memories by project ID."""
        store.store_user(sample_user)
        store.store_project(sample_project)
        
        # Create project memory
        project_memory = Memory.create(
            content="Project memory",
            memory_type=MemoryType.PROJECT_CONTEXT,
            scope=MemoryScope.PROJECT,
            user_id=sample_user.id,
            project_id=sample_project.id
        )
        store.store(project_memory)
        
        # Create user memory (different project scope)
        user_memory = Memory.create(
            content="User memory",
            memory_type=MemoryType.USER_PREFERENCE,
            scope=MemoryScope.USER,
            user_id=sample_user.id
        )
        store.store(user_memory)
        
        # Query for project memories
        query = MemoryQuery(project_id=sample_project.id)
        results = store.query(query)
        
        assert len(results) == 1
        assert results[0].id == project_memory.id
    
    def test_query_by_memory_types(self, store, sample_user):
        """Should filter memories by type."""
        store.store_user(sample_user)
        
        # Create different types of memories
        conv_memory = Memory.create(
            content="Conversation",
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.USER,
            user_id=sample_user.id
        )
        pref_memory = Memory.create(
            content="Preference",
            memory_type=MemoryType.USER_PREFERENCE,
            scope=MemoryScope.USER,
            user_id=sample_user.id
        )
        correction_memory = Memory.create(
            content="Correction",
            memory_type=MemoryType.LEARNED_CORRECTION,
            scope=MemoryScope.USER,
            user_id=sample_user.id
        )
        
        store.store(conv_memory)
        store.store(pref_memory)
        store.store(correction_memory)
        
        # Query for specific types
        query = MemoryQuery(memory_types=[MemoryType.CONVERSATION, MemoryType.USER_PREFERENCE])
        results = store.query(query)
        
        assert len(results) == 2
        memory_ids = [m.id for m in results]
        assert conv_memory.id in memory_ids
        assert pref_memory.id in memory_ids
        assert correction_memory.id not in memory_ids
    
    def test_query_by_scopes(self, store, sample_user):
        """Should filter memories by scope."""
        store.store_user(sample_user)
        
        # Create different scoped memories
        user_memory = Memory.create(
            content="User scoped",
            memory_type=MemoryType.USER_PREFERENCE,
            scope=MemoryScope.USER,
            user_id=sample_user.id
        )
        global_memory = Memory.create(
            content="Global scoped",
            memory_type=MemoryType.TOOL_PATTERN,
            scope=MemoryScope.GLOBAL
        )
        
        store.store(user_memory)
        store.store(global_memory)
        
        # Query for user scope only
        query = MemoryQuery(scopes=[MemoryScope.USER])
        results = store.query(query)
        
        assert len(results) == 1
        assert results[0].id == user_memory.id
    
    def test_query_by_retention_policies(self, store, sample_user):
        """Should filter memories by retention policy."""
        store.store_user(sample_user)
        
        # Create memories with different retention policies
        short_memory = Memory.create(
            content="Short term",
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.USER,
            user_id=sample_user.id,
        )
        short_memory.retention_policy = RetentionPolicy.SHORT_TERM
        
        long_memory = Memory.create(
            content="Long term",
            memory_type=MemoryType.USER_PREFERENCE,
            scope=MemoryScope.USER,
            user_id=sample_user.id,
        )
        long_memory.retention_policy = RetentionPolicy.LONG_TERM
        
        store.store(short_memory)
        store.store(long_memory)
        
        # Query for short term only
        query = MemoryQuery(retention_policies=[RetentionPolicy.SHORT_TERM])
        results = store.query(query)
        
        assert len(results) == 1
        assert results[0].id == short_memory.id
    
    def test_query_multiple_filters(self, store, sample_user, sample_project):
        """Should handle multiple filters together."""
        store.store_user(sample_user)
        store.store_project(sample_project)
        
        # Create memories that match various criteria
        target_memory = Memory.create(
            content="Target memory",
            memory_type=MemoryType.PROJECT_CONTEXT,
            scope=MemoryScope.PROJECT,
            user_id=sample_user.id,
            project_id=sample_project.id
        )
        
        other_memory = Memory.create(
            content="Other memory",
            memory_type=MemoryType.CONVERSATION,  # Different type
            scope=MemoryScope.PROJECT,
            user_id=sample_user.id,
            project_id=sample_project.id
        )
        
        store.store(target_memory)
        store.store(other_memory)
        
        # Query with multiple filters
        query = MemoryQuery(
            user_id=sample_user.id,
            project_id=sample_project.id,
            memory_types=[MemoryType.PROJECT_CONTEXT]
        )
        results = store.query(query)
        
        assert len(results) == 1
        assert results[0].id == target_memory.id


# =============================================================================
# Count and Bulk Operations Tests
# =============================================================================

class TestBulkOperations:
    """Tests for count, delete_by_query, and bulk operations."""
    
    def test_count_empty_database(self, store):
        """Count should return 0 for empty database."""
        assert store.count() == 0
    
    def test_count_all_memories(self, store, sample_user):
        """Should count all memories when no query provided."""
        store.store_user(sample_user)
        
        # Add multiple memories
        for i in range(5):
            memory = Memory.create(
                content=f"Memory {i}",
                memory_type=MemoryType.CONVERSATION,
                scope=MemoryScope.USER,
                user_id=sample_user.id
            )
            store.store(memory)
        
        assert store.count() == 5
    
    def test_count_with_query(self, store, sample_user):
        """Should count memories matching query filters."""
        store.store_user(sample_user)
        
        # Add different types of memories
        for i in range(3):
            conv_memory = Memory.create(
                content=f"Conversation {i}",
                memory_type=MemoryType.CONVERSATION,
                scope=MemoryScope.USER,
                user_id=sample_user.id
            )
            pref_memory = Memory.create(
                content=f"Preference {i}",
                memory_type=MemoryType.USER_PREFERENCE,
                scope=MemoryScope.USER,
                user_id=sample_user.id
            )
            store.store(conv_memory)
            store.store(pref_memory)
        
        # Count conversations only
        query = MemoryQuery(memory_types=[MemoryType.CONVERSATION])
        assert store.count(query) == 3
        
        # Count all
        assert store.count() == 6
    
    def test_delete_by_query_user(self, store, sample_user):
        """Should delete all memories for a user."""
        store.store_user(sample_user)
        
        # Create another user for comparison
        other_user = User.create("Other User")
        store.store_user(other_user)
        
        # Add memories for both users
        for user in [sample_user, other_user]:
            for i in range(3):
                memory = Memory.create(
                    content=f"Memory {i}",
                    memory_type=MemoryType.CONVERSATION,
                    scope=MemoryScope.USER,
                    user_id=user.id
                )
                store.store(memory)
        
        # Delete all memories for sample_user
        query = MemoryQuery(user_id=sample_user.id)
        deleted_count = store.delete_by_query(query)
        
        assert deleted_count == 3
        assert store.count() == 3  # Other user's memories remain
    
    def test_delete_by_query_project(self, store, sample_user, sample_project):
        """Should delete all memories for a project."""
        store.store_user(sample_user)
        store.store_project(sample_project)
        
        # Create another project
        other_project = Project.from_path("/other/project")
        store.store_project(other_project)
        
        # Add memories for both projects
        for project in [sample_project, other_project]:
            for i in range(2):
                memory = Memory.create(
                    content=f"Project memory {i}",
                    memory_type=MemoryType.PROJECT_CONTEXT,
                    scope=MemoryScope.PROJECT,
                    user_id=sample_user.id,
                    project_id=project.id
                )
                store.store(memory)
        
        # Delete all memories for sample_project
        query = MemoryQuery(project_id=sample_project.id)
        deleted_count = store.delete_by_query(query)
        
        assert deleted_count == 2
        assert store.count() == 2  # Other project's memories remain
    
    def test_clear_all_memories(self, store, sample_user):
        """clear() should delete all memories."""
        store.store_user(sample_user)
        
        # Add some memories
        for i in range(5):
            memory = Memory.create(
                content=f"Memory {i}",
                memory_type=MemoryType.CONVERSATION,
                scope=MemoryScope.USER,
                user_id=sample_user.id
            )
            store.store(memory)
        
        assert store.count() == 5
        
        deleted_count = store.clear()
        assert deleted_count == 5
        assert store.count() == 0


# =============================================================================
# Maintenance Operations Tests
# =============================================================================

class TestMaintenanceOperations:
    """Tests for cleanup and maintenance operations."""
    
    def test_delete_expired_no_expired(self, store):
        """Should return 0 when no expired memories exist."""
        deleted_count = store.delete_expired()
        assert deleted_count == 0
    
    def test_delete_expired_with_expired_memories(self, store, sample_user):
        """Should delete only expired memories."""
        store.store_user(sample_user)
        
        # Create expired memory
        expired_memory = Memory.create(
            content="Expired memory",
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.USER,
            user_id=sample_user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        
        # Create non-expired memory
        active_memory = Memory.create(
            content="Active memory",
            memory_type=MemoryType.USER_PREFERENCE,
            scope=MemoryScope.USER,
            user_id=sample_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        
        # Create memory with no expiration
        permanent_memory = Memory.create(
            content="Permanent memory",
            memory_type=MemoryType.LEARNED_CORRECTION,
            scope=MemoryScope.USER,
            user_id=sample_user.id
            # No expires_at set
        )
        
        store.store(expired_memory)
        store.store(active_memory)
        store.store(permanent_memory)
        
        assert store.count() == 3
        
        # Delete expired
        deleted_count = store.delete_expired()
        assert deleted_count == 1
        assert store.count() == 2
        
        # Verify the right one was deleted
        assert store.get(expired_memory.id) is None
        assert store.get(active_memory.id) is not None
        assert store.get(permanent_memory.id) is not None
    
    def test_get_stats_empty(self, store):
        """Should return stats for empty database."""
        stats = store.get_stats()
        assert "Total Memories" in stats
        assert stats["Total Memories"] == 0
    
    def test_get_stats_with_data(self, store, sample_user):
        """Should return correct stats with data."""
        store.store_user(sample_user)
        
        # Add some memories
        for i in range(7):
            memory = Memory.create(
                content=f"Memory {i}",
                memory_type=MemoryType.CONVERSATION,
                scope=MemoryScope.USER,
                user_id=sample_user.id
            )
            store.store(memory)
        
        stats = store.get_stats()
        assert stats["Total Memories"] == 7


# =============================================================================
# Error Handling and Edge Cases
# =============================================================================

class TestErrorHandling:
    """Tests for error conditions and edge cases."""
    
    def test_store_memory_invalid_user_foreign_key(self, store, sample_memory):
        """Should handle foreign key violation gracefully."""
        # Try to store memory without storing user first
        with pytest.raises(Exception):  # SQLite will raise an integrity error
            store.store(sample_memory)
    
    def test_store_memory_invalid_project_foreign_key(self, store, sample_user):
        """Should handle foreign key violation for project."""
        store.store_user(sample_user)
        
        memory = Memory.create(
            content="Invalid project memory",
            memory_type=MemoryType.PROJECT_CONTEXT,
            scope=MemoryScope.PROJECT,
            user_id=sample_user.id,
            project_id="proj_nonexistent"  # This project doesn't exist
        )
        
        with pytest.raises(Exception):  # Foreign key constraint violation
            store.store(memory)
    
    def test_get_and_track_updates_access_count(self, store, sample_user, sample_memory):
        """get_and_track should update access statistics."""
        store.store_user(sample_user)
        store.store(sample_memory)
        
        # Get without tracking
        memory1 = store.get(sample_memory.id)
        assert memory1.access_count == 0
        
        # Get with tracking
        memory2 = store.get_and_track(sample_memory.id)
        assert memory2.access_count == 1
        
        # Get again to verify it was saved
        memory3 = store.get(sample_memory.id)
        assert memory3.access_count == 1
    
    def test_get_and_track_nonexistent_memory(self, store):
        """get_and_track should return None for non-existent memory."""
        result = store.get_and_track("mem_nonexistent")
        assert result is None


# =============================================================================
# Context Manager Tests
# =============================================================================

class TestContextManager:
    """Tests for context manager functionality."""
    
    def test_context_manager_initializes_and_closes(self, config, temp_db):
        """Should properly initialize and close when used as context manager."""
        with SQLiteMemoryStore(config, temp_db) as store:
            # Should be able to use the store
            assert store.conn is not None
            
            # Should be able to perform operations
            user = User.create("Context Test")
            store.store_user(user)
            retrieved = store.get_user(user.id)
            assert retrieved is not None
        
        # After exiting context, connection should be closed
        # Note: SQLite doesn't fail immediately on closed connections,
        # so we test this by checking if operations still work
        with pytest.raises(Exception):
            store.get_user(user.id)


# =============================================================================
# Performance and Stress Tests
# =============================================================================

class TestPerformance:
    """Basic performance tests (optional - run with pytest -v)."""
    
    def test_bulk_insert_performance(self, store, sample_user):
        """Should handle bulk inserts efficiently."""
        import time
        
        store.store_user(sample_user)
        
        # Insert 100 memories and measure time
        start_time = time.time()
        
        for i in range(100):
            memory = Memory.create(
                content=f"Performance test memory {i}",
                memory_type=MemoryType.CONVERSATION,
                scope=MemoryScope.USER,
                user_id=sample_user.id
            )
            store.store(memory)
        
        elapsed = time.time() - start_time
        
        # Should complete in reasonable time (less than 5 seconds)
        assert elapsed < 5.0
        assert store.count() == 100
    
    def test_query_performance(self, store, sample_user):
        """Should handle queries efficiently."""
        import time
        
        store.store_user(sample_user)
        
        # Insert data
        for i in range(50):
            memory = Memory.create(
                content=f"Query test memory {i}",
                memory_type=MemoryType.CONVERSATION,
                scope=MemoryScope.USER,
                user_id=sample_user.id
            )
            store.store(memory)
        
        # Test query performance
        start_time = time.time()
        
        query = MemoryQuery(user_id=sample_user.id)
        results = store.query(query)
        
        elapsed = time.time() - start_time
        
        assert len(results) == 50
        assert elapsed < 1.0  # Should be very fast for this size