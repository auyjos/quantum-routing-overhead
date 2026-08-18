import json
import os

import numpy as np
import pandas as pd

OUTDIR = '/home/claude/work/artifacts/seedstrat'
os.makedirs(OUTDIR, exist_ok=True)

# ---------- Load ----------
df1 = pd.read_csv('/home/claude/qro/raw.csv')
df2 = pd.read_csv('/home/claude/work/artifacts/runs/control-label-permutation/raw_results.csv')

GROUP_COLS = ['circuit_family', 'logical_qubits', 'topology', 'optimization_level']

def iqr(x):
    q75, q25 = np.percentile(x, 75), np.percentile(x, 25)
    return q75 - q25

def per_config_stats(df, value_col='two_qubit_depth_penalty'):
    rows = []
    for keys, g in df.groupby(GROUP_COLS):
        vals = g[value_col].values.astype(float)
        n = len(vals)
        vmax, vmin, vmed = vals.max(), vals.min(), np.median(vals)
        spread = vmax - vmin
        rel_spread = vmax / vmin if vmin != 0 else np.nan
        iqr_v = iqr(vals)
        norm_spread = spread / vmed if vmed != 0 else np.nan
        rows.append({
            'circuit_family': keys[0],
            'logical_qubits': keys[1],
            'topology': keys[2],
            'optimization_level': keys[3],
            'n_seeds': n,
            'min': vmin,
            'max': vmax,
            'median': vmed,
            'spread': spread,
            'relative_spread': rel_spread,
            'iqr': iqr_v,
            'normalized_spread': norm_spread,
            'zero_spread': bool(spread == 0),
        })
    return pd.DataFrame(rows)

# ================= A & B: per-config stats for constrained topologies (input1) =================
constrained = df1[df1['topology'] != 'complete_27'].copy()
per_config = per_config_stats(constrained, 'two_qubit_depth_penalty')
assert len(per_config) == 144, f"expected 144 configs, got {len(per_config)}"

per_config['stratum'] = per_config['optimization_level'].map({0: 'L0', 1: 'L1', 3: 'L3'})
per_config = per_config.sort_values(['optimization_level', 'topology', 'circuit_family', 'logical_qubits']).reset_index(drop=True)
per_config.to_csv(os.path.join(OUTDIR, 'per_config.csv'), index=False)

def strat_summary(sub):
    n = len(sub)
    frac_zero = float((sub['spread'] == 0).mean())
    frac_zero_rel = float((sub['relative_spread'] == 1.0).mean())
    out = {
        'n_configs': n,
        'spread': {
            'frac_zero': frac_zero,
            'median': float(sub['spread'].median()),
            'q75': float(sub['spread'].quantile(0.75)),
            'max': float(sub['spread'].max()),
            'mean': float(sub['spread'].mean()),
        },
        'relative_spread': {
            'frac_zero_(==1.0)': frac_zero_rel,
            'median': float(sub['relative_spread'].median()),
            'q75': float(sub['relative_spread'].quantile(0.75)),
            'max': float(sub['relative_spread'].max()),
            'mean': float(sub['relative_spread'].mean()),
        },
        'iqr': {
            'median': float(sub['iqr'].median()),
            'q75': float(sub['iqr'].quantile(0.75)),
            'max': float(sub['iqr'].max()),
        },
        'normalized_spread_(spread/median_penalty)': {
            'frac_zero': frac_zero,
            'median': float(sub['normalized_spread'].median()),
            'q75': float(sub['normalized_spread'].quantile(0.75)),
            'max': float(sub['normalized_spread'].max()),
            'mean': float(sub['normalized_spread'].mean()),
        },
        'median_penalty': {
            'median': float(sub['median'].median()),
            'mean': float(sub['median'].mean()),
            'max': float(sub['median'].max()),
        },
    }
    return out

B_by_level_pooled = {}
B_by_level_by_topology = {}
for lvl, lbl in [(0, 'L0'), (1, 'L1'), (3, 'L3')]:
    sub = per_config[per_config['optimization_level'] == lvl]
    B_by_level_pooled[lbl] = strat_summary(sub)
    B_by_level_by_topology[lbl] = {}
    for topo in sub['topology'].unique():
        subt = sub[sub['topology'] == topo]
        B_by_level_by_topology[lbl][topo] = strat_summary(subt)

# ================= C: Question 1 - is seed spread larger at L1/L3 than L0? =================
def describe(sub, col):
    return {
        'n': len(sub),
        'median': float(sub[col].median()) if len(sub) else None,
        'mean': float(sub[col].mean()) if len(sub) else None,
        'q75': float(sub[col].quantile(0.75)) if len(sub) else None,
        'max': float(sub[col].max()) if len(sub) else None,
    }

