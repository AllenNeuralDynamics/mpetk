class MTrainUnavailableError(Exception):
    """
    Exception raised when the LIMS server is unavailable.
    """

    pass


class MTrainBadResponse(Exception):
    """
    Bad return codes
    """

    def __inti__(self):
        self.response_code = None
        self.response = None


class MTrainURLFormatError(Exception):
    """
    Exception raised when the mtrain request can't build a URL properly.
    """
    pass
