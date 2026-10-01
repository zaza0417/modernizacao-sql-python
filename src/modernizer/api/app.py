from fastapi import FastAPI

app = FastAPI(title="Modernizer")

@app.get("/health")
def health() -> dict[str,str]:
    return {"status": "ok"}