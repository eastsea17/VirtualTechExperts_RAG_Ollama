import yaml
import operator
import sys
from typing import TypedDict, List, Annotated
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langgraph.graph import StateGraph, END
from src.layer2.vector_store import VectorStoreManager

class DebateState(TypedDict):
    topic: str
    expert_id: str
    messages: Annotated[List[BaseMessage], operator.add]
    current_speaker: str
    turns: int
    mode: str
    status: str

class AdvancedDebateGraph:
    """
    Supports Mode A (Sequential), Mode B (Parallel), Mode C (Consensus).
    """
    
    def __init__(self, config_path: str = "config/config.yaml", personas_path: str = "config/personas.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        with open(personas_path, 'r') as f:
            self.personas = yaml.safe_load(f)['personas']
            
        self.max_turns = self.config.get('debate_rules', {}).get('max_turns_per_persona', 3)
        self.max_tokens = self.config.get('debate_rules', {}).get('max_tokens_per_turn', 300)
            
        self.llm = ChatOllama(
            model=self.config['ollama']['chat_model'],
            base_url=self.config['ollama']['base_url'],
            temperature=0.7
        )
        
        self.retrieve_k = self.config.get('intelligence_engine', {}).get('retrieve_top_k', 3)
        self.vector_manager = VectorStoreManager(config_path)

    def _retrieve_context(self, state: DebateState) -> str:
        expert_id = state['expert_id']
        query = state['topic']
        if state['messages']:
            query = state['messages'][-1].content[-200:]
            
        retriever = self.vector_manager.get_retriever(expert_id, k=self.retrieve_k)
        docs = retriever.invoke(query)
        return "\n\n".join([d.page_content for d in docs])

    def _generate_response(self, state: DebateState, persona_key: str, prompt_addon: str) -> dict:
        print(f"\n--- {self.personas[persona_key]['name']} Speaking (Turn {state['turns']}) ---")
        sys.stdout.flush()
        
        persona_cfg = self.personas[persona_key]
        context = self._retrieve_context(state)
        
        # Enforce conciseness in system prompt
        constraint_prompt = f" IMPORTANT: Keep response under {self.max_tokens} words. Be direct."
        
        system_prompt = persona_cfg['system_prompt'] + \
                        f"\n\nCONTEXT FROM DATABASE:\n{context}\n\nTOPIC: {state['topic']}" + \
                        constraint_prompt
        
        messages = [SystemMessage(content=system_prompt)] + state['messages'] + [HumanMessage(content=prompt_addon)]
        
        # Stream response to terminal for visibility
        full_content = ""
        for chunk in self.llm.stream(messages):
            content = chunk.content
            print(content, end="", flush=True)
            full_content += content
        print("\n") # Newline after stream
        
        response = SystemMessage(content=full_content) # Wrap as message
        # Note: In newer LangChain, we might want AIMessage, but SystemMessage works for graph state typically or AIMessage. 
        # The graph expects BaseMessage. Let's use AIMessage to be semantically correct.
        from langchain_core.messages import AIMessage
        
        # Attach the proper speaker name (e.g., "Tech Optimist") to the message
        speaker_name = self.personas[persona_key]['name']
        response = AIMessage(content=full_content, name=speaker_name)
        
        return {"messages": [response], "current_speaker": persona_key, "turns": state['turns'] + 1}

    # --- NODE DEFINITIONS ---
    def optimist_node(self, state: DebateState):
        prompt = f"Propose/Defend {state['topic']}."
        if state['messages']: prompt = "Respond to the critique."
        return self._generate_response(state, 'P_OPT', prompt)

    def skeptic_node(self, state: DebateState):
        return self._generate_response(state, 'P_SKEP', "Critique the proposal based on costs/risks.")

    def competitor_node(self, state: DebateState):
        return self._generate_response(state, 'P_COMP', "Critique from a competitor's view. What are the weaknesses?")
        
    def regulation_node(self, state: DebateState):
        return self._generate_response(state, 'P_REG', "Analyze legal/compliance risks.")

    def moderator_node(self, state: DebateState):
        # Moderator resets turns usually or ends debate
        return self._generate_response(state, 'P_MOD', "Synthesize the debate so far and provide a conclusion.")

    # --- CONDITIONAL EDGES ---
    def check_turns(self, state: DebateState):
        # Simple limit check
        if state['turns'] >= (self.max_turns * 3): # 3 speakers approx
            return "moderator"
        return "continue"

    # --- GRAPH BUILDERS ---
    def build_mode_a(self):
        # OPT -> SKEP -> MOD
        workflow = StateGraph(DebateState)
        workflow.add_node("optimist", self.optimist_node)
        workflow.add_node("skeptic", self.skeptic_node)
        workflow.add_node("moderator", self.moderator_node)
        
        workflow.set_entry_point("optimist")
        workflow.add_edge("optimist", "skeptic")
        workflow.add_edge("skeptic", "moderator")
        workflow.add_edge("moderator", END)
        return workflow.compile()

    def build_mode_b(self):
        # Parallel: OPT->COMP and SKEP->REG then MOD
        # Simplified linear approximation for Ollama (true parallel needs Async)
        # OPT -> COMP -> SKEP -> REG -> MOD
        workflow = StateGraph(DebateState)
        workflow.add_node("optimist", self.optimist_node)
        workflow.add_node("competitor", self.competitor_node)
        workflow.add_node("skeptic", self.skeptic_node)
        workflow.add_node("regulator", self.regulation_node)
        workflow.add_node("moderator", self.moderator_node)

        workflow.set_entry_point("optimist")
        workflow.add_edge("optimist", "competitor")
        workflow.add_edge("competitor", "skeptic")
        workflow.add_edge("skeptic", "regulator")
        workflow.add_edge("regulator", "moderator")
        workflow.add_edge("moderator", END)
        return workflow.compile()

    def build_mode_c(self):
        # Consensus: OPT <-> SKEP loop
        workflow = StateGraph(DebateState)
        workflow.add_node("optimist", self.optimist_node)
        workflow.add_node("skeptic", self.skeptic_node)
        workflow.add_node("moderator", self.moderator_node)

        workflow.set_entry_point("optimist")
        
        def router(state):
            # Dynamic check against max_turns (approx 3 turns per speaker normally, but let's just check total turns)
            # If standard debate is 2 speakers (Opt/Skep), max_turns * 2 is roughly the limit for full exchanges.
            # Let's say user --turn 5 means 5 rounds of exchange.
            limit = self.max_turns * 2 
            if state['turns'] >= limit: 
                return "moderator"
            return "skeptic" if state['current_speaker'] == 'P_OPT' else "optimist"

        workflow.add_conditional_edges("optimist", router, {"skeptic": "skeptic", "moderator": "moderator"})
        workflow.add_conditional_edges("skeptic", router, {"optimist": "optimist", "moderator": "moderator"})
        workflow.add_edge("moderator", END)
        return workflow.compile()

    def run(self, topic: str, expert_id: str, mode: str = 'a', turns: int = None):
        print(f"Initializing Debate Mode {mode.upper()}...")
        
        # Override config default if turns is provided via CLI
        if turns is not None and turns > 0:
             self.max_turns = turns
             print(f"[DebateGraph] Turn limit set to: {self.max_turns} per persona (approx).")
        
        if mode == 'b':
            app = self.build_mode_b()
        elif mode == 'c':
            app = self.build_mode_c()
        else:
            app = self.build_mode_a()
            
        initial_state = {
            "topic": topic,
            "expert_id": expert_id,
            "messages": [],
            "current_speaker": "System",
            "turns": 0,
            "mode": mode,
            "status": "start"
        }
        
        final_state = app.invoke(initial_state)
        return final_state
