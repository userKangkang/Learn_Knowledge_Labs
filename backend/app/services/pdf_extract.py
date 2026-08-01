from pathlib import Path

from pypdf import PdfReader


def extract_pdf_text(path: Path, *, max_chars: int = 200_000) -> str:
    reader = PdfReader(str(path))
    chunks: list[str] = []
    total = 0
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        piece = f"--- 第 {index} 页 ---\n{text}"
        if total + len(piece) > max_chars:
            remaining = max_chars - total
            if remaining > 0:
                chunks.append(piece[:remaining])
            chunks.append("\n…（正文过长，已截断）")
            break
        chunks.append(piece)
        total += len(piece) + 2
    return "\n\n".join(chunks).strip()
