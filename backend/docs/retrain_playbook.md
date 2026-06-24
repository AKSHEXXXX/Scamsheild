# Retrain Playbook

> Decided before labels arrive so nobody renegotiates the bar mid-sprint.

## 1. Agent 1 — Text Scam Classifier (TF-IDF + LogReg)

### Data source
```
export_training_data.py --only-labeled --channel=text
```

### Label assignment
| Label | Condition |
|-------|-----------|
| `1` (scam) | `feedback.label = "scam"` AND text matches patterns: `work from home`, `earn`, `returns`, `investment`, `crypto`, `signal group` |
| `0` (legit) | `feedback.label = "legit"` AND text is meeting reminders, family chats, logistics (no money promises) |

### Model
- Start with upgraded **TF-IDF + Logistic Regression** (same architecture, fresh fit).
- Only consider a tiny transformer (DistilBERT) if labeled samples > 10 000.

---

## 2. Agent 3 — URL Phishing Classifier (XGBoost)

### Data source
`url_training.csv` joined with feedback where `feedback.label in {"scam","legit"}` and at least one URL present.

### Label assignment
| Label | Condition |
|-------|-----------|
| `1` (phishing) | `feedback.label = "scam"` OR domain in OSINT feeds (OpenPhish, PhishTank, etc.) |
| `0` (legit) | `feedback.label = "legit"` AND domain in whitelist (banks, news, e-commerce) |

### Features
TLD, brand tokens, suspicious TLD flag, subdomain count, URL length, path length, special char count, IP presence.

---

## 3. Rollback gating

A retrained model **only ships** if ALL of these hold on the candidate deploy:

### 3.1 Adversarial suite (v1 + v2)
- No increase in FN count for any channel.
- No increase in FP count for any channel.

### 3.2 Dashboard (last N hours on staging)
- `high_risk_ratio` per channel stays within ±5 pp of previous deploy, **OR**
- Moves in the expected direction (e.g., job-scam FN rate drops).

### 3.3 Feedback-based FN/FP (text + URL)
- FN candidates per 1k labeled scans **do not increase**.
- FP candidates per 1k labeled scans **do not increase**.

### Rollback procedure
1. Revert the model artifact file (`.pkl`, `.json`) to the previous version.
2. Redeploy via `railway up` — code stays, only the model rolls back.
3. Confirm rollback passes the same gating checks within one dashboard window.

---

## 4. Second adversarial suite (v2)

Tracked in a separate test file once each bucket has ≥20 labeled examples.

### Proposed buckets (15–20 examples each)
| Bucket | Example patterns |
|--------|-----------------|
| Banking KYC + link | IN banks, PayPal, fake login URLs |
| Delivery scams | FedEx/DHL/customs pay links |
| Job scams | "work from home", "data entry", "earn per day" |
| Investment/crypto | guaranteed returns, signal groups |
| UPI scams | "double your money", refund scams |
| Romance / emotional blackmail | deferred until data flows |
| Benign transactional | bills, OTP without link, legitimate bank SMS |
| Benign chats | family, meetings, casual |
| Benign URLs | news, big brands |
| Unicode/leet obfuscations | 1–5 variants of known scam templates |

### Freeze rule
Once 20+ labeled examples exist in any bucket (via feedback), freeze 15 into suite v2 and track them forever.

---

## 5. Infra freeze

No new infrastructure work unless it directly improves:
- Eval (test suite pass rate)
- Labeling (feedback quantity or quality)
- Retraining (model iteration speed)
