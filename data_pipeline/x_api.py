#!/usr/bin/env python3
"""
Simple X (Twitter API v2) data ingestion and preprocessing pipeline for NLP/ML.

Requirements:
- Python 3.8+
- requests (pip install requests)

Authentication:
- Set environment variable TWITTER_BEARER_TOKENS with comma-separated list of tokens
- Tokens will automatically rotate when rate limits are hit
- Example: TWITTER_BEARER_TOKENS=token1,token2,token3

Token Rotation:
- The system tries each token in order when rate limited
- Automatically switches to the next available token
- Only fails when ALL tokens have been tried and are rate limited
- Logs which token is currently in use and which have been tried

Notes:
- This uses the "Recent Search" endpoint. To run at scale you need appropriate API access/limits.
- Default: 1 tweet per request to preserve monthly quota (Free tier limitation)
- Location filtering on X is imperfect because most tweets lack precise geo. This implementation:
  - Optionally uses the point_radius operator if you supply geo_point (lat, lon) and radius_km.
  - Additionally supports post-filtering by place name or country code if place information is present.

Cross-platform:
- File I/O is atomic and compatible with Linux/macOS/Windows.

Logging:
- Uses the standard logging module. Adjust level in setup_logger if needed.
- Logs to console and logs/x_api.log
- Request history logged to logs/x_request_history.json
- Successful responses logged to logs/x_success.json
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from html import unescape as html_unescape
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import requests

# Load environment variables from .env file
def load_env_file(env_path: Union[str, Path] = ".env") -> None:
    """Load environment variables from .env file if it exists."""
    env_file = Path(env_path)
    if env_file.exists():
        with env_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

# Load .env file from the script's directory
script_dir = Path(__file__).parent
env_path = script_dir / ".env"
load_env_file(env_path)

# -----------------------
# Logging configuration
# -----------------------
def setup_logger(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("tweet_ingest")
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # File handler for all logs
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "x_api.log", encoding="utf-8")
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
            "%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    logger.setLevel(level)
    return logger


LOGGER = setup_logger()


# -----------------------
# Response logging helpers
# -----------------------
def log_response_to_file(response_data: Dict[str, Any], filepath: Union[str, Path]) -> None:
    """
    Append a response record to a JSON file.
    Each record includes timestamp and the response data.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": response_data
    }
    
    # Read existing data
    existing_data = []
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = [existing_data]
        except (json.JSONDecodeError, Exception) as e:
            LOGGER.warning("Could not read existing log file %s: %s. Starting fresh.", path, e)
            existing_data = []
    
    # Append new record
    existing_data.append(record)
    
    # Write back
    with path.open("w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    
    LOGGER.debug("Logged response to %s", path)


# -----------------------
# Token Rotation System
# -----------------------
class TokenRotator:
    """
    Manages rotation of multiple API bearer tokens.
    Automatically switches to the next token when rate limits are hit.
    Cycles through all tokens until all are exhausted.
    """
    def __init__(self, tokens: Optional[List[str]] = None):
        if tokens is None:
            # Load from environment variable (comma-separated)
            # Try TWITTER_BEARER_TOKENS first (plural), then fallback to singular
            token_str = os.getenv("TWITTER_BEARER_TOKENS") or os.getenv("TWITTER_BEARER_TOKEN") or os.getenv("X_BEARER_TOKEN")
            if not token_str:
                raise RuntimeError(
                    "No bearer tokens found. Set TWITTER_BEARER_TOKENS env var (comma-separated list)."
                )
            self.tokens = [t.strip() for t in token_str.split(",") if t.strip()]
        else:
            self.tokens = tokens
        
        if not self.tokens:
            raise RuntimeError("No valid bearer tokens provided.")
        
        self.current_index = 0
        self.rate_limit_info = {}  # Track rate limit info per token
        self.tried_tokens = set()  # Track which tokens we've tried
        LOGGER.info("Initialized TokenRotator with %d token(s)", len(self.tokens))
    
    def get_current_token(self) -> str:
        """Get the current active token."""
        return self.tokens[self.current_index]
    
    def rotate(self) -> bool:
        """
        Rotate to the next token.
        Returns True if rotation was successful, False if all tokens have been tried.
        """
        if len(self.tokens) == 1:
            LOGGER.warning("Only one token available - cannot rotate")
            self.tried_tokens.add(0)
            return False
        
        # Mark current token as tried
        self.tried_tokens.add(self.current_index)
        
        # Check if we've tried all tokens
        if len(self.tried_tokens) >= len(self.tokens):
            LOGGER.error("All %d tokens have been tried and are rate limited", len(self.tokens))
            return False
        
        old_index = self.current_index
        # Move to next token
        self.current_index = (self.current_index + 1) % len(self.tokens)
        
        LOGGER.info("Rotated from token %d to token %d (%d/%d tokens tried)", 
                   old_index + 1, self.current_index + 1, 
                   len(self.tried_tokens), len(self.tokens))
        return True
    
    def record_rate_limit(self, reset_timestamp: int) -> None:
        """Record rate limit info for current token."""
        token_key = f"token_{self.current_index}"
        self.rate_limit_info[token_key] = {
            "reset_timestamp": reset_timestamp,
            "reset_time": datetime.fromtimestamp(reset_timestamp).strftime("%Y-%m-%d %H:%M:%S")
        }
        LOGGER.info("Token %d rate limited until %s", 
                   self.current_index + 1, 
                   self.rate_limit_info[token_key]["reset_time"])
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of all tokens."""
        return {
            "total_tokens": len(self.tokens),
            "current_token_index": self.current_index + 1,
            "tokens_tried": len(self.tried_tokens),
            "rate_limit_info": self.rate_limit_info
        }


# -----------------------
# Twitter/X API Client
# -----------------------
@dataclass
class TwitterClient:
    """
    Minimal v2 API client for X (Twitter).

    Attributes:
        bearer_token: API Bearer Token. If None, uses TokenRotator from env var.
        base_url: API base URL. Defaults to https://api.x.com
        timeout: per-request timeout seconds.
        max_retries: retries for transient errors and 429 rate limits.
        backoff_factor: backoff multiplier for retries.
    """
    bearer_token: Optional[str] = None
    base_url: str = "https://api.x.com"
    timeout: int = 30
    max_retries: int = 3  # Reduced from 5 to be more conservative
    backoff_factor: float = 1.5

    def __post_init__(self):
        if not self.bearer_token:
            # Use token rotator
            self.token_rotator = TokenRotator()
            self.bearer_token = self.token_rotator.get_current_token()
        else:
            self.token_rotator = None
        
        self.session = requests.Session()
        self._update_session_token()
    
    def _update_session_token(self):
        """Update the session with the current bearer token."""
        self.session.headers.update({"Authorization": f"Bearer {self.bearer_token}"})

    def get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        GET request with basic retry + backoff for 429/5xx.

        Raises requests.HTTPError for unrecoverable errors.
        """
        url = f"{self.base_url}{path}"
        attempt = 0
        
        # Log request details
        LOGGER.info("Making request to %s with params: %s", url, json.dumps(params, default=str))
        
        while True:
            attempt += 1
            request_start = time.time()
            
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                request_duration = time.time() - request_start
                
                # Log all request/response info
                request_log = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "attempt": attempt,
                    "method": "GET",
                    "url": url,
                    "params": params,
                    "status_code": resp.status_code,
                    "duration_seconds": round(request_duration, 3),
                    "headers": dict(resp.headers),
                }
                
                # Add response body for non-200 responses
                if resp.status_code != 200:
                    try:
                        request_log["response_body"] = resp.json()
                    except Exception:
                        request_log["response_body"] = resp.text
                
                # Log to request history file
                log_response_to_file(request_log, "logs/x_request_history.json")
                
            except requests.RequestException as e:
                request_duration = time.time() - request_start
                LOGGER.error("Request exception on attempt %d after %.2fs: %s", attempt, request_duration, e)
                
                # Log failed request
                error_log = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "attempt": attempt,
                    "method": "GET",
                    "url": url,
                    "params": params,
                    "error": str(e),
                    "duration_seconds": round(request_duration, 3),
                }
                log_response_to_file(error_log, "logs/x_request_history.json")
                
                if attempt >= self.max_retries:
                    LOGGER.error("Request failed after %d retries: %s", self.max_retries, e)
                    raise
                sleep_s = self.backoff_factor * attempt
                LOGGER.warning("Request exception: %s. Retrying in %.1fs", e, sleep_s)
                time.sleep(sleep_s)
                continue

            if resp.status_code == 200:
                response_json = resp.json()
                
                # Log successful response
                LOGGER.info("Successful response (200) in %.2fs. Data count: %d", 
                           request_duration, len(response_json.get("data", [])))
                
                success_log = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "attempt": attempt,
                    "url": url,
                    "params": params,
                    "status_code": 200,
                    "duration_seconds": round(request_duration, 3),
                    "result_count": len(response_json.get("data", [])),
                    "meta": response_json.get("meta", {}),
                    "response": response_json,
                }
                log_response_to_file(success_log, "logs/x_success.json")
                
                return response_json

            if resp.status_code == 429:
                # Respect rate limit reset if provided
                reset = resp.headers.get("x-rate-limit-reset")
                remaining = resp.headers.get("x-rate-limit-remaining", "unknown")
                limit = resp.headers.get("x-rate-limit-limit", "unknown")
                
                # Try to get error details from response body
                try:
                    error_body = resp.json()
                    error_msg = error_body.get("detail") or error_body.get("title") or str(error_body)
                except Exception:
                    error_msg = resp.text
                
                LOGGER.warning("Rate limited (429). Remaining: %s, Limit: %s. Error: %s", 
                              remaining, limit, error_msg)
                
                if reset and reset.isdigit():
                    wait_s = max(0, int(reset) - int(time.time())) + 1
                    reset_time = datetime.fromtimestamp(int(reset)).strftime("%Y-%m-%d %H:%M:%S")
                    LOGGER.warning("Current token rate limited until: %s (in %.1f seconds / %.1f minutes)", 
                                  reset_time, wait_s, wait_s/60)
                    
                    # Record rate limit for this token
                    if self.token_rotator:
                        self.token_rotator.record_rate_limit(int(reset))
                else:
                    wait_s = self.backoff_factor * attempt
                
                # Try to rotate to next token
                if self.token_rotator and self.token_rotator.rotate():
                    self.bearer_token = self.token_rotator.get_current_token()
                    self._update_session_token()
                    LOGGER.info("Switched to next token. Retrying request immediately...")
                    continue  # Retry with new token
                
                # No more tokens available
                LOGGER.error("API access denied due to rate limiting. This usually means:")
                LOGGER.error("  1. All available tokens are rate limited")
                LOGGER.error("  2. You're on Free tier with very restrictive limits (1 req/15min)")
                LOGGER.error("  3. Consider upgrading API access tier")
                LOGGER.error("  4. Check https://developer.x.com/en/portal/dashboard for your limits")
                LOGGER.error("Next available token resets in %.1f minutes", wait_s/60)
                
                # Stop immediately - don't wait
                resp.raise_for_status()

            if 500 <= resp.status_code < 600:
                LOGGER.error("Server error %s on attempt %d", resp.status_code, attempt)
                if attempt >= self.max_retries:
                    resp.raise_for_status()
                sleep_s = self.backoff_factor * attempt
                LOGGER.warning("Server error %s. Retrying in %.1fs", resp.status_code, sleep_s)
                time.sleep(sleep_s)
                continue

            # Non-retryable
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            LOGGER.error("HTTP %s: %s", resp.status_code, err)
            resp.raise_for_status()


