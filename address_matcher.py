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
        'TP.': ' ', 'TP ': ' ', 'ThP ': ' ', 'Thành Phố ': ' ', 'Thành phố ': ' ', 'thành phố ': ' ',
        'Thà6nh phố': ' ','Tỉnh': ' ','t.P': ' ','T.P': ' ','T0P': ' ',
        'Tnh': ' ', 'TỉnhC': ' ', 'tỉnh ': ' ', 'Tỉnh ': ' ', 'tp.': ' ', 'tp ': ' ', 'T ': ' ',
        'Quận ': ' ', 'Quận': ' ', 'Q.': ' ', 'Q ': ' ', 'quận': ' ',
        'Huyện ': ' ', 'H.': ' ', 'H ': ' ', 'huyện ': ' ', 'Huyện': ' ', 'huyện': ' ',
        'hyện': ' ','HZuyện': ' ','Huyên': ' ','Huzyen': ' ','h ': ' ',
        'Thị Trấn ': ' ', 'thị trấn ': ' ', 'Thị Trấn': ' ', 'thị trấn': ' ', 'Thị trấn': ' ', 'TT.': ' ', 'TT ': ' ',
        'Thi trấ ': ' ',
        'Thị Xã ': ' ', 'thị xã ': ' ', 'TX.': ' ', 'TX ': ' ', 'Thị xã ': ' ','T.X': ' ',
        'Phường ': ' ', 'phường ': ' ', 'Ph.': ' ', 'P.': ' ', 'P ': ' ', 'F ': ' ', 'f ': ' ', 'F. ': ' ',
        'Phường': ' ',
        'F.': ' ', 'f': ' ', 'f.': ' ','F': ' ',
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

    def find_best_match(self, part: str, level: str, in_scope) -> Optional[str]:
        """Find best matching address component"""
        normalized_part = self.normalize(part)

        # Try exact match first
        if in_scope is not None:
            normalized_items = {self.normalize(item.name): item.name for item in in_scope.values()}
            if normalized_part in normalized_items:
                return normalized_items[normalized_part]
        else:
            if normalized_part in self.length_maps[level]:
                return self.length_maps[level]

        # Fall back to fuzzy matching
        candidates = []
        items_to_check = in_scope.values() if in_scope is not None else self.data[level]

        for item in items_to_check:
            item_name = item.name if in_scope is not None else item
            normalized_item = self.normalize(item_name)


            if abs(len(normalized_part) - len(normalized_item)) > 2:
                continue

            score = self.levenshtein_distance(normalized_part, normalized_item)
            max_length = max(len(normalized_part), len(normalized_item))
            similarity = (max_length - score) / max_length * 100

            if similarity >= 80:
                candidates.append({
                    'item': item_name,
                    'score': score,
                    'similarity': similarity
                })

        if candidates:
            candidates.sort(key=lambda x: (x['score'], -x['similarity']))
            return candidates[0]['item']

        # move to stress search
        normalized_part = self.normalize(part)
        part_length = len(normalized_part)
        candidates = []

        # Only check items with similar lengths (±2)
        for length in range(part_length - 2, part_length + 3):
            # Get items of this length from our precomputed map
            for item, normalized_item in self.length_maps[level][length]:
                score = self.levenshtein_distance(normalized_part, normalized_item)
                max_length = max(part_length, length)
                similarity = (max_length - score) / max_length * 100

                if similarity >= 80:
                    candidates.append({
                        'item': item,
                        'score': score,
                        'similarity': similarity
                    })

                # Optional: Early return if we find a perfect match
                if similarity == 100:
                    return item

        if candidates:
            candidates.sort(key=lambda x: (x['score'], -x['similarity']))
            return candidates[0]['item']

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
            if len(new_string) <= 7:
                new_string = self.abbreviations.get(new_string, new_string)

            province_match = self.find_best_match(new_string, 'province', None)
            if province_match:
                result['province'] = province_match
                words = words[:len(words) - (i + 1)]
                province = next((p for p in self.provinces.values() if p.name == province_match), None)
                break

        # Find district
        district = None
        for i in range(len(words)):
            new_string = ' '.join(words[-(i + 1):])
            district_match = self.find_best_match(new_string, 'district',
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
            ward_match = self.find_best_match(new_string, 'ward',
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