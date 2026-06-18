import re, json, yaml
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional

def _safe_str(value: Any) -> str:
    return '' if value is None else str(value).strip()

def _safe_lower(value: Any) -> str:
    return _safe_str(value).lower()

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default

def normalize_vpa(vpa: Any) -> str:
    return _safe_lower(vpa)

def extract_vpa_domain(vpa: Any) -> str:
    vpa = normalize_vpa(vpa)
    return vpa.split('@')[-1].strip() if '@' in vpa else ''

def parse_timestamp_hour(timestamp: Any) -> Optional[int]:
    if timestamp is None:
        return None
    ts = _safe_str(timestamp)
    try:
        return int(datetime.fromisoformat(ts.replace('Z', '+00:00')).hour)
    except Exception:
        pass
    m = re.search(r'(?:T|\s)([0-2][0-9]):[0-5][0-9]', ts)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return h
    return None

class UPIHeuristicEngine:
    def __init__(self, rules_config):
        if isinstance(rules_config, (str, Path)):
            with open(rules_config, 'r') as f:
                self.config = yaml.safe_load(f)
        elif isinstance(rules_config, dict):
            self.config = rules_config
        else:
            raise TypeError('rules_config must be dict or YAML path')
        self.version = self.config.get('version', 'upi_rules_unknown')
        self.rules = self.config.get('rules', [])
        self.whitelists = self.config.get('whitelists', {})
        self.scoring = self.config.get('scoring', {})
        self.score_cap = int(self.scoring.get('score_cap', 100))
        self.multi_rule_boost = int(self.scoring.get('multi_rule_boost', 10))
        self.severity_thresholds = self.scoring.get('severity_thresholds', {'HIGH':80, 'MEDIUM':60, 'LOW':40, 'SAFE':0})
        self.vpa_domain_whitelist = set(_safe_lower(x) for x in self.whitelists.get('vpa_domains', []))

    def score_to_severity(self, score:int) -> str:
        if score >= int(self.severity_thresholds.get('HIGH', 80)):
            return 'HIGH'
        if score >= int(self.severity_thresholds.get('MEDIUM', 60)):
            return 'MEDIUM'
        if score >= int(self.severity_thresholds.get('LOW', 40)):
            return 'LOW'
        return 'SAFE'

    def _rule_hit(self, rule:Dict[str,Any], txn:Dict[str,Any]) -> bool:
        pt = rule.get('pattern_type')
        field = rule.get('field')
        if pt == 'regex':
            return re.search(rule.get('pattern', ''), _safe_lower(txn.get(field, '')), flags=re.I) is not None
        if pt == 'numeric':
            value = _safe_float(txn.get(field))
            cond = rule.get('condition')
            if cond == 'in':
                return value in set(float(x) for x in rule.get('values', []))
            if cond == 'gte':
                return value >= float(rule.get('threshold', 0))
            if cond == 'lte':
                return value <= float(rule.get('threshold', 0))
            return False
        if pt == 'boolean':
            return bool(txn.get(field, False)) == bool(rule.get('expected', True))
        if pt == 'vpa_domain_not_in_whitelist':
            vpa = normalize_vpa(txn.get(field, ''))
            domain = extract_vpa_domain(vpa)
            return bool(vpa and domain and domain not in self.vpa_domain_whitelist)
        if pt == 'upi_collect_suspicious':
            channel = _safe_lower(txn.get('channel', ''))
            note = _safe_lower(txn.get('note', ''))
            is_collect = 'collect' in channel or 'collect' in note or 'approve' in note
            terms = ['receive money', 'money coming', 'approve', 'refund', 'reward', 'cashback', 'claim', 'verify', 'kyc', 'otp']
            return is_collect and any(t in note for t in terms)
        if pt == 'impersonation_keyword_vpa':
            vpa = normalize_vpa(txn.get(field, ''))
            domain = extract_vpa_domain(vpa)
            keys = [_safe_lower(x) for x in rule.get('keywords', [])]
            return bool(vpa and any(k in vpa for k in keys) and domain not in self.vpa_domain_whitelist)
        if pt == 'new_recipient_high_amount':
            return bool(txn.get('is_new_recipient', False)) and _safe_float(txn.get('amount')) >= float(rule.get('threshold', 10000))
        if pt == 'odd_hours':
            hour = parse_timestamp_hour(txn.get(field))
            if hour is None:
                return False
            start = int(rule.get('start_hour', 0)); end = int(rule.get('end_hour', 5))
            return start <= hour < end if start <= end else hour >= start or hour < end
        if pt == 'round_number_high_amount':
            amount = _safe_float(txn.get(field))
            threshold = float(rule.get('threshold', 10000))
            multiple = float(rule.get('multiple', 10000))
            return amount >= threshold and amount % multiple == 0
        return False

    def scan(self, txn: Dict[str,Any]) -> Dict[str,Any]:
        txn = txn or {}
        triggered = []
        for rule in self.rules:
            try:
                hit = self._rule_hit(rule, txn)
            except Exception:
                hit = False
            if hit:
                triggered.append({
                    'rule': rule.get('name'),
                    'severity': rule.get('severity'),
                    'weight': int(rule.get('weight', 0)),
                    'explanation': rule.get('explanation', rule.get('description', '')),
                })
        if not triggered:
            score = 0
        else:
            base = max(r['weight'] for r in triggered)
            score = min(self.score_cap, base + self.multi_rule_boost * max(0, len(triggered) - 1))
        severity = self.score_to_severity(score)
        explanation = '; '.join([r.get('explanation', '') for r in triggered if r.get('explanation')]) or 'No high-risk UPI heuristic rule triggered.'
        return {'score': int(score), 'severity': severity, 'triggered_rules': triggered, 'explanation': explanation, 'engine_version': self.version}

def load_engine(config_path='upi_heuristic_rules.yaml'):
    return UPIHeuristicEngine(config_path)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='upi_heuristic_rules.yaml')
    parser.add_argument('--txn_json', required=True)
    args = parser.parse_args()
    engine = UPIHeuristicEngine(args.config)
    print(json.dumps(engine.scan(json.loads(args.txn_json)), indent=2))
