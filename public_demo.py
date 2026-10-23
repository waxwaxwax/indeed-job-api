from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Indeed Job API - Public Demo", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://agreeable-coast-0f1a24f10.6.azurestaticapps.net"],
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)

class Job(BaseModel):
    id: int
    title: str
    location: str
    salary: int

JOBS = [
    Job(id=1, title="Technical Support", location="Tokyo", salary=4500000),
    Job(id=2, title="Web Engineer", location="Osaka", salary=6000000),
    Job(id=3, title="IT Support", location="Remote", salary=5000000),
]

@app.get("/")
def home():
    return {"message": "Public Job API is running"}

@app.get("/jobs", response_model=list[Job])
def list_jobs():
    return JOBS

@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: int):
    for job in JOBS:
        if job.id == job_id:
            return job
    raise HTTPException(status_code=404, detail="Job not found")
