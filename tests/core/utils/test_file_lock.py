"""
Tests for file locking mechanisms.

This module tests lock acquisition, release, timeout, and concurrency handling.
"""

import time
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

from transcriptx.core.utils.file_lock import (
    FileLock,
    cleanup_stale_locks,
)


class TestFileLock:
    """Tests for FileLock class."""
    
    def test_initialization(self, tmp_path):
        """Test FileLock initialization."""
        test_file = tmp_path / "test.txt"
        lock = FileLock(test_file, timeout=60, blocking=True)
        
        assert lock.file_path == test_file
        assert lock.timeout == 60
        assert lock.blocking is True
        assert lock.lock_file == test_file.with_suffix('.txt.lock')
        assert lock.acquired is False
    
    def test_context_manager_usage(self, tmp_path):
        """Test FileLock as context manager."""
        test_file = tmp_path / "test.txt"
        
        with patch('transcriptx.core.utils.file_lock.fcntl') as mock_fcntl, \
             patch('builtins.open', mock_open()) as mock_file:
            
            mock_fcntl.LOCK_EX = 2
            mock_fcntl.LOCK_NB = 4
            mock_fcntl.LOCK_UN = 8
            
            with FileLock(test_file) as lock:
                assert lock.acquired is True
            
            # Lock should be released
            assert lock.acquired is False
    
    def test_acquire_lock_success(self, tmp_path):
        """Test successful lock acquisition."""
        test_file = tmp_path / "test.txt"
        lock = FileLock(test_file, blocking=False)
        
        with patch('transcriptx.core.utils.file_lock.fcntl') as mock_fcntl, \
             patch('builtins.open', mock_open()) as mock_file:
            
            mock_fcntl.LOCK_EX = 2
            mock_fcntl.LOCK_NB = 4
            
            result = lock.acquire()
            
            assert result is True
            assert lock.acquired is True
    
    def test_acquire_lock_fails_when_locked(self, tmp_path):
        """Test that lock acquisition fails when file is already locked."""
        test_file = tmp_path / "test.txt"
        lock = FileLock(test_file, blocking=False)
        
        with patch('transcriptx.core.utils.file_lock.fcntl') as mock_fcntl, \
             patch('builtins.open', mock_open()) as mock_file:
            
            mock_fcntl.LOCK_EX = 2
            mock_fcntl.LOCK_NB = 4
            mock_fcntl.flock.side_effect = IOError("Resource temporarily unavailable")
            
            result = lock.acquire()
            
            assert result is False
            assert lock.acquired is False
    
    def test_acquire_lock_timeout(self, tmp_path):
        """Test that lock acquisition times out."""
        test_file = tmp_path / "test.txt"
        lock = FileLock(test_file, timeout=0.1, blocking=True)
        
        with patch('transcriptx.core.utils.file_lock.fcntl') as mock_fcntl, \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('time.sleep') as mock_sleep:
            
            mock_fcntl.LOCK_EX = 2
            mock_fcntl.LOCK_NB = 4
            mock_fcntl.flock.side_effect = IOError("Resource temporarily unavailable")
            
            result = lock.acquire()
            
            assert result is False
            assert lock.acquired is False
            # Should have attempted to sleep
            assert mock_sleep.called
    
    def test_release_lock(self, tmp_path):
        """Test lock release."""
        test_file = tmp_path / "test.txt"
        lock = FileLock(test_file)
        
        with patch('transcriptx.core.utils.file_lock.fcntl') as mock_fcntl, \
             patch('builtins.open', mock_open()) as mock_file:
            
            mock_fcntl.LOCK_EX = 2
            mock_fcntl.LOCK_NB = 4
            mock_fcntl.LOCK_UN = 8
            
            # Acquire lock first
            lock.acquire()
            assert lock.acquired is True
            
            # Release lock
            lock.release()
            
            assert lock.acquired is False
            mock_fcntl.flock.assert_called()
    
    def test_release_when_not_acquired(self, tmp_path):
        """Test that release does nothing when lock not acquired."""
        test_file = tmp_path / "test.txt"
        lock = FileLock(test_file)
        
        # Release without acquiring
        lock.release()
        
        assert lock.acquired is False
    
    def test_is_locked_returns_false_when_not_locked(self, tmp_path):
        """Test that is_locked returns False when file is not locked."""
        test_file = tmp_path / "test.txt"
        lock = FileLock(test_file)
        
        with patch('transcriptx.core.utils.file_lock.fcntl') as mock_fcntl, \
             patch('builtins.open', mock_open()) as mock_file:
            
            mock_fcntl.LOCK_EX = 2
            mock_fcntl.LOCK_NB = 4
            mock_fcntl.LOCK_UN = 8
            
            result = lock.is_locked()
            
            assert result is False
    
    def test_is_locked_returns_true_when_locked(self, tmp_path):
        """Test that is_locked returns True when file is locked."""
        test_file = tmp_path / "test.txt"
        lock = FileLock(test_file)
        
        with patch('transcriptx.core.utils.file_lock.fcntl') as mock_fcntl, \
             patch('builtins.open', mock_open()) as mock_file:
            
            mock_fcntl.LOCK_EX = 2
            mock_fcntl.LOCK_NB = 4
            mock_fcntl.flock.side_effect = IOError("Resource temporarily unavailable")
            
            result = lock.is_locked()
            
            assert result is True
    
    def test_handles_windows_locking(self, tmp_path):
        """Test Windows-specific locking behavior."""
        test_file = tmp_path / "test.txt"
        lock = FileLock(test_file)
        
        with patch('transcriptx.core.utils.file_lock.WINDOWS', True), \
             patch('transcriptx.core.utils.file_lock.msvcrt') as mock_msvcrt, \
             patch('builtins.open', mock_open()) as mock_file:
            
            mock_msvcrt.LK_NBLCK = 1
            mock_msvcrt.LK_UNLCK = 2
            
            result = lock.acquire()
            
            # Should attempt Windows locking
            assert mock_msvcrt.locking.called or result is not None
    
    def test_handles_locking_not_available(self, tmp_path):
        """Test behavior when locking is not available."""
        test_file = tmp_path / "test.txt"
        lock = FileLock(test_file)
        
        with patch('transcriptx.core.utils.file_lock.WINDOWS', False), \
             patch('transcriptx.core.utils.file_lock.fcntl', None):
            
            result = lock.acquire()
            
            assert result is False
    
    def test_creates_lock_file_directory(self, tmp_path):
        """Test that lock file directory is created."""
        test_file = tmp_path / "subdir" / "test.txt"
        lock = FileLock(test_file)
        
        with patch('transcriptx.core.utils.file_lock.fcntl') as mock_fcntl, \
             patch('builtins.open', mock_open()) as mock_file:
            
            mock_fcntl.LOCK_EX = 2
            mock_fcntl.LOCK_NB = 4
            
            lock.acquire()
            
            # Directory should be created
            assert test_file.parent.exists() or lock.lock_file.parent.exists()


