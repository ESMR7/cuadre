from fastapi import FastAPI

app = FastAPI(title="Cuadre")


@app.get("/health")
def health():
    return {"status": "ok"}
