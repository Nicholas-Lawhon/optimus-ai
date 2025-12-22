"""
Memory Safety Module

This module provides the security layer for the memory system.
All data MUST pass through MemorySafetyGuard before being stored.

Security threats addressed:
1. Sensitive data leakage (API keys, passwords, tokens)
2. Prompt injection via stored memories
3. Path traversal attacks
4. Memory content size attacks (DoS via huge content)

Design principle: Defense in depth - assume all input is potentially malicious.

Usage:
    guard = MemorySafetyGuard(config.safety)
    safe_content = guard.sanitize_content(raw_content)
    if guard.is_path_safe(path, working_dir):
        # proceed with operation
"""

import re
import os
import hashlib
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

# Import safety settings from config
# This creates a dependency on config.py but keeps all settings centralized
from memory.config import SafetySettings


class SanitizationAction(Enum):
    """
    What happened during sanitization.
    Useful for logging and debugging security events.
    """
    NONE = "none"                    # No changes made
    REDACTED_SECRET = "redacted_secret"  # Removed sensitive data
    ESCAPED_INJECTION = "escaped_injection"  # Neutralized prompt injection
    TRUNCATED = "truncated"          # Content was too long
    BLOCKED = "blocked"              # Content was entirely rejected


@dataclass
class SanitizationResult:
    """
    Result of sanitizing content.
    
    Provides both the sanitized content AND metadata about what was done.
    This transparency helps with debugging and auditing.
    """
    content: str                     # The sanitized content
    actions: list[SanitizationAction] = field(default_factory=list)
    original_length: int = 0
    redacted_count: int = 0          # How many secrets were found/redacted
    
    @property
    def was_modified(self) -> bool:
        """Check if any sanitization was performed."""
        return len(self.actions) > 0 and SanitizationAction.NONE not in self.actions
    
    @property
    def was_blocked(self) -> bool:
        """Check if content was entirely rejected."""
        return SanitizationAction.BLOCKED in self.actions


@dataclass
class PathValidationResult:
    """
    Result of validating a file path.
    
    Provides detailed information about why a path was accepted or rejected.
    """
    is_safe: bool
    normalized_path: str = ""
    error_message: str = ""
    

