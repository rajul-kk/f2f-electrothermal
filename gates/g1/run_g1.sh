#!/bin/bash
# One S8-style gcd/ibex replicate in a fresh Kaggle CPU session. Set G1_RUN_ID in the notebook.
# Do not reuse a session's /tmp/rs or /kaggle/working/record.
set -uo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd) || exit 2
bundle=$script_dir
if [[ ! -f "$bundle/rs_lib.sh" && ! -f "$bundle/add_layers.py" ]]; then
    bundle=$(cd -- "$script_dir/../../dry/rs" && pwd) || exit 2
fi
if [[ ! ${G1_RUN_ID:-} =~ ^g1-[[:alnum:]][[:alnum:]_.-]*$ ]]; then
    printf '%s\n' 'Set a distinct G1_RUN_ID, for example g1-v1-r1.' >&2
    exit 2
fi

OUT=/kaggle/working
B=/tmp/rs
BUDGET_S=39600
TAR_RESERVE_S=1800
R=$OUT/record
if [[ -e "$OUT/flow_results.tgz" || -e "$OUT/flow_logs.tgz" ]] || ! mkdir "$R"; then
    printf '%s\n' 'G1 requires a fresh Kaggle output directory.' >&2
    exit 2
fi
printf '%s\n' "$G1_RUN_ID" > "$R/run_id.txt" || exit 2
if [[ $(nproc) != 4 ]] || ! mkdir "$B"; then
    printf '%s\n' 'G1 requires four available CPU threads and a fresh /tmp/rs.' | tee "$R/preflight_error.txt" >&2
    exit 2
fi

# Hashes from dry/rs/record/2026-11-20_s8_v1/script.sha256.
if ! printf '%s\n' \
    '43bddc33bf472264c177e2295fd810deaa7f908d143f0afb08108cbcb3920522  rs_lib.sh' \
    'ee3ca9c1241ed36f9170bd3761009cb7712c344da79d7e5f21f42a4860a9a950  add_layers.py' \
    | (cd -- "$bundle" && sha256sum -c -) > "$R/sidecars_check.txt" 2>&1; then
    cat "$R/sidecars_check.txt" >&2
    exit 2
fi
sha256sum -- "$script_dir/run_g1.sh" "$bundle/rs_lib.sh" "$bundle/add_layers.py" > "$R/script.sha256" || exit 2
source "$bundle/rs_lib.sh" || exit 2

record_packages() {
    dpkg-query -W -f='${binary:Package}\t${Version}\n' | LC_ALL=C sort > "$R/$1"
}

record_linked_libraries() {
    ldd "$B/orfs/tools/install/OpenROAD/bin/openroad" "$B/orfs/tools/install/yosys/bin/yosys" > "$R/ldd.txt" 2>&1 \
        || return 1
    if grep -q 'not found' "$R/ldd.txt"; then
        return 1
    fi
    # Ignore dynamic load addresses when comparing dependency identities.
    awk '$2 == "=>" && $3 ~ /^\// {print $3; next} $1 ~ /^\// && NF > 1 {print $1}' "$R/ldd.txt" \
        | LC_ALL=C sort -u \
        | while IFS= read -r library; do sha256sum -- "$library" || exit 1; done > "$R/linked_libraries.sha256" \
        || return 1
    [[ -s "$R/linked_libraries.sha256" ]]
}

