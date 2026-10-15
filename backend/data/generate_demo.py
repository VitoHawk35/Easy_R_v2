import numpy as np
import pandas as pd

np.random.seed(42)
n = 300

# Basic demographics
ids = np.arange(1, n+1)
gender = np.random.choice([0, 1], n)
age = np.random.randint(21, 81, n)
edu = np.random.choice([1, 2, 3], n, p=[0.3, 0.5, 0.2])
hypertension = np.random.choice([0, 1], n, p=[0.7, 0.3])

# Outcomes (binary)
outcome1 = np.random.choice([0, 1], n, p=[0.6, 0.4])
outcome2 = np.random.choice([0, 1], n, p=[0.5, 0.5])
outcome3 = np.random.choice([0, 1], n, p=[0.7, 0.3])

# Lab values with some missing
wbc = np.round(np.random.normal(7.0, 2.5, n), 2)
rbc = np.round(np.random.normal(4.5, 0.6, n), 2)
hgb = np.round(np.random.normal(130, 18, n), 1)
hct = np.round(np.random.normal(40, 5, n), 1)
plt = np.round(np.random.normal(230, 60, n), 0)
neut = np.round(np.random.normal(3.5, 2.0, n), 2)
lymph = np.round(np.random.normal(2.5, 1.2, n), 2)
mono = np.round(np.random.normal(0.4, 0.2, n), 2)
eos = np.round(np.random.normal(0.2, 0.15, n), 2)
baso = np.round(np.random.normal(0.05, 0.03, n), 2)
tbil = np.round(np.random.normal(14, 5, n), 1)
glu = np.round(np.random.normal(5.5, 1.8, n), 2)
tc = np.round(np.random.normal(5.0, 1.5, n), 2)
tg = np.round(np.random.normal(1.8, 1.5, n), 2)

# Introduce missing values
for arr in [wbc, rbc, hgb, hct, plt, neut, lymph, mono, eos, baso, tbil, glu, tc, tg]:
    miss_idx = np.random.choice(n, size=int(n*0.03), replace=False)
    arr[miss_idx] = np.nan

# Create dataframe
df = pd.DataFrame({
    'id': ids,
    '性别': gender,
    '年龄': age,
    '教育程度': edu,
    '高血压': hypertension,
    '结局Y1': outcome1,
    '结局Y2': outcome2,
    '结局Y3': outcome3,
    '白细胞': wbc,
    '红细胞': rbc,
    '血红蛋白': hgb,
    '红细胞压积': hct,
    '血小板': plt,
    '中性粒细胞': neut,
    '淋巴细胞': lymph,
    '单核细胞': mono,
    '嗜酸性细胞': eos,
    '嗜碱性细胞': baso,
    '总胆红素': tbil,
    '空腹血糖': glu,
    '总胆固醇': tc,
    '甘油三酯': tg,
})

# Add more columns to reach ~38
cols_extra = {
    '肌酐': np.round(np.random.normal(80, 20, n), 1),
    '尿素氮': np.round(np.random.normal(5.5, 1.5, n), 2),
    '尿酸': np.round(np.random.normal(350, 80, n), 1),
    '谷丙转氨酶': np.round(np.random.normal(25, 15, n), 1),
    '谷草转氨酶': np.round(np.random.normal(28, 12, n), 1),
    '白蛋白': np.round(np.random.normal(42, 5, n), 1),
    '球蛋白': np.round(np.random.normal(28, 5, n), 1),
    '钾': np.round(np.random.normal(4.2, 0.5, n), 2),
    '钠': np.round(np.random.normal(140, 4, n), 1),
    '氯': np.round(np.random.normal(102, 4, n), 1),
    '钙': np.round(np.random.normal(2.4, 0.15, n), 2),
    '磷': np.round(np.random.normal(1.2, 0.2, n), 2),
    '体重': np.round(np.random.normal(65, 12, n), 1),
    '身高': np.round(np.random.normal(165, 8, n), 1),
    'BMI': np.round(np.random.normal(23.5, 3.5, n), 1),
    '吸烟': np.random.choice([0, 1], n, p=[0.65, 0.35]),
    '饮酒': np.random.choice([0, 1], n, p=[0.75, 0.25]),
}
for k, v in cols_extra.items():
    if k in ['体重','身高','BMI','肌酐','尿酸','谷丙转氨酶','谷草转氨酶','白蛋白','球蛋白']:
        miss = np.random.choice(n, size=int(n*0.02), replace=False)
        v[miss] = np.nan
    df[k] = v

df.to_csv('demo.csv', index=False, encoding='utf-8-sig')
print(f"Generated demo.csv: {df.shape}")
