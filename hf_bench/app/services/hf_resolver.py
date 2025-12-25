from __future__ import annotations

import re
from typing import Optional, Tuple
from fastapi import HTTPException

HF_URL_RE = re.compile(r"^https?://huggingface\.co/([^/\s]+/[^/\s]+)(?:/.*)?$")

def parse_hf_input(model: str, revision: Optional[str]) -> Tuple[str, Optional[str]]:
    model = model.strip()
    m = HF_URL_RE.match(model)
    if m:
        model_id = m.group(1)
        inferred = None
        tree = re.search(r"/tree/([^/\s]+)", model)
        if tree:
            inferred = tree.group(1)
        res = re.search(r"/resolve/([^/\s]+)/", model)
        if res:
            inferred = res.group(1)
        if revision is None:
            revision = inferred
        return model_id, revision

    if "/" in model and " " not in model:
        return model, revision

    raise HTTPException(status_code=400, detail="Invalid HF model input. Provide 'org/model' or a huggingface.co URL.")
