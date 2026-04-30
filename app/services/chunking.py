from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    text: str
    page_number: int | None
    token_estimate: int


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_pages(pages: list[tuple[str, int | None]], chunk_size: int, overlap: int) -> list[TextChunk]:
    if overlap >= chunk_size:
        raise ValueError('overlap must be smaller than chunk_size')

    chunks: list[TextChunk] = []
    for page_text, page_number in pages:
        normalized = ' '.join(page_text.split())
        start = 0
        while start < len(normalized):
            end = min(start + chunk_size, len(normalized))
            candidate = normalized[start:end]
            if end < len(normalized):
                last_sentence = max(candidate.rfind('. '), candidate.rfind('? '), candidate.rfind('! '))
                if last_sentence > chunk_size * 0.55:
                    end = start + last_sentence + 1
                    candidate = normalized[start:end]
            text = candidate.strip()
            if len(text) > 40:
                chunks.append(TextChunk(text=text, page_number=page_number, token_estimate=estimate_tokens(text)))
            if end == len(normalized):
                break
            start = max(0, end - overlap)
    return chunks