class MemorySafetyGuard:
    """
    Main security gatekeeper for the memory system.
    
    All content destined for storage should pass through this class.
    It applies multiple layers of sanitization and validation.
    
    Thread-safety: This class is stateless and safe to use across threads.
    
    Example:
        >>> guard = MemorySafetyGuard()
        >>> result = guard.sanitize_content("My API key is sk-abc123xyz")
        >>> print(result.content)
        "My API key is [REDACTED]"
        >>> print(result.was_modified)
        True
    """
    
    # Replacement text for redacted content
    REDACTION_MARKER = "[REDACTED]"
    
    # Maximum content length (can be overridden via settings)
    DEFAULT_MAX_LENGTH = 10000
    
    def __init__(self, settings: Optional[SafetySettings] = None):
        """
        Initialize the safety guard.
        
        Args:
            settings: SafetySettings instance. If None, uses defaults.
        """
        self.settings = settings or SafetySettings()
        
        # Pre-compile regex patterns for performance
        # These are compiled once at initialization, not on every call
        self._compiled_sensitive_patterns: list[re.Pattern] = []
        if self.settings.filter_sensitive_data:
            self._compile_sensitive_patterns()
    
    def _compile_sensitive_patterns(self) -> None:
        """
        Compile regex patterns for sensitive data detection.
        
        Called once during initialization to avoid repeated compilation.
        Handles invalid patterns gracefully.
        """
        for pattern in self.settings.sensitive_patterns:
            try:
                # Use IGNORECASE for most patterns to catch variations
                compiled = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                self._compiled_sensitive_patterns.append(compiled)
            except re.error as e:
                # Log but don't crash - one bad pattern shouldn't break everything
                # In production, this should go to a proper logging system
                print(f"WARNING: Invalid sensitive pattern '{pattern}': {e}")
    
    def sanitize_content(
        self, 
        content: str, 
        max_length: Optional[int] = None
    ) -> SanitizationResult:
        """
        Apply all sanitization steps to content before storage.
        
        Order of operations matters:
        1. Check for empty/None content
        2. Filter sensitive data (secrets, API keys)
        3. Escape prompt injection sequences
        4. Truncate to max length
        
        Args:
            content: Raw content to sanitize
            max_length: Override default max length. None uses settings.
            
        Returns:
            SanitizationResult with sanitized content and metadata
        """
        # Handle None/empty gracefully
        if content is None:
            return SanitizationResult(
                content="",
                actions=[SanitizationAction.NONE],
                original_length=0
            )
        
        if not isinstance(content, str):
            content = str(content)
        
        original_length = len(content)
        actions: list[SanitizationAction] = []
        redacted_count = 0
        
        # Step 1: Filter sensitive data
        if self.settings.filter_sensitive_data:
            content, count = self._redact_sensitive_data(content)
            if count > 0:
                actions.append(SanitizationAction.REDACTED_SECRET)
                redacted_count = count
        
        # Step 2: Escape prompt injection sequences
        if self.settings.escape_control_sequences:
            content, escaped = self._escape_injection_sequences(content)
            if escaped:
                actions.append(SanitizationAction.ESCAPED_INJECTION)
        
        # Step 3: Truncate if too long
        effective_max = max_length or self.DEFAULT_MAX_LENGTH
        if len(content) > effective_max:
            content = self._truncate_safely(content, effective_max)
            actions.append(SanitizationAction.TRUNCATED)
        
        # If nothing happened, mark as NONE
        if not actions:
            actions.append(SanitizationAction.NONE)
        
        return SanitizationResult(
            content=content,
            actions=actions,
            original_length=original_length,
            redacted_count=redacted_count
        )
    
    def _redact_sensitive_data(self, content: str) -> tuple[str, int]:
        """
        Remove sensitive data like API keys, passwords, tokens.
        
        Uses regex patterns from SafetySettings to identify sensitive data.
        Replaces matches with [REDACTED] marker.
        
        Args:
            content: Content to scan
            
        Returns:
            Tuple of (sanitized content, number of redactions made)
        """
        redaction_count = 0
        
        for pattern in self._compiled_sensitive_patterns:
            # Count matches before replacing
            matches = pattern.findall(content)
            if matches:
                redaction_count += len(matches)
                content = pattern.sub(self.REDACTION_MARKER, content)
        
        return content, redaction_count
    
    def _escape_injection_sequences(self, content: str) -> tuple[str, bool]:
        """
        Neutralize potential prompt injection sequences.
        
        These sequences could trick the LLM into thinking stored memory
        is actually part of the system prompt or user message.
        
        Strategy: Replace dangerous sequences with escaped versions
        that are visually similar but won't be interpreted as control sequences.
        
        We avoid double-escaping by checking if the sequence is already
        wrapped in brackets before escaping.
        
        Args:
            content: Content to scan
            
        Returns:
            Tuple of (escaped content, whether any escaping was done)
        """
        escaped = False
        
        for sequence in self.settings.blocked_sequences:
            safe_version = f"[{sequence}]"
            
            # Skip if already escaped (don't double-escape)
            # We temporarily replace already-escaped versions with a placeholder,
            # then escape the raw ones, then restore the placeholders
            placeholder = f"\x00ESCAPED_{hash(sequence)}\x00"
            
            # Step 1: Protect already-escaped sequences
            content_with_placeholders = content.replace(safe_version, placeholder)
            
            # Step 2: Escape any remaining raw sequences
            if sequence in content_with_placeholders:
                content_with_placeholders = content_with_placeholders.replace(
                    sequence, safe_version
                )
                escaped = True
            
            # Step 3: Restore the already-escaped sequences
            content = content_with_placeholders.replace(placeholder, safe_version)
        
        return content, escaped
    
    def _truncate_safely(self, content: str, max_length: int) -> str:
        """
        Truncate content to max length with a clear marker.
        
        Tries to truncate at word boundaries to avoid cutting mid-word.
        Always adds a truncation indicator so it's clear content was cut.
        
        Args:
            content: Content to truncate
            max_length: Maximum allowed length
            
        Returns:
            Truncated content with indicator
        """
        truncation_indicator = "\n... [TRUNCATED]"
        effective_max = max_length - len(truncation_indicator)
        
        if effective_max <= 0:
            return truncation_indicator
        
        # Try to find a word boundary (space, newline) near the cut point
        truncated = content[:effective_max]
        
        # Look for last whitespace in final 100 chars
        last_space = truncated.rfind(' ', max(0, effective_max - 100))
        last_newline = truncated.rfind('\n', max(0, effective_max - 100))
        
        # Use whichever is closer to the end (but still exists)
        best_break = max(last_space, last_newline)
        
        if best_break > effective_max - 100:
            truncated = truncated[:best_break]
        
        return truncated + truncation_indicator
    
    def validate_path(
        self, 
        file_path: str, 
        working_directory: str
    ) -> PathValidationResult:
        """
        Validate that a file path is safe to use.
        
        This reuses the security pattern from your existing codebase
        (get_files_info.py, get_file_content.py, etc.)
        
        Security checks:
        1. Path must not escape working directory (no ../ attacks)
        2. Path must be within the allowed working directory
        3. Path is normalized to prevent tricks like /foo/bar/../../../etc/passwd
        
        Args:
            file_path: Path to validate (can be relative or absolute)
            working_directory: The sandboxed working directory
            
        Returns:
            PathValidationResult with safety status and details
        """
        if not self.settings.validate_file_paths:
            # Validation disabled - return as-is (not recommended!)
            return PathValidationResult(
                is_safe=True,
                normalized_path=file_path,
                error_message=""
            )
        
        try:
            # Get absolute path of working directory
            working_dir_abs = os.path.abspath(working_directory)
            
            # Normalize the target path (resolves ../, ./, etc.)
            # Join with working dir first to handle relative paths
            target_path = os.path.normpath(os.path.join(working_dir_abs, file_path))
            
            # THE CRITICAL CHECK: Is target within working directory?
            # os.path.commonpath() returns the longest common path prefix
            # If it equals working_dir_abs, target is inside working directory
            common = os.path.commonpath([working_dir_abs, target_path])
            is_valid = common == working_dir_abs
            
            if is_valid:
                return PathValidationResult(
                    is_safe=True,
                    normalized_path=target_path,
                    error_message=""
                )
            else:
                return PathValidationResult(
                    is_safe=False,
                    normalized_path="",
                    error_message=f'Path "{file_path}" escapes the permitted working directory'
                )
                
        except (ValueError, OSError) as e:
            # Handle edge cases like paths on different drives (Windows)
            return PathValidationResult(
                is_safe=False,
                normalized_path="",
                error_message=f'Invalid path "{file_path}": {e}'
            )
    
    def is_path_safe(self, file_path: str, working_directory: str) -> bool:
        """
        Convenience method for simple path safety checks.
        
        Use validate_path() if you need detailed error information.
        
        Args:
            file_path: Path to check
            working_directory: Sandbox directory
            
        Returns:
            True if path is safe, False otherwise
        """
        return self.validate_path(file_path, working_directory).is_safe
    
    def hash_for_id(self, value: str) -> str:
        """
        Create a stable hash for use as an identifier.
        
        Used for things like project IDs (hash of absolute path).
        
        Args:
            value: Value to hash
            
        Returns:
            First 16 chars of SHA256 hex digest (64-bit entropy)
        """
        return hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]


# Convenience function for quick sanitization without creating an instance
def sanitize(content: str, settings: Optional[SafetySettings] = None) -> str:
    """
    Quick sanitization of content.
    
    Creates a temporary guard and sanitizes content.
    For repeated use, create a MemorySafetyGuard instance instead.
    
    Args:
        content: Content to sanitize
        settings: Optional safety settings
        
    Returns:
        Sanitized content string
    """
    guard = MemorySafetyGuard(settings)
    return guard.sanitize_content(content).content