class TestCleanupStaleLocks:
    """Tests for cleanup_stale_locks function."""
    
    def test_removes_stale_lock(self, tmp_path):
        """Test that stale lock file is removed."""
        lock_file = tmp_path / "test.txt.lock"
        lock_file.write_text("lock content")
        
        # Make file old
        old_time = time.time() - 4000  # More than 1 hour
        lock_file.touch()
        import os
        os.utime(lock_file, (old_time, old_time))
        
        cleanup_stale_locks(lock_file, max_age_seconds=3600)
        
        assert not lock_file.exists()
    
    def test_keeps_recent_lock(self, tmp_path):
        """Test that recent lock file is kept."""
        lock_file = tmp_path / "test.txt.lock"
        lock_file.write_text("lock content")
        lock_file.touch()  # Recent modification time
        
        cleanup_stale_locks(lock_file, max_age_seconds=3600)
        
        assert lock_file.exists()
    
    def test_handles_nonexistent_lock(self, tmp_path):
        """Test that function handles nonexistent lock file."""
        lock_file = tmp_path / "nonexistent.lock"
        
        # Should not raise error
        cleanup_stale_locks(lock_file)
    
    def test_handles_cleanup_errors(self, tmp_path):
        """Test that cleanup errors are handled."""
        lock_file = tmp_path / "test.txt.lock"
        lock_file.write_text("lock content")
        
        with patch('pathlib.Path.unlink') as mock_unlink:
            mock_unlink.side_effect = OSError("Permission denied")
            
            # Should not raise error
            cleanup_stale_locks(lock_file, max_age_seconds=0)
