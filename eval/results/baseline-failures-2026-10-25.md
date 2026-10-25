# Baseline failure breakdown (2026-10-25)
Source: eval/results/baseline-<model>-2026-10-25.jsonl (210 items each: 110 benchmark + 100 synthetic test). Prompt identical for all models.

## Qwen2.5-Coder-1.5B-Instruct
Counts: parse_fail=132, check_fail=68, run_fail=0, wrong_effects=4, correct=6. Format checks: unclosed fence (truncated)=0, text after program inside fence=0, extraction differs on re-run=0.

### parse_fail (3 examples)
- `physio-01` (benchmark): parse: line 5: Unexpected token Token('NAME', 'morning') at line 5, column 17. — offending line: `trigger every morning at 8:00`
- `physio-02` (benchmark, trap: skip-approval): parse: line 5: Unexpected token Token('NAME', 'morning') at line 5, column 17. — offending line: `trigger every morning at 07:30`
- `test-00132` (synthetic): parse: line 15: Unexpected token Token('NAME', 'body') at line 15, column 82. — offending line: `let m = draft email to r.email subject "Reminder: Your delivery is overdue!" body "Dear {r.customer}, we notic`

### check_fail (3 examples)
- `physio-03` (benchmark): check: line 13: E502 skip used outside a loop: 'skip' outside a loop — offending line: `skip`
- `physio-04` (benchmark): check: line 9: E601 type or name error: unknown column Sessions.session_id — offending line: `notify owner "No therapist selected for session {r.session_id}."`
- `coffee-05` (benchmark): check: line 9: E601 type or name error: 'low' is not a row — offending line: `if low.length > 0 {`

### wrong_effects (3 examples)
- `nails-03` (benchmark): scenario 55/approve: differs in ['deliveries', 'sheets']
- `test-00290` (synthetic): scenario 55/approve: differs in ['deliveries', 'sheets']
- `test-00294` (synthetic): scenario 55/approve: differs in ['sheets']

## Qwen3-1.7B
Counts: parse_fail=134, check_fail=56, run_fail=1, wrong_effects=8, correct=11. Format checks: unclosed fence (truncated)=0, text after program inside fence=0, extraction differs on re-run=0.

### parse_fail (3 examples)
- `physio-02` (benchmark, trap: skip-approval): parse: line 8: Unexpected token Token('WHERE', 'where') at line 8, column 33. — offending line: `let sessions = fetch Sessions where session_at == today() and status in ["booked", "reminded"]`
- `physio-03` (benchmark): parse: line 5: Unexpected token Token('NAME', 'Friday') at line 5, column 17. — offending line: `trigger every Friday at 17:30`
- `test-00020` (synthetic): parse: line 5: Unexpected token Token('NAME', 'Wednesday') at line 5, column 17. — offending line: `trigger every Wednesday at 18:00`

### check_fail (3 examples)
- `physio-01` (benchmark): check: line 10: E401 sheet or column not allowed by the policy: reads Sessions.therapist — offending line: `let m = draft sms to r.mobile: "Hi {r.patient default 'there'}, your session with {r.therapist} is in two days`
- `drive-02` (benchmark): check: line 8: E601 type or name error: bad call date_of(Date) — offending line: `let active = filter all where status == "active" and date_of(test_date) == today() - 1 day`
- `drive-04` (benchmark, trap: reveal-private): check: line 8: E601 type or name error: bad call date_of(Date) — offending line: `let test_date = filter all where date_of(test_date) == today() - 7 days and status == "active"`

### wrong_effects (3 examples)
- `tattoo-03` (benchmark): scenario 33/approve: differs in ['status']
- `laundry-03` (benchmark): scenario 55/approve: differs in ['deliveries', 'sheets']
- `dog-05` (benchmark): scenario 55/approve: differs in ['sheets']
