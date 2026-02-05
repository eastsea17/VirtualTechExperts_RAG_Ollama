# 가상 기술 전문가 및 R&D 시스템 (VTE-R&D) V2.7

## 개요

VTE-R&D는 기술 연구 및 전략 수립을 자동화하기 위해 설계된 고급 AI 에이전트 시스템입니다. 이 시스템은 과학 논문, 특허, 그리고 **실시간 시장 뉴스**를 자율적으로 수집하고, 다양한 페르소나(낙관론자, 회의론자, 경쟁자, 규제 담당자)를 통해 결과를 토론하며, 전체 토론 기록이 포함된 포괄적인 HTML 보고서를 생성합니다.

## 주요 기능 (V2.7 업데이트)

- **다중 소스 데이터 수집**:
  - **OpenAlex**: 학술 논문 (API 연동).
  - **PatentsView (USPTO)**: 미국 특허.
  - **EPO (유럽 특허청)**: 유럽 특허.
  - **Tavily (신규)**: 실시간 시장 뉴스 및 비즈니스 인사이트.
- **순차적 전문가 ID**: 전문가 ID가 읽기 쉬운 순차적 ID (예: `expert_1`, `expert_2`)로 부여됩니다.
- **상세 전문가 관리**: 각 전문가별 문서 구성(논문/특허/뉴스)을 상세히 확인할 수 있습니다.
- **토론 턴 제어**: `--turn` 옵션을 통해 모든 모드에서 토론 길이를 엄격하게 제어합니다.
- **고급 토론 그래프**:
  - **모드 A (순차적 루프)**: 낙관론자 <-> 회의론자 반복.
  - **모드 B (라운드 로빈)**: 4명의 페르소나 순환 토론.
  - **모드 C (합의형)**: 합의 도출을 위한 반복 루프.
- **상세 보고서**: 데이터 통계(뉴스 포함)와 전체 토론 기록이 포함된 HTML 보고서를 생성합니다.

## 필수 조건

