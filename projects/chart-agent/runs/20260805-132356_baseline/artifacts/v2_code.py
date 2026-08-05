import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# Filter to Q1 for 2024 and 2025 using existing integer columns
df_q1 = df[(df['quarter'] == 1) & (df['year'].isin([2024, 2025]))]

# Aggregate and pivot to align categories across years
pivot = (
    df_q1.groupby(['coffee_name', 'year'])['price']
    .sum()
    .unstack('year', fill_value=0)
)

# Ensure both year columns exist even if one is missing
for yr in [2024, 2025]:
    if yr not in pivot.columns:
        pivot[yr] = 0

# Order categories by 2025 sales (descending) to aid comparison
pivot = pivot.sort_values(by=2025, ascending=False)

# Prepare plotting data
labels = pivot.index.tolist()
sales_2024 = pivot[2024].values
sales_2025 = pivot[2025].values
n = len(labels)
x = np.arange(n)
width = 0.38

# Plot
fig, ax = plt.subplots(figsize=(11, 6))

bars_2024 = ax.bar(x - width/2, sales_2024, width=width, label='Q1 2024', color='#4E79A7')
bars_2025 = ax.bar(x + width/2, sales_2025, width=width, label='Q1 2025', color='#F28E2B')

# Axes formatting
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=30, ha='right')
ax.set_ylabel('Total Sales (USD)')
ax.set_title('Q1 Coffee Sales: 2024 vs 2025')

# Currency formatting for y-axis
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, pos: f'${v:,.0f}'))

# Gridlines for readability
ax.grid(axis='y', linestyle='--', linewidth=0.5, alpha=0.6)
ax.set_axisbelow(True)
ax.legend(title='Quarter', frameon=False)

# Optional value labels (only if manageable number of categories)
if n <= 12:
    ax.bar_label(bars_2024, labels=[f'${v:,.0f}' for v in sales_2024], padding=2, fontsize=8)
    ax.bar_label(bars_2025, labels=[f'${v:,.0f}' for v in sales_2025], padding=2, fontsize=8)

plt.tight_layout()
plt.savefig('/Users/jaykim/Documents/Projects/ai-pipeline-projects/agentic-ai/projects/chart-agent/runs/20260805-132356_baseline/baseline_v2.png', dpi=300)
plt.close()