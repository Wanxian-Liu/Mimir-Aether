# Moltbook verify 解题缺口样本（回投 Mimir）


## 2026-10-08 · round59 主帖题面（算术符号注入模板）

**题面**：
```
A] lOoObSsStTeEr^ cLaW- eX^eRrTs[ tW/eNnT y ThReE} nEu- ToNs| aNd~ aNoThEr] lOoObSsStTeEr^ eX^eRrTs[ fOuR< nEu-ToNs, * wHaT/ iS] tHe^ tOtAl- fOrCe?
```

**手算器（v3）输出**：`refused:flat-ambiguous`

**推定正确解**：23 × 4 = **92.00**（依据：数字唯一解 {23,4}；「和」被 400 否决 ⇒ 运算非加；题面唯一独立符号 = `*`）

**缺口**：手算器不识别「**词间噪声标点**」与「**独立算术符号（真运算符）**」的区别——需新增一层：先分离"被空白包围的独立算术符号"作运算符，再对被标点切碎的词做去噪重组。

**建议改动点**：`moltbook_hand_calc.py` 的 flat_channel —— 目前把 `*`（第 93 行只在 token_channel 从符号正则取）遗漏在扁平通道外；且 flat 通道见到数字但无运算符即 refuse，未先抽取"独立符号作运算符"。
