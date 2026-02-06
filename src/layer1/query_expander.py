import yaml
import re
from typing import List, Tuple
from langchain_ollama import ChatOllama
import itertools

class QueryExpander:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # User requested specific model for reporting, but for query expansion a fast smart model is good.
        # We'll use the chat model or a specific one if defined.
        self.model_name = self.config['ollama'].get('chat_model', "gpt-oss:120b-cloud")
        self.base_url = self.config['ollama']['base_url']
        
        self.llm = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=0.2 
        )

    def _extract_keywords(self, topic: str) -> List[str]:
        """
        Extracts core technical phrases (not just words) from the topic.
        """
        prompt = f"""
        Extract 2-5 specific technical phrases explicitly present in the research topic.
        Do NOT add any related concepts or terms not found in the input text.
        Do not split compound terms (e.g., keep "Solid State Batteries" as one phrase).
        
        TOPIC: "{topic}"
        
        OUTPUT FORMAT:
        Return ONLY a comma-separated list of phrases without quotes.
        Example: Solid State Batteries, Lithium Metal Anode
        """
        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            # Remove any quotes or brackets if LLM adds them
            content = content.replace('"', '').replace('[', '').replace(']', '')
            keywords = [k.strip() for k in content.split(',')]
            # Simple cleanup
            keywords = [k for k in keywords if k and len(k) > 2]
            return keywords[:5] # Max 5 phrases
        except Exception as e:
            print(f"[QueryExpander] Extraction Error: {e}")
            return [topic]

    def _generate_synonyms(self, topic: str) -> List[str]:
        """
        Generates interchangeable technical synonyms for short topics (<10 words).
        """
        # Quick word count check
        if len(topic.split()) >= 10:
            return []
            
        prompt = f"""
        Generate 2-3 interchangeable technical synonyms/variations for: "{topic}"
        Return ONLY a comma-separated list of phrases.
        Example: "coprocessing of bio feedstock", "co-processing of biomass"
        """
        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            # Cleanup quotes
            content = content.replace('"', '').replace("'", "")
            synonyms = [s.strip() for s in content.split(',')]
            return [s for s in synonyms if s and len(s) > 3][:3]
        except Exception as e:
            print(f"[QueryExpander] Synonym Gen Error: {e}")
            return []

    def _rank_combinations(self, topic: str, combos: List[Tuple[str]], limit: int = 2) -> List[Tuple[str]]:
        """
        Asks LLM which keyword subsets best preserve the original topic's intent.
        """
        # Format options for LLM
        options_text = ""
        for i, combo in enumerate(combos):
            options_text += f"{i}. {', '.join(combo)}\n"
            
        prompt = f"""
        Original Topic: "{topic}"
        
        I have split the topic into keyword subsets to broaden the search.
        Which of the following subsets best RETAINS the core technical intent of the original topic?
        (i.e., Avoid dropping the most critical 'anchor' keyword).
        
        Options:
        {options_text}
        
        Select the top {limit} indices.
        RETURN ONLY the indices separated by commas (e.g., "0, 2").
        """
        try:
            response = self.llm.invoke(prompt)
            indices_str = response.content.strip()
            # Parse indices like "0, 2" or "1"
            indices = [int(x) for x in re.findall(r'\d+', indices_str)]
            
            selected_combos = []
            for idx in indices:
                if 0 <= idx < len(combos):
                    selected_combos.append(combos[idx])
            
            if not selected_combos:
                return combos[:limit]
                
            return selected_combos[:limit]
        except Exception as e:
            print(f"[QueryExpander] Ranking Error: {e}")
            return combos[:limit] # Fallback to first ones

    def generate_search_queries(self, topic: str) -> List[str]:
        """
        Generates a prioritized list of search queries.
        1. Full Exact Query (Phrases AND-ed)
        2. Top N-1 Combinations (if N >= 3)
        """
        # print(f"[QueryExpander] Analyzing topic: '{topic}'...")
        keywords = self._extract_keywords(topic)
        # print(f"[QueryExpander] Extracted Phrases: {keywords}")
        
        queries = []
        
        # Priority 1: Full Combination (Most Precise)
        # Use simple ANDjoin of quotes. 
        # Note: Some APIs might struggle with complex quotes, but standard for exact phrase is quotes.
        full_query = " AND ".join([f'"{k}"' for k in keywords])
        queries.append(full_query)
        
        # Priority 1.5: Synonyms (New)
        # Verify if synonym expansion is applicable
        if len(topic.split()) < 10:
            synonyms = self._generate_synonyms(topic)
            if synonyms:
                # print(f"[QueryExpander] Generated Synonyms: {synonyms}")
                for syn in synonyms:
                    # Treat synonym as a direct query (or should we extract phrases? usually synonym is a full phrase replacement)
                    # We'll use the whole synonym phrase
                    queries.append(f'"{syn}"')
        
        N = len(keywords)
        # If too simple, no need to relax
        if N < 3:
            return queries
        
        # Priority 2: N-1 Combinations
        combos = list(itertools.combinations(keywords, N-1))
        
        if combos:
            # print(f"[QueryExpander] Generating relaxation candidates (Total {len(combos)})...")
            ranked_combos = self._rank_combinations(topic, combos, limit=2)
            # print(f"[QueryExpander] Selected top {len(ranked_combos)} relaxed queries coverage.")
            
            for combo in ranked_combos:
                sub_query = " AND ".join([f'"{k}"' for k in combo])
                queries.append(sub_query)
        
        return queries

    # Legacy method compatibility
    def refine_search_query(self, topic: str) -> Tuple[str, List[str]]:
        # This was the old signature returning (single_query, keywords)
        # We will wrap new logic to return the PRIMARY query and the keywords
        qs = self.generate_search_queries(topic)
        keywords = self._extract_keywords(topic) # Redundant call but simple for legacy
        return qs[0], keywords

