#!/bin/sh
set -eu

for dir in data source_cache pages_cache graphs_cache markdown_cache relations_cache ocr_cache vlm_cache images_cache; do
  source="/legacy/$dir"
  target="/data/$dir"
  if [ -d "$source" ] && [ -z "$(ls -A "$target")" ]; then
    cp -R "$source/." "$target/"
  fi
done

exec "$@"
