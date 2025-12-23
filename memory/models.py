"""
Memory Data Models

This module defines the data structures for memories stored by the agent.
These models are storage-agnostic - they work with any backend.

Design principles:
- Immutable where possible (use frozen dataclasses)
- Type-safe with full annotations
- Serializable to/from dict for storage flexibility
- Clear separation between required and optional fields

The models follow a hierarchy:
- Memory: The core unit of stored information
- User: Identifies who the memory belongs to
- Project: Identifies which project context the memory is associated with
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Any
from enum import Enum
import uuid

# Import our enums from config to maintain single source of truth
from memory.config import MemoryType, MemoryScope, RetentionPolicy


# =============================================================================
# Identity Models
# =============================================================================

@dataclass(frozen=True)
class User:
    """
    Represents a user of the agent.
    
    Frozen (immutable) because user identity shouldn't change mid-operation.
    
    Attributes:
        id: Stable UUID for database references
        name: Human-readable display name
        created_at: When this user was first seen
    
    Example:
        >>> user = User.create("Alice")
        >>> print(user.id)  # "usr_a1b2c3d4..."
        >>> print(user.name)  # "Alice"
    """
    id: str
    name: str
    created_at: datetime
    
    @classmethod
    def create(cls, name: str) -> "User":
        """
        Factory method to create a new user with generated ID.
        
        Args:
            name: Display name for the user
            
        Returns:
            New User instance with UUID and current timestamp
        """
        return cls(
            id=f"usr_{uuid.uuid4().hex[:12]}",
            name=name,
            created_at=datetime.now(timezone.utc)
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User":
        """Reconstruct from dictionary."""
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            id=data["id"],
            name=data["name"],
            created_at=created_at
        )


@dataclass(frozen=True)
class Project:
    """
    Represents a project/codebase the agent is working on.
    
    The project is identified by a hash of its absolute path, making it
    portable across machines while still being unique.
    
    Attributes:
        id: Stable identifier (hash-based), e.g., "proj_a1b2c3d4"
        name: Human-readable name (usually directory name)
        path_hash: SHA256 hash of absolute path for matching
        last_known_path: The actual path (for display/debugging only)
        created_at: When this project was first seen
    
    Example:
        >>> project = Project.from_path("/home/user/my-project")
        >>> print(project.name)  # "my-project"
    """
    id: str
    name: str
    path_hash: str
    last_known_path: str
    created_at: datetime
    
    @classmethod
    def from_path(cls, absolute_path: str, hasher=None) -> "Project":
        """
        Factory method to create a project from its path.
        
        Args:
            absolute_path: The absolute path to the project directory
            hasher: Optional hash function (for testing). Defaults to SHA256.
            
        Returns:
            New Project instance
        """
        import hashlib
        import os
        
        # Use provided hasher or default to SHA256
        if hasher is None:
            path_hash = hashlib.sha256(absolute_path.encode()).hexdigest()
        else:
            path_hash = hasher(absolute_path)
        
        # Extract directory name for human-readable name
        name = os.path.basename(absolute_path.rstrip("/\\")) or "root"
        
        return cls(
            id=f"proj_{path_hash[:12]}",
            name=name,
            path_hash=path_hash,
            last_known_path=absolute_path,
            created_at=datetime.now(timezone.utc)
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "path_hash": self.path_hash,
            "last_known_path": self.last_known_path,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        """Reconstruct from dictionary."""
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            id=data["id"],
            name=data["name"],
            path_hash=data["path_hash"],
            last_known_path=data["last_known_path"],
            created_at=created_at
        )


# =============================================================================
# Core Memory Model
# =============================================================================

@dataclass
class Memory:
    """
    The core unit of stored information.
    
    A Memory represents a single piece of information the agent should
    remember, such as a conversation exchange, user preference, or
    learned correction.
    
    Not frozen because we may need to update metadata (like access_count).
    
    Attributes:
        id: Unique identifier for this memory
        content: The actual information to remember (sanitized!)
        memory_type: Category of memory (conversation, preference, etc.)
        scope: Visibility scope (user, project, global)
        
        # Ownership
        user_id: Optional user this memory belongs to
        project_id: Optional project this memory is associated with
        
        # Metadata
        created_at: When the memory was created
        updated_at: When the memory was last modified
        expires_at: When this memory should be auto-deleted (None = never)
        
        # Retrieval helpers
        importance: Priority score (0.0 to 1.0) for retrieval ranking
        access_count: How many times this memory has been retrieved
        last_accessed_at: When this memory was last retrieved
        
        # Content metadata
        tags: Optional tags for categorization/filtering
        source: Where this memory came from (e.g., "conversation", "tool_result")
        metadata: Additional structured data (flexible JSON-like dict)
    
    Example:
        >>> memory = Memory.create(
        ...     content="User prefers verbose explanations",
        ...     memory_type=MemoryType.USER_PREFERENCE,
        ...     scope=MemoryScope.USER,
        ...     user_id="usr_abc123"
        ... )
    """
    # Core fields
    id: str
    content: str
    memory_type: MemoryType
    scope: MemoryScope
    retention_policy: RetentionPolicy = RetentionPolicy.SHORT_TERM # Default value
    
    # Ownership (at least one should be set based on scope)
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    
    # Retrieval metadata
    importance: float = 0.5  # Default to medium importance
    access_count: int = 0
    last_accessed_at: Optional[datetime] = None
    
    # Content metadata
    tags: list[str] = field(default_factory=list)
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate the memory after creation."""
        # Validate importance is in range
        if not 0.0 <= self.importance <= 1.0:
            raise ValueError(f"importance must be between 0.0 and 1.0, got {self.importance}")
        
        # Validate scope/ownership consistency
        if self.scope == MemoryScope.USER and not self.user_id:
            raise ValueError("USER-scoped memories must have a user_id")
        if self.scope == MemoryScope.PROJECT and not self.project_id:
            raise ValueError("PROJECT-scoped memories must have a project_id")
    
    @classmethod
    def create(
        cls,
        content: str,
        memory_type: MemoryType,
        scope: MemoryScope,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        importance: float = 0.5,
        tags: Optional[list[str]] = None,
        source: str = "unknown",
        metadata: Optional[dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
    ) -> "Memory":
        """
        Factory method to create a new memory with generated ID.
        
        Args:
            content: The information to remember
            memory_type: Category of memory
            scope: Visibility scope
            user_id: Owner user (required for USER scope)
            project_id: Associated project (required for PROJECT scope)
            importance: Priority score 0.0-1.0
            tags: Optional categorization tags
            source: Origin of this memory
            metadata: Additional structured data
            expires_at: When to auto-delete (None = use retention policy)
            
        Returns:
            New Memory instance
        """
        now = datetime.now(timezone.utc)
        return cls(
            id=f"mem_{uuid.uuid4().hex[:16]}",
            content=content,
            memory_type=memory_type,
            scope=scope,
            user_id=user_id,
            project_id=project_id,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            importance=importance,
            access_count=0,
            last_accessed_at=None,
            tags=tags or [],
            source=source,
            metadata=metadata or {},
        )
    
    def mark_accessed(self) -> None:
        """Update access tracking when this memory is retrieved."""
        self.access_count += 1
        self.last_accessed_at = datetime.now(timezone.utc)
    
    def update_content(self, new_content: str) -> None:
        """Update the memory's content and timestamp."""
        self.content = new_content
        self.updated_at = datetime.now(timezone.utc)
    
    def is_expired(self) -> bool:
        """Check if this memory has passed its expiration date."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for storage.
        
        Handles enum serialization and datetime ISO formatting.
        """
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "scope": self.scope.value,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            "tags": self.tags,
            "source": self.source,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Memory":
        """
        Reconstruct from dictionary.
        
        Handles enum deserialization and datetime parsing.
        """
        def parse_datetime(value: Any) -> Optional[datetime]:
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(value)
        
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            scope=MemoryScope(data["scope"]),
            user_id=data.get("user_id"),
            project_id=data.get("project_id"),
            created_at=parse_datetime(data["created_at"]) or datetime.now(timezone.utc),
            updated_at=parse_datetime(data["updated_at"]) or datetime.now(timezone.utc),
            expires_at=parse_datetime(data.get("expires_at")),
            importance=data.get("importance", 0.5),
            access_count=data.get("access_count", 0),
            last_accessed_at=parse_datetime(data.get("last_accessed_at")),
            tags=data.get("tags", []),
            source=data.get("source", "unknown"),
            metadata=data.get("metadata", {}),
        )
    
    def __repr__(self) -> str:
        """Readable representation for debugging."""
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return (
            f"Memory(id={self.id!r}, type={self.memory_type.value}, "
            f"scope={self.scope.value}, content={content_preview!r})"
        )


# =============================================================================
# Query/Filter Models
# =============================================================================

@dataclass
class MemoryQuery:
    """
    Represents a query for retrieving memories.
    
    All fields are optional - unset fields mean "don't filter by this".
    This allows for flexible querying like:
    - Get all memories for a user
    - Get project memories of a specific type
    - Get recent memories across all scopes
    
    Example:
        >>> query = MemoryQuery(
        ...     user_id="usr_abc123",
        ...     memory_types=[MemoryType.USER_PREFERENCE],
        ...     limit=10
        ... )
    """
    # Filter by ownership
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    
    # Filter by type/scope
    memory_types: Optional[list[MemoryType]] = None
    scopes: Optional[list[MemoryScope]] = None
    retention_policies: Optional[list[RetentionPolicy]] = None
    
    # Filter by content
    tags: Optional[list[str]] = None  # Match ANY of these tags
    source: Optional[str] = None
    
    # Filter by time
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    
    # Filter expired
    include_expired: bool = False
    
    # Result control
    limit: int = 100
    offset: int = 0
    
    # Ordering
    order_by: str = "created_at"  # created_at, updated_at, importance, access_count
    order_desc: bool = True  # True = newest/highest first