# -----------------------
# Utility: Query builder
# -----------------------
def build_search_query(
    hashtag: Optional[str] = None,
    keywords: Optional[Iterable[str]] = None,
    include_retweets: bool = False,
    lang_hint: Optional[str] = None,
    geo_point: Optional[Tuple[float, float]] = None,  # (lat, lon)
    radius_km: Optional[float] = None,
) -> str:
    """
    Build a search query string for v2 Recent Search.

    Supported operators used here:
    - hashtags: #example
    - keywords: "exact phrase" OR keyword
    - retweets exclusion: -is:retweet
    - language hint: lang:en (optional)
    - geo operator: point_radius:[lon lat radius_km] (only matches tweets with geo point coords)

    Note: The point_radius operator is only effective for tweets with precise geo coordinates,
    which are relatively rare.

    Returns:
        Query string.
    """
    parts: List[str] = []
    if hashtag:
        h = hashtag
        if not h.startswith("#"):
            h = f"#{h}"
        parts.append(h)

    if keywords:
        kw_parts = []
        for k in keywords:
            k = k.strip()
            if not k:
                continue
            # Quote multi-word tokens
            if re.search(r"\s", k):
                kw_parts.append(f'"{k}"')
            else:
                kw_parts.append(k)
        if kw_parts:
            parts.append("(" + " OR ".join(kw_parts) + ")")

    if not include_retweets:
        parts.append("-is:retweet")

    if lang_hint:
        parts.append(f"lang:{lang_hint}")

    if geo_point and radius_km:
        lat, lon = geo_point
        # point_radius expects lon lat
        parts.append(f"point_radius:[{lon:.6f} {lat:.6f} {radius_km:.2f}km]")

    # Fallback if query is empty (should not happen in normal use)
    if not parts:
        parts.append("(*)")

    return " ".join(parts)


