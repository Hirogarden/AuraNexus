import hashlib
import math
import re
from typing import List


def embed_text(text: str, dim: int = 128) -> List[float]:
    """
    Converts text to a normalized 128-dimensional vector using character
    n-gram frequency hashing.  No external model required; produces consistent
    vectors for similar text, allowing HiRAG clustering.
    """
    text = re.sub(r"\s+", " ", text.lower().strip())
    if not text:
        return [0.0] * dim

    freq: List[float] = [0.0] * dim
    tokens = re.split(r"\W+", text)

    for token in tokens:
        if not token:
            continue
        # Unigram contributes 1.0
        bucket = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % dim
        freq[bucket] += 1.0
        # Character bigrams contribute 0.5
        for i in range(len(token) - 1):
            bigram = token[i : i + 2]
            bucket = int(hashlib.md5(bigram.encode("utf-8")).hexdigest(), 16) % dim
            freq[bucket] += 0.5
        # Character trigrams contribute 0.25
        for i in range(len(token) - 2):
            trigram = token[i : i + 3]
            bucket = int(hashlib.md5(trigram.encode("utf-8")).hexdigest(), 16) % dim
            freq[bucket] += 0.25

    norm = math.sqrt(sum(v * v for v in freq))
    if norm == 0.0:
        return [0.0] * dim
    return [v / norm for v in freq]
