class LIMSUnavailableError(Exception):
    """
    Exception raised when the LIMS server is unavailable.
    """

    pass


class LIMSURLFormatError(Exception):
    """
    Exception raised when the lims_request.request can't build a URL properly.
    """

    pass
