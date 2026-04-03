"""
WeatherTwin — Monitoring & Metrics Service
Tracks API latency, query analytics, system health, and LLM performance.
Stores metrics in PostgreSQL for persistence across sessions.
"""

import time
import os
import json
import functools
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from contextlib import contextmanager
from typing import Optional

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


# ──────────────────────────────────────────────
# In-Memory Metrics Buffer (flushed to DB periodically)
# ──────────────────────────────────────────────

class MetricsBuffer:
    """Thread-safe in-memory buffer for metrics before DB flush."""

    def __init__(self):
        self._lock = threading.Lock()
        self._api_calls = []        # List of API call records
        self._queries = []           # List of user query records
        self._llm_calls = []         # List of LLM call records
        self._errors = []            # List of error records

    def record_api_call(self, service: str, endpoint: str, latency_ms: float,
                        status_code: int = 200, success: bool = True,
                        metadata: dict = None):
        with self._lock:
            self._api_calls.append({
                "timestamp": datetime.utcnow().isoformat(),
                "service": service,
                "endpoint": endpoint,
                "latency_ms": round(latency_ms, 2),
                "status_code": status_code,
                "success": success,
                "metadata": json.dumps(metadata or {}),
            })

    def record_query(self, user_id: int, city: str, query_type: str,
                     lat: float = None, lon: float = None,
                     response_time_ms: float = None):
        with self._lock:
            self._queries.append({
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "city": city,
                "query_type": query_type,
                "lat": lat,
                "lon": lon,
                "response_time_ms": round(response_time_ms, 2) if response_time_ms else None,
            })

    def record_llm_call(self, model: str, prompt_tokens: int, completion_tokens: int,
                        total_tokens: int, latency_ms: float, success: bool = True,
                        call_type: str = "chat", error: str = None):
        with self._lock:
            self._llm_calls.append({
                "timestamp": datetime.utcnow().isoformat(),
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "latency_ms": round(latency_ms, 2),
                "success": success,
                "call_type": call_type,
                "error": error,
            })

    def record_error(self, service: str, error_type: str, message: str,
                     stack_trace: str = None):
        with self._lock:
            self._errors.append({
                "timestamp": datetime.utcnow().isoformat(),
                "service": service,
                "error_type": error_type,
                "message": message[:500],
                "stack_trace": (stack_trace or "")[:2000],
            })

    def flush(self):
        """Return and clear all buffered records."""
        with self._lock:
            data = {
                "api_calls": list(self._api_calls),
                "queries": list(self._queries),
                "llm_calls": list(self._llm_calls),
                "errors": list(self._errors),
            }
            self._api_calls.clear()
            self._queries.clear()
            self._llm_calls.clear()
            self._errors.clear()
            return data

    def get_snapshot(self):
        """Get current data without clearing (for display)."""
        with self._lock:
            return {
                "api_calls": list(self._api_calls),
                "queries": list(self._queries),
                "llm_calls": list(self._llm_calls),
                "errors": list(self._errors),
            }


# Global buffer instance
_buffer = MetricsBuffer()


# ──────────────────────────────────────────────
# Database Tables for Persistent Metrics
# ──────────────────────────────────────────────

def _get_connection():
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise ConnectionError("DATABASE_URL not set")
    return psycopg2.connect(database_url)


