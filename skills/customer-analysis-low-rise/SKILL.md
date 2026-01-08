---
name: customer-analysis-low-rise
description: 金地上海地区公司营销部，上海方松项目洋房客户情况深度分析.
license: MIT
metadata:
  version: 1.0.0
  author: Homer Meng
  category: marketing
  domain: customer analysis
  updated: 2026-1-8
---

# 上海方松项目洋房客群分析（Customer Analysis for Low-Rise Real Estate Products）

## Overview

This skill processes sales conversation transcripts (docx files) from real estate property viewings and extracts structured customer data specifically for **洋房** (low-rise apartment) products. If the customer is interested in 叠拼别墅 (stacked villa) products instead, the data is skipped.

## Input Format

The skill accepts `.docx` files with the following naming convention:
```
yyyymmdd_上海方松项目_营销_销售接待录音文本XXXX_customerName_salesRepCode_yyyymmdd.docx
```

Example: `20251221_上海方松项目_营销_销售接待录音文本6581程先生_雁_20251221.docx`

### Filename Parsing

| Field | Example | Description |
|-------|---------|-------------|
| Date | 20251221 | Visit date |
| Project Name | 上海方松项目 | Project identifier |
| Customer ID | 6581 | 4-digit customer code |
| Customer Name | 程先生 | Customer name |
| Sales Rep Code | 雁 | Sales rep identifier (春/芳/文/淼/娜/雁) |
| Date | 20251221 | Visit date |


## Workflow for Claude

When a user provides a docx file for analysis, follow these steps:

### Step 1: Convert and Read the Document

Use pandoc to convert the docx file to markdown/text:

```bash
pandoc --track-changes=all <input-file.docx> -o output.md
```

Then read the converted content using the Read tool.

### Step 2: Parse Filename for Metadata

Extract from the filename:
- `date`: Visit date (convert to YYYY-MM-DD format)
- `customer_id`: 4-digit customer code
- `customer_name`: Customer name
- `sales_rep_code`: Sales rep identifier

Filename regex pattern: `(\d{8})_上海方松项目_营销_销售接待录音文本(\d{4})(.+?)_([春秋文淼娜雁])_\d{8}`

### Step 3: Determine Customer Intention

Analyze the conversation to determine which product type the customer is interested in:

- **洋房**: Low-rise apartment (7 floors max, flat-style layout)
- **叠拼**: Stacked villa (multi-level with basement)

**Decision Rule**: If customer shows interest in 叠拼产品, skip processing with message: "Customer interested in 叠拼 product - skipping analysis."

Only proceed if customer wants 洋房 or if intention is unclear.

### Step 4: Extract Answers to Questions

If customer wants 洋房, extract answers to these 15 questions:

| # | Question | Header Name |
|---|----------|-------------|
| 1 | 您是通过什么方式了解到我们项目的？ | channel_source |
| 2 | 项目到你们单位/目前住的地方距离多少？ | distance_km |
| 3 | 洋房您的预算是多少？觉得我们洋房价格怎么样？ | budget_amount |
| 4 | 针对洋房，您大概几个人住，3+1户型能满足吗？ | household_size |
| 5 | 洋房有个北房间，可以做书房，可以做衣帽间，可以做卧室，您有什么打算？ | north_room_plan |
| 6 | 除了看我们的洋房，还看了哪里呀，新房看哪里，二手对比哪个板块？ | competing_projects |
| 7 | 您觉得我们洋房产品对比同价位其他项目您会考虑哪一边？ | product_preference |
| 8 | 针对洋房，您是需要置换，或者手中有部分20%的资金，可以先买，后面再慢慢卖房，再把贷款还掉呢？ | purchase_method |
| 9 | 您来看我们洋房，是首次置业还是二次置业？ | purchase_times |
| 10 | 洋房产品，您是喜欢精装修的还是毛坯的？ | decoration_preference |
| 11 | 下叠加总价950万左右，你预算多少，首付15%有吗？ | down_payment_percent |
| 12 | 我们叠加做的四房三卫设计，你几代人住？需要几个房间？和老人住吗？ | generations_living |
| 13 | 您更喜欢横厅的上叠还是竖厅的上叠？ | upper_unit_preference |
| 14 | 您更喜欢横厅的下叠还是竖厅的下叠？ | lower_unit_preference |
| 15 | 您觉得洋房的装修标准怎么样？ | decoration_standard_feedback |

**Important**: If information is not mentioned in the transcript, use "NA" as the answer.

### Step 5: Save to Parquet

Structure the output with these columns and save to parquet:

- `date` - Visit date (YYYY-MM-DD format)
- `customer_id` - 4-digit customer code
- `customer_name` - Customer name
- `sales_rep_code` - Sales rep identifier
- `raw_filename` - Original filename for reference
- `intention` - Product intention (洋房/叠拼/unclear)
- All 15 question answer columns

Output file: `./customer-analysis-low-rise/customer_analysis_output.parquet`

Use this Python code to save:

```python
import pandas as pd
from pathlib import Path

# Prepare data row
data = {
    'date': '2025-12-21',  # from filename
    'customer_id': '6581',  # from filename
    'customer_name': '程先生',  # from filename
    'sales_rep_code': '雁',  # from filename
    'raw_filename': '20251221_上海方松项目_营销_销售接待录音文本6581程先生_雁_20251221.docx',
    'intention': '洋房',
    'channel_source': '朋友介绍',  # extracted from conversation
    'distance_km': '3-5公里',  # extracted from conversation
    # ... all other answers
}

# Load existing, append, and save
output_path = Path('./customer-analysis-low-rise/customer_analysis_output.parquet')
df_new = pd.DataFrame([data])

if output_path.exists():
    df_existing = pd.read_parquet(output_path)
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
else:
    df_combined = df_new

df_combined.to_parquet(output_path, index=False)
```

## Output Summary

After processing, provide the user with:

1. **Customer Intention**: 洋房 or 叠拼
2. **Extracted Data**: Summary of key findings (if 洋房)
3. **File Location**: Where the parquet file was saved

Example output format:
```
Analysis complete for: 程先生 (2025-12-21)

Customer Intention: 洋房
Channel Source: 朋友介绍
Distance: 3-5公里
Budget: 700-800万
...

Data appended to: ./customer-analysis-low-rise/customer_analysis_output.parquet
Total records: 42
```

## Dependencies

```bash
pip install pandas pyarrow
```

System requirements:
- pandoc (for docx conversion)
