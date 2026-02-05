import yaml
import re
from typing import List, Tuple
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

class QueryExpander:
    """
    Expands user natural language queries into optimized boolean search strings
    for OpenAlex, EPO and USPTO APIs using an LLM.
    Adapted from ref_query_refiner.py.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.llm = ChatOllama(
            model=self.config['ollama']['chat_model'],
            base_url=self.config['ollama']['base_url']
        )
        
    def refine_search_query(self, user_input: str) -> Tuple[str, List[str]]:
        """
        Converts user input into keywords and an optimized query string.
        """
        print(f"[QueryExpander] Optimizing search query for: '{user_input}'...")

        template = """
        You are a search query optimizer for an academic and patents database (OpenAlex, EPO and USPTO).
        Convert the USER_INPUT into keyword phrases for academic paper search.

        RULES:
        1. Extract 2-4 core technical concepts (not individual words).
        2. Wrap each concept in double quotes for exact phrase matching.
        3. Separate phrases with spaces (no AND/OR operators).
        4. Remove stop words (I want to, study about, etc.).
        5. Convert to English if the input is in another language.
        6. Output ONLY the query string, no explanation.

        EXAMPLES:
        USER_INPUT: "I want to improve the methodology for analyzing competitive relationships between companies by applying patent network analysis."
        OPTIMIZED QUERY: "patent network" "competitive analysis"

        USER_INPUT: "딥러닝을 활용한 배터리 수명 예측 연구"
        OPTIMIZED QUERY: "deep learning" "battery life prediction"

        USER_INPUT: "{user_input}"

        OPTIMIZED QUERY:
        """
        
        prompt = PromptTemplate(template=template, input_variables=["user_input"])
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            raw_query = chain.invoke({"user_input": user_input}).strip()
            
            # Post-processing to extract quoted keywords
            keywords = re.findall(r'"([^"]*)"', raw_query)
            
            if keywords:
                # Reconstruct query to ensure safety
                optimized_query = " ".join([f'"{k}"' for k in keywords])
            else:
                # Fallback if LLM didn't return quotes
                optimized_query = raw_query.replace('```', '').strip()
                keywords = optimized_query.split() # Rough split if no quotes
            
            print(f"[QueryExpander] Optimized Query: '{optimized_query}'")
            return optimized_query, keywords
            
        except Exception as e:
            print(f"[QueryExpander] Error in query expansion: {e}")
            # Fallback: just use the input as is
            return user_input, user_input.split()

    def select_best_keyword_pair(self, keywords: List[str], user_input: str) -> str:
        """
        Selects the top 2 most relevant keywords if the list is too long,
        to avoid over-filtering in the search API.
        """
        if len(keywords) < 3:
            return " ".join([f'"{k}"' for k in keywords])
            
        keywords_str = ", ".join([f'"{k}"' for k in keywords])
        
        template = """
        You are selecting the 2 most important keywords for academic paper search.

        USER_INTENT: "{user_input}"
        AVAILABLE_KEYWORDS: {keywords_str}

        RULES:
        1. Select exactly 2 keywords that best capture the user's research intent.
        2. Prioritize keywords that are most specific to the research topic.
        3. Output ONLY the 2 selected keywords in double quotes, separated by space.

        SELECTED KEYWORDS:
        """
        
        prompt = PromptTemplate(template=template, input_variables=["user_input", "keywords_str"])
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            raw_response = chain.invoke({"user_input": user_input, "keywords_str": keywords_str}).strip()
            selected = re.findall(r'"([^"]*)"', raw_response)
            
            if len(selected) >= 2:
                return f'"{selected[0]}" "{selected[1]}"'
            elif len(selected) == 1:
                return f'"{selected[0]}"'
            else:
                return f'"{keywords[0]}" "{keywords[1]}"'
                
        except Exception as e:
            print(f"[QueryExpander] Error in keyword selection: {e}")
            return f'"{keywords[0]}" "{keywords[1]}"'

if __name__ == "__main__":
    # Simple test
    qe = QueryExpander()
    query, keys = qe.refine_search_query("Generative AI for Drug Discovery")
    print(f"Result: {query}")
