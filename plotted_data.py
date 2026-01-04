import pandas as pd
import matplotlib.pyplot as plt

# Read the CSV
data = pd.read_csv('risk_log.csv')

# Plot Risk and Distance
plt.figure(figsize=(10, 6))

# Subplot 1: Risk
plt.subplot(2, 1, 1)
plt.plot(data['Step'], data['Risk'], label='Risk', color='red')
plt.axhline(y=0.6, color='black', linestyle='--', label='Threshold (0.6)')
plt.ylabel('Risk')
plt.legend()
plt.title('Risk vs. Time Step')

# Subplot 2: Distance to Truck
plt.subplot(2, 1, 2)
plt.plot(data['Step'], data['Dist_to_Truck'], label='Distance', color='blue')
plt.ylabel('Meters')
plt.xlabel('Step')
plt.legend()

plt.tight_layout()
plt.show()