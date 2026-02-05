"""
VTE-R&D System - Streamlit Interface
=====================================
A web-based UI for the Virtual Tech Experts & R&D Acceleration System.
"""

import streamlit as st
import yaml
import os
import sys
import time

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.layer1.query_expander import QueryExpander
from src.layer1.openalex_client import OpenAlexClient
from src.layer1.epo_client import EPOClient
from src.layer1.uspto_client import USPTOClient
from src.layer1.market_client import MarketClient
from src.layer2.vector_store import VectorStoreManager
from src.layer3.debate_graph import AdvancedDebateGraph
from src.report_generator import ReportGenerator

# --- Page Configuration ---
st.set_page_config(
    page_title="Virtual Tech Experts Debate System",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        color: #6c757d;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    .status-box {
        padding: 1rem;
        border-radius: 10px;
        background: #f8f9fa;
        border-left: 4px solid #667eea;
        margin: 1rem 0;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        font-size: 1.1rem;
        font-weight: 600;
        border-radius: 10px;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- Load Default Config ---
@st.cache_data
def load_config():
    with open("config/config.yaml", 'r') as f:
        return yaml.safe_load(f)

config = load_config()

# --- Sidebar: Configuration Controls ---
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    
    st.markdown("---")
    st.markdown("### 📊 Data Acquisition")
    
    openalex_limit = st.slider(
        "OpenAlex Papers (Limit)",
        min_value=10, max_value=500, 
        value=config['data_acquisition']['openalex']['fetch_limit'],
        step=10,
        help="Number of papers to fetch from OpenAlex"
    )
    
    uspto_limit = st.slider(
        "USPTO Patents (Limit)",
        min_value=10, max_value=100,
        value=config['data_acquisition']['uspto']['fetch_limit'],
        step=10,
        help="Number of patents to fetch from USPTO"
    )
    
    epo_limit = st.slider(
        "EPO Patents (Limit)",
        min_value=10, max_value=100,
        value=config['data_acquisition']['epo']['fetch_limit'],
        step=10,
        help="Number of patents to fetch from EPO"
    )
    
    tavily_limit = st.slider(
        "Tavily News (Limit)",
        min_value=1, max_value=20,
        value=config['data_acquisition']['tavily']['fetch_limit'],
        step=1,
        help="Number of news articles to fetch from Tavily"
    )
    
    st.markdown("---")
    st.markdown("### 🗣️ Debate Settings")
    
    debate_mode = st.selectbox(
        "Debate Mode",
        options=['a', 'b', 'c'],
        format_func=lambda x: {'a': 'A: Sequential Loop', 'b': 'B: Round Robin', 'c': 'C: Consensus'}[x],
        index=['a', 'b', 'c'].index(config['defaults']['mode']),
        help="Select debate structure"
    )
    
    max_turns = st.slider(
        "Max Turns per Persona",
        min_value=1, max_value=10,
        value=config['debate_rules']['max_turns_per_persona'],
        step=1,
        help="Number of turns each persona gets"
    )
    
    max_tokens = st.slider(
        "Max Tokens per Turn",
        min_value=100, max_value=1000,
        value=config['debate_rules']['max_tokens_per_turn'],
        step=50,
        help="Maximum response length per turn"
    )
    
    st.markdown("---")
    st.markdown("### 🧠 Intelligence Engine")
    
    retrieve_top_k = st.slider(
        "Context Retrieval Depth (k)",
        min_value=1, max_value=20,
        value=config['intelligence_engine']['retrieve_top_k'],
        step=1,
        help="Number of document chunks to retrieve for context"
    )
    
    st.markdown("---")
    st.markdown("### 🤖 Model Settings")
    
    chat_model = st.text_input(
        "Chat Model",
        value=config['ollama']['chat_model'],
        help="Ollama model name for debate"
    )
    
    embedding_model = st.text_input(
        "Embedding Model",
        value=config['ollama']['embedding_model'],
        help="Ollama model name for embeddings"
    )

# --- Main Content ---
st.markdown('<p class="main-header">🔬 Virtual Tech Experts Debate System</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">AI-Powered Technical Research & Strategic Debate Platform</p>', unsafe_allow_html=True)

# --- Topic Input ---
col1, col2 = st.columns([3, 1])
with col1:
    topic = st.text_input(
        "🎯 Enter Your Research Topic",
        value=config['defaults']['topic'],
        placeholder="e.g., Solid State Batteries, Quantum Computing, etc.",
        help="The technology domain you want to research and analyze"
    )

with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    run_button = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

# --- Status Container ---
status_container = st.container()
progress_bar = st.empty()
results_container = st.container()

# --- Run Pipeline ---
if run_button:
    if not topic.strip():
        st.error("❌ Please enter a research topic.")
    else:
        with status_container:
            st.markdown("---")
            st.markdown("### 📡 Analysis Progress")
            
            # Initialize progress
            progress = 0
            progress_bar = st.progress(progress)
            status_text = st.empty()
            
            try:
                # --- Layer 1: Data Acquisition ---
                status_text.markdown("**🔍 Layer 1: Data Acquisition...**")
                
                # Query Expansion
                status_text.markdown("&nbsp;&nbsp;&nbsp;&nbsp;↳ Expanding search queries...")
                qe = QueryExpander()
                optimized_query, keywords = qe.refine_search_query(topic)
                progress_bar.progress(10)
                
                # OpenAlex
                status_text.markdown("&nbsp;&nbsp;&nbsp;&nbsp;↳ Fetching papers from OpenAlex...")
                oa_client = OpenAlexClient()
                papers = oa_client.fetch_papers(optimized_query)
                progress_bar.progress(25)
                
                # EPO
                status_text.markdown("&nbsp;&nbsp;&nbsp;&nbsp;↳ Fetching patents from EPO...")
                epo_client = EPOClient()
                patents_epo = epo_client.fetch_patents(keywords[0] if keywords else topic)
                progress_bar.progress(40)
                
                # USPTO
                status_text.markdown("&nbsp;&nbsp;&nbsp;&nbsp;↳ Fetching patents from USPTO...")
                uspto_client = USPTOClient()
                patents_uspto = uspto_client.fetch_patents(keywords)
                progress_bar.progress(55)
                
                # Tavily
                status_text.markdown("&nbsp;&nbsp;&nbsp;&nbsp;↳ Fetching market news from Tavily...")
                market_client = MarketClient()
                market_news = market_client.fetch_market_news(topic)
                progress_bar.progress(65)
                
                combined_data = papers + patents_epo + patents_uspto + market_news
                
                if not combined_data:
                    st.error("❌ No data found for this topic. Try a different query.")
                    st.stop()
                
                # Show data stats
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📄 Papers", len(papers))
                with col2:
                    st.metric("📜 EPO Patents", len(patents_epo))
                with col3:
                    st.metric("🇺🇸 USPTO Patents", len(patents_uspto))
                with col4:
                    st.metric("📰 News", len(market_news))
                
                # --- Layer 2: Vector Store ---
                status_text.markdown("**🧠 Layer 2: Building Knowledge Base...**")
                vsm = VectorStoreManager()
                expert_id = vsm.generate_next_expert_id()
                vsm.add_expert_knowledge(combined_data, expert_id, topic)
                progress_bar.progress(75)
                st.info(f"📌 Created Expert: **{expert_id}**")
                
                # --- Layer 3: Debate ---
                status_text.markdown(f"**🗣️ Layer 3: Running Debate (Mode {debate_mode.upper()})...**")
                
                # Create a placeholder for live debate messages
                debate_container = st.container()
                with debate_container:
                    st.markdown("#### 💬 Live Debate Transcript")
                    debate_placeholder = st.empty()
                
                debate = AdvancedDebateGraph()
                final_state = debate.run(topic, expert_id, debate_mode, turns=max_turns)
                progress_bar.progress(90)
                
                # --- Display Debate Transcript ---
                messages = final_state.get('messages', [])
                
                with debate_container:
                    st.markdown("---")
                    st.markdown("### 🎭 Debate Transcript")
                    
                    for msg in messages:
                        # Determine speaker name
                        if hasattr(msg, 'name') and msg.name:
                            speaker = msg.name
                        else:
                            speaker = "System / Moderator"
                        
                        # Assign colors and icons based on persona
                        if "Optimist" in speaker:
                            color = "#27ae60"  # Green
                            icon = "🚀"
                            bg_color = "#e8f5e9"
                        elif "Skeptic" in speaker:
                            color = "#c0392b"  # Red
                            icon = "🛡️"
                            bg_color = "#ffebee"
                        elif "Competitor" in speaker:
                            color = "#d35400"  # Orange
                            icon = "⚔️"
                            bg_color = "#fff3e0"
                        elif "Regulator" in speaker:
                            color = "#2980b9"  # Blue
                            icon = "⚖️"
                            bg_color = "#e3f2fd"
                        elif "Maestro" in speaker or "Mod" in speaker:
                            color = "#8e44ad"  # Purple
                            icon = "🎯"
                            bg_color = "#f3e5f5"
                        else:
                            color = "#34495e"
                            icon = "👤"
                            bg_color = "#f5f5f5"
                        
                        # Display each message as an expander
                        with st.expander(f"{icon} **{speaker}**", expanded=True):
                            st.markdown(
                                f"""
                                <div style="
                                    background: {bg_color};
                                    padding: 15px;
                                    border-left: 4px solid {color};
                                    border-radius: 8px;
                                    margin: 5px 0;
                                ">
                                    {msg.content}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                
                # --- Layer 4: Reporting ---
                status_text.markdown("**📊 Layer 4: Generating Report...**")
                data_stats = {
                    "OpenAlex Papers": len(papers),
                    "EPO Patents": len(patents_epo),
                    "USPTO Patents": len(patents_uspto),
                    "Tavily News": len(market_news),
                    "Total Documents": len(combined_data)
                }
                
                rg = ReportGenerator()
                report_path = rg.generate_report(final_state, data_stats=data_stats)
                progress_bar.progress(100)
                
                # --- Success ---
                status_text.markdown("**✅ Analysis Complete!**")
                
                if report_path:
                    st.success(f"🎉 Report generated successfully!")
                    
                    # Display report
                    with open(report_path, 'r') as f:
                        report_html = f.read()
                    
                    st.markdown("---")
                    st.markdown("### 📄 Generated Report")
                    
                    # Download button
                    st.download_button(
                        label="⬇️ Download HTML Report",
                        data=report_html,
                        file_name=os.path.basename(report_path),
                        mime="text/html"
                    )
                    
                    # Preview in iframe
                    st.components.v1.html(report_html, height=800, scrolling=True)
                    
            except Exception as e:
                st.error(f"❌ Error during analysis: {str(e)}")
                st.exception(e)

# --- Footer ---
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #6c757d; font-size: 0.9rem;'>
        VTE-R&D System V2.7 | Powered by LangGraph, ChromaDB, and Ollama
    </div>
    """,
    unsafe_allow_html=True
)
