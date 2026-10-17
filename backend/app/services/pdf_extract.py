"""A bounded child process, never OCR and never uploads documents."""

import json
import resource
import sys

resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
try:
    from pypdf import PdfReader

    reader = PdfReader(sys.argv[1])
    if reader.is_encrypted:
        raise ValueError("encrypted")
    text = "\n".join((p.extract_text() or "")[:40000] for p in reader.pages[:50])[
        :500000
    ]
    print(
        json.dumps(
            {
                "text": text,
                "status": "partial_50_pages"
                if len(reader.pages) > 50
                else "text"
                if text.strip()
                else "no_text_layer",
            },
            ensure_ascii=False,
        )
    )
except Exception:
    print(json.dumps({"text": "", "status": "unavailable"}))
