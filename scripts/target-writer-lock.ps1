# Shared stable lock for project writers. Windows uses the byte 0 range used by
# olympus.source_edit's msvcrt.locking protocol; Unix uses libc flock, matching
# Python's fcntl.flock. This shares exclusion only, never its private journal.
if (-not ('OlympusTargetWriterLockFileInfo' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class OlympusTargetWriterLockFileInfo
{
    [StructLayout(LayoutKind.Sequential)]
    private struct BY_HANDLE_FILE_INFORMATION
    {
        public uint FileAttributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME CreationTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastAccessTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWriteTime;
        public uint VolumeSerialNumber;
        public uint FileSizeHigh;
        public uint FileSizeLow;
        public uint NumberOfLinks;
        public uint FileIndexHigh;
        public uint FileIndexLow;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetFileInformationByHandle(
        SafeFileHandle handle, out BY_HANDLE_FILE_INFORMATION information);

    public static string WindowsIdentity(SafeFileHandle handle, out uint links, out uint attributes)
    {
        BY_HANDLE_FILE_INFORMATION information;
        if (!GetFileInformationByHandle(handle, out information))
            throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        links = information.NumberOfLinks;
        attributes = information.FileAttributes;
        return information.VolumeSerialNumber.ToString("X8") + ":" +
            information.FileIndexHigh.ToString("X8") + information.FileIndexLow.ToString("X8");
    }

    [DllImport("libc", EntryPoint = "fstat", SetLastError = true)]
    private static extern int FStat(int descriptor, IntPtr buffer);

    [DllImport("libc", EntryPoint = "lstat", CharSet = CharSet.Ansi, SetLastError = true)]
    private static extern int LStat(string path, IntPtr buffer);

    [DllImport("libc", EntryPoint = "flock", SetLastError = true)]
    private static extern int FLock(int descriptor, int operation);

    [DllImport("libc", EntryPoint = "open", CharSet = CharSet.Ansi, SetLastError = true)]
    private static extern int Open(string path, int flags, uint mode);

    private sealed class UnixStat
    {
        public ulong Device;
        public ulong Inode;
        public ulong Links;
        public uint Mode;
        public long Size;
    }

    private static UnixStat ReadUnixStat(IntPtr buffer)
    {
        if (IntPtr.Size != 8)
            throw new PlatformNotSupportedException("Unix writer locks require a 64-bit process.");

        // Linux x86_64 and arm64 have different mode/nlink offsets. macOS uses
        // the Darwin stat layout on both supported 64-bit architectures.
        if (RuntimeInformation.IsOSPlatform(OSPlatform.OSX))
        {
            return new UnixStat {
                Device = unchecked((uint)Marshal.ReadInt32(buffer, 0)),
                Mode = unchecked((ushort)Marshal.ReadInt16(buffer, 4)),
                Links = unchecked((ushort)Marshal.ReadInt16(buffer, 6)),
                Inode = unchecked((ulong)Marshal.ReadInt64(buffer, 8)),
                Size = Marshal.ReadInt64(buffer, 96)
            };
        }

        if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux))
        {
            var architecture = RuntimeInformation.ProcessArchitecture;
            if (architecture == Architecture.X64)
            {
                return new UnixStat {
                    Device = unchecked((ulong)Marshal.ReadInt64(buffer, 0)),
                    Inode = unchecked((ulong)Marshal.ReadInt64(buffer, 8)),
                    Links = unchecked((ulong)Marshal.ReadInt64(buffer, 16)),
                    Mode = unchecked((uint)Marshal.ReadInt32(buffer, 24)),
                    Size = Marshal.ReadInt64(buffer, 48)
                };
            }
            if (architecture == Architecture.Arm64)
            {
                return new UnixStat {
                    Device = unchecked((ulong)Marshal.ReadInt64(buffer, 0)),
                    Inode = unchecked((ulong)Marshal.ReadInt64(buffer, 8)),
                    Mode = unchecked((uint)Marshal.ReadInt32(buffer, 16)),
                    Links = unchecked((uint)Marshal.ReadInt32(buffer, 20)),
                    Size = Marshal.ReadInt64(buffer, 48)
                };
            }
        }

        throw new PlatformNotSupportedException("Unix writer lock identity is not qualified for this OS or architecture.");
    }

    private static void ValidateUnixStat(UnixStat information, string description)
    {
        if ((information.Mode & 0xF000) != 0x8000)
            throw new InvalidOperationException("OLYMPUS_TARGET_LOCK_UNSAFE: lock must be a regular, non-symlink file: " + description);
        if (information.Links != 1)
            throw new InvalidOperationException("OLYMPUS_TARGET_LOCK_UNSAFE: lock must not have hard-link aliases: " + description);
        if (information.Size != 0)
            throw new InvalidOperationException("OLYMPUS_TARGET_LOCK_UNSAFE: stable lock file must remain empty: " + description);
        if (information.Inode == 0)
            throw new InvalidOperationException("OLYMPUS_TARGET_LOCK_IDENTITY: filesystem did not provide a stable lock identity: " + description);
    }

    public static FileStream OpenUnixFile(string path)
    {
        bool isMac = RuntimeInformation.IsOSPlatform(OSPlatform.OSX);
        bool isLinux = RuntimeInformation.IsOSPlatform(OSPlatform.Linux);
        Architecture architecture = RuntimeInformation.ProcessArchitecture;
        if ((!isMac && !isLinux) || IntPtr.Size != 8 ||
            (architecture != Architecture.X64 && architecture != Architecture.Arm64))
            throw new PlatformNotSupportedException("Unix writer lock open is not qualified for this OS or architecture.");

        // Inspect an existing path before open; O_NOFOLLOW and O_NONBLOCK then
        // close symlink/FIFO races while preserving safe fail-closed checks.
        IntPtr buffer = Marshal.AllocHGlobal(256);
        try
        {
            if (LStat(path, buffer) == 0)
                ValidateUnixStat(ReadUnixStat(buffer), path);
            else if (Marshal.GetLastWin32Error() != 2) // ENOENT: first writer creates the stable file.
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Cannot inspect the Unix lock path before open.");
        }
        finally { Marshal.FreeHGlobal(buffer); }

        int flags;
        if (isLinux)
            flags = 2 | 64 | 2048 | 131072 | 524288; // O_RDWR|O_CREAT|O_NONBLOCK|O_NOFOLLOW|O_CLOEXEC
        else
            flags = 2 | 4 | 256 | 16777216; // O_RDWR|O_NONBLOCK|O_NOFOLLOW|O_CREAT|O_CLOEXEC

        int descriptor = Open(path, flags, 384); // mode 0600; never truncate or replace an existing stable lock.
        if (descriptor < 0)
            throw new Win32Exception(Marshal.GetLastWin32Error(), "Cannot open the stable Unix lock file.");

        SafeFileHandle handle = new SafeFileHandle(new IntPtr(descriptor), true);
        try { return new FileStream(handle, System.IO.FileAccess.ReadWrite); }
        catch { handle.Dispose(); throw; }
    }

    public static string UnixIdentity(SafeFileHandle handle, string path,
        out ulong links, out uint mode, out long size)
    {
        IntPtr buffer = Marshal.AllocHGlobal(256);
        try
        {
            int descriptor = handle.DangerousGetHandle().ToInt32();
            if (FStat(descriptor, buffer) != 0)
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Cannot inspect the open Unix lock file.");
            UnixStat byHandle = ReadUnixStat(buffer);
            ValidateUnixStat(byHandle, "open descriptor");

            if (LStat(path, buffer) != 0)
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Cannot inspect the Unix lock path.");
            UnixStat byPath = ReadUnixStat(buffer);
            ValidateUnixStat(byPath, path);
            if (byHandle.Device != byPath.Device || byHandle.Inode != byPath.Inode)
                throw new InvalidOperationException("OLYMPUS_TARGET_LOCK_IDENTITY: stable lock path changed identity.");

            links = byHandle.Links;
            mode = byHandle.Mode;
            size = byHandle.Size;
            return byHandle.Device.ToString("X16") + ":" + byHandle.Inode.ToString("X16");
        }
        finally { Marshal.FreeHGlobal(buffer); }
    }

    // flock(LOCK_EX | LOCK_NB) is the native Unix operation used by Python's
    // fcntl.flock. Return errno so PowerShell can distinguish contention.
    public static int UnixLock(SafeFileHandle handle, bool unlock)
    {
        int operation = unlock ? 8 : (2 | 4); // LOCK_UN, or LOCK_EX | LOCK_NB
        if (FLock(handle.DangerousGetHandle().ToInt32(), operation) == 0) return 0;
        return Marshal.GetLastWin32Error();
    }
}
'@
}

