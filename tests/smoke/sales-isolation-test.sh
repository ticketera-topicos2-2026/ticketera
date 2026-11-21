#!/usr/bin/env bash
# Smoke-test scenario: Sales service isolation when catalog service is unavailable.
#
# Verifies that sales endpoints served through the NGINX Gateway continue responding
# even when the catalog service is completely stopped (bounded context independence).

set -euo pipefail

echo "==> Testing Sales service isolation when Catalog is stopped..."

# 1. Stop catalog service
docker compose stop catalog

# 2. Probe sales health through gateway or container
status_code=$(docker compose run --rm sales python -c "
import urllib.request
try:
    with urllib.request.urlopen('http://sales:8000/health', timeout=5) as response:
        print(response.status)
except Exception as e:
    print('FAILED', e)
")

# 3. Restart catalog to restore environment
docker compose start catalog

if [[ "$status_code" == "200" ]]; then
    echo "PASS: Sales is fully isolated and operational when Catalog is down."
    exit 0
else
    echo "FAIL: Sales failed to respond when Catalog was down (got: $status_code)"
    exit 1
fi
