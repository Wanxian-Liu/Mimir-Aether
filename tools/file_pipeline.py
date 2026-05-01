"""
File Pipeline - stdin pipe writing functionality for large file handling.
"""

import sys
import os
from typing import Optional, Callable


def write_file_large(
    file_path: str,
    content: Optional[str] = None,
    chunk_size: int = 64 * 1024,  # 64KB chunks
    encoding: str = 'utf-8',
    create_dirs: bool = True,
    overwrite: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> dict:
    """
    Write a large file with support for stdin pipe streaming.
    
    Args:
        file_path: Target file path
        content: Content to write (if None, reads from stdin)
        chunk_size: Size of chunks for streaming (default 64KB)
        encoding: File encoding
        create_dirs: Create parent directories if needed
        overwrite: Overwrite existing file
        progress_callback: Optional callback(bytes_written, total_size)
    
    Returns:
        dict with 'success', 'bytes_written', 'file_path', 'duration_ms'
    """
    import time
    
    start_time = time.time()
    
    # Validate path
    if not file_path:
        raise ValueError("file_path is required")
    
    # Check if file exists
    if os.path.exists(file_path) and not overwrite:
        raise FileExistsError(f"File already exists: {file_path}")
    
    # Create parent directories if needed
    if create_dirs:
        parent_dir = os.path.dirname(file_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
    
    # Determine data source
    if content is not None:
        # Direct content provided
        data_source = content
        total_size = len(content.encode(encoding)) if isinstance(content, str) else len(content)
        use_stdin = False
    else:
        # Read from stdin
        data_source = None
        total_size = 0
        use_stdin = True
    
    bytes_written = 0
    
    try:
        if use_stdin:
            # Read from stdin in streaming mode
            with open(file_path, 'wb') as f:
                while True:
                    chunk = sys.stdin.buffer.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_written += len(chunk)
                    if progress_callback:
                        progress_callback(bytes_written, total_size)
        else:
            # Write from content
            if isinstance(data_source, str):
                data_bytes = data_source.encode(encoding)
            else:
                data_bytes = data_source
            
            total_size = len(data_bytes)
            
            with open(file_path, 'wb') as f:
                offset = 0
                while offset < total_size:
                    chunk = data_bytes[offset:offset + chunk_size]
                    f.write(chunk)
                    bytes_written += len(chunk)
                    offset += chunk_size
                    if progress_callback:
                        progress_callback(bytes_written, total_size)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return {
            'success': True,
            'bytes_written': bytes_written,
            'file_path': os.path.abspath(file_path),
            'duration_ms': duration_ms
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'bytes_written': bytes_written,
            'file_path': os.path.abspath(file_path) if 'file_path' in locals() else None
        }


def write_file_large_stdin(
    file_path: str,
    chunk_size: int = 64 * 1024,
    create_dirs: bool = True,
    overwrite: bool = True
) -> dict:
    """
    Convenience function to write from stdin to a file.
    
    Reads all stdin data and writes to file_path.
    """
    return write_file_large(
        file_path=file_path,
        content=None,  # Triggers stdin mode
        chunk_size=chunk_size,
        create_dirs=create_dirs,
        overwrite=overwrite
    )


def read_from_stdin(max_size: Optional[int] = None) -> bytes:
    """
    Read all data from stdin.
    
    Args:
        max_size: Maximum bytes to read (None for unlimited)
    
    Returns:
        bytes read from stdin
    """
    if max_size:
        return sys.stdin.buffer.read(max_size)
    else:
        return sys.stdin.buffer.read()


def pipe_file_content(
    source_path: str,
    target_path: str,
    chunk_size: int = 64 * 1024,
    verify: bool = True
) -> dict:
    """
    Pipe content from one file to another (efficient large file copy).
    
    Args:
        source_path: Source file path
        target_path: Target file path
        chunk_size: Size of chunks for streaming
        verify: Verify written data matches source
    
    Returns:
        dict with success, bytes_copied, and verification status
    """
    import hashlib
    
    source_hash = None
    target_hash = None
    
    if verify:
        # Pre-compute source hash
        source_hash = hashlib.sha256()
        with open(source_path, 'rb') as sf:
            while chunk := sf.read(chunk_size):
                source_hash.update(chunk)
        source_hash = source_hash.hexdigest()
    
    # Copy with optional progress
    def progress(written, total):
        pass  # Could add progress tracking here
    
    result = write_file_large(
        file_path=target_path,
        content=None,
        chunk_size=chunk_size,
        overwrite=True
    )
    
    if verify and result['success']:
        # Verify target hash
        target_hash = hashlib.sha256()
        with open(target_path, 'rb') as tf:
            while chunk := tf.read(chunk_size):
                target_hash.update(chunk)
        target_hash = target_hash.hexdigest()
        
        if source_hash != target_hash:
            result['success'] = False
            result['error'] = 'Verification failed: hash mismatch'
            result['source_hash'] = source_hash
            result['target_hash'] = target_hash
            return result
    
    if verify:
        result['source_hash'] = source_hash
        result['target_hash'] = target_hash
    
    return result


# CLI entry point for stdin pipe writing
if __name__ == '__main__':
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Write stdin to file')
    parser.add_argument('file_path', help='Target file path')
    parser.add_argument('--chunk-size', type=int, default=64*1024, help='Chunk size in bytes')
    parser.add_argument('--no-create-dirs', action='store_true', help='Do not create parent directories')
    parser.add_argument('--no-overwrite', action='store_true', help='Do not overwrite existing file')
    parser.add_argument('--json', action='store_true', help='Output result as JSON')
    
    args = parser.parse_args()
    
    result = write_file_large(
        file_path=args.file_path,
        content=None,  # Read from stdin
        chunk_size=args.chunk_size,
        create_dirs=not args.no_create_dirs,
        overwrite=not args.no_overwrite
    )
    
    if args.json:
        print(json.dumps(result))
    else:
        if result['success']:
            print(f"Wrote {result['bytes_written']} bytes to {result['file_path']}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
            sys.exit(1)
