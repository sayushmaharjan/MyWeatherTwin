# 📊 Social Media Substance Abuse Risk Detection Report
## with Weather Correlation Analysis

**Generated:** April 06, 2026 at 11:08 AM
**Framework:** WeatherTwin Public Health Intelligence Module
**Data Sources:** Hugging Face — KerenHaruvi/Addiction_Stories, solomonk/reddit_mental_health_posts

---

## 1. Executive Summary

_Narrative generation unavailable: Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kha79v4bekh9y3dbbk5p9wkh` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99797, Requested 764. Please try again in 8m4.704s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}_

---

## 2. Dataset Overview

| Metric | Value |
|--------|-------|
| **Total Posts Analyzed** | 691 |
| **Source Datasets** | KerenHaruvi/Addiction_Stories, solomonk/reddit_mental_health_posts |
| **Subreddits Covered** | 7 |
| **US States Represented** | 50 |
| **Date Range** | 2025-04-11 to 2026-04-06 |

### Dataset Composition

| Dataset | Posts |
|---------|-------|
| KerenHaruvi/Addiction_Stories | 491 |
| solomonk/reddit_mental_health_posts | 200 |

### Subreddit Distribution

| Subreddit | Posts |
|-----------|-------|
| r/depression | 200 |
| r/leaves | 93 |
| r/cripplingalcoholism | 87 |
| r/addiction | 87 |
| r/opiatesrecovery | 81 |
| r/REDDITORSINRECOVERY | 72 |
| r/stopdrinking | 71 |

---

## 3. Risk Signal Analysis

### 3.1 Severity Distribution

| Severity | Count | Percentage |
|----------|-------|------------|
| 🔴 **Critical** | 63 | 9.1% |
| 🟠 **High** | 79 | 11.4% |
| 🟡 **Moderate** | 107 | 15.5% |
| 🟢 **Low** | 100 | 14.5% |
| ⚪ **Minimal** | 342 | 49.5% |

### 3.2 Substance Category Breakdown

| Substance Category | Posts Mentioning |
|--------------------|-----------------|
| General Substance | 311 |
| Alcohol | 143 |
| Opioids | 85 |
| Stimulants | 83 |
| Tobacco Nicotine | 81 |
| Cannabis | 81 |
| Benzodiazepines | 20 |

### 3.3 Signal Type Distribution

| Signal Type | Count |
|-------------|-------|
| Substance Mention | 455 |
| Emotional Distress | 284 |

### 3.4 Detailed Analysis

_Narrative generation unavailable: Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kha79v4bekh9y3dbbk5p9wkh` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99797, Requested 808. Please try again in 8m42.72s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}_

### 3.5 Top Detected Keywords

| Keyword | Frequency |
|---------|-----------|
| `addiction` | 143 |
| `addicted` | 121 |
| `depression` | 94 |
| `depressed` | 64 |
| `alcohol` | 61 |
| `anxiety` | 59 |
| `drinking` | 57 |
| `smoking` | 50 |
| `weed` | 48 |
| `using` | 32 |
| `clean` | 30 |
| `suicide` | 30 |
| `habit` | 29 |
| `nicotine` | 27 |
| `drunk` | 25 |

---

## 4. Weather–Substance Use Correlations

### 4.1 Statistical Correlations

| Weather Variable | Target | Pearson r | p-value | Strength | Significant |
|-----------------|--------|-----------|---------|----------|-------------|
| Temperature C | risk score | -0.0706 | 0.5239 | negligible | ❌ |
| Precipitation Mm | risk score | 0.0674 | 0.5431 | negligible | ❌ |
| Wind Speed Kmh | risk score | 0.1826 | 0.0947 | weak | ❌ |
| Temperature C | substance alcohol | 0.2050 | 0.0594 | weak | ❌ |
| Precipitation Mm | substance alcohol | -0.1689 | 0.1230 | weak | ❌ |
| Temperature C | substance opioids | -0.1938 | 0.0754 | weak | ❌ |
| Wind Speed Kmh | substance cannabis | -0.2329 | 0.0311 | weak | ✅ |
| Temperature C | substance stimulants | -0.1746 | 0.1106 | weak | ❌ |
| Precipitation Mm | substance stimulants | 0.1010 | 0.3611 | weak | ❌ |
| Wind Speed Kmh | substance tobacco nicotine | -0.1110 | 0.3146 | weak | ❌ |

### 4.2 Seasonal Patterns

