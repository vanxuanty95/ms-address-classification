import re
import unicodedata
import json


class AddressMatcher:
    def __init__(self, xa_file, huyen_file, tinh_file):
        self.data = {
            'ward': set(self.load_data(xa_file)),
            'district': set(self.load_data(huyen_file)),
            'province': set(self.load_data(tinh_file))
        }
        self.cache = {}

    def load_data(self, filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f]

    def normalize(self, text):
        # Convert to lowercase and remove diacritics
        text = text.lower()
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        # Remove non-alphanumeric characters
        text = re.sub(r'[^a-z0-9\s]', '', text)
        return text

    def find_exact_match(self, part, level):
        normalized_part = self.normalize(part)
        for item in self.data[level]:
            if self.normalize(item) == normalized_part:
                return item
        return None

    def find_best_match(self, part, level):
        best_match = None
        best_score = float('inf')
        normalized_part = self.normalize(part)
        for item in self.data[level]:
            normalized_item = self.normalize(item)
            score = self.levenshtein_distance(normalized_part, normalized_item)
            if score < best_score:
                best_score = score
                best_match = item
        return best_match if best_score <= (len(normalized_part) / 100 * 60) else None

    def levenshtein_distance(self, s1, s2):
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

    def match_address(self, input_address):
        if input_address in self.cache:
            return self.cache[input_address]

        result = {
            'province': None,
            'district': None,
            'ward': None
        }

        parts = self.parse_vn_geo_structured(input_address)

        if len(parts) == 3:
            result['ward'] = self.find_exact_match(parts['ward'], 'ward') or self.find_best_match(parts['ward'], 'ward') or ''
            result['district'] = self.find_exact_match(parts['district'], 'district') or self.find_best_match(parts['district'], 'district') or ''
            result['province'] = self.find_exact_match(parts['province'], 'province') or self.find_best_match(parts['province'], 'province') or ''
        else:
            result = {
                'province': self.find_exact_match(input_address, 'xa') or self.find_best_match(input_address, 'xa') or '',
                'district': self.find_exact_match(input_address, 'huyen') or self.find_best_match(input_address,
                                                                                                  'huyen') or '',
                'ward': self.find_exact_match(input_address, 'tinh') or self.find_best_match(input_address, 'tinh') or ''}

        output = {
            'province': result['province'],
            'district': result['district'],
            'ward': result['ward']
        }
        self.cache[input_address] = output
        return output

    def parse_vn_geo_structured(self, text):
        text = text.strip()

        # Initialize result
        result = {
            "province": None,
            "district": None,
            "ward": None
        }

        # Split by comma first (province is usually after last comma)
        parts = [p.strip() for p in text.split(',')]

        # Get province (rightmost part) - handle TP.HoChiMinh case
        if parts:
            result["province"] = parts[-1].strip().strip('.')

        # Get the remaining text (everything before province)
        remaining = ','.join(parts[:-1]) if len(parts) > 1 else parts[0]

        # Enhanced district pattern - handle Q3, Quận 3 cases
        district_pattern = r'(?:Huyện| H\.|,H\.|,H | H |Quận |Q\.|Q |[Qq](?=\d{1,2}(?:\s|$|\.|,))|Thị xã|TX|TX\.)\s*([^,]+?)(?=\s*(?:TT|Thị Trấn|X |X\.|Xã|P|Phường|$))'
        district_match = re.search(district_pattern, remaining, re.IGNORECASE)
        if district_match:
            district = district_match.group(1).strip()
            # Clean up district number
            if district.isdigit() or (len(district) > 1 and district[0].isdigit()):
                district = district.split()[0]  # Take only the number part
            result["district"] = district
            remaining = remaining[:district_match.start()].strip()

        # Enhanced ward pattern - handle P1, Phường 1 cases
        ward_pattern = r'(?:TT|,TT\.|,TT | TT |Thị Trấn|,X\.| X | X\. | X\.|Xã|,P(?=\d{1,2}(?:\s|$|\.|,))| P(?=\d{1,2}(?:\s|$|\.|,))|,P\.| P\.| P | P\. |Phường)\s*([^,]+?)(?=\s*(?:Huyện| H\.|,H\.|,H | H |Quận|Q.|Q |Thị xã|TX|TX.|$))'
        ward_match = re.search(ward_pattern, remaining, re.IGNORECASE)
        if ward_match:
            ward = ward_match.group(1).strip()
            # Clean up ward number
            if ward.isdigit() or (len(ward) > 1 and ward[0].isdigit()):
                ward = ward.split()[0]  # Take only the number part
            result["ward"] = ward

        return result


# Helper function to load test cases
def load_test_cases(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)
