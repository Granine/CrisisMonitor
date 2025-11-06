# Twitter/X API Data Pipeline

A robust data ingestion pipeline for Twitter/X API v2 with automatic token rotation, comprehensive logging, and preprocessing for NLP/ML applications.

## Features

### 🔄 Automatic Token Rotation

- **Multiple API Keys**: Configure multiple bearer tokens for automatic failover
- **Smart Rotation**: Automatically switches to the next token when rate limited
- **Exhaustive Retry**: Tries all available tokens before failing
- **Rate Limit Tracking**: Logs reset times for each token

### 📊 Comprehensive Logging

- Console and file logging (`logs/x_api.log`)
- Request history tracking (`logs/x_request_history.json`)
- Successful response logging (`logs/x_success.json`)
- Detailed error messages and diagnostics

### 🛡️ Conservative Defaults

- **Default: 1 tweet per request** (preserves monthly quota)
- **Max: 10 tweets per request** (prevents quota exhaustion)
- **Max retries: 3** (reduced from 5 for safety)
- Designed for Free tier API limits

### 🧹 Text Preprocessing

- URL replacement/removal
- Mention and hashtag handling
- Non-English character filtering (keeps emojis)
- RT prefix removal
- Whitespace normalization

## Setup

### 1. Create `.env` File

Create a `.env` file in the `data_pipeline` directory:

```bash
# Comma-separated list of Twitter API Bearer Tokens
TWITTER_BEARER_TOKENS=token1,token2,token3
```

### 2. Install Dependencies

```bash
pip install requests
```

### 3. Run the Pipeline

```python
python x_api.py
```

## Usage

### Basic Example

```python
from x_api import ingest_tweets

ingest_tweets(
    number=1,                    # Number of tweets to fetch
    hashtag="datascience",       # Hashtag to search
    storage_path="data/tweets.jsonl",
    lang_hint="en",              # Language filter
    log_level=logging.INFO
)
```

### Advanced Example

```python
ingest_tweets(
    number=10,
    hashtag="AI",
    location={"country_code": "US"},  # Filter by location
    keywords=["machine learning", "deep learning"],
    include_retweets=False,
    start_time="2025-01-01T00:00:00Z",
    storage_path="data/ai_tweets.jsonl"
)
```

## Token Rotation System

### How It Works

1. **Initial Setup**: Loads all tokens from `TWITTER_BEARER_TOKENS`
2. **First Request**: Uses Token #1
3. **Rate Limited**: Automatically switches to Token #2
4. **Continue**: Tries all tokens in sequence
5. **All Exhausted**: Fails with detailed error message

### Environment Variables

The system checks for tokens in this order:

1. `TWITTER_BEARER_TOKENS` (recommended, plural)
2. `TWITTER_BEARER_TOKEN` (fallback, singular)
3. `X_BEARER_TOKEN` (fallback)

### Token Format

```bash
# Multiple tokens (comma-separated)
TWITTER_BEARER_TOKENS=AAAAAAAAAtoken1,AAAAAAAAAtoken2,AAAAAAAAAtoken3

# Single token (also works)
TWITTER_BEARER_TOKENS=AAAAAAAAAtoken1
```

## Rate Limits (Free Tier)

- **Search Endpoint**: 1 request per 15 minutes
- **Monthly Tweet Cap**: Limited number of tweets per month
- **Recommendation**: Use 1-10 tweets per request

## File Structure

```
data_pipeline/
├── x_api.py              # Main pipeline script
├── .env                  # API tokens (DO NOT COMMIT)
├── README.md             # This file
├── logs/                 # Auto-created
│   ├── x_api.log        # Detailed logs
│   ├── x_request_history.json
│   └── x_success.json
└── data/                 # Auto-created
    └── tweets.jsonl      # Output data
```

## Output Format

Each tweet is saved as a JSON object per line (JSONL):

```json
{
  "id": "1234567890",
  "text": "Original tweet text",
  "clean_text": "preprocessed text",
  "lang": "en",
  "label": true,
  "meta": {
    "created_at": "2025-01-01T12:00:00.000Z",
    "author_id": "123456",
    "author_username": "user123",
    "public_metrics": {...}
  },
  "raw": {...}
}
```

## Troubleshooting

### Rate Limit Errors

```
ERROR: All available tokens are rate limited
```

**Solution**: Wait 15 minutes or add more API keys

### No Tokens Found

```
RuntimeError: No bearer tokens found
```

**Solution**: Create `.env` file with `TWITTER_BEARER_TOKENS`

### Import Error

```
ModuleNotFoundError: No module named 'requests'
```

**Solution**: `pip install requests`

## Best Practices

1. **Start Small**: Use `number=1` for testing
2. **Multiple Keys**: Configure 2-3 API keys for rotation
3. **Monitor Logs**: Check `logs/x_api.log` for issues
4. **Backup Data**: Output files are atomic but keep backups
5. **Respect Limits**: Free tier has monthly caps

## Security

⚠️ **NEVER commit `.env` file to version control!**

Add to `.gitignore`:

```
.env
*.env
logs/
data/
```

## API Documentation

- [Twitter API v2 Documentation](https://developer.twitter.com/en/docs/twitter-api)
- [Rate Limits](https://developer.twitter.com/en/docs/twitter-api/rate-limits)
- [API Portal](https://developer.x.com/en/portal/dashboard)
