import pandas as pd
import matplotlib.pyplot as plt
from pandas.plotting import scatter_matrix
import numpy as np
import sys
import shutil
from datetime import datetime
from pathlib import Path

class _Tee:
    def __init__(self, *streams): self.streams = streams
    def write(self, s):
        for st in self.streams: st.write(s)
    def flush(self):
        for st in self.streams: st.flush()

# =============================================================================
# 1. LOAD DATA
# =============================================================================
try:
    df = pd.read_csv('risk_log.csv')
except FileNotFoundError:
    print("Error: 'risk_log.csv' not found. Make sure it is in the same folder.")
    exit()

OUTPUT_DIR = Path('results') / f'run_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}'
OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
sys.stdout = _Tee(sys.__stdout__, open(OUTPUT_DIR / 'analysis_log.txt', 'w', encoding='utf-8'))

print(f"Loaded {len(df)} timesteps from risk_log.csv")
print(f"Output folder: {OUTPUT_DIR}")

shutil.copy2('risk_log.csv', OUTPUT_DIR / 'risk_log.csv')
print(f"Archived source CSV to: {OUTPUT_DIR / 'risk_log.csv'}")

# =============================================================================
# 2. DETECT CRITICAL EVENTS (For Annotations)
# =============================================================================

# Event A: First time Risk exceeds 0.6 threshold (Creep Mode Activation)
creep_activation = df[df['Risk'] > 0.6]['Step'].min()

# Event B: Pedestrian Detection (Risk jumps to 1.0)
ped_detection = df[df['Risk'] == 1.0]['Step'].min()

# Event C: Recovery Start (First step after Risk drops from 1.0)
post_detection = df[(df['Step'] > ped_detection) & (df['Risk'] < 1.0)]
recovery_start = post_detection['Step'].min() if len(post_detection) > 0 else None

# Event D: Safe Zone (Risk drops below 0.1)
safe_zone = df[(df['Step'] > 90) & (df['Risk'] < 0.1)]['Step'].min()

print(f"\nDetected Events:")
print(f"  Creep Mode Activated: Step {creep_activation}")
print(f"  Pedestrian Detected:  Step {ped_detection}")
print(f"  Recovery Started:     Step {recovery_start}")
print(f"  Safe Zone Reached:    Step {safe_zone}")

# =============================================================================
# 3. MULTI-PANEL TIME SERIES PLOT
# =============================================================================

fig, axes = plt.subplots(5, 1, figsize=(14, 12), sharex=True)
fig.suptitle('Bayesian Safety Controller: Temporal Behavior Analysis', fontsize=14, fontweight='bold')

# Color scheme
color_dist = '#2E86AB'      # Blue
color_speed = '#A23B72'     # Magenta
color_margin = '#F18F01'    # Orange
color_risk = '#C73E1D'      # Red
color_stop = '#6B4E71'      # Purple

# Panel 1: Distance to Truck
ax1 = axes[0]
ax1.plot(df['Step'], df['Dist_to_Truck'], color=color_dist, linewidth=1.5)
ax1.set_ylabel('Dist to Truck (m)', fontsize=10)
ax1.grid(True, alpha=0.3)
ax1.set_ylim(bottom=0)

# Panel 2: Speed
ax2 = axes[1]
ax2.plot(df['Step'], df['Speed'], color=color_speed, linewidth=1.5)
ax2.axhline(y=2.75, color='gray', linestyle='--', alpha=0.7, label='Creep Limit (2.75 m/s)')
ax2.axhline(y=6.0, color='gray', linestyle=':', alpha=0.7, label='Target Speed (6.0 m/s)')
ax2.set_ylabel('Speed (m/s)', fontsize=10)
ax2.legend(loc='upper right', fontsize=8)
ax2.grid(True, alpha=0.3)
ax2.set_ylim(bottom=0)

