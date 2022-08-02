"""
Module with helpers functions
"""
import time
from functools import wraps


def repeat(times: int, timeout: int, exceptions: list = []):
    """
    Simple repeat decorator for repeating inner functions or methods based on occurred exceptions.

    :param times: how many times function or method will be repeated.
    :param timeout: timeout in seconds between attempts.
    :param exceptions: list of exceptions to trigger repeat

    :return: depends on function or method from input.
    """

    def decorate(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            result = None
            for _ in range(times):
                result = fn(*args, **kwargs)
                if type(result) not in exceptions or result is None:
                    break
                time.sleep(timeout)
            return result

        return wrapper

    return decorate
