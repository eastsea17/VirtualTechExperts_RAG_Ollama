import requests
import yaml
import os
import base64
import time  # API 호출 속도 제한(Rate Limiting) 준수를 위해 사용
from typing import List, Dict, Any
from dotenv import load_dotenv

# .env 파일에서 환경 변수(API 키 등)를 로드합니다.
load_dotenv()

class EPOClient:
    """
    유럽특허청(EPO)의 OPS(Open Patent Services) API를 사용하여 특허 데이터를 수집하는 클라이언트입니다.
    OAuth 인증을 처리하고, 검색 결과 파싱 및 상세 정보 조회를 수행합니다.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        초기화 메서드: 설정 파일을 로드하고 API 인증 정보를 준비합니다.
        
        Args:
            config_path (str): 설정 파일 경로.
        """
        # 설정 파일 로드 시 예외 처리 (파일이 없거나 형식이 잘못된 경우 대비)
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        except Exception:
            self.config = {}
            
        # 환경 변수에서 Consumer Key와 Secret을 가져옵니다.
        self.consumer_key = os.getenv("EPO_CONSUMER_KEY")
        self.consumer_secret = os.getenv("EPO_CONSUMER_SECRET")
        
        # 설정 파일에서 EPO 관련 설정값을 읽어옵니다. (없으면 기본값 사용)
        data_acq = self.config.get('data_acquisition', {}) if self.config else {}
        epo_cfg = data_acq.get('epo', {})
        
        self.auth_url = epo_cfg.get('auth_url', "https://ops.epo.org/3.2/auth/accesstoken")
        self.service_url = epo_cfg.get('service_url', "https://ops.epo.org/3.2/rest-services")
        self.limit = epo_cfg.get('fetch_limit', 20)
        self.access_token = None

    def _get_access_token(self):
        """
        EPO API 사용을 위한 OAuth 2.0 액세스 토큰을 발급받습니다.
        토큰은 일정 시간 후 만료되므로 필요할 때마다 호출하여 갱신할 수 있어야 합니다.
        """
        # API 키 유효성 검사
        if not self.consumer_key or not self.consumer_secret or "YOUR_EPO_KEY" in self.consumer_key:
            print("[EPOClient] 경고: .env 파일에서 유효한 EPO Consumer Key/Secret을 찾을 수 없습니다.")
            return None
            
        # Basic Auth 헤더 생성 (Key:Secret을 Base64로 인코딩)
        credentials = f"{self.consumer_key}:{self.consumer_secret}"
        encoded_creds = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_creds}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        try:
            # POST 요청으로 액세스 토큰 요청
            response = requests.post(self.auth_url, data={"grant_type": "client_credentials"}, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 발급받은 토큰 저장
            self.access_token = response.json()['access_token']
            return self.access_token
        except Exception as e:
            print(f"[EPOClient] 인증 오류: {e}")
            return None

    def fetch_patents(self, keyword: str) -> List[Dict[str, Any]]:
        """
        주어진 키워드로 특허를 검색합니다.
        
        개선 사항:
        1. 제목(Title)뿐만 아니라 초록(Abstract)까지 검색하여 재현율을 높임 (ti -> ta).
        2. 미국(US), 국제특허(WO), 유럽(EP) 출원을 우선적으로 필터링하여 검색 품질 향상.
        
        Args:
            keyword (str): 검색할 키워드 또는 CQL 쿼리
        """
        # 토큰 발급/갱신 (실패 시 빈 리스트 반환)
        if not self._get_access_token():
            return []
            
        print(f"[EPOClient] 특허 검색 중: {keyword}...")
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        
        # CQL(Contextual Query Language) 쿼리 구성 로직
        if ' AND ' in keyword or ' OR ' in keyword:
             # 이미 복합 쿼리인 경우 그대로 사용
             cql_query = keyword
        else:
             # 단일 키워드나 구문인 경우
             clean_key = keyword.strip()
             if clean_key.startswith('"') and clean_key.endswith('"'):
                 # 따옴표로 감싸진 경우: 구문 검색 (Title or Abstract)
                 cql_query = f'ta={clean_key}' 
             else:
                 # 일반 단어인 경우: 단어 검색
                 cql_query = f'ta="{clean_key}"'
        
        # [중요] 검색 필터 적용: 미국(US), 국제(WO), 유럽(EP) 특허만 검색
        # 단, 쿼리가 이미 복잡한 경우(괄호 포함) 필터를 추가하면 EPO Term Limit(10개)을 초과할 수 있음.
        # 따라서 복잡한 쿼리는 필터를 제외하고, 단순 쿼리에만 국가 필터를 적용함.
        if '(' not in cql_query:
            cql_query = f'({cql_query}) AND (pn="US" OR pn="WO" OR pn="EP")'
             
        # GET 요청은 URL 길이 제한(413 Error)에 걸릴 수 있으므로 POST 방식 사용 권장
        # Content-Type: text/plain으로 설정하고 쿼리를 그대로 Body에 담아 보냅니다.
        headers["Content-Type"] = "text/plain"
        
        search_url = f"{self.service_url}/published-data/search"
        
        try:
            # API 요청 수행 (POST)
            # data에 딕셔너리가 아닌 문자열을 전달하면 requests는 text/plain으로 보내지 않으므로
            # 명시적으로 헤더를 설정하고 문자열을 보냅니다.
            response = requests.post(search_url, headers=headers, data=cql_query, timeout=30)
            
            # 검색 결과가 없는 경우 (404 Not Found는 에러가 아니라 '없음'으로 처리)
            if response.status_code == 404:
                print(f"[EPOClient] 검색 결과 없음.")
                return []
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            # --- OPS JSON 응답 구조 파싱 ---
            # 구조가 매우 복잡하므로 단계별로 안전하게 접근
            ops_data = data.get('ops:world-patent-data', {})
            biblio = ops_data.get('ops:biblio-search', {})
            
            # 간혹 'biblio-search' 대신 'standardization' 래퍼 안에 있는 경우가 있음
            if not biblio:
                 std_data = ops_data.get('ops:standardization', {})
                 output = std_data.get('ops:output', {})
                 biblio = output.get('ops:biblio-search', {})
            
            search_result = biblio.get('ops:search-result', {})
            publications = search_result.get('ops:publication-reference', [])
            
            # 결과가 1개일 경우 리스트가 아닌 딕셔너리로 반환되므로 리스트로 변환
            if isinstance(publications, dict):
                publications = [publications]
                
            print(f"[EPOClient] {len(publications)}개의 특허 레퍼런스 발견.")
                
            for i, pub in enumerate(publications):
                # 검색 제한 설정 (상위 N개만 처리)
                if i >= self.limit: 
                    break

                try:
                    # Document ID 추출 (docdb 형식 우선 사용)
                    doc_id_list = pub.get('document-id', [])
                    if isinstance(doc_id_list, dict): doc_id_list = [doc_id_list]
                    
                    docdb_obj = None
                    for ref in doc_id_list:
                        if ref.get('@document-id-type') == 'docdb':
                            docdb_obj = ref
                            break
                    
                    # docdb 형식이 없으면 첫 번째 ID 사용
                    if not docdb_obj and doc_id_list:
                        docdb_obj = doc_id_list[0]
                        
                    if not docdb_obj:
                        continue
                     
                    # ID 구성 요소 추출
                    doc_number = docdb_obj.get('doc-number', {}).get('$', 'Unknown')
                    kind = docdb_obj.get('kind', {}).get('$', '')
                    country = docdb_obj.get('country', {}).get('$', 'EP')
                    date = docdb_obj.get('date', {}).get('$', 'Unknown Date')
                    
                    full_id = f"{country}.{doc_number}.{kind}"
                    
                    # [상세 조회] 검색 결과에는 제목/초록이 없으므로 별도 API 호출이 필요함
                    # API 호출 간 딜레이 추가 (서버 부하 방지)
                    time.sleep(0.2) 
                    title, abstract, applicant = self._fetch_patent_details(country, doc_number, kind)
                    
                    # 최종 결과 리스트에 추가
                    results.append({
                        "source": "EPO",
                        "id": full_id,
                        "title": title if title else f"Patent {full_id}",
                        "abstract": abstract if abstract else "Abstract details not available.",
                        "published_date": date,
                        # Espacenet(특허 검색 사이트) 링크 생성
                        "url": f"https://worldwide.espacenet.com/publicationDetails/biblio?CC={country}&NR={doc_number}&KC={kind}",
                        "authors": [applicant] if applicant else [],
                        "raw": pub
                    })
                    
                except Exception as ex:
                    print(f"[EPOClient] 항목 파싱 중 오류 (Index {i}): {ex}")
                    continue
            
            return results
            return results
        except Exception as e:
            print(f"[EPOClient] 검색 중 오류 발생: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"[EPOClient] 상세 에러 메시지: {e.response.text}")
            return []

    def _fetch_patent_details(self, country, number, kind):
        """
        특정 특허의 상세 서지 정보(제목, 초록, 출원인)를 조회합니다.
        
        Args:
            country (str): 국가 코드 (예: US)
            number (str): 특허 번호
            kind (str): 종류 코드 (예: A1)
            
        Returns:
            Tuple[str, str, str]: (제목, 초록, 출원인)
        """
        try:
            # OPS API ID 포맷: 'CC.Number.Kind'
            doc_id_str = f"{country}.{number}.{kind}"
            url = f"{self.service_url}/published-data/publication/docdb/{doc_id_str}/biblio"
            
            headers = {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}
            res = requests.get(url, headers=headers, timeout=10)
            
            if res.status_code != 200: 
                return None, None, None
            
            b_data = res.json()
            
            # JSON 깊은 구조 탐색
            wpd = b_data.get('ops:world-patent-data', {})
            eds = wpd.get('exchange-documents', {})
            ed = eds.get('exchange-document', {})
            
            # exchange-document가 리스트일 경우 첫 번째 요소 사용
            if isinstance(ed, list) and len(ed) > 0:
                ed = ed[0]
            
            biblio_data = ed.get('bibliographic-data', {})

            # 1. 제목(Title) 추출
            title = None
            titles = biblio_data.get('invention-title', [])
            if isinstance(titles, dict): titles = [titles]
            
            # 영어 제목(@lang='en') 우선 탐색
            for t in titles:
                if t.get('@lang') == 'en':
                    title = t.get('$', None)
                    break
            # 영어가 없으면 첫 번째 언어 사용
            if not title and titles:
                title = titles[0].get('$', "Unknown Title")
            
            # 2. 초록(Abstract) 추출
            abstract = None
            abst_obj = ed.get('abstract', [])
            if isinstance(abst_obj, dict): abst_obj = [abst_obj]
            
            selected_abs = None
            # 영어 초록 우선 탐색
            for a in abst_obj:
                if a.get('@lang') == 'en':
                    selected_abs = a
                    break
            if not selected_abs and abst_obj:
                selected_abs = abst_obj[0]
                
            if selected_abs:
                p_text = selected_abs.get('p', [])
                # 초록 본문이 여러 문단(p 태그)일 경우 합치기
                if isinstance(p_text, dict):
                    abstract = p_text.get('$', '')
                elif isinstance(p_text, list):
                    abstract = " ".join([p.get('$', '') for p in p_text if isinstance(p, dict)])
            
            # 3. 출원인(Applicant) 추출
            applicant = "Unknown"
            parties = biblio_data.get('parties', {})
            applicants = parties.get('applicants', {}).get('applicant', [])
            if isinstance(applicants, dict): applicants = [applicants]
            
            if applicants:
                app_name_obj = applicants[0].get('applicant-name', {}).get('name', {})
                applicant = app_name_obj.get('$', 'Unknown')
                
            return title, abstract, applicant
            
        except Exception as e:
            # 상세 정보 조회 실패 시 None 반환 (메인 로직에서 처리)
            return None, None, None

if __name__ == "__main__":
    client = EPOClient()
    # 테스트 코드 (주석 처리됨)
    # res = client.fetch_patents("liquid cooling")
    # print(res)
