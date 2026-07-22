# app/core/config.py - SUPER SIMPLE
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Application
    APP_NAME = os.getenv("APP_NAME", "Absensi API")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000") # <-- TAMBAHKAN INI
    DATABASE_URL = os.getenv("DATABASE_URL")
    BACKEND_URL = os.getenv("BACKEND_URL")
    
    # JWT
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))
    
    # Email
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_FROM = os.getenv("MAIL_FROM")
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_STARTTLS = os.getenv("MAIL_STARTTLS", "True").lower() == "true"
    MAIL_SSL_TLS = os.getenv("MAIL_SSL_TLS", "False").lower() == "true"
    
    # GPS
    DEFAULT_GPS_RADIUS_METERS = int(os.getenv("DEFAULT_GPS_RADIUS_METERS", 100))
    MAX_VALID_DISTANCE_METERS = int(os.getenv("MAX_VALID_DISTANCE_METERS", 200))
    
    # Genetic Algorithm
    GA_POPULATION_SIZE = int(os.getenv("GA_POPULATION_SIZE", 100))
    GA_GENERATIONS = int(os.getenv("GA_GENERATIONS", 100))
    GA_MUTATION_RATE = float(os.getenv("GA_MUTATION_RATE", 0.01))
    GA_MIN_WFO_PER_WEEK = int(os.getenv("GA_MIN_WFO_PER_WEEK", 2))
    GA_MAX_WFO_PER_WEEK = int(os.getenv("GA_MAX_WFO_PER_WEEK", 4))
    
    # CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "[\"http://localhost:3000\",\"http://localhost:5173\"]")
    # Parse JSON string to list
    import json
    try:
        CORS_ORIGINS = json.loads(CORS_ORIGINS)
    except:
        CORS_ORIGINS = ["http://localhost:3000", "http://localhost:5173"]

settings = Settings()