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

if __name__ == "__main__":
    # Test
    rg = ReportGenerator()
    print("Report Generator Initialized.")
