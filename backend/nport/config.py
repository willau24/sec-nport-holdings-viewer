SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

# This is required by the SEC's documented format.
# TODO: I'd set up env vars here
USER_AGENT = "Will McCormick willster2424@gmail.com"

# SEC caps requests at 10 req/s, so this stays comfortably under it
MAX_CONCURRENT_REQUESTS = 5

CONNECT_TIMEOUT = 10.0

# I saw some of the responses take long, so this is a generous timeout
READ_TIMEOUT = 60.0

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 0.5

NPORT_NS = "http://www.sec.gov/edgar/nport"
