"""
Tests for Memory Data Models

These tests verify that the data models:
1. Create correctly with factory methods
2. Serialize/deserialize properly (to_dict/from_dict)
3. Validate constraints (scope/ownership consistency)
4. Handle edge cases gracefully

Run with: pytest tests/memory/test_models.py -v
"""

import pytest
from datetime import datetime, timezone, timedelta

from memory.models import Memory, User, Project, MemoryQuery
from memory.config import MemoryType, MemoryScope


# =============================================================================
# User Tests
# =============================================================================

class TestUser:
    """Tests for the User model."""
    
    def test_create_generates_id(self):
        """User.create() should generate a unique ID."""
        user = User.create("Alice")
        
        assert user.id.startswith("usr_")
        assert len(user.id) == 16  # "usr_" + 12 hex chars
        assert user.name == "Alice"
    
    def test_create_sets_timestamp(self):
        """User.create() should set created_at to now."""
        before = datetime.now(timezone.utc)
        user = User.create("Bob")
        after = datetime.now(timezone.utc)
        
        assert before <= user.created_at <= after
    
    def test_unique_ids(self):
        """Each user should get a unique ID."""
        users = [User.create("Test") for _ in range(100)]
        ids = [u.id for u in users]
        
        assert len(ids) == len(set(ids))  # All unique
    
    def test_to_dict_and_back(self):
        """User should survive round-trip serialization."""
        original = User.create("Charlie")
        
        data = original.to_dict()
        restored = User.from_dict(data)
        
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.created_at == original.created_at
    
    def test_from_dict_parses_iso_datetime(self):
        """from_dict should handle ISO datetime strings."""
        data = {
            "id": "usr_test123",
            "name": "Test",
            "created_at": "2024-01-15T10:30:00+00:00"
        }
        
        user = User.from_dict(data)
        
        assert user.created_at.year == 2024
        assert user.created_at.month == 1
        assert user.created_at.day == 15
    
    def test_user_is_immutable(self):
        """User should be frozen (immutable)."""
        user = User.create("Immutable")
        
        with pytest.raises(AttributeError):
            user.name = "Changed"


# =============================================================================
# Project Tests
# =============================================================================

class TestProject:
    """Tests for the Project model."""
    
    def test_from_path_generates_id(self):
        """Project.from_path() should generate a hash-based ID."""
        project = Project.from_path("/home/user/my-project")
        
        assert project.id.startswith("proj_")
        assert len(project.id) == 17  # "proj_" + 12 hex chars
    
    def test_from_path_extracts_name(self):
        """Project name should be extracted from path."""
        project = Project.from_path("/home/user/my-awesome-project")
        
        assert project.name == "my-awesome-project"
    
    def test_from_path_handles_trailing_slash(self):
        """Should handle paths with trailing slashes."""
        project = Project.from_path("/home/user/project/")
        
        assert project.name == "project"
    
    def test_same_path_same_hash(self):
        """Same path should always produce same hash."""
        path = "/consistent/path"
        
        project1 = Project.from_path(path)
        project2 = Project.from_path(path)
        
        assert project1.path_hash == project2.path_hash
        assert project1.id == project2.id
    
    def test_different_paths_different_hashes(self):
        """Different paths should produce different hashes."""
        project1 = Project.from_path("/path/one")
        project2 = Project.from_path("/path/two")
        
        assert project1.path_hash != project2.path_hash
    
    def test_to_dict_and_back(self):
        """Project should survive round-trip serialization."""
        original = Project.from_path("/test/project")
        
        data = original.to_dict()
        restored = Project.from_dict(data)
        
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.path_hash == original.path_hash
        assert restored.last_known_path == original.last_known_path
    
    def test_project_is_immutable(self):
        """Project should be frozen (immutable)."""
        project = Project.from_path("/test")
        
        with pytest.raises(AttributeError):
            project.name = "Changed"


# =============================================================================
# Memory Tests
# =============================================================================

