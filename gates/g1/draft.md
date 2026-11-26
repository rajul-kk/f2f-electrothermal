# G1 draft — Repeatability of the open ibex flow

**Status.** Draft for the student’s bars. The student selected option A on November 20, 2026 ([goals, decision 5](../../goals.md), [g1-baseline](../../tasks.json)).

## Question and why

How much do the final physical-design metrics vary when independent Kaggle CPU sessions run the same open `ord` flow on `ibex/asap7_3D`? G2 needs a traceable physical input. A measure of repeatability lets us distinguish differences between physical inputs from differences in the downstream thermal solvers.

S8 completed the flow at a 1.200 ns target with negative setup slack, 99 detailed-route markers on `hb_layer`, and some nets without detailed routes ([S8 record](../../dry/rs/record/2026-11-20_s8_v1/NOTE.md), [published comparison](../../dry/rs/published_ibex.md)). S8 supplies the setup, metric definitions and cost estimate. Its results are context for the repeatability runs. The RosettaStone 2.0 Table 2 Flexible 7+7 ORD `ibex` row is literature context. The paper used a 1.000 ns target, a different branch and Innovus v21.39 for timing, power and violations. Its authors describe Table 2 as a demonstration of flow completeness ([paper details and values](../../dry/rs/published_ibex.md)).

## What is compared

One fresh CPU session per replicate. Plan two valid replicates, with a third only if the student fixes the count before launch. Run `gcd` then `ibex` once per session, as in S8. `gcd` checks toolchain and setup completion. Its metrics are diagnostic. Evaluate the full range across the selected valid `ibex` replicates together. Log every attempt, and replace an invalid attempt under the same protocol and a new ID. A valid run outside a bar stays in the comparison.

Keep the same Kaggle CPU image and setup as S8, the same ORFS-Research and TaiWei-Pin-3D commits, the same S1 install archive and binary hashes, and the exact S8 `rs_lib.sh` and `add_layers.py` inputs. The G1 runner applies `--view direct --config` to enable upper routing layers `M2_add` and `M3_add`, pins `ASAP7_HBT_RDL := 0`, and verifies the 15-routing-layer extraction deck. Keep the `ibex` clock, floorplan and flow options unchanged from S8. The [S8 script and input hashes](../../dry/rs/record/2026-11-20_s8_v1/script.sha256) and [S8 note](../../dry/rs/record/2026-11-20_s8_v1/NOTE.md) identify the setup.

S8 ran on four available CPU threads, and its OpenROAD logs report four threads. `rs_lib.sh` sets `NUM_CORES` from `nproc`, so require `nproc=4` before setup and require the stage logs that report OpenROAD threads to report four. Keep the configured S8 seeds and defaults. Partitioning and detailed placement used seed 1 in the S8 `ibex` stage logs (`2_tritonpart.log:27`, `3_4_lg_bottom.log:397`, `3_5_lg_upper.log:951` in `flow_logs.tgz`). The independent worker and process scheduling can vary, including scheduling of OpenROAD’s parallel workers at the fixed thread count. No variation source has been isolated. Record the Kaggle job and session IDs, immutable image ID when exposed, OS, kernel, CPU model and flags, memory, installed packages before and after setup, and linked-library hashes for OpenROAD and Yosys. Compare the observable environment before deciding validity. If Kaggle exposes no immutable image ID, report the check as matched observed environment, with the student’s acceptance of that fallback fixed before launch.

## Proposed bars

Read `ibex/openroad/final_summary.txt` for every replicate. Use the same report precision across runs. Exact means the parsed values agree across all valid replicates. For positive continuous values, relative spread is `100 × (max − min) / mean`. Use max minus min in ps for setup metrics because slacks are signed and may approach zero. The tolerances below are proposed engineering limits. S8 is one observation and does not estimate run-to-run noise.

