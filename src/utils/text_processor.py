"""
Vietnamese Text Processing Module
Process Vietnamese text with the following capabilities:
- Detect important phrases
- Remove stop words
- Remove generic terms
- Automatically detect phrases using patterns
"""
import json
import re
import os
from pathlib import Path
from typing import List, Set, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class VietnameseTextProcessor:
    """Process Vietnamese"""
    
    def __init__(self, config_path: str = None):
        """
        Initialize processor with configuration file
        
        Args:
            config_path: Path to JSON configuration file.
                        If None, it will search in the current directory or src/utils
        """
        self.config_path = config_path or self._find_config_file()
        self.config = self._load_config()
        
        # Load lists from configuration
        self.important_phrases = set(self.config.get('important_phrases', []))
        self.stop_words = set(self.config.get('stop_words', []))
        self.generic_terms = set(self.config.get('generic_terms', []))
        
        # Patterns used to automatically detect important phrases
        self.phrase_patterns = self.config.get('phrase_patterns', [])
        
        # Cache for detected phrases
        self._detected_phrases_cache: Dict[str, List[str]] = {}
        
    def _find_config_file(self) -> str:
        """Search for the configuration file in possible directories"""
        possible_paths = [
            Path(__file__).parent / 'vietnamese_text_config.json',
            Path(__file__).parent.parent.parent / 'src' / 'utils' / 'vietnamese_text_config.json',
            Path(__file__).parent.parent.parent / 'vietnamese_text_config.json',
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path)
        
        # If not found, create a default file
        default_path = Path(__file__).parent / 'vietnamese_text_config.json'
        logger.warning(f"Config file not found, will create default at: {default_path}")
        return str(default_path)
    
    def _load_config(self) -> Dict:
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"Loaded config from {self.config_path}")
                    return config
            else:
                # Create default configuration file
                logger.warning(f"Config file not found at {self.config_path}, creating default...")
                default_config = self._get_default_config()
                self._save_config(default_config)
                return default_config
        except Exception as e:
            logger.error(f"Error loading config: {e}, using default config")
            return self._get_default_config()
    
    def _save_config(self, config: Dict):
        """Lưu cấu hình vào file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved default config to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def _get_default_config(self) -> Dict:
        """Save configuration to file"""
        return {
            "important_phrases": [
                # Lao động / Labor
                "hợp đồng lao động", "người lao động", "người sử dụng lao động", 
                "lao động", "tiền lương", "trả lương", "nợ lương",
                "sa thải", "chấm dứt hợp đồng", "thôi việc",
                # Đất đai / Land
                "tranh chấp đất đai", "tranh chấp đất", "quyền sử dụng đất", 
                "đất đai", "giấy chứng nhận", "sổ đỏ", "sổ hồng",
                # Hôn nhân gia đình / Marriage & family
                "hôn nhân", "ly hôn", "giấy chứng nhận kết hôn",
                # Thuế / Tax
                "thuế thu nhập", "nộp thuế", "khai thuế",
                # Pháp lý / Legal
                "khởi kiện", "giải quyết tranh chấp", "tòa án",
                "luật sư", "cơ quan có thẩm quyền",
                # Thủ tục hành chính / Administrative procedures
                "thủ tục hành chính", "giấy tờ", "hồ sơ",
                # Bảo hiểm / Insurance
                "bảo hiểm xã hội", "bảo hiểm y tế", "bảo hiểm thất nghiệp"
            ],
            "stop_words": {
                "tôi", "bạn", "có", "là", "cần", "phải", "làm", "gì", 
                "nên", "với", "và", "của", "để", "cho", "một", "các", 
                "nào", "đâu", "thì", "khi", "về", "vấn", "đề", "từ", 
                "tháng", "năm", "giải", "thích", "hiểu", "được", "sẽ",
                "đã", "đang", "sẽ", "bị", "bởi", "vì", "do", "nếu",
                "nhưng", "mà", "hoặc", "hay", "cũng", "rất", "quá"
            },
            "generic_terms": {
                "doanh", "nghiệp", "tổ", "chức", "hoạt", "động", 
                "quy", "định", "thông", "tư", "nghị", "công", "ty",
                "văn", "bản", "pháp", "luật", "điều", "khoản", "điểm"
            },
            "phrase_patterns": [
                # Pattern for legal phrases: 2–4 words
                r"\b\w+\s+\w+\b",  # 2 từ
                r"\b\w+\s+\w+\s+\w+\b",  # 3 từ
                r"\b\w+\s+\w+\s+\w+\s+\w+\b",  # 4 từ
                # Pattern for legal terms
                r"\b(luật|nghị định|thông tư|quyết định|chỉ thị)\s+\w+",
                r"\b(điều|khoản|điểm)\s+\d+",
                # Pattern for common legal phrases
                r"\b\w+\s+(lao động|đất đai|hôn nhân|thuế|bảo hiểm)\b",
                r"\b(quyền|nghĩa vụ|trách nhiệm)\s+\w+",
            ]
        }
    
    def detect_important_phrases(self, text: str) -> List[str]:
        """
        Automatically detect important phrases in text
        
        Args:
            text: Text to process
            
        Returns:
            List of detected important phrases
        """
        text_lower = text.lower()
        detected_phrases = []
        
        # 1. Check predefined phrases
        for phrase in self.important_phrases:
            if phrase in text_lower:
                detected_phrases.append(phrase)
        
        # 2. Detect new phrases using patterns
        for pattern in self.phrase_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = ' '.join(match)
                words = match.split()
                if len(words) >= 2 and not all(word in self.stop_words for word in words):
                    if match not in detected_phrases and len(match) > 5:
                        detected_phrases.append(match)
        
        
        return detected_phrases
    
    def extract_key_terms(self, text: str, remove_stop_words: bool = True, 
                         remove_generic_terms: bool = True) -> Set[str]:
        """
        Extract key terms from text
        
        Args:
            text: Input text
            remove_stop_words: Whether to remove stop words
            remove_generic_terms: Whether to remove generic terms
            
        Returns:
            Set of important key terms
        """
        words = text.lower().split()
        
        # Remove punctuation and special characters.
        words = [re.sub(r'[^\w\s]', '', word) for word in words]
        words = [word for word in words if word and len(word) > 1]
        
        # Convert to a set
        terms = set(words)
        
        # Remove stop words
        if remove_stop_words:
            terms = terms - self.stop_words
        
        # Remove generic terms
        if remove_generic_terms:
            terms = terms - self.generic_terms
        
        # Filter out words that are too short (under 2 characters).
        terms = {term for term in terms if len(term) >= 2}
        
        return terms
    
    def validate_phrase_in_text(self, phrase: str, text: str) -> bool:
        """
        Check whether a phrase appears in text
        """
        return phrase.lower() in text.lower()
    
    def find_phrase_matches(self, query: str, document_text: str, 
                           document_title: str = "") -> Tuple[List[str], List[str]]:
        """
        Find important phrases that appear in both the query and the document.

        Args:
            query (str): User query.
            document_text (str): Content of the document.
            document_title (str, optional): Title of the document.

        Returns:
            Tuple[List[str], List[str]]:
                - query_phrases: Important phrases detected in the query.
                - doc_phrases: Phrases from the query that also appear in the document.
        """
        # Detecting phrases in queries
        query_phrases = self.detect_important_phrases(query)
        
        # Check which phrases appear in the document.
        doc_text = (document_title + " " + document_text).lower()
        doc_phrases = []
        
        for phrase in query_phrases:
            if self.validate_phrase_in_text(phrase, doc_text):
                doc_phrases.append(phrase)
        
        return query_phrases, doc_phrases
    
    def add_important_phrase(self, phrase: str):
         """Add important phrase at list(runtime)"""
        self.important_phrases.add(phrase.lower())
    
    def add_stop_word(self, word: str):
        """Add stop word at list(runtime)"""
        self.stop_words.add(word.lower())
    
    def add_generic_term(self, term: str):
        """Add generic term at list(runtime)"""
        self.generic_terms.add(term.lower())
    
    def reload_config(self):
        """Reload configuration from file"""
        self.config = self._load_config()
        self.important_phrases = set(self.config.get('important_phrases', []))
        self.stop_words = set(self.config.get('stop_words', []))
        self.generic_terms = set(self.config.get('generic_terms', []))
        self.phrase_patterns = self.config.get('phrase_patterns', [])
        self._detected_phrases_cache.clear()
        logger.info("Config reloaded successfully")


# Singleton instance for reuse
_processor_instance = None

def get_text_processor(config_path: str = None) -> VietnameseTextProcessor:
    """
    Get VietnameseTextProcessor instance (singleton pattern)
    
    Args:
        config_path: the path to the configuration file
        
    Returns:
        VietnameseTextProcessor instance
    """
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = VietnameseTextProcessor(config_path)
    return _processor_instance

