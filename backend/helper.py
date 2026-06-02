"""
helper.py — Utility / text-processing functions for Jarvis.
"""

import re


def extract_yt_term(command: str) -> str | None:
    """
    Extract the search term from a playback voice command.

    Args:
        command: The full voice command string.

    Returns:
        The extracted search term, or None if the pattern doesn't match.

    Example:
        >>> extract_yt_term("play Shape of You on youtube")
        'Shape of You'
        >>> extract_yt_term("open youtube and play hello")
        'hello'
        >>> extract_yt_term("play Believer")
        'Believer'
    """
    command = command.lower().strip()

    # Pattern 1: open youtube and play X
    match1 = re.search(r"open\s+youtube\s+and\s+play\s+(.+)", command)
    if match1:
        return match1.group(1).strip()

    # Pattern 2: play X on youtube
    match2 = re.search(r"play\s+(.*?)\s+on\s+youtube", command)
    if match2:
        return match2.group(1).strip()

    # Pattern 3: play X (if not just "play youtube")
    match3 = re.search(r"^play\s+(.+)", command)
    if match3:
        term = match3.group(1).strip()
        if term == "youtube":
            return None
        return term

    return None


def remove_words(input_string: str, words_to_remove: list) -> str:
    """
    Remove specific words from a string (case-insensitive).

    Args:
        input_string:    The original string.
        words_to_remove: List of words to strip out.

    Returns:
        Cleaned string with specified words removed.

    Example:
        >>> remove_words("call John on whatsapp", ["call", "on", "whatsapp"])
        'John'
    """
    words = input_string.split()
    filtered = [w for w in words if w.lower() not in words_to_remove]
    return ' '.join(filtered)
