"""
Tool Selector Agent
Intelligently selects relevant tools from the large tool set
"""

from typing import Dict, Any, List
from .base_agent import BaseAgent
from .context_manager import AgentMessage


class ToolSelectorAgent(BaseAgent):
    """
    Tool Selector Agent: Intelligent Tool Filtering
    - Receives step description and keywords from Master
    - Filters 152 tools down to 5-10 most relevant
    - Uses keyword matching and semantic understanding
    """
    
    def __init__(self, model: str, console, context_manager, tool_manager):
        system_prompt = """You are a Tool Selection Agent for penetration testing and security analysis.

Your role:
1. Receive a task step description and keywords
2. Select 5-10 most relevant tools from the available set
3. Prioritize tools that directly match the task requirements

Selection Criteria:
- Tool name/description matches keywords
- Tool category aligns with task type (scanning, exploitation, information gathering)
- Tool is commonly used for similar tasks in penetration testing

IMPORTANT: You MUST output ONLY the tool numbers, nothing else.
Example output: "1, 3, 5, 7, 9"

DO NOT include explanations or any other text in your response."""

        super().__init__(
            name="ToolSelectorAgent",
            model=model,
            console=console,
            context_manager=context_manager,
            system_prompt=system_prompt
        )
        self.tool_manager = tool_manager
        
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Select relevant tools for a specific step
        
        Input: {
            "step_id": 1,
            "description": "Scan target for open ports",
            "keywords": ["nmap", "port", "scan"]
        }
        Output: {
            "step_id": 1,
            "selected_tools": ["hexstrike-ai.nmap_scan", ...],
            "tool_details": [...]
        }
        """
        step_id = input_data["step_id"]
        description = input_data["description"]
        keywords = input_data.get("keywords", [])
        
        self.log(f"Selecting tools for Step {step_id}: {description}")
        
        # Get all available tools
        all_tools = self.tool_manager.get_enabled_tool_objects()
        
        # Stage 1: Fast keyword filtering (reduce to ~20-30 tools)
        keyword_matched = self._keyword_filter(all_tools, keywords, description)
        
        self.log(f"Keyword filter: {len(all_tools)} → {len(keyword_matched)} tools", "debug")
        
        # Debug: show top matched tools with scores for transparency
        if keyword_matched and len(keyword_matched) > 0:
            top_tools = [t.name for t in keyword_matched[:5]]
            self.log(f"Top matched tools: {', '.join(top_tools)}", "debug")
        
        # If keyword filter found nothing, use all tools
        if len(keyword_matched) == 0:
            self.log("⚠ Keyword filter found no matches, using all tools for LLM selection", "warning")
            keyword_matched = all_tools
        
        # Stage 2: LLM-based intelligent selection (reduce to 5-10 tools)
        # Due to LLM returning empty responses, temporarily use keyword filter results directly
        if len(keyword_matched) > 8:
            # Use top 8 from keyword filter
            self.log("Using top 8 tools from keyword filter (LLM selection disabled due to empty responses)", "info")
            final_selected = keyword_matched[:8]
        elif len(keyword_matched) > 0:
            # Use all keyword matched tools
            final_selected = keyword_matched
        else:
            # Fallback: use top 8 tools by name relevance
            self.log("⚠ No tools matched, using first 8 tools", "warning")
            final_selected = all_tools[:8]
            
        self.log(f"✓ Selected {len(final_selected)} tools for execution", "success")
        
        # Log selected tool names for debugging
        if final_selected:
            tool_names = [t.name for t in final_selected[:5]]  # Show first 5
            more = f" +{len(final_selected)-5} more" if len(final_selected) > 5 else ""
            self.log(f"  Tools: {', '.join(tool_names)}{more}", "debug")
        
        # Update step in context
        step = self.context_manager.get_step(step_id)
        if step:
            step.assigned_tools = [tool.name for tool in final_selected]
            
        # Send message to Executor Agent
        message = AgentMessage(
            from_agent=self.name,
            to_agent="ExecutorAgent",
            message_type="tool_selection",
            content={
                "step_id": step_id,
                "selected_tools": [tool.name for tool in final_selected],
                "tool_objects": final_selected  # Full tool objects for executor
            }
        )
        self.context_manager.add_message(message)
        
        return {
            "step_id": step_id,
            "selected_tools": [tool.name for tool in final_selected],
            "tool_count": len(final_selected)
        }
        
    def _keyword_filter(self, tools: List, keywords: List[str], description: str) -> List:
        """
        Fast keyword-based filtering
        Matches tool name, description, and category
        """
        matched_tools = []
        
        # Combine keywords and description words
        search_terms = set([k.lower() for k in keywords])
        desc_words = description.lower().split()
        search_terms.update([w for w in desc_words if len(w) > 3])
        
        self.log(f"Search terms: {', '.join(sorted(search_terms))}", "debug")
        
        # Add common variations and related terms
        term_expansions = {
            'nmap': ['scan', 'port', 'network', 'discovery', 'host'],
            'scan': ['nmap', 'port', 'detect', 'probe', 'discovery'],
            'cve': ['vulnerability', 'exploit', 'vuln', 'poc', 'nuclei', 'attack'],
            'exploit': ['vulnerability', 'attack', 'poc', 'cve', 'rce', 'execute'],
            'vulnerability': ['vuln', 'exploit', 'cve', 'weakness', 'nuclei', 'detect'],
            'nuclei': ['vulnerability', 'scan', 'cve', 'template', 'detect'],
            'apache': ['solr', 'tomcat', 'web', 'server'],
            'solr': ['apache', 'search', 'lucene'],
            # Web/HTTP request related terms
            'curl': ['http', 'request', 'web', 'get', 'post', 'api', 'endpoint', 'httpx'],
            'http': ['curl', 'request', 'web', 'get', 'post', 'api', 'httpx', 'fetch'],
            'request': ['curl', 'http', 'web', 'get', 'post', 'api', 'httpx'],
            'web': ['http', 'curl', 'request', 'httpx', 'browser', 'url'],
            'api': ['http', 'curl', 'request', 'endpoint', 'rest', 'httpx'],
            'httpx': ['http', 'curl', 'request', 'probe', 'web'],
            'actuator': ['springboot', 'spring', 'endpoint', 'http', 'api'],
            'springboot': ['spring', 'actuator', 'java', 'web', 'http'],
            'spring': ['springboot', 'actuator', 'java', 'web'],
        }
        
        expanded_terms = set(search_terms)
        for term in search_terms:
            if term in term_expansions:
                expanded_terms.update(term_expansions[term])
        
        # Special handling for CVE numbers
        cve_pattern = r'cve[-_]?\d{4}[-_]?\d+'
        import re
        cve_matches = re.findall(cve_pattern, description.lower())
        if cve_matches:
            expanded_terms.update(cve_matches)
        
        for tool in tools:
            tool_text = f"{tool.name} {tool.description}".lower()
            
            # Check if any search term appears in tool text
            score = 0
            
            # Prioritize exact matches in tool name (highest priority)
            tool_name_lower = tool.name.lower()
            for term in search_terms:
                if term in tool_name_lower:
                    # Very high score for original keywords in tool name
                    score += 10
            
            # Check for matches in full tool text
            for term in expanded_terms:
                if term in tool_text:
                    # Higher score for exact keyword matches
                    score += 5 if term in search_terms else 1
            
            # Bonus for tools that match multiple original keywords
            match_count = sum(1 for term in search_terms if term in tool_text)
            score += match_count * 3
            
            if score > 0:
                matched_tools.append((tool, score))
                
        # Sort by score and return top matches
        matched_tools.sort(key=lambda x: x[1], reverse=True)
        
        # Debug: log top matches with scores
        if matched_tools:
            self.log(f"Top 5 matches by score:", "debug")
            for tool, score in matched_tools[:5]:
                self.log(f"  {tool.name}: score={score}", "debug")
        
        # Return top 10 or all if less (reduced from 30 to improve precision)
        return [tool for tool, score in matched_tools[:10]]
        
    async def _llm_select(
        self,
        candidate_tools: List,
        description: str,
        keywords: List[str],
        target_count: int = 8
    ) -> List:
        """
        Use LLM to intelligently select final tools from candidates
        """
        # Build tool list for LLM
        tool_list = []
        for i, tool in enumerate(candidate_tools, 1):
            tool_list.append(f"{i}. {tool.name}: {tool.description[:100]}")
            
        tool_text = "\n".join(tool_list)
        
        prompt = f"""Task: {description}
