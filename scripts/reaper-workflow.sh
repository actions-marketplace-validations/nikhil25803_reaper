#!/usr/bin/env bash

set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: reaper-workflow.sh --runtime local|docker --model MODEL.gguf

Scan and analyze the current directory, then generate a refactoring prompt.
EOF
}

fail() {
  echo "Error: $*" >&2
  exit 1
}

runtime=""
model=""
while (($#)); do
  case "$1" in
    --runtime)
      (($# >= 2)) || fail "--runtime requires local or docker"
      runtime="$2"
      shift 2
      ;;
    --model)
      (($# >= 2)) || fail "--model requires a GGUF file path"
      model="$2"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

[[ "$runtime" == "local" || "$runtime" == "docker" ]] || \
  fail "--runtime must be local or docker"
[[ -n "$model" ]] || fail "--model is required"
[[ -f "$model" && -r "$model" ]] || fail "model is not a readable file: $model"
command -v reaper >/dev/null 2>&1 || fail "reaper is not installed or not on PATH"
command -v curl >/dev/null 2>&1 || fail "curl is required to check llama-server"

model_dir="$(cd -- "$(dirname -- "$model")" && pwd -P)"
model_path="$model_dir/$(basename -- "$model")"
server_url="http://127.0.0.1:8080"
output_dir="$PWD/reaper-analysis"
server_log="$output_dir/llama-server.log"
llama_pid=""
container_id=""
llama_image="ghcr.io/ggml-org/llama.cpp:server"

reaper --check graphify >/dev/null

if [[ "$runtime" == "local" ]]; then
  command -v llama-server >/dev/null 2>&1 || \
    fail "local runtime requires llama-server on PATH"
else
  command -v docker >/dev/null 2>&1 || fail "docker is not installed or not on PATH"
  docker info >/dev/null 2>&1 || fail "docker daemon is not available"
  docker image inspect "$llama_image" >/dev/null 2>&1 || \
    fail "llama.cpp image is missing; run: docker pull $llama_image"
fi

if (echo >/dev/tcp/127.0.0.1/8080) >/dev/null 2>&1; then
  fail "port 8080 is already in use"
fi

mkdir -p "$output_dir"

cleanup() {
  if [[ -n "$container_id" ]]; then
    docker logs "$container_id" >"$server_log" 2>&1 || true
    docker stop "$container_id" >/dev/null 2>&1 || true
  fi
  if [[ -n "$llama_pid" ]] && kill -0 "$llama_pid" 2>/dev/null; then
    kill "$llama_pid" 2>/dev/null || true
    wait "$llama_pid" 2>/dev/null || true
  fi
}

show_server_log() {
  if [[ -n "$container_id" ]]; then
    docker logs "$container_id" >&2 || true
  elif [[ -f "$server_log" ]]; then
    cat "$server_log" >&2
  fi
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "$runtime" == "local" ]]; then
  llama-server \
    --model "$model_path" \
    --host 127.0.0.1 \
    --port 8080 \
    --ctx-size 16384 \
    --parallel 1 \
    >"$server_log" 2>&1 &
  llama_pid=$!
else
  container_id="$(
    docker run --detach --rm \
      --publish 127.0.0.1:8080:8080 \
      --volume "$model_path:/models/model.gguf:ro" \
      "$llama_image" \
      --model /models/model.gguf \
      --host 0.0.0.0 \
      --port 8080 \
      --ctx-size 16384 \
      --parallel 1
  )"
fi

ready=false
for _ in {1..60}; do
  if curl --fail --silent --max-time 2 "$server_url/health" >/dev/null; then
    ready=true
    break
  fi
  if [[ -n "$llama_pid" ]] && ! kill -0 "$llama_pid" 2>/dev/null; then
    break
  fi
  if [[ -n "$container_id" ]] && \
    [[ "$(docker inspect --format '{{.State.Running}}' "$container_id" 2>/dev/null)" != "true" ]]; then
    break
  fi
  sleep 2
done

if [[ "$ready" != "true" ]]; then
  show_server_log
  fail "llama-server did not become ready within 120 seconds"
fi

reaper --scan .
reaper analyze . --all --server "$server_url"
reaper prompt .

echo "Workflow complete: $output_dir/refactor-prompt.md"
