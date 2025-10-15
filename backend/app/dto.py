from fastapi import FastAPI
from pydantic import BaseModel
import random

app = FastAPI()

class TweetInput(BaseModel):
    tweet: str

class PredictionOutput(BaseModel):
    is_real_disaster: bool
