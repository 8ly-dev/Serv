"""Tests for the MemoryStore class."""

import asyncio
import time
from unittest.mock import patch

import pytest

from serv.bundled.auth.memory.store import MemoryStore, TTLEntry


class TestTTLEntry:
    """Test TTL entry functionality."""

    def test_create_entry_without_ttl(self):
        """Test creating an entry without TTL."""
        entry = TTLEntry("test_value")
        assert entry.value == "test_value"
        assert entry.expires_at is None
        assert not entry.is_expired()

    def test_create_entry_with_ttl(self):
        """Test creating an entry with TTL."""
        current_time = time.time()
        entry = TTLEntry("test_value", ttl_seconds=10.0)
        
        assert entry.value == "test_value"
        assert entry.expires_at is not None
        assert entry.expires_at >= current_time + 9.9  # Allow for small timing differences
        assert not entry.is_expired()

    def test_entry_expiration(self):
        """Test entry expiration."""
        # Create entry that expires immediately
        entry = TTLEntry("test_value", ttl_seconds=0.001)
        
        # Wait for expiration
        time.sleep(0.002)
        
        assert entry.is_expired()

    def test_entry_no_expiration_when_no_ttl(self):
        """Test that entries without TTL never expire."""
        entry = TTLEntry("test_value")
        assert not entry.is_expired()


