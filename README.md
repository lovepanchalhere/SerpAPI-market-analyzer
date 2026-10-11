# Market Analyzer

Discover competition levels and search trends for any business in India — 
powered by real-time data from SerpApi.

## Problem

People looking to open a small business (a bakery, gym, salon, etc.) often 
have no easy way to check whether an area is already saturated with similar 
businesses, or whether demand is rising or falling. Most decisions are made 
on gut feeling rather than real data.

## Solution

Market Analyzer lets anyone enter a business type and a location, and 
instantly see:
- **Competition level** — how many similar businesses already exist nearby, 
  with their ratings and review counts
- **Search trend** — whether interest in that business type is rising, 
  stable, or declining in that region
- A clear verdict: high competition, moderate competition, or low 
  competition / opportunity

All data is pulled live from Google's actual search results — no mock or 
simulated data is used.

## How It Works

1. User enters a business type (e.g., "bakery") and a location (e.g., 
   "Karnal, Haryana")
2. The backend calls SerpApi's **Google Local API** to fetch real nearby 
   businesses of that type — names, ratings, review counts
3. The backend calls SerpApi's **Google Trends API** to fetch search 
   interest over time for that business type in India
4. A verdict engine analyzes both datasets and returns a competition level 
   and a trend direction
5. The frontend displays the verdicts along with the list of real 
   competitors found

## SerpApi Usage

This project's core functionality depends entirely on SerpApi:

- **Google Local API** (`engine=google_local`) — fetches real local business 
  listings for the given business type and location, including name, rating, 
  and review count. This data directly determines the competition verdict.
- **Google Trends API** (`engine=google_trends`) — fetches search interest 
  over time for the business type in the specified region. This data 
  directly determines the trend verdict.

Without SerpApi, the app has no data to analyze — both APIs are material, 
not decorative, to the product.

## Tech Stack

- **Backend:** Python (Flask)
- **Frontend:** HTML, CSS, JavaScript
- **Data source:** SerpApi (Google Local API, Google Trends API)

## Setup Instructions

1. Clone this repository:https://github.com/lovepanchalhere/SerpAPI-market-analyzer.git
2. Install dependencies:pip install -r requirements.txt
3. Create a `.env` file in the project root with your own SerpApi key:SERPAPI_KEY=1ab3348bc0b9f0a83da761890ebab5a6b7ef958baef22a7e51bf98ed4db6b5314
4. Start the backend server:python app.py
#
5. Open http://localhost:5000 in your browser.

6. Enter a business type and location (including the state, e.g., "Karnal, 
   Haryana", for best results) and click "Analyze Market."

## AI Tools Used

Google Antigravity was used to scaffold the backend endpoints, frontend UI, 
and error-handling logic, based on specific requirements and iterative 
testing by the developer.

## Track

Commerce & Market Intelligence

##Live demo: https://serp-api-market-analyzer.vercel.app

## Team

- Love Panchal — Lead participant (solo project)

## Notes

- Location inputs work best when they include the state (e.g., 
  "Karnal, Haryana" rather than just "Karnal"), since Google's local data 
  requires a recognizable location string.
- If a data source fails or can't resolve the location, the app shows a 
  clear message rather than a false result.