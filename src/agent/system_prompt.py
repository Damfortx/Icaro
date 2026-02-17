"""
Dynamic System Prompt Manager for Icaro Trading Bot.
Handles loading, updating, and saving the AI's system prompt.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.config import get_config


class SystemPromptManager:
    """Manages the dynamic system prompt that the AI can modify."""
    
    def __init__(self):
        self.config = get_config()
        self.prompt_path = self.config.data_dir / "system_prompt.md"
        self._cached_prompt: Optional[str] = None
        self._last_loaded: Optional[datetime] = None
    
    def load(self, force_reload: bool = False) -> str:
        """Load the system prompt from file."""
        # Use cache if available and recent (within 5 seconds)
        if (not force_reload and 
            self._cached_prompt is not None and 
            self._last_loaded is not None):
            age = (datetime.now() - self._last_loaded).total_seconds()
            if age < 5:
                return self._cached_prompt
        
        with open(self.prompt_path, 'r', encoding='utf-8') as f:
            self._cached_prompt = f.read()
        
        self._last_loaded = datetime.now()
        return self._cached_prompt
    
    def save(self, content: str) -> None:
        """Save the system prompt to file."""
        with open(self.prompt_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self._cached_prompt = content
        self._last_loaded = datetime.now()
    
    def append_learning(self, learning: str, adjustment: str) -> None:
        """
        Append a new learning to the Learnings Log section.
        
        Args:
            learning: What was learned from trading
            adjustment: How the strategy should be adjusted
        """
        prompt = self.load(force_reload=True)
        
        # Find the Learnings Log section
        learnings_marker = "## Learnings Log"
        performance_marker = "## Performance Tracking"
        
        if learnings_marker not in prompt:
            return  # Section not found
        
        # Create the new learning entry
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n**[{timestamp}]**\n- Learning: {learning}\n- Adjustment: {adjustment}\n"
        
        # Insert after the learnings marker and any existing content
        parts = prompt.split(learnings_marker)
        if len(parts) == 2:
            # Find where to insert (before the next section)
            after_learnings = parts[1]
            
            if performance_marker in after_learnings:
                perf_parts = after_learnings.split(performance_marker)
                # Insert learning before performance section
                new_after = perf_parts[0].rstrip() + entry + "\n\n---\n\n" + performance_marker + perf_parts[1]
            else:
                new_after = after_learnings.rstrip() + entry
            
            new_prompt = parts[0] + learnings_marker + new_after
            self.save(new_prompt)
    
    def update_performance(
        self, 
        total_trades: int,
        win_rate: float,
        best_trade: str,
        current_pnl: float
    ) -> None:
        """Update the Performance Tracking section."""
        prompt = self.load(force_reload=True)
        
        # Build new performance section
        perf_content = f"""## Performance Tracking
<!-- Auto-updated with each significant trade -->

- **Total Trades**: {total_trades}
- **Win Rate**: {win_rate:.1f}%
- **Best Trade**: {best_trade}
- **Current P&L**: {current_pnl:+.2f}%

---"""
        
        # Replace existing performance section
        pattern = r"## Performance Tracking.*?(?=\n---|\n## |$)"
        new_prompt = re.sub(pattern, perf_content, prompt, flags=re.DOTALL)
        
        self.save(new_prompt)
    
    def add_recent_decision(self, decision: str, outcome: str) -> None:
        """
        Add a decision to Recent Decisions section (keep last 5).
        
        Args:
            decision: Description of the decision made
            outcome: Result of the decision
        """
        prompt = self.load(force_reload=True)
        
        decisions_marker = "## Recent Decisions"
        
        if decisions_marker not in prompt:
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- [{timestamp}] {decision} → {outcome}"
        
        # Find existing decisions
        parts = prompt.split(decisions_marker)
        if len(parts) != 2:
            return
        
        after_decisions = parts[1]
        
        # Parse existing decision lines
        lines = after_decisions.strip().split('\n')
        decision_lines = [l for l in lines if l.strip().startswith('-')]
        
        # Keep only last 4 and add new one
        decision_lines = decision_lines[-4:] if len(decision_lines) >= 4 else decision_lines
        decision_lines.append(entry)
        
        # Rebuild section
        new_section = decisions_marker + "\n<!-- Keep last 5 decisions for context -->\n\n"
        new_section += '\n'.join(decision_lines)
        
        new_prompt = parts[0] + new_section
        self.save(new_prompt)


# Singleton instance
_manager: Optional[SystemPromptManager] = None

def get_prompt_manager() -> SystemPromptManager:
    """Get the global system prompt manager instance."""
    global _manager
    if _manager is None:
        _manager = SystemPromptManager()
    return _manager