# --- Helper for Adaptive Fetching ---
def adaptive_fetch(client_fetch_func, queries: List[str], limit: int, source_name: str) -> List[any]:
    """
    Executes search queries adaptively:
    1. Try precise query first.
    2. If sufficient results, stop.
    3. If not, try fallback (relaxed) queries until limit or end.
    """
    all_results = []
    seen_ids = set()
    
    # print(f"   [{source_name}] Adaptive Fetch with {len(queries)} queries...")
    
    for i, query in enumerate(queries):
        try:
            # print(f"      -> Q{i+1}: {query}")
            results = client_fetch_func(query)
            
            new_count = 0
            for item in results:
                # Deduplicate based on 'id' or 'doi' or url depending on object
                # Clients might return dicts or objects. 
                # OpenAlex: dict with 'id'
                # EPO: dict with 'publication_number' or similar
                # Tavily: dict with 'url'
                if isinstance(item, dict):
                    unique_id = item.get('id') or item.get('url') or item.get('publication_number') or str(item)
                else:
                    unique_id = str(item)
                
                if unique_id not in seen_ids:
                    all_results.append(item)
                    seen_ids.add(unique_id)
                    new_count += 1
            
            # Early Stop Conditions
            # 1. If strict query (first one) returns enough results (e.g. > 50% of limit), we trust it.
            if i == 0 and new_count >= (limit * 0.5):
                # print(f"      -> Precise query found {new_count} items. Stopping early.")
                break
                
            # 2. If we reached total limit
            if len(all_results) >= limit:
                # print(f"      -> Limit {limit} reached. Stopping.")
                break
                
        except Exception as e:
            print(f"      [{source_name}] Error fetching Q{i+1}: {e}")
            continue
            
    return all_results[:limit]

if __name__ == "__main__":
    qe = QueryExpander()
    topic = "Co-processing of bio-based feedstock in FCC units"
    queries = qe.generate_search_queries(topic)
    print(f"Topic: {topic}")
    print("Generated Queries:")
    for q in queries:
        print(f" - {q}")
