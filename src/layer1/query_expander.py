import yaml
import re
from typing import List, Tuple
from langchain_ollama import ChatOllama
import itertools

class QueryExpander:
    """
    연구 주제(research topic)를 분석하여 최적의 검색 쿼리 리스트를 생성하는 클래스입니다.
    LLM을 활용하여 핵심 키워드를 추출하고, 동의어를 생성하며, 검색 결과가 없을 경우를 대비한 
    'N-1 적응형 전략(Adaptive Strategy)' 쿼리를 제공합니다.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        초기화 메서드: 설정 파일을 로드하고 LLM(Ollama) 클라이언트를 설정합니다.
        
        Args:
            config_path (str): 설정 파일 경로.
        """
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # 쿼리 확장에는 빠르고 똑똑한 모델이 유리하므로 설정에서 chat_model을 가져오거나 기본값을 사용합니다.
        self.model_name = self.config['ollama'].get('chat_model', "gpt-oss:120b-cloud")
        self.base_url = self.config['ollama']['base_url']
        
        # ChatOllama 인스턴스 생성 (창의성은 낮추고 정확도를 높이기 위해 temperature=0.2 설정)
        self.llm = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=0.2 
        )

    def _extract_keywords(self, topic: str) -> List[str]:
        """
        주제에서 핵심 기술 구문(Technical Phrases)을 추출합니다.
        단순 단어 나열이 아니라, "Solid State Batteries" 처럼 의미 있는 덩어리를 유지합니다.
        
        Args:
            topic (str): 연구 주제 문자열
            
        Returns:
            List[str]: 추출된 핵심 구문 리스트 (최대 5개)
        """
        prompt = f"""
        연구 주제에서 명시적으로 언급된 2~5개의 구체적인 기술 구문(Technical Phrases)을 추출하세요.
        입력 텍스트에 없는 관련 개념이나 용어를 임의로 추가하지 마세요.
        복합 용어는 분리하지 말고 하나의 구문으로 유지하세요 (예: "Solid State Batteries").
        
        TOPIC: "{topic}"
        
        출력 형식:
        따옴표 없이 쉼표로 구분된 구문 리스트만 반환하세요.
        예시: Solid State Batteries, Lithium Metal Anode
        """
        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            # 불필요한 따옴표나 대괄호 제거
            content = content.replace('"', '').replace('[', '').replace(']', '')
            # 쉼표 기준으로 분리
            keywords = [k.strip() for k in content.split(',')]
            # 너무 짧거나 빈 키워드 제거
            keywords = [k for k in keywords if k and len(k) > 2]
            return keywords[:5] # 최대 5개까지만 사용
        except Exception as e:
            print(f"[QueryExpander] 키워드 추출 오류: {e}")
            return [topic] # 실패 시 원본 주제 그대로 반환

    def _generate_synonyms(self, topic: str) -> List[str]:
        """
        주제가 짧은 경우(<10 단어), 상호 교환 가능한 기술적 동의어(Synonyms)를 생성합니다.
        예: "bio feedstock" -> "biomass"
        
        Args:
            topic (str): 연구 주제
            
        Returns:
            List[str]: 생성된 동의어 리스트 (최대 3개)
        """
        # 문장형 긴 주제는 동의어 생성이 오히려 노이즈가 될 수 있어 건너뜀
        if len(topic.split()) >= 10:
            return []
            
        prompt = f"""
        다음 주제에 대해 상호 교환 가능한 기술적 동의어/변형(Synonyms)을 약 5개를 생성하세요.: "{topic}"
        따옴표 없이 쉼표로 구분된 리스트만 반환하세요.
        예시: coprocessing of bio feedstock, co-processing of biomass
        """
        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            content = content.replace('"', '').replace("'", "")
            synonyms = [s.strip() for s in content.split(',')]
            return [s for s in synonyms if s and len(s) > 3][:3]
        except Exception as e:
            print(f"[QueryExpander] 동의어 생성 오류: {e}")
            return []

    def _rank_combinations(self, topic: str, combos: List[Tuple[str]], limit: int = 2) -> List[Tuple[str]]:
        """
        키워드 조합(Subset) 중에서 원래 주제의 의도를 가장 잘 보존하는 조합을 LLM에게 물어 순위를 매깁니다.
        (N-1 전략 사용 시, 어떤 키워드를 뺐을 때 가장 의미가 덜 왜곡되는지 판단)
        
        Args:
            topic (str): 원본 주제
            combos (List[Tuple[str]]): 키워드 조합 후보들
            limit (int): 선택할 조합 개수
            
        Returns:
            List[Tuple[str]]: 선택된 최적의 조합 리스트
        """
        # LLM에게 보낼 옵션 텍스트 구성
        options_text = ""
        for i, combo in enumerate(combos):
            options_text += f"{i}. {', '.join(combo)}\n"
            
        prompt = f"""
        Original Topic: "{topic}"
        
        검색 범위를 넓히기 위해 주제를 키워드 부분집합(Subset)으로 나누었습니다.
        다음 중 원본 주제의 핵심 기술적 의도를 가장 잘 유지하고 있는 부분집합은 무엇입니까?
        (즉, 가장 중요한 '앵커' 키워드를 빠뜨리지 않은 것은?)
        
        옵션:
        {options_text}
        
        상위 {limit}개의 번호(index)를 선택하세요.
        오직 쉼표로 구분된 숫자만 반환하세요 (예: "0, 2").
        """
        try:
            response = self.llm.invoke(prompt)
            indices_str = response.content.strip()
            # 숫자만 추출
            indices = [int(x) for x in re.findall(r'\d+', indices_str)]
            
            selected_combos = []
            for idx in indices:
                if 0 <= idx < len(combos):
                    selected_combos.append(combos[idx])
            
            if not selected_combos:
                return combos[:limit]
            
            # 선택된 조합 반환
            return selected_combos[:limit]
        except Exception as e:
            print(f"[QueryExpander] 순위 선정 오류: {e}")
            return combos[:limit] # 오류 시 앞부분 반환

    def generate_search_queries(self, topic: str) -> List[str]:
        """
        우선순위가 지정된 검색 쿼리 리스트를 생성합니다.
        
        전략:
        1. 전체 정확 일치 (Full Exact Match): 추출된 모든 키워드를 AND로 연결
        2. 동의어 (Synonyms): 주제가 짧을 경우 동의어 쿼리 추가
        3. N-1 조합 (N-1 Combinations): 키워드가 3개 이상일 경우, 하나씩 뺀 조합으로 검색 범위 확장 (Fallback)
        """
        keywords = self._extract_keywords(topic)
        
        queries = []
        
        # [우선순위 1] 전체 조합 (가장 정확함)
        # 키워드들을 AND로 연결하고 각각 따옴표로 감싸서 정확한 구문 검색(Phrase Match)을 유도합니다.
        full_query = " AND ".join([f'"{k}"' for k in keywords])
        queries.append(full_query)
        
        # [우선순위 1.5] 동의어 검색
        if len(topic.split()) < 10:
            synonyms = self._generate_synonyms(topic)
            if synonyms:
                for syn in synonyms:
                    # 동의어 전체를 하나의 구문으로 검색
                    queries.append(f'"{syn}"')
        
        N = len(keywords)
        
        # [중요] N-1 전략 제외 조건
        # 키워드가 3개 미만(1개 또는 2개)일 때는 하나를 빼면(N-1) 너무 광범위한 단어만 남습니다.
        # 예: "Ammonia Cracking" -> "Ammonia", "Cracking" (너무 넓음)
        # 따라서 노이즈 방지를 위해 이 경우에는 확장하지 않고 종료합니다.
        if N < 3:
            return queries
        
        # [우선순위 2] N-1 조합 (조금 더 넓은 검색)
        combos = list(itertools.combinations(keywords, N-1))
        
        if combos:
            # LLM을 통해 가장 의미 있는 조합 순으로 정렬
            ranked_combos = self._rank_combinations(topic, combos, limit=2)
            
            for combo in ranked_combos:
                sub_query = " AND ".join([f'"{k}"' for k in combo])
                queries.append(sub_query)
        
        return queries

    # 레거시 메서드 호환성 유지
    def refine_search_query(self, topic: str) -> Tuple[str, List[str]]:
        qs = self.generate_search_queries(topic)
        keywords = self._extract_keywords(topic)
        return qs[0], keywords

