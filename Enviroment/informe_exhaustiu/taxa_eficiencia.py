import os
import pandas as pd
import matplotlib.pyplot as plt

# Carrega el CSV
base_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(base_dir, 'FULL_DATA_Personalitzat_a0.1.csv')
df = pd.read_csv(file_path, sep=';')

total_records = len(df)
count_on_time = len(df[df['Estat'] == 'PUNTUAL'])
count_advanced = len(df[df['Estat'] == 'AVANÇAT'])
count_others = total_records - count_on_time - count_advanced

efficiency_rate = (count_on_time / total_records) * 100 if total_records else 0.0

print(f"Total records processed: {total_records}")
print(f"On-time records (PUNTUAL): {count_on_time}")
print(f"Efficiency rate: {efficiency_rate:.2f}%")

categories = ['ON TIME', 'ADVANCED', 'OTHERS']
values = [count_on_time, count_advanced, count_others]
percentages = [
	(v / total_records) * 100 if total_records else 0.0
	for v in values
]

fig, ax = plt.subplots(figsize=(5, 4))
bars = ax.bar(categories, values, color=['green', 'gray', 'blue'])
ax.set_title("Efficiency rate")
ax.set_ylabel("Record count")

for bar, pct in zip(bars, percentages):
	height = bar.get_height()
	ax.text(bar.get_x() + bar.get_width() / 2, height, f"{pct:.1f}%", ha='center', va='bottom')

plt.tight_layout()
output_path = os.path.join(base_dir, 'taxa_eficiencia.png')
plt.savefig(output_path)
print(f"Chart saved to: {output_path}")