#!/usr/bin/env bash
# Run multiple LLM reference game simulations across groups.
#
# Usage:
#   bash analysis/llm_simulation/run_llm_simulation.sh                              # 20 groups
#   bash analysis/llm_simulation/run_llm_simulation.sh --num-groups 2 --blocks 2    # quick test
#   bash analysis/llm_simulation/run_llm_simulation.sh --model gemini-3-pro-preview
#   bash analysis/llm_simulation/run_llm_simulation.sh --temperature 0              # deterministic
#   bash analysis/llm_simulation/run_llm_simulation.sh --temperature 1              # default sampling

set -euo pipefail

NUM_GROUPS=20
MODEL="gemini-2.0-flash"
TANGRAM_SET=0
BLOCKS=6
TEMPERATURE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --num-groups) NUM_GROUPS="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --tangram-set) TANGRAM_SET="$2"; shift 2 ;;
        --blocks) BLOCKS="$2"; shift 2 ;;
        --temperature) TEMPERATURE="$2"; shift 2 ;;
        --help)
            echo "Usage: $0 [--num-groups N] [--model MODEL] [--tangram-set 0|1] [--blocks N] [--temperature T]"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="analysis/llm_simulation/llm_results_${TIMESTAMP}"
mkdir -p "$OUTPUT_DIR"

# Save config
cat > "$OUTPUT_DIR/config.json" <<EOF
{
  "num_groups": $NUM_GROUPS,
  "model": "$MODEL",
  "tangram_set": $TANGRAM_SET,
  "blocks": $BLOCKS,
  "temperature": ${TEMPERATURE:-null},
  "timestamp": "$TIMESTAMP"
}
EOF

echo "LLM Simulation"
echo "============================================"
echo "Groups: $NUM_GROUPS"
echo "Model: $MODEL"
echo "Tangram set: $TANGRAM_SET"
echo "Blocks: $BLOCKS"
echo "Temperature: ${TEMPERATURE:-API default}"
echo "Output: $OUTPUT_DIR"
echo "============================================"

TEMP_FLAG=""
if [[ -n "$TEMPERATURE" ]]; then
    TEMP_FLAG="--temperature $TEMPERATURE"
fi

for i in $(seq 1 "$NUM_GROUPS"); do
    GROUP_ID=$(printf "G%02d" "$i")
    OUTPUT_FILE="$OUTPUT_DIR/${GROUP_ID}.json"
    SEED=$((42 + i))

    echo ""
    echo ">>> Running group $GROUP_ID (seed=$SEED) ..."
    uv run python analysis/llm_simulation/llm_simulation.py \
        --tangram-set "$TANGRAM_SET" \
        --blocks "$BLOCKS" \
        --model "$MODEL" \
        --group-id "$GROUP_ID" \
        --output "$OUTPUT_FILE" \
        --seed "$SEED" \
        $TEMP_FLAG

    echo ">>> Group $GROUP_ID done: $OUTPUT_FILE"
done

echo ""
echo "============================================"
echo "All $NUM_GROUPS groups complete."
echo "Results in: $OUTPUT_DIR"
