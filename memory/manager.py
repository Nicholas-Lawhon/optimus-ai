"""
Memory Manager - High-Level Memory Orchestration

This is the main interface between the agent and the memory system.
The agent should ONLY interact with memory through this class.

Responsibilities:
- User and project lifecycle management (auto-create when needed)
- Content sanitization before storage (security!)
- Intelligent context building for prompts
- Automatic cleanup and retention enforcement

Design Pattern: Facade
- Hides the complexity of storage, safety, and models
- Provides simple, intent-based methods like store_conversation()

Usage:
    from memory.manager import MemoryManager
    
    # Initialize with defaults (uses config's default_user_id)
    memory = MemoryManager.initialize()
    
    # Or with explicit user/project
    memory = MemoryManager.initialize(
        user_name="Nick",
        project_path="/home/nick/my-project"
    )
    
    # Store conversations (content auto-sanitized)
    memory.store_conversation(
        user_message="How do I read a file?",
        assistant_response="Use open() with a context manager..."
    )
    
    # Build context for prompt injection
    context = memory.build_context_string()
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import json

from memory.config import MemoryConfig, MemoryType, MemoryScope, RetentionPolicy
from memory.models import Memory, User, Project, MemoryQuery
from memory.safety import MemorySafetyGuard
from memory.stores.base import MemoryStore
from memory.stores.sqlite import SQLiteMemoryStore


class MemoryManager:
    """
    High-level interface for agent memory operations.
    
    This class is the ONLY memory interface the agent should use.
    It coordinates between safety, storage, and the agent's needs.
    
    Thread Safety Note:
        This class is NOT thread-safe. If you need concurrent access,
        create separate instances or add locking.
    
    Attributes:
        config: The memory configuration settings
        store: The underlying storage backend
        safety: The safety guard for content sanitization
        _current_user: The active user (lazy-loaded)
        _current_project: The active project (may be None)
    """
    
    def __init__(
        self,
        config: MemoryConfig,
        store: MemoryStore,
        safety_guard: MemorySafetyGuard,
        current_user: Optional[User] = None,
        current_project: Optional[Project] = None,
    ):
        """
        Direct constructor - prefer using initialize() class method.
        
        This constructor expects all dependencies to be pre-configured.
        For typical usage, use the initialize() factory method instead.
        
        Args:
            config: Memory configuration settings
            store: Initialized storage backend
            safety_guard: Safety guard for content sanitization
            current_user: Pre-loaded user (optional, lazy-loads if None)
            current_project: Pre-loaded project (optional)
        """
        self.config = config
        self.store = store
        self.safety = safety_guard
        
        # These use underscore prefix because we have @property accessors
        # that handle lazy loading
        self._current_user: Optional[User] = current_user
        self._current_project: Optional[Project] = current_project
        
        # Track if we own the store (for cleanup)
        # If someone passes their own store, we shouldn't close it
        self._owns_store: bool = False
        
    @classmethod
    def initialize(
        cls,
        config: Optional[MemoryConfig] = None,
        user_name: Optional[str] = None,
        project_path: Optional[str] = None,
    ) -> "MemoryManager":
        """
        Factory method to create a fully configured MemoryManager.
        
        This is the preferred way to create a MemoryManager instance.
        It handles all setup complexity:
        - Creates config with smart defaults if not provided
        - Initializes the storage backend
        - Sets up the safety guard
        - Optionally loads/creates user and project
        
        Args:
            config: Memory configuration. If None, uses defaults.
            user_name: User's display name. If None, uses config default.
            project_path: Absolute path to project directory. Optional.
        
        Returns:
            Fully initialized MemoryManager ready for use.
        
        Example:
            # Minimal setup (uses all defaults)
            memory = MemoryManager.initialize()
            
            # With specific user
            memory = MemoryManager.initialize(user_name="Nick")
            
            # With user and project
            memory = MemoryManager.initialize(
                user_name="Nick",
                project_path="/home/nick/optimus-ai"
            )
        """
        # Step 1: Use provided config or create default
        if config is None:
            config = MemoryConfig()
        
        # Step 2: Create and initialize the storage backend
        # Note: config.storage_path is already resolved by MemoryConfig.__post_init__
        store = SQLiteMemoryStore(config, config.storage_path)
        store.initialize()
        
        # Step 3: Create the safety guard using config's safety settings
        safety_guard = MemorySafetyGuard(config.safety)
        
        # Step 4: Create the manager instance
        manager = cls(
            config=config,
            store=store,
            safety_guard=safety_guard,
            current_user=None,  # Will be lazy-loaded
            current_project=None,
        )
        
        # Mark that we own the store (so we close it in cleanup)
        manager._owns_store = True
        
        # Step 5: Set up user if name provided, otherwise defer to lazy loading
        if user_name:
            user = manager.get_or_create_user(user_name)
            manager._current_user = user
        
        # Step 6: Set up project if path provided
        if project_path:
            project = manager.get_or_create_project(project_path)
            manager._current_project = project
        
        return manager
    
    # =========================================================================
    # User Management
    # =========================================================================
    
    def get_or_create_user(self, name: str) -> User:
        """
        Get an existing user by name, or create a new one.
        
        This is the primary method for user management. It ensures
        idempotent behavior - calling multiple times with the same
        name always returns the same user.
        
        Args:
            name: The user's display name
            
        Returns:
            The User object (existing or newly created)
        """
        # Try to find existing user by name
        existing_user = self.store.get_user_by_name(name)
        
        if existing_user:
            return existing_user
        
        # Create new user
        new_user = User.create(name)
        self.store.store_user(new_user)
        
        return new_user
    
    def set_current_user(self, user: User) -> None:
        """
        Set the active user for subsequent operations.
        
        All user-scoped memory operations will use this user.
        
        Args:
            user: The User object to set as current
        """
        self._current_user = user
    
    @property
    def current_user(self) -> User:
        """
        Get the current active user.
        
        If no user has been set, creates/loads the default user
        from config.default_user_id.
        
        Returns:
            The current User object
            
        Note:
            This property is lazy-loading. The default user is only
            created when first accessed.
        """
        if self._current_user is None:
            # Lazy load: create/get default user from config
            default_name = self.config.default_user_id
            self._current_user = self.get_or_create_user(default_name)
        
        return self._current_user
    
    # =========================================================================
    # Project Management
    # =========================================================================
    
    def get_or_create_project(self, path: str) -> Project:
        """
        Get an existing project by path, or create a new one.
        
        Projects are identified by a hash of their absolute path,
        making them portable across machines while remaining unique.
        
        Args:
            path: Absolute path to the project directory
            
        Returns:
            The Project object (existing or newly created)
        """
        # Try to find existing project by path hash
        existing_project = self.store.get_project_by_path(path)
        
        if existing_project:
            return existing_project
        
        # Create new project
        new_project = Project.from_path(path)
        self.store.store_project(new_project)
        
        return new_project
    
    def set_current_project(self, project: Optional[Project]) -> None:
        """
        Set the active project for subsequent operations.
        
        All project-scoped memory operations will use this project.
        Can be set to None to clear project context.
        
        Args:
            project: The Project object to set, or None to clear
        """
        self._current_project = project
    
    @property
    def current_project(self) -> Optional[Project]:
        """
        Get the current active project.
        
        Unlike current_user, this can be None - not all agent
        sessions are tied to a specific project.
        
        Returns:
            The current Project object, or None if not set
        """
        return self._current_project
    
    # =========================================================================
    # Lifecycle
    # =========================================================================
    
    def close(self) -> None:
        """
        Close the memory manager and release resources.
        
        Only closes the store if we created it (via initialize()).
        """
        if self._owns_store and self.store:
            self.store.close()
    
    def __enter__(self) -> "MemoryManager":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()