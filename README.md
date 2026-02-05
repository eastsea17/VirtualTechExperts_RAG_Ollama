# Virtual Tech Experts & R&D System (VTE-R&D) V2.7

## Overview

VTE-R&D is an advanced AI agent system designed to automate technical research and strategy formulation. It autonomously gathers scientific papers, patents, and **real-time market news**, debates the findings using diverse personas (Optimist, Skeptic, Competitor, Regulator), and generates a comprehensive HTML report with a full debate transcript.

## Key Features (V2.7 Updates)

- **Multi-Source Data Acquisition**:
  - **OpenAlex**: Academic papers (via API).
  - **PatentsView (USPTO)**: US Patents.
  - **EPO (European Patent Office)**: European Patents.
  - **Tavily (New)**: Real-time market news and business insights.
- **Sequential Expert IDs**: Experts are now assigned clean, readable IDs (e.g., `expert_1`, `expert_2`).
- **Detailed Expert Management**: View document breakdown (Articles/Patents/News) for each expert.
- **Turn-Controlled Debate**: Strictly enforce debate length across all modes using `--turn`.
- **Advanced Debate Graph**:
  - **Mode A (Sequential Loop)**: Optimist <-> Skeptic loop.
  - **Mode B (Round Robin)**: Loop through all 4 personas.
  - **Mode C (Consensus)**: Consensus-seeking loop.
- **Reporting**: HTML reports with full transcript and "Data Statistics" breakdown.

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai/) installed and running.
- API Keys:
  - **Tavily** (Required for News).
  - **USPTO/EPO** (Optional but recommended).

## Installation

1. **Clone the repository**:

   ```bash
   git clone <repo_url>
   cd 260205_VirtualTechExperts_Ollama
   ```

2. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   - Create `.env`:

     ```bash
     USPTO_API_KEY=your_key
     EPO_CONSUMER_KEY=your_key
     EPO_CONSUMER_SECRET=your_secret
     TAVILY_API_KEY=tvly-xxxxxxxxxxxx
     ```

   - Edit `config/config.yaml` to adjust model settings, fetch limits, and `retrieve_top_k`.

## Usage

Run the main script with your research topic:

```bash
python main.py "Liquid Cooling for Data Centers" --mode c --turn 5
```

### Arguments

- `topic`: The research subject.
- `--mode`:
  - `a`: Sequential Loop (Standard)
  - `b`: Round Robin (Comprehensive)
  - `c`: Consensus (Deep Dive)
- `--turn`: Override maximum turns per persona (e.g., `--turn 5` means 5 rounds *per speaker*).

### Manage Virtual Experts

Unified management via `main.py`:

1. **List Saved Experts (with Detailed Stats)**:

   ```bash
   python main.py --list
   ```

   *Output Example:*

   ```text
   Expert ID       | Topic                | Art.  | Pat.  | News  | Total
   -----------------------------------------------------------------------
   expert_1        | Hydrogen Generation  | 150   | 50    | 5     | 205
   expert_2        | Agentic AI           | 100   | 0     | 10    | 110
   ```

2. **Reuse an Expert**:

   ```bash
   python main.py --expert_id expert_1 --mode b
   ```

3. **Delete an Expert**:

   ```bash
   python main.py --delete expert_1
   ```

## System Architecture

1. **Layer 1: Data Acquisition**
   - Fetches Papers (OpenAlex), Patents (USPTO/EPO), and **News (Tavily)**.
2. **Layer 2: Intelligence Engine**
   - Vectorizes documents into ChromaDB.
   - Assigns sequential IDs (`expert_1`).
3. **Layer 3: Debate Simulation**
   - Agents debate utilizing the Vector Store context (`retrieve_top_k` chunks).
   - Loops for `max_turns` rounds.
4. **Layer 4: Reporting**
   - Generates HTML Report + Styled Transcript.

### System Flow

```mermaid
graph TD
    User["User Input: Topic"] --> QE["Query Expander"]
    QE -->|Keywords| APIs{"Data Acquisition"}
    APIs -->|Papers| OA["OpenAlex"]
    APIs -->|US Patents| USPTO["USPTO V1"]
    APIs -->|EU Patents| EPO["EPO OPS"]
    APIs -->|Market News| Tavily["Tavily API"]
    OA --> Combined["Combined Data"]
    USPTO --> Combined
    EPO --> Combined
    Tavily --> Combined
    Combined --> VS["Vector Store (ChromaDB)"]
    VS --> Debate["Debate Simulation"]
    Debate -->|"Loops (Mode A/B/C)"| Agents["Personas: Optimist, Skeptic, etc."]
    Agents -->|Transcript| RG["Report Generator"]
    RG --> HTML["HTML Report"]
```

## Configuration (`config.yaml`)

- **Data Acquisition**: Set `fetch_limit` for OpenAlex, USPTO, EPO, and **Tavily**.
- **Intelligence**: Set `retrieve_top_k` (context depth).
- **Debate Rules**: Set `max_turns_per_persona` and `max_tokens_per_turn`.

