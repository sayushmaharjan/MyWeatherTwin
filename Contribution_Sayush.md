## Individual Contribution: Sayush Maharjan 

**Github Commit:** https://github.com/sayushmaharjan/CS-5588/commit/d43fdb96cd920a06ddaa7c7e819e26301f9aac93#diff-e7125391bd4d44f4c563042105a7c0cd1616f496ff71591589d505884194d28f

### Week 6 Contributions
- **Agent Tool Schemas:**
  - Created `agent/tool_schemas.py` with JSON schemas for all 5 tools
  - Defined parameter specifications and descriptions for LLM tool selection

- **Application Interface Update:**
  - Updated the UI of the application to integrate the agent and new dashboard
  - Implemented WeatherAPI integration for the agent's real-time weather tools
  - Developed BERT model setup and historical data loading pipeline for agent tools
  - Configured environment variables and API key management for Groq and WeatherAPI
  - Updated quick-action chips for multi-tool scenarios

- **AgentRunner Integration:**
  - Maintains conversation history for follow-up questions
  - Records full execution trace (tool, input, output, timestamp)
  - Handles errors gracefully with partial-answer fallback

- **Evaluation & Documentation:**
  - Designed 3 evaluation scenarios (simple, medium, complex) in `task4_evaluation_report.md`
  - Updated `README.md` with Week 6 agent architecture, tools table, and setup instructions
  - Updated `requirements.txt` with agent-related dependencies
  - Curated and organized historical weather CSV datasets for the agent's analysis tools

### Reflection
In Week 6, I focused on transforming the application into a more intelligent, agent-driven system by building structured tool integration, improving orchestration, and strengthening system reliability. I began by creating agent/tool_schemas.py, where I defined JSON schemas for all five tools, carefully specifying parameters and descriptions to guide accurate LLM tool selection. This step highlighted the importance of clear interface design in ensuring reliable agent behavior. I then updated the application interface to integrate the agent and new dashboard and implemented OpenWeatherMap API for real-time weather retrieval. Additionally, I enhanced quick-action chips to support multi-tool scenarios, improving overall usability. The integration of AgentRunner marked a key advancement, as it maintains conversation history for contextual follow-up questions, records full execution traces for transparency and debugging, and handles errors with partial-answer fallback. Finally, I designed structured evaluation scenarios (simple, medium, and complex), updated documentation including the README and requirements, and organized historical weather datasets to ensure reproducibility and maintainability.