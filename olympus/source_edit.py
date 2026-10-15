"""Private, stable source-edit lock primitives for Slice B.

This module deliberately contains no model staging, replacement, or recovery
logic. Callers must acquire the lock before inspecting any pending batch.
"""

from __future__ import annotations

import errno
import os
import stat
from dataclasses import dataclass
from pathlib import Path


_LOCK_NAME = ".olympus-cli-edit.lock"
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class LockError(RuntimeError):
    """The stable edit lock is missing, unsafe, or has changed identity."""


class LockBusy(LockError):
    """Another cooperating process owns the stable edit lock."""


class LockIdentityError(LockError):
    """The lock descriptor and canonical path no longer identify one file."""


@dataclass(slots=True)
class _Lock:
    path: Path
    descriptor: int
    identity: tuple[int, int]
    released: bool = False


def _canonical_source(source_root: os.PathLike[str] | str) -> Path:
    try:
        source = Path(source_root).resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise LockError(f"Invalid canonical source root: {source_root}") from error
    if not source.is_dir():
        raise LockError(f"Canonical source root is not a directory: {source}")
    return source


def _file_identity(metadata: os.stat_result, description: str) -> tuple[int, int]:
    attributes = getattr(metadata, "st_file_attributes", 0)
    if attributes & _REPARSE_POINT or stat.S_ISLNK(metadata.st_mode):
        raise LockError(f"Lock may not be a link or reparse point: {description}")
    if not stat.S_ISREG(metadata.st_mode):
        raise LockError(f"Lock must be a regular file: {description}")
    if metadata.st_nlink != 1:
        raise LockError(f"Lock must not have hard-link aliases: {description}")
    if metadata.st_size != 0:
        raise LockError(f"Lock file must remain empty: {description}")
    identity = (metadata.st_dev, metadata.st_ino)
    if identity[0] < 0 or identity[1] <= 0:
        raise LockIdentityError(f"Filesystem did not provide a stable lock identity: {description}")
    return identity


def _lock_identity(lock: _Lock, expected: tuple[int, int] | None = None) -> tuple[int, int]:
    """Verify descriptor/path identity and return the stable (device, inode)."""
    if lock.released:
        raise LockIdentityError("Lock descriptor has already been released")
    try:
        descriptor_stat = os.fstat(lock.descriptor)
        path_stat = os.lstat(lock.path)
    except OSError as error:
        raise LockIdentityError(f"Cannot verify stable lock identity at {lock.path}") from error

    try:
        descriptor_identity = _file_identity(descriptor_stat, "open descriptor")
        path_identity = _file_identity(path_stat, str(lock.path))
    except LockError as error:
        raise LockIdentityError(f"Stable lock is no longer a safe regular file: {lock.path}") from error
    if descriptor_identity != path_identity or descriptor_identity != lock.identity:
        raise LockIdentityError(f"Stable lock path was substituted: {lock.path}")
    if expected is not None and descriptor_identity != expected:
        raise LockIdentityError(f"Stable lock identity contradicts the expected identity: {lock.path}")
    return descriptor_identity


def _acquire_lock(source_root: os.PathLike[str] | str, *, create: bool) -> _Lock:
    """Acquire the canonical source's stable lock without waiting.

    ``create=True`` is only for a preflight-approved real edit and uses
    exclusive creation. Recovery callers must use ``create=False``; that path
    never creates, truncates, or replaces the stable lock.
    """
    source = _canonical_source(source_root)
    path = source / _LOCK_NAME
    flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)

    try:
        if create:
            try:
                descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                descriptor = os.open(path, flags)
        else:
            descriptor = os.open(path, flags)
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.EMLINK):
            raise LockError(f"Lock may not be a link: {path}") from error
        raise LockError(f"Cannot open stable lock at {path}: {error}") from error

    acquired = False
    try:
        os.set_inheritable(descriptor, False)
        descriptor_stat = os.fstat(descriptor)
        initial_identity = _file_identity(descriptor_stat, "open descriptor")
        try:
            path_stat = os.lstat(path)
        except OSError as error:
            raise LockIdentityError(f"Stable lock path disappeared during acquisition: {path}") from error
        path_identity = _file_identity(path_stat, str(path))
        if initial_identity != path_identity:
            raise LockIdentityError(f"Stable lock path changed during acquisition: {path}")

        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError as error:
                if error.errno in (errno.EACCES, errno.EDEADLK) or getattr(error, "winerror", None) in (32, 33, 36):
                    raise LockBusy(f"Stable lock is owned by another process: {path}") from error
                raise LockError(f"Cannot acquire stable lock at {path}: {error}") from error
        else:
            import fcntl

            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                if error.errno in (errno.EACCES, errno.EAGAIN):
                    raise LockBusy(f"Stable lock is owned by another process: {path}") from error
                raise LockError(f"Cannot acquire stable lock at {path}: {error}") from error

        acquired = True
        lock = _Lock(path=path, descriptor=descriptor, identity=initial_identity)
        _lock_identity(lock)
        return lock
    except BaseException:
        if acquired:
            try:
                _unlock_descriptor(descriptor)
            except OSError:
                pass
        os.close(descriptor)
        raise


def _unlock_descriptor(descriptor: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_UN)


def _release_lock(lock: _Lock) -> None:
    """Release the OS lock and close its private, non-inheritable descriptor."""
    if lock.released:
        raise LockIdentityError("Lock descriptor has already been released")

    identity_error: LockIdentityError | None = None
    try:
        _lock_identity(lock)
    except LockIdentityError as error:
        identity_error = error

    unlock_error: OSError | None = None
    try:
        _unlock_descriptor(lock.descriptor)
    except OSError as error:
        unlock_error = error
    finally:
        try:
            os.close(lock.descriptor)
        finally:
            lock.released = True

    if identity_error is not None:
        raise identity_error
    if unlock_error is not None:
        raise LockError(f"Cannot release stable lock at {lock.path}: {unlock_error}") from unlock_error
