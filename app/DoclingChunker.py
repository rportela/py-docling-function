import re
from typing import Counter, List, Set


def is_good_chunk(chunk: str) -> bool:
    """
    Check if a chunk is a good candidate for processing.
    """
    text = chunk.strip().lower()
    boilerplate_keywords = [
        "no part may be copied",
        "is provided only to investment professionals",
        "this document is not a research report or research material",
        "this message is for information purposes only",
        "this document is being provided for the exclusive use of",
    ]
    is_boilerplate = any(kw in chunk for kw in boilerplate_keywords)
    has_metadata = bool(
        re.search(r"\bpage \d+\b", text)
        or re.search(r"\bphone\b|\bfax\b", text)
        or re.search(r"\+\d{1,3}[\s\-]?\d{3}", text)
        or re.search(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", text)
        or re.search(r"https?://[^\s]+", text)
    )
    return not is_boilerplate and not has_metadata


def clean_chunk(text: str, repeated_chunks: Set[str]) -> str:
    """
    Clean a chunk by removing repeated chunks and boilerplate text.
    """
    for rc in repeated_chunks:
        text = text.replace(rc, "")
    return text


def filter_chunks(chunks) -> List[str]:
    """
    Filter out duplicate chunks and boilerplate text.
    """
    chunk_counts = Counter(chunks)
    repeated_chunks = {c for c, count in chunk_counts.items() if count > 1}
    return [
        clean_chunk(chunk, repeated_chunks)
        for chunk in chunks
        if chunk_counts[chunk] == 1  # remove duplicates
        and is_good_chunk(chunk)  # remove boilerplate and metadata
    ]
