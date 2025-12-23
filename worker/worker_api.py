from fastapi import FastAPI, Body
import time
import psutil
import os
import traceback

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok", "service": "benchmark-worker"}  

@app.post("/execute")
async def execute_code(payload: dict = Body(...)):
    code = payload.get("code")
    language = payload.get("language", "Python").lower()
    
    process = psutil.Process(os.getpid())
    start_mem = process.memory_info().rss / (1024 * 1024)
    start_time = time.perf_counter()
    
    captured_state = {}
    status = "success"
    error = None
    
    try:
        if language == "python":
            # Environnement local pour exec()
            local_vars = {}
            exec(code, {"__builtins__": __builtins__}, local_vars)
            # On capture les variables créées (Silver Standard)
            captured_state = {k: str(v) for k, v in local_vars.items() if not k.startswith('_')}
        else:
            status = "unsupported_language"
            
    except Exception as e:
        status = "error"
        error = traceback.format_exc()

    # Mesures finales
    end_time = time.perf_counter()
    end_mem = process.memory_info().rss / (1024 * 1024)

    return {
        "status": status,
        "exec_time": (end_time - start_time) * 1000,
        "ram": end_mem - start_mem,
        "cpu": psutil.cpu_percent(),
        "captured_state": captured_state,
        "error": error
    }