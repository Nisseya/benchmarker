from fastapi import FastAPI
from dotenv import load_dotenv

from api.routes.ws import router as ws_router
from api.routes.datasets import router as datasets_router
from api.routes.benchmarks import router as benchmarks_router
from api.routes.results import router as results_router
from api.routes.teams import router as teams_router
from api.routes.participants import router as participants_router

load_dotenv()

app = FastAPI(title="Hackathon Benchmark Platform")

app.include_router(ws_router)
app.include_router(datasets_router)
app.include_router(benchmarks_router)
app.include_router(results_router)
app.include_router(teams_router)
app.include_router(participants_router)