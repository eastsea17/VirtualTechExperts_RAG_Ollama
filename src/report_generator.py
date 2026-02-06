import yaml
import os
import datetime
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

class ReportGenerator:
    """
    Generates an HTML report of the debate history.
    Uses 'deepseek-v3.1:671b-cloud' (or configured model) for summarization.
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        self.output_dir = "results"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Use the specific model requested for reporting
        self.model_name = self.config.get('reporting', {}).get('model', 'deepseek-v3.1:671b-cloud')
        self.base_url = self.config['ollama']['base_url']
        
        self.llm = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=0.3
        )

    def generate_report(self, debate_state: dict, data_stats: dict = None):
        """
        Takes the final debate state and produces a formatted HTML report.
        """
        topic = debate_state.get('topic', 'Unknown Topic')
        messages = debate_state.get('messages', [])
        
        print(f"[ReportGenerator] Generating report for '{topic}' using {self.model_name}...")
        
        # 1. Prepare Content for LLM
        transcript = ""
        for msg in messages:
            role = "AI" if msg.type == 'ai' else "User/System"
            transcript += f"[{role}]: {msg.content}\n\n"
            
        stats_text = "No data statistics provided."
        if data_stats:
            stats_text = "\n".join([f"- {k}: {v} documents" for k, v in data_stats.items()])
            
        # 2. visual_summary Prompt
        prompt = f"""
        You are an expert technical writer.
        Based on the following debate transcript about "{topic}", create a comprehensive HTML report.
        
        DATA SOURCES USED:
        {stats_text}
        
        TRANSCRIPT:
        {transcript[:15000]} # Limit char count
        
        REQUIREMENTS:
        1. Output pure HTML code.
        2. Use modern, professional styling (CSS inside <style>).
        3. Sections:
           - Executive Summary
           - Data Source Overview (Visual presentation of the data stats provided above)
           - Key Arguments (Pros/Cons)
           - Critical Issues (Risks, Regulations)
           - Final Verdict
           - Full Debate Statistics (Turns, Participants)
        4. Highlight the "Winner" or "Consensus" clearly.
        """
        
        users_msg = [HumanMessage(content=prompt)]
        
        try:
            print("   > Thinking... (This may take a minute for 671b model)... ", end="", flush=True)
            response = self.llm.invoke(users_msg)
            print("Done!")
            html_content = response.content
            
            # 3. Save to File
            safe_topic = "".join([c if c.isalnum() else "_" for c in topic]).strip("_")
            # Limit length and remove duplicate underscores
            import re
            safe_topic = re.sub(r'_+', '_', safe_topic)[:50]
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.output_dir}/{timestamp}_{safe_topic}.html"
            
            # Remove markdown code blocks if present
            # Remove markdown code blocks if present
            html_content = html_content.replace("```html", "").replace("```", "")
            
            # --- Append Raw Debate Transcript ---
            import markdown
            
            transcript_html = """
            <hr>
            <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">Appendix: Full Debate Transcript</h2>
            <div style='background:#f9f9f9; padding:20px; border-radius:8px; border: 1px solid #e0e0e0;'>
            """
            
            for msg in messages:
                # Use the 'name' attribute if available, otherwise guess based on type
                if hasattr(msg, 'name') and msg.name:
                    speaker = msg.name
                else:
                    speaker = "System / Moderator" if msg.type == 'ai' else "System"
                
                # Check for specific speakers to add icons or colors
                color = "#34495e" # default dark
                icon = "👤"
                if "Optimist" in speaker: 
                    color = "#27ae60" # Green
                    icon = "🚀"
                elif "Skeptic" in speaker: 
                    color = "#c0392b" # Red
                    icon = "🛡️"
                elif "Competitor" in speaker:
                    color = "#d35400" # Orange
                    icon = "⚔️"
                elif "Maestro" in speaker or "Mod" in speaker:
                    color = "#8e44ad" # Purple
                    icon = "⚖️"
                
                # Convert Markdown to HTML
                content_html = markdown.markdown(msg.content)
                
                transcript_html += f"""
                <div style="margin-bottom: 25px;">
                    <div style="font-weight: bold; font-size: 1.1em; color: {color}; margin-bottom: 5px;">
                        {icon} {speaker}
                    </div>
                    <div style="background: white; padding: 15px; border-left: 4px solid {color}; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        {content_html}
                    </div>
                </div>
                """
            
            transcript_html += "</div>"
            
            # Insert before body end if exists, else append
            if "</body>" in html_content:
                html_content = html_content.replace("</body>", f"{transcript_html}</body>")
            else:
                html_content += transcript_html
            
            with open(filename, 'w') as f:
                f.write(html_content)
                
            print(f"[ReportGenerator] Report saved to: {filename}")
            return filename
            
        except Exception as e:
            print(f"[ReportGenerator] Failed to generate report: {e}")
            return None

    def export_data_collection_csv(self, gathered_data: list, topic: str) -> str:
        """
        Exports the gathered raw data (Papers, Patents, News) to a CSV file.
        Useful for auditing what the agents actually found.
        """
        if not gathered_data:
            return None
            
        import csv
        
        # Normalize Data
        normalized = []
        for item in gathered_data:
            # Determine Source Type based on available keys or explicit 'source' key
            source_type = item.get('source', 'Unknown')
            
            # Simple heuristic if 'source' key is missing or generic
            if source_type == 'Unknown':
               if 'patent_number' in item: source_type = 'USPTO'
               elif 'publication_number' in item: source_type = 'EPO'
               elif 'id' in item and 'openalex' in str(item.get('id', '')): source_type = 'OpenAlex'
               elif 'url' in item: source_type = 'Tavily'
            
            row = {
                "Source": source_type,
                "Type": "Unknown",
                "ID": "N/A",
                "Title": "N/A",
                "Date": "N/A",
                "Abstract": "N/A",
                "Link": "N/A"
            }
            
            # --- Normalization Logic ---
            # OpenAlex Papers
            if source_type == "OpenAlex" or (item.get('id') and 'openalex' in str(item.get('id'))):
                row["Source"] = "OpenAlex"
                row["Type"] = "Paper"
                row["ID"] = item.get('id', 'N/A')
                row["Title"] = item.get('title', 'N/A')
                row["Date"] = str(item.get('publication_year', 'N/A'))
                row["Abstract"] = str(item.get('abstract', ''))[:500] 
                row["Link"] = item.get('doi', item.get('id', ''))

            # EPO Patents
            elif source_type == "EPO" or 'epo' in source_type.lower():
                row["Source"] = "EPO"
                row["Type"] = "Patent"
                row["ID"] = item.get('id', 'N/A')
                row["Title"] = item.get('title', 'N/A')
                row["Date"] = item.get('published_date', 'N/A')
                row["Abstract"] = item.get('abstract', 'N/A')[:500]
                if item.get('url'):
                     row["Link"] = item.get('url')
                elif item.get('id'):
                     try:
                        parts = item.get('id','').split('.')
                        if len(parts) >= 3:
                            row["Link"] = f"https://worldwide.espacenet.com/publicationDetails/biblio?CC={parts[0]}&NR={parts[1]}&KC={parts[2]}"
                     except: pass
            
            # USPTO Patents
            elif source_type == "USPTO" or 'patent_number' in item:
                row["Source"] = "USPTO"
                row["Type"] = "Patent"
                row["ID"] = item.get('patent_number', 'N/A')
                row["Title"] = item.get('title', 'N/A')
                row["Date"] = item.get('date', 'N/A')
                row["Abstract"] = item.get('abstract', 'N/A')[:500]
                row["Link"] = f"https://patents.google.com/patent/US{item.get('patent_number','')}"

            # Tavily News
            elif source_type == "Tavily" or 'content' in item:
                row["Source"] = "Tavily"
                row["Type"] = "News"
                row["ID"] = "N/A"
                row["Title"] = item.get('title', 'N/A')
                row["Date"] = item.get('published_date', 'N/A')
                row["Abstract"] = item.get('content', 'N/A')[:500]
                row["Link"] = item.get('url', 'N/A')
            
            normalized.append(row)

        # Generate Filename
        safe_topic = "".join([c if c.isalnum() else "_" for c in topic]).strip("_")
        import re
        safe_topic = re.sub(r'_+', '_', safe_topic)[:50]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.output_dir}/raw_data_{timestamp}_{safe_topic}.csv"

        # Write CSV
        if normalized:
            keys = normalized[0].keys()
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(normalized)
            print(f"[ReportGenerator] Raw Data Exported: {filename}")
            return filename
        return None

if __name__ == "__main__":
    # Test
    rg = ReportGenerator()
    print("Report Generator Initialized.")
