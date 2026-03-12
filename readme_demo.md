

# WeatherTwin — 5-Minute Pitch Script

---

## 🎯 OPENING — The Problem (0:00 – 0:45)

> "Imagine this: You open your weather app. It says 85°F and sunny in Los Angeles. Great, right? But what it *doesn't* tell you is that the average high for today's date is normally 72°F — meaning it's **13 degrees above normal**. It doesn't tell you that this pattern has occurred only **3 times in the last 30 years**. And it definitely doesn't tell you that when this happens in October, it's historically associated with **Santa Ana wind events and elevated wildfire risk.**"

> "Every weather app on the market answers **what**. Almost none of them answer **why it matters**."

> "This is the gap WeatherTwin fills."

---

## 💡 THE SOLUTION — What WeatherTwin Does (0:45 – 1:45)

> "WeatherTwin is a GenAI-powered climate intelligence assistant. It doesn't just tell you the weather — it **explains** it."

> "It combines three things:"

> **One — Real-time weather data** from live APIs, so you always have current conditions.

> **Two — Historical climate records** spanning decades, so we can ground every observation in long-term context. Is today unusual? How unusual? Has this happened before?

> **Three — A large language model agent** that reasons over all of this data and delivers clear, conversational, citation-backed explanations tailored to *your* question."

> "Ask it: *'Is it unusually hot in San Francisco right now?'* — and it won't just say yes or no. It'll pull today's live temperature, compare it against 30 years of historical averages for this exact week, run a statistical analysis, and tell you: *'Yes, today's high of 78°F is 2.1 standard deviations above the October average of 64°F. This is in the top 3% of recorded days. Here's the data.'*"

> "That's the difference between a forecast and an **insight**."

---

## 🏗️ HOW IT WORKS — Architecture (1:45 – 3:00)

> "Under the hood, WeatherTwin runs on a **ReAct agent architecture** — Reason plus Act."

> "Here's the flow:"

> "A user types a natural language question into our Streamlit dashboard. That question goes to **Llama 3.3 70B**, hosted via the Groq API — blazing fast inference. The LLM doesn't just generate an answer from memory. Instead, it **selects from five specialized tools**:"

*[Count on fingers or show slide]*

> 1. **Live weather** — pulls real-time conditions from WeatherAPI
> 2. **Hourly forecast** — gets upcoming conditions for planning
> 3. **Historical analysis** — queries our curated CSV datasets for statistical context
> 4. **BERT prediction** — runs a fine-tuned BERT model to classify expected weather conditions
> 5. **City comparison** — side-by-side analysis of two locations

> "The agent picks the right tool — or *chains multiple tools together* — executes them, observes the results, reasons over them, and then delivers a grounded, explainable response."

> "And here's what makes it trustworthy: **every response shows its reasoning trace**. You can expand it in the UI and see exactly which tools were called, what data was returned, and how the LLM arrived at its conclusion. No black boxes."

> "We also built in authentication, an interactive map interface with Folium, and support for multiple California cities with historical data going back decades."

---

## 📊 DEMO MOMENT (3:00 – 3:45)

*[If live demo, show screen. If not, describe:]*

> "Let me show you a quick example."

> "I type: **'Compare the weather in Los Angeles and San Diego right now, and tell me which one is more unusual for this time of year.'**"

> "The agent fires two tools — live weather for both cities — then pulls historical baselines from our datasets, computes the deviation for each, and responds:"

> *'Los Angeles is currently 9°F above its historical average while San Diego is only 2°F above. LA's conditions are significantly more anomalous. Based on historical records, today's LA temperature ranks in the 94th percentile for this week of the year.'*

> "Click the agent trace — you can see every step. **That's explainability.**"

---

## 🌍 IMPACT & WHO IT'S FOR (3:45 – 4:30)

> "Who needs this?"

> "**Everyday users** who want to know if they should actually worry about a forecast — or if it's just normal weather. **Travelers** planning trips who want historical context, not just a 5-day forecast. **Urban planners and local governments** making infrastructure and emergency management decisions. **Educators and analysts** who want reproducible, explainable climate insights."

> "The broader impact is about **climate literacy and trust**. In a world where extreme weather is becoming more common, people need more than numbers — they need **context, comparison, and confidence** in what they're being told. WeatherTwin provides all three."

> "And unlike proprietary weather platforms, our system is **transparent** — open-source, citation-backed, with human-in-the-loop feedback built into the design."

---

## 🚀 CLOSING — What'S NEXT (4:30 – 5:00)

> "We've built a working prototype with five agent tools, a fine-tuned BERT model, a full Streamlit dashboard, and a modular architecture ready to scale."

> "Next steps: expanding our historical dataset to cover more cities and variables, adding RAG over IPCC climate reports for policy-level context, and running formal evaluation on grounding accuracy, hallucination rate, and user trust scores."

> "Weather apps tell you what's happening. **WeatherTwin tells you what it means.**"

> "Thank you."

---

## 📝 Speaker Notes — Timing Summary

| Section | Time | Duration |
|---|---|---|
| The Problem | 0:00 – 0:45 | 45 sec |
| The Solution | 0:45 – 1:45 | 60 sec |
| Architecture | 1:45 – 3:00 | 75 sec |
| Demo Moment | 3:00 – 3:45 | 45 sec |
| Impact & Users | 3:45 – 4:30 | 45 sec |
| Closing & Next Steps | 4:30 – 5:00 | 30 sec |

