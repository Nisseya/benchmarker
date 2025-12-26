from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.ws import router as ws_router
from app.routes.datasets import router as datasets_router
from app.routes.benchmarks import router as benchmarks_router
from app.routes.results import router as results_router
from app.routes.teams import router as teams_router
from app.routes.participants import router as participants_router
from app.routes.hackathons import router as hackathon_router
from app.routes.bench_routes import router as sse_bench_router

from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="Hackathon Benchmark Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow everything for now
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sse_bench_router, tags=["SSE ROUTER"])
app.include_router(ws_router)
app.include_router(datasets_router)
app.include_router(benchmarks_router)
app.include_router(hackathon_router)
app.include_router(results_router)
app.include_router(teams_router)
app.include_router(participants_router)