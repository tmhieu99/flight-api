import aiohttp
import asyncio
import logging
import uvicorn
import os

from datetime import datetime
from collections import defaultdict
from typing import Optional, List, Tuple
from cachetools import TTLCache
from functools import lru_cache

from dotenv import load_dotenv

from pydantic import BaseModel
from pydantic_settings import BaseSettings

from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv(override=True)

class Settings(BaseSettings):
    FLIGHT_API_KEY: str = os.getenv("FLIGHT_API_KEY"),
    API_BASE_URL: str = "https://api.flightapi.io"
    CACHE_TTL: int = 300
    CACHE_MAXSIZE: int = 100
    CONCURRENT_REQUESTS: int = 10
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

class FlightData(BaseModel):
    country: str
    count: int

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
flights_cache = TTLCache(maxsize=settings.CACHE_MAXSIZE, ttl=settings.CACHE_TTL)

# Create a session pool
session_pool = None

async def get_session_pool():
    global session_pool
    if session_pool is None:
        connector = aiohttp.TCPConnector(
            limit=settings.CONCURRENT_REQUESTS,
            ttl_dns_cache=300,
            enable_cleanup_closed=True
        )
        session_pool = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=60)
        )
    return session_pool

app = FastAPI(
    title="Flight Data API",
    description="API for getting flights by airport code, groupby countries",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    # init aiohttp session pool
    await get_session_pool()

@app.on_event("shutdown")
async def shutdown_event():
    # close session pool when shutdown
    global session_pool
    if session_pool:
        await session_pool.close()

templates = Jinja2Templates(directory="app/templates")

# Fetch and parse flight data
async def fetch_flight_data(
    session: aiohttp.ClientSession,
    airport_code: str
) -> List[Tuple[str, int]]:
    try:
        async with session.get(
            f"{settings.API_BASE_URL}/compschedule/{settings.FLIGHT_API_KEY}",
            params={
                'mode': 'arrivals',
                'day': '1', # 1 is today
                'iata': airport_code.lower()
            }
        ) as response:
            response.raise_for_status()
            data = await response.json()
            
            country_flights = defaultdict(int)
            if isinstance(data, list):
                for item in data:
                    flights_data = (item.get('airport', {})
                                  .get('pluginData', {})
                                  .get('schedule', {})
                                  .get('arrivals', {})
                                  .get('data', []))
                    
                    for flight in flights_data:
                        country_name = (flight.get('flight', {})
                                      .get('airport', {})
                                      .get('origin', {})
                                      .get('position', {})
                                      .get('country', {})
                                      .get('name'))
                        
                        if country_name:
                            country_flights[country_name] += 1
            
            if not country_flights:
                raise ValueError(f"No flight data found for airport code: {airport_code}")
            
            return sorted(
                country_flights.items(),
                key=lambda x: x[1],
                reverse=True
            )
    except asyncio.TimeoutError:
        logger.error(f"Timeout while fetching data for airport {airport_code}")
        raise
    except aiohttp.ClientError as e:
        logger.error(f"API error for airport {airport_code}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error for airport {airport_code}: {str(e)}")
        raise

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, error: Optional[str] = None):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "error": error}
    )

# handle main logic to get flight data
# get from cache first and query API if cache miss
@app.post("/flights")
async def get_flights(
    request: Request,
    airport_code: str = Form(...),
):
    try:
        if len(airport_code) != 3:
            raise ValueError("Please enter a valid 3-letter airport code")
        
        airport_code = airport_code.upper()
        cache_key = f"flights_{airport_code}"
        
        if cache_key in flights_cache:
            logger.info(f"Cache hit for airport {airport_code}")
            return templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "flights": flights_cache[cache_key],
                    "airport_code": airport_code
                }
            )
        
        session = await get_session_pool()
        flight_data = await fetch_flight_data(session, airport_code)
        flights_cache[cache_key] = flight_data
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "flights": flight_data,
                "airport_code": airport_code
            }
        )
            
    except ValueError as e:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "error": str(e)}
        )
    except asyncio.TimeoutError:
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "error": "Request timed out. Please try again or try a different airport."}
        )
    except Exception as e:
        logger.error(f"Unexpected error for airport {airport_code}: {str(e)}")
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "error": f"An unexpected error occurred: {str(e)}"}
        )

# do healthcheck periodically 
@app.get("/health")
async def health_check(
    request: Request,
):
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "version": "1.0.0",
        "cache_size": len(flights_cache),
        "cache_info": {
            "current_size": flights_cache.currsize,
            "maxsize": flights_cache.maxsize,
            "ttl": flights_cache.ttl
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )