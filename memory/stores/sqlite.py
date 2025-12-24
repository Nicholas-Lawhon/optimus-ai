import hashlib
import sqlite3
import json
from typing import Collection, List, Optional, Any, Tuple, Dict
from datetime import datetime, timezone

from memory.stores.base import MemoryStore
from memory.models import Memory, User, Project, MemoryQuery
from memory.config import MemoryConfig, MemoryScope, MemoryType, RetentionPolicy


class SQLiteMemoryStore(MemoryStore):
    def __init__(self, config: MemoryConfig, db_path: str = "memory.db"):
        self.config = config
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Return an active DB connection or raise if not initialized."""
        if self._conn is None:
            raise RuntimeError(
                "Database connection has not been initialized. Call initialize() first."
            )
        return self._conn

    def initialize(self) -> None:
        """Establish connection and ensure tables exist."""
        # check_same_thread=False allows using the connection across threads,
        # which is needed if the agent runs async operations.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)

        # Use the non-optional property
        self.conn.execute("PRAGMA foreign_keys = ON;")

        self._create_tables()
        self.conn.commit()

    def _create_tables(self) -> None:
        # Narrow once into a local non-optional variable
        conn = self.conn

        with conn:
            # Users Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
            """)

            # Projects Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    path_hash TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    last_known_path TEXT,
                    created_at TIMESTAMP NOT NULL
                )
            """)

            # Memories Table - Added missing fields
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    retention_policy TEXT NOT NULL,
                    user_id TEXT,
                    project_id TEXT,
                    tags TEXT,         -- Stored as JSON string
                    metadata TEXT,     -- Stored as JSON string
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP,
                    last_accessed_at TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    importance REAL DEFAULT 0.5,
                    source TEXT DEFAULT 'unknown',
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                )
            """)

            # Create some indexes for speed
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);"
            )

    def _build_query_conditions(self, query: MemoryQuery) -> Tuple[str, List[Any]]:
        conditions = []
        params = []

        if query.user_id:
            conditions.append("user_id = ?")  # The Rule
            params.append(query.user_id)      # The Data
            
        if query.project_id:
            conditions.append("project_id = ?")
            params.append(query.project_id)
            
        if query.scopes:
            placeholders = self._build_query_conditions_string(query.scopes)
            conditions.append(f"scope IN ({placeholders})")
            params.extend([scope.value for scope in query.scopes])
            
        if query.memory_types:
            placeholders = self._build_query_conditions_string(query.memory_types)
            conditions.append(f"memory_type IN ({placeholders})")
            params.extend([memory_type.value for memory_type in query.memory_types])
            
        if query.retention_policies:
            placeholders = self._build_query_conditions_string(query.retention_policies)
            conditions.append(f"retention_policy IN ({placeholders})")
            params.extend([policy.value for policy in query.retention_policies])

        # Add time-based filters
        if query.created_after:
            conditions.append("created_at > ?")
            params.append(query.created_after.isoformat())
            
        if query.created_before:
            conditions.append("created_at < ?")
            params.append(query.created_before.isoformat())
            
        # Handle expired filter
        if not query.include_expired:
            conditions.append("(expires_at IS NULL OR expires_at > ?)")
            params.append(datetime.now().isoformat())

        if not conditions:
            return "", []
        
        return f" WHERE {' AND '.join(conditions)}", params

    def _build_query_conditions_string(self, query: List[Any]) -> str:
        """Fixed: Create proper SQL placeholder string with parentheses for IN clauses."""
        return ", ".join(["?" for _ in query])
    
    def _row_to_memory(self, row: Tuple) -> Memory:
        # Updated to handle all fields including the new ones
        (mem_id, content, scope_val, type_val, policy_val, 
         user_id, project_id, tags_json, metadata_json, 
         created_at, updated_at, expires_at, last_accessed, access_count,
         importance, source) = row

        scope_val = MemoryScope(scope_val)
        type_val = MemoryType(type_val)
        policy_val = RetentionPolicy(policy_val)

        if tags_json:
            tags = json.loads(tags_json)
        else:
            tags = []  # Handle None

        if metadata_json:
            metadata = json.loads(metadata_json)
        else:
            metadata = {}
        
        created_at = datetime.fromisoformat(created_at)
        updated_at = datetime.fromisoformat(updated_at)
        
        if expires_at:
            expires_at = datetime.fromisoformat(expires_at)
            
        if last_accessed:
            last_accessed = datetime.fromisoformat(last_accessed)
            
        return Memory(
            id=mem_id, content=content, memory_type=type_val, scope=scope_val, 
            retention_policy=policy_val, user_id=user_id, project_id=project_id, 
            created_at=created_at, updated_at=updated_at, expires_at=expires_at, 
            access_count=access_count, last_accessed_at=last_accessed, tags=tags, 
            metadata=metadata, importance=importance, source=source
        )

    def get(self, memory_id: str) -> Optional[Memory]:
        query = "SELECT * FROM memories WHERE id = ?"
        row = self.conn.execute(query, (memory_id,)).fetchone()
        
        if not row:
            return None
        else:
            return self._row_to_memory(row)
        
    def store(self, memory: Memory) -> Memory:
        # 1. Unpack and Convert Data
        mem_id = memory.id
        content = memory.content
        user_id = memory.user_id
        project_id = memory.project_id
        access_count = memory.access_count

        # Convert Enums to their string values
        scope = memory.scope.value
        memory_type = memory.memory_type.value
        retention_policy = memory.retention_policy.value

        # Serialize list/dict to JSON strings
        tags = json.dumps(memory.tags)
        metadata = json.dumps(memory.metadata)

        # Convert datetimes to ISO strings
        created_at = memory.created_at.isoformat()
        updated_at = memory.updated_at.isoformat()
        
        # Handle optional datetimes
        expires_at = memory.expires_at.isoformat() if memory.expires_at else None
        last_accessed_at = memory.last_accessed_at.isoformat() if memory.last_accessed_at else None

        # 2. Execute the INSERT - Added missing fields
        query = """
            INSERT OR REPLACE INTO memories 
            (id, content, scope, memory_type, retention_policy, user_id, project_id, 
             tags, metadata, created_at, updated_at, expires_at, last_accessed_at, 
             access_count, importance, source) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        values = (
            mem_id, content, scope, memory_type, retention_policy, user_id, project_id, 
            tags, metadata, created_at, updated_at, expires_at, last_accessed_at, 
            access_count, memory.importance, memory.source
        )

        with self.conn:
            self.conn.execute(query, values)
        
        return memory
    
    def query(self, query: MemoryQuery) -> List[Memory]:
        base_query = "SELECT * FROM memories"
        condition, params = self._build_query_conditions(query)
        
        # Add ordering
        order_direction = "DESC" if query.order_desc else "ASC"
        order_clause = f" ORDER BY {query.order_by} {order_direction}"
        
        # Add limit and offset
        limit_clause = f" LIMIT {query.limit}"
        if query.offset > 0:
            limit_clause += f" OFFSET {query.offset}"
        
        final_query = base_query + condition + order_clause + limit_clause
        rows = self.conn.execute(final_query, params).fetchall()
        
        return [self._row_to_memory(row) for row in rows]
    
    def delete(self, memory_id: str) -> bool:
        """
        Delete a memory by ID.
        Returns: True if the memory was deleted, False if it didn't exist
        """
        query = "DELETE FROM memories WHERE id = ?"
        
        with self.conn:
            cursor = self.conn.execute(query, (memory_id,))
        
        return cursor.rowcount > 0
        
    def close(self) -> None:
        """
        Clean up resources and close connections.
        """
        if self._conn:
            self._conn.close()
            self._conn = None
        
    def store_user(self, user: User) -> User:
        """
        Store or update a user in the database.
        Returns: The stored user object
        """
        user_id = user.id
        user_name = user.name
        created_at = user.created_at.isoformat()
        
        query = "INSERT OR REPLACE INTO users (id, display_name, created_at) VALUES (?, ?, ?)"
        values = (user_id, user_name, created_at)
        
        with self.conn:
            self.conn.execute(query, values)
        
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """
        Retrieve a user by their ID.
        Returns: The user object if found, None otherwise
        """
        query = "SELECT * FROM users WHERE id = ?"
        row = self.conn.execute(query, (user_id,)).fetchone()
        
        if not row:
            return None
        else:
            return self._row_to_user(row)
    
    def get_user_by_name(self, name: str) -> Optional[User]:
        """
        Retrieve a user by their name.
        Returns: The user object if found, None otherwise
        """
        query = "SELECT * FROM users WHERE display_name = ?"
        row = self.conn.execute(query, (name,)).fetchone()
        
        if not row:
            return None
        else:
            return self._row_to_user(row)
    
    def _row_to_user(self, row: Tuple) -> User:
        """
        Convert a database row tuple to a User object.
        Returns: The converted User object
        """
        user_id, user_name, created_at = row
        created_at = datetime.fromisoformat(created_at)
        
        return User(id=user_id, name=user_name, created_at=created_at)

    def store_project(self, project: Project) -> Project:
        """
        Store or update a project in the database.
        Returns: The stored project object
        """
        project_id = project.id
        project_name = project.name
        path_hash = project.path_hash
        last_known_path = project.last_known_path
        created_at = project.created_at.isoformat()
        
        query = "INSERT OR REPLACE INTO projects (id, name, path_hash, last_known_path, created_at) VALUES (?, ?, ?, ?, ?)"
        values = (project_id, project_name, path_hash, last_known_path, created_at)
        
        with self.conn:
            self.conn.execute(query, values)
        
        return project

    def get_project(self, project_id: str) -> Optional[Project]:
        """
        Retrieve a project by its ID.
        Returns: The project object if found, None otherwise
        """
        query = "SELECT * FROM projects WHERE id = ?"
        row = self.conn.execute(query, (project_id,)).fetchone()
        
        if not row:
            return None
        else:
            return self._row_to_project(row)
    
    def get_project_by_path(self, absolute_path: str) -> Optional[Project]:
        """
        Retrieve a project by its absolute file path.
        Returns: The project object if found, None otherwise
        """
        path_hash = hashlib.sha256(absolute_path.encode()).hexdigest()
        query = "SELECT * FROM projects WHERE path_hash = ?"
        row = self.conn.execute(query, (path_hash,)).fetchone()
        
        if not row:
            return None
        else:
            return self._row_to_project(row)
    
    def _row_to_project(self, row: Tuple) -> Project:
        """
        Convert a database row tuple to a Project object.
        Returns: The converted Project object
        """
        # Fixed: Match the actual column order from CREATE TABLE
        project_id, path_hash, project_name, last_known_path, created_at = row
        created_at = datetime.fromisoformat(created_at)
        
        return Project(id=project_id, name=project_name, path_hash=path_hash, last_known_path=last_known_path, created_at=created_at)
    
    def count(self, query: Optional[MemoryQuery] = None) -> int:
        """
        Count memories matching a query.
        Args: query: Optional query filters. If None, counts all memories.
        Returns: The count (int) of memories matching a query
        """
        base_query = "SELECT COUNT(*) FROM memories"
        
        if not query:
            return self.conn.execute(base_query).fetchone()[0]
        else:
            sql_query, params = self._build_query_conditions(query)
            final_query = base_query + sql_query
            return self.conn.execute(final_query, params).fetchone()[0]
            
    def delete_by_query(self, query: MemoryQuery) -> int:
        """Delete memories matching a query using the same condition builder."""
        base_query = "DELETE FROM memories"
        condition, params = self._build_query_conditions(query)
        
        final_query = base_query + condition
        
        with self.conn:
            cursor = self.conn.execute(final_query, params)
        
        return cursor.rowcount
    
    def delete_expired(self) -> int:
        """Fixed: Proper handling of NULL expires_at and datetime comparison."""
        query = "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at < ?"
        curr_time = datetime.now(timezone.utc)
        
        with self.conn:
            cursor = self.conn.execute(query, (curr_time.isoformat(),))
        
        return cursor.rowcount
    
    def get_stats(self) -> Dict:
        """Enhanced stats with more useful information."""
        stats = {}
        
        # Total count
        stats["Total Memories"] = self.count()
        
        # Count by type
        stats["memories_by_type"] = {}
        for memory_type in MemoryType:
            query = MemoryQuery(memory_types=[memory_type])
            count = self.count(query)
            if count > 0:
                stats["memories_by_type"][memory_type.value] = count
        
        # Count by scope
        stats["memories_by_scope"] = {}
        for scope in MemoryScope:
            query = MemoryQuery(scopes=[scope])
            count = self.count(query)
            if count > 0:
                stats["memories_by_scope"][scope.value] = count
        
        # Oldest and newest memories
        try:
            oldest = self.conn.execute("SELECT MIN(created_at) FROM memories").fetchone()[0]
            newest = self.conn.execute("SELECT MAX(created_at) FROM memories").fetchone()[0]
            
            if oldest:
                stats["oldest_memory"] = datetime.fromisoformat(oldest)
            if newest:
                stats["newest_memory"] = datetime.fromisoformat(newest)
                
        except Exception:
            # Handle empty database gracefully
            pass
        
        return stats