# -----------------------
# Function 1: get_tweet
# -----------------------
def get_tweet(
    number: int,
    hashtag: Optional[str] = None,
    location: Optional[Union[str, Dict[str, str]]] = None,
    *,
    keywords: Optional[Iterable[str]] = None,
    geo_point: Optional[Tuple[float, float]] = None,
    radius_km: Optional[float] = None,
    include_retweets: bool = False,
    start_time: Optional[str] = None,  # RFC3339 e.g., "2025-01-01T00:00:00Z"
    end_time: Optional[str] = None,    # RFC3339
    since_id: Optional[str] = None,
    until_id: Optional[str] = None,
    lang_hint: Optional[str] = None,
    bearer_token: Optional[str] = None,
    log_level: int = logging.INFO,
) -> List[Dict[str, Any]]:
    """
    Fetch up to `number` tweets using X (Twitter) v2 Recent Search.

    Return format (list of dicts, one per tweet). Each item has:
        {
          "id": str,                        # Tweet ID
          "text": str,                      # Raw tweet text
          "created_at": str,                # ISO timestamp
          "lang": Optional[str],            # BCP47 language code per API (may be None)
          "author_id": str,
          "author_username": Optional[str],
          "conversation_id": str,
          "public_metrics": dict,           # per API
          "entities": Optional[dict],       # per API
          "geo": Optional[dict],            # per API
          "place": Optional[dict],          # Resolved place object if available
          "referenced_tweets": Optional[list], # per API
          "context_annotations": Optional[list], # per API
          "raw": {                          # Near-raw snapshot of relevant API objects
             "tweet": dict,                 # Raw tweet object as returned in data
             "author": Optional[dict],      # Raw user object for author
             "place": Optional[dict],       # Raw place object
          }
        }

    Parameters:
        number: Max number of tweets to return (<= 500 advised for demo; API returns up to 100 per page).
        hashtag: Single hashtag (with or without leading '#').
        location:
            - If str: case-insensitive substring match against place.full_name or place.country_code (post-filter).
            - If dict: may include {"country_code": "US"} or {"place_substr": "San Francisco"} for post-filtering.
              Post-filter applies only when tweet includes place metadata.
        keywords: Iterable of keywords/phrases to OR into the query.
        geo_point: Optional (lat, lon) for point_radius operator (requires radius_km).
        radius_km: Radius for point_radius.
        include_retweets: If True, do not exclude retweets.
        start_time, end_time: RFC3339 timestamps to bound the search time.
        since_id, until_id: Filter by tweet IDs.
        lang_hint: Optional operator hint like "en". This does not replace preprocessing.
        bearer_token: If not provided, the function will use env var TWITTER_BEARER_TOKEN.
        log_level: Logging verbosity.

    Returns:
        List of tweet dicts as described in the format above.
    """
    LOGGER.setLevel(log_level)
    
    LOGGER.info("Starting tweet fetch: number=%d, hashtag=%s, location=%s", number, hashtag, location)
    LOGGER.info("Additional params: keywords=%s, geo_point=%s, radius_km=%s, include_retweets=%s",
                keywords, geo_point, radius_km, include_retweets)
    
    client = TwitterClient(bearer_token=bearer_token)

    query = build_search_query(
        hashtag=hashtag,
        keywords=keywords,
        include_retweets=include_retweets,
        lang_hint=lang_hint,
        geo_point=geo_point,
        radius_km=radius_km,
    )
    
    LOGGER.info("Built search query: %s", query)

    tweet_fields = [
        "id",
        "text",
        "created_at",
        "lang",
        "author_id",
        "conversation_id",
        "public_metrics",
        "entities",
        "geo",
        "context_annotations",
        "referenced_tweets",
        "source",
    ]
    user_fields = ["id", "name", "username", "verified", "public_metrics", "created_at", "entities"]
    place_fields = ["id", "full_name", "name", "country", "country_code", "geo", "place_type"]

    # Conservative: limit max_results to requested number, cap at 10 by default for safety
    # Free tier has monthly tweet caps, so be very conservative
    actual_max = min(number, 10)  # Cap at 10 tweets per request to preserve monthly quota
    
    params = {
        "query": query,
        "max_results": actual_max,
        "expansions": "author_id,geo.place_id",
        "tweet.fields": ",".join(tweet_fields),
        "user.fields": ",".join(user_fields),
        "place.fields": ",".join(place_fields),
    }
    
    LOGGER.info("Requesting max_results=%d (requested %d tweets total)", actual_max, number)
    if start_time:
        params["start_time"] = start_time
    if end_time:
        params["end_time"] = end_time
    if since_id:
        params["since_id"] = since_id
    if until_id:
        params["until_id"] = until_id

    path = "/2/tweets/search/recent"
    out: List[Dict[str, Any]] = []
    
    # Warn about limits
    if number > 10:
        LOGGER.warning(
            "Requested %d tweets. To preserve monthly quota and avoid rate limits, "
            "limiting to 10 tweets per request. Consider making multiple smaller requests.",
            number
        )

    # Make a single API call (no pagination)
    LOGGER.info("Fetching tweets from API endpoint: %s", path)
    payload = client.get(path, params)
    data = payload.get("data", [])
    includes = payload.get("includes", {})
    users = {u["id"]: u for u in includes.get("users", [])}
    places = {p["id"]: p for p in includes.get("places", [])}
    
    LOGGER.info("Received %d tweets, %d users, %d places from API", 
                len(data), len(users), len(places))
    LOGGER.debug("API metadata: %s", payload.get("meta", {}))

    filtered_count = 0
    for t in data:
            author = users.get(t.get("author_id"))
            place_obj = None
            if t.get("geo", {}).get("place_id"):
                place_obj = places.get(t["geo"]["place_id"])

            record = {
                "id": t["id"],
                "text": t.get("text", ""),
                "created_at": t.get("created_at"),
                "lang": t.get("lang"),
                "author_id": t.get("author_id"),
                "author_username": author["username"] if author else None,
                "conversation_id": t.get("conversation_id"),
                "public_metrics": t.get("public_metrics", {}),
                "entities": t.get("entities"),
                "geo": t.get("geo"),
                "place": place_obj,
                "referenced_tweets": t.get("referenced_tweets"),
                "context_annotations": t.get("context_annotations"),
                "raw": {
                    "tweet": t,
                    "author": author,
                    "place": place_obj,
                },
            }

            # Optional post-filter by place information
            if location:
                if isinstance(location, str):
                    want = location.lower()
                    p_ok = False
                    if place_obj:
                        full_name = (place_obj.get("full_name") or "").lower()
                        country_code = (place_obj.get("country_code") or "").lower()
                        p_ok = want in full_name or want == country_code
                    if not p_ok:
                        filtered_count += 1
                        LOGGER.debug("Filtered tweet %s: location '%s' not in place", t["id"], want)
                        continue
                elif isinstance(location, dict):
                    p_ok = True
                    if place_obj:
                        if "country_code" in location:
                            p_ok = p_ok and str(place_obj.get("country_code", "")).lower() == str(
                                location["country_code"]
                            ).lower()
                        if "place_substr" in location:
                            p_ok = p_ok and (
                                str(location["place_substr"]).lower()
                                in str(place_obj.get("full_name", "")).lower()
                            )
                    else:
                        # If no place metadata, we cannot verify location => exclude
                        p_ok = False
                    if not p_ok:
                        filtered_count += 1
                        LOGGER.debug("Filtered tweet %s: location filter not satisfied", t["id"])
                        continue

            out.append(record)
            if len(out) >= number:
                break

    LOGGER.info("Fetched %d tweets (requested %d). Filtered out %d tweets by location.", 
                len(out), number, filtered_count)
    return out


