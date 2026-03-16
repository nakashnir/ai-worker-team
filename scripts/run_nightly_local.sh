#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

ORCH_URL="${ORCH_URL:-http://127.0.0.1:8080}"
DATASET_PATH="${DATASET_PATH:-datasets/sample_eval_valid_v1.jsonl}"
MODEL="${MODEL:-stub.echo_expected}"
SCORERS_JSON="${SCORERS_JSON:-[\"exact_match\",\"contains_expected\",\"format_nonempty\"]}"
MAX_POLLS="${MAX_POLLS:-120}"
POLL_SLEEP_SECS="${POLL_SLEEP_SECS:-5}"

REPORT_DIR="${ROOT_DIR}/shared/reports"
mkdir -p "${REPORT_DIR}"

for cmd in curl python3; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "missing required command: ${cmd}" >&2
    exit 1
  fi
done

TS="$(date -u +%Y%m%dT%H%M%SZ)"
SUBMIT_JSON="${REPORT_DIR}/nightly_${TS}_submit.json"
STATUS_JSON="${REPORT_DIR}/nightly_${TS}_status.json"
EVAL_JSON="${REPORT_DIR}/nightly_${TS}_eval_run.json"

echo "[nightly] submitting eval.run task to ${ORCH_URL}"
curl -fsS -X POST "${ORCH_URL}/task/submit" \
  -H "Content-Type: application/json" \
  -d "{
    \"description\": \"nightly regression eval\",
    \"task_type\": \"eval.run\",
    \"inputs\": {
      \"dataset_path\": \"${DATASET_PATH}\",
      \"model\": \"${MODEL}\",
      \"scorers\": ${SCORERS_JSON}
    }
  }" > "${SUBMIT_JSON}"

TASK_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["task_id"])' "${SUBMIT_JSON}")"
echo "[nightly] task_id=${TASK_ID}"

attempt=0
while true; do
  attempt=$((attempt + 1))
  curl -fsS "${ORCH_URL}/task/status/${TASK_ID}" > "${STATUS_JSON}"
  STATUS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "${STATUS_JSON}")"
  echo "[nightly] poll=${attempt} status=${STATUS}"

  if [[ "${STATUS}" == "done" ]]; then
    break
  fi
  if [[ "${STATUS}" == "failed" ]]; then
    echo "[nightly] task failed; see ${STATUS_JSON}" >&2
    exit 1
  fi
  if (( attempt >= MAX_POLLS )); then
    echo "[nightly] timeout waiting for completion (${MAX_POLLS} polls)" >&2
    exit 1
  fi
  sleep "${POLL_SLEEP_SECS}"
done

curl -fsS "${ORCH_URL}/eval/run/${TASK_ID}" > "${EVAL_JSON}"
echo "[nightly] wrote eval payload to ${EVAL_JSON}"

python3 scripts/check_regression.py \
  --baseline baselines/eval_valid_v1_baseline.json \
  --actual "${EVAL_JSON}"

echo "[nightly] regression check completed successfully"
