from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

import random

app = FastAPI()

class TweetInput(BaseModel):
    text: str

class PredictionOutput(BaseModel):
    id: str
    cleaned_tweet: str
    is_real_disaster: bool
    disaster_probability: float
    evaluated_at: datetime