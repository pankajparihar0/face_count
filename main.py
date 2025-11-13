from typing import Union,List
import os
import asyncio

from fastapi import FastAPI,File, UploadFile,Form
from face_embed import process_registration_object
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/register_user")
async def register_user(username:str=Form(...),photos: List[UploadFile] = File(...)):

    base_path = "D:\in_out\\backend\photos"
    saved_paths = []
    for photo in photos:
        file_path = os.path.join(base_path, photo.filename)
        with open(file_path, "wb") as f:
            f.write(await photo.read())
        saved_paths.append(file_path)
    result = await asyncio.to_thread(
            process_registration_object, 
            username, 
            saved_paths
)