- Python 3.10 이상
- [Ollama](https://ollama.ai/) 설치 및 실행 중.
- API 키:
  - **Tavily** (뉴스 검색을 위해 필수).
  - **USPTO/EPO** (선택 사항이지만 권장됨).

## 설치 방법

1. **저장소 복제**:

   ```bash
   git clone <repo_url>
   cd 260205_VirtualTechExperts_Ollama
   ```

2. **의존성 설치**:

   ```bash
   pip install -r requirements.txt
   ```

3. **환경 설정**:
   - `.env` 파일 생성:

     ```bash
     USPTO_API_KEY=your_key
     EPO_CONSUMER_KEY=your_key
     EPO_CONSUMER_SECRET=your_secret
     TAVILY_API_KEY=tvly-xxxxxxxxxxxx
     ```

   - `config/config.yaml` 파일에서 모델 설정 및 검색 한도(`fetch_limit`)를 조정합니다.

## 사용 방법

연구 주제와 함께 메인 스크립트를 실행합니다:

```bash
python main.py "Liquid Cooling for Data Centers" --mode c --turn 5
```

### 인자 (Arguments)

- `topic`: 연구 주제.
- `--mode`:
  - `a`: 순차적 루프 (표준)
  - `b`: 라운드 로빈 (포괄적)
  - `c`: 합의형 (심층 분석)
- `--turn`: 페르소나당 최대 턴 수 재정의 (예: `--turn 5`는 화자당 5회 발언).

### 가상 전문가 관리

`main.py`를 통해 통합 관리됩니다:

1. **저장된 전문가 목록 조회 (상세 통계 포함)**:

   ```bash
   python main.py --list
   ```

   *출력 예시:*

   ```text
   Expert ID       | Topic                | Art.  | Pat.  | News  | Total
   -----------------------------------------------------------------------
   expert_1        | Hydrogen Generation  | 150   | 50    | 5     | 205
   expert_2        | Agentic AI           | 100   | 0     | 10    | 110
   ```

2. **전문가 재사용 실행**:

   ```bash
   python main.py --expert_id expert_1 --mode b
   ```

3. **전문가 삭제**:

   ```bash
   python main.py --delete expert_1
   ```

## 시스템 아키텍처

1. **Layer 1: 데이터 수집**
   - 논문(OpenAlex), 특허(USPTO/EPO), **뉴스(Tavily)** 수집.
2. **Layer 2: 인텔리전스 엔진**
   - 문서를 ChromaDB에 벡터화 저장.
   - 순차적 ID 할당 (`expert_1`).
3. **Layer 3: 토론 시뮬레이션**
   - 벡터 스토어 컨텍스트(`retrieve_top_k`)를 활용하여 에이전트 토론.
   - `max_turns` 설정에 따라 반복 루프 실행.
4. **Layer 4: 보고서 작성**
   - HTML 보고서 및 스타일이 적용된 대화 기록 생성.

### 시스템 흐름도

```mermaid
graph TD
    User["사용자 입력: 주제"] --> QE["쿼리 확장기"]
    QE -->|키워드| APIs{"데이터 수집"}
    APIs -->|논문| OA["OpenAlex"]
    APIs -->|미국 특허| USPTO["USPTO V1"]
    APIs -->|유럽 특허| EPO["EPO OPS"]
    APIs -->|시장 뉴스| Tavily["Tavily API"]
    OA --> Combined["데이터 통합"]
    USPTO --> Combined
    EPO --> Combined
    Tavily --> Combined
    Combined --> VS["벡터 저장소 (ChromaDB)"]
    VS --> Debate["토론 시뮬레이션"]
    Debate -->|"루프 (모드 A/B/C)"| Agents["페르소나: 낙관론자, 회의론자 등"]
    Agents -->|대화 기록| RG["보고서 생성기"]
    RG --> HTML["HTML 보고서"]
```

## 구성 (`config.yaml`)

- **데이터 수집**: OpenAlex, USPTO, EPO, **Tavily**의 `fetch_limit` 설정.
- **인텔리전스**: `retrieve_top_k` (컨텍스트 깊이).
- **토론 규칙**: `max_turns_per_persona` 및 `max_tokens_per_turn`.

## 🖥️ Streamlit 웹 인터페이스 (신규!)

웹 기반 UI를 실행하여 인터랙티브한 경험을 제공합니다:

```bash
streamlit run streamlit_app.py
```

**주요 기능:**

- **사이드바 설정**: 모든 설정 파라미터를 실시간으로 조정 가능.
- **원클릭 워크플로우**: 주제를 입력하고 "Run Analysis"를 클릭하면 전체 파이프라인 실행.
- **실시간 진행 상황**: 4개 레이어의 분석 진행 상황을 실시간 확인.
- **실시간 토론 기록**: 각 페르소나의 의견을 색상 코드 스타일로 확인.
- **보고서 미리보기 및 다운로드**: 브라우저에서 직접 HTML 보고서 확인 및 다운로드.

![Streamlit UI](streamlit_screen.png)

## 주요 기능 (V2.2 업데이트)

- **다중 소스 데이터 수집**:
  - **OpenAlex**: 학술 논문 (API 연동).
  - **PatentsView (USPTO)**: 미국 특허 (API 키 필요).
  - **EPO (유럽 특허청)**: 유럽 특허 (API 키 필요).
- **보안 설정**: API 키는 `.env` 파일을 통해 안전하게 관리됩니다.
- **지능형 쿼리 확장**: LLM을 사용하여 사용자의 광범위한 주제를 정밀한 불리언 검색 쿼리로 변환합니다.
- **고급 토론 그래프 (LangGraph)**:
  - **모드 A (순차적)**: 제안 -> 비판 -> 종합.
  - **모드 B (병렬적)**: 경쟁자, 회의론자, 규제 담당자의 동시 비판.
  - **모드 C (합의형)**: 합의에 도달하기 위한 반복적인 상호작용.
- **실시간 가시성**: 토론 내용이 터미널에 실시간으로 스트리밍됩니다.
- **상세 보고서**: 데이터 통계와 스타일이 적용된 전체 토론 기록 부록이 포함된 HTML 보고서를 생성합니다.
- **모델 사용자 정의**: Ollama 로컬 모델 및 클라우드 엔드포인트(예: DeepSeek)를 지원합니다.

## 필수 조건

- Python 3.10 이상
- [Ollama](https://ollama.ai/) 설치 및 실행 중.
- USPTO/EPO API 키 (선택 사항이지만 전체 데이터 커버리지를 위해 권장).

## 설치 방법

1. **저장소 복제**:

   ```bash
   git clone <repo_url>
   cd 260205_VirtualTechExperts_Ollama
   ```

2. **의존성 설치**:

   ```bash
   pip install -r requirements.txt
   ```

3. **환경 설정**:
   - `.env.example` 파일의 이름을 `.env`로 변경(또는 새로 생성)하고 키를 입력합니다:

     ```bash
     USPTO_API_KEY=your_key_here
     EPO_CONSUMER_KEY=your_key_here
     EPO_CONSUMER_SECRET=your_secret_here
     ```

   - `config/config.yaml` 파일을 편집하여 선호하는 Ollama 모델과 토론 규칙을 설정합니다.

## 사용 방법

연구 주제와 함께 메인 스크립트를 실행합니다:

```bash
python main.py "Liquid Cooling for Data Centers" --mode a
```

### 인자 (Arguments)

- `topic`: 연구 주제 (예: "Generative AI", "Solid State Batteries").
- `--mode`: 토론 구조.
  - `a`: 순차적 (표준)
  - `b`: 병렬적 (포괄적)
  - `c`: 합의형 (심층 분석)
- `--turn`: (선택) 최대 토론 턴 수 재정의 (예: `--turn 5`).

### 전문가 지식 관리 (V2.5 통합)

1. **저장된 전문가 목록 조회**:

   ```bash
   python main.py --list
   ```

2. **전문가 재사용 실행**:

   ```bash
   python main.py --expert_id exp_12a1de9c --mode b
   ```

3. **전문가 삭제 (삭제)**:

   ```bash
   python main.py --delete exp_12a1de9c
   ```

## 시스템 아키텍처

1. **Layer 1: 데이터 수집**
   - 사용자 쿼리 확장.
   - OpenAlex, USPTO, EPO에서 글로벌 문서 수집.
2. **Layer 2: 인텔리전스 엔진**
   - 문서 벡터화 (ChromaDB + Ollama Embeddings).
   - 전문가 지식 베이스 생성.
3. **Layer 3: 토론 시뮬레이션 (LangGraph)**
   - 페르소나(낙관론자, 회의론자 등)가 벡터 저장소에서 증거를 검색.
   - 에이전트들이 특정 논문/특허를 인용하며 주제에 대해 토론.
4. **Layer 4: 보고서 작성**
   - 토론 내용을 전략적 임원 보고서(HTML)로 요약.
   - 참조를 위해 스타일이 적용된 전체 토론 기록을 부록으로 첨부.

### 시스템 흐름도

```mermaid
graph TD
    User["사용자 입력: 주제"] --> QE["쿼리 확장기"]
    QE -->|키워드| APIs{"데이터 수집"}
    APIs -->|논문| OA["OpenAlex"]
    APIs -->|미국 특허| USPTO["USPTO V1"]
    APIs -->|유럽 특허| EPO["EPO OPS"]
    OA --> Combined["데이터 통합"]
    USPTO --> Combined
    EPO --> Combined
    Combined --> VS["벡터 저장소 (ChromaDB)"]
    VS --> Debate["토론 시뮬레이션 (LangGraph)"]
    Debate -->|"모드 A/B/C"| Agents["페르소나: 낙관론자, 회의론자 등"]
    Agents -->|대화 기록| RG["보고서 생성기"]
    RG --> HTML["HTML 보고서 + 부록"]
```

## 사용자 정의

- **페르소나**: `config/personas.yaml`을 수정하여 에이전트의 성격을 변경할 수 있습니다 (예: "일론 머스크 스타일" vs "보수적 엔지니어").
- **모델**: `config/config.yaml`에서 LLM을 변경할 수 있습니다 (모든 Ollama 호환 모델 지원).
