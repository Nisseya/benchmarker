import json
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Iterable

import requests
import streamlit as st


SSE_URL_DEFAULT = "http://localhost:8000/bench/complete/stream"


def _safe_json_loads(s: str) -> Optional[dict]:
    try:
        return json.loads(s)
    except Exception:
        return None


def parse_sse_frames(lines_iter: Iterable[bytes]):
    event_name: Optional[str] = None
    data_lines: List[str] = []

    for raw in lines_iter:
        if raw is None:
            continue

        line = raw.decode("utf-8", errors="replace").rstrip("\n")

        if line == "":
            if event_name is None and not data_lines:
                continue
            data_str = "\n".join(data_lines).strip()
            data_json = _safe_json_loads(data_str) if data_str else None
            yield event_name, data_json
            event_name = None
            data_lines = []
            continue

        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
            continue

        if line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
            continue

    if event_name is not None or data_lines:
        data_str = "\n".join(data_lines).strip()
        data_json = _safe_json_loads(data_str) if data_str else None
        yield event_name, data_json


def extract_sql_from_markdown_fence(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text.strip()


@dataclass
class TryView:
    index: int
    question_id: Optional[int] = None
    status: str = "pending"
    title: str = ""
    sql: str = ""
    raw_answer: str = ""
    gen_time_ms: Optional[float] = None
    tokens_per_s: Optional[float] = None
    new_tokens: Optional[int] = None
    exec_time_ms: Optional[float] = None
    cpu_percent: Optional[float] = None
    ram_delta_mb: Optional[float] = None
    gpu_allocated_mb: Optional[float] = None
    gpu_reserved_mb: Optional[float] = None
    pred_error: Optional[str] = None
    match_kind: Optional[str] = None


@dataclass
class RunState:
    run_id: Optional[str] = None
    phase: str = "idle"
    expected: int = 0
    received: int = 0
    tries: Dict[int, TryView] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    done: bool = False
    done_status: Optional[str] = None


def status_to_badge(status: str) -> Tuple[str, str]:
    if status == "success":
        return "SUCCESS", "success"
    if status == "warning":
        return "WARNING", "warning"
    if status == "error":
        return "ERROR", "error"
    if status == "running":
        return "RUNNING", "info"
    return "PENDING", "info"


def classify_try(scoring: Optional[dict]) -> str:
    if not scoring:
        return "running"
    if scoring.get("pred_exec_success") is True:
        return "success"
    if scoring.get("match_kind") == "exec_failed" or scoring.get("pred_error"):
        return "error"
    return "warning"


def post_stream_sse(url: str, payload: dict, timeout_s: int = 600):
    headers = {
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
    }
    with requests.post(url, json=payload, headers=headers, stream=True, timeout=timeout_s) as r:
        r.raise_for_status()
        yield from parse_sse_frames(r.iter_lines(chunk_size=1, decode_unicode=False))


def _metric(v: Optional[float], fmt: str) -> str:
    if v is None:
        return "—"
    try:
        return fmt.format(v)
    except Exception:
        return str(v)


st.set_page_config(page_title="Bench Stream UI", layout="wide")
st.title("Bench Complete Stream — SSE UI")

with st.sidebar:
    st.subheader("Endpoint")
    url = st.text_input("SSE URL", value=SSE_URL_DEFAULT)

    st.subheader("Payload")
    default_payload = {
        "model": "Qwen/Qwen2.5-0.5B-Instruct",
        "revision": "main",
        "db_id": "soccer_3",
        "limit": 3,
        "offset": 0,
        "max_new_tokens": 256,
        "temperature": 0.0,
        "top_p": 1.0,
        "do_sample": False,
        "dtype": "float16",
    }

    payload_str = st.text_area(
        "JSON payload",
        value=json.dumps(default_payload, indent=2),
        height=260,
    )

    col_a, col_b = st.columns(2)
    run_btn = col_a.button("Run", type="primary", use_container_width=True)
    clear_btn = col_b.button("Clear", use_container_width=True)

if "run_state" not in st.session_state:
    st.session_state.run_state = RunState()

if clear_btn:
    st.session_state.run_state = RunState()
    st.rerun()

payload = _safe_json_loads(payload_str)
if payload is None:
    st.error("Payload JSON is invalid.")
    st.stop()

top_row = st.container()
progress_ph = st.empty()
phase_ph = st.empty()
tries_ph = st.empty()
raw_ph = st.expander("Raw SSE events (debug)", expanded=False)
raw_log_ph = raw_ph.empty()

if run_btn:
    st.session_state.run_state = RunState(
        expected=int(payload.get("limit", 0) or 0),
        started_at=time.time(),
    )
    rs: RunState = st.session_state.run_state

    with top_row:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("db_id", str(payload.get("db_id", "")))
        c2.metric("model", str(payload.get("model", "")))
        c3.metric("revision", str(payload.get("revision", "")))
        c4.metric("limit", str(payload.get("limit", "")))

    raw_events: List[str] = []

    try:
        for ev_name, data in post_stream_sse(url, payload):
            raw_events.append(
                f"event={ev_name} data={json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else data}"
            )
            raw_log_ph.code("\n".join(raw_events[-200:]), language="text")

            if ev_name == "meta" and isinstance(data, dict):
                rs.run_id = data.get("run_id") or rs.run_id

            if ev_name == "status" and isinstance(data, dict):
                rs.phase = str(data.get("phase") or rs.phase)

            if ev_name == "result" and isinstance(data, dict):
                idx = int(data.get("index", 0))
                tv = rs.tries.get(idx) or TryView(index=idx)

                tv.question_id = data.get("question_id", tv.question_id)
                tv.raw_answer = data.get("raw_answer") or tv.raw_answer

                sql_field = data.get("sql") or ""
                if sql_field:
                    tv.sql = extract_sql_from_markdown_fence(sql_field)
                else:
                    tv.sql = extract_sql_from_markdown_fence(tv.raw_answer)

                tv.gen_time_ms = data.get("gen_time_ms", tv.gen_time_ms)

                metrics = data.get("metrics") or {}
                if isinstance(metrics, dict):
                    tv.tokens_per_s = metrics.get("tokens_per_s", tv.tokens_per_s)
                    tv.new_tokens = metrics.get("new_tokens", tv.new_tokens)
                    tv.exec_time_ms = metrics.get("exec_time_ms", tv.exec_time_ms)
                    tv.cpu_percent = metrics.get("cpu_percent", tv.cpu_percent)
                    tv.ram_delta_mb = metrics.get("ram_delta_mb", tv.ram_delta_mb)
                    gpu = metrics.get("gpu") or {}
                    if isinstance(gpu, dict):
                        tv.gpu_allocated_mb = gpu.get("allocated_mb", tv.gpu_allocated_mb)
                        tv.gpu_reserved_mb = gpu.get("reserved_mb", tv.gpu_reserved_mb)

                scoring = data.get("scoring") or {}
                if isinstance(scoring, dict):
                    tv.pred_error = scoring.get("pred_error", tv.pred_error)
                    tv.match_kind = scoring.get("match_kind", tv.match_kind)
                    tv.status = classify_try(scoring)
                else:
                    tv.status = "warning"

                tv.title = f"Try #{idx} (question_id={tv.question_id})"
                rs.tries[idx] = tv
                rs.received = len(rs.tries)

            if ev_name == "done" and isinstance(data, dict):
                rs.done = True
                rs.done_status = data.get("status")
                rs.phase = "done"

            expected = max(rs.expected, 1)
            p = min(rs.received / expected, 1.0)
            progress_ph.progress(p, text=f"{rs.received}/{rs.expected} results")
            phase_ph.info(f"run_id: {rs.run_id or '—'} • phase: {rs.phase}")

            with tries_ph.container():
                st.subheader("Attempts")

                for i in range(rs.expected):
                    tv = rs.tries.get(i) or TryView(index=i, status="pending", title=f"Try #{i}")
                    label, badge_state = status_to_badge(tv.status)

                    exp_title = f"[{label}] {tv.title}"
                    with st.expander(exp_title, expanded=(tv.status in ("error", "warning"))):
                        if badge_state == "success":
                            st.success(f"Status: {label}")
                        elif badge_state == "warning":
                            st.warning(f"Status: {label}")
                        elif badge_state == "error":
                            st.error(f"Status: {label}")
                        else:
                            st.info(f"Status: {label}")

                        st.markdown("**Generated SQL**")
                        st.code(tv.sql or "", language="sql")

                        if tv.raw_answer:
                            st.markdown("**Raw answer**")
                            st.code(tv.raw_answer, language="text")

                        if tv.pred_error:
                            st.markdown("**Execution / scoring error**")
                            st.code(tv.pred_error, language="text")

                        st.markdown("**Metrics**")
                        mcols = st.columns(6)
                        mcols[0].metric("gen_time_ms", _metric(tv.gen_time_ms, "{:.2f}"))
                        mcols[1].metric("tokens/s", _metric(tv.tokens_per_s, "{:.2f}"))
                        mcols[2].metric("new_tokens", str(tv.new_tokens) if tv.new_tokens is not None else "—")
                        mcols[3].metric("exec_time_ms", _metric(tv.exec_time_ms, "{:.2f}"))
                        mcols[4].metric("cpu_%", _metric(tv.cpu_percent, "{:.1f}"))
                        mcols[5].metric("ram_Δ_mb", _metric(tv.ram_delta_mb, "{:.2f}"))

                        gcols = st.columns(3)
                        gcols[0].metric("gpu_alloc_mb", _metric(tv.gpu_allocated_mb, "{:.2f}"))
                        gcols[1].metric("gpu_reserved_mb", _metric(tv.gpu_reserved_mb, "{:.2f}"))
                        gcols[2].metric("match_kind", tv.match_kind or "—")

            if rs.done and rs.received >= rs.expected:
                break

        if rs.done_status == "ok":
            st.success("Run finished (status=ok).")
        elif rs.done:
            st.warning(f"Run finished (status={rs.done_status}).")
        else:
            st.warning("Stream ended without a done event.")

    except requests.RequestException as e:
        st.error(f"HTTP/SSE error: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
else:
    rs: RunState = st.session_state.run_state
    st.info("Configure payload and click **Run**.")
    if rs.tries:
        progress_ph.progress(min(rs.received / max(rs.expected, 1), 1.0), text=f"{rs.received}/{rs.expected} results")
        phase_ph.info(f"run_id: {rs.run_id or '—'} • phase: {rs.phase}")
