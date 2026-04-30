#!/usr/bin/env bash
set -euo pipefail
BASE_URL=${BASE_URL:-http://localhost:8000/api/v1}
DOC=${DOC:-sample_docs/acme_leave_policy.pdf}

echo "Health:"
curl -s "$BASE_URL/health"; echo

echo "Uploading $DOC"
UPLOAD_RESPONSE=$(curl -s -X POST "$BASE_URL/documents" -F "file=@$DOC")
echo "$UPLOAD_RESPONSE"
DOC_ID=$(printf '%s' "$UPLOAD_RESPONSE" | python3 -c 'import sys,json; print(json.load(sys.stdin)["document"]["id"])')

echo "Polling $DOC_ID"
for i in {1..60}; do
  STATUS=$(curl -s "$BASE_URL/documents/$DOC_ID")
  echo "$STATUS"
  STATE=$(printf '%s' "$STATUS" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')
  if [[ "$STATE" == "ready" || "$STATE" == "failed" ]]; then break; fi
  sleep 2
done

echo "Asking question"
curl -s -X POST "$BASE_URL/documents/$DOC_ID/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"How many vacation days do full-time employees receive?"}'
echo
