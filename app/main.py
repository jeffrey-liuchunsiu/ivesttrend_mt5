# main.py
from fastapi import FastAPI, Depends
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from test_instance_dependencies import get_test_instances  # Import from dependencies.py

from routers.create_test import router as create_test_router

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app = FastAPI()


app.include_router(create_test_router, dependencies=[Depends(get_test_instances)])


# You may also include additional routers or middleware heres