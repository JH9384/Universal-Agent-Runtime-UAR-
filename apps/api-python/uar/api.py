from fastapi import FastAPI
from .models import UORObjectIn
from .store import create_record

app = FastAPI()


@app.post("/objects")
def create(obj: UORObjectIn):
    return create_record(
        obj.mediaType, obj.mode, obj.attributes, obj.links, obj.content
    )