# Panel 3: Stopping Distance
ax3 = axes[2]
ax3.plot(df['Step'], df['Stopping_Dist'], color=color_stop, linewidth=1.5)
ax3.set_ylabel('Stopping Dist (m)', fontsize=10)
ax3.grid(True, alpha=0.3)
ax3.set_ylim(bottom=0)

# Panel 4: Safety Margin
ax4 = axes[3]
ax4.plot(df['Step'], df['Safety_Margin'], color=color_margin, linewidth=1.5)
ax4.axhline(y=0, color='red', linestyle='-', alpha=0.5, linewidth=2, label='Zero Margin (Critical)')
ax4.fill_between(df['Step'], df['Safety_Margin'], 0, 
                  where=(df['Safety_Margin'] < 0), 
                  color='red', alpha=0.2, label='Negative Margin Zone')
ax4.set_ylabel('Safety Margin (m)', fontsize=10)
ax4.legend(loc='upper right', fontsize=8)
ax4.grid(True, alpha=0.3)

# Panel 5: Risk (The Key Output)
ax5 = axes[4]
ax5.plot(df['Step'], df['Risk'], color=color_risk, linewidth=1.5)
ax5.axhline(y=0.6, color='orange', linestyle='--', alpha=0.7, label='Creep Threshold (0.6)')
ax5.axhline(y=0.85, color='red', linestyle='--', alpha=0.7, label='Emergency Threshold (0.85)')
ax5.fill_between(df['Step'], df['Risk'], 0.6, 
                  where=(df['Risk'] > 0.6) & (df['Risk'] <= 0.85), 
                  color='orange', alpha=0.2, label='Creep Zone')
ax5.fill_between(df['Step'], df['Risk'], 0.85, 
                  where=(df['Risk'] > 0.85), 
                  color='red', alpha=0.2, label='Emergency Zone')
ax5.set_ylabel('Risk P(collision)', fontsize=10)
ax5.set_xlabel('Timestep', fontsize=10)
ax5.legend(loc='upper right', fontsize=8)
ax5.grid(True, alpha=0.3)
ax5.set_ylim(0, 1.05)

# =============================================================================
# 4. ADD VERTICAL EVENT MARKERS (Across All Panels)
# =============================================================================

event_lines = [
    (creep_activation, 'Creep Mode', 'orange'),
    (ped_detection, 'Pedestrian Detected', 'red'),
    (recovery_start, 'Recovery', 'green'),
    (safe_zone, 'Safe Zone', 'blue')
]

for ax in axes:
    for step, label, color in event_lines:
        if step is not None and not np.isnan(step):
            ax.axvline(x=step, color=color, linestyle='--', alpha=0.6, linewidth=1.5)

# Add text labels only on top panel
for step, label, color in event_lines:
    if step is not None and not np.isnan(step):
        ax1.annotate(label, xy=(step, ax1.get_ylim()[1]), 
                     xytext=(step + 5, ax1.get_ylim()[1] * 0.9),
                     fontsize=8, color=color, fontweight='bold',
                     rotation=0)

plt.tight_layout(rect=[0, 0.03, 1, 0.96])
plt.savefig(OUTPUT_DIR / 'time_series_analysis.png', dpi=150)
print(f"\nSaved: {OUTPUT_DIR / 'time_series_analysis.png'}")

# =============================================================================
# 5. SCATTER MATRIX (Your Original Plot, Kept for Comparison)
# =============================================================================

columns_to_plot = ['Dist_to_Truck', 'Speed', 'Safety_Margin', 'Risk']
print("\nGenerating Scatter Matrix...")
fig2, axs = plt.subplots(figsize=(12, 12))
scatter_matrix(df[columns_to_plot], alpha=0.5, figsize=(12, 12), diagonal='kde')
plt.suptitle("Scenario Analysis: Variable Correlations", fontsize=16)
plt.tight_layout(rect=[0, 0.03, 1, 0.95])
plt.savefig(OUTPUT_DIR / 'scatter_matrix.png', dpi=150)
print(f"Saved: {OUTPUT_DIR / 'scatter_matrix.png'}")

