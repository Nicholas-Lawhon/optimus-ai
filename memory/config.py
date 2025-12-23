"""
Enhanced Memory System Configuration with Smart Path Resolution

This module defines all configurable aspects of the memory system with added support for intelligent database path resolution following platform conventions.

New Features:
- Platform-specific user data directories
- Environment variable overrides
- Automatic directory creation
- Fallback handling for edge cases

SAFETY NOTE: This configuration controls security-sensitive features.
Review carefully before changing defaults.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import timedelta
import os
from pathlib import Path


class MemoryScope(Enum):
    """
    Defines the visibility/scope of a memory.
    
    - USER: Tied to a specific user, visible across all their projects
    - PROJECT: Tied to a specific project directory, visible to all users of that project
    - GLOBAL: Visible to all users and projects (use sparingly!)
    """
    USER = "user"
    PROJECT = "project"
    GLOBAL = "global"


class RetentionPolicy(Enum):
    """
    Defines how long memories are kept before automatic cleanup.
    
    - SESSION: Deleted when the session ends (not persisted)
    - SHORT_TERM: Days to weeks
    - MEDIUM_TERM: Weeks to months  
    - LONG_TERM: Months to a year
    - PERMANENT: Never auto-deleted (requires manual deletion)
    """
    SESSION = "session"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    PERMANENT = "permanent"


class MemoryType(Enum):
    """
    Categories of memories the agent can store.
    Each type has different default retention and importance.
    """
    CONVERSATION = "conversation"         # Chat history
    USER_PREFERENCE = "user_preference"   # User's preferred styles/settings
    PROJECT_CONTEXT = "project_context"   # Info about a codebase
    TASK_RESULT = "task_result"          # Outcomes of completed tasks
    LEARNED_CORRECTION = "correction"     # When user corrects the agent
    TOOL_PATTERN = "tool_pattern"        # Successful tool usage patterns


@dataclass
class RetentionSettings:
    """
    Time-to-live settings for each memory type.
    
    These can be adjusted based on your storage constraints and
    how long you want the agent to remember different things.
    """
    conversation_ttl: timedelta = field(default_factory=lambda: timedelta(days=7))
    user_preference_ttl: timedelta = field(default_factory=lambda: timedelta(days=90))
    project_context_ttl: timedelta = field(default_factory=lambda: timedelta(days=30))
    task_result_ttl: timedelta = field(default_factory=lambda: timedelta(days=14))
    correction_ttl: timedelta = field(default_factory=lambda: timedelta(days=180))
    tool_pattern_ttl: timedelta = field(default_factory=lambda: timedelta(days=60))
    
    def get_ttl(self, memory_type: MemoryType) -> timedelta:
        """Get the TTL for a specific memory type."""
        mapping = {
            MemoryType.CONVERSATION: self.conversation_ttl,
            MemoryType.USER_PREFERENCE: self.user_preference_ttl,
            MemoryType.PROJECT_CONTEXT: self.project_context_ttl,
            MemoryType.TASK_RESULT: self.task_result_ttl,
            MemoryType.LEARNED_CORRECTION: self.correction_ttl,
            MemoryType.TOOL_PATTERN: self.tool_pattern_ttl,
        }
        return mapping.get(memory_type, timedelta(days=7))


@dataclass
class StorageLimits:
    """
    Limits to prevent unbounded memory growth.
    
    SAFETY: These limits protect against:
    - Disk exhaustion attacks
    - Memory exhaustion when loading context
    - Performance degradation from too many memories
    """
    # Maximum memories per type (oldest are pruned when exceeded)
    max_conversations_per_user: int = 500
    max_preferences_per_user: int = 50
    max_project_contexts: int = 100
    max_task_results_per_project: int = 200
    max_corrections_per_user: int = 100
    max_tool_patterns: int = 50
    
    # Size limits
    max_content_length: int = 10000      # Max chars per memory content
    max_total_storage_mb: int = 500      # Total DB size limit
    
    # Context building limits (for prompt injection)
    max_memories_in_context: int = 20    # Max memories to include in prompt
    max_context_chars: int = 8000        # Max total chars for memory context


@dataclass
class SafetySettings:
    """
    Security-related configuration.
    
    CRITICAL: These settings protect against:
    - Sensitive data leakage (API keys, passwords)
    - Prompt injection via stored memories
    - Path traversal attacks
    - Memory poisoning
    """
    # Sensitive data filtering
    filter_sensitive_data: bool = True
    sensitive_patterns: list[str] = field(default_factory=lambda: [
        # API Keys
        r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?[\w-]+',
        r'sk-[a-zA-Z0-9]{20,}',                    # OpenAI
        r'AIza[a-zA-Z0-9]{35}',                    # Google
        r'ghp_[a-zA-Z0-9]{36}',                    # GitHub
        r'xox[baprs]-[\w-]+',                      # Slack
        
        # Secrets and passwords
        r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\']+',
        r'(?i)(secret|token)\s*[=:]\s*["\']?[^\s"\']+',
        r'-----BEGIN\s+\w+\s+PRIVATE\s+KEY-----',  # Private keys
        
        # Connection strings
        r'(?i)(mysql|postgres|mongodb)://[^\s]+',
    ])
    
    # Prompt injection prevention
    escape_control_sequences: bool = True
    blocked_sequences: list[str] = field(default_factory=lambda: [
        "SYSTEM:",
        "USER:", 
        "ASSISTANT:",
        "</s>",
        "<|endoftext|>",
        "<|im_start|>",
        "<|im_end|>",
    ])
    
    # Path validation (reuses your existing pattern!)
    validate_file_paths: bool = True
    
    # Require user confirmation for high-impact operations
    require_confirmation_for_clear: bool = True


@dataclass  
class MemoryConfig:
    """
    Main configuration container with smart database path resolution.
    
    Features:
    - Platform-appropriate default paths
    - Environment variable overrides  
    - Automatic directory creation
    - Fallback handling
    
    Usage:
        # Use defaults (recommended)
        config = MemoryConfig()
        
        # Custom storage path
        config = MemoryConfig(storage_path="./my_data/memory.db")
        
        # From environment variables
        config = MemoryConfig.from_env()
    """
    # Storage - will be resolved to smart path if None
    storage_path: Optional[str] = None
    storage_backend: str = "sqlite"  # Future: "postgres", "chromadb"
    
    # Default user/project (can be overridden per-operation)
    default_user_id: str = "default_user"
    
    # Sub-configurations
    retention: RetentionSettings = field(default_factory=RetentionSettings)
    limits: StorageLimits = field(default_factory=StorageLimits)
    safety: SafetySettings = field(default_factory=SafetySettings)
    
    # Feature flags
    enable_semantic_search: bool = False  # Future: requires vector DB
    enable_auto_summarization: bool = False  # Future: summarize old convos
    
    def __post_init__(self):
        """Resolve storage path if not explicitly set and ensure directory exists."""
        if self.storage_path is None:
            self.storage_path = self._get_default_db_path()
        else:
            # Ensure directory exists for explicit paths too
            storage_path = Path(self.storage_path)
            storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _get_default_db_path(self) -> str:
        """
        Get platform-appropriate default database path.
        
        Priority order:
        1. OPTIMUS_MEMORY_PATH environment variable
        2. Platform-specific user data directory
        3. Fallback to project directory
        
        Returns:
            str: Absolute path to database file
        """
        # Check for environment variable override first
        if override_path := os.getenv("OPTIMUS_MEMORY_PATH"):
            return str(Path(override_path).expanduser().resolve())
        
        try:
            # Determine platform-appropriate base directory
            if os.name == 'nt':  # Windows
                base_dir = Path(os.getenv('APPDATA', Path.home() / 'AppData' / 'Roaming'))
            else:  # Linux/Mac
                base_dir = Path.home()
            
            # Create the optimus_ai subdirectory path
            app_data_dir = base_dir / '.optimus_ai'
            db_path = app_data_dir / 'memory.db'
            
            # Ensure directory exists
            app_data_dir.mkdir(parents=True, exist_ok=True)
            
            return str(db_path)
            
        except (PermissionError, OSError) as e:
            # Fallback to project directory if user directory fails
            print(f"Warning: Could not access user directory ({e}), falling back to project directory")
            fallback_dir = Path.cwd() / 'data'
            fallback_dir.mkdir(parents=True, exist_ok=True)
            return str(fallback_dir / 'memory.db')
    
    @classmethod
    def from_env(cls, **overrides) -> "MemoryConfig":
        """
        Create configuration from environment variables.
        
        Environment variables:
        - OPTIMUS_MEMORY_PATH: Database file path
        - OPTIMUS_MEMORY_BACKEND: Storage backend (sqlite, postgres, etc.)
        - OPTIMUS_DEFAULT_USER: Default user ID
        
        Args:
            **overrides: Direct overrides for any config field
            
        Returns:
            MemoryConfig: Configuration instance
        """
        config_data = {
            "storage_path": os.getenv("OPTIMUS_MEMORY_PATH"),
            "storage_backend": os.getenv("OPTIMUS_MEMORY_BACKEND", "sqlite"),
            "default_user_id": os.getenv("OPTIMUS_DEFAULT_USER", "default_user"),
        }
        
        # Apply any direct overrides
        config_data.update(overrides)
        
        # Filter out None values to let __post_init__ handle defaults
        config_data = {k: v for k, v in config_data.items() if v is not None}
        
        return cls(**config_data)
    
    def get_storage_info(self) -> dict[str, str | bool]:
        """
        Get information about the storage configuration.
        
        Returns:
            dict: Storage configuration details
        """
        storage_path = Path(self.storage_path)
        return {
            "storage_path": str(storage_path),
            "storage_dir": str(storage_path.parent),
            "database_name": storage_path.name,
            "backend": self.storage_backend,
            "directory_exists": storage_path.parent.exists(),
            "database_exists": storage_path.exists(),
            "is_override": bool(os.getenv("OPTIMUS_MEMORY_PATH")),
        }
    
    def validate(self) -> list[str]:
        """
        Validate configuration and return list of warnings/errors.
        Call this at startup to catch misconfigurations early.
        """
        issues = []
        
        if self.limits.max_content_length > 50000:
            issues.append("WARNING: max_content_length > 50000 may cause performance issues")
        
        if self.limits.max_context_chars > 15000:
            issues.append("WARNING: max_context_chars > 15000 may exceed model context limits")
        
        if not self.safety.filter_sensitive_data:
            issues.append("SECURITY: Sensitive data filtering is disabled!")
        
        # Validate storage path accessibility
        try:
            storage_path = Path(self.storage_path)
            storage_path.parent.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            issues.append(f"ERROR: Cannot access storage directory: {e}")
        
        return issues