# -----------------------
# Function 2: preprocess
# -----------------------
# Pre-compiled regexes and constants for cleaning
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_]{1,15})")
HASHTAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_]+)")
RT_PREFIX_RE = re.compile(r"^RT\s+@[\w_]+:\s*", re.IGNORECASE)
CONTROL_CHARS_RE = re.compile(r"[\u0000-\u001F\u007F-\u009F]")

# Emoji ranges (commonly used blocks)
EMOJI_RANGES = [
    ("\U0001F300", "\U0001F5FF"),  # Misc Symbols and Pictographs
    ("\U0001F600", "\U0001F64F"),  # Emoticons
    ("\U0001F680", "\U0001F6FF"),  # Transport & Map Symbols
    ("\U0001F700", "\U0001F77F"),  # Alchemical Symbols
    ("\U0001F780", "\U0001F7FF"),  # Geometric Shapes Extended
    ("\U0001F800", "\U0001F8FF"),  # Supplemental Arrows-C
    ("\U0001F900", "\U0001F9FF"),  # Supplemental Symbols and Pictographs
    ("\U0001FA70", "\U0001FAFF"),  # Symbols and Pictographs Extended-A
    ("\u2600", "\u26FF"),          # Misc symbols
    ("\u2700", "\u27BF"),          # Dingbats
]
# Allowed ASCII-like punctuation
ALLOWED_PUNCT = r"""!\"#$%&'()*+,\-./:;<=>?@[\]^_`{|}~"""