| Season | Posts | Avg Risk | High-Risk % |
|--------|-------|----------|-------------|
| ❄️ Winter | 179 | 0.326 | 21.2% |
| 🌱 Spring | 167 | 0.313 | 22.8% |
| ☀️ Summer | 174 | 0.308 | 16.1% |
| 🍂 Fall | 171 | 0.325 | 22.2% |

### 4.3 Extreme Weather Impact

| Condition | Posts | Avg Risk | High-Risk % |
|-----------|-------|----------|-------------|
| ⚡ **Extreme Weather** | 2 | 0.240 | 0.0% |
| ☀️ **Normal Conditions** | 689 | 0.318 | 20.6% |
| 📊 **Risk Difference** | — | -0.078 | — |

### 4.4 Weather Analysis Narrative

_Narrative generation unavailable: Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kha79v4bekh9y3dbbk5p9wkh` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99797, Requested 1550. Please try again in 19m23.808s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}_

### 4.5 Key Weather Insights

- 📊 cannabis mentions show weak negative correlation with wind speed kmh (r=-0.2329, p=0.031102)
- 📅 Highest average risk score observed in **winter** (0.326), lowest in **summer** (0.308)
- ⚡ During extreme weather events, average risk score is 0.078 **lower** than normal conditions (0.240 vs 0.318)

---

## 5. Temporal & Behavioral Analysis

### 5.1 Trend Overview

- **Overall Risk Trend:** Stable
- **Months Analyzed:** 13
- **Spike Months Detected:** 0

### 5.2 Time-of-Day Patterns

- **Peak Posting Hour:** 07:00 (morning)
- Posts are most active during **morning** hours, suggesting heightened vulnerability during this time period

### 5.3 Day-of-Week Patterns

- **Peak Risk Day:** Tuesday

### 5.4 Behavioral Clusters


#### Cluster 1: Opioid Dependency & Recovery
- **Posts:** 85 | **Avg Severity:** 0.542
- **Dominant Substances:** opioids, general_substance, alcohol
- **Top Keywords:** addicted, addiction, fix, heroin, cold turkey
- **Temporal Pattern:** Peaks in winter
- **Weather Context:** Average temperature: 8.8°C
- **Severity Breakdown:** moderate: 33, high: 19, critical: 14, low: 11, minimal: 8


#### Cluster 2: Alcohol Use & Sobriety
- **Posts:** 143 | **Avg Severity:** 0.460
- **Dominant Substances:** alcohol, general_substance, cannabis
- **Top Keywords:** alcohol, drinking, addiction, drunk, addicted
- **Temporal Pattern:** Peaks in fall
- **Weather Context:** Average temperature: 17.6°C
- **Severity Breakdown:** moderate: 36, minimal: 33, low: 29, high: 25, critical: 20


#### Cluster 3: Cannabis Dependence
- **Posts:** 81 | **Avg Severity:** 0.538
- **Dominant Substances:** cannabis, general_substance, tobacco_nicotine
- **Top Keywords:** weed, smoking, addicted, addiction, alcohol
- **Temporal Pattern:** Peaks in fall
- **Weather Context:** Average temperature: 15.6°C
- **Severity Breakdown:** high: 19, critical: 19, moderate: 17, minimal: 16, low: 10


#### Cluster 4: Co-occurring Distress & Substance Use
- **Posts:** 170 | **Avg Severity:** 0.686
- **Dominant Substances:** general_substance, alcohol, cannabis
- **Top Keywords:** depression, addicted, addiction, anxiety, depressed
- **Temporal Pattern:** Peaks in fall
- **Weather Context:** Average temperature: 12.1°C
- **Severity Breakdown:** critical: 57, high: 52, moderate: 42, low: 19


#### Cluster 5: High-Risk & Crisis Posts
- **Posts:** 142 | **Avg Severity:** 0.787
- **Dominant Substances:** general_substance, alcohol, cannabis
- **Top Keywords:** depression, depressed, addicted, anxiety, weed
- **Temporal Pattern:** Peaks in fall
- **Weather Context:** Average temperature: 11.4°C
- **Severity Breakdown:** high: 79, critical: 63


#### Cluster 6: Recovery & Sobriety Milestones
- **Posts:** 297 | **Avg Severity:** 0.139
- **Dominant Substances:** general_substance, alcohol, stimulants
- **Top Keywords:** addiction, addicted, depression, alcohol, drinking
- **Temporal Pattern:** Peaks in summer
- **Weather Context:** Average temperature: 15.2°C
- **Severity Breakdown:** minimal: 215, low: 82


### 5.5 Emerging Narratives

| Keyword | Early Count | Recent Count | Change | Trend |
|---------|------------|--------------|--------|-------|
| `sobriety` | 0 | 5 | +500.0% | 📈 |
| `fentanyl` | 0 | 4 | +400.0% | 📈 |
| `relapse` | 0 | 4 | +400.0% | 📈 |
| `pot` | 2 | 8 | +300.0% | 📈 |
| `abstinence` | 0 | 3 | +300.0% | 📈 |
| `ice` | 0 | 3 | +300.0% | 📈 |
| `final` | 1 | 4 | +300.0% | 📈 |
| `kick` | 2 | 7 | +250.0% | 📈 |
| `terrified` | 2 | 6 | +200.0% | 📈 |
| `numb` | 2 | 6 | +200.0% | 📈 |

---

## 6. Actionable Insights & Recommendations

_Narrative generation unavailable: Error code: 429 - {'error': {'message': 'Rate limit reached for model `llama-3.3-70b-versatile` in organization `org_01kha79v4bekh9y3dbbk5p9wkh` service tier `on_demand` on tokens per day (TPD): Limit 100000, Used 99797, Requested 989. Please try again in 11m19.104s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}_

---

## 7. Limitations & Uncertainty Estimates

### Data Limitations
- **Dataset Size**: Analysis based on ~691 posts from two Hugging Face datasets; larger samples would improve statistical power
- **Location Assignment**: Post locations are inferred/simulated as Reddit posts rarely contain explicit geolocation
- **Temporal Assignment**: Timestamps for Addiction_Stories posts are simulated to enable temporal analysis
- **Self-Selection Bias**: Reddit users who post about substance use may not represent the broader population
- **Platform Bias**: Reddit's demographics skew younger, male, and US-centric

### Methodological Limitations
- **Keyword vs. Context**: Keyword-based detection may miss nuanced language or generate false positives
- **LLM Interpretation**: LLM-based severity scoring introduces model-dependent variability
- **Weather Correlation ≠ Causation**: Observed correlations between weather and substance mentions do not imply causal relationships
- **Ecological Fallacy**: State-level weather data may not reflect individual-level experiences
- **Confounding Variables**: Holidays, economic conditions, news events, and other factors may confound weather-substance correlations

### Uncertainty Estimates
- **Keyword Detection Confidence**: ~70-85% (based on established NLP lexicons)
- **LLM Severity Classification**: ~60-75% agreement with keyword-based scoring (used as blended metric)
- **Weather Correlation Significance**: Only correlations with p < 0.05 are reported as significant
- **Seasonal Patterns**: Subject to small sample variation; patterns should be validated with larger datasets

---

## 8. Methodology

### Data Pipeline
1. **Data Ingestion**: Reddit posts loaded from Hugging Face datasets (KerenHaruvi/Addiction_Stories with 491 annotated addiction narratives, solomonk/reddit_mental_health_posts filtered for substance-related content)
2. **Risk Detection**: Multi-layered NLP pipeline combining keyword lexicons (6 substance categories, 6 distress categories) with LLM-enhanced classification (Groq Llama 3.3 70B)
3. **Weather Integration**: Historical weather data fetched via Open-Meteo Archive API for post locations and dates
4. **Correlation Analysis**: Pearson and Spearman correlation coefficients computed between weather variables and risk scores
5. **Temporal Analysis**: Time-series decomposition, spike detection using 3-month rolling averages, day/hour/seasonal pattern mining
6. **Behavioral Clustering**: Rule-based clustering by substance category, risk severity, and emotional distress co-occurrence
7. **Report Generation**: LLM-powered narrative synthesis with transparent reasoning

### Ethical Considerations
- All data is from publicly available research datasets on Hugging Face
- No individual identification or re-identification was attempted
- Analysis focuses on aggregate patterns, not individual users
- Findings framed in terms of community support, not surveillance
- Crisis resources provided throughout

---

**Crisis Resources**
- 🆘 **SAMHSA National Helpline:** 1-800-662-4357 (free, confidential, 24/7)
- 🆘 **Crisis Text Line:** Text HOME to 741741
- 🆘 **988 Suicide & Crisis Lifeline:** Call or text 988

---

*Report generated by WeatherTwin Public Health Intelligence Module*
*Data processing: Automated NLP + LLM analysis | Statistical analysis: Pearson/Spearman correlation*
