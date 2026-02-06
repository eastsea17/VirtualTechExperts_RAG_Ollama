import os
import requests
import yaml
from typing import List, Dict, Any
from dotenv import load_dotenv

# .env 파일에서 환경 변수를 로드합니다 (API 키 등)
s = load_dotenv()

class MarketClient:
    """
    Tavily API를 사용하여 시장 뉴스(Market News)와 최신 동향을 수집하는 클라이언트입니다.
    주로 기술 트렌드나 시장 반응을 파악하는 용도로 사용됩니다.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        초기화 메서드: 설정 파일을 로드하고 Tavily API 연결을 준비합니다.
        
        Args:
            config_path (str): 설정 파일 경로. 기본값은 "config/config.yaml"
        """
        # 설정 파일(.yaml)을 읽어옵니다.
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        # 환경 변수에서 TAVILY_API_KEY를 가져옵니다.
        self.api_key = os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            print("[MarketClient] 경고: 환경 변수에서 TAVILY_API_KEY를 찾을 수 없습니다.")
        
        # Tavily 검색 API 엔드포인트
        self.base_url = "https://api.tavily.com/search"
        
        # 설정 파일에서 가져올 뉴스 개수 제한을 설정합니다. (기본값 5개)
        self.fetch_limit = self.config.get('data_acquisition', {}).get('tavily', {}).get('fetch_limit', 5)
        
    def fetch_market_news(self, query: str) -> List[Dict[str, Any]]:
        """
        주어진 검색어(query)에 대해 시장 뉴스와 인사이트를 검색합니다.
        
        Args:
            query (str): 검색할 키워드 (예: "Solid State Batteries Market Trends")
            
        Returns:
            List[Dict[str, Any]]: 뉴스 아이템들의 리스트. 제목, URL, 내용, 출처 등을 포함.
        """
        # API 키가 없으면 빈 리스트 반환
        if not self.api_key:
            return []
            
        print(f"[MarketClient] 시장 뉴스 검색 중: '{query}'...")
        
        # Tavily API 요청 본문 (Payload) 구성
        payload = {
            "api_key": self.api_key,       # 인증 키
            "query": query,                # 검색어
            "search_depth": "advanced",    # 검색 깊이: 'advanced'를 사용하여 더 깊이 있는 시장 정보를 찾습니다.
            "max_results": self.fetch_limit, # 반환받을 결과의 최대 개수
            "include_domains": [],         # 특정 도메인만 포함하고 싶을 때 사용
            "exclude_domains": [],         # 특정 도메인을 제외하고 싶을 때 사용
            "include_answer": False,       # Tavily의 AI 요약 답변 포함 여부 (여기선 원본 링크가 중요하므로 False)
            "include_raw_content": False,  # 웹페이지의 원본 HTML 포함 여부
            "include_images": False        # 이미지 포함 여부
        }
        
        try:
            # POST 요청으로 검색 수행
            response = requests.post(self.base_url, json=payload, timeout=30)
            response.raise_for_status() # HTTP 오류 발생 시 예외 처리
            
            data = response.json()
            results = data.get("results", [])
            
            news_items = []
            for result in results:
                # 결과 데이터를 내부 표준 포맷으로 변환하여 저장
                news_items.append({
                    "title": result.get("title"),
                    "url": result.get("url"),
                    # 호환성을 위해 content를 abstract 필드에도 복사
                    "abstract": result.get("content"), 
                    "content": result.get("content"),
                    # Tavily는 실시간 검색이므로 대부분 최신이지만, 연도 필드가 없어 현재 연도로 가정하거나 비워둠
                    "publication_year": "2024", 
                    "source": "Tavily News"
                })
            
            print(f"[MarketClient] 검색 완료: {len(news_items)}개의 뉴스 발견.")
            return news_items
            
        except requests.exceptions.RequestException as e:
            print(f"[MarketClient] API 요청 오류: {e}")
            return []
        except Exception as e:
            print(f"[MarketClient] 알 수 없는 오류: {e}")
            return []

if __name__ == "__main__":
    # 테스트 코드
    client = MarketClient()
    news = client.fetch_market_news("Solid State Batteries Market Trends")
    for item in news:
        print(f"- {item['title']} ({item['url']})")