# =============================================================================
# 6. PHASE ANALYSIS (Research Insight: Variance by Phase)
# =============================================================================

# Define phases based on detected events
def get_phase(step):
    if step < creep_activation:
        return 'Approach'
    elif step < ped_detection:
        return 'Creep (Pre-Detection)'
    elif step <= 89:  # During pedestrian detection
        return 'Emergency Stop'
    elif step < safe_zone:
        return 'Recovery/Creep'
    else:
        return 'Safe Departure'

df['Phase'] = df['Step'].apply(get_phase)

# Calculate statistics by phase
print("\n" + "="*60)
print("PHASE ANALYSIS: Speed Variance (Hysteresis Validation)")
print("="*60)

phase_stats = df.groupby('Phase').agg({
    'Speed': ['mean', 'std', 'min', 'max'],
    'Risk': ['mean', 'max'],
    'Step': 'count'
}).round(3)

print(phase_stats)

# Specific insight: Compare speed variance in Creep vs Normal
creep_phases = df[df['Phase'].str.contains('Creep')]
normal_phases = df[df['Phase'] == 'Safe Departure']

if len(creep_phases) > 0 and len(normal_phases) > 0:
    creep_var = creep_phases['Speed'].var()
    normal_var = normal_phases['Speed'].var()
    print(f"\nSpeed Variance in Creep Mode: {creep_var:.4f}")
    print(f"Speed Variance in Normal Mode: {normal_var:.4f}")
    print(f"Ratio (Lower = More Stable): {creep_var/normal_var:.2f}x")

# =============================================================================
# 7. RISK DISTRIBUTION HISTOGRAM
# =============================================================================

fig3, ax = plt.subplots(figsize=(10, 5))

# Filter out the Risk=1.0 emergency stop plateau for cleaner visualization
risk_operational = df[df['Risk'] < 1.0]['Risk']

ax.hist(risk_operational, bins=50, color=color_risk, alpha=0.7, edgecolor='black')
ax.axvline(x=0.6, color='orange', linestyle='--', linewidth=2, label='Creep Threshold (risk = 0.60)')
ax.axvline(x=0.85, color='red', linestyle='--', linewidth=2, label='Critical Threshold (risk = 0.85)')
ax.set_xlabel('Risk Value', fontsize=12)
ax.set_ylabel('Frequency (Timesteps)', fontsize=12)
ax.set_title('Risk Distribution During Operation (Excluding Saturated Emergency-Stop Plateau)', fontsize=12)
ax.legend(loc='upper left', framealpha=0.9)
ax.grid(True, alpha=0.3)

# Give the percentage box headroom so it sits clearly below the legend
ymax = ax.get_ylim()[1]
ax.set_ylim(top=ymax * 1.15)

# Add percentage annotations (placed below the legend on the left)
total_steps = len(risk_operational)
below_creep = len(risk_operational[risk_operational <= 0.6]) / total_steps * 100
in_creep = len(risk_operational[(risk_operational > 0.6) & (risk_operational <= 0.85)]) / total_steps * 100
in_emergency = len(risk_operational[risk_operational > 0.85]) / total_steps * 100

textstr = (
    f'Normal: risk ≤ 0.60 ({below_creep:.1f}%)\n'
    f'Creep: 0.60 < risk ≤ 0.85 ({in_creep:.1f}%)\n'
    f'Non-saturated critical: 0.85 < risk < 1.00 ({in_emergency:.1f}%)'
)
ax.text(0.02, 0.70, textstr, transform=ax.transAxes, fontsize=10,
        verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.85))

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'risk_distribution.png', dpi=150)
print(f"\nSaved: {OUTPUT_DIR / 'risk_distribution.png'}")

# =============================================================================
# 8. PHASE-COLORED SCATTER MATRIX (Risk < 1.0)
# =============================================================================

vars_sm = ['Dist_to_Truck', 'Speed', 'Safety_Margin', 'Risk']
df_sm = df[df['Risk'] < 1.0].copy()

