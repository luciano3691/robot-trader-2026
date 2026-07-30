# -*- coding: utf-8 -*-
"""Utility condivise per i value screener — scoring percentile."""
import os, json, math

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Direzione fissa per metrica (indipendente dal piano — è una proprietà della metrica stessa)
_DIRECTIONS = {
    'Dividend Yield':   True,   # alto = meglio
    'P/B':              False,  # basso = meglio
    'ROE':              True,
    'Var_1D_%':         True,
    'EV/FCF':           False,
    'Net Debt/EBITDA':  False,
    'Perf 3M %':        True,
    'Performance 1Y':   True,
    'TER':              False,
    'Sharpe Ratio':     True,
}

_DEFAULT_WEIGHTS = {
    'azioni': {
        'BASIC': {'Dividend Yield': 35, 'P/B': 10, 'ROE': 20, 'Var_1D_%': 25, 'EV/FCF': 10, 'Net Debt/EBITDA': 0},
        'PRO':   {'EV/FCF': 35, 'ROE': 25, 'P/B': 20, 'Net Debt/EBITDA': 15, 'Dividend Yield': 0, 'Var_1D_%': 5},
        'VALUE': {'EV/FCF': 40, 'ROE': 25, 'Net Debt/EBITDA': 20, 'P/B': 15, 'Dividend Yield': 0, 'Var_1D_%': 0},
    },
    'etf': {
        'BASIC': {'Perf 3M %': 45, 'Performance 1Y': 20, 'TER': 20, 'Sharpe Ratio': 15},
        'PRO':   {'Sharpe Ratio': 40, 'Performance 1Y': 30, 'TER': 20, 'Perf 3M %': 10},
        'VALUE': {'Sharpe Ratio': 45, 'Performance 1Y': 25, 'TER': 25, 'Perf 3M %': 5},
    },
    'fondi': {
        'BASIC': {'Perf 3M %': 30, 'Performance 1Y': 30, 'TER': 25, 'Sharpe Ratio': 15},
        'PRO':   {'Sharpe Ratio': 40, 'Performance 1Y': 25, 'TER': 30, 'Perf 3M %': 5},
        'VALUE': {'Sharpe Ratio': 45, 'TER': 35, 'Performance 1Y': 15, 'Perf 3M %': 5},
    },
}


def get_default_weights():
    return {
        asset: {plan: dict(w) for plan, w in plans.items()}
        for asset, plans in _DEFAULT_WEIGHTS.items()
    }


def load_scoring_weights(asset_type, plan_name):
    """Carica pesi da config.json; fallback ai default hardcoded."""
    plan_key = plan_name
    try:
        cfg_path = os.path.join(BASE_DIR, 'config.json')
        with open(cfg_path, encoding='utf-8') as f:
            cfg = json.load(f)
        w = cfg.get('scoring_weights', {}).get(asset_type, {}).get(plan_key)
        if isinstance(w, dict) and w:
            return w
    except Exception:
        pass
    return dict(_DEFAULT_WEIGHTS.get(asset_type, {}).get(plan_key, {}))


def batch_percentile_score(items, asset_type, plan_name):
    """Calcola score percentile 0–100 per tutti gli item (modifica in-place).
    Score alto = migliore nella lista selezionata per quel piano.
    Le metriche con peso 0 vengono ignorate.
    """
    if not items:
        return
    weights = load_scoring_weights(asset_type, plan_name)
    active = [(k, float(v)) for k, v in weights.items() if float(v or 0) > 0]
    if not active:
        for item in items:
            item['Score'] = 0.0
        return

    total_w = sum(w for _, w in active)

    # Raccogli tutti i valori per ogni metrica attiva
    metric_vals = {}
    for key, _ in active:
        vals = []
        for item in items:
            v = item.get(key)
            try:
                vals.append(float(v) if v is not None else None)
            except (TypeError, ValueError):
                vals.append(None)
        metric_vals[key] = vals

    for i, item in enumerate(items):
        score = 0.0
        for key, weight in active:
            v = metric_vals[key][i]
            valid = [x for x in metric_vals[key] if x is not None and not math.isnan(x)]
            if not valid or v is None:
                pct = 0.0
            else:
                hib = _DIRECTIONS.get(key, True)
                if hib:
                    pct = sum(1 for x in valid if x <= v) / len(valid) * 100
                else:
                    pct = sum(1 for x in valid if x >= v) / len(valid) * 100
            score += pct * weight
        item['Score'] = round(score / total_w, 1)