# --- 적응형 페치(Adaptive Fetch) 헬퍼 함수 ---
def adaptive_fetch(client_fetch_func, queries: List[str], limit: int, source_name: str) -> List[any]:
    """
    쿼리 리스트를 순차적으로 실행하며 데이터를 수집하는 적응형 함수입니다.
    
    작동 방식:
    1. 가장 정확한 첫 번째 쿼리(Q1)를 실행합니다.
    2. Q1에서 충분한 데이터(목표의 50% 이상)가 나오면 즉시 중단합니다 (Early Stop).
    3. 데이터가 부족하면 다음 우선순위 쿼리(동의어, N-1 등)를 실행하여 결과를 보충합니다.
    4. 중복된 데이터는 제거합니다.
    
    Args:
        client_fetch_func (func): 데이터를 가져올 클라이언트의 메서드 (예: epo_client.fetch_patents)
        queries (List[str]): 실행할 쿼리 문자열 리스트
        limit (int): 목표 수집 개수
        source_name (str): 로그용 소스 이름 (예: "EPO", "OpenAlex")
        
    Returns:
        List[any]: 수집된 데이터 리스트
    """
    all_results = []
    seen_ids = set() # 중복 방지를 위한 ID 집합
    
    for i, query in enumerate(queries):
        try:
            results = client_fetch_func(query)
            
            new_count = 0
            for item in results:
                # 데이터 타입에 따른 고유 ID 추출 (중복 제거용)
                if isinstance(item, dict):
                    # OpenAlex: id, EPO: id/publication_number, Tavily: url
                    unique_id = item.get('id') or item.get('url') or item.get('publication_number') or str(item)
                else:
                    unique_id = str(item)
                
                if unique_id not in seen_ids:
                    all_results.append(item)
                    seen_ids.add(unique_id)
                    new_count += 1
            
            # [조기 종료 조건 1] 첫 번째 정밀 쿼리가 충분히 성공했을 때
            # 목표의 50% 이상을 찾으면, 굳이 더 넓은 범위의(덜 정확할 수 있는) 쿼리를 실행하지 않음.
            if i == 0 and new_count >= (limit * 0.5):
                break
                
            # [조기 종료 조건 2] 목표 개수 달성 시
            if len(all_results) >= limit:
                break
                
        except Exception as e:
            print(f"      [{source_name}] 쿼리 실행 오류 Q{i+1}: {e}")
            continue
            
    return all_results[:limit]

if __name__ == "__main__":
    qe = QueryExpander()
    topic = "Co-processing of bio-based feedstock in FCC units"
    queries = qe.generate_search_queries(topic)
    print(f"주제: {topic}")
    print("생성된 쿼리 목록:")
    for q in queries:
        print(f" - {q}")