## 🖥️ Streamlit Web Interface (New!)

Launch the web-based UI for an interactive experience:

```bash
streamlit run streamlit_app.py
```
<img width="1461" height="811" alt="image" src="https://github.com/user-attachments/assets/8c0c483d-6853-482c-a56f-886674e307e8" />



**Features:**

- **Sidebar Controls**: Adjust all configuration parameters in real-time.
- **One-Click Workflow**: Enter a topic and click "Run Analysis" to execute the full pipeline.
- **Live Progress**: Watch the analysis progress through all 4 layers.
- **Live Debate Transcript**: View each persona's arguments with color-coded styling.
- **Report Preview & Download**: View and download the HTML report directly in the browser.

![Streamlit UI](streamlit_screen.png)

## Key Features (V2.2 Updates)

- **Multi-Source Data Acquisition**:
  - **OpenAlex**: Academic papers (via API).
  - **PatentsView (USPTO)**: US Patents (API Key required).
  - **EPO (European Patent Office)**: European Patents (API Key required).
- **Secure Configuration**: API keys are managed safely via `.env`.
- **Intelligent Query Expansion**: Converts broad topics into precise boolean search queries using LLMs.
- **Advanced Debate Graph**:
  - **Mode A (Sequential)**: Propose -> Critique -> Synthesize.
  - **Mode B (Parallel)**: Simultaneous critique from Competitor, Skeptic, and Regulator.
  - **Mode C (Consensus)**: Back-and-forth iteration to reach agreement.
- **Real-Time Visibility**: Live streaming of debate arguments to the terminal.
- **Detailed Reporting**: Generates formatted HTML reports with data statistics and a full, styled debate transcript appendix.
- **Customizable Models**: Supports Ollama local models and cloud endpoints (e.g., DeepSeek).

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai/) installed and running.
- API Keys for USPTO/EPO (optional but recommended for full data coverage).

## Installation

1. **Clone the repository**:

   ```bash
   git clone <repo_url>
   cd 260205_VirtualTechExperts_Ollama
   ```

2. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   - Rename `.env.example` (or create new) to `.env`:

     ```bash
     USPTO_API_KEY=your_key_here
     EPO_CONSUMER_KEY=your_key_here
     EPO_CONSUMER_SECRET=your_secret_here
     ```

   - Edit `config/config.yaml` to set your preferred Ollama models and debate rules.

## Usage

Run the main script with your research topic:

```bash
python main.py "Liquid Cooling for Data Centers" --mode a
```

### Arguments

- `topic`: The research subject (e.g., "Generative AI", "Solid State Batteries").
- `--mode`: Debate structure.
  - `a`: Sequential (Standard)
  - `b`: Parallel (Comprehensive)
  - `c`: Consensus (Deep Dive)
- `--turn`: (Optional) Override maximum number of turns (e.g., `--turn 5`).

### Manage Virtual Experts (V2.5 Unified)

1. **List Saved Experts**:

   ```bash
   python main.py --list
   ```

2. **Reuse an Expert**:

   ```bash
   python main.py --expert_id exp_12a1de9c --mode b
   ```

3. **Delete an Expert**:

   ```bash
   python main.py --delete exp_12a1de9c
   ```

## System Architecture

1. **Layer 1: Data Acquisition**
   - Expands user query.
   - Fetches global docs from OpenAlex, USPTO, EPO.
2. **Layer 2: Intelligence Engine**
   - Vectorizes documents (ChromaDB + Ollama Embeddings).
   - Creates an Expert Knowledge Base.
3. **Layer 3: Debate Simulation (LangGraph)**
   - Personas (Optimist, Skeptic, etc.) retrieve evidence from the Vector Store.
   - Agents debate the topic, citing specific papers/patents.
4. **Layer 4: Reporting**
   - Summarizes the debate into a strategic executive report (HTML).
   - Appends the full, styled transcript for reference.

### System Flow

```mermaid
graph TD
    User["User Input: Topic"] --> QE["Query Expander"]
    QE -->|Keywords| APIs{"Data Acquisition"}
    APIs -->|Papers| OA["OpenAlex"]
    APIs -->|US Patents| USPTO["USPTO V1"]
    APIs -->|EU Patents| EPO["EPO OPS"]
    OA --> Combined["Combined Data"]
    USPTO --> Combined
    EPO --> Combined
    Combined --> VS["Vector Store (ChromaDB)"]
    VS --> Debate["Debate Simulation (LangGraph)"]
    Debate -->|"Mode A/B/C"| Agents["Personas: Optimist, Skeptic, etc."]
    Agents -->|Transcript| RG["Report Generator"]
    RG --> HTML["HTML Report + Appendix"]
```

## Customization

- **Personas**: Modify `config/personas.yaml` to change agent personalities (e.g., "Elon Musk style" vs "Conservative Engineer").
- **Models**: Change LLMs in `config/config.yaml` (supports any Ollama-compatible model).
