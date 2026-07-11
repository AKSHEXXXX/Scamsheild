"""
Circuit breaker wrapper for agent inference calls.
Provides automatic failover and health tracking for agent calls.
"""
import logging
import time
import functools
from typing import Callable, Any, Optional, Dict
from app.ml.model_loader import record_agent_error, record_agent_success, is_agent_healthy

logger = logging.getLogger("scamshield.circuit_breaker")


class CircuitBreaker:
    """
    Circuit breaker for agent inference calls.
    
    States:
    - CLOSED: Normal operation, calls go through
    - OPEN: Too many failures, calls fail fast
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        agent_id: str,
        failure_threshold: int = 3,
        recovery_timeout: int = 300,  # 5 minutes
        half_open_max_calls: int = 3,
    ):
        self.agent_id = agent_id
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = "CLOSED"
        self._failure_count = 0
        self._last_failure_time = 0
        self._half_open_calls = 0
    
    @property
    def state(self) -> str:
        if self._state == "OPEN":
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = "HALF_OPEN"
                self._half_open_calls = 0
                logger.info("[CIRCUIT BREAKER] %s: OPEN -> HALF_OPEN", self.agent_id)
        return self._state
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        current_state = self.state
        
        if current_state == "OPEN":
            raise CircuitBreakerOpenError(
                f"Circuit breaker OPEN for {self.agent_id}. "
                f"Retry after {self.recovery_timeout}s."
            )
        
        if current_state == "HALF_OPEN":
            if self._half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker HALF_OPEN for {self.agent_id}. "
                    f"Max test calls ({self.half_open_max_calls}) reached."
                )
            self._half_open_calls += 1
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        if self._state == "HALF_OPEN":
            self._state = "CLOSED"
            self._failure_count = 0
            logger.info("[CIRCUIT BREAKER] %s: HALF_OPEN -> CLOSED (recovered)", self.agent_id)
        elif self._state == "CLOSED":
            self._failure_count = 0
        record_agent_success(self.agent_id)
    
    def _on_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        record_agent_error(self.agent_id)
        
        if self._state == "HALF_OPEN":
            self._state = "OPEN"
            logger.warning("[CIRCUIT BREAKER] %s: HALF_OPEN -> OPEN (test call failed)", self.agent_id)
        elif self._state == "CLOSED" and self._failure_count >= self.failure_threshold:
            self._state = "OPEN"
            logger.warning(
                "[CIRCUIT BREAKER] %s: CLOSED -> OPEN (%d consecutive failures)",
                self.agent_id, self._failure_count
            )
    
    def get_status(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "state": self.state,
            "failure_count": self._failure_count,
            "last_failure": self._last_failure_time,
        }
    
    def reset(self):
        self._state = "CLOSED"
        self._failure_count = 0
        self._last_failure_time = 0
        self._half_open_calls = 0
        logger.info("[CIRCUIT BREAKER] %s: MANUAL RESET", self.agent_id)


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is OPEN and call is rejected."""
    pass


# Global circuit breaker registry
_CIRCUIT_BREAKERS: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(agent_id: str) -> CircuitBreaker:
    """Get or create circuit breaker for an agent."""
    if agent_id not in _CIRCUIT_BREAKERS:
        _CIRCUIT_BREAKERS[agent_id] = CircuitBreaker(agent_id)
    return _CIRCUIT_BREAKERS[agent_id]


def with_circuit_breaker(agent_id: str):
    """
    Decorator to wrap agent inference functions with circuit breaker.
    
    Usage:
        @with_circuit_breaker("agent1")
        def agent1_predict_text(text: str) -> float:
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Quick health check first
            if not is_agent_healthy(agent_id):
                logger.warning("Agent %s unhealthy, skipping", agent_id)
                return -1.0  # Skip signal
            
            breaker = get_circuit_breaker(agent_id)
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


def get_all_circuit_breaker_status() -> Dict[str, Dict]:
    """Get status of all circuit breakers."""
    return {aid: cb.get_status() for aid, cb in _CIRCUIT_BREAKERS.items()}


def reset_all_circuit_breakers():
    """Reset all circuit breakers (admin operation)."""
    for cb in _CIRCUIT_BREAKERS.values():
        cb.reset()
    logger.info("All circuit breakers reset")