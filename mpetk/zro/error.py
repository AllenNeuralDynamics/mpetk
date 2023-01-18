"""
error.py
"""
from zmq.error import Again

__all__ = ["ZroError", "ZroNoAttributeError", "ZroNoCallableError",
           "ZroAttrNotCallableError", "ZroCallableFailedError",
           "ZroArgumentsInvalidError", "ZroAsyncHandleInvalidError",
           "ZroResultUnfinishedError", "ZroCallbackFailedError", "Again"]

class ZroError(Exception):
    """ Base class for zro errors. """

    error_codes = {
        1: "{} -> HAS_NO_ATTRIBUTE -> {}",
        2: "{} -> HAS_NO_CALLABLE -> {}",
        3: "{} -> ATTRIBUTE_NOT_CALLABLE -> {}",
        4: "{} -> CALLABLE_FAILED -> {}",
        5: "{} -> ARGUMENTS_INVALID -> {}",
        6: "{} -> UNHANDLED_ERROR -> {}",
        7: "{} -> ASYNC_RESULT_INVALID_HANDLE -> {}",
        8: "{} -> ASYNC_RESULT_UNFINISHED -> {}",
        9: "{} -> ASYNC_CALLBACK_FAILED -> {}",
    }

    HAS_NO_ATTRIBUTE = 1
    HAS_NO_CALLABLE = 2
    ATTRIBUTE_NOT_CALLABLE = 3
    CALLABLE_FAILED = 4
    ARGUMENTS_INVALID = 5
    UNHANDLED_ERROR = 6
    ASYNC_RESULT_INVALID_HANDLE = 7
    ASYNC_RESULT_UNFINISHED = 8
    ASYNC_CALLBACK_FAILED = 9

    def __init__(self, obj=None, target=None, error_code=6, message=""):
        if not message:
            message = self.error_codes[error_code].format(obj, target)
        self.message = message
        self.error_code = error_code
        super(ZroError, self).__init__(message)

    def to_JSON(self):
        return {
            'ZroError': str(type(self.get_specific_error())), # this key lets zro convert this on the receive side
            'error_code': self.error_code,
            'message': str(self.message)
        }

    @staticmethod
    def from_dict(d):
        return ZroError(error_code=d['error_code'], message=d['message']).get_specific_error()

    def get_specific_error(self, to_raise=False):
        """ Get the appropriate ZroError for the error type. """
        err = _SPECIFIC_ERRORS[self.error_code](message=self.message)
        if to_raise:
            raise err
        return err


class ZroNoAttributeError(ZroError):
    """ Error for HAS_NO_ATTRIBUTE. """
    def __init__(self, obj=None, target=None, message=""):
        super(ZroNoAttributeError, self).__init__(
            obj, target, ZroError.HAS_NO_ATTRIBUTE, message)


class ZroNoCallableError(ZroError):
    """ Error for HAS_NO_CALLABLE. """
    def __init__(self, obj=None, target=None, message=""):
        super(ZroNoCallableError, self).__init__(
            obj, target, ZroError.HAS_NO_CALLABLE, message)


class ZroAttrNotCallableError(ZroError):
    """ Error for ATTRIBUTE_NOT_CALLABLE. """
    def __init__(self, obj=None, target=None, message=""):
        super(ZroAttrNotCallableError, self).__init__(
            obj, target, ZroError.ATTRIBUTE_NOT_CALLABLE, message)


class ZroCallableFailedError(ZroError):
    """ Error for CALLABLE_FAILED. """
    def __init__(self, obj=None, target=None, message=""):
        super(ZroCallableFailedError, self).__init__(
            obj, target, ZroError.CALLABLE_FAILED, message)


class ZroArgumentsInvalidError(ZroError):
    """ Error for ARGUMENTS_INVALID. """
    def __init__(self, obj=None, target=None, message=""):
        super(ZroArgumentsInvalidError, self).__init__(
            obj, target, ZroError.ARGUMENTS_INVALID, message)


class ZroAsyncHandleInvalidError(ZroError):
    """ Error for ASYNC_RESULT_INVALID_HANDLE. """
    def __init__(self, obj=None, target=None, message=""):
        super(ZroAsyncHandleInvalidError, self).__init__(
            obj, target, ZroError.ASYNC_RESULT_INVALID_HANDLE, message)


class ZroResultUnfinishedError(ZroError):
    """ Error for ASYNC_RESULT_UNFINISHED. """
    def __init__(self, obj=None, target=None, message=""):
        super(ZroResultUnfinishedError, self).__init__(
            obj, target, ZroError.ASYNC_RESULT_UNFINISHED, message)


class ZroCallbackFailedError(ZroError):
    """ Error for ASYNC_CALLBACK_FAILED. """
    def __init__(self, obj=None, target=None, message=""):
        super(ZroCallbackFailedError, self).__init__(
            obj, target, ZroError.ASYNC_CALLBACK_FAILED, message)


_SPECIFIC_ERRORS = {
    1: ZroNoAttributeError,
    2: ZroNoCallableError,
    3: ZroAttrNotCallableError,
    4: ZroCallableFailedError,
    5: ZroArgumentsInvalidError,
    6: ZroError,
    7: ZroAsyncHandleInvalidError,
    8: ZroResultUnfinishedError,
    9: ZroCallbackFailedError,
}
