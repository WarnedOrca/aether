# Aether: related work


Goal: find out what already exists and what Aether does differently. Do not assume novelty.

Date surveyed: 2026-10-24. Every link below was opened and read on that date. Facts come from the pages' own text (mostly abstracts for papers), so I did **not** read full papers; check a paper's body before relying on any detail not stated here.

## Bottom line (read this first)
**The broad idea is not new.** In 2026 several papers already cover "a rule language that keeps LLM agents safe" (AgentSpec, Agenra, Agentproof, AgentLTL). "Human approval before sending" is a standard feature in Zapier and LangGraph. "Fine-tune a small model to write a DSL" has Microsoft and academic precedents.
**A narrower version may still be new**, but I could not confirm this (absence from a limited search is not proof). See "How to sharpen it" at the bottom.

## Framing (decided 2026-10-24)
Aether is **an open benchmark, a small model, and a checker**, not a new safety paradigm.
- **Benchmark:** English SOPs paired with Aether programs, policies, and must-reject safety traps; it scores parse rate, checker pass, execution, intended behavior, and safe-and-correct together.
- **Small model:** an open-weight model fine-tuned on $0 compute to translate SOPs into Aether.
- **Checker:** verifies the named core rules C1-C8 (see `spec/SPEC.md` section 5) for this language only. Claim only what it verifies; never "safe" in general.
- **Possible study:** per-message vs batch approval, as a configurable mode compared on identical tasks.

## Novelty doubts (keep honest; revisit before writing anything public)
1. **Rule languages for agents already exist.** AgentSpec (runtime rules), Agenra (quotas, approvals, Lean proofs), Agentproof (static checks, including human-approval gates), and AgentLTL (rule-scored fine-tuning) together cover most of the safety side.
2. **Approval steps already exist.** Zapier Human in the Loop and LangGraph `interrupt()`. Aether's only difference is that the checker *requires* them; that is a guarantee, not a new capability.
3. **Small-model NL-to-DSL already exists.** The Microsoft case study, validated synthetic data for formulas, and the 39-model DSL evaluation.
4. **The four-part combination may be new, but this is unconfirmed.** The search was short and read mostly abstracts.
5. **Batch approval and approval fatigue were not surveyed.** Human-factors and usable-security work on approval fatigue and bulk consent probably exists. Read it before claiming anything about the per-message vs batch comparison.
6. **Property-based testing of policy engines was not surveyed.** Cedar's verification-guided development (differential testing against formal models) is a known precedent; open it before citing.

## Survey checklist
- [x] BPMN / workflow engines (Camunda, Temporal)
- [x] No-code automation (Zapier, n8n, Make)
- [x] Policy languages (OPA/Rego, Cedar)
- [x] Agent frameworks (LangGraph, tool-calling agents)
- [x] LLM guardrail and verification work
- [x] Natural-language-to-DSL and execution-verified training papers
- Not covered: Camunda and Make pages (not opened), Guardrails AI (not opened), full-text reading of any paper, approval-fatigue / bulk-consent research, property-based testing of policy engines.

## Notes

