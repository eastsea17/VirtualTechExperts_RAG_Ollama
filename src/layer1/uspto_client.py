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

    def fetch_patents(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        주어진 키워드 리스트를 기반으로 특허를 검색합니다.
        현재 구현은 첫 번째 키워드를 사용하여 제목 또는 초록에서 일치하는 항목을 찾습니다.
        
        Args:
            keywords (List[str]): 검색할 키워드 리스트
            
        Returns:
            List[Dict[str, Any]]: 검색된 특허 정보 리스트
        """
        if not keywords:
            return []
            
        print(f"[USPTOClient] 특허 검색 중 (키워드: {keywords[:2]})...")
        
        # API 키 유효성 검사
        if not self.api_key or "YOUR_USPTO_KEY" in self.api_key:
            print("[USPTOClient] 경고: .env 파일에서 유효한 USPTO_API_KEY를 찾을 수 없습니다.")
            print("   > .env 파일에 키를 추가해주세요.")
            print("   > 키 발급: https://patentsview.org/apis/key")
            return []

        # 현재는 첫 번째 키워드만 사용 (복합 쿼리 개선 가능)
        query_text = keywords[0].replace('"', '')
        
        # PatentsView API 쿼리 구조 구성
        # _or 조건으로 제목(patent_title) 또는 초록(patent_abstract)에 키워드가 포함된 문서를 찾음
        query = {
            "q": {
                "_or": [
                    {"_text_phrase": {"patent_title": query_text}},
                    {"_text_phrase": {"patent_abstract": query_text}}
                ]
            },
            # 반환받을 필드 지정 (번호, 제목, 초록, 날짜)
            "f": ["patent_number", "patent_title", "patent_abstract", "patent_date"],
            "o": {"per_page": self.limit} # 결과 개수 제한
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key,
            "User-Agent": self.contact_email # 예의바른 API 사용을 위해 연락처 포함
        }
        
        try:
            # POST 요청 전송
            response = requests.post(self.base_url, json=query, headers=headers, timeout=30)
            
            # 일반적인 에러 코드 처리
            if response.status_code == 403:
                print(f"[USPTOClient] 인증 오류 (403): API 키가 올바르지 않습니다.")
                return []
            if response.status_code == 400:
                 print(f"[USPTOClient] 요청 오류 (400): 쿼리 형식을 확인해주세요.")
                 return []
                 
            response.raise_for_status()
            
            data = response.json()
            patents_data = data.get("patents", [])
            
            results = []
            for p in patents_data:
                results.append({
                    "id": p.get("patent_number"),
                    "title": p.get("patent_title"),
                    "abstract": p.get("patent_abstract"),
                    "publication_year": p.get("patent_date", "")[:4], # 날짜에서 연도만 추출 (YYYY)
                    "source": "USPTO"
                })
                
            print(f"[USPTOClient] 검색 완료: {len(results)}개의 특허 발견.")
            return results
            
        except Exception as e:
            print(f"[USPTOClient] 연결 오류: {e}")
            return []

if __name__ == "__main__":
    client = USPTOClient()
    pass
