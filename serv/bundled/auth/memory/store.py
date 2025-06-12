"""Thread-safe in-memory data store with TTL support."""

import asyncio
import time
from collections import defaultdict
from threading import RLock
from typing import Any, Dict, Iterator, Optional, Set


class TTLEntry:
    """Entry in the TTL store with expiration tracking."""
    
    def __init__(self, value: Any, ttl_seconds: Optional[float] = None):
        """Initialize TTL entry.
        
        Args:
            value: The stored value
            ttl_seconds: Time to live in seconds, None for no expiration
        """
        self.value = value
        self.created_at = time.time()
        self.expires_at = (
            self.created_at + ttl_seconds if ttl_seconds is not None else None
        )
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def time_until_expiry(self) -> Optional[float]:
        """Get time until expiry in seconds."""
        if self.expires_at is None:
            return None
        return max(0, self.expires_at - time.time())


class MemoryStore:
    """Thread-safe in-memory key-value store with TTL support.
    
    This store provides:
    - Thread-safe operations using RLock
    - TTL (Time To Live) support for automatic expiration
    - Background cleanup of expired entries
    - Namespace support for different data types
    - Efficient iteration and querying
    """
    
    def __init__(self, cleanup_interval: float = 300.0):
        """Initialize memory store.
        
        Args:
            cleanup_interval: Interval between cleanup runs in seconds
        """
        self._data: Dict[str, Dict[str, TTLEntry]] = defaultdict(dict)
        self._lock = RLock()
        self._cleanup_interval = cleanup_interval
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_running = False
    
    async def start_cleanup(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop_cleanup(self) -> None:
        """Stop background cleanup task."""
        self._cleanup_running = False
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        self._cleanup_task = None
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop to remove expired entries."""
        while self._cleanup_running:
            try:
                self._cleanup_expired()
                await asyncio.sleep(self._cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error in production, continue cleanup
                await asyncio.sleep(self._cleanup_interval)
    
    def _cleanup_expired(self) -> int:
        """Remove expired entries from all namespaces.
        
        Returns:
            Number of entries cleaned up
        """
        cleaned_count = 0
        with self._lock:
            for namespace_data in self._data.values():
                expired_keys = [
                    key for key, entry in namespace_data.items()
                    if entry.is_expired()
                ]
                for key in expired_keys:
                    del namespace_data[key]
                    cleaned_count += 1
        return cleaned_count
    
    def set(
        self, 
        namespace: str, 
        key: str, 
        value: Any, 
        ttl_seconds: Optional[float] = None
    ) -> None:
        """Set a value in the store.
        
        Args:
            namespace: Namespace for the key
            key: Key to store under
            value: Value to store
            ttl_seconds: Time to live in seconds, None for no expiration
        """
        with self._lock:
            self._data[namespace][key] = TTLEntry(value, ttl_seconds)
    
    def get(self, namespace: str, key: str) -> Optional[Any]:
        """Get a value from the store.
        
        Args:
            namespace: Namespace to look in
            key: Key to retrieve
            
        Returns:
            Value if found and not expired, None otherwise
        """
        with self._lock:
            if namespace not in self._data:
                return None
            
            entry = self._data[namespace].get(key)
            if entry is None:
                return None
            
            if entry.is_expired():
                del self._data[namespace][key]
                return None
            
            return entry.value
    
    def delete(self, namespace: str, key: str) -> bool:
        """Delete a key from the store.
        
        Args:
            namespace: Namespace to delete from
            key: Key to delete
            
        Returns:
            True if key was deleted, False if not found
        """
        with self._lock:
            if namespace not in self._data:
                return False
            
            if key in self._data[namespace]:
                del self._data[namespace][key]
                return True
            
            return False
    
    def exists(self, namespace: str, key: str) -> bool:
        """Check if a key exists and is not expired.
        
        Args:
            namespace: Namespace to check in
            key: Key to check
            
        Returns:
            True if key exists and is not expired
        """
        return self.get(namespace, key) is not None
    
    def keys(self, namespace: str) -> Set[str]:
        """Get all non-expired keys in a namespace.
        
        Args:
            namespace: Namespace to get keys from
            
        Returns:
            Set of keys that exist and are not expired
        """
        with self._lock:
            if namespace not in self._data:
                return set()
            
            # Remove expired entries and return valid keys
            valid_keys = set()
            namespace_data = self._data[namespace]
            expired_keys = []
            
            for key, entry in namespace_data.items():
                if entry.is_expired():
                    expired_keys.append(key)
                else:
                    valid_keys.add(key)
            
            # Clean up expired keys
            for key in expired_keys:
                del namespace_data[key]
            
            return valid_keys
    
    def values(self, namespace: str) -> Iterator[Any]:
        """Get all non-expired values in a namespace.
        
        Args:
            namespace: Namespace to get values from
            
        Yields:
            Values that exist and are not expired
        """
        with self._lock:
            if namespace not in self._data:
                return
            
            namespace_data = self._data[namespace]
            expired_keys = []
            
            for key, entry in namespace_data.items():
                if entry.is_expired():
                    expired_keys.append(key)
                else:
                    yield entry.value
            
            # Clean up expired keys
            for key in expired_keys:
                del namespace_data[key]
    
    def items(self, namespace: str) -> Iterator[tuple[str, Any]]:
        """Get all non-expired key-value pairs in a namespace.
        
        Args:
            namespace: Namespace to get items from
            
        Yields:
            Tuples of (key, value) that exist and are not expired
        """
        with self._lock:
            if namespace not in self._data:
                return
            
            namespace_data = self._data[namespace]
            expired_keys = []
            
            for key, entry in namespace_data.items():
                if entry.is_expired():
                    expired_keys.append(key)
                else:
                    yield (key, entry.value)
            
            # Clean up expired keys
            for key in expired_keys:
                del namespace_data[key]
    
    def clear(self, namespace: str) -> None:
        """Clear all data from a specific namespace.
        
        Args:
            namespace: Namespace to clear
        """
        with self._lock:
            self._data[namespace].clear()
    
    def clear_all(self) -> None:
        """Clear all data from all namespaces."""
        with self._lock:
            self._data.clear()
    
    def size(self, namespace: Optional[str] = None) -> int:
        """Get number of non-expired entries.
        
        Args:
            namespace: Namespace to count, None to count all namespaces
            
        Returns:
            Number of non-expired entries
        """
        if namespace is None:
            return sum(len(self.keys(ns)) for ns in self._data.keys())
        else:
            return len(self.keys(namespace))
    
    def expire(self, namespace: str, key: str, ttl_seconds: float) -> bool:
        """Set expiration time for an existing key.
        
        Args:
            namespace: Namespace of the key
            key: Key to set expiration for
            ttl_seconds: Time to live in seconds from now
            
        Returns:
            True if expiration was set, False if key doesn't exist
        """
        with self._lock:
            if namespace not in self._data:
                return False
            
            entry = self._data[namespace].get(key)
            if entry is None or entry.is_expired():
                return False
            
            entry.expires_at = time.time() + ttl_seconds
            return True
    
    def ttl(self, namespace: str, key: str) -> Optional[float]:
        """Get time to live for a key.
        
        Args:
            namespace: Namespace of the key
            key: Key to get TTL for
            
        Returns:
            Time to live in seconds, None if no expiration or key doesn't exist
        """
        with self._lock:
            if namespace not in self._data:
                return None
            
            entry = self._data[namespace].get(key)
            if entry is None or entry.is_expired():
                return None
            
            return entry.time_until_expiry()