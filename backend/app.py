from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import pandas as pd # type: ignore
from multi_tool_agent.agent import (
    analyze_dataset,
    recommend_cleaning_steps,
    clean_dataset
)

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------------------- UPLOAD FILE ----------------------
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_location = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    analysis = analyze_dataset(file_location)
    suggestions = recommend_cleaning_steps(analysis["analysis"])

    return {
        "status": "uploaded",
        "file_path": file_location,
        "analysis": analysis,
        "recommendations": suggestions
    }


# ---------------------- CLEAN FILE ----------------------
@app.post("/clean")
async def clean_file(payload: dict):
    file_path = payload["file_path"]
    techniques = payload["techniques"]

    cleaned = clean_dataset(file_path=file_path, techniques=techniques)

    cleaned_df = pd.read_csv(cleaned["cleaned_file_path"])
    cleaned_records = cleaned_df.fillna("").to_dict(orient="records")

    return {
        "status": "success",
        "cleaned_data": cleaned_records
    }
