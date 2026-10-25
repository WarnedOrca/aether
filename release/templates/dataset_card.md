---
license: cc-by-4.0
language: [en]
task_categories: [text-generation]
tags: [code, dsl, business-process, safety]
pretty_name: Aether synthetic SOP-to-program dataset
---

# Aether synthetic SOP-to-program dataset

Pairs of plain-English business procedures (SOPs) and programs in Aether, a small language for checkable business procedures. Each row also carries the owner's policy (safety rules) and the sheet declarations the program may use.

**How it was made:** a rule-based generator (no language model) builds the SOP, the policy, and the program from the same random choices, so they agree by construction. A row was kept only if its program parses, passes the Aether checker with zero errors, and runs on 3 random mock workspaces with no run error and no monitor violation.

| Split | Rows |
|---|---|
| train | {train} |
| valid | {valid} |
| test | {test} (held-out business types: {test_domains}) |

{kept} rows in total, from {patterns} procedure patterns.

**Fields:** `id`, `domain`, `pattern`, `batch` (approval mode), `sop`, `policy`, `sheets`, `program`.

**Trap-style samples** (`traps_train.jsonl`, `traps_valid.jsonl`; used to train model v0.2): the SOP asks for something the policy forbids or Aether cannot do, and the program does the permitted alternative. These samples were checked for overlap with every benchmark and held-out SOP; see `traps_overlap_report.json`. They have an extra field, `trap`. Training on them did not improve held-out trap performance (see the model card).

**Limitations:** the English is templated, so it is far less varied than real owners' writing. All businesses are invented, and all data in the programs is mock data.
