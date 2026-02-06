import requests
import yaml
import os
import base64
import time  # Rate limiting을 위해 추가
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class EPOClient:
    """
    Client for fetching Patents from European Patent Office (OPS).
    Keys managed via .env.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        # config 로드 시 예외 처리 추가
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        except Exception:
            self.config = {}
            
        self.consumer_key = os.getenv("EPO_CONSUMER_KEY")
        self.consumer_secret = os.getenv("EPO_CONSUMER_SECRET")
        
        # config 파일이 없거나 키가 없을 경우를 대비해 기본값 설정
        data_acq = self.config.get('data_acquisition', {}) if self.config else {}
        epo_cfg = data_acq.get('epo', {})
        
        self.auth_url = epo_cfg.get('auth_url', "https://ops.epo.org/3.2/auth/accesstoken")
        self.service_url = epo_cfg.get('service_url', "https://ops.epo.org/3.2/rest-services")
        self.limit = epo_cfg.get('fetch_limit', 20)
        self.access_token = None

    def _get_access_token(self):
        if not self.consumer_key or not self.consumer_secret or "YOUR_EPO_KEY" in self.consumer_key:
            print("[EPOClient] No valid EPO Keys found in .env. Skipping EPO fetch.")
            return None
            
        credentials = f"{self.consumer_key}:{self.consumer_secret}"
        encoded_creds = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_creds}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        try:
            response = requests.post(self.auth_url, data={"grant_type": "client_credentials"}, headers=headers, timeout=10)
            response.raise_for_status()
            self.access_token = response.json()['access_token']
            return self.access_token
        except Exception as e:
            print(f"[EPOClient] Auth Error: {e}")
            return None

    def fetch_patents(self, keyword: str) -> List[Dict[str, Any]]:
        if not self._get_access_token():
            return []
            
        print(f"[EPOClient] Fetching patents for: {keyword}...")
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        
        # CQL 쿼리 결정 로직
        if ' AND ' in keyword or ' OR ' in keyword:
             cql_query = keyword
        else:
             cql_query = f'ti="{keyword}"' # 단순 키워드면 제목 검색
             
        params = {'q': cql_query}
        search_url = f"{self.service_url}/published-data/search"
        
        try:
            response = requests.get(search_url, headers=headers, params=params, timeout=30)
            if response.status_code == 404:
                print(f"[EPOClient] No results found.")
                return []
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            # OPS JSON 구조 탐색
            ops_data = data.get('ops:world-patent-data', {})
            biblio = ops_data.get('ops:biblio-search', {})
            
            # 표준화된 래퍼(standardization)가 있는 경우 처리
            if not biblio:
                 std_data = ops_data.get('ops:standardization', {})
                 output = std_data.get('ops:output', {})
                 biblio = output.get('ops:biblio-search', {})
            
            search_result = biblio.get('ops:search-result', {})
            publications = search_result.get('ops:publication-reference', [])
            
            # 결과가 1개일 경우 dict로 오므로 리스트로 변환
            if isinstance(publications, dict):
                publications = [publications]
                
            print(f"[EPOClient] Found {len(publications)} raw patent references.")
                
            for i, pub in enumerate(publications):
                # 테스트 모드나 API 부하 방지를 위해 상위 N개만 상세 조회
                if i >= self.limit: 
                    break

                try:
                    # Document ID 추출
                    doc_id_list = pub.get('document-id', [])
                    if isinstance(doc_id_list, dict): doc_id_list = [doc_id_list]
                    
                    docdb_obj = None
                    for ref in doc_id_list:
                        if ref.get('@document-id-type') == 'docdb':
                            docdb_obj = ref
                            break
                    
                    if not docdb_obj and doc_id_list:
                        docdb_obj = doc_id_list[0]
                        
                    if not docdb_obj:
                        continue
                        
                    doc_number = docdb_obj.get('doc-number', {}).get('$', 'Unknown')
                    kind = docdb_obj.get('kind', {}).get('$', '')
                    country = docdb_obj.get('country', {}).get('$', 'EP')
                    date = docdb_obj.get('date', {}).get('$', 'Unknown Date')
                    
                    full_id = f"{country}.{doc_number}.{kind}"
                    
                    # [중요] 상세 정보(제목/초록) 가져오기
                    # OPS API 호출 제한을 피하기 위해 약간의 딜레이 추가
                    time.sleep(0.2) 
                    title, abstract, applicant = self._fetch_patent_details(country, doc_number, kind)
                    
                    # 결과 저장
                    results.append({
                        "source": "EPO",
                        "id": full_id,
                        "title": title if title else f"Patent {full_id}",
                        "abstract": abstract if abstract else "Abstract details not available.",
                        "published_date": date,
                        "url": f"https://worldwide.espacenet.com/publicationDetails/biblio?CC={country}&NR={doc_number}&KC={kind}",
                        "authors": [applicant] if applicant else [],
                        "raw": pub
                    })
                    
                except Exception as ex:
                    print(f"[EPOClient] Parse error for item {i}: {ex}")
                    continue
            
            return results
        except Exception as e:
            print(f"[EPOClient] Fetch Error: {e}")
            return []

    def _fetch_patent_details(self, country, number, kind):
        """
        특허의 상세 정보(제목, 초록)를 가져옵니다.
        List/Dict 구조를 유연하게 처리하고, 영어가 없으면 다른 언어라도 가져오도록 개선됨.
        """
        try:
            # OPS API requires the ID to be a single segment in format 'CC.Number.Kind'
            # Previous version using slashes caused 404s.
            doc_id_str = f"{country}.{number}.{kind}"
            url = f"{self.service_url}/published-data/publication/docdb/{doc_id_str}/biblio"
            
            headers = {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}
            res = requests.get(url, headers=headers, timeout=10)
            
            if res.status_code != 200: 
                # print(f"[EPOClient] Detail fetch failed for {doc_id_str}: {res.status_code}")
                return None, None, None
            
            b_data = res.json()
            
            # 구조가 깊으므로 안전하게 가져오기 (ops: 네임스페이스 주의)
            # 보통 ops:world-patent-data -> exchange-documents -> exchange-document
            wpd = b_data.get('ops:world-patent-data', {})
            eds = wpd.get('exchange-documents', {})
            ed = eds.get('exchange-document', {})
            
            # exchange-document가 리스트일 수 있음 (드물지만)
            if isinstance(ed, list) and len(ed) > 0:
                ed = ed[0]
            
            biblio_data = ed.get('bibliographic-data', {})

            # 1. Title Extraction
            title = None
            titles = biblio_data.get('invention-title', [])
            if isinstance(titles, dict): titles = [titles]
            
            # 우선 영어(@lang='en')를 찾고, 없으면 첫 번째 것을 사용
            for t in titles:
                if t.get('@lang') == 'en':
                    title = t.get('$', None)
                    break
            if not title and titles:
                title = titles[0].get('$', "Unknown Title")
            
            # 2. Abstract Extraction
            abstract = None
            abst_obj = ed.get('abstract', [])
            if isinstance(abst_obj, dict): abst_obj = [abst_obj]
            
            selected_abs = None
            # 우선 영어 초록 찾기
            for a in abst_obj:
                if a.get('@lang') == 'en':
                    selected_abs = a
                    break
            # 영어 없으면 첫 번째 초록 사용
            if not selected_abs and abst_obj:
                selected_abs = abst_obj[0]
                
            if selected_abs:
                p_text = selected_abs.get('p', [])
                # p 태그가 하나면 dict, 여러개면 list
                if isinstance(p_text, dict):
                    abstract = p_text.get('$', '')
                elif isinstance(p_text, list):
                    # 문단 합치기
                    abstract = " ".join([p.get('$', '') for p in p_text if isinstance(p, dict)])
            
            # 3. Applicant Extraction
            applicant = "Unknown"
            parties = biblio_data.get('parties', {})
            applicants = parties.get('applicants', {}).get('applicant', [])
            if isinstance(applicants, dict): applicants = [applicants]
            
            if applicants:
                # 첫 번째 출원인 이름 가져오기
                app_name_obj = applicants[0].get('applicant-name', {}).get('name', {})
                applicant = app_name_obj.get('$', 'Unknown')
                
            return title, abstract, applicant
            
        except Exception as e:
            # 디버깅을 위해 에러 출력 (필요시 주석 처리)
            # print(f"[EPOClient] Detail fetch failed for {country}{number}{kind}: {e}")
            return None, None, None

if __name__ == "__main__":
    client = EPOClient()
    # 테스트용 호출
    # res = client.fetch_patents("liquid cooling")
    # print(res)
