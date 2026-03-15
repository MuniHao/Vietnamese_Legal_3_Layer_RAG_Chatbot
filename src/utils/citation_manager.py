"""
Module to manage invalid citations and automatically update the config
"""
import json
import logging
from pathlib import Path
from typing import List, Set
import re

logger = logging.getLogger(__name__)

class CitationManager:
    """Manage invalid citations and automatically update the configuration"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default path relative to this file
            config_path = Path(__file__).parent / 'vietnamese_text_config.json'
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._excluded_citations: Set[str] = set(self.config.get('excluded_citations', []))
    
    def _load_config(self) -> dict:
        """Load configuration from JSON file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning(f"Config file not found: {self.config_path}")
                return {}
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
    
    def _save_config(self):
        """Save configuration to JSON file"""
        try:
            # Ensure excluded_citations exists in config
            if 'excluded_citations' not in self.config:
                self.config['excluded_citations'] = []
            
            # Update excluded_citations from set
            self.config['excluded_citations'] = sorted(list(self._excluded_citations))
            
            # Save file with pretty formatting
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Config updated: {len(self._excluded_citations)} excluded citations")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def add_invalid_citations(self, invalid_citations: List[str]):
        """Add invalid citations to the excluded list and save to config"""
        if not invalid_citations:
            return
        
        added_count = 0
        for citation in invalid_citations:
            # Normalize citation (lowercase, strip)
            normalized = citation.lower().strip()
            if normalized and normalized not in self._excluded_citations:
                self._excluded_citations.add(normalized)
                added_count += 1
                logger.info(f"Added invalid citation to config: '{citation}'")
        
        if added_count > 0:
            self._save_config()
            logger.info(f"Added {added_count} invalid citations to {self.config_path}")
        else:
            logger.debug("No new invalid citations to add")
    
    def is_excluded(self, citation: str) -> bool:
        """Check whether a citation is excluded"""
        normalized = citation.lower().strip()
        return normalized in self._excluded_citations
    
    def filter_invalid_citations(self, found_citations: List[str]) -> tuple[List[str], List[str]]:
        """
        Filter citations into valid and invalid based on the excluded list
        Returns: (valid_citations, invalid_citations)
        """
        valid = []
        invalid = []
        
        for citation in found_citations:
            if self.is_excluded(citation):
                invalid.append(citation)
            else:
                valid.append(citation)
        
        return valid, invalid
    
    def get_excluded_citations(self) -> List[str]:
        """Get the list of excluded citations"""
        return sorted(list(self._excluded_citations))


# Global instance
_citation_manager = None

def get_citation_manager(config_path: str = None) -> CitationManager:
    """Get the global citation manager instance"""
    global _citation_manager
    if _citation_manager is None:
        _citation_manager = CitationManager(config_path)
    return _citation_manager