def _is_allowed_char(ch: str) -> bool:
    """
    Keep:
    - ASCII letters and digits
    - ASCII-like punctuation and whitespace
    - Emoji ranges defined above

    Drop:
    - Characters from non-Latin scripts (e.g., CJK, Cyrillic, etc.)
    - Control characters

    Note: This intentionally removes non-English scripts. Accented Latin (é, ñ) are removed as well.
    Adjust as needed for your use case.
    """
    o = ord(ch)
    # ASCII letters/digits
    if 0x30 <= o <= 0x39 or 0x41 <= o <= 0x5A or 0x61 <= o <= 0x7A:
        return True
    # Whitespace
    if ch in (" ", "\t"):
        return True
    # ASCII-like punctuation
    if ch in ALLOWED_PUNCT:
        return True
    # Emoji blocks
    for lo, hi in EMOJI_RANGES:
        if ord(lo) <= o <= ord(hi):
            return True
    return False


def _strip_non_english_keep_emoji(text: str) -> str:
    # Remove control chars first
    text = CONTROL_CHARS_RE.sub(" ", text)
    chars = []
    for ch in text:
        if _is_allowed_char(ch):
            chars.append(ch)
        else:
            # Replace disallowed characters with space to avoid word gluing
            chars.append(" ")
    out = "".join(chars)
    # Collapse whitespace
    out = re.sub(r"\s+", " ", out).strip()
    return out


