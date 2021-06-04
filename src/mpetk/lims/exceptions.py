class LIMSUnavailableError(Exception):
    """
    Exception raised when the LIMS server is unavailable.
    """

    pass

class LIMSBadResponse(Exception):

    """
    Bad return codes 404, 
    """
    def __inti__(self):
        self.response_code = None
        self.response = None

class LIMSURLFormatError(Exception):
    """
    Exception raised when the lims_request.request can't build a URL properly.
    """

    pass
