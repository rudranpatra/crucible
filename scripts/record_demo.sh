#!/usr/bin/env bash
# Record a Crucible demo GIF
# Requirements: pip install asciinema && cargo install agg (or brew install agg)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRUCIBLE_DIR="$SCRIPT_DIR/../crucible"
CAST_FILE="$SCRIPT_DIR/../demo.cast"
GIF_FILE="$SCRIPT_DIR/../demo.gif"

echo "Recording Crucible demo..."
echo "Run: python cli/crucible.py attack --demo --rich"
echo "Then Ctrl+D to stop recording."
echo ""

cd "$CRUCIBLE_DIR"

# Record with asciinema
asciinema rec "$CAST_FILE" \
  --title "Crucible — Adversarial CI/CD Engine" \
  --cols 120 \
  --rows 40

echo ""
echo "Cast saved to $CAST_FILE"

# Convert to GIF if agg is available
if command -v agg &>/dev/null; then
  echo "Converting to GIF..."
  agg \
    --font-size 14 \
    --speed 1.5 \
    "$CAST_FILE" "$GIF_FILE"
  echo "GIF saved to $GIF_FILE"
  echo "Add to README: ![Crucible Demo](demo.gif)"
else
  echo ""
  echo "To convert to GIF, install agg:"
  echo "  cargo install agg          # via Rust"
  echo "  brew install agg           # via Homebrew (macOS)"
  echo ""
  echo "Then run:"
  echo "  agg --speed 1.5 $CAST_FILE $GIF_FILE"
  echo ""
  echo "Or upload the .cast file to https://asciinema.org and embed the player."
fi
