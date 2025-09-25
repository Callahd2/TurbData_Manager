import time
import logging
import functools

class LogDuration:
    """
    Context manager for timing a section. Logs start and end and logs exception stack trace.

        Usage:
                with log_duraction(log, "getData()", warn_if_over=2.0):
                    result = getData(...)
    """
    def __init__(self,
                 logger: logging.Logger,
                 label: str,
                 level: int = logging.INFO,
                 warn_if_over: float | None = None):

        self.logger = logger
        self.label = label
        self.level = level
        self.warn_if_over = warn_if_over

    def __enter__(self):
        self.t0 = time.perf_counter()
        self.logger.log(self.level, "%s - start", self.label)

        return self

    def __exit__(self, exec_type, exc, tb):
        dt = time.perf_counter() - self.t0

        if exc is not None:
            self.logger.exception("%s - failed in %.3fs", self.label, dt)

            return False

        if self.warn_if_over is not None and dt >= self.warn_if_over:
            self.logger.warning("%s - done in %.3fs (slow)", self.label, dt)

        else:
            self.logger.log(self.level, "%s, done in %.2fs", self.label, dt)

        return False



def log_duration_decorator(logger: logging.Logger,
                           label: str | None = None,
                           level: int = logging.INFO,
                           warn_if_over: float | None = None):
    """
    Decorator variant of log_duration. Times a function call and logs success/exception.

        Usage:
                @log_duration_decorator(log, "update_chunk", warn_if_over=0.5)
                def update_chunk(...):
    """

    def decorate(func):

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = label or func.__qualname__
            t0 = time.perf_counter()
            ok = False

            try:
                result = func(*args, **kwargs)
                ok = True
                return result

            except Exception:
                dt = time.perf_counter() - t0
                logger.exception("%s - failed in %.3fs", name, dt)
                raise

            finally:
                if ok:
                    dt = time.perf_counter() - t0

                    if warn_if_over is not None and dt >= warn_if_over:
                        logger.warning("%s - done in %3fs", name, dt)

                    else:
                        logger.log(level, "%s - done in %.3fs", name, dt)

        return wrapper
    return decorate