class TestMemory:
    """Tests for the Memory model."""
    
    def test_create_generates_id(self):
        """Memory.create() should generate a unique ID."""
        memory = Memory.create(
            content="Test content",
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.USER,
            user_id="usr_test123"
        )
        
        assert memory.id.startswith("mem_")
        assert len(memory.id) == 20  # "mem_" + 16 hex chars
    
    def test_create_sets_timestamps(self):
        """Memory.create() should set created_at and updated_at."""
        before = datetime.now(timezone.utc)
        memory = Memory.create(
            content="Test",
            memory_type=MemoryType.USER_PREFERENCE,
            scope=MemoryScope.USER,
            user_id="usr_test"
        )
        after = datetime.now(timezone.utc)
        
        assert before <= memory.created_at <= after
        assert before <= memory.updated_at <= after
    
    def test_create_with_all_options(self):
        """Memory.create() should accept all optional parameters."""
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        
        memory = Memory.create(
            content="Full featured memory",
            memory_type=MemoryType.PROJECT_CONTEXT,
            scope=MemoryScope.PROJECT,
            project_id="proj_test123",
            importance=0.8,
            tags=["tag1", "tag2"],
            source="test",
            metadata={"key": "value"},
            expires_at=expires
        )
        
        assert memory.importance == 0.8
        assert memory.tags == ["tag1", "tag2"]
        assert memory.source == "test"
        assert memory.metadata == {"key": "value"}
        assert memory.expires_at == expires
    
    def test_default_importance(self):
        """Default importance should be 0.5."""
        memory = Memory.create(
            content="Test",
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.GLOBAL
        )
        
        assert memory.importance == 0.5
    
    def test_importance_validation(self):
        """Importance must be between 0.0 and 1.0."""
        with pytest.raises(ValueError, match="importance"):
            Memory.create(
                content="Test",
                memory_type=MemoryType.CONVERSATION,
                scope=MemoryScope.GLOBAL,
                importance=1.5  # Invalid
            )
        
        with pytest.raises(ValueError, match="importance"):
            Memory.create(
                content="Test",
                memory_type=MemoryType.CONVERSATION,
                scope=MemoryScope.GLOBAL,
                importance=-0.1  # Invalid
            )
    
    def test_user_scope_requires_user_id(self):
        """USER-scoped memories must have a user_id."""
        with pytest.raises(ValueError, match="user_id"):
            Memory.create(
                content="Test",
                memory_type=MemoryType.USER_PREFERENCE,
                scope=MemoryScope.USER,
                # Missing user_id!
            )
    
    def test_project_scope_requires_project_id(self):
        """PROJECT-scoped memories must have a project_id."""
        with pytest.raises(ValueError, match="project_id"):
            Memory.create(
                content="Test",
                memory_type=MemoryType.PROJECT_CONTEXT,
                scope=MemoryScope.PROJECT,
                # Missing project_id!
            )
    
    def test_global_scope_no_requirements(self):
        """GLOBAL-scoped memories don't require user or project."""
        memory = Memory.create(
            content="Global knowledge",
            memory_type=MemoryType.TOOL_PATTERN,
            scope=MemoryScope.GLOBAL
        )
        
        assert memory.scope == MemoryScope.GLOBAL
        assert memory.user_id is None
        assert memory.project_id is None
    
    def test_mark_accessed(self):
        """mark_accessed() should update tracking fields."""
        memory = Memory.create(
            content="Test",
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.USER,
            user_id="usr_test"
        )
        
        assert memory.access_count == 0
        assert memory.last_accessed_at is None
        
        memory.mark_accessed()
        
        assert memory.access_count == 1
        assert memory.last_accessed_at is not None
        
        memory.mark_accessed()
        
        assert memory.access_count == 2
    
    def test_update_content(self):
        """update_content() should update content and timestamp."""
        memory = Memory.create(
            content="Original",
            memory_type=MemoryType.USER_PREFERENCE,
            scope=MemoryScope.USER,
            user_id="usr_test"
        )
        original_updated = memory.updated_at
        
        # Small delay to ensure timestamp changes
        import time
        time.sleep(0.01)
        
        memory.update_content("Updated content")
        
        assert memory.content == "Updated content"
        assert memory.updated_at > original_updated
    
    def test_is_expired(self):
        """is_expired() should correctly check expiration."""
        # Not expired (no expiration set)
        memory1 = Memory.create(
            content="Test",
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.GLOBAL
        )
        assert memory1.is_expired() is False
        
        # Not expired (future date)
        memory2 = Memory.create(
            content="Test",
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.GLOBAL,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1)
        )
        assert memory2.is_expired() is False
        
        # Expired (past date)
        memory3 = Memory.create(
            content="Test",
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.GLOBAL,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        assert memory3.is_expired() is True
    
    def test_to_dict_serializes_enums(self):
        """to_dict() should convert enums to their string values."""
        memory = Memory.create(
            content="Test",
            memory_type=MemoryType.USER_PREFERENCE,
            scope=MemoryScope.USER,
            user_id="usr_test"
        )
        
        data = memory.to_dict()
        
        assert data["memory_type"] == "user_preference"
        assert data["scope"] == "user"
    
    def test_to_dict_and_back(self):
        """Memory should survive round-trip serialization."""
        original = Memory.create(
            content="Serialization test",
            memory_type=MemoryType.PROJECT_CONTEXT,
            scope=MemoryScope.PROJECT,
            project_id="proj_test",
            importance=0.7,
            tags=["test", "serialization"],
            source="unit_test",
            metadata={"nested": {"data": True}},
            expires_at=datetime.now(timezone.utc) + timedelta(days=30)
        )
        original.mark_accessed()  # Set access tracking
        
        data = original.to_dict()
        restored = Memory.from_dict(data)
        
        assert restored.id == original.id
        assert restored.content == original.content
        assert restored.memory_type == original.memory_type
        assert restored.scope == original.scope
        assert restored.project_id == original.project_id
        assert restored.importance == original.importance
        assert restored.tags == original.tags
        assert restored.source == original.source
        assert restored.metadata == original.metadata
        assert restored.access_count == original.access_count
    
    def test_repr(self):
        """__repr__ should be readable."""
        memory = Memory.create(
            content="A" * 100,  # Long content
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.GLOBAL
        )
        
        repr_str = repr(memory)
        
        assert "Memory(" in repr_str
        assert "conversation" in repr_str
        assert "..." in repr_str  # Truncated content


# =============================================================================
# MemoryQuery Tests
# =============================================================================

class TestMemoryQuery:
    """Tests for the MemoryQuery model."""
    
    def test_default_values(self):
        """Query should have sensible defaults."""
        query = MemoryQuery()
        
        assert query.limit == 100
        assert query.offset == 0
        assert query.order_by == "created_at"
        assert query.order_desc is True
        assert query.include_expired is False
    
    def test_all_filters_optional(self):
        """All filter fields should be optional."""
        query = MemoryQuery()
        
        assert query.user_id is None
        assert query.project_id is None
        assert query.memory_types is None
        assert query.scopes is None
        assert query.tags is None
    
    def test_filter_by_user(self):
        """Should support filtering by user."""
        query = MemoryQuery(user_id="usr_abc123")
        
        assert query.user_id == "usr_abc123"
    
    def test_filter_by_types(self):
        """Should support filtering by multiple types."""
        query = MemoryQuery(
            memory_types=[MemoryType.CONVERSATION, MemoryType.USER_PREFERENCE]
        )
        
        assert len(query.memory_types) == 2
    
    def test_filter_by_time_range(self):
        """Should support time-based filtering."""
        start = datetime.now(timezone.utc) - timedelta(days=7)
        end = datetime.now(timezone.utc)
        
        query = MemoryQuery(
            created_after=start,
            created_before=end
        )
        
        assert query.created_after == start
        assert query.created_before == end