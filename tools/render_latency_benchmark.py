import json
import os
import statistics
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = os.environ["BASE_URL"].rstrip("/")
OPT_URL = os.environ["OPT_URL"].rstrip("/")
API_KEY = os.environ["API_KEY"]
SAMPLES = int(os.getenv("SAMPLES", "100"))
TIMEOUT = float(os.getenv("TIMEOUT", "20"))
TG_URL = os.environ.get(
    "TG_URL",
    "https://api.telegram.org/bot123456789:PERFTESTTOKEN/getMe",
)

PAYLOAD = {
    "symbol": "EURUSD",
    "direction": "BUY",
    "entry": 1.1000,
    "sl": 1.0950,
    "tp1": 1.1050,
    "tp2": 1.1100,
    "confidence": 80,
    "reasons": ["structure break confirmed", "liquidity sweep"],
    "timeframe": "M15",
}


def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    index = max(0, min(len(values) - 1, int((len(values) * q) + 0.999999) - 1))
    return values[index]


def timed_get(url, path, headers=None):
    req = Request(url + path, headers=headers or {})
    start = time.perf_counter()
    with urlopen(req, timeout=TIMEOUT) as response:
        body = response.read()
        status = response.status
    return (time.perf_counter() - start) * 1000.0, status, body


def timed_signal(url, signal_id):
    body = dict(PAYLOAD, signal_id=signal_id)
    req = Request(
        url + "/signal",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": API_KEY,
        },
        method="POST",
    )
    start = time.perf_counter()
    with urlopen(req, timeout=TIMEOUT) as response:
        parsed = json.loads(response.read())
        status = response.status
    return (time.perf_counter() - start) * 1000.0, status, parsed


def benchmark_service(name, url):
    first_ms, first_status, _ = timed_get(url, "/")
    db_samples = [timed_get(url, "/health/db")[0] for _ in range(25)]

    warm = []
    fingerprints = []
    for i in range(SAMPLES):
        elapsed, status, response = timed_signal(url, f"render-bench-{name}-{uuid.uuid4().hex}")
        if status != 200 or response.get("status") != "queued":
            raise RuntimeError(f"{name} /signal failed: {status} {response}")
        warm.append(elapsed)
        fingerprints.append(response["decision_fingerprint"])

    return {
        "first_root_ms": first_ms,
        "first_root_status": first_status,
        "db": {
            "p50_ms": statistics.median(db_samples),
            "p95_ms": percentile(db_samples, 0.95),
            "p99_ms": percentile(db_samples, 0.99),
        },
        "signal": {
            "p50_ms": statistics.median(warm),
            "p95_ms": percentile(warm, 0.95),
            "p99_ms": percentile(warm, 0.99),
            "min_ms": min(warm),
            "max_ms": max(warm),
        },
        "fingerprints": fingerprints,
    }


def benchmark_telegram():
    samples = []
    statuses = []
    for _ in range(20):
        start = time.perf_counter()
        try:
            with urlopen(Request(TG_URL), timeout=TIMEOUT) as response:
                response.read()
                statuses.append(response.status)
        except HTTPError as exc:
            exc.read()
            statuses.append(exc.code)
        except URLError as exc:
            raise RuntimeError(f"Telegram API request failed: {exc}") from exc
        samples.append((time.perf_counter() - start) * 1000.0)
    return {
        "p50_ms": statistics.median(samples),
        "p95_ms": percentile(samples, 0.95),
        "p99_ms": percentile(samples, 0.99),
        "statuses": sorted(set(statuses)),
    }


baseline = benchmark_service("baseline", BASE_URL)
optimized = benchmark_service("optimized", OPT_URL)

bfp = set(baseline.pop("fingerprints"))
ofp = set(optimized.pop("fingerprints"))
if bfp != ofp:
    raise RuntimeError("Signal fingerprint mismatch between baseline and optimized services")

result = {
    "samples_per_service": SAMPLES,
    "signal_fingerprint_equivalent": len(bfp) == 1 and bfp == ofp,
    "baseline": baseline,
    "optimized": optimized,
    "telegram_external_api": benchmark_telegram(),
}
print(json.dumps(result, indent=2, sort_keys=True))
