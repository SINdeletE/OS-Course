"""Build the research figure from the supplied evtest button transitions."""
import csv
from decimal import Decimal
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
with (root / 'data/button_events.csv').open() as stream:
    rows = list(csv.DictReader(stream))
origin = Decimal('1794736999.199258')
end = float(Decimal('1794737019.447129') - origin)
plt.rcParams.update({'font.family': 'DejaVu Serif', 'font.size': 11,
                     'pdf.fonttype': 42})
fig, axes = plt.subplots(2, 1, figsize=(8.4, 3.8), sharex=True)
for axis, button, title in zip(axes, ['BTN_LEFT', 'BTN_RIGHT'], ['Левая кнопка', 'Правая кнопка']):
    points = [(0.0, 0)]
    for row in rows:
        if row['button'] == button:
            points.extend([(float(Decimal(row['down']) - origin), 1),
                           (float(Decimal(row['up']) - origin), 0)])
    points.append((end, 0))
    points.sort()
    axis.step([p[0] for p in points], [p[1] for p in points], where='post', color='black', linewidth=1.25)
    axis.set_title(title, loc='left', fontsize=11)
    axis.set_ylim(-0.12, 1.18)
    axis.set_yticks([0, 1], ['Отпущена', 'Нажата'])
    axis.grid(axis='x', color='0.85', linewidth=0.5)
    axis.spines[['top', 'right']].set_visible(False)
axes[-1].set_xlim(0, end)
axes[-1].set_xlabel('Время от первого события фрагмента, с')
fig.tight_layout()
fig.savefig(root / 'pdf/button_states.pdf', bbox_inches='tight')
plt.close(fig)
