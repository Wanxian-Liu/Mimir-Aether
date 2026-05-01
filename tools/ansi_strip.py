#!/usr/bin/env python3
"""
ansi_strip - Strip ANSI escape sequences from text

Used to clean terminal output for logging and display.
"""

import re


# ANSI escape sequence pattern
ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')


def strip_ansi(text: str) -> str:
    """
    Remove ANSI escape sequences from text.
    
    Args:
        text: Text that may contain ANSI escape sequences
        
    Returns:
        Text with ANSI sequences removed
    """
    if not text:
        return text
    return ANSI_ESCAPE.sub('', text)


def strip_ansi_preserve_urls(text: str) -> str:
    """
    Remove ANSI escape sequences but preserve URLs.
    
    Args:
        text: Text that may contain ANSI escape sequences
        
    Returns:
        Text with ANSI sequences removed, URLs intact
    """
    # First protect URLs by temporarily replacing them
    urls = []
    
    def protect_url(match):
        urls.append(match.group(0))
        return f"__URL_{len(urls) - 1}__"
    
    # Protect URLs
    url_pattern = re.compile(r'https?://[^\s]+')
    text = url_pattern.sub(protect_url, text)
    
    # Strip ANSI
    text = strip_ansi(text)
    
    # Restore URLs
    for i, url in enumerate(urls):
        text = text.replace(f"__URL_{i}__", url)
    
    return text
