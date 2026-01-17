import pandas as pd
import matplotlib.pyplot as plt
from pandas.plotting import scatter_matrix
import numpy as np

# =============================================================================
# 1. LOAD DATA
# =============================================================================
try:
    df = pd.read_csv('risk_log.csv')
except FileNotFoundError:
    print("Error: 'risk_log.csv' not found. Make sure it is in the same folder.")
    exit()

print(f"Loaded {len(df)} timesteps from risk_log.csv")

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
plt.savefig('time_series_analysis.png', dpi=150)
print("\nSaved: time_series_analysis.png")

# =============================================================================
# 5. SCATTER MATRIX (Your Original Plot, Kept for Comparison)
# =============================================================================

columns_to_plot = ['Dist_to_Truck', 'Speed', 'Safety_Margin', 'Risk']
print("\nGenerating Scatter Matrix...")
fig2, axs = plt.subplots(figsize=(12, 12))
scatter_matrix(df[columns_to_plot], alpha=0.5, figsize=(12, 12), diagonal='kde')
plt.suptitle("Scenario Analysis: Variable Correlations", fontsize=16)
plt.tight_layout(rect=[0, 0.03, 1, 0.95])
plt.savefig('scatter_matrix.png', dpi=150)
print("Saved: scatter_matrix.png")

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
ax.axvline(x=0.6, color='orange', linestyle='--', linewidth=2, label='Creep Threshold')
ax.axvline(x=0.85, color='red', linestyle='--', linewidth=2, label='Emergency Threshold')
ax.set_xlabel('Risk Value', fontsize=12)
ax.set_ylabel('Frequency (Timesteps)', fontsize=12)
ax.set_title('Risk Distribution During Operation (Excluding Emergency Stop Plateau)', fontsize=12)
ax.legend()
ax.grid(True, alpha=0.3)

# Add percentage annotations
total_steps = len(risk_operational)
below_creep = len(risk_operational[risk_operational < 0.6]) / total_steps * 100
in_creep = len(risk_operational[(risk_operational >= 0.6) & (risk_operational < 0.85)]) / total_steps * 100
in_emergency = len(risk_operational[risk_operational >= 0.85]) / total_steps * 100

textstr = f'Below 0.6: {below_creep:.1f}%\nCreep Zone: {in_creep:.1f}%\nEmergency: {in_emergency:.1f}%'
ax.text(0.02, 0.95, textstr, transform=ax.transAxes, fontsize=10,
        verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()
plt.savefig('risk_distribution.png', dpi=150)
print("\nSaved: risk_distribution.png")

plt.show()
print("\nAnalysis complete.")
