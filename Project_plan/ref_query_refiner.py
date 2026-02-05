from typing import List, Dict, Any
from agents.base_agent import BaseAgent
from core.types import IdeaObject, IdeaSnapshot, IdeaContent
from utils.parser import extract_json
import requests
import re
import uuid

# Concise example JSON structure for one-shot learning
EXAMPLE_JSON_STRUCTURE = """
{
  "topics": [
    {
      "title": "Graph Neural Network for Patent Claim Analysis",
      "background": "Current patent analysis is manual and slow.",
      "necessity": "Existing NLP fails to capture claim hierarchy.",
      "methodology": "Use GNN + RAG: (1) Build claim graph, (2) Embed with PatentBERT, (3) Apply GAT for reasoning.",
      "table_of_contents": ["1. Introduction", "2. Related Work", "3. Method", "4. Experiments", "5. Conclusion"],
      "expected_effects": "60% faster analysis, 85% accuracy on prior art detection.",
      "description": "Novel GNN+RAG approach for patent analysis."
    }
  ]
}
"""

class GeneratorAgent(BaseAgent):
    """
    Generator Agent that fetches papers from OpenAlex API and generates research ideas
    based on the latest, most relevant papers.
    """
    
    def __init__(self, model_manager, role: str):
        super().__init__(model_manager, role)
        self.openalex_url = "https://api.openalex.org/works"
        self.user_agent_email = "research-agent@example.com"
        
        # Read OpenAlex settings from config
        openalex_config = model_manager.config.get("openalex", {})
        
        if "fetch_limit" not in openalex_config or "top_k_papers" not in openalex_config:
            raise ValueError("Missing 'fetch_limit' or 'top_k_papers' in config.yaml under 'openalex' section.")
            
        self.fetch_limit = openalex_config["fetch_limit"]
        self.top_k_papers = openalex_config["top_k_papers"]

    def refine_search_query(self, user_input: str) -> str:
        """
        사용자의 구체적인 문장을 OpenAlex 검색에 최적화된 검색식으로 변환합니다.
        핵심 키워드를 인용부호로 감싸서 정확한 구문 매칭을 수행합니다.
        """
        print(f"[{self.role}] Optimizing search query for: '{user_input}'...")
        
        prompt = f"""
You are a search query optimizer for an academic database (OpenAlex).
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

OPTIMIZED QUERY:"""
        
        raw_query = self.generate(prompt).strip()
        
        # 안전장치: 정규표현식으로 "키워드" 형태만 추출하여 재조립
        # LLM이 "Here is the optimized query: ..." 같은 사족을 붙일 경우 대비
        keywords = re.findall(r'"([^"]*)"', raw_query)
        if keywords:
            optimized_query = " ".join([f'"{k}"' for k in keywords])
        else:
            optimized_query = raw_query.replace('```', '').strip()
        
        print(f"[{self.role}] Optimized Query: '{optimized_query}'")
        return optimized_query, keywords  # Return both query and keywords list

    def select_best_keyword_pair(self, keywords: List[str], user_input: str) -> str:
        """
        3개 이상의 키워드 중에서 사용자 의도에 가장 부합하는 2개의 키워드를 선택합니다.
        LLM을 사용하여 문맥과 의도를 분석합니다.
        """
        if len(keywords) < 3:
            return " ".join([f'"{k}"' for k in keywords])
        
        keywords_str = ", ".join([f'"{k}"' for k in keywords])
        
        prompt = f"""
You are selecting the 2 most important keywords for academic paper search.

USER_INTENT: "{user_input}"
AVAILABLE_KEYWORDS: {keywords_str}

RULES:
1. Select exactly 2 keywords that best capture the user's research intent.
2. Prioritize keywords that are most specific to the research topic.
3. Output ONLY the 2 selected keywords in double quotes, separated by space.

SELECTED KEYWORDS:"""
        
        raw_response = self.generate(prompt).strip()
        
        # Extract quoted keywords from response
        selected = re.findall(r'"([^"]*)"', raw_response)
        if len(selected) >= 2:
            return f'"{selected[0]}" "{selected[1]}"'
        elif len(selected) == 1:
            return f'"{selected[0]}"'
        else:
            # Fallback: use first 2 keywords
            return f'"{keywords[0]}" "{keywords[1]}"'
    
    def fetch_papers_from_openalex(self, keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch papers from OpenAlex API.
        Returns list of papers with title, abstract, year, authors.
        """
        print(f"[{self.role}] Fetching papers from OpenAlex for: '{keyword}'...")
        
        params = {
            "search": keyword,
            "per-page": min(limit, 200),  # OpenAlex max is 200 per page
            "filter": "has_abstract:true,from_publication_date:2020-01-01"
        }
        headers = {
            "User-Agent": f"mailto:{self.user_agent_email}"
        }
        
        try:
            response = requests.get(self.openalex_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            
            papers = []
            for result in results:
                title = result.get("title")
                abstract_inverted = result.get("abstract_inverted_index")
                abstract = self._reconstruct_abstract(abstract_inverted)
                
                # Extract authors
                authorships = result.get("authorships", [])
                authors = []
                for authorship in authorships[:5]:  # Limit to 5 authors
                    author = authorship.get("author", {})
                    author_name = author.get("display_name")
                    if author_name:
                        authors.append(author_name)
                
                if title and abstract:
                    papers.append({
                        "title": title,
                        "abstract": abstract,
                        "year": result.get("publication_year"),
                        "authors": authors,
                        "url": result.get("id"),
                        "cited_by_count": result.get("cited_by_count", 0)
                    })
            
            print(f"[{self.role}] Found {len(papers)} papers from OpenAlex.")
            return papers
            
        except Exception as e:
            print(f"[{self.role}] Error fetching from OpenAlex: {e}")
            return []
    
    def _reconstruct_abstract(self, inverted_index: Dict) -> str:
        """Reconstruct abstract from OpenAlex inverted index format."""
        if not inverted_index:
            return ""
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort()
        return " ".join([word for _, word in word_positions])
    
    def _select_top_papers(self, papers: List[Dict], keyword: str, top_k: int = 10) -> List[Dict]:
        """
        Select top-k papers from relevance-sorted results.
        Since OpenAlex already returns results sorted by relevance,
        we simply slice the first top_k papers.
        """
        if not papers:
            return []
        
        return papers[:top_k]
    
    def _format_papers_for_prompt(self, papers: List[Dict]) -> str:
        """Format papers into a readable context for the LLM."""
        if not papers:
            return "No papers found."
        
        formatted = []
        for i, paper in enumerate(papers, 1):
            year = paper.get('year', 'N/A')
            title = paper.get('title', 'Unknown')
            authors = ', '.join(paper.get('authors', [])[:3])  # First 3 authors
            abstract = paper.get('abstract', '')[:1000]  # Truncated to 200 chars
            citations = paper.get('cited_by_count', 0)
            
            formatted.append(f"""
                            **Paper {i}** [{year}] (Cited: {citations})
                            - **Title:** {title}
                            - **Authors:** {authors}
                            - **Abstract:** {abstract}...
                            """)
        
        return "\n".join(formatted)
    
    def create_drafts(self, keyword: str, context: str = "", n: int = 3) -> List[IdeaObject]:
        """
        Generate research topic drafts by:
        1. Fetching papers from OpenAlex API
        2. Selecting most relevant recent papers
        3. Using Chain of Thought reasoning with Critic -> Solution framework
        """
        
        # Step 1: Fetch papers from OpenAlex
        search_query, keywords = self.refine_search_query(keyword)
        papers = self.fetch_papers_from_openalex(search_query, limit=self.fetch_limit)
        
        # Step 1.5: Fallback - expand paper pool if too few results and 3+ keywords
        min_paper_threshold = 10
        if len(papers) < min_paper_threshold and len(keywords) >= 3:
            print(f"[{self.role}] Found only {len(papers)} papers. Attempting keyword combination fallback...")
            
            # Select best 2 keywords based on user intent
            reduced_query = self.select_best_keyword_pair(keywords, keyword)
            print(f"[{self.role}] Fallback Query: '{reduced_query}'")
            
            # Fetch additional papers with reduced query
            additional_papers = self.fetch_papers_from_openalex(reduced_query, limit=self.fetch_limit)
            
            # Merge and deduplicate by title
            existing_titles = {p['title'].lower() for p in papers}
            for paper in additional_papers:
                if paper['title'].lower() not in existing_titles:
                    papers.append(paper)
                    existing_titles.add(paper['title'].lower())
            
            print(f"[{self.role}] After fallback: {len(papers)} unique papers in pool.")
        
        # Step 2: Select top relevant papers
        top_papers = self._select_top_papers(papers, search_query, top_k=self.top_k_papers)
        
        print(f"[{self.role}] Top {len(top_papers)} Relevant Papers:")
        for i, paper in enumerate(top_papers, 1):
             print(f"  {i}. {paper.get('title', 'Unknown')} ({paper.get('year', 'N/A')})")
        papers_context = self._format_papers_for_prompt(top_papers)
        
        # Build latest papers list for SOTA analysis
        latest_titles = []
        for paper in top_papers:
            year = paper.get('year', 'N/A')
            title = paper.get('title', 'Unknown')
            latest_titles.append(f"- [{year}] {title}")
        latest_papers_str = "\n".join(latest_titles) if latest_titles else "No latest papers found."
        
        # Step 3: Generate ideas with concise prompt
        prompt = f"""You are a research PI proposing {n} novel research topics for "{keyword}".

                    RECENT PAPERS:
                    {latest_papers_str}

                    CONTEXT:
                    {papers_context}

                    TASK:
                    1. First, use <think> to identify limitations in current research and propose solutions.
                    2. Then output JSON with {n} topics.

                    <think>
                    CRITIC: What's missing/flawed in current research?
                    SOLUTION: How to fix it with novel approaches?
                    </think>

                    OUTPUT FORMAT (JSON only, no markdown):
                    {EXAMPLE_JSON_STRUCTURE}

                    Generate {n} topics now:
                    """
        
        print(f"[{self.role}] Generating ideas based on {len(top_papers)} relevant papers...")
        response = self.generate(prompt)
        
        # Post-processing: Remove <think> tags before JSON parsing
        processed_response = response
        if '<think>' in processed_response:
            # Extract thinking content for debugging/logging
            think_match = re.search(r'<think>(.*?)</think>', processed_response, re.DOTALL)
            if think_match:
                thinking_content = think_match.group(1).strip()
                print(f"[{self.role}] Thinking process captured ({len(thinking_content)} chars)")
            
            # Remove <think> block for JSON parsing
            processed_response = re.sub(r'<think>.*?</think>', '', processed_response, flags=re.DOTALL).strip()
        
        # Clean markdown artifacts
        processed_response = processed_response.replace('```json', '').replace('```', '').strip()
        
        data = extract_json(processed_response)
        
        ideas = []
        
        # Handle the nested structure: {"topics": [...]}
        if isinstance(data, dict) and "topics" in data:
            topics_list = data["topics"]
        elif isinstance(data, list):
            topics_list = data
        else:
            print(f"[{self.role}] Warning: Unexpected response format. Attempting recovery...")
            topics_list = []
        
        for item in topics_list:
            if not isinstance(item, dict):
                continue
                
            # Build detailed methodology from available fields
            methodology_parts = []
            
            if item.get("methodology"):
                methodology_parts.append(item["methodology"])
            
            if item.get("table_of_contents"):
                toc = item["table_of_contents"]
                if isinstance(toc, list):
                    methodology_parts.append("\n**Proposed Structure:**\n" + "\n".join(toc))
            
            methodology = "\n\n".join(methodology_parts) if methodology_parts else item.get("methodology", "")
            
            # Build description from background, necessity, expected_effects
            description_parts = []
            if item.get("background"):
                description_parts.append(f"**Background:** {item['background']}")
            if item.get("necessity"):
                description_parts.append(f"**Necessity:** {item['necessity']}")
            if item.get("expected_effects"):
                description_parts.append(f"**Expected Effects:** {item['expected_effects']}")
            
            description = "\n\n".join(description_parts) if description_parts else item.get("description", "")
            
            content = IdeaContent(
                title=item.get("title", "Untitled"),
                methodology=methodology,
                description=description,
                raw_content=str(item)
            )
            
            # Create IdeaObject with initial snapshot
            idea = IdeaObject()
            snapshot = IdeaSnapshot(
                iteration=0,
                role="draft",
                content=content
            )
            idea.evolution_history.append(snapshot)
            ideas.append(idea)
        
        print(f"[{self.role}] Generated Ideas:")
        for i, idea in enumerate(ideas, 1):
            print(f"  {i}. {idea.latest_content.title}")

        print(f"[{self.role}] Generated {len(ideas)} ideas.")
        return ideas