$script:OlympusTargetWriterLockName = '.olympus-cli-edit.lock'
$script:OlympusTargetWriterLockReparse = [uint32][IO.FileAttributes]::ReparsePoint

function Get-OlympusTargetWriterLockIdentity([IO.FileStream]$Stream, [string]$Path) {
    [uint32]$links = 0
    [uint32]$attributes = 0
    if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
        $identity = [OlympusTargetWriterLockFileInfo]::WindowsIdentity(
            $Stream.SafeFileHandle, [ref]$links, [ref]$attributes)
        if ($links -ne 1 -or ($attributes -band $script:OlympusTargetWriterLockReparse) -ne 0) {
            throw 'OLYMPUS_TARGET_LOCK_UNSAFE: lock must be a regular, non-linked file.'
        }
    } else {
        [uint64]$unixLinks = 0
        [uint32]$unixMode = 0
        [long]$size = 0
        $identity = [OlympusTargetWriterLockFileInfo]::UnixIdentity(
            $Stream.SafeFileHandle, $Path, [ref]$unixLinks, [ref]$unixMode, [ref]$size)
    }
    return $identity
}

function Assert-OlympusTargetWriterLock($Lock) {
    if ($null -eq $Lock -or $null -eq $Lock.Stream -or $Lock.Stream.SafeFileHandle.IsClosed) {
        throw 'OLYMPUS_TARGET_LOCK_INVALID: no live target writer lock is held.'
    }
    $pathItem = Get-Item -LiteralPath $Lock.Path -Force -ErrorAction Stop
    if ($pathItem.PSIsContainer -or ($pathItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'OLYMPUS_TARGET_LOCK_UNSAFE: lock path is not a regular file.'
    }
    if ($Lock.Stream.Length -ne 0) {
        throw 'OLYMPUS_TARGET_LOCK_UNSAFE: stable lock file must remain empty.'
    }

    if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
        $pathStream = $null
        try {
            $pathStream = [IO.FileStream]::new(
                $Lock.Path, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::ReadWrite)
            $pathIdentity = Get-OlympusTargetWriterLockIdentity $pathStream $Lock.Path
            $handleIdentity = Get-OlympusTargetWriterLockIdentity $Lock.Stream $Lock.Path
            if ($pathStream.Length -ne 0 -or $pathIdentity -cne $Lock.Identity -or
                $handleIdentity -cne $Lock.Identity) {
                throw 'OLYMPUS_TARGET_LOCK_IDENTITY: stable lock path changed identity.'
            }
        } finally {
            if ($null -ne $pathStream) { $pathStream.Dispose() }
        }
    } else {
        $pathIdentity = Get-OlympusTargetWriterLockIdentity $Lock.Stream $Lock.Path
        if ($Lock.Stream.Length -ne 0 -or $pathIdentity -cne $Lock.Identity) {
            throw 'OLYMPUS_TARGET_LOCK_IDENTITY: stable lock path changed identity.'
        }
    }
}

