import pandas as pd
import matplotlib.pyplot as plt

# Load the data
df = pd.read_csv('research_data.csv')

# create a figure with 2 subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

# Graph 1: System Latency (The "Real-Time" Constraint)
# This proves you care about efficiency
ax1.plot(df['Timestamp'], df['Latency_ms'], color='purple')
ax1.set_title('System Latency over Time', fontsize=14)
ax1.set_ylabel('Processing Time (ms)')
ax1.grid(True, alpha=0.3)

# Graph 2: Cross Track Error (The "Control" Stability)
# This proves you care about precision
ax2.plot(df['Timestamp'], df['Cross_Track_Error'], color='red')
ax2.set_title('Controller Accuracy (Cross-Track Error)', fontsize=14)
ax2.set_xlabel('Simulation Time (s)')
ax2.set_ylabel('Error (meters)')
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('research_metrics.png')
plt.show()