collect_case() {
    local case_name=$1
    local case_path="asap7_3D/$case_name/openroad"
    local logs="$B/pin3d/logs/$case_path" summary route counts drc route_drc
    summary=$logs/final_summary.txt
    route=$logs/5_2_route.log
    counts=$(grep -hE '^\[INFO ORD-0030\] Using [0-9]+ thread\(s\)\.' "$logs"/*.log | LC_ALL=C sort -u) || return 1
    [[ "$counts" == '[INFO ORD-0030] Using 4 thread(s).' ]] || return 1
    grep -Fq 'INFO(RC): verified RCX rules='"$B"'/pin3d/platforms/asap7_3D/asap7_tech_1x_2A6M7M.rcx_patterns.rules routing_layers=15' \
        "$logs/6_report.log" || return 1
    drc=$(awk '/^DRC Violations[[:space:]]+[0-9]+[[:space:]]*$/ {print $NF}' "$summary") || return 1
    route_drc=$(awk '/Number of violations = [0-9]+\./ {n=$NF; sub(/\.$/, "", n)} END {print n}' "$route") \
        || return 1
    [[ "$drc" =~ ^[0-9]+$ && "$drc" == "$route_drc" ]] || return 1
    if [[ "$drc" != 0 && ! -s "$B/pin3d/reports/$case_path/5_route_drc.rpt" ]]; then
        return 1
    fi
    printf '%s\t%s\n' "$case_name" "$drc" >> "$R/final_route_drc.tsv" || return 1
    local final=("results/$case_path/6_final."{odb,def,v,sdc})
    (cd -- "$B/pin3d" && sha256sum -- "${final[@]}") >> "$R/final_outputs.sha256"
}

finish_g1() {
    local rc=$1 tree
    local log_dirs=()
    trap - EXIT
    finish_common "$rc"
    for tree in flow_logs flow_reports flow_run_logs; do
        [[ ! -d "$R/$tree" ]] || log_dirs+=("$tree")
    done
    if (( ${#log_dirs[@]} > 0 )); then
        if ! timeout -k 10 240 tar -czf "$OUT/flow_logs.tgz.partial" -C "$R" "${log_dirs[@]}" \
            || ! mv -- "$OUT/flow_logs.tgz.partial" "$OUT/flow_logs.tgz" \
            || ! (cd -- "$OUT" && sha256sum -- flow_logs.tgz) > "$R/flow_logs.sha256"; then
            log 'G1 log archive failed'
            rc=1
        fi
    fi
    if (( rc == 0 )); then
        if [[ ! -s "$OUT/flow_results.tgz" || ! -s "$OUT/flow_logs.tgz" || ! -s "$R/flow_results.sha256" \
            || ! -s "$R/final_outputs.sha256" ]] || ! grep -q 'results tar rc=0$' "$R/steps.log"; then
            log 'G1 archive evidence is incomplete'
            rc=1
        # The marker binds this run id to both archives and every record file, so no file from another replicate
        # (or edited after the run) passes the download check.
        elif ! { printf 'G1 artifacts complete: %s\n' "$G1_RUN_ID" \
                && (cd -- "$OUT" && sha256sum -- flow_results.tgz flow_logs.tgz \
                    && find record -type f ! -name 'complete.txt*' -print0 | LC_ALL=C sort -z \
                    | xargs -0 sha256sum --); } > "$R/complete.txt.partial" \
            || ! mv -- "$R/complete.txt.partial" "$R/complete.txt"; then
            rc=1
        fi
    fi
    exit "$rc"
}

lscpu > "$R/cpu.txt" || exit 2
record_packages packages_before_setup.tsv || exit 2
session_start
trap 'finish_g1 $?' EXIT
record_packages packages_after_setup.tsv || exit 2
record_linked_libraries || { log 'G1 could not fingerprint linked runtime libraries'; exit 2; }
step add_layers python3 "$bundle/add_layers.py" "$B/pin3d" --view direct --config || exit 1
cp -- "$B/pin3d/platforms/asap7_3D/config.mk" "$R/asap7_3D_config.mk" || exit 1
printf '%s\n' 'e331a03addecde361252cb46d6a0bc4333559a1416270062762eba79bb5f40c5  asap7_3D_config.mk' \
    | (cd -- "$R" && sha256sum -c -) > "$R/patched_config_check.txt" 2>&1 \
    || { log 'Patched platform config differs from S8'; exit 2; }
log 'G1: S8 direct view patched and verified; no flow overrides'
run_case gcd asap7_3D || exit 1
run_case ibex asap7_3D || exit 1
for case_name in gcd ibex; do
    collect_case "$case_name" || { log "G1 final evidence check failed for $case_name"; exit 1; }
done
