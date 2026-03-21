#!/usr/bin/env bash
# Run multiple LLM reference game simulations across groups.
#
# Usage:
#   bash analysis/llm_simulation/run_llm_simulation.sh                              # 20 groups, nucleus sampling
#   bash analysis/llm_simulation/run_llm_simulation.sh --num-groups 2 --blocks 2    # quick test
#   bash analysis/llm_simulation/run_llm_simulation.sh --model gemini-3-pro-preview
#   bash analysis/llm_simulation/run_llm_simulation.sh --temperature 0              # greedy decoding
#   bash analysis/llm_simulation/run_llm_simulation.sh --both                       # run nucleus + greedy

set -uo pipefail

NUM_GROUPS=20
MODEL="gemini-2.0-flash"
TANGRAM_SET=0
BLOCKS=6
TEMPERATURE=""
TOP_P=""
BOTH=false
OUTPUT_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --num-groups|--num_groups) NUM_GROUPS="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --tangram-set) TANGRAM_SET="$2"; shift 2 ;;
        --blocks) BLOCKS="$2"; shift 2 ;;
        --temperature) TEMPERATURE="$2"; shift 2 ;;
        --top-p) TOP_P="$2"; shift 2 ;;
        --both) BOTH=true; shift ;;
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --help)
            echo "Usage: $0 [--num-groups N] [--model MODEL] [--tangram-set 0|1] [--blocks N] [--temperature T] [--top-p P] [--both] [--output-dir DIR]"
            echo ""
            echo "  --both        Run two conditions: nucleus (temp=1.0, top_p=0.95) and greedy (temp=0)"
            echo "  --output-dir  Reuse an existing results directory (for retrying failed groups)"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

run_condition() {
    local COND_NAME="$1"
    local TEMP="$2"
    local TP="$3"

    if [[ -z "$OUTPUT_DIR" ]]; then
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        OUTPUT_DIR="analysis/llm_simulation/llm_results_${COND_NAME}_${TIMESTAMP}"
    fi
    mkdir -p "$OUTPUT_DIR"

    # Save config
    cat > "$OUTPUT_DIR/config.json" <<EOF
{
  "num_groups": $NUM_GROUPS,
  "model": "$MODEL",
  "tangram_set": $TANGRAM_SET,
  "blocks": $BLOCKS,
  "temperature": ${TEMP:-null},
  "top_p": ${TP:-null},
  "condition": "$COND_NAME",
  "timestamp": "$TIMESTAMP"
}
EOF

    echo ""
    echo "============================================"
    echo "Condition: $COND_NAME"
    echo "Groups: $NUM_GROUPS"
    echo "Model: $MODEL"
    echo "Tangram set: $TANGRAM_SET"
    echo "Blocks: $BLOCKS"
    echo "Temperature: ${TEMP:-API default}"
    echo "Top-p: ${TP:-API default}"
    echo "Output: $OUTPUT_DIR"
    echo "============================================"

    local FLAGS=""
    [[ -n "$TEMP" ]] && FLAGS="$FLAGS --temperature $TEMP"
    [[ -n "$TP" ]] && FLAGS="$FLAGS --top-p $TP"

    local FAILED=()
    local COMPLETED=0

    for i in $(seq 1 "$NUM_GROUPS"); do
        GROUP_ID=$(printf "G%02d" "$i")
        OUTPUT_FILE="$OUTPUT_DIR/${GROUP_ID}.json"
        SEED=$((42 + i))

        # Skip groups that already completed (supports re-running after partial failure)
        if [[ -f "$OUTPUT_FILE" ]] && grep -q '"status": "complete"' "$OUTPUT_FILE" 2>/dev/null; then
            echo ""
            echo ">>> [$COND_NAME] Group $GROUP_ID already complete, skipping."
            COMPLETED=$((COMPLETED + 1))
            continue
        fi

        echo ""
        echo ">>> [$COND_NAME] Group $GROUP_ID (seed=$SEED) ..."
        if uv run python analysis/llm_simulation/llm_simulation.py \
            --tangram-set "$TANGRAM_SET" \
            --blocks "$BLOCKS" \
            --model "$MODEL" \
            --group-id "$GROUP_ID" \
            --output "$OUTPUT_FILE" \
            --seed "$SEED" \
            $FLAGS; then
            echo ">>> Group $GROUP_ID done: $OUTPUT_FILE"
            COMPLETED=$((COMPLETED + 1))
        else
            echo ">>> ERROR: Group $GROUP_ID failed (exit code $?). Continuing..."
            FAILED+=("$GROUP_ID")
        fi
    done

    echo ""
    echo "============================================"
    echo "Condition $COND_NAME: ${COMPLETED}/${NUM_GROUPS} groups completed."
    if [[ ${#FAILED[@]} -gt 0 ]]; then
        echo "FAILED groups: ${FAILED[*]}"
        echo "Re-run this script to retry failed/incomplete groups."
    fi
    echo "Results in: $OUTPUT_DIR"
}

if [[ "$BOTH" == true ]]; then
    echo "Running both conditions: nucleus (temp=1.0, top_p=0.95) and greedy (temp=0)"
    run_condition "nucleus" "1.0" "0.95"
    run_condition "greedy" "0" ""
    echo ""
    echo "============================================"
    echo "Both conditions complete."
else
    # Single condition
    COND_NAME="custom"
    if [[ -z "$TEMPERATURE" && -z "$TOP_P" ]]; then
        # Default: nucleus sampling (matches Vaduguru et al. 2025 tangram settings)
        TEMPERATURE="1.0"
        TOP_P="0.95"
        COND_NAME="nucleus"
    elif [[ "$TEMPERATURE" == "0" ]]; then
        COND_NAME="greedy"
    fi
    run_condition "$COND_NAME" "$TEMPERATURE" "$TOP_P"
fi
