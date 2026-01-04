import pandas as pd
import matplotlib.pyplot as plt
from pandas.plotting import scatter_matrix

# 1. Load your log file
try:
    df = pd.read_csv('risk_log.csv')
except FileNotFoundError:
    print("Error: 'risk_log.csv' not found. Make sure it is in the same folder.")
    exit()

# 2. Filter/Clean Data (Optional)
# If you only want to see the moment it gets 'careless', you could filter:
# df = df[df['Dist_to_Truck'] < 20] 

# 3. Define the columns to plot
# We exclude 'Step' usually because it's just time, but keeping it helps 
# you see how things change over the run.
columns_to_plot = ['Dist_to_Truck', 'Speed', 'Safety_Margin', 'Risk']

# 4. Generate the Scatter Matrix
# alpha=0.5 makes points semi-transparent so you can see density
# figsize controls the size of the image
print("Generating Scatter Matrix...")
axs = scatter_matrix(df[columns_to_plot], alpha=0.5, figsize=(12, 12), diagonal='kde')

# 5. Make it readable
plt.suptitle("Scenario Analysis: Variable Correlations", fontsize=16)

# 6. Save and Show
plt.tight_layout(rect=[0, 0.03, 1, 0.95]) # Adjust layout to make room for title
plt.savefig('scatter_matrix.png')
print("Saved plot to 'scatter_matrix.png'")
plt.show()