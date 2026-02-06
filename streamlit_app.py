"""
VTE-R&D System - Streamlit Interface
=====================================
A web-based UI for the Virtual Tech Experts & R&D Acceleration System.
Includes: Virtual Debate Simulation + Virtual Tech Expert Hub (Chatbot)
"""

import streamlit as st
import yaml
import os
import sys
import time

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.layer1.query_expander import QueryExpander, adaptive_fetch
from src.layer1.openalex_client import OpenAlexClient
from src.layer1.epo_client import EPOClient
from src.layer1.uspto_client import USPTOClient
from src.layer1.market_client import MarketClient
from src.layer2.vector_store import VectorStoreManager
from src.layer3.debate_graph import AdvancedDebateGraph
from src.layer3.report_generator import ReportGenerator
from langchain_ollama import ChatOllama

# --- Page Configuration ---
st.set_page_config(
    page_title="Virtual Tech Experts System",
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
    .expert-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border-left: 4px solid #667eea;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .chat-user {
        background: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    .chat-assistant {
        background: #f3e5f5;
        border-left: 4px solid #9c27b0;
    }
</style>
""", unsafe_allow_html=True)

# --- Load Default Config ---
@st.cache_data
def load_config():
    with open("config/config.yaml", 'r') as f:
        return yaml.safe_load(f)

config = load_config()

# --- Load Saved Experts ---
@st.cache_data(ttl=60)
def get_saved_experts():
    try:
        vsm = VectorStoreManager()
        experts = vsm.list_experts()
        return experts
    except Exception:
        return []

# --- Initialize Session State ---
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "selected_hub_expert" not in st.session_state:
    st.session_state.selected_hub_expert = None
if "chat_model" not in st.session_state:
    st.session_state.chat_model = config['ollama']['chat_model']
if "custom_personas" not in st.session_state:
    st.session_state.custom_personas = {}
if "show_new_persona_form" not in st.session_state:
    st.session_state.show_new_persona_form = False

# --- Main Header ---
st.markdown('<p class="main-header">🔬 Virtual Tech Experts System</p>', unsafe_allow_html=True)

# --- Navigation ---
# Using Sidebar Navigation instead of Tabs for better state persistence
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["🗣️ Virtual Debate Simulation", "🎓 Virtual Tech Expert Hub"])

# ========================================
# PAGE 1: Virtual Debate Simulation
# ========================================
if page == "🗣️ Virtual Debate Simulation":
    st.markdown('<p class="sub-header">AI-Powered Multi-Persona Technical Debate Platform</p>', unsafe_allow_html=True)
    
    # --- Sidebar for Debate Tab ---
    with st.sidebar:
        st.markdown("---")
        st.markdown("## ⚙️ Debate Configuration")
        
        # Note: Saved Experts section removed - always create new expert
        use_existing_expert = False
        selected_expert_id = None
        selected_expert_topic = None
        
        st.markdown("---")
        st.markdown("### 📊 Data Acquisition")
        
        openalex_limit = st.slider("OpenAlex Papers", 10, 500, config['data_acquisition']['openalex']['fetch_limit'], 10)
        uspto_limit = st.slider("USPTO Patents", 10, 100, config['data_acquisition']['uspto']['fetch_limit'], 10)
        epo_limit = st.slider("EPO Patents", 10, 100, config['data_acquisition']['epo']['fetch_limit'], 10)
        tavily_limit = st.slider("Tavily News", 1, 20, config['data_acquisition']['tavily']['fetch_limit'], 1)
        
        st.markdown("---")
        st.markdown("### 🗣️ Debate Settings")
        
        debate_mode = st.selectbox(
            "Debate Mode",
            options=['a', 'b', 'c'],
            format_func=lambda x: {'a': 'A: Sequential', 'b': 'B: Round Robin', 'c': 'C: Consensus'}[x],
            index=['a', 'b', 'c'].index(config['defaults']['mode'])
        )
        
        max_turns = st.slider("Max Turns per Persona", 1, 10, config['debate_rules']['max_turns_per_persona'])
        
        st.markdown("---")
        st.markdown("### 🤖 Model")
        debate_model_name = st.text_input("Debate Model", config['ollama'].get('debate_model', "deepseek-v3.1:671b-cloud"))

    # --- Topic Input ---
    col1, col2 = st.columns([3, 1])
    with col1:
        topic = st.text_input(
            "🎯 Enter Your Research Topic",
            value=config['defaults']['topic'],
            placeholder="e.g., Solid State Batteries, Quantum Computing, etc."
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_button = st.button("🚀 Run Debate", type="primary", use_container_width=True)

    # --- Run Debate Pipeline ---
    if run_button:
        if use_existing_expert:
            effective_topic = selected_expert_topic
            effective_expert_id = selected_expert_id
        else:
            effective_topic = topic.strip()
            effective_expert_id = None
        
        if not effective_topic:
            st.error("❌ Please enter a topic or select a saved expert.")
        else:
            st.markdown("---")
            st.markdown("### 📡 Analysis Progress")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                vsm = VectorStoreManager()
                
                if use_existing_expert:
                    st.success(f"🔄 Using saved expert: **{effective_expert_id}**")
                    status_text.markdown("**⏩ Skipping data acquisition...**")
                    progress_bar.progress(70)
                    expert_id = effective_expert_id
                    data_stats = {"Source": "Cache", "Expert ID": expert_id}
                else:
                    status_text.markdown("**🔍 Fetching data...**")
                    qe = QueryExpander()
                    queries = qe.generate_search_queries(effective_topic)
                    keywords = qe._extract_keywords(effective_topic)
                    progress_bar.progress(10)
                    
                    oa_client = OpenAlexClient()
                    papers = adaptive_fetch(oa_client.fetch_papers, queries, limit=20, source_name="OpenAlex")
                    progress_bar.progress(25)
                    
                    epo_client = EPOClient()
                    patents_epo = adaptive_fetch(epo_client.fetch_patents, queries, limit=20, source_name="EPO")
                    progress_bar.progress(40)
                    
                    uspto_client = USPTOClient()
                    patents_uspto = uspto_client.fetch_patents(keywords)
                    progress_bar.progress(55)
                    
                    market_client = MarketClient()
                    market_news = adaptive_fetch(market_client.fetch_market_news, queries, limit=10, source_name="Tavily")
                    progress_bar.progress(65)
                    
                    combined_data = papers + patents_epo + patents_uspto + market_news
                    
                    if not combined_data:
                        st.error("❌ No data found.")
                        st.stop()
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("📄 Papers", len(papers))
                    col2.metric("📜 EPO", len(patents_epo))
                    col3.metric("🇺🇸 USPTO", len(patents_uspto))
                    col4.metric("📰 News", len(market_news))
                    
                    status_text.markdown("**🧠 Building knowledge base...**")
                    expert_id = vsm.generate_next_expert_id()
                    vsm.add_expert_knowledge(combined_data, expert_id, effective_topic)
                    progress_bar.progress(75)
                    st.info(f"📌 Created: **{expert_id}**")
                    
                    data_stats = {
                        "OpenAlex Papers": len(papers),
                        "EPO Patents": len(patents_epo),
                        "USPTO Patents": len(patents_uspto),
                        "Tavily News": len(market_news),
                        "Total": len(combined_data)
                    }
                
                # Debate
                status_text.markdown(f"**🗣️ Running debate (Mode {debate_mode.upper()})...**")
                debate_container = st.container()
                with debate_container:
                    st.markdown("#### 💬 Debate Transcript")
                
                debate = AdvancedDebateGraph(model_name=debate_model_name)
                final_state = debate.run(effective_topic, expert_id, debate_mode, turns=max_turns)
                progress_bar.progress(90)
                
                # Display transcript
                messages = final_state.get('messages', [])
                with debate_container:
                    for msg in messages:
                        speaker = msg.name if hasattr(msg, 'name') and msg.name else "Moderator"
                        if "Optimist" in speaker:
                            icon, color = "🚀", "#27ae60"
                        elif "Skeptic" in speaker:
                            icon, color = "🛡️", "#c0392b"
                        elif "Competitor" in speaker:
                            icon, color = "⚔️", "#d35400"
                        elif "Regulator" in speaker:
                            icon, color = "⚖️", "#2980b9"
                        else:
                            icon, color = "🎯", "#8e44ad"
                        
                        with st.expander(f"{icon} {speaker}", expanded=True):
                            st.markdown(msg.content)
                
                # Report
                status_text.markdown("**📊 Generating report...**")
                rg = ReportGenerator()
                report_path = rg.generate_report(final_state, data_stats=data_stats)
                progress_bar.progress(100)
                
                status_text.markdown("**✅ Complete!**")
                if report_path:
                    st.success("🎉 Report generated!")
                    with open(report_path, 'r') as f:
                        report_html = f.read()
                    st.download_button("⬇️ Download Report", report_html, os.path.basename(report_path), "text/html")
                    st.components.v1.html(report_html, height=600, scrolling=True)
                    
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                st.exception(e)

# ========================================
# PAGE 2: Virtual Tech Expert Hub (Chatbot)
# ========================================
elif page == "🎓 Virtual Tech Expert Hub":
    st.markdown('<p class="sub-header">Interactive Chat with Your Virtual Tech Experts</p>', unsafe_allow_html=True)
    
    # Layout: Experts selection (left) + Persona selection (right) on top row
    col_experts, col_persona = st.columns([2, 1])
    
    saved_experts = get_saved_experts()
    
    with col_experts:
        st.markdown("### 👨‍🔬 Select an Expert")
        
        if not saved_experts:
            st.warning("No experts saved yet. Create one in the Debate tab first!")
        else:
            for exp in saved_experts:
                eid = exp['expert_id']
                topic = exp['topic']
                doc_count = exp['doc_count']
                
                # Professional expert icon based on document count
                if doc_count > 100:
                    expert_icon = "👨‍🎓"  # Professor
                elif doc_count > 50:
                    expert_icon = "👩‍🔬"  # Scientist
                elif doc_count > 20:
                    expert_icon = "🧑‍💼"  # Business professional
                else:
                    expert_icon = "👨‍💻"  # Tech professional
                
                with st.container():
                    st.markdown(f"""
                    <div class="expert-card">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <span style="font-size:2rem;">{expert_icon}</span>
                            <div>
                                <small style="color:#888;">🏷️ {eid}</small><br>
                                <strong style="font-size:1.1rem;">{topic[:50]}{'...' if len(topic) > 50 else ''}</strong><br>
                                <span style="color:#667eea; font-size:0.85rem;">📄 {exp.get('articles',0)} Papers | 📜 {exp.get('patents',0)} Patents | 📰 {exp.get('news',0)} News</span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    def set_expert(expert):
                        st.session_state.selected_hub_expert = expert
                        st.session_state.chat_messages = []
                    
                    st.button(f"💬 Chat with {eid}", key=f"chat_{eid}", use_container_width=True, on_click=set_expert, args=(exp,))
    
    with col_persona:
        st.markdown("### 🎭 Select Persona")
        
        # Default personas
        default_personas = ["Balanced Expert", "Optimist (Opportunity-focused)", "Skeptic (Risk-focused)", 
                     "Competitor Analyst", "Regulator (Compliance-focused)"]
        
        # Combine with custom personas
        custom_persona_names = list(st.session_state.custom_personas.keys())
        all_personas = default_personas + custom_persona_names
        
        persona = st.selectbox(
            "Persona Style",
            options=all_personas,
            help="How should the expert respond?"
        )
        
        # Persona description with icon
        persona_icons = {
            "Balanced Expert": ("⚖️", "Provides objective, balanced analysis"),
            "Optimist (Opportunity-focused)": ("🚀", "Focuses on opportunities and potential"),
            "Skeptic (Risk-focused)": ("🛡️", "Focuses on risks and limitations"),
            "Competitor Analyst": ("⚔️", "Analyzes market dynamics and competition"),
            "Regulator (Compliance-focused)": ("📋", "Focuses on compliance and legal aspects")
        }
        
        # Add custom persona icons
        for name in custom_persona_names:
            persona_icons[name] = ("✨", st.session_state.custom_personas[name][:50] + "...")
        
        icon, desc = persona_icons.get(persona, ("🎭", "Expert persona"))
        st.markdown(f"<p style='color:#667eea; font-size:1.5rem;'>{icon}</p><small style='color:#888;'>{desc}</small>", unsafe_allow_html=True)
        
        # New Persona Button
        st.markdown("---")
        if st.button("➕ New Persona", use_container_width=True):
            st.session_state.show_new_persona_form = not st.session_state.show_new_persona_form
        
        # New Persona Form
        if st.session_state.show_new_persona_form:
            st.markdown("#### 🆕 Create Custom Persona")
            new_persona_name = st.text_input("Persona Name", placeholder="e.g., Investor Analyst")
            new_persona_prompt = st.text_area(
                "Persona Prompt", 
                placeholder="e.g., You are a venture capital investor. Focus on market potential, ROI, and scalability.",
                height=100
            )
            
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("💾 Save", use_container_width=True):
                    if new_persona_name and new_persona_prompt:
                        st.session_state.custom_personas[new_persona_name] = new_persona_prompt
                        st.session_state.show_new_persona_form = False
                        st.success(f"✅ '{new_persona_name}' persona created!")
                        st.rerun()
                    else:
                        st.error("Please fill both name and prompt.")
            with col_cancel:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.show_new_persona_form = False
                    st.rerun()
    
    st.markdown("---")
    
    # Chat Interface below (full width)
    
    st.markdown("### 💬 Chat Interface")
    
    if st.session_state.selected_hub_expert:
        exp = st.session_state.selected_hub_expert
        
        # Selected expert icon
        doc_count = exp.get('doc_count', 0)
        if doc_count > 100:
            current_icon = "👨‍🎓"
        elif doc_count > 50:
            current_icon = "👩‍🔬"
        elif doc_count > 20:
            current_icon = "🧑‍💼"
        else:
            current_icon = "👨‍💻"
        
        st.info(f"{current_icon} **Chatting with:** {exp['expert_id']} | **Topic:** {exp['topic']}")
        
        # Chat history display
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.chat_messages:
                if msg["role"] == "user":
                    st.markdown(f'<div class="chat-message chat-user">🧑 <strong>You:</strong> {msg["content"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="chat-message chat-assistant">{current_icon} <strong>Expert:</strong> {msg["content"]}</div>', unsafe_allow_html=True)
        
        # Chat input
        user_input = st.chat_input("Ask the expert anything...")
        
        if user_input:
            # Add user message
            st.session_state.chat_messages.append({"role": "user", "content": user_input})
            
            # Display user message immediately
            with chat_container:
                st.markdown(f'<div class="chat-message chat-user">🧑 <strong>You:</strong> {user_input}</div>', unsafe_allow_html=True)
            
            # Generate response using RAG
            with st.spinner("🤔 Expert is thinking..."):
                try:
                    vsm = VectorStoreManager()
                    retriever = vsm.get_retriever(exp['expert_id'])
                    
                    # Retrieve relevant context (use invoke for newer LangChain)
                    docs = retriever.invoke(user_input)
                    context = "\n\n".join([doc.page_content for doc in docs[:5]])
                    
                    # Default persona prompts
                    persona_prompts = {
                        "Balanced Expert": "You are a balanced technical expert. Provide objective analysis.",
                        "Optimist (Opportunity-focused)": "You are an optimistic innovation advocate. Focus on opportunities and potential.",
                        "Skeptic (Risk-focused)": "You are a critical skeptic. Focus on risks, challenges, and limitations.",
                        "Competitor Analyst": "You are a competitive intelligence analyst. Focus on market dynamics and competition.",
                        "Regulator (Compliance-focused)": "You are a regulatory expert. Focus on compliance, standards, and legal aspects."
                    }
                    
                    # Add custom personas
                    persona_prompts.update(st.session_state.custom_personas)
                    
                    prompt = f"""
{persona_prompts.get(persona, persona_prompts["Balanced Expert"])}

You are engaging in a conversation about the research topic: "{exp['topic']}".

### Context from Knowledge Base:
{context if context.strip() else "No specific documents found for this query."}

### User Input:
{user_input}

### Instructions:
1. **Greetings**: If the user says "Hello", "Hi", or similar greetings, respond naturally and introduce yourself as an expert on this topic. Do not try to force the context into a greeting.
2. **Technical Questions**: Use the "Context from Knowledge Base" to answer accurately. 
3. **Missing Info**: If the context doesn't contain the answer, use your general knowledge but clarify that it's based on general principles, not the specific database documents.
4. **Style**: Maintain the persona defined above throughout the response. Be professional yet conversational.
"""
                    
                    llm = ChatOllama(model=st.session_state.chat_model)
                    response = llm.invoke(prompt)
                    
                    # Add assistant response
                    st.session_state.chat_messages.append({"role": "assistant", "content": response.content})
                    
                    # Display assistant response immediately
                    with chat_container:
                        st.markdown(f'<div class="chat-message chat-assistant">{current_icon} <strong>Expert:</strong> {response.content}</div>', unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        # Clear chat button
        def clear_chat():
            st.session_state.chat_messages = []
        
        st.button("🗑️ Clear Chat", on_click=clear_chat)
    else:
        st.info("👆 Select an expert from above to start chatting!")
    
    # Sidebar for Virtual Tech Expert Hub - Model Selection
    with st.sidebar:
        st.markdown("---")
        st.markdown("## 🤖 Chat Model")
        
        # Model options
        model_options = [
            "gpt-oss:120b-cloud",
            "gpt-oss:20b",
            "deepseek-v3.1:671b-cloud",
            "deepseek-r1:8b",
            "deepseek-r1:14b",
            "qwen3:8b",
            "llama3:8b" # Added llama3:8b to default options
        ]
        
        # Ensure current model is in the list
        if st.session_state.chat_model not in model_options:
            model_options.insert(0, st.session_state.chat_model)
        
        selected_model = st.selectbox(
            "Select Model",
            options=model_options,
            index=model_options.index(st.session_state.chat_model),
            help="Choose the LLM model for chatbot responses"
        )
        
        if selected_model != st.session_state.chat_model:
            st.session_state.chat_model = selected_model
            st.success(f"✅ Model changed to: {selected_model}")
        
        st.caption(f"📍 Current: `{st.session_state.chat_model}`")
        
        # Custom model input
        custom_model = st.text_input("Or enter custom model name:", placeholder="e.g., llama3:8b")
        if custom_model and st.button("Apply Custom Model"):
            st.session_state.chat_model = custom_model
            st.success(f"✅ Model changed to: {custom_model}")
            st.rerun()

# --- Footer ---
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #6c757d; font-size: 0.9rem;'>
        VTE-R&D System V2.8 | Powered by LangGraph, ChromaDB, and Ollama
    </div>
    """,
    unsafe_allow_html=True
)
