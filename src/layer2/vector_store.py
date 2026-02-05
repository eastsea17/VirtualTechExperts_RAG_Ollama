import yaml
import os
from typing import List, Dict, Optional
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document

class VectorStoreManager:
    """
    Manages the Vector Database (ChromaDB) for storing and retrieving
    paper/patent data. Supports expert reuse via metadata tagging.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.persist_directory = self.config['intelligence_engine']['vector_db_path']
        self.collection_name = self.config['intelligence_engine']['collection_name']
        self.embedding_model_name = self.config['ollama']['embedding_model']
        self.base_url = self.config['ollama']['base_url']
        
        self.embeddings = OllamaEmbeddings(
            model=self.embedding_model_name,
            base_url=self.base_url
        )
        
        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )
        
    def add_expert_knowledge(self, papers: List[Dict], expert_id: str, topic: str):
        """
        Ingests papers into the vector store tagged with a specific expert_id.
        Avoids duplicates if the expert_id already exists (check usually done before calling this,
        but idempotent adds are good).
        """
        print(f"[VectorStore] Adding {len(papers)} documents for ExpertID: {expert_id}...")
        
        documents = []
        for paper in papers:
            # Create a rich context string
            page_content = f"Title: {paper['title']}\nAbstract: {paper['abstract']}\nYear: {paper.get('publication_year', 'N/A')}"
            
            metadata = {
                "source": paper.get('source', 'openalex'),
                "expert_id": expert_id,
                "topic": topic,
                "paper_id": paper.get("id"),
                "year": paper.get("publication_year", 0),
                "citations": paper.get("cited_by_count", 0)
            }
            
            documents.append(Document(page_content=page_content, metadata=metadata))
            
        # Add to Chroma
        if documents:
            self.vector_store.add_documents(documents)
            print(f"[VectorStore] Successfully added {len(documents)} chunks.")
            
    def get_retriever(self, expert_id: str, k: int = 5):
        """
        Returns a retriever filtered by the specific expert_id.
        """
        return self.vector_store.as_retriever(
            search_kwargs={
                "k": k,
                "filter": {"expert_id": expert_id}
            }
        )
        
    def expert_exists(self, expert_id: str) -> bool:
        """
        Checks if an expert with this ID already exists in the DB.
        """
        results = self.vector_store.get(where={"expert_id": expert_id}, limit=1)
        exists = len(results['ids']) > 0
        if exists:
            print(f"[VectorStore] Expert '{expert_id}' found in cache.")
        else:
            print(f"[VectorStore] Expert '{expert_id}' not found. Need to build.")
        return exists

    def list_experts(self) -> List[Dict]:
        """
        Scans the DB to find all unique expert_ids and their metadata.
        Returns a list of dicts: {'expert_id': str, 'topic': str, 'doc_count': int}
        
        Note: This effectively scans all metadata, which is fine for local/prototype scale.
        """
        try:
            # Fetch all metadata (Chroma default limit might need adjustment for huge DBs)
            # using get() with only metadatas is efficient enough for thousands of docs
            data = self.vector_store.get(include=["metadatas"])
            metadatas = data.get("metadatas", [])
            
            expert_map = {}
            
            for meta in metadatas:
                if not meta: continue
                e_id = meta.get("expert_id")
                if not e_id: continue
                
                if e_id not in expert_map:
                    expert_map[e_id] = {
                        "expert_id": e_id,
                        "topic": meta.get("topic", "Unknown"),
                        "doc_count": 0,
                        "articles": 0,
                        "patents": 0,
                        "news": 0
                    }
                expert_map[e_id]["doc_count"] += 1
                
                source = meta.get("source", "").lower()
                if "openalex" in source:
                    expert_map[e_id]["articles"] += 1
                elif "uspto" in source or "epo" in source:
                    expert_map[e_id]["patents"] += 1
                elif "tavily" in source or "news" in source:
                    expert_map[e_id]["news"] += 1
                else: 
                     # Fallback for older data or other sources
                     if "patent" in source:
                         expert_map[e_id]["patents"] += 1
                     else:
                         expert_map[e_id]["articles"] += 1
                
            return list(expert_map.values())
        except Exception as e:
            print(f"[VectorStore] Error listing experts: {e}")
            return []

    def get_expert_topic(self, expert_id: str) -> Optional[str]:
        """
        Retrieves the original research topic for a given expert_id.
        """
        results = self.vector_store.get(where={"expert_id": expert_id}, limit=1, include=["metadatas"])
        if results and results['metadatas'] and len(results['metadatas']) > 0:
            return results['metadatas'][0].get('topic')
        return None

    def delete_expert(self, expert_id: str) -> bool:
        """
        Deletes all documents associated with the expert_id.
        """
        try:
            # Check existence first
            if not self.expert_exists(expert_id):
                return False
                
            print(f"[VectorStore] Deleting expert: {expert_id}...")
            self.vector_store.delete(where={"expert_id": expert_id})
            print(f"[VectorStore] Successfully deleted expert: {expert_id}")
            return True
        except Exception as e:
            print(f"[VectorStore] Error deleting expert: {e}")
            return False

    def generate_next_expert_id(self) -> str:
        """
        Scans existing expert IDs, finds the highest number N in 'expert_N',
        and returns 'expert_{N+1}'. Defaults to 'expert_1'.
        """
        try:
            experts = self.list_experts()
            max_id = 0
            for exp in experts:
                eid = exp.get('expert_id', '')
                # Check for format 'expert_N'
                if eid.startswith('expert_') and eid[7:].isdigit():
                    try:
                        num = int(eid[7:])
                        if num > max_id:
                            max_id = num
                    except ValueError:
                        pass
            
            return f"expert_{max_id + 1}"
        except Exception as e:
            print(f"[VectorStore] Error generating next ID: {e}")
            # Fallback to random if something breaks
            import uuid
            return f"expert_{uuid.uuid4().hex[:8]}"

if __name__ == "__main__":
    # Test
    vsm = VectorStoreManager()
    print("Vector Store Initialized.")