class TestMemoryStore:
    """Test memory store functionality."""

    def test_basic_operations(self):
        """Test basic get/set/delete operations."""
        store = MemoryStore()
        
        # Test set and get
        store.set("test_ns", "key1", "value1")
        assert store.get("test_ns", "key1") == "value1"
        
        # Test non-existent key
        assert store.get("test_ns", "nonexistent") is None
        
        # Test exists
        assert store.exists("test_ns", "key1")
        assert not store.exists("test_ns", "nonexistent")
        
        # Test delete
        assert store.delete("test_ns", "key1")
        assert not store.exists("test_ns", "key1")
        assert not store.delete("test_ns", "key1")  # Already deleted

    def test_ttl_operations(self):
        """Test TTL-based operations."""
        store = MemoryStore()
        
        # Set with TTL
        store.set("test_ns", "key1", "value1", ttl_seconds=1.0)
        assert store.get("test_ns", "key1") == "value1"
        
        # Set without TTL in same namespace
        store.set("test_ns", "key2", "value2")
        assert store.get("test_ns", "key2") == "value2"
        
        # Wait for TTL expiration
        time.sleep(1.1)
        
        # TTL entry should be gone, non-TTL should remain
        assert store.get("test_ns", "key1") is None
        assert store.get("test_ns", "key2") == "value2"

    def test_namespace_isolation(self):
        """Test that namespaces are isolated."""
        store = MemoryStore()
        
        store.set("ns1", "key1", "value1")
        store.set("ns2", "key1", "value2")
        
        assert store.get("ns1", "key1") == "value1"
        assert store.get("ns2", "key1") == "value2"
        
        # Deleting from one namespace shouldn't affect the other
        store.delete("ns1", "key1")
        assert store.get("ns1", "key1") is None
        assert store.get("ns2", "key1") == "value2"

    def test_keys_and_values(self):
        """Test listing keys and values."""
        store = MemoryStore()
        
        store.set("test_ns", "key1", "value1")
        store.set("test_ns", "key2", "value2")
        store.set("other_ns", "key3", "value3")
        
        # Test keys for specific namespace
        keys = list(store.keys("test_ns"))
        assert set(keys) == {"key1", "key2"}
        
        # Test values for specific namespace
        values = list(store.values("test_ns"))
        assert set(values) == {"value1", "value2"}
        
        # Test size
        assert store.size("test_ns") == 2
        assert store.size("other_ns") == 1
        assert store.size("nonexistent") == 0

    def test_clear_operations(self):
        """Test clearing namespaces and entire store."""
        store = MemoryStore()
        
        store.set("ns1", "key1", "value1")
        store.set("ns1", "key2", "value2")
        store.set("ns2", "key3", "value3")
        
        # Clear specific namespace
        store.clear("ns1")
        assert store.size("ns1") == 0
        assert store.size("ns2") == 1
        
        # Clear all
        store.clear_all()
        assert store.size("ns1") == 0
        assert store.size("ns2") == 0

    @pytest.mark.asyncio
    async def test_cleanup_task(self):
        """Test automatic cleanup of expired entries."""
        store = MemoryStore(cleanup_interval=0.1)  # Very frequent cleanup
        
        # Set entries with different TTLs
        store.set("test_ns", "short_ttl", "value1", ttl_seconds=0.05)
        store.set("test_ns", "long_ttl", "value2", ttl_seconds=1.0)
        store.set("test_ns", "no_ttl", "value3")
        
        # Start cleanup
        await store.start_cleanup()
        
        # Wait for short TTL to expire and cleanup to run
        await asyncio.sleep(0.2)
        
        # Short TTL should be cleaned up, others should remain
        assert store.get("test_ns", "short_ttl") is None
        assert store.get("test_ns", "long_ttl") == "value2"
        assert store.get("test_ns", "no_ttl") == "value3"
        
        # Stop cleanup
        await store.stop_cleanup()

    @pytest.mark.asyncio
    async def test_cleanup_task_lifecycle(self):
        """Test cleanup task start/stop lifecycle."""
        store = MemoryStore(cleanup_interval=0.1)
        
        # Initially no cleanup task
        assert store._cleanup_task is None
        
        # Start cleanup
        await store.start_cleanup()
        assert store._cleanup_task is not None
        assert not store._cleanup_task.done()
        
        # Starting again should be idempotent
        await store.start_cleanup()
        
        # Stop cleanup
        await store.stop_cleanup()
        assert store._cleanup_task is None

    def test_thread_safety_basic(self):
        """Test basic thread safety of operations."""
        import threading
        
        store = MemoryStore()
        results = []
        errors = []
        
        def worker(worker_id):
            try:
                for i in range(100):
                    key = f"key_{worker_id}_{i}"
                    value = f"value_{worker_id}_{i}"
                    
                    # Set value
                    store.set("test_ns", key, value)
                    
                    # Get value
                    retrieved = store.get("test_ns", key)
                    if retrieved != value:
                        errors.append(f"Worker {worker_id}: Expected {value}, got {retrieved}")
                    
                    # Delete value
                    store.delete("test_ns", key)
                    
                results.append(f"Worker {worker_id} completed")
            except Exception as e:
                errors.append(f"Worker {worker_id} error: {e}")
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 5

    def test_concurrent_ttl_operations(self):
        """Test concurrent operations with TTL entries."""
        import threading
        
        store = MemoryStore()
        errors = []
        
        def set_worker():
            try:
                for i in range(50):
                    store.set("test_ns", f"key_{i}", f"value_{i}", ttl_seconds=0.1)
            except Exception as e:
                errors.append(f"Set worker error: {e}")
        
        def get_worker():
            try:
                for i in range(50):
                    # Try to get values, some may be expired
                    value = store.get("test_ns", f"key_{i}")
                    # We don't check the value since it may have expired
            except Exception as e:
                errors.append(f"Get worker error: {e}")
        
        def cleanup_worker():
            try:
                for _ in range(10):
                    store._cleanup_expired()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"Cleanup worker error: {e}")
        
        # Start multiple threads
        threads = []
        for worker_func in [set_worker, get_worker, cleanup_worker]:
            thread = threading.Thread(target=worker_func)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check for errors
        assert len(errors) == 0, f"Concurrent TTL errors: {errors}"

    def test_cleanup_expired_manual(self):
        """Test manual cleanup of expired entries."""
        store = MemoryStore()
        
        # Add expired and non-expired entries
        store.set("test_ns", "expired1", "value1", ttl_seconds=0.001)
        store.set("test_ns", "expired2", "value2", ttl_seconds=0.001)
        store.set("test_ns", "valid", "value3", ttl_seconds=10.0)
        store.set("test_ns", "no_ttl", "value4")
        
        # Wait for expiration
        time.sleep(0.01)
        
        # Manual cleanup
        cleaned_count = store._cleanup_expired()
        
        # Should have cleaned 2 expired entries
        assert cleaned_count == 2
        
        # Check remaining entries
        assert store.get("test_ns", "expired1") is None
        assert store.get("test_ns", "expired2") is None
        assert store.get("test_ns", "valid") == "value3"
        assert store.get("test_ns", "no_ttl") == "value4"

    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        store = MemoryStore()
        
        # Test with empty strings
        store.set("", "", "")
        assert store.get("", "") == ""
        
        # Test with None values
        store.set("test_ns", "none_key", None)
        assert store.get("test_ns", "none_key") is None
        
        # Test with complex objects
        complex_obj = {"list": [1, 2, 3], "dict": {"nested": "value"}}
        store.set("test_ns", "complex", complex_obj)
        retrieved = store.get("test_ns", "complex")
        assert retrieved == complex_obj
        assert retrieved is complex_obj  # Should be the same object
        
        # Test zero TTL
        store.set("test_ns", "zero_ttl", "value", ttl_seconds=0)
        assert store.get("test_ns", "zero_ttl") is None  # Should be immediately expired
        
        # Test negative TTL  
        store.set("test_ns", "negative_ttl", "value", ttl_seconds=-1)
        assert store.get("test_ns", "negative_ttl") is None  # Should be immediately expired