def init_monitoring_tables():
    """Create monitoring tables if they don't exist."""
    conn = _get_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS wt_api_metrics (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                service VARCHAR(50) NOT NULL,
                endpoint VARCHAR(200),
                latency_ms FLOAT NOT NULL,
                status_code INTEGER DEFAULT 200,
                success BOOLEAN DEFAULT TRUE,
                metadata JSONB DEFAULT '{}'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS wt_query_log (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                city VARCHAR(200),
                query_type VARCHAR(50),
                lat FLOAT,
                lon FLOAT,
                response_time_ms FLOAT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS wt_llm_metrics (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                model VARCHAR(100),
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                latency_ms FLOAT NOT NULL,
                success BOOLEAN DEFAULT TRUE,
                call_type VARCHAR(50) DEFAULT 'chat',
                error TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS wt_error_log (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                service VARCHAR(50) NOT NULL,
                error_type VARCHAR(100),
                message TEXT,
                stack_trace TEXT
            )
        """)

        # Create indexes for efficient querying
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_metrics_ts 
            ON wt_api_metrics(timestamp DESC)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_metrics_service 
            ON wt_api_metrics(service)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_log_ts 
            ON wt_query_log(timestamp DESC)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_log_city 
            ON wt_query_log(city)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_metrics_ts 
            ON wt_llm_metrics(timestamp DESC)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_error_log_ts 
            ON wt_error_log(timestamp DESC)
        """)

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[Monitoring] Table init error: {e}")
    finally:
        conn.close()


def flush_to_database():
    """Flush all buffered metrics to PostgreSQL."""
    data = _buffer.flush()

    if not any(data.values()):
        return  # Nothing to flush

    try:
        conn = _get_connection()
        cur = conn.cursor()

        # Insert API calls
        for record in data["api_calls"]:
            cur.execute(
                """INSERT INTO wt_api_metrics 
                   (timestamp, service, endpoint, latency_ms, status_code, success, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (record["timestamp"], record["service"], record["endpoint"],
                 record["latency_ms"], record["status_code"], record["success"],
                 record["metadata"])
            )

        # Insert queries
        for record in data["queries"]:
            cur.execute(
                """INSERT INTO wt_query_log 
                   (timestamp, user_id, city, query_type, lat, lon, response_time_ms)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (record["timestamp"], record["user_id"], record["city"],
                 record["query_type"], record["lat"], record["lon"],
                 record["response_time_ms"])
            )

        # Insert LLM calls
        for record in data["llm_calls"]:
            cur.execute(
                """INSERT INTO wt_llm_metrics 
                   (timestamp, model, prompt_tokens, completion_tokens, total_tokens,
                    latency_ms, success, call_type, error)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (record["timestamp"], record["model"], record["prompt_tokens"],
                 record["completion_tokens"], record["total_tokens"],
                 record["latency_ms"], record["success"], record["call_type"],
                 record["error"])
            )

        # Insert errors
        for record in data["errors"]:
            cur.execute(
                """INSERT INTO wt_error_log 
                   (timestamp, service, error_type, message, stack_trace)
                   VALUES (%s, %s, %s, %s, %s)""",
                (record["timestamp"], record["service"], record["error_type"],
                 record["message"], record["stack_trace"])
            )

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Monitoring] Flush error: {e}")


# ──────────────────────────────────────────────
# Instrumentation Decorators & Context Managers
# ──────────────────────────────────────────────

@contextmanager
def track_latency(service: str, endpoint: str = ""):
    """Context manager to track execution time of any block."""
    start = time.perf_counter()
    result = {"status_code": 200, "success": True, "metadata": {}}
    try:
        yield result
    except Exception as e:
        result["success"] = False
        result["status_code"] = 500
        result["metadata"]["error"] = str(e)
        _buffer.record_error(service, type(e).__name__, str(e))
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        _buffer.record_api_call(
            service=service,
            endpoint=endpoint,
            latency_ms=elapsed_ms,
            status_code=result["status_code"],
            success=result["success"],
            metadata=result["metadata"],
        )


def track_api_call(service: str, endpoint: str = ""):
    """Decorator to track API call latency and success/failure."""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            success = True
            status_code = 200
            error_msg = None
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                status_code = 500
                error_msg = str(e)
                _buffer.record_error(service, type(e).__name__, str(e))
                raise
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                _buffer.record_api_call(
                    service=service,
                    endpoint=endpoint or func.__name__,
                    latency_ms=elapsed_ms,
                    status_code=status_code,
                    success=success,
                    metadata={"error": error_msg} if error_msg else {},
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            success = True
            status_code = 200
            error_msg = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                status_code = 500
                error_msg = str(e)
                _buffer.record_error(service, type(e).__name__, str(e))
                raise
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                _buffer.record_api_call(
                    service=service,
                    endpoint=endpoint or func.__name__,
                    latency_ms=elapsed_ms,
                    status_code=status_code,
                    success=success,
                    metadata={"error": error_msg} if error_msg else {},
                )

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def record_query(user_id: int, city: str, query_type: str,
                 lat: float = None, lon: float = None,
                 response_time_ms: float = None):
    """Record a user query for analytics."""
    _buffer.record_query(user_id, city, query_type, lat, lon, response_time_ms)


def record_llm_call(model: str, prompt_tokens: int, completion_tokens: int,
                    total_tokens: int, latency_ms: float, success: bool = True,
                    call_type: str = "chat", error: str = None):
    """Record an LLM API call for performance tracking."""
    _buffer.record_llm_call(model, prompt_tokens, completion_tokens,
                            total_tokens, latency_ms, success, call_type, error)


def record_error(service: str, error_type: str, message: str,
                 stack_trace: str = None):
    """Record an error for debugging."""
    _buffer.record_error(service, error_type, message, stack_trace)


# ──────────────────────────────────────────────
# Query Functions (for the monitoring dashboard)
# ──────────────────────────────────────────────

def get_api_metrics(hours: int = 24, service: str = None) -> list:
    """Get API call metrics for the last N hours."""
    try:
        conn = _get_connection()
        cur = conn.cursor()
        query = """
            SELECT timestamp, service, endpoint, latency_ms, status_code, success, metadata
            FROM wt_api_metrics
            WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
        """
        params = [hours]
        if service:
            query += " AND service = %s"
            params.append(service)
        query += " ORDER BY timestamp DESC LIMIT 1000"

        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        return [
            {
                "timestamp": r[0].isoformat() if r[0] else None,
                "service": r[1],
                "endpoint": r[2],
                "latency_ms": r[3],
                "status_code": r[4],
                "success": r[5],
                "metadata": r[6],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[Monitoring] Query error: {e}")
        return []


def get_query_analytics(hours: int = 24) -> dict:
    """Get query analytics for the last N hours."""
    try:
        conn = _get_connection()
        cur = conn.cursor()

        # Total queries
        cur.execute(
            "SELECT COUNT(*) FROM wt_query_log WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'",
            (hours,)
        )
        total_queries = cur.fetchone()[0]

        # Top cities
        cur.execute("""
            SELECT city, COUNT(*) as cnt
            FROM wt_query_log
            WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
              AND city IS NOT NULL
            GROUP BY city
            ORDER BY cnt DESC
            LIMIT 10
        """, (hours,))
        top_cities = [{"city": r[0], "count": r[1]} for r in cur.fetchall()]

        # Queries by type
        cur.execute("""
            SELECT query_type, COUNT(*) as cnt
            FROM wt_query_log
            WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
            GROUP BY query_type
            ORDER BY cnt DESC
        """, (hours,))
        by_type = [{"type": r[0], "count": r[1]} for r in cur.fetchall()]

        # Average response time
        cur.execute("""
            SELECT AVG(response_time_ms), MIN(response_time_ms), MAX(response_time_ms)
            FROM wt_query_log
            WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
              AND response_time_ms IS NOT NULL
        """, (hours,))
        row = cur.fetchone()
        avg_response = row[0] if row[0] else 0
        min_response = row[1] if row[1] else 0
        max_response = row[2] if row[2] else 0

        # Queries per hour (for timeline chart)
        cur.execute("""
            SELECT date_trunc('hour', timestamp) as hour, COUNT(*)
            FROM wt_query_log
            WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
            GROUP BY hour
            ORDER BY hour
        """, (hours,))
        hourly = [{"hour": r[0].isoformat() if r[0] else None, "count": r[1]}
                  for r in cur.fetchall()]

        # Unique users
        cur.execute("""
            SELECT COUNT(DISTINCT user_id)
            FROM wt_query_log
            WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
              AND user_id IS NOT NULL
        """, (hours,))
        unique_users = cur.fetchone()[0]

        conn.close()

        return {
            "total_queries": total_queries,
            "unique_users": unique_users,
            "top_cities": top_cities,
            "by_type": by_type,
            "avg_response_ms": round(avg_response, 1),
            "min_response_ms": round(min_response, 1),
            "max_response_ms": round(max_response, 1),
            "hourly_timeline": hourly,
        }
    except Exception as e:
        print(f"[Monitoring] Analytics error: {e}")
        return {
            "total_queries": 0, "unique_users": 0, "top_cities": [],
            "by_type": [], "avg_response_ms": 0, "min_response_ms": 0,
            "max_response_ms": 0, "hourly_timeline": [],
        }


def get_llm_metrics(hours: int = 24) -> dict:
    """Get LLM performance metrics for the last N hours."""
    try:
        conn = _get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT COUNT(*), 
                   AVG(latency_ms), 
                   AVG(total_tokens),
                   AVG(prompt_tokens),
                   AVG(completion_tokens),
                   SUM(total_tokens),
                   SUM(CASE WHEN success THEN 1 ELSE 0 END),
                   MIN(latency_ms),
                   MAX(latency_ms)
            FROM wt_llm_metrics
            WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
        """, (hours,))
        row = cur.fetchone()

        total_calls = row[0] if row[0] else 0
        avg_latency = row[1] if row[1] else 0
        avg_tokens = row[2] if row[2] else 0
        avg_prompt = row[3] if row[3] else 0
        avg_completion = row[4] if row[4] else 0
        total_tokens = row[5] if row[5] else 0
        successful = row[6] if row[6] else 0
        min_latency = row[7] if row[7] else 0
        max_latency = row[8] if row[8] else 0

        # By call type
        cur.execute("""
            SELECT call_type, COUNT(*), AVG(latency_ms), AVG(total_tokens)
            FROM wt_llm_metrics
            WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
            GROUP BY call_type
        """, (hours,))
        by_type = [
            {"type": r[0], "count": r[1],
             "avg_latency_ms": round(r[2], 1) if r[2] else 0,
             "avg_tokens": round(r[3], 0) if r[3] else 0}
            for r in cur.fetchall()
        ]

        # Latency over time (hourly buckets)
        cur.execute("""
            SELECT date_trunc('hour', timestamp) as hour,
                   AVG(latency_ms), COUNT(*)
            FROM wt_llm_metrics
            WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
            GROUP BY hour
            ORDER BY hour
        """, (hours,))
        latency_timeline = [
            {"hour": r[0].isoformat() if r[0] else None,
             "avg_latency_ms": round(r[1], 1) if r[1] else 0,
             "count": r[2]}
            for r in cur.fetchall()
        ]

        # Recent errors
        cur.execute("""
            SELECT timestamp, call_type, error
            FROM wt_llm_metrics
            WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
              AND success = FALSE
            ORDER BY timestamp DESC
            LIMIT 10
        """, (hours,))
        recent_errors = [
            {"timestamp": r[0].isoformat() if r[0] else None,
             "call_type": r[1], "error": r[2]}
            for r in cur.fetchall()
        ]

        conn.close()

        success_rate = (successful / total_calls * 100) if total_calls > 0 else 100

        return {
            "total_calls": total_calls,
            "success_rate": round(success_rate, 1),
            "avg_latency_ms": round(avg_latency, 1),
            "min_latency_ms": round(min_latency, 1),
            "max_latency_ms": round(max_latency, 1),
            "avg_tokens": round(avg_tokens, 0),
            "avg_prompt_tokens": round(avg_prompt, 0),
            "avg_completion_tokens": round(avg_completion, 0),
            "total_tokens_used": total_tokens,
            "by_type": by_type,
            "latency_timeline": latency_timeline,
            "recent_errors": recent_errors,
        }
    except Exception as e:
        print(f"[Monitoring] LLM metrics error: {e}")
        return {
            "total_calls": 0, "success_rate": 100, "avg_latency_ms": 0,
            "min_latency_ms": 0, "max_latency_ms": 0, "avg_tokens": 0,
            "avg_prompt_tokens": 0, "avg_completion_tokens": 0,
            "total_tokens_used": 0, "by_type": [], "latency_timeline": [],
            "recent_errors": [],
        }


def get_api_health(hours: int = 24) -> dict:
    """Get API health summary (success rates per service)."""
    try:
        conn = _get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT service,
                   COUNT(*) as total,
                   SUM(CASE WHEN success THEN 1 ELSE 0 END) as ok,
                   AVG(latency_ms) as avg_lat,
                   MAX(latency_ms) as max_lat,
                   MIN(latency_ms) as min_lat
            FROM wt_api_metrics
            WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
            GROUP BY service
        """, (hours,))
        rows = cur.fetchall()
        conn.close()

        services = {}
        for r in rows:
            total = r[1]
            ok = r[2]
            rate = (ok / total * 100) if total > 0 else 100
            services[r[0]] = {
                "total_calls": total,
                "success_count": ok,
                "success_rate": round(rate, 1),
                "avg_latency_ms": round(r[3], 1) if r[3] else 0,
                "max_latency_ms": round(r[4], 1) if r[4] else 0,
                "min_latency_ms": round(r[5], 1) if r[5] else 0,
                "status": "✅" if rate >= 99 else ("⚠️" if rate >= 95 else "❌"),
            }

        return services
    except Exception as e:
        print(f"[Monitoring] Health error: {e}")
        return {}


def get_error_log(hours: int = 24, limit: int = 50) -> list:
    """Get recent error log entries."""
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT timestamp, service, error_type, message, stack_trace
            FROM wt_error_log
            WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '%s hours'
            ORDER BY timestamp DESC
            LIMIT %s
        """, (hours, limit))
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "timestamp": r[0].isoformat() if r[0] else None,
                "service": r[1],
                "error_type": r[2],
                "message": r[3],
                "stack_trace": r[4],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[Monitoring] Error log query error: {e}")
        return []


def get_recent_queries(limit: int = 20) -> list:
    """Get the most recent user queries."""
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT timestamp, user_id, city, query_type, response_time_ms
            FROM wt_query_log
            ORDER BY timestamp DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "timestamp": r[0].isoformat() if r[0] else None,
                "user_id": r[1],
                "city": r[2],
                "query_type": r[3],
                "response_time_ms": round(r[4], 1) if r[4] else None,
            }
            for r in rows
        ]
    except Exception as e:
        return []


def get_system_summary(hours: int = 24) -> dict:
    """Get a high-level system summary combining all metrics."""
    query_analytics = get_query_analytics(hours)
    llm_metrics = get_llm_metrics(hours)
    api_health = get_api_health(hours)
    error_count = len(get_error_log(hours))

    return {
        "total_queries": query_analytics["total_queries"],
        "unique_users": query_analytics["unique_users"],
        "avg_response_ms": query_analytics["avg_response_ms"],
        "llm_calls": llm_metrics["total_calls"],
        "llm_success_rate": llm_metrics["success_rate"],
        "llm_avg_latency_ms": llm_metrics["avg_latency_ms"],
        "total_tokens_used": llm_metrics["total_tokens_used"],
        "api_services": api_health,
        "error_count": error_count,
        "top_city": query_analytics["top_cities"][0]["city"] if query_analytics["top_cities"] else "N/A",
    }


# ──────────────────────────────────────────────
# Background Flush Thread
# ──────────────────────────────────────────────

_flush_thread_started = False


def start_flush_thread(interval_seconds: int = 30):
    """Start a background thread that flushes metrics to DB periodically."""
    global _flush_thread_started
    if _flush_thread_started:
        return

    def _flush_loop():
        while True:
            try:
                flush_to_database()
            except Exception as e:
                print(f"[Monitoring] Flush thread error: {e}")
            time.sleep(interval_seconds)

    t = threading.Thread(target=_flush_loop, daemon=True)
    t.start()
    _flush_thread_started = True


# Auto-start on import
try:
    init_monitoring_tables()
    start_flush_thread(30)
except Exception as e:
    print(f"[Monitoring] Init warning: {e}")