L0 = per_config[per_config['optimization_level'] == 0]
L1 = per_config[per_config['optimization_level'] == 1]
L3 = per_config[per_config['optimization_level'] == 3]
L13 = per_config[per_config['optimization_level'].isin([1, 3])]

from scipy import stats as sstats


def mannwhitney(a, b):
    try:
        stat, p = sstats.mannwhitneyu(a, b, alternative='two-sided')
        return {'statistic': float(stat), 'p_value': float(p)}
    except ValueError as error:
        return {"error": str(error)}

C = {
    'raw_spread': {
        'L0': describe(L0, 'spread'),
        'L1': describe(L1, 'spread'),
        'L3': describe(L3, 'spread'),
        'L1_L3_pooled': describe(L13, 'spread'),
        'mannwhitney_L0_vs_L1L3': mannwhitney(L0['spread'], L13['spread']),
    },
    'normalized_spread_(spread_over_median_penalty)': {
        'L0': describe(L0, 'normalized_spread'),
        'L1': describe(L1, 'normalized_spread'),
        'L3': describe(L3, 'normalized_spread'),
        'L1_L3_pooled': describe(L13, 'normalized_spread'),
        'mannwhitney_L0_vs_L1L3': mannwhitney(L0['normalized_spread'].dropna(), L13['normalized_spread'].dropna()),
    },
    'relative_spread_(max_over_min)': {
        'L0': describe(L0, 'relative_spread'),
        'L1': describe(L1, 'relative_spread'),
        'L3': describe(L3, 'relative_spread'),
        'L1_L3_pooled': describe(L13, 'relative_spread'),
        'mannwhitney_L0_vs_L1L3': mannwhitney(L0['relative_spread'].dropna(), L13['relative_spread'].dropna()),
    },
    'median_penalty_by_level': {
        'L0': describe(L0, 'median'),
        'L1': describe(L1, 'median'),
        'L3': describe(L3, 'median'),
    },
    'interpretation_note': (
        'Compares raw spread (max-min of two_qubit_depth_penalty) between L0 and L1/L3, '
        'plus normalized_spread = spread / median_penalty and relative_spread = max/min, which '
        'divide out the fact that L0 penalties are numerically larger. If raw spread is larger at L0 '
        'but normalized/relative spread is NOT larger at L0 (or is larger at L1/L3), that confirms the '
        'prior "worst cases at L0" observation is an artifact of L0 having bigger penalty magnitudes, '
        'not more seed-to-seed randomness.'
    ),
}

# ================= D: Question 2 - within L1/L3, is spread zero exactly where median==1.0? =================
D = {}
for lvl, lbl in [(1, 'L1'), (3, 'L3')]:
    sub = per_config[per_config['optimization_level'] == lvl].copy()
    sub['median_eq_1'] = sub['median'] == 1.0
    ct = pd.crosstab(sub['median_eq_1'], sub['zero_spread'])
    # ensure both True/False present
    for b in [True, False]:
        if b not in ct.index:
            ct.loc[b] = 0
        if b not in ct.columns:
            ct[b] = 0
    ct = ct.sort_index().sort_index(axis=1)
    contingency = {
        'median_eq_1_AND_zero_spread': int(ct.loc[True, True]) if True in ct.index and True in ct.columns else 0,
        'median_eq_1_AND_nonzero_spread': int(ct.loc[True, False]) if True in ct.index and False in ct.columns else 0,
        'median_ne_1_AND_zero_spread': int(ct.loc[False, True]) if False in ct.index and True in ct.columns else 0,
        'median_ne_1_AND_nonzero_spread': int(ct.loc[False, False]) if False in ct.index and False in ct.columns else 0,
    }
    exceptions_median1_nonzero = sub[(sub['median_eq_1']) & (~sub['zero_spread'])][
        ['circuit_family', 'logical_qubits', 'topology', 'optimization_level', 'min', 'max', 'median', 'spread', 'relative_spread']
    ].to_dict(orient='records')
    exceptions_zero_median_ne1 = sub[(~sub['median_eq_1']) & (sub['zero_spread'])][
        ['circuit_family', 'logical_qubits', 'topology', 'optimization_level', 'min', 'max', 'median', 'spread', 'relative_spread']
    ].to_dict(orient='records')
    D[lbl] = {
        'n_configs': len(sub),
        'contingency': contingency,
        'exact_correspondence': bool(len(exceptions_median1_nonzero) == 0 and len(exceptions_zero_median_ne1) == 0),
        'exceptions_median1_but_nonzero_spread': exceptions_median1_nonzero,
        'exceptions_zero_spread_but_median_ne_1': exceptions_zero_median_ne1,
    }

# ================= E: input 2 only - relabelling effect on variability =================
TOPO_PAIRS = [
    ('line_27', 'line_27_relabelled'),
    ('cairo_heavy_hex_27', 'cairo_heavy_hex_27_relabelled'),
]

df2_per_config = per_config_stats(df2[df2['topology'] != 'complete_27'], 'two_qubit_depth_penalty')

E = {}
for lvl, lbl in [(1, 'L1'), (3, 'L3')]:
    E[lbl] = {}
    for base, relab in TOPO_PAIRS:
        sub_base = df2_per_config[(df2_per_config['optimization_level'] == lvl) & (df2_per_config['topology'] == base)]
        sub_relab = df2_per_config[(df2_per_config['optimization_level'] == lvl) & (df2_per_config['topology'] == relab)]
        E[lbl][f'{base}_vs_{relab}'] = {
            base: {
                'n_configs': len(sub_base),
                'median_spread': float(sub_base['spread'].median()),
                'q75_spread': float(sub_base['spread'].quantile(0.75)),
                'max_spread': float(sub_base['spread'].max()),
                'frac_zero_spread': float((sub_base['spread'] == 0).mean()),
                'median_relative_spread': float(sub_base['relative_spread'].median()),
            },
            relab: {
                'n_configs': len(sub_relab),
                'median_spread': float(sub_relab['spread'].median()),
                'q75_spread': float(sub_relab['spread'].quantile(0.75)),
                'max_spread': float(sub_relab['spread'].max()),
                'frac_zero_spread': float((sub_relab['spread'] == 0).mean()),
                'median_relative_spread': float(sub_relab['relative_spread'].median()),
            },
            'delta_median_spread_(relabelled_minus_base)': float(sub_relab['spread'].median() - sub_base['spread'].median()),
            'mannwhitney_spread_base_vs_relabelled': mannwhitney(sub_base['spread'], sub_relab['spread']),
        }

E['note'] = 'Source: input 2 (control-label-permutation/raw_results.csv, Qiskit 2.5.2) ONLY — not directly comparable to input 1 (Qiskit 2.5.1) medians.'

# ================= F: complete_27 output_two_qubit_depth seed variability (denominator) =================
complete = df1[df1['topology'] == 'complete_27'].copy()
complete_per_config = per_config_stats(complete, 'output_two_qubit_depth')
F = {}
for lvl, lbl in [(0, 'L0'), (1, 'L1'), (3, 'L3')]:
    sub = complete_per_config[complete_per_config['optimization_level'] == lvl]
    n_nonzero = int((sub['spread'] != 0).sum())
    F[lbl] = {
        'n_configs': len(sub),
        'n_nonzero_spread_output_two_qubit_depth': n_nonzero,
        'frac_nonzero_spread_output_two_qubit_depth': float((sub['spread'] != 0).mean()),
        'median_spread': float(sub['spread'].median()),
        'max_spread': float(sub['spread'].max()),
    }

# ================= Assemble final JSON =================
summary = {
    'meta': {
        'input1_path': '/home/claude/qro/raw.csv',
        'input1_qiskit_version': '2.5.1',
        'input1_n_rows': len(df1),
        'input2_path': '/home/claude/work/artifacts/runs/control-label-permutation/raw_results.csv',
        'input2_qiskit_version': sorted(df2['qiskit_version'].unique().tolist()),
        'input2_n_rows': len(df2),
        'seeds': sorted(df1['transpiler_seed'].unique().tolist()),
        'n_constrained_configs_input1': len(per_config),
        'value_col_primary': 'two_qubit_depth_penalty',
        'definitions': {
            'spread': 'max - min of two_qubit_depth_penalty across the 5 seeds, per configuration',
            'relative_spread': 'max / min of two_qubit_depth_penalty across the 5 seeds',
            'iqr': 'interquartile range (q75-q25) of two_qubit_depth_penalty across the 5 seeds',
            'normalized_spread': 'spread / median(two_qubit_depth_penalty) for that configuration',
        },
    },
    'A_per_config_spread_stats': {
        'description': 'Computed for all 144 constrained (topology != complete_27) configs from input 1; full detail in per_config.csv',
        'n_configs': len(per_config),
    },
    'B_stratified_by_level': {
        'pooled_across_topology': B_by_level_pooled,
        'by_topology': B_by_level_by_topology,
    },
    'C_question1_L0_vs_L1L3': C,
    'D_question2_zero_spread_vs_median_eq_1': D,
    'E_relabelling_variability_input2_only': E,
    'F_complete_27_denominator_variability_input1': F,
}

with open(os.path.join(OUTDIR, 'seedstrat_summary.json'), 'w') as f:
    json.dump(summary, f, indent=2)

print('DONE')
print(json.dumps(summary['A_per_config_spread_stats'], indent=2))
