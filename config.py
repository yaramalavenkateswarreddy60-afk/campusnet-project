"""
CampusNet: Configuration Module
Defines settings, thresholds, and environment parameters.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "campusnet-dev-key-7729-cn-secret")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", str(INSTANCE_DIR / "campusnet.db"))
    
    # Server host & port binding (localhost by default for security)
    HOST = "127.0.0.1"
    PORT = 5000
    DEBUG = False
    TESTING = False
    TEMPLATES_AUTO_RELOAD = True

    # Default Shared Campus Gateway Capacity (Mbps)
    DEFAULT_CAMPUS_CAPACITY_MBPS = 800.0

    # Configurable Congestion Detection Demonstration Thresholds
    # Note: These are configurable demonstration thresholds, not universal standards.
    THRESHOLD_WARNING_UTILIZATION = 70.0  # Percentage
    THRESHOLD_CRITICAL_UTILIZATION = 85.0  # Percentage
    THRESHOLD_WARNING_LATENCY_MS = 50.0   # Milliseconds
    THRESHOLD_CRITICAL_LATENCY_MS = 100.0  # Milliseconds
    THRESHOLD_WARNING_PACKET_LOSS = 1.0   # Percentage
    THRESHOLD_CRITICAL_PACKET_LOSS = 3.0  # Percentage

    # Security & Session Settings
    SECRET_KEY = os.environ.get("CAMPUSNET_SECRET_KEY") or os.environ.get("SECRET_KEY", "campusnet-dev-key-7729-cn-secret")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("CAMPUSNET_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    
    # Network Safety & Enforcement Constraints
    # Enforcement is strictly disabled by default; only allowed on isolated testbed
    NETWORK_ENFORCEMENT_ENABLED = os.environ.get("NETWORK_ENFORCEMENT_ENABLED", "false").lower() == "true"
    ALLOW_PRODUCTION_ENFORCEMENT = False  # Production enforcement strictly prohibited by default
    DEFAULT_ENVIRONMENT_TARGET = "ISOLATED_TESTBED"

    # CSV Upload Constraints
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max upload
    ALLOWED_EXTENSIONS = {"csv"}


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing configuration with separate in-memory or test database."""
    TESTING = True
    DATABASE_PATH = str(INSTANCE_DIR / "campusnet_test.db")
