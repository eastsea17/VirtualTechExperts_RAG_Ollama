# Project Plan: Virtual Tech Experts & R&D Acceleration System

## 1. Project Overview

* **Project Name**: Virtual Tech Experts R&D System (VTE-R&D)
* **Goal**: To build a Multi-Agent system where users can instantly generate RAG-based virtual experts to debate technical topics and produce comprehensive research reports.
* **Core Value**: Overcoming physical/time constraints in R&D by utilizing AI swarm intelligence powered by local/cloud LLMs and real-time data.

## 2. Problem & Solution

* **Problem**: Time-consuming literature review, difficulty in accessing human experts, and the need for continuous hypothesis verification.
* **Solution**:
  * **On-demand Knowledge**: Instant instantiation of experts using RAG.
  * **Context-Aware**: Agents possess deep context via real-time data fetching (OpenAlex for papers, EPO for patents).
  * **Multi-Perspective**: Debate simulation using distinct personas (Optimist, Skeptic, etc.).

## 3. System Architecture & Tech Stack

### 3.1. High-Level Architecture

1. **Layer 1 (Data Acquisition)**: External API handling (OpenAlex, EPO OPS).
2. **Layer 2 (Intelligence Engine)**: High-speed Clustering & Filtering.
3. **Layer 3 (Agentic Core)**: Local/Cloud LLM Inference & Debate Orchestration.

### 3.2. Technical Specifications (Strict Constraints)

The system must be built using the following specific models and libraries:

* **Language**: Python 3.10+
* **LLM Inference (Ollama Support Required)**:
  * **Primary (Local)**: `deepseek-r1:14b` (via Ollama Local)
  * **Secondary (Cloud)**: `gpt-oss:120b-cloud` (via Custom Ollama Cloud Endpoint)
  * *Configuration*: The code must allow easy switching between Local and Cloud endpoints in `.env`.
* **Embedding Model**:
  * Model: `nomic-embed-text:latest`
  * Runtime: Ollama
* **Clustering Model (Speed Optimized)**:
  * Algorithm: **Mini-Batch K-Means** (via Scikit-learn).
  * Reasoning: Selected for maximum speed on large datasets compared to standard K-Means or DBSCAN.
* **Vector DB**: ChromaDB (Local) or Milvus.
* **Orchestration**: LangGraph (preferred for cyclic debate flows).
* **Data APIs**:
  * **Papers**: OpenAlex API.
  * **Patents**: **EPO OPS (European Patent Office Open Patent Services) API**.

---

## 4. Detailed Workflow & Logic

### Step 1: Query Expansion & Data Collection

* **Input**: User natural language query.
* **Process**:
    1. **LLM Agent**: Uses `deepseek-r1:14b` to convert the query into a Boolean search string.
    2. **API Handler**: Fetches ~1,000 raw documents.
        * **Source A**: OpenAlex (Academic Papers).
        * **Source B**: **EPO OPS API (Patents)**.

### Step 2: High-Speed Data Refining (The Intelligence Engine)

* **Vectorization**:
  * Convert titles/abstracts to vectors using `nomic-embed-text:latest`.
* **Fast Clustering (Mini-Batch K-Means)**:
  * Apply `MiniBatchKMeans` to the vectors to identify sub-topics instantly.
  * **Noise Reduction**: Discard clusters that are semantically distant from the user query vector.
* **Selection**: Keep top N (e.g., 100) documents closest to the cluster centroids.

### Step 3: Knowledge Injection (RAG Setup)

* **Indexing**: Store valid chunks in Vector DB using the `nomic-embed-text:latest` embeddings.
* **Metadata**: Tag documents with Cluster ID and Source Type (Paper/Patent).

### Step 4: Persona Instantiation & Debate

* **System Prompt Injection**:
  * Inject persona constraints (Optimist, Skeptic, etc.) into `deepseek-r1:14b`.
  * Ensure the model strictly adheres to the provided context.

---

## 5. Multi-Agent Persona Library

*Model Configuration: All agents use `deepseek-r1:14b` by default.*

| Persona ID | Name | Role Definition |
| :--- | :--- | :--- |
| **P_OPT** | **Tech Optimist** | Emphasize innovation/scaling. Ignore minor costs. |
| **P_SKEP** | **Market Skeptic** | Focus on ROI, regulation, and failure points. |
| **P_COMP** | **Competitor** | Analyze weaknesses from a rival's perspective. |
| **P_REG** | **Regulator** | Check compliance (legal/safety/standards). |
| **P_MOD** | **Moderator** | Synthesize arguments and drive consensus. |

---

## 6. Debate Simulation Modes (Implementation Logic)

### Mode A: Sequential Verification

* **Flow**: `P_OPT` -> `P_SKEP` -> `P_MOD`.
* **Logic**: Simple linear chain using LangGraph.

### Mode B: Parallel & Converge

* **Flow**:
  * Branch 1: `P_OPT` vs `P_COMP` (Tech Debate)
  * Branch 2: `P_SKEP` vs `P_REG` (Biz Debate)
  * Merge: `P_MOD` summarizes both branches.

### Mode C: Consensus Building (Iterative)

* **Loop**:
    1. `P_OPT` drafts.
    2. Others critique.
    3. If strict critique exists -> `P_OPT` revises -> Loop.
    4. If consensus reached -> Exit.

---

## 7. Development Roadmap (Code Generation Instructions)

### Phase 1: Environment & Models

* Set up `OllamaClient` class to handle `deepseek-r1:14b` and `nomic-embed-text:latest`.
* Implement `MiniBatchKMeans` logic in `DataProcessor` class.

### Phase 2: Data Pipeline

* Implement `OpenAlexFetcher`.
* Implement **`EPOPatentFetcher`** (using EPO OPS API).
* Integrate the Embedding-Clustering-Filtering pipeline.

### Phase 3: Agent Graph

* Build the LangGraph structure using `deepseek-r1:14b`.
* Define the prompt templates for each Persona.

### Phase 4: Runner

* Create a `main.py` CLI or `app.py` (Streamlit) to trigger the workflow.
