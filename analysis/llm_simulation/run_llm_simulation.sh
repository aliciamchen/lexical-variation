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
MODEL="gemini-3.1-pro-preview"
TANGRAM_SET=0
BLOCKS=6
TEMPERATURE=""
TOP_P=""
BOTH=false
OUTPUT_DIR=""
PARALLEL=1

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
        --parallel|-j) PARALLEL="$2"; shift 2 ;;
        --help)
            echo "Usage: $0 [--num-groups N] [--model MODEL] [--tangram-set 0|1] [--blocks N] [--temperature T] [--top-p P] [--both] [--output-dir DIR] [--parallel N]"
            echo ""
            echo "  --both        Run two conditions: nucleus (temp=1.0, top_p=0.95) and greedy (temp=0)"
            echo "  --output-dir  Reuse an existing results directory (for retrying failed groups)"
            echo "  --parallel N  Run N groups concurrently (default: 1, sequential)"
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
    echo "Parallel: $PARALLEL"
    echo "Output: $OUTPUT_DIR"
    echo "============================================"

    local FLAGS=""
    [[ -n "$TEMP" ]] && FLAGS="$FLAGS --temperature $TEMP"
    [[ -n "$TP" ]] && FLAGS="$FLAGS --top-p $TP"

    local FAILED=()
    local COMPLETED=0
    local PIDS=()
    local PID_GROUP=()
    local LOG_DIR="$OUTPUT_DIR/logs"
    mkdir -p "$LOG_DIR"

    for i in $(seq 1 "$NUM_GROUPS"); do
        GROUP_ID=$(printf "G%02d" "$i")
        OUTPUT_FILE="$OUTPUT_DIR/${GROUP_ID}.json"
        SEED=$((42 + i))

        # Skip groups that already completed (supports re-running after partial failure)
        if [[ -f "$OUTPUT_FILE" ]] && grep -q '"status": "complete"' "$OUTPUT_FILE" 2>/dev/null; then
            echo ">>> [$COND_NAME] Group $GROUP_ID already complete, skipping."
            COMPLETED=$((COMPLETED + 1))
            continue
        fi

        echo ">>> [$COND_NAME] Group $GROUP_ID (seed=$SEED) ..."

        if [[ "$PARALLEL" -gt 1 ]]; then
            # Run in background, log to file
            uv run python analysis/llm_simulation/llm_simulation.py \
                --tangram-set "$TANGRAM_SET" \
                --blocks "$BLOCKS" \
                --model "$MODEL" \
                --group-id "$GROUP_ID" \
                --output "$OUTPUT_FILE" \
                --seed "$SEED" \
                $FLAGS \
                > "$LOG_DIR/${GROUP_ID}.log" 2>&1 &
            PIDS+=($!)
            PID_GROUP+=("$GROUP_ID")

            # Wait if we've hit the concurrency limit
            if [[ ${#PIDS[@]} -ge $PARALLEL ]]; then
                # Wait for any one process to finish
                for idx in "${!PIDS[@]}"; do
                    if ! kill -0 "${PIDS[$idx]}" 2>/dev/null; then
                        wait "${PIDS[$idx]}" 2>/dev/null
                        if [[ $? -eq 0 ]]; then
                            echo ">>> Group ${PID_GROUP[$idx]} done."
                            COMPLETED=$((COMPLETED + 1))
                        else
                            echo ">>> ERROR: Group ${PID_GROUP[$idx]} failed. See $LOG_DIR/${PID_GROUP[$idx]}.log"
                            FAILED+=("${PID_GROUP[$idx]}")
                        fi
                        unset 'PIDS[$idx]'
                        unset 'PID_GROUP[$idx]'
                        PIDS=("${PIDS[@]}")
                        PID_GROUP=("${PID_GROUP[@]}")
                        break
                    fi
                done
                # If none finished yet, wait for the first one
                if [[ ${#PIDS[@]} -ge $PARALLEL ]]; then
                    wait -n 2>/dev/null || true
                    for idx in "${!PIDS[@]}"; do
                        if ! kill -0 "${PIDS[$idx]}" 2>/dev/null; then
                            wait "${PIDS[$idx]}" 2>/dev/null
                            if [[ $? -eq 0 ]]; then
                                echo ">>> Group ${PID_GROUP[$idx]} done."
                                COMPLETED=$((COMPLETED + 1))
                            else
                                echo ">>> ERROR: Group ${PID_GROUP[$idx]} failed. See $LOG_DIR/${PID_GROUP[$idx]}.log"
                                FAILED+=("${PID_GROUP[$idx]}")
                            fi
                            unset 'PIDS[$idx]'
                            unset 'PID_GROUP[$idx]'
                            PIDS=("${PIDS[@]}")
                            PID_GROUP=("${PID_GROUP[@]}")
                            break
                        fi
                    done
                fi
            fi
        else
            # Sequential (original behavior)
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
        fi
    done

    # Wait for remaining background processes
    for idx in "${!PIDS[@]}"; do
        wait "${PIDS[$idx]}" 2>/dev/null
        if [[ $? -eq 0 ]]; then
            echo ">>> Group ${PID_GROUP[$idx]} done."
            COMPLETED=$((COMPLETED + 1))
        else
            echo ">>> ERROR: Group ${PID_GROUP[$idx]} failed. See $LOG_DIR/${PID_GROUP[$idx]}.log"
            FAILED+=("${PID_GROUP[$idx]}")
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