| Metric | Proposed bar | Reason |
|---|---:|---|
| Core area (µm²) | Exact | Fixed floorplan inputs should give the same footprint. |
| Std-cell area (µm²) | ≤0.1% relative | Allows small changes in the cell mix and flags larger implementation drift. |
| Total power (W) | ≤1.0% relative | Allows modest variation in the implemented cells and extraction. At S8’s reported 0.0213 W this is about two ticks of the printed precision. |
| Routed wirelength (µm) | ≤0.5% relative | Allows small route choices to vary. Use the final reporting value consistently. |
| Setup WNS (ps) | ≤1 ps absolute | Measures the movement of the worst endpoint on a time scale that works near zero. |
| Setup TNS (ps) | ≤10 ps absolute | Allows a small aggregate movement across endpoints. |
| Detailed-route DRC marker count | Exact | An integer outcome expected to repeat for the fixed inputs, seeds and thread count. |
| Failing endpoint count | Exact | Tests whether the count of failing setup endpoints repeats. |
| Physical bond-via count | Exact | Counts physical bond vias under the same reporting convention. |
| Cross-tier net count, `All` | Exact | Uses the same tier and IO classification as the S8 final summary. |

## Validity and verdict

A replicate requires a separately allocated CPU session, fresh trees, the intended job identity and pinned inputs, four available and effective threads, and matching image and userspace provenance under the agreed fallback. Verify `gcd` and `ibex` completed the flow, the last Pin-3D status is successful, and the `ibex` final report confirms the expected extraction deck and layer count. Require the completion marker, verified archive checksums, readable evidence and a single complete final summary per case. Check that area, power and wirelength are finite and positive, setup values finite, counts nonnegative integers, and the reported DRC count agrees with the final detailed-route log. Verify that the SDC clock and the recorded view match S8. For a zero-marker run, the final route log and summary must both explicitly report zero even when the marker file is absent or empty.

Use **INCONCLUSIVE** if a required replicate or its evidence is missing, corrupt, timed out, or uses a mismatched configuration, or if the agreed number of independent valid runs is unavailable. Keep its record and reason. Use **PASS** when the full set is valid and meets every registered spread bar. Use **FAIL** when the full set is valid and a registered bar is exceeded. A failure means the chosen setup does not reproduce that metric within the selected spread over these runs. Compare the saved stage evidence before assigning a cause.

## Reported with the verdict

Report final DRC rule and layer counts, stage or iteration where markers remain, unrouted-net warnings, the setup closure class, cross-tier net breakdown, `gcd` metrics, per-stage and total wall time and peak RAM, and machine differences. Keep the final ODB, DEF, netlist and SDC hashes per run. Hash differences help target inspection. File bytes can also differ for serialization or metadata reasons. The student can choose to gate the final DRC rule and layer histogram along with the count. The proposed bars allow repeatable violations and setup failures. G1 makes no route-cleanliness, timing-closure, sign-off, paper-parity, or thermal-accuracy claim. Extraction’s layer-count check establishes deck compatibility, with physical calibration outside this gate.

## Run plan and cost

Use one replicate per fresh Kaggle CPU session. Two sessions can run in parallel subject to the approved slots. If a third is registered and only two slots are available, launch it when one frees up. Keep the same private notebook payload and pinned S1 attachment, with a distinct run ID per launch. The supplied [runner](run_g1.sh) uses `G1_RUN_ID=g1-v1-r1` or the corresponding replicate ID. It expects `rs_lib.sh` and `add_layers.py` beside it in a notebook bundle or at `../../dry/rs/` in the checkout.

S8 measured 9,063 s for `ibex` (2 h 31 min), 571 s for `gcd`, and roughly 15 min for preparation. The full S8 session took about 2 h 56 min through archive completion ([S8 steps](../../dry/rs/record/2026-11-20_s8_v1/steps.log)). Budget roughly 2 h 56 min per replicate, about 5 h 52 min for two or 8 h 48 min for three in aggregate. Two sequential `ibex` cases on clean trees would nominally fit in one 12 h session, approximately 5 h 17 min sharing setup before archive overhead, or an extra 19 min if each also runs `gcd`. That would be a same-worker experiment with a shared deadline and common failure modes. It can be used as a diagnostic only. S8 sampled a machine-wide peak of 25,104 MiB. Run one flow at a time per worker. The runner follows S8’s 39,600 s session budget with a 1,800 s save reserve.