phase_colors = {
    'Approach':              '#2E86AB',
    'Creep (Pre-Detection)': '#F18F01',
    'Emergency Stop':        '#C73E1D',
    'Recovery/Creep':        '#A23B72',
    'Safe Departure':        '#6B4E71',
}

fig4, axes_sm = plt.subplots(len(vars_sm), len(vars_sm), figsize=(12, 12))
fig4.suptitle('Phase-Colored Scatter Matrix (Risk < 1.0)', fontsize=14, fontweight='bold')

for i, yv in enumerate(vars_sm):
    for j, xv in enumerate(vars_sm):
        ax = axes_sm[i, j]
        if i == j:
            for phase, color in phase_colors.items():
                vals = df_sm[df_sm['Phase'] == phase][xv]
                if len(vals) > 1:
                    ax.hist(vals, bins=20, color=color, alpha=0.5)
        else:
            for phase, color in phase_colors.items():
                sub = df_sm[df_sm['Phase'] == phase]
                ax.scatter(sub[xv], sub[yv], c=color, alpha=0.5, s=10)
        if i == len(vars_sm) - 1:
            ax.set_xlabel(xv, fontsize=9)
        else:
            ax.set_xticklabels([])
        if j == 0:
            ax.set_ylabel(yv, fontsize=9)
        else:
            ax.set_yticklabels([])
        ax.tick_params(axis='both', labelsize=7)

handles = [plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=c,
                      markersize=8, label=p) for p, c in phase_colors.items()]
fig4.legend(handles=handles, loc='upper right', fontsize=9, bbox_to_anchor=(0.99, 0.97))

plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig(OUTPUT_DIR / 'scatter_matrix_phased.png', dpi=150)
print(f"Saved: {OUTPUT_DIR / 'scatter_matrix_phased.png'}")

# =============================================================================
# 9. CORRELATION HEATMAP + FOCUSED SCATTER
# =============================================================================

fig5, (axh, axsc) = plt.subplots(1, 2, figsize=(14, 6))

corr = df_sm[vars_sm].corr()
im = axh.imshow(corr.values, cmap='RdBu_r', vmin=-1, vmax=1)
axh.set_xticks(range(len(vars_sm)))
axh.set_yticks(range(len(vars_sm)))
axh.set_xticklabels(vars_sm, rotation=30, ha='right')
axh.set_yticklabels(vars_sm)
axh.set_title('Pearson Correlation (Risk < 1.0)', fontsize=12)
for i in range(len(vars_sm)):
    for j in range(len(vars_sm)):
        v = corr.values[i, j]
        axh.text(j, i, f'{v:.2f}', ha='center', va='center',
                 color='white' if abs(v) > 0.5 else 'black', fontsize=10)
fig5.colorbar(im, ax=axh, fraction=0.046, pad=0.04)

sc = axsc.scatter(df_sm['Safety_Margin'], df_sm['Risk'], c=df_sm['Speed'],
                  cmap='viridis', alpha=0.6, s=15)
axsc.axvline(x=0, color='red', linestyle='-', alpha=0.5, linewidth=1.5)
axsc.axhline(y=0.6, color='orange', linestyle='--', alpha=0.7, label='Creep Threshold')
axsc.axhline(y=0.85, color='red', linestyle='--', alpha=0.7, label='Emergency Threshold')
axsc.set_xlabel('Safety Margin (m)', fontsize=11)
axsc.set_ylabel('Risk', fontsize=11)
axsc.set_title('Safety Margin vs Risk  (color = Speed)', fontsize=12)
axsc.legend(loc='upper right', fontsize=9)
axsc.grid(True, alpha=0.3)
fig5.colorbar(sc, ax=axsc, label='Speed (m/s)', fraction=0.046, pad=0.04)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'risk_correlations.png', dpi=150)
print(f"Saved: {OUTPUT_DIR / 'risk_correlations.png'}")

plt.show()
print("\nAnalysis complete.")
