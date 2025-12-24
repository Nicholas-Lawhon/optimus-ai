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
from dataclasses import replace
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
        store = SQLiteMemoryStore(config, config.storage_path or "memory.db")
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
        
    def add_user_tag(self, tag: str) -> User:
        """
        Add a tag to the current user using the copy-on-write pattern.
        
        Since User objects are immutable (frozen), we create a new instance
        with the updated tag list, store it, and update the current session.
        """
        # 1. Check if tag already exists to avoid redundant writes
        if tag in self.current_user.tags:
            return self.current_user
            
        # 2. Create new tags list (User is frozen, so we make a new list)
        new_tags = self.current_user.tags + [tag]
        
        # 3. Use 'replace' to create a new User instance with updated tags
        updated_user = replace(self.current_user, tags=new_tags)
        
        # 4. Persist the new version to the database
        self.store.store_user(updated_user)
        
        # 5. Update our current session reference
        self._current_user = updated_user
        
        return updated_user
    
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
        
    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _create_and_store(
        self,
        content: str,
        memory_type: MemoryType,
        scope: MemoryScope,
        importance: float,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Memory:
        """
        Internal helper to centralize memory creation logic.
        
        Handles:
        - Content sanitization (SECURITY)
        - ID resolution (User/Project)
        - Expiration calculation
        - Object creation and storage
        """
        # Sanitize content to prevent secret leakage
        sanitization_result = self.safety.sanitize_content(content)
        sanitized_content = sanitization_result.content
        
        # Determine ownership based on current context
        # Always attach user_id if we have a current user
        user_id = self.current_user.id if self.current_user else None
        
        # Attach project_id if we have a current project
        # (Even for USER scope, it's useful to know where it happened)
        project_id = self.current_project.id if self.current_project else None
        
        # Calculate expiration based on retention policy
        ttl = self.config.retention.get_ttl(memory_type)
        expires_at = datetime.now(timezone.utc) + ttl
        
        # Determine the RetentionPolicy label based on type
        policy_map = {
            MemoryType.USER_PREFERENCE: RetentionPolicy.LONG_TERM,
            MemoryType.LEARNED_CORRECTION: RetentionPolicy.LONG_TERM,
            MemoryType.PROJECT_CONTEXT: RetentionPolicy.MEDIUM_TERM,
            MemoryType.TOOL_PATTERN: RetentionPolicy.MEDIUM_TERM,
            MemoryType.TASK_RESULT: RetentionPolicy.SHORT_TERM,
            MemoryType.CONVERSATION: RetentionPolicy.SHORT_TERM,
        }
        policy = policy_map.get(memory_type, RetentionPolicy.SHORT_TERM)
        
        # Create the memory object
        memory = Memory.create(
            content=sanitized_content,
            memory_type=memory_type,
            scope=scope,
            user_id=user_id,
            project_id=project_id,
            importance=importance,
            tags=tags,
            metadata=metadata or {},
            expires_at=expires_at,
            retention_policy=policy
        )
        
        # Persist to storage
        return self.store.store(memory)
    
    # =========================================================================
    # High-Level Storage Operations
    # =========================================================================

    def store_conversation(
        self,
        user_message: str,
        assistant_response: str,
        importance: float = 0.1,
        tags: list[str] | str = "chat"
    ) -> Memory:
        """
        Store a chat exchange.
        
        Automatically determines scope:
        - PROJECT scope if a project is active
        - USER scope otherwise
        """
        # Format the interaction clearly
        content = f"User: {user_message}\nAssistant: {assistant_response}"
        
        # Determine scope based on whether we are in a project
        scope = MemoryScope.PROJECT if self.current_project else MemoryScope.USER
        
        if isinstance(tags, str):
            tags = [tags]
        
        return self._create_and_store(
            content=content,
            memory_type=MemoryType.CONVERSATION,
            scope=scope,
            importance=importance,
            tags=tags
        )
        
    def store_user_preference(
        self,
        preference: str,
        importance: float = 0.8
    ) -> Memory:
        """
        Store a user preference or fact.
        
        Always USER scope so it follows the user across projects.
        High default importance because these are explicit instructions.
        """
        return self._create_and_store(
            content=preference,
            memory_type=MemoryType.USER_PREFERENCE,
            scope=MemoryScope.USER,
            importance=importance,
            tags=["preference", "personalization"]
        )
        
    def store_project_context(
        self,
        context: str,
        importance: float = 0.5
    ) -> Memory:
        """
        Store information about the project structure or tech stack.
        """
        return self._create_and_store(
            content=context,
            memory_type=MemoryType.PROJECT_CONTEXT,
            scope=MemoryScope.PROJECT,
            importance=importance,
            tags=["context", "architecture"]
        )

    def store_learned_correction(
        self,
        original_response: str,
        correction: str,
        importance: float = 0.9  # High default!
    ) -> Memory:
        """
        Record when the user corrects the agent.
        High importance ensures it's retrieved often.
        """
        # We combine them to give the agent full context of the mistake
        content = f"Original: {original_response}\nCorrection: {correction}"
        
        return self._create_and_store(
            content=content,
            memory_type=MemoryType.LEARNED_CORRECTION,
            scope=MemoryScope.USER,
            importance=importance,
            tags=["correction", "learning"]
        )
        
    def store_tool_pattern(
        self,
        tool_name: str,
        pattern: str,
        success: bool = True,
        importance: float = 0.5
    ) -> Memory:
        """
        Record a successful tool usage pattern globally.
        
        Scope is GLOBAL because a good way to use a tool is valid 
        regardless of the user or project.
        """
        content = f"Tool: {tool_name}\nPattern: {pattern}\nResult: {'Success' if success else 'Failure'}"
        
        return self._create_and_store(
            content=content,
            memory_type=MemoryType.TOOL_PATTERN,
            scope=MemoryScope.GLOBAL,
            importance=importance,
            tags=["tool", "pattern", tool_name]
        )
        
    def get_recent_conversations(
        self, 
        limit: int = 10, 
        include_project: bool = True
    ) -> List[Memory]:
        """
        Retrieve recent chat history.
        
        Args:
            limit: Max number of messages to return
            include_project: If True, filter by current project (if active)
        """
        query_project_id = self.current_project.id if include_project and self.current_project else None
        
        query = MemoryQuery(
            user_id=self.current_user.id,
            project_id=query_project_id,
            include_no_project=True,
            memory_types=[MemoryType.CONVERSATION],
            limit=limit
        )
        
        return self.store.query(query)
    
    def get_project_context(self) -> List[Memory]:
        """
        Retrieve context for the current active project.
        Returns empty list if no project is active.
        """
        if not self.current_project:
            return []
        
        query = MemoryQuery(
            user_id=self.current_user.id,
            project_id=self.current_project.id,
            memory_types=[MemoryType.PROJECT_CONTEXT]
        )
        
        return self.store.query(query)
        
    def get_user_preferences(self) -> List[Memory]:
        """
        Retrieve all preferences for the current user.
        """
        query = MemoryQuery(
            user_id=self.current_user.id,
            memory_types=[MemoryType.USER_PREFERENCE]
        )
        
        return self.store.query(query)
    
    def get_relevant_corrections(
        self,
        limit: int = 10
    ) -> List[Memory]:
        """
        Retrieve recent corrections to prevent repeating mistakes.
        """
        query = MemoryQuery(
            user_id=self.current_user.id,
            memory_types=[MemoryType.LEARNED_CORRECTION],
            limit=limit
        )
        
        return self.store.query(query)
    
    def build_context_string(
        self,
        include_preferences: bool = True,
        include_project: bool = True,
        include_history: bool = True,
        include_corrections: bool = True,
        max_chars: Optional[int] = None
    ) -> str:
        """
        Build a context string for the LLM prompt.
        Prioritizes content in this order:
        1. Learned Corrections (Critical)
        2. User Preferences (Personalization)
        3. Project Context (Background)
        4. Conversation History (Fills remaining space)
        """
        # Resolve limit from config if not provided
        if max_chars is None:
            max_chars = self.config.limits.max_context_chars
            
        parts = []
        current_chars = 0
        
        # Helper to safely add sections (for the first 3 types)
        def add_section(header: str, items: List[Memory]):
            nonlocal current_chars
            if not items:
                return
            
            # Format: "- Content"
            section_content = "\n".join([f"- {m.content}" for m in items])
            section_text = f"\n=== {header} ===\n{section_content}\n"
            
            # Only add if it fits
            if current_chars + len(section_text) <= max_chars:
                parts.append(section_text)
                current_chars += len(section_text)
        
        # --- PHASE 1: Retrieve Data ---
        # Fetch a reasonable batch of history (e.g., 50) and let the squeezer filter it
        history = self.get_recent_conversations(limit=50) if include_history else []
        corrections = self.get_relevant_corrections() if include_corrections else []
        preferences = self.get_user_preferences() if include_preferences else []
        project_context = self.get_project_context() if include_project else []
        
        # --- PHASE 2: Assemble (Fixed Sections First) ---
        
        # 1. Corrections (High Priority)
        add_section("Learned Corrections", corrections)
        
        # 2. Preferences (High Priority)
        add_section("User Preferences", preferences)
        
        # 3. Project Context (Medium Priority - takes precedence over old history)
        add_section("Project Context", project_context)
        
        # --- PHASE 3: The "Squeeze" (History) ---
        
        if history:
            remaining_chars = max_chars - current_chars
            
            # If we have no space left, we have to skip history
            if remaining_chars < 100: # Buffer for header
                print("Warning: Context full, skipping history")
            else:
                # Temp list to hold the messages we select
                selected_history = []
                
                # Iterate through history (which is stored Newest -> Oldest)
                for mem in history:
                    # Calculate size of this memory entry (plus a little for formatting)
                    # We estimate roughly 10 chars overhead for "- " and "\n"
                    mem_size = len(mem.content) + 10
                    
                    if mem_size <= remaining_chars:
                        selected_history.append(mem)
                        remaining_chars -= mem_size
                    else:
                        # If the next newest message is too big, we stop.
                        # This prevents "gaps" in the conversation.
                        break
                    
                add_section("Conversation History", selected_history[::-1])
                
        return "".join(parts).strip()