function Enter-OlympusTargetWriterLock([string]$Target) {
    $path = Join-Path ([IO.Path]::GetFullPath($Target)) $script:OlympusTargetWriterLockName
    $existing = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    if ($null -ne $existing -and ($existing.PSIsContainer -or
        ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint))) {
        throw 'OLYMPUS_TARGET_LOCK_UNSAFE: lock path must be a regular, non-reparse file.'
    }

    $stream = $null
    $locked = $false
    try {
        # Opening never truncates or replaces the stable file. Kernel locks are
        # released by the OS when this process exits, even after termination.
        if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
            $stream = [IO.FileStream]::new(
                $path, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::ReadWrite)
        } else {
            $stream = [OlympusTargetWriterLockFileInfo]::OpenUnixFile($path)
        }
        $identity = Get-OlympusTargetWriterLockIdentity $stream $path
        if ($stream.Length -ne 0) {
            throw 'OLYMPUS_TARGET_LOCK_UNSAFE: stable lock file must be empty.'
        }
        if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
            try {
                $stream.Lock(0, 1)
                $locked = $true
            } catch [IO.IOException] {
                $win32Error = $_.Exception.HResult -band 0xFFFF
                if ($win32Error -in @(32, 33, 36)) {
                    throw 'OLYMPUS_TARGET_LOCK_BUSY: another cooperating writer owns the target lock.'
                }
                throw ('OLYMPUS_TARGET_LOCK_FAILED: cannot acquire the target lock: ' + $_.Exception.Message)
            }
        } else {
            $lockError = [OlympusTargetWriterLockFileInfo]::UnixLock($stream.SafeFileHandle, $false)
            if ($lockError -in @(11, 13, 35)) {
                throw 'OLYMPUS_TARGET_LOCK_BUSY: another cooperating writer owns the target lock.'
            }
            if ($lockError -ne 0) {
                throw "OLYMPUS_TARGET_LOCK_FAILED: cannot acquire the Unix target lock (errno $lockError)."
            }
            $locked = $true
        }

        $lock = [pscustomobject]@{ Path = $path; Identity = $identity; Stream = $stream }
        Assert-OlympusTargetWriterLock $lock
        return $lock
    } catch {
        if ($null -ne $stream) {
            if ($locked) {
                try {
                    if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
                        $stream.Unlock(0, 1)
                    } else {
                        [void][OlympusTargetWriterLockFileInfo]::UnixLock($stream.SafeFileHandle, $true)
                    }
                } catch { }
            }
            $stream.Dispose()
        }
        throw
    }
}

function Exit-OlympusTargetWriterLock($Lock) {
    if ($null -eq $Lock -or $null -eq $Lock.Stream) { return }
    try {
        Assert-OlympusTargetWriterLock $Lock
        if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
            $Lock.Stream.Unlock(0, 1)
        } else {
            $lockError = [OlympusTargetWriterLockFileInfo]::UnixLock($Lock.Stream.SafeFileHandle, $true)
            if ($lockError -ne 0) {
                throw "OLYMPUS_TARGET_LOCK_FAILED: cannot release the Unix target lock (errno $lockError)."
            }
        }
    } finally {
        $Lock.Stream.Dispose()
    }
}
