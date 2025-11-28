def humanize_bytes(value: float) -> str:
    """
    Convert a byte count into a human-readable string (e.g., 1K, 1M, 1G).
    """
    if value == 0:
        return "0B"
    
    suffixes = ['B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y']
    i = 0
    while value >= 1024 and i < len(suffixes) - 1:
        value /= 1024.0
        i += 1
        
    return f"{value:.1f}{suffixes[i]}"
