from fastapi import FastAPI
from .dto import TweetInput, PredictionOutput
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="FastAPI + Postgres App")


app = FastAPI()

# Define allowed origins (frontend domains)
origins = [
    "http://localhost:3000",     # local dev (React/Vite/Next.js)
    "https://disaster-classification-mscac.netlify.app/",  # deployed frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # List of allowed origins
    allow_credentials=True,
    allow_methods=["*"],              # Allow all HTTP methods
    allow_headers=["*"],              # Allow all headers
)

@app.get("/")
def home():
    return {"message": "Hello FastAPI"}


@app.post("/predict-tweet", response_model=PredictionOutput)
def predict_tweet(input: TweetInput):
    # Mock prediction (random True/False for now)
    if any(map(lambda kw: kw in input.tweet.lower(), ["help", "fire", "disaster"])):
        return PredictionOutput(is_real_disaster=True)
    
    return PredictionOutput(is_real_disaster=False)

