import requests
import yaml
from typing import List, Dict, Any

class OpenAlexClient:
    """
    OpenAlex API를 사용하여 학술 논문을 검색하고 수집하는 클라이언트 클래스입니다.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        초기화 메서드: 설정 파일을 로드하고 API 연결에 필요한 기본 정보를 설정합니다.
        
        Args:
            config_path (str): 설정 파일(.yaml)의 경로. 기본값은 "config/config.yaml"
        """
        # 설정 파일 로드
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        # OpenAlex 관련 설정값 추출
        # API 기본 URL, 사용자 식별용 이메일(User-Agent), 검색 건수 제한(limit)을 가져옵니다.
        self.base_url = self.config['data_acquisition']['openalex']['base_url']
        self.user_agent = self.config['data_acquisition']['openalex']['user_agent_email']
        self.limit = self.config['data_acquisition']['openalex']['fetch_limit']
        
    def fetch_papers(self, query: str) -> List[Dict[str, Any]]:
        """
        주어진 검색어(query)를 사용하여 OpenAlex에서 관련 논문을 검색합니다.
        
        Args:
            query (str): 검색할 키워드 또는 쿼리 문자열 (예: '"artificial intelligence" AND "ethics"')
            
        Returns:
            List[Dict[str, Any]]: 검색된 논문들의 정보를 담은 딕셔너리 리스트.
                                  각 딕셔너리는 id, title, abstract, year, citation count, url 등을 포함.
        """
        print(f"[OpenAlexClient] 논문 검색 중: '{query}'...")
        
        # API 요청 파라미터 설정
        params = {
            "search": query,  # 검색어 (제목, 초록, 전문 등에서 검색)
            "per-page": min(self.limit, 200),  # 한 페이지당 가져올 결과 수 (최대 200개 제한)
            # 필터링 조건: 
            # 1. has_abstract:true -> 초록이 있는 논문만 검색
            # 2. from_publication_date:2020-01-01 -> 2020년 이후 출판된 최신 논문만 검색
            "filter": "has_abstract:true,from_publication_date:2020-01-01" 
        }
        
        # 예의바른 API 사용을 위해 User-Agent에 이메일을 포함합니다.
        headers = {
            "User-Agent": f"mailto:{self.user_agent}"
        }
        
        try:
            # GET 요청 전송
            response = requests.get(self.base_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()  # 200 OK가 아니면 예외 발생
            
            data = response.json()
            results = data.get("results", [])
            
            papers = []
            for result in results:
                title = result.get("title")
                abstract_inverted = result.get("abstract_inverted_index")
                
                # OpenAlex는 데이터 절약을 위해 역색인(Inverted Index) 형태로 초록을 제공합니다.
                # 이를 사람이 읽을 수 있는 텍스트로 재조립합니다.
                abstract = self._reconstruct_abstract(abstract_inverted)
                
                # 제목과 초록이 모두 유효한 경우에만 결과에 추가합니다.
                if title and abstract:
                    papers.append({
                        "id": result.get("id"),  # OpenAlex ID (예: https://openalex.org/W123456789)
                        "title": title,          # 논문 제목
                        "abstract": abstract,    # 재조립된 초록 본문
                        "publication_year": result.get("publication_year"), # 출판 연도
                        "cited_by_count": result.get("cited_by_count", 0),  # 피인용 횟수
                        "url": result.get("id")  # 논문 URL
                    })
            
            print(f"[OpenAlexClient] 검색 완료: {len(papers)}개의 논문을 발견했습니다.")
            return papers
            
        except requests.exceptions.RequestException as e:
            print(f"[OpenAlexClient] API 요청 오류: {e}")
            return []
        except Exception as e:
            print(f"[OpenAlexClient] 알 수 없는 오류: {e}")
            return []

    def _reconstruct_abstract(self, inverted_index: Dict) -> str:
        """
        OpenAlex의 역색인(Inverted Index) 형태의 초록 데이터를 일반 텍스트 문자열로 복원합니다.
        
        OpenAlex는 초록을 {"word": [position1, position2], ...} 형태로 제공합니다.
        이를 위치(position) 순서대로 정렬하여 문장으로 만듭니다.
        
        Args:
            inverted_index (Dict): 단어와 위치 리스트가 매핑된 딕셔너리
            
        Returns:
            str: 복원된 초록 텍스트
        """
        if not inverted_index:
            return ""
            
        # (위치, 단어) 튜플의 리스트를 생성
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        
        # 위치(index)를 기준으로 오름차순 정렬
        word_positions.sort()
        
        # 단어들을 공백으로 이어 붙여서 전체 문장 생성
        return " ".join([word for _, word in word_positions])

if __name__ == "__main__":
    # 테스트 코드: 클라이언트 생성 및 간단한 검색 테스트
    client = OpenAlexClient()
    papers = client.fetch_papers("blockchain")
    if papers:
        print(f"첫 번째 논문 제목: {papers[0]['title']}")
