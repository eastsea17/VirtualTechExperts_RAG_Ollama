import requests
import yaml
import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv

# .env 파일 로드 (환경 변수 설정)
load_dotenv()

class USPTOClient:
    """
    PatentsView API v1을 사용하여 미국 특허(US Patents)를 검색하는 클라이언트입니다.
    API 키는 .env 파일에서 관리됩니다.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        설정 파일을 읽어 기본 구성을 초기화합니다.
        """
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        # USPTO 관련 설정 로드
        uspto_cfg = self.config['data_acquisition'].get('uspto', {})
        self.base_url = uspto_cfg.get('base_url', "https://search.patentsview.org/api/v1/patent")
        self.contact_email = uspto_cfg.get('contact_email', "research-agent@example.com")
        self.limit = uspto_cfg.get('fetch_limit', 25)
        
        # 환경 변수에서 API 키 로드
        self.api_key = os.getenv("USPTO_API_KEY")

    def fetch_patents(self, keywords: Any) -> List[Dict[str, Any]]:
        """
        주어진 키워드 또는 불리언 쿼리 문자열을 기반으로 특허를 검색합니다.
        
        Args:
            keywords (Union[List[str], str]): 검색할 키워드 리스트 또는 불리언 쿼리 문자열
            
        Returns:
            List[Dict[str, Any]]: 검색된 특허 정보 리스트
        """
        if not keywords:
            return []
            
        # API 키 유효성 검사
        if not self.api_key or "YOUR_USPTO_KEY" in self.api_key:
            print("[USPTOClient] 경고: .env 파일에서 유효한 USPTO_API_KEY를 찾을 수 없습니다.")
            return []

        query = {}
        
        # 1. 입력이 문자열(Boolean Query)인 경우
        if isinstance(keywords, str):
            print(f"[USPTOClient] 특허 검색 중 (Query: {keywords[:50]}...)...")
            try:
                query = self._parse_boolean_query(keywords)
            except Exception as e:
                print(f"[USPTOClient] 쿼리 파싱 오류: {e}")
                return []
                
        # 2. 입력이 리스트(Keyword List)인 경우 - 기존 로직 유지
        elif isinstance(keywords, list):
            print(f"[USPTOClient] 특허 검색 중 (Keywords: {keywords[:2]})...")
            query_text = keywords[0].replace('"', '')
            query = {
                "q": {
                    "_or": [
                        {"_text_phrase": {"patent_title": query_text}},
                        {"_text_phrase": {"patent_abstract": query_text}}
                    ]
                }
            }
        else:
             print(f"[USPTOClient] 지원하지 않는 입력 형식입니다: {type(keywords)}")
             return []

        # 공통 파라미터 추가
        query["f"] = ["patent_id", "patent_title", "patent_abstract", "patent_date"]
        query["o"] = {"per_page": self.limit}
        
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key,
            "User-Agent": self.contact_email
        }
        
        try:
            # POST 요청 전송
            response = requests.post(self.base_url, json=query, headers=headers, timeout=30)
            
            if response.status_code == 403:
                print(f"[USPTOClient] 인증 오류 (403): API 키가 올바르지 않습니다.")
                return []
            if response.status_code == 400:
                 print(f"[USPTOClient] 요청 오류 (400): 쿼리 형식을 확인해주세요. (Query: {json.dumps(query)})")
                 return []
                 
            response.raise_for_status()
            
            data = response.json()
            patents_data = data.get("patents", [])
            
            results = []
            if patents_data:
                for p in patents_data:
                    results.append({
                        "id": p.get("patent_id"),
                        "title": p.get("patent_title"),
                        "abstract": p.get("patent_abstract"),
                        "publication_year": p.get("patent_date", "")[:4],
                        "source": "USPTO"
                    })
                
            print(f"[USPTOClient] 검색 완료: {len(results)}개의 특허 발견.")
            return results
            
        except Exception as e:
            print(f"[USPTOClient] 연결 오류: {e}")
            return []

    def _parse_boolean_query(self, query_str: str) -> Dict[str, Any]:
        """
        QueryExpander가 생성한 불리언 쿼리 문자열을 PatentsView API JSON 형식으로 변환합니다.
        지원 형식: (A OR B) AND (C OR D) 형태의 CNF
        
        Args:
            query_str (str): 불리언 쿼리 문자열
            
        Returns:
            Dict[str, Any]: PatentsView API 'q' 파라미터 객체
        """
        # 1. 단순 텍스트 (불리언 연산자가 없는 경우)
        if "AND" not in query_str and "OR" not in query_str:
            clean_str = query_str.replace('"', '').replace('(', '').replace(')', '')
            return {
                "q": {
                    "_or": [
                        {"_text_phrase": {"patent_title": clean_str}},
                        {"_text_phrase": {"patent_abstract": clean_str}}
                    ]
                }
            }

        # 2. AND로 분리 (그룹 단위)
        # 예: "(A OR B) AND (C OR D)" -> ["(A OR B)", "(C OR D)"]
        groups = query_str.split(" AND ")
        
        and_conditions = []
        
        for group in groups:
            # 괄호 제거
            group = group.strip().replace('(', '').replace(')', '')
            
            # OR로 분리 (동의어 단위)
            terms = group.split(" OR ")
            
            or_conditions = []
            for term in terms:
                term = term.strip().replace('"', '')
                # 와일드카드(*) 처리: PatentsView는 *를 지원하지 않거나 다른 방식을 사용하므로 일단 제거하거나 text_phrase 사용
                # PatentsView fulltext search supports wildcards in some fields but _text_phrase is safer for exact/phrase match.
                # If term has *, valid in _text_patter match perhaps? Standardize on text_phrase for now for stability.
                 
                # 각 용어에 대해 제목 또는 초록 검색
                term_condition = {
                    "_or": [
                        {"_text_phrase": {"patent_title": term}},
                        {"_text_phrase": {"patent_abstract": term}}
                    ]
                }
                or_conditions.append(term_condition)
            
            if len(or_conditions) == 1:
                and_conditions.append(or_conditions[0])
            else:
                and_conditions.append({"_or": or_conditions})
                
        if len(and_conditions) == 1:
            return {"q": and_conditions[0]}
        else:
            return {"q": {"_and": and_conditions}}

if __name__ == "__main__":
    client = USPTOClient()
    pass
