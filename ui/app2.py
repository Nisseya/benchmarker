import json
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple

import requests
import streamlit as st


API_URL_DEFAULT = "http://localhost:8000/bench/complete/stream"


def sse_iter(response: requests.Response) -> Iterator[Tuple[str, Dict[str, Any]]]:
    event: Optional[str] = None
    data_lines: List[str] = []

    for raw in response.iter_lines(decode_unicode=True):
        if raw is None:
            continue

        line = raw.strip()

        if line == "":
            if event and data_lines:
                data_str = "\n".join(data_lines)
                try:
                    payload = json.loads(data_str)
                except Exception:
                    payload = {"raw": data_str}
                yield event, payload
            event = None
            data_lines = []
            continue

        if line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:"):].strip())


def badge_correct(is_correct: Any) -> Tuple[str, str]:
    if is_correct is True:
        return "✅", "success"
    if is_correct is False:
        return "❌", "error"
    return "⚠️", "warning"


def safe_mean(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    return sum(xs) / len(xs)


def truncate(s: Optional[str], n: int = 120) -> str:
    if not s:
        return ""
    return s if len(s) <= n else s[: n - 1] + "…"


st.set_page_config(page_title="Global Bench SSE", layout="wide")
st.title("Global Bench — Live SSE Benchmark")

with st.sidebar:
    st.subheader("Request")
    api_url = st.text_input("API URL", API_URL_DEFAULT)

    model = st.text_input("Model", "Qwen/Qwen2.5-0.5B-Instruct")
    revision = st.text_input("Revision", "main")
    db_id = st.text_input("db_id", "soccer_3")
    limit = st.number_input("limit", min_value=1, max_value=100000, value=3)
    dtype = st.text_input("dtype", "float16")

    max_new_tokens = st.number_input("max_new_tokens", min_value=1, max_value=4096, value=256)
    temperature = st.number_input("temperature", min_value=0.0, max_value=2.0, value=0.0, step=0.1)
    top_p = st.number_input("top_p", min_value=0.0, max_value=1.0, value=1.0, step=0.05)
    do_sample = st.checkbox("do_sample", value=False)

    follow_latest = st.checkbox("Follow latest result", value=True)

    c1, c2 = st.columns(2)
    start_btn = c1.button("🚀 Start", use_container_width=True)
    stop_btn = c2.button("🛑 Stop", use_container_width=True)

st.caption("Tip: sur Streamlit, le stop “hard” le plus fiable est de refresh la page (ou relancer le run).")

meta_box = st.empty()
phase_box = st.empty()

colA, colB, colC, colD = st.columns(4)
m_acc = colA.empty()
m_execfail = colB.empty()
m_latency = colC.empty()
m_tps = colD.empty()

progress = st.progress(0, text="Idle")

left, right = st.columns([0.62, 0.38], gap="large")
table_container = left.container()
detail_container = right.container()

log_expander = st.expander("SSE logs (last 200)", expanded=False)
log_box = log_expander.empty()

if "run" not in st.session_state:
    st.session_state.run = None

if start_btn:
    st.session_state.run = {
        "running": True,
        "meta": None,
        "phase": "",
        "results": [],
        "logs": [],
        "expected": int(limit),
        "correct_count": 0,
        "scored_count": 0,
        "pred_exec_fail": 0,
        "gen_ms": [],
        "tps": [],
        "t0": time.time(),
    }

if stop_btn and st.session_state.run:
    st.session_state.run["running"] = False

run = st.session_state.run
if not run:
    phase_box.info("Idle")
    progress.progress(0, text="Idle")
    st.stop()

if not run.get("running"):
    phase_box.warning("Stopped (click Start to run again)")
    st.stop()

payload = {
    "model": model,
    "revision": revision,
    "db_id": db_id,
    "limit": int(limit),
    "offset": 0,
    "max_new_tokens": int(max_new_tokens),
    "temperature": float(temperature),
    "top_p": float(top_p),
    "do_sample": bool(do_sample),
    "dtype": dtype,
}

try:
    with requests.post(api_url, json=payload, stream=True, timeout=3600) as r:
        r.raise_for_status()

        while True:
            for event, data in sse_iter(r):
                if not run.get("running"):
                    phase_box.warning("Stopped")
                    progress.progress(0, text="Stopped")
                    st.stop()

                run["logs"].append(f"{event}: {data}")
                run["logs"] = run["logs"][-200:]
                log_box.text("\n".join(run["logs"]))

                if event == "meta":
                    run["meta"] = data
                    meta_box.json(data)

                elif event == "status":
                    run["phase"] = data.get("phase", "")
                    phase = run["phase"]

                    if phase in ("started", "downloading_or_cache_check", "model_ready_on_nvme", "loading_model_to_gpu", "model_loaded"):
                        phase_box.info(f"Phase: {phase}")
                    elif phase in ("loading_questions", "running", "warmup_done"):
                        phase_box.warning(f"Phase: {phase}")
                    else:
                        phase_box.write(f"Phase: {phase}")

                elif event == "result":
                    run["results"].append(data)

                    done = len(run["results"])
                    expected = max(1, int(run["expected"]))
                    pct = min(1.0, done / expected)
                    progress.progress(int(pct * 100), text=f"{done}/{expected} processed")

                    scoring = data.get("scoring") or {}
                    is_correct = scoring.get("is_correct")
                    pred_exec_success = scoring.get("pred_exec_success")

                    if pred_exec_success is False:
                        run["pred_exec_fail"] += 1
                    if is_correct is True:
                        run["correct_count"] += 1
                    if is_correct is not None:
                        run["scored_count"] += 1

                    metrics = data.get("metrics") or {}
                    tps = metrics.get("tokens_per_s")
                    gen_ms = data.get("gen_time_ms")

                    if isinstance(tps, (int, float)):
                        run["tps"].append(float(tps))
                        run["tps"] = run["tps"][-200]
                    if isinstance(gen_ms, (int, float)):
                        run["gen_ms"].append(float(gen_ms))
                        run["gen_ms"] = run["gen_ms"][-200]

                    scored = run["scored_count"]
                    ok = run["correct_count"]
                    acc = (ok / scored) if scored > 0 else 0.0

                    m_acc.metric("Accuracy (scored)", f"{acc*100:.1f}%", f"{ok}/{scored}")
                    m_execfail.metric("Pred exec fail", str(run["pred_exec_fail"]))

                    avg_gen = safe_mean(run["gen_ms"])
                    if avg_gen is not None:
                        m_latency.metric("Avg gen_time_ms", f"{avg_gen:.1f}")

                    avg_tps = safe_mean(run["tps"])
                    if avg_tps is not None:
                        m_tps.metric("Avg tokens/s", f"{avg_tps:.1f}")

                    rows = []
                    for it in run["results"]:
                        sc = it.get("scoring") or {}
                        icon, _kind = badge_correct(sc.get("is_correct"))
                        rows.append(
                            {
                                "idx": it.get("index"),
                                "qid": it.get("question_id"),
                                "ok": icon,
                                "pred_exec": sc.get("pred_exec_success"),
                                "gen_ms": round(it.get("gen_time_ms", 0), 1) if it.get("gen_time_ms") is not None else None,
                                "tps": round((it.get("metrics") or {}).get("tokens_per_s", 0), 1)
                                if (it.get("metrics") or {}).get("tokens_per_s") is not None
                                else None,
                                "match": sc.get("match_kind"),
                                "err": truncate(sc.get("pred_error"), 90),
                            }
                        )

                    table_container.dataframe(rows, use_container_width=True, height=420)

                    if run["results"]:
                        available = list(range(len(run["results"])))
                        default_idx = (len(available) - 1) if follow_latest else 0
                        default_idx = max(0, min(default_idx, len(available) - 1))

                        selected_idx = detail_container.selectbox(
                            "Select result index",
                            options=available,
                            index=default_idx,
                            key="selected_idx",
                        )

                        cur = run["results"][selected_idx]
                        sc = cur.get("scoring") or {}
                        icon, kind = badge_correct(sc.get("is_correct"))

                        if kind == "success":
                            detail_container.success(f"{icon} Result #{selected_idx} — correct")
                        elif kind == "error":
                            detail_container.error(f"{icon} Result #{selected_idx} — wrong")
                        else:
                            detail_container.warning(f"{icon} Result #{selected_idx} — unscored / exec fail")

                        detail_container.write("**Question ID:**", cur.get("question_id"))
                        detail_container.write("**db_id:**", cur.get("db_id"))

                        detail_container.write("**SQL (pred):**")
                        detail_container.code(cur.get("sql") or "", language="sql")

                        detail_container.write("**Gold SQL:**")
                        detail_container.code(cur.get("gold_sql") or "", language="sql")

                        if sc.get("pred_error"):
                            detail_container.write("**Pred error:**")
                            detail_container.code(sc["pred_error"])

                        detail_container.write("**Scoring:**")
                        detail_container.json(sc)
                    else:
                        detail_container.info("No results yet.")

                elif event == "done":
                    progress.progress(100, text="Done ✅")
                    phase_box.success("Done ✅")
                    run["running"] = False
                    st.stop()

                elif event == "error":
                    phase_box.error(f"Error: {data}")
                    run["running"] = False
                    st.stop()

            # If stream ends without explicit "done"
            phase_box.warning("Stream ended")
            run["running"] = False
            st.stop()

except Exception as e:
    st.error(f"Stream error: {type(e).__name__}: {e}")
    if run:
        run["running"] = False
