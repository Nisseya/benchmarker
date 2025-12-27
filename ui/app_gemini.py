import streamlit as st
import requests
import json
import sseclient

st.set_page_config(page_title="SQL Model Benchmarker", layout="wide")

st.title("📊 SQL Model Benchmark Runner")

# Configuration Sidebar
with st.sidebar:
    st.header("Endpoint Configuration")
    url = st.text_input("Endpoint URL", "http://localhost:8000/bench/complete/stream")
    
    st.header("Parameters")
    payload = {
        "model": "Qwen/Qwen2.5-0.5B-Instruct",
        "revision": "main",
        "db_id": "soccer_3",
        "limit": st.number_input("Limit", value=3),
        "offset": st.number_input("Offset", value=0),
        "max_new_tokens": 256,
        "temperature": 0.0,
        "top_p": 1.0,
        "do_sample": False,
        "dtype": "float16"
    }

if st.button("Run Benchmark", type="primary"):
    # Initialize Progress and Containers
    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.container()
    
    try:
        # Use stream=True for SSE
        response = requests.post(url, json=payload, stream=True)
        client = sseclient.SSEClient(response)

        # Track total items for the progress bar
        total_items = payload["limit"]
        completed_items = 0

        for event in client.events():
            if not event.data:
                continue
                
            data = json.loads(event.data)
            
            # Handle status updates
            if event.event == "status":
                status_text.info(f"Phase: {data.get('phase')}...")
            
            # Handle individual result results
            elif event.event == "result":
                completed_items += 1
                progress = min(completed_items / total_items, 1.0)
                progress_bar.progress(progress)
                
                scoring = data.get("scoring", {})
                is_success = scoring.get("pred_exec_success", False)
                
                # Visual styling based on success
                with results_container:
                    color = "green" if is_success else "red"
                    icon = "✅" if is_success else "❌"
                    
                    with st.expander(f"{icon} Question {data['question_id']} - Result", expanded=not is_success):
                        st.markdown(f"**Status:** :{color}[{'Success' if is_success else 'Execution Failed'}]")
                        
                        # Display SQL
                        st.code(data.get("sql", "No SQL generated"), language="sql")
                        
                        # Display Error if any
                        if not is_success:
                            st.error(f"Error: {scoring.get('pred_error')}")
                        
                        # Metrics breakdown
                        cols = st.columns(3)
                        metrics = data.get("metrics", {})
                        cols[0].metric("Gen Time", f"{metrics.get('gen_time_ms', 0):.2f}ms")
                        cols[1].metric("Tokens/s", f"{metrics.get('tokens_per_s', 0):.2f}")
                        cols[2].metric("New Tokens", metrics.get("new_tokens", 0))

            elif event.event == "done":
                status_text.success("Benchmark Complete!")
                progress_bar.progress(1.0)

    except Exception as e:
        st.error(f"Connection Error: {e}")