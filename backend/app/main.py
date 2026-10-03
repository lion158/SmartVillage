from fastapi import FastAPI

app = FastAPI(
    title="Village City API",
    description="Demand-responsive public transport for rural communities.",
    version="0.1.0",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to the Village City API"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