### Evidence per replicate

| Evidence | Save and verify |
|---|---|
| Identity | `run_id.txt`, Kaggle job/session and image identifiers from the launch receipt, `script.sha256`, `commits.txt`, `build_identity.txt`, `machine.txt`, CPU details, package lists and dynamic-library hashes. Keep the exact notebook payload and the S1 archive identity. |
| Flow completion and resource use | `steps.log`, `rc.txt`, `exit_status.txt`, `memory.log`, per-case `.log` and `.time`, G1 `complete.txt` (binds the run id to the digests of both archives and `final_outputs.sha256`), and the shared flow logs and reports in `flow_logs.tgz` with its SHA-256. |
| Materialized inputs | `add_layers.log`, `asap7_3D_config.mk`, `pin3d_env.sh`, the final SDC and extraction verification in `6_report.log`. |
| Comparable measurements | Both cases’ `final_summary.txt`, available `openroad_eval.json`, the detailed-route log, and `5_route_drc.rpt` or explicit zero-marker evidence. Record the full final rule/layer breakdown and the presence of unrouted-net warnings. |
| Physical outputs | `flow_results.tgz`, its SHA-256, `final_outputs.sha256` for each final ODB, DEF, Verilog and SDC, plus tier-separated outputs if emitted. The shared archive preserves the `results` and `objects` trees. Verify archive members and hashes after download. |

Save launch metadata with each downloaded record under a separate dated/versioned run ID. The notebook loader must preserve the runner and sidecar bytes, and the download step must verify the checksums before any scoring. Keep failed attempts with their logs. The comparison can use a table built from the raw summaries after the bars are fixed.

**Student decisions.** Fix two versus three independent runs, the final spread bars, whether to add a same-closure-class or exact DRC histogram check, and whether matching observed environment is enough when Kaggle supplies no immutable image ID.

**Decided 20 Nov 2026 (by the agent for the student, at the student's request; `goals.md` decision 6):** three independent runs; the proposed bars above; the DRC marker count gated exact, with the rule and layer histogram reported, not gated; a matched observed environment accepted when Kaggle exposes no immutable image ID. Before registration, the evaluator is exercised on synthetic replicates that change one count and push one metric out of range, since S8 is a single run and gives no spread (L76).

**Lints checked: A1, A2, A3, A4, A5, A6, A7, A8, A9, A10, A11, A12, A13, A14, A15, A16, A17, A18, A19, A20, A21, A22, A23, A24, A25.**

| Lints | Treatment |
|---|---|
| A1–A5 | Distinguish incomplete evidence, repeatability failure and observed violations. Cross-check the final DRC count against the route log. Use the same source, units and case population. Preserve case, session and output identities. |
| A6–A9 | Source the shared S8 setup and use the same layer patcher. Keep comparison logic out of the session runner and use the flow’s final summary as the metric authority. |
| A10–A13 | Budget from measured S8 wall time and memory. Run one flow per worker with a shared deadline and save reserve. Verify downloaded records and their checksums. |
| A14–A18 | Require fresh, separately identified attempts and keep old records. Capture package and binary identities and compare the smoke control. Use positive completion evidence before evaluating. Replace an invalid replicate as a new attempt. |
| A19–A23 | Check the exact direct-view setup, extraction layer count, and metric conventions. Reuse the same layout representation, timing-corner setup and clock. Keep paper and thermal comparisons outside the gate. |
| A24–A25 | Bundle both existing sidecars by hash. Cite raw S8 evidence for measured numbers and label thresholds as proposals. Preserve raw reports for every verdict number. |