### 1. Workflow engines and notations
- **Temporal**: [architecture docs](https://docs.temporal.io/encyclopedia/architecture/temporal-architecture.md). Runs workflows durably: it stores an event history so a crashed workflow can be replayed and resumed. The page describes no built-in safety policies or approval step (Signals can send messages to a running workflow, which a developer could use to build approval).
  *Aether differs:* Temporal is a reliable runtime for code written by developers. It does not check what the program is allowed to do.
- **BPMN 2.0**: [OMG overview](https://www.omg.org/spec/BPMN/2.0/About-BPMN). A standard flowchart notation for business processes, readable by business people and precise enough to translate into software components. I did **not** confirm from this page whether it defines execution semantics.
  *Aether differs:* BPMN is a diagram standard; Aether is a text language with built-in safety checks and an owner-facing rendering. BPMN is the closest "business-readable process" precedent, so I should compare against it honestly. (Camunda page not opened.)

### 2. No-code automation
- **Zapier Human in the Loop**: [app page](https://zapier.com/apps/human-in-the-loop/integrations/email). A Zap step that asks a reviewer to approve, reject, or edit content before the Zap continues, with timeout, reminder, and channel options.
- **n8n**: [docs](https://docs.n8n.io/). Open "fair-code" workflow tool with AI agent features and an MCP server. The docs front page does not mention human approvals (I did not search deeper).
  *Aether differs:* in Zapier the owner must remember to add the approval step. Nothing checks that every customer-facing action is covered. In Aether the checker rejects the program if approval is missing. This is the clearest practical difference, but Zapier users get approvals today, so it is not a new capability, only a new guarantee.

### 3. Policy languages
- **OPA / Rego**: [docs](https://www.openpolicyagent.org/docs). General policy engine, separates deciding from enforcing. The caller supplies input and must enforce the answer.
- **Cedar**: [docs](https://docs.cedarpolicy.com/). Authorization language: who (principal) may do what (action) to which resource under which conditions, validated against a schema. Not general-purpose.
  *Aether differs:* both answer "is this single request allowed?" Neither runs a multi-step procedure or reads English. Aether's rules (refund limits, approval-before-send) are about a whole procedure, not one request. Cedar's design goal of being analyzable and readable by non-experts is the same spirit; I can cite it as inspiration for keeping the rule language small.

### 4. Agent frameworks
- **LangGraph interrupts**: [docs](https://docs.langchain.com/oss/python/langgraph/interrupts). `interrupt()` pauses a graph and saves state until a human resumes it. The developer still has to place interrupts correctly, handle re-execution, and make side effects safe.
  *Aether differs:* LangGraph gives the mechanism; correctness of where it is used is left to the developer. Aether verifies placement statically.

### 5. Safety / guardrail / verification work for LLM agents (closest competitors)
- **AgentSpec**: [arXiv 2503.18666](https://arxiv.org/abs/2503.18666) (Wang, Poskitt, Sun). A lightweight DSL for runtime constraints on LLM agents; rules have triggers, predicates, and enforcement actions. Reports (in its abstract) over 90% unsafe-execution prevention on code agents, with millisecond overhead.
  **Closest to Aether's safety-rule idea.** Difference: it constrains an existing agent at runtime; it is not a procedure language and not compiled from English SOPs.
- **Agenra**: [arXiv 2608.22868](https://arxiv.org/abs/2608.22868) (Shivakumar, Priya, Gao). Language and verified core for stateful agent authorization: tracks quotas, earlier calls, approvals; Lean-checked proofs. (Note: a search result labelled this "AgentFlow"; the opened page is titled Agenra.)
  **Very close to "spending/refund limits + approvals".** Difference: authorization layer for agents, not a business-procedure language, no English input.
- **Agentproof**: [arXiv 2603.20356](https://arxiv.org/abs/2603.20356). Statically checks agent workflow graphs (LangGraph, CrewAI, AutoGen, Google ADK) with a temporal-policy DSL. The authors' own 18 hand-made workflows showed 55% human-gate violations (authors say this is not a real-world rate).
  **Closest to the "static checker" idea, including checking human-approval gates.** Difference: it analyses graphs extracted from other frameworks; Aether would be a language where the program is checkable by construction.
- **Solver-aided policy compliance**: [arXiv 2603.20449](https://arxiv.org/abs/2603.20449) (Winston, Winston, Just). LLM-assisted, human-guided translation of policies to SMT constraints; Z3 checks each tool call before it runs; fewer violations on TauBench.
- **AgentLTL**: [arXiv 2607.02599](https://arxiv.org/abs/2607.02599) (Elkoussy, Perez). Temporal-logic rules over agent traces; the score is used as a fine-tuning reward and reportedly improved accuracy and compliance on the authors' benchmark. **Already combines rule-checking with training**, which overlaps with my plan to train on checker-verified data.
- **NeMo Guardrails**: [arXiv 2310.10501](https://arxiv.org/abs/2310.10501) (Rebedea et al., EMNLP 2023 demo). Programmable runtime rails for LLM apps, focused on conversational systems.
- **Survey**: [arXiv 2608.14590](https://arxiv.org/abs/2608.14590) (Dantas et al.). 38 studies, 2022-2026. Says specification (turning requirements into formal rules) is the main bottleneck; blocking unsafe actions can leave very few tasks completed both safely and correctly; evidence is weak (7 of 9 claims rated "Very Low" certainty).
  **Useful for Aether:** it names exactly the two problems Aether could target (English to checkable spec; safety without wrecking usefulness).

### 6. NL-to-DSL and verified training data
- **Microsoft SLM case study**: [arXiv 2604.09952](https://arxiv.org/abs/2604.09952). Fine-tuned small models beat larger ones on latency and test-set performance for natural-language-to-DSL in production. The abstract gives no numbers and does not name the DSL.
- **Validated synthetic data**: [arXiv 2407.10657](https://arxiv.org/abs/2407.10657) (Singh et al.). For spreadsheet formulas, validating synthetic examples before fine-tuning beat using raw synthetic data across four models.
- **Open LLMs to DSL**: [arXiv 2605.15865](https://arxiv.org/abs/2605.15865) (Baber et al.). 39 open models (0.5B-32B), few-shot only; some compact models approach much larger ones on UI/data-model DSLs.
  *Aether differs:* these show the technique works; none is about business procedures or safety checking.
  Search also surfaced execution-based text-to-SQL work (SLM-SQL, arXiv 2507.22478). I did not open it, so I am not citing details.

## Conclusion
**Not new:** safety-rule DSLs for agents (AgentSpec, Agenra), static checking of human-approval gates (Agentproof), pre-execution policy checks (solver-aided work), rule-scored training (AgentLTL), human-approval steps (Zapier, LangGraph), small-model NL-to-DSL fine-tuning (Microsoft, formula, UI-DSL papers).
**Possibly new, unconfirmed:** the *combination* aimed at non-programmers: (a) a small closed procedure language where safety checks are decidable by construction, (b) a plain-English rendering the owner approves, (c) an open benchmark of English SOPs paired with programs **and safety traps**, (d) a small model trained only on examples that parse, pass the checker, and run in a sandbox. I found no single paper doing all four. My search was short and mostly read abstracts, so I cannot claim this.

## How to sharpen it
1. **Drop "new safety paradigm".** Frame as "an open, small, reproducible NL-to-checked-procedure system and benchmark".
2. **Make the benchmark the contribution.** Include SOPs that ask for unsafe things (send without approval, refund over limit). Score: parses, passes checker, runs, matches intended behaviour, and *safe-and-correct together* (the survey says this joint measure is missing).
3. **Test the owner rendering with real people** (parent-approved, no customer data): can a non-programmer spot a bad program from the English rendering? Measurable and genuinely different from the formal-methods papers.
4. **Compare against baselines honestly:** a prompted small model, and (if time) generating a Zapier-like JSON workflow instead of Aether.
5. **Keep the language tiny** (no loops, no arbitrary code), so the checker can be sound for that fragment. State the guarantee precisely and its limits.
6. Before any claim of novelty, do a deeper search (Google Scholar, arXiv listings) and read the full text of Agentproof, AgentSpec, and AgentLTL.
