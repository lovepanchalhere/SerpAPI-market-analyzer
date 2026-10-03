import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
SERPAPI_URL = "https://serpapi.com/search"


# ---------------------------------------------------------------------------
# Helper: SerpApi Google Local
# ---------------------------------------------------------------------------
def fetch_local_results(business_type, location, api_key):
    """Call SerpApi Google Local and return parsed list of businesses."""
    params = {
        "engine":   "google_local",
        "q":        business_type,
        "location": location,
        "api_key":  api_key,
        "gl":       "in",
        "hl":       "en",
    }
    resp = requests.get(SERPAPI_URL, params=params, timeout=15)
    resp.raise_for_status()

    body = resp.json()
    # SerpApi signals errors inside a 200 response via an "error" field
    if "error" in body:
        raise ValueError(f"SerpApi (local): {body['error']}")

    raw = body.get("local_results", [])
    return [
        {
            "title":   entry.get("title"),
            "rating":  entry.get("rating"),
            "reviews": entry.get("reviews"),
        }
        for entry in raw
    ]


# ---------------------------------------------------------------------------
# Helper: SerpApi Google Trends
# ---------------------------------------------------------------------------
def fetch_trends_timeline(business_type, api_key):
    """Call SerpApi Google Trends (TIMESERIES) and return timeline data."""
    params = {
        "engine":    "google_trends",
        "q":         business_type,
        "geo":       "IN",
        "data_type": "TIMESERIES",
        "api_key":   api_key,
    }
    resp = requests.get(SERPAPI_URL, params=params, timeout=15)
    resp.raise_for_status()

    body = resp.json()
    # SerpApi signals errors inside a 200 response via an "error" field
    if "error" in body:
        raise ValueError(f"SerpApi (trends): {body['error']}")

    timeline_data = (
        body
        .get("interest_over_time", {})
        .get("timeline_data", [])
    )
    # Normalise each data point for clean output
    parsed = []
    for point in timeline_data:
        values = point.get("values", [])
        parsed.append({
            "date":            point.get("date"),
            "timestamp":       point.get("timestamp"),
            "value":           values[0].get("value") if values else None,
            "extracted_value": values[0].get("extracted_value") if values else None,
        })
    return parsed


# ---------------------------------------------------------------------------
# Verdict: Competition level
# ---------------------------------------------------------------------------
def analyze_competition(local_results):
    """
    Rules:
      - > 8 competitors AND avg rating > 4.2  → 'High competition'
      - < 4 competitors                        → 'Low competition - opportunity'
      - otherwise                              → 'Moderate competition'
    """
    total = len(local_results)

    if total < 4:
        return "Low competition - opportunity"

    ratings = [r["rating"] for r in local_results if r.get("rating") is not None]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

    if total > 8 and avg_rating > 4.2:
        return "High competition"

    return "Moderate competition"


# ---------------------------------------------------------------------------
# Verdict: Search-interest trend
# ---------------------------------------------------------------------------
def analyze_trend(timeline_data):
    """
    Compares the average of the last 3 data points against the first 3.
      - last_avg > first_avg → 'Rising'
      - last_avg < first_avg → 'Declining'
      - equal (or < 6 points) → 'Stable'
    """
    if len(timeline_data) < 6:
        return "Stable"

    def safe_value(point):
        try:
            return float(point.get("extracted_value") or point.get("value") or 0)
        except (TypeError, ValueError):
            return 0.0

    first_avg = sum(safe_value(p) for p in timeline_data[:3]) / 3
    last_avg  = sum(safe_value(p) for p in timeline_data[-3:]) / 3

    if last_avg > first_avg:
        return "Rising"
    elif last_avg < first_avg:
        return "Declining"
    return "Stable"


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------
@app.route("/analyze", methods=["POST"])
def analyze():
    """
    POST /analyze
    Body: { "business_type": "...", "location": "..." }

    Calls in parallel:
      - SerpApi Google Local  ? local_results  (title, rating, reviews)
      - SerpApi Google Trends ? interest_over_time timeline (TIMESERIES, geo=IN)

    Returns both datasets merged in a single JSON response.
    """
    data = request.get_json(silent=True)

    # --- Validate request body ---
    if not data:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    business_type = data.get("business_type", "").strip()
    location      = data.get("location", "").strip()

    if not business_type:
        return jsonify({"error": "'business_type' is required and cannot be empty."}), 400
    if not location:
        return jsonify({"error": "'location' is required and cannot be empty."}), 400
    if not SERPAPI_KEY:
        return jsonify({"error": "SerpApi key is not configured on the server."}), 500

    # --- Normalise location: append state/country if only a bare city was given ---
    if "," not in location:
        location = f"{location}, Haryana, India"

    # --- Fire both API calls concurrently ---
    local_results    = []
    trends_timeline  = []
    errors           = {}

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_local  = executor.submit(fetch_local_results,  business_type, location, SERPAPI_KEY)
        future_trends = executor.submit(fetch_trends_timeline, business_type, SERPAPI_KEY)

        for future in as_completed([future_local, future_trends]):
            label = "local" if future is future_local else "trends"
            try:
                result = future.result()
                if label == "local":
                    local_results = result
                else:
                    trends_timeline = result
            except requests.exceptions.Timeout:
                errors[label] = "Request timed out — SerpApi did not respond in time."
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else "unknown"
                errors[label] = f"SerpApi returned HTTP {status}: {str(e)}"
            except ValueError as e:
                # SerpApi-level error returned inside a 200 body
                errors[label] = str(e)
            except requests.exceptions.RequestException as e:
                errors[label] = f"Network error: {str(e)}"
            except Exception as e:
                errors[label] = f"Unexpected error: {str(e)}"

    # --- Guard: both APIs failed entirely ---
    if errors and not local_results and not trends_timeline:
        return jsonify({
            "error": "Both SerpApi calls failed. No data could be retrieved.",
            "details": errors,
        }), 502

    # --- Guard: APIs succeeded but returned no data ---
    if not local_results and not trends_timeline:
        return jsonify({
            "error": "No results found.",
            "message": (
                f"SerpApi returned no local businesses or trend data for "
                f"'{business_type}' in '{location}'. "
                "Try a different business type or location."
            ),
        }), 404

    # --- Compute verdicts ---
    # Only compute competition if the local API actually succeeded.
    # A failed call returns [] which would give a misleading "Low competition" verdict.
    competition_verdict = (
        None if "local" in errors
        else analyze_competition(local_results)
    )
    trend_verdict = (
        None if "trends" in errors
        else analyze_trend(trends_timeline)
    )

    # --- Build response ---
    response_body = {
        "business_type": business_type,
        "location":      location,
        # Google Local results
        "local_results": {
            "total": len(local_results),
            "data":  local_results,
        },
        # Google Trends timeline
        "interest_over_time": {
            "total": len(trends_timeline),
            "data":  trends_timeline,
        },
        # Verdicts
        "verdicts": {
            "competition": competition_verdict,
            "trend":       trend_verdict,
        },
    }

    # Surface non-fatal per-API warnings without blocking the response
    if errors:
        response_body["warnings"] = errors

    return jsonify(response_body), 200


# ---------------------------------------------------------------------------
# Global error handler — catches any unhandled exception in a route
# ---------------------------------------------------------------------------
@app.errorhandler(Exception)
def handle_unexpected_error(e):
    return jsonify({
        "error": "An unexpected server error occurred.",
        "details": str(e),
    }), 500


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    """Simple health-check endpoint."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