def preprocess(
    tweet: Union[str, Dict[str, Any]],
    *,
    replace_urls_with: Optional[str] = "<URL>",
    keep_mentions: bool = False,
    replace_mentions_with: Optional[str] = "@user",
    keep_hashtags: bool = True,
    lower: bool = True,
    remove_rt_prefix: bool = True,
    strip_non_english: bool = True,
    min_len: int = 3,
    log_preprocessing: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Preprocess a single tweet to be suitable for training.

    Input:
        tweet: Either a raw text string or a tweet dict as returned by get_tweet().

    Behavior:
        - Normalizes Unicode (NFC), unescapes HTML entities.
        - Optionally removes leading "RT @user:" patterns from retweets.
        - Replaces URLs with a placeholder (default "<URL>") if replace_urls_with is not None; otherwise removes them.
        - Mentions:
            - If keep_mentions is True, keep @handles as-is.
            - Else if replace_mentions_with is not None, replace with that token (default "@user").
            - Else remove mentions entirely.
        - Hashtags:
            - If keep_hashtags is True, keep them (preserving the leading '#').
            - Else convert "#word" to "word" (strip '#').
        - If lower is True, lowercases the text.
        - If strip_non_english is True, removes all characters not in:
            - ASCII letters/digits
            - ASCII punctuation
            - Whitespace
            - Emoji ranges defined in EMOJI_RANGES
          This removes non-English scripts (e.g., Japanese, Cyrillic, etc.) while preserving standard emojis.
        - Collapses repeated whitespace, trims ends.
        - Drops the tweet if resulting clean_text has length < min_len.

    Output:
        A dict with:
        {
          "id": Optional[str],
          "text": str,              # original text (if input was dict) or the input string
          "clean_text": str,        # cleaned/preprocessed text
          "lang": Optional[str],    # from input if available
          "meta": Optional[dict],   # selected metadata if input was dict (author, created_at, etc.)
        }
        Returns None if the cleaned text is too short or empty.

    Examples of characters removed when strip_non_english=True:
        - Japanese Kanji/Hiragana/Katakana, Chinese Han, Cyrillic, Arabic, etc.
        - Accented Latin letters (é ñ) will also be removed (strict English-only). Adjust _is_allowed_char if needed.
    """
    if isinstance(tweet, dict):
        raw_text = tweet.get("text", "")
        tw_id = tweet.get("id")
        lang = tweet.get("lang")
        meta = {
            "created_at": tweet.get("created_at"),
            "author_id": tweet.get("author_id"),
            "author_username": tweet.get("author_username"),
            "public_metrics": tweet.get("public_metrics"),
            "place": tweet.get("place"),
        }
    else:
        raw_text = str(tweet)
        tw_id = None
        lang = None
        meta = None

    if not raw_text:
        return None

    # Normalize and unescape HTML entities
    txt = unicodedata.normalize("NFC", raw_text)
    txt = html_unescape(txt)

    # Remove RT prefix
    if remove_rt_prefix:
        txt = RT_PREFIX_RE.sub("", txt)

    # URLs
    if replace_urls_with is None:
        txt = URL_RE.sub("", txt)
    else:
        txt = URL_RE.sub(replace_urls_with, txt)

    # Mentions
    def _mention_sub(m: re.Match) -> str:
        handle = m.group(0)
        if keep_mentions:
            return handle
        if replace_mentions_with is None:
            return ""
        return replace_mentions_with

    txt = MENTION_RE.sub(_mention_sub, txt)

    # Hashtags
    def _hashtag_sub(m: re.Match) -> str:
        tag = m.group(0)
        if keep_hashtags:
            return tag
        # strip '#' but keep token
        return m.group(1)

    txt = HASHTAG_RE.sub(_hashtag_sub, txt)

    # Lowercase
    if lower:
        txt = txt.lower()

    # Strip non-English scripts but keep emoji (per _is_allowed_char)
    if strip_non_english:
        txt = _strip_non_english_keep_emoji(txt)

    # Cleanup whitespace and drop too-short
    txt = re.sub(r"\s+", " ", txt).strip()
    if len(txt) < min_len:
        if log_preprocessing:
            LOGGER.debug("Dropped tweet %s: clean_text too short (%d < %d)", tw_id, len(txt), min_len)
        return None

    result = {
        "id": tw_id,
        "text": raw_text,
        "clean_text": txt,
        "lang": lang,
        "meta": meta,
    }
    
    if log_preprocessing:
        LOGGER.debug("Preprocessed tweet %s: '%s' -> '%s'", tw_id, raw_text[:50], txt[:50])
    
    return result


# -----------------------
# Function 3: get_label
# -----------------------
def get_label(tweet: Union[str, Dict[str, Any]], *args, **kwargs) -> bool:
    """
    Placeholder labeling function.

    Input:
        tweet: Can be a preprocessed tweet dict (recommended) or raw string.
    Output:
        True | False | raises Exception
    Current behavior:
        - Always returns True.

    Note:
        In your production code, replace this function with your labeling logic.
        If your implementation raises an exception for a tweet, the main pipeline will
        log a warning and drop that tweet (as required).
    """
    return True


# -----------------------
# Function 4: save_tweets
# -----------------------
def save_tweets(
    storage_path: Union[str, Path],
    tweets_with_label: Sequence[Dict[str, Any]],
    *,
    key_field: str = "id",
    atomic: bool = True,
    log_level: int = logging.INFO,
    log_details: bool = True,
) -> None:
    """
    Save labeled tweets to a JSONL file, keyed by `key_field`. On duplication:
    - The new record replaces the old record.
    - Emits a warning.

    Behavior:
        - If file exists, it is fully read and merged with new tweets by key.
        - If atomic=True, writes to a temp file and then renames for crash safety.
        - File encoding is UTF-8. One JSON object per line.

    Each stored record is expected to contain:
        {
          "id": str,
          "clean_text": str,
          "label": True|False,
          ... (any other metadata you keep, e.g., raw, meta)
        }

    Parameters:
        storage_path: File path to JSONL.
        tweets_with_label: Iterable of tweet dicts including labels.
        key_field: Unique identifier field (default "id").
        atomic: Use atomic write via temp file+rename.
    """
    LOGGER.setLevel(log_level)
    path = Path(storage_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    LOGGER.info("Saving tweets to %s", path)

    existing: Dict[str, Dict[str, Any]] = {}
    if path.exists():
        LOGGER.info("Loading existing tweets from %s", path)
        with path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    LOGGER.warning("Skipping corrupt line %d in %s", line_num, path)
                    continue
                k = obj.get(key_field)
                if k is not None:
                    existing[str(k)] = obj
        LOGGER.info("Loaded %d existing tweets", len(existing))

    # Merge
    updates = 0
    adds = 0
    for tw in tweets_with_label:
        k = tw.get(key_field)
        if k is None:
            LOGGER.warning("Tweet missing key_field '%s'; skipping", key_field)
            continue
        k = str(k)
        if k in existing:
            if log_details:
                LOGGER.debug("Duplicate key '%s' found; replacing old record", k)
            updates += 1
        else:
            if log_details:
                LOGGER.debug("Adding new tweet with key '%s'", k)
            adds += 1
        existing[k] = tw

    records = list(existing.values())
    LOGGER.info("Saving %d records to %s (adds=%d, updates=%d)", len(records), str(path), adds, updates)

    if atomic:
        LOGGER.debug("Using atomic write via temporary file")
        with NamedTemporaryFile("w", dir=str(path.parent), delete=False, encoding="utf-8", newline="\n") as tmp:
            tmp_path = Path(tmp.name)
            for obj in records:
                tmp.write(json.dumps(obj, ensure_ascii=False) + "\n")
        tmp_path.replace(path)
        LOGGER.debug("Atomic write completed successfully")
    else:
        LOGGER.debug("Using direct write (non-atomic)")
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for obj in records:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    
    LOGGER.info("Successfully saved %d tweets to %s", len(records), path)


# -----------------------
# Main loop: ingest_tweets
# -----------------------
def ingest_tweets(
    number: int,
    hashtag: Optional[str],
    location: Optional[Union[str, Dict[str, str]]],
    storage_path: Union[str, Path],
    *,
    keywords: Optional[Iterable[str]] = None,
    geo_point: Optional[Tuple[float, float]] = None,
    radius_km: Optional[float] = None,
    include_retweets: bool = False,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    since_id: Optional[str] = None,
    until_id: Optional[str] = None,
    lang_hint: Optional[str] = None,
    bearer_token: Optional[str] = None,
    log_level: int = logging.INFO,
) -> None:
    """
    Orchestrates: get -> preprocess -> get_label -> save.

    Steps:
        1) Fetch tweets via get_tweet()
        2) Preprocess each tweet via preprocess()
        3) Label each preprocessed tweet via get_label()
           - If labeling throws, log a warning and drop the tweet.
        4) Save to storage via save_tweets()

    Parameters mirror get_tweet plus storage_path.

    Output:
        Writes/updates the JSONL at storage_path.
    """
    LOGGER.setLevel(log_level)
    
    LOGGER.info("="*80)
    LOGGER.info("Starting tweet ingestion pipeline")
    LOGGER.info("Target storage: %s", storage_path)
    LOGGER.info("="*80)
    
    raw_tweets = get_tweet(
        number=number,
        hashtag=hashtag,
        location=location,
        keywords=keywords,
        geo_point=geo_point,
        radius_km=radius_km,
        include_retweets=include_retweets,
        start_time=start_time,
        end_time=end_time,
        since_id=since_id,
        until_id=until_id,
        lang_hint=lang_hint,
        bearer_token=bearer_token,
        log_level=log_level,
    )

    LOGGER.info("Beginning preprocessing of %d tweets", len(raw_tweets))
    labeled: List[Dict[str, Any]] = []
    preprocessing_dropped = 0
    labeling_dropped = 0
    
    for i, t in enumerate(raw_tweets, 1):
        p = preprocess(t, log_preprocessing=(log_level <= logging.DEBUG))
        if not p:
            preprocessing_dropped += 1
            continue

        # Labeling with error handling
        try:
            lbl = get_label(p)
            LOGGER.debug("Tweet %s labeled as: %s", p.get("id"), lbl)
        except Exception as e:
            LOGGER.warning("Labeling failed for tweet id=%s: %s. Dropping.", p.get("id"), e)
            labeling_dropped += 1
            continue

        p["label"] = lbl
        # Optionally retain a subset of original fields for traceability
        p["id"] = p.get("id") or t.get("id")
        p["raw"] = t.get("raw")  # keep near-raw for auditing if needed
        labeled.append(p)
        
        if i % 10 == 0:
            LOGGER.info("Processed %d/%d tweets (%d labeled so far)", i, len(raw_tweets), len(labeled))

    LOGGER.info("Preprocessing complete: %d tweets labeled, %d dropped in preprocessing, %d dropped in labeling",
                len(labeled), preprocessing_dropped, labeling_dropped)

    if not labeled:
        LOGGER.warning("No tweets to save after preprocessing/labeling.")
        return

    save_tweets(storage_path=storage_path, tweets_with_label=labeled, key_field="id", log_level=log_level)
    LOGGER.info("="*80)
    LOGGER.info("Ingestion complete. Saved %d tweets to %s", len(labeled), storage_path)
    LOGGER.info("="*80)


# -----------------------
# Example usage
# -----------------------
if __name__ == "__main__":
    # Example: Conservative settings for Free tier API access
    # - Default: 1 tweet per request to preserve monthly quota
    # - Uses automatic token rotation from .env file
    # - Environment variable: TWITTER_BEARER_TOKENS (comma-separated list)
    # - System will try all tokens before failing
    try:
        ingest_tweets(
            number=10, 
            hashtag="datascience",
            location=None,  # Removed location filter for better results
            storage_path="data/tweets.jsonl",
            keywords=None,  # Simplified query
            include_retweets=False,
            lang_hint="en",  # Focus on English tweets
            log_level=logging.INFO,
        )
    except Exception as e:
        LOGGER.error("Pipeline failed: %s", e)
        sys.exit(1)
