#!/usr/bin/env bash
set -euo pipefail

input_dir="${1:-}"
output_file="${2:-master.json}"

if [[ -z "$input_dir" || ! -d "$input_dir" ]]; then
  echo "Usage: $0 /path/to/reviews_dir [output_file]"
  exit 1
fi

if ! command -v jq &> /dev/null; then
  echo "Error: jq is not installed. Please install jq to use this script."
  exit 1
fi

shopt -s nullglob
json_files=("$input_dir"/*.json)
shopt -u nullglob

if [[ ${#json_files[@]} -eq 0 ]]; then
  echo "No JSON files found in '$input_dir'."
  exit 1
fi

jq -s '[.[][]]' "${json_files[@]}" > "$output_file"

echo "✅ Merged ${#json_files[@]} files into '$output_file'."
