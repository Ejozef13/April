#!/usr/bin/env bash
# CPU only; never installs drivers, starts Ollama, or changes shared services.
set -euo pipefail
cd "$(dirname "$0")/.."
april_tools_dir="${APRIL_TOOLS_DIR:-$PWD/.tools}"
april_whisper_dir="$april_tools_dir/whisper.cpp"
april_whisper_commit=d1be6fde11ac6e0407606b4e42fe72d34add8037
mkdir -p "$april_tools_dir"
if [[ ! -e "$april_whisper_dir" ]]; then
  git clone --depth 1 --branch v1.9.5 https://github.com/ggml-org/whisper.cpp.git "$april_whisper_dir"
fi
[[ "$(git -C "$april_whisper_dir" rev-parse HEAD)" == "$april_whisper_commit" ]] || {
  echo 'Existing whisper.cpp checkout has a different revision; refusing to overwrite it.' >&2
  exit 1
}
.venv/bin/cmake -S "$april_whisper_dir" -B "$april_whisper_dir/build" \
  -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF -DGGML_HIP=OFF \
  -DGGML_VULKAN=OFF -DWHISPER_BUILD_TESTS=OFF -DGGML_NATIVE=OFF
.venv/bin/cmake --build "$april_whisper_dir/build" --target whisper-cli -j 4
"$april_whisper_dir/build/bin/whisper-cli" --help
.venv/bin/piper --help
echo "CPU tools prepared. Configure whisper_cli as $april_whisper_dir/build/bin/whisper-cli"
echo 'Model downloads and a real interaction are separate readiness checks; see docs/STACK.md.'
