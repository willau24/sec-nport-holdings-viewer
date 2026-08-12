class NportError(Exception):
    status = 500
    message = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        if message is not None:
            self.message = message
        super().__init__(self.message)

class InvalidCik(NportError):
    status = 400
    message = "CIK must be 1-10 digits."

class CikNotFound(NportError):
    status = 404
    message = "No SEC filer found with that CIK."

class NoNportFilings(NportError):
    status = 404
    message = (
        "This CIK has no N-PORT filings. It may be an operating company "
        "rather than a registered fund."
    )

class SeriesNotFound(NportError):
    status = 404
    message = (
        "That fund has no N-PORT filings available. It may be closed, merged, "
        "or not yet required to report."
    )

class EdgarUnavailable(NportError):
    status = 502
    message = "SEC EDGAR is unavailable. Please retry shortly."

class EdgarRateLimited(NportError):
    status = 429
    message = "Rate limited by SEC. Please wait a moment and try again."

class FilingParseError(NportError):
    status = 502
    message = "Could not parse the filing."

class UnrecognizedFiling(FilingParseError):
    message = "The filing document did not contain recognizable N-PORT data."