Keywords: {', '.join(keywords)}

Select the top {target_count} most relevant tools for this specific task.

Available Tools ({len(candidate_tools)} total):
{tool_text}

Instructions:
- Choose tools whose names or descriptions closely match the task
- For scanning tasks, prefer tools with "scan", "nmap", "port" in their name
- For CVE exploitation, prefer tools with "exploit", "cve", "vulnerability" in their name
- Output ONLY numbers separated by commas (e.g., "1, 3, 5, 7")
- Select exactly {target_count} tools or fewer if less are relevant

Your selection (numbers only):"""

        try:
            response = await self.call_model(prompt, max_tokens=1000)
            self.log(f"LLM raw response: '{response.strip()}'", "debug")
            
            # Try to extract numbers from response
            import re
            
            # Clean response - remove any text, keep only numbers and commas
            cleaned = re.sub(r'[^\d,\s]', '', response)
            numbers = re.findall(r'\d+', cleaned)
            
            self.log(f"Extracted numbers: {numbers}", "debug")
            
            if not numbers:
                self.log(f"⚠ No numbers found in LLM response, using fallback", "warning")
                return candidate_tools[:target_count]
            
            selected_indices = [int(n) - 1 for n in numbers if 0 < int(n) <= len(candidate_tools)]
            
            # Limit to target count
            selected_indices = selected_indices[:target_count]
            
            selected = [candidate_tools[i] for i in selected_indices]
            
            self.log(f"LLM selection: {len(candidate_tools)} → {len(selected)} tools", "debug")
            
            # If LLM returned nothing, use fallback
            if not selected:
                self.log("⚠ No valid tools selected by LLM, using top matches", "warning")
                return candidate_tools[:target_count]
            
            return selected
            
        except Exception as e:
            self.log(f"LLM selection failed: {e}, using top {target_count}", "warning")
            # Fallback: return first N tools from keyword filter
            return candidate_tools[:target_count]
