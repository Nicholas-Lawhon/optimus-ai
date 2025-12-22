"""
Abstract Memory Storage Interface

This module defines the contract that all storage backends must implement.
By coding to this interface, the rest of the application is decoupled
from the specific storage technology.

Design principles:
- All methods that can fail should return Optional or raise specific exceptions
- Async-ready design (can be extended to async in future)
- Clear documentation of expected behavior
- Type hints for all parameters and returns

Implementing a new backend:
1. Create a class that inherits from MemoryStore
2. Implement all abstract methods
3. Register it in the factory (stores/__init__.py)

Example:
    class PostgresMemoryStore(MemoryStore):
        def store(self, memory: Memory) -> Memory:
            # Implementation here
            ...
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

from memory.models import Memory, User, Project, MemoryQuery
from memory.config import MemoryType, MemoryScope


class MemoryStoreError(Exception):
    """Base exception for storage errors."""
    pass


class MemoryNotFoundError(MemoryStoreError):
    """Raised when a requested memory doesn't exist."""
    pass


class StorageConnectionError(MemoryStoreError):
    """Raised when the storage backend is unreachable."""
    pass


class StorageCapacityError(MemoryStoreError):
    """Raised when storage limits are exceeded."""
    pass


class MemoryStore(ABC):
    """
    Abstract base class for memory storage backends.
    
    This interface defines all operations that a storage backend must support.
    Implementations might include SQLite, PostgreSQL, Redis, ChromaDB, etc.
    
    Thread Safety:
        Implementations should be thread-safe for concurrent access.
        
    Transaction Support:
        Implementations may optionally support transactions via context manager.
    
    Example usage:
        store = SQLiteMemoryStore("./data/memory.db")
        
        # Store a memory
        memory = Memory.create(
            content="User prefers Python",
            memory_type=MemoryType.USER_PREFERENCE,
            scope=MemoryScope.USER,
            user_id="usr_123"
        )
        stored = store.store(memory)
        
        # Retrieve memories
        query = MemoryQuery(user_id="usr_123", limit=10)
        memories = store.query(query)
        
        # Clean up
        store.close()
    """
    
    # =========================================================================
    # Lifecycle Methods
    # =========================================================================
    
    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the storage backend.
        
        This should:
        - Create necessary tables/collections if they don't exist
        - Verify the schema is up to date
        - Establish connections if needed
        
        Raises:
            StorageConnectionError: If the backend is unreachable
            MemoryStoreError: For other initialization failures
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """
        Clean up resources and close connections.
        
        This should be called when the application shuts down.
        After calling close(), the store should not be used.
        """
        pass
    
    def __enter__(self) -> "MemoryStore":
        """Context manager entry - initialize the store."""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close the store."""
        self.close()
    
    # =========================================================================
    # Memory CRUD Operations
    # =========================================================================
    
    @abstractmethod
    def store(self, memory: Memory) -> Memory:
        """
        Store a new memory or update an existing one.
        
        If a memory with the same ID exists, it should be updated.
        If it doesn't exist, it should be created.
        
        Args:
            memory: The memory to store (should already be sanitized!)
            
        Returns:
            The stored memory (may have updated timestamps)
            
        Raises:
            StorageCapacityError: If storage limits are exceeded
            MemoryStoreError: For other storage failures
        """
        pass
    
    @abstractmethod
    def get(self, memory_id: str) -> Optional[Memory]:
        """
        Retrieve a single memory by ID.
        
        Args:
            memory_id: The unique identifier of the memory
            
        Returns:
            The memory if found, None otherwise
            
        Note:
            This should NOT update access tracking. Use get_and_track()
            if you want to record the access.
        """
        pass
    
    def get_and_track(self, memory_id: str) -> Optional[Memory]:
        """
        Retrieve a memory and update its access tracking.
        
        This is the preferred method for retrieval when building
        context for the LLM, as it helps with relevance ranking.
        
        Args:
            memory_id: The unique identifier of the memory
            
        Returns:
            The memory if found (with updated access_count), None otherwise
        """
        memory = self.get(memory_id)
        if memory:
            memory.mark_accessed()
            self.store(memory)  # Save updated access tracking
        return memory
    
    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """
        Delete a memory by ID.
        
        Args:
            memory_id: The unique identifier of the memory to delete
            
        Returns:
            True if the memory was deleted, False if it didn't exist
        """
        pass
    
    @abstractmethod
    def query(self, query: MemoryQuery) -> list[Memory]:
        """
        Query memories based on filters.
        
        Args:
            query: A MemoryQuery object specifying filters and options
            
        Returns:
            List of matching memories (may be empty)
            
        Note:
            Results are ordered according to query.order_by and query.order_desc
        """
        pass
    
    # =========================================================================
    # User Operations
    # =========================================================================
    
    @abstractmethod
    def store_user(self, user: User) -> User:
        """
        Store a new user or update an existing one.
        
        Args:
            user: The user to store
            
        Returns:
            The stored user
        """
        pass
    
    @abstractmethod
    def get_user(self, user_id: str) -> Optional[User]:
        """
        Retrieve a user by ID.
        
        Args:
            user_id: The unique identifier of the user
            
        Returns:
            The user if found, None otherwise
        """
        pass
    
    @abstractmethod
    def get_user_by_name(self, name: str) -> Optional[User]:
        """
        Retrieve a user by their display name.
        
        Args:
            name: The display name to search for
            
        Returns:
            The user if found, None otherwise
            
        Note:
            If multiple users have the same name, returns the first one.
            Consider using get_user() with ID for precise lookups.
        """
        pass
    
    # =========================================================================
    # Project Operations
    # =========================================================================
    
    @abstractmethod
    def store_project(self, project: Project) -> Project:
        """
        Store a new project or update an existing one.
        
        Args:
            project: The project to store
            
        Returns:
            The stored project
        """
        pass
    
    @abstractmethod
    def get_project(self, project_id: str) -> Optional[Project]:
        """
        Retrieve a project by ID.
        
        Args:
            project_id: The unique identifier of the project
            
        Returns:
            The project if found, None otherwise
        """
        pass
    
    @abstractmethod
    def get_project_by_path(self, absolute_path: str) -> Optional[Project]:
        """
        Retrieve a project by its path.
        
        This uses the path hash for matching, so it works even if
        the path was registered from a different machine.
        
        Args:
            absolute_path: The absolute path to the project directory
            
        Returns:
            The project if found, None otherwise
        """
        pass
    
    # =========================================================================
    # Bulk Operations
    # =========================================================================
    
    @abstractmethod
    def delete_by_query(self, query: MemoryQuery) -> int:
        """
        Delete all memories matching a query.
        
        This is useful for bulk cleanup operations like:
        - Deleting all memories for a user
        - Clearing expired memories
        - Removing all memories of a certain type
        
        Args:
            query: A MemoryQuery specifying which memories to delete
            
        Returns:
            The number of memories deleted
        """
        pass
    
    @abstractmethod
    def count(self, query: Optional[MemoryQuery] = None) -> int:
        """
        Count memories matching a query.
        
        Args:
            query: Optional query filters. If None, counts all memories.
            
        Returns:
            The count of matching memories
        """
        pass
    
    # =========================================================================
    # Maintenance Operations
    # =========================================================================
    
    @abstractmethod
    def delete_expired(self) -> int:
        """
        Delete all memories that have passed their expiration date.
        
        This should be called periodically (e.g., on startup, daily).
        
        Returns:
            The number of expired memories deleted
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> dict:
        """
        Get storage statistics.
        
        Returns:
            Dictionary with stats like:
            - total_memories: int
            - memories_by_type: dict[str, int]
            - memories_by_scope: dict[str, int]
            - oldest_memory: datetime
            - newest_memory: datetime
            - storage_size_bytes: int (if available)
        """
        pass
    
    # =========================================================================
    # Optional: Semantic Search (for vector DB implementations)
    # =========================================================================
    
    def search_similar(
        self, 
        query_text: str, 
        limit: int = 10,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> list[tuple[Memory, float]]:
        """
        Search for semantically similar memories.
        
        This is optional - only vector DB backends (ChromaDB, Pinecone)
        need to implement this. Default implementation returns empty list.
        
        Args:
            query_text: The text to find similar memories for
            limit: Maximum number of results
            user_id: Optional filter by user
            project_id: Optional filter by project
            
        Returns:
            List of (memory, similarity_score) tuples, highest score first
        """
        # Default implementation for non-vector stores
        return []
    
    def supports_semantic_search(self) -> bool:
        """
        Check if this store supports semantic/vector search.
        
        Returns:
            True if search_similar() is implemented, False otherwise
        """
        return False