import json
import re
import signal
from collections import defaultdict
from functools import lru_cache
from typing import Dict, List, Optional


class Ward:
    __slots__ = ['id', 'name', 'code', 'district_id']

    def __init__(self, id: str, name: str, code: str, district_id: str):
        self.id = id
        self.name = name
        self.code = code
        self.district_id = district_id


class District:
    __slots__ = ['id', 'name', 'code', 'province_id', 'wards']

    def __init__(self, id: str, name: str, code: str, province_id: str):
        self.id = id
        self.name = name
        self.code = code
        self.province_id = province_id
        self.wards = {}


class Province:
    __slots__ = ['id', 'name', 'code', 'districts']

    def __init__(self, id: str, name: str, code: str):
        self.id = id
        self.name = name
        self.code = code
        self.districts = {}


class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end = False
        self.word = None
        self.suggestions = set()  # Store similar words


class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str, original: str):
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
            # Store similar words at each node
            if len(node.suggestions) < 10:  # Limit suggestions
                node.suggestions.add(original)
        node.is_end = True
        node.word = original

    def search_similar(self, word: str, max_distance: int = 2) -> list:
        def _search_recursive(node, prefix, remaining_word, distance):
            results = set()

            # If we've reached end and distance is acceptable
            if not remaining_word and node.is_end and distance <= max_distance:
                results.add((node.word, distance))

            # If we've exceeded max distance, stop this branch
            if distance > max_distance:
                return results

            # Handle insertion
            if remaining_word:
                char = remaining_word[0]
                rest = remaining_word[1:]

                # Match current character
                if char in node.children:
                    results.update(_search_recursive(node.children[char],
                                                     prefix + char,
                                                     rest,
                                                     distance))

                # Try deletion
                results.update(_search_recursive(node,
                                                 prefix,
                                                 rest,
                                                 distance + 1))

                # Try substitution
                for c in node.children:
                    if c != char:
                        results.update(_search_recursive(node.children[c],
                                                         prefix + c,
                                                         rest,
                                                         distance + 1))

            # Try insertion
            for c in node.children:
                results.update(_search_recursive(node.children[c],
                                                 prefix + c,
                                                 remaining_word,
                                                 distance + 1))

            return results

        return sorted(_search_recursive(self.root, "", word, 0),
                      key=lambda x: x[1])  # Sort by distance


class AddressMatcher:
    # Vietnamese character mappings
    VIET_CHARS = {
        'đ': 'd', 'Đ': 'D',
        'á': 'a', 'à': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
        'ă': 'a', 'ắ': 'a', 'ằ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
        'â': 'a', 'ấ': 'a', 'ầ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
        'é': 'e', 'è': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
        'ê': 'e', 'ế': 'e', 'ề': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
        'í': 'i', 'ì': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
        'ó': 'o', 'ò': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
        'ô': 'o', 'ố': 'o', 'ồ': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
        'ơ': 'o', 'ớ': 'o', 'ờ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
        'ú': 'u', 'ù': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
        'ư': 'u', 'ứ': 'u', 'ừ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
        'ý': 'y', 'ỳ': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y'
    }

    # Address cleaning replacements
    REPLACEMENTS = {
        'TP.': ' ', 'TP ': ' ', 'ThP ': ' ', 'Thành Phố ': ' ', 'Thành phố ': ' ', 'thành phố ': ' ', 'T.Phw': ' ',
        'Thà6nh phố': ' ', 'Tỉnh': ' ', 't.P': ' ', 'T.P': ' ', 'T0P': ' ', 'TỉnhV': ' ', 'Tỉnwh': ' ', 'Thành phô': ' ',
        'Tnh': ' ', 'TỉnhC': ' ', 'tỉnh ': ' ', 'Tỉnh ': ' ', 'tp.': ' ', 'tp ': ' ', 'T ': ' ',
        'Quận ': ' ', 'Quận': ' ', 'Q.': ' ', 'Q ': ' ', 'quận': ' ',
        'Huyện ': ' ', 'H.': ' ', 'H ': ' ', 'huyện ': ' ', 'Huyện': ' ', 'huyện': ' ',
        'hyện': ' ', 'HZuyện': ' ', 'Huyên': ' ', 'Huzyen': ' ', 'h ': ' ',
        'Thị Trấn ': ' ', 'thị trấn ': ' ', 'Thị Trấn': ' ', 'thị trấn': ' ', 'Thị trấn': ' ', 'TT.': ' ', 'TT ': ' ',
        'Thi trấ ': ' ',
        'Thị Xã ': ' ', 'thị xã ': ' ', 'TX.': ' ', 'TX ': ' ', 'Thị xã ': ' ', 'T.X': ' ',
        'Phường ': ' ', 'phường ': ' ', 'Ph.': ' ', 'P.': ' ', 'P ': ' ', 'F ': ' ', 'f ': ' ', 'F. ': ' ',
        'Phường': ' ',
        'F.': ' ', 'f': ' ', 'f.': ' ', 'F': ' ',
        'Xã ': ' ', 'Xã': ' ', 'xã ': ' ', 'xã': ' ', 'X.': ' ', 'X ': ' ', 'x.': ' ', 'x ': ' ',
        'Phuong ': ' ', 'phuong ': ' ', 'Xa ': ' ', 'xa ': ' ',
        'Huyen ': ' ', 'huyen ': ' ', 'Tinh ': ' ', 'tinh ': ' ',

        '.': ' ', ',': ' ', '-': ' ', '_': ' ',
    }

    def __init__(self, xa_file: str, huyen_file: str, tinh_file: str):
        # Initialize data structures
        self.data = {
            'ward': set(self.load_data(xa_file)),
            'district': set(self.load_data(huyen_file)),
            'province': set(self.load_data(tinh_file))
        }

        # Initialize lookup maps
        self.provinces = {}
        self.cache = {}
        self.abbreviations = self._load_abbreviations()

        self.province_trie = Trie()
        self.district_trie = Trie()
        self.ward_trie = Trie()
        self.tries = {
            'province': self.province_trie,
            'district': self.district_trie,
            'ward': self.ward_trie
        }

        # Precompile regex patterns
        self.admin_indicators = re.compile(r'^.*?(Thị\s*[Tt]rấn|TT|Phường|P|Ph?|[Xx]ã)\.?\s+')
        self.p_patterns = [
            re.compile(p) for p in [
                r'P\.?\s*(\d+)',
                r'Ph\.?\s*(\d+)',
                r'[Pp]hường\s*(\d+)',
                r'Q\.?\s*(\d+)',
                r'[Qq]uận\s*(\d+)'
            ]
        ]

        # Create normalized lookup maps
        self._init_lookup_maps()

        # Load hierarchical data
        self.load_own_file('wards_with_code.txt', 'districts_with_code.txt', 'provinces_with_code.txt')

    @staticmethod
    def load_data(filename: str) -> List[str]:
        result = []
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line:  # Skip empty or whitespace-only lines
                    result.append(stripped_line)
        return result

    def _load_abbreviations(self) -> Dict[str, str]:
        abbreviations = {}
        with open('abbreviations.txt', 'r', encoding='utf-8') as file:
            for line in file:
                abbr, full = line.strip().split(',')
                abbreviations[abbr] = full
        return abbreviations

    def _init_lookup_maps(self):
        """Initialize normalized lookup maps for faster matching"""
        # Create dictionaries grouped by length for each level
        self.length_maps = {
            'province': defaultdict(list),
            'district': defaultdict(list),
            'ward': defaultdict(list)
        }

        # Group items by their normalized length
        for level in ['province', 'district', 'ward']:
            for item in self.data[level]:
                norm_item = self.normalize(item)
                self.length_maps[level][len(norm_item)].append((item, norm_item))
                # Add to trie
                self.tries[level].insert(norm_item, item)

    @lru_cache(maxsize=10000)
    def normalize(self, text: str) -> str:
        """Normalize text with caching"""
        text = text.lower()
        for viet_char, ascii_char in self.VIET_CHARS.items():
            text = text.replace(viet_char, ascii_char)
        return re.sub(r'[^a-z0-9\s]', '', text)

    @lru_cache(maxsize=1000)
    def levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance with caching"""
        if len(s1) < len(s2):
            return self.levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def find_best_match_v3(self, part: str, level: str, in_scope) -> Optional[str]:
        """Find best matching address component"""
        normalized_part = self.normalize(part)

        # Try exact match first
        if in_scope is not None:
            normalized_items = {self.normalize(item.name): item.name for item in in_scope.values()}
            if normalized_part in normalized_items:
                return normalized_items[normalized_part]

        # Use trie for fuzzy matching
        if in_scope is not None:
            # Build temporary trie for in_scope items
            temp_trie = Trie()
            for item in in_scope.values():
                temp_trie.insert(self.normalize(item.name), item.name)
            matches = temp_trie.search_similar(normalized_part, max_distance=2)
        else:
            matches = self.tries[level].search_similar(normalized_part, max_distance=2)

        if matches:
            return matches[0][0]  # Return the closest match

        return None

    @lru_cache(maxsize=1000)
    def clean_address(self, address: str) -> str:
        """Clean address string with caching"""
        cleaned = address

        # Apply replacements
        for old, new in self.REPLACEMENTS.items():
            cleaned = cleaned.replace(old, new)

        # Handle administrative indicators
        match = self.admin_indicators.search(cleaned)
        if match:
            cleaned = cleaned[match.end():].strip()

        # Apply number patterns
        for pattern in self.p_patterns:
            cleaned = pattern.sub(r'\1', cleaned)

        return ' '.join(cleaned.split())

    def process(self, address: str):
        return self.run_with_timeout(self.match_address, address)

    def run_with_timeout(self, func, address, timeout=0.09):
        def timeout_handler(signum, frame):
            raise TimeoutError()

        # Set signal handler
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, timeout)

        try:
            result = func(address)
            signal.setitimer(signal.ITIMER_REAL, 0)  # Disable timer
            return result
        except TimeoutError:
            return {
                'province': 'overtime',
                'district': '',
                'ward': ''
            }
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)

    def match_address(self, input_address: str) -> Dict[str, str]:
        """Match address components with caching"""
        if input_address in self.cache:
            return self.cache[input_address]

        result = {
            'province': '',
            'district': '',
            'ward': ''
        }

        input_address = self.clean_address(input_address)
        words = input_address.split()

        # Find province
        province = None
        for i in range(len(words)):
            new_string = ' '.join(words[-(i + 1):])
            if len(new_string) <= 9:
                new_string = self.abbreviations.get(new_string, new_string)

            province_match = self.find_best_match_v3(new_string, 'province', None)
            if province_match:
                result['province'] = province_match
                words = words[:len(words) - (i + 1)]
                province = next((p for p in self.provinces.values() if p.name == province_match), None)
                break

        # Find district
        district = None
        for i in range(len(words)):
            new_string = ' '.join(words[-(i + 1):])
            district_match = self.find_best_match_v3(new_string, 'district',
                                                    province.districts if province else None)
            if district_match:
                result['district'] = district_match
                words = words[:len(words) - (i + 1)]
                district = next((d for d in (province.districts.values() if province else [])
                                 if d.name == district_match), None)
                break

        # Find ward
        for i in range(len(words)):
            new_string = ' '.join(words[-(i + 1):])
            ward_match = self.find_best_match_v3(new_string, 'ward',
                                                district.wards if district else None)
            if ward_match:
                result['ward'] = ward_match
                break

        self.cache[input_address] = result
        return result

    def load_own_file(self, xa_file: str, huyen_file: str, tinh_file: str):
        """Load hierarchical address data"""
        # Load provinces
        with open(tinh_file, 'r', encoding='utf-8') as file:
            for line in file:
                id, name, code = line.strip().split(';')
                self.provinces[id] = Province(id, name, code)

        # Load districts
        with open(huyen_file, 'r', encoding='utf-8') as file:
            for line in file:
                id, name, code, province_id = line.strip().split(';')
                if province_id in self.provinces:
                    self.provinces[province_id].districts[id] = District(id, name, code, province_id)

        # Load wards
        with open(xa_file, 'r', encoding='utf-8') as file:
            for line in file:
                id, name, code, district_id = line.strip().split(';')
                ward = Ward(id, name, code, district_id)
                for province in self.provinces.values():
                    if district_id in province.districts:
                        province.districts[district_id].wards[id] = ward
                        break


def load_test_cases(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)
