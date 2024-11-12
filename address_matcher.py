import re
import json


class AddressMatcher:
    def __init__(self, xa_file, huyen_file, tinh_file):
        self.data = {
            'ward': set(self.load_data(xa_file)),
            'district': set(self.load_data(huyen_file)),
            'province': set(self.load_data(tinh_file))
        }
        self.provinces = {}

        self.load_own_file('wards_with_code.txt', 'districts_with_code.txt', 'provinces_with_code.txt')

        self.cache = {}
        self.abbreviations = {}
        self.load_abbreviations()

    def load_data(self, filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f]

    def load_abbreviations(self):
        # Load abbreviations from txt file into dictionary
        self.abbreviations = {}
        with open('abbreviations.txt', 'r', encoding='utf-8') as file:
            for line in file:
                abbr, full = line.strip().split(',')
                self.abbreviations[abbr] = full

    def normalize(self, text):
        # Define Vietnamese character mappings
        vietnamese_map = {
            'đ': 'd',
            'Đ': 'D',
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

        # Convert to lowercase
        text = text.lower()

        # Replace Vietnamese characters
        for vietnamese_char, ascii_char in vietnamese_map.items():
            text = text.replace(vietnamese_char, ascii_char)

        # Remove non-alphanumeric characters
        text = re.sub(r'[^a-z0-9\s]', '', text)

        return text

    def find_exact_match(self, part, level):
        normalized_part = self.normalize(part)
        for item in self.data[level]:
            if self.normalize(item) == normalized_part:
                return item
        return None

    def find_best_match(self, part, level, in_scope):
        candidates = []  # List to store all candidates with their scores
        normalized_part = self.normalize(part)

        if in_scope is not None:
            for item in in_scope.values():
                normalized_item = self.normalize(item.name)

                # Skip if length difference is too big
                if abs(len(normalized_part) - len(normalized_item)) > 2:
                    continue

                score = self.levenshtein_distance(normalized_part, normalized_item)

                # Calculate similarity percentage
                max_length = max(len(normalized_part), len(normalized_item))
                similarity = (max_length - score) / max_length * 100

                if similarity >= 80:  # Require 80% similarity
                    candidates.append({
                        'item': item.name,
                        'score': score,
                        'similarity': similarity
                    })
        else:
            for item in self.data[level]:
                normalized_item = self.normalize(item)

                # Skip if length difference is too big
                if abs(len(normalized_part) - len(normalized_item)) > 2:
                    continue

                score = self.levenshtein_distance(normalized_part, normalized_item)

                # Calculate similarity percentage
                max_length = max(len(normalized_part), len(normalized_item))
                similarity = (max_length - score) / max_length * 100

                if similarity >= 80:  # Require 80% similarity
                    candidates.append({
                        'item': item,
                        'score': score,
                        'similarity': similarity
                    })

        # Sort candidates by score (ascending) and similarity (descending)
        if candidates:
            candidates.sort(key=lambda x: (x['score'], -x['similarity']))
            return candidates[0]['item']  # Return the first (best) match

        return None

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

        input_address = self.clean_address(input_address)

        province = None
        district = None

        words = input_address.split()
        for i in range(len(words)):
            new_string = ' '.join(words[-(i + 1):])
            remain = words[:len(words) - (i + 1)]

            if len(new_string) <= 7:
                for abbr, full_name in self.abbreviations.items():
                    if new_string == abbr:
                        new_string = full_name
                        break

            result_sub = self.find_best_match(new_string, 'province', None)

            if result_sub:  # If a match is found
                words = remain
                result['province'] = result_sub
                for province in self.provinces.values():
                    if province.name == result_sub:
                        province = province
                        break
                break

        for i in range(len(words)):
            new_string = ' '.join(words[-(i + 1):])
            remain = words[:len(words) - (i + 1)]

            if province is not None:
                result_sub = self.find_best_match(new_string, 'district', province.districts)
            else:
                result_sub = self.find_best_match(new_string, 'district', None)

            if result_sub:  # If a match is found
                words = remain
                result['district'] = result_sub
                for district in province.districts.values():
                    if district.name == result_sub:
                        district = district
                        break
                break

        if result['district'] is None:
            for i in range(len(words)):
                new_string = ' '.join(words[-(i + 1):])
                remain = words[:len(words) - (i + 1)]

                result_sub = self.find_best_match(new_string, 'district', None)

                if result_sub:  # If a match is found
                    words = remain
                    result['district'] = result_sub
                    for district in province.districts.values():
                        if district.name == result_sub:
                            district = district
                            break
                    break

        for i in range(len(words)):
            new_string = ' '.join(words[-(i + 1):])
            remain = words[:len(words) - (i + 1)]

            if district is not None:
                result_sub = self.find_best_match(new_string, 'ward', district.wards)
            else:
                result_sub = self.find_best_match(new_string, 'ward', None)

            if result_sub:  # If a match is found
                words = remain
                result['ward'] = result_sub
                break

        if result['ward'] is None:
            for i in range(len(words)):
                new_string = ' '.join(words[-(i + 1):])
                remain = words[:len(words) - (i + 1)]

                result_sub = self.find_best_match(new_string, 'ward', None)

                if result_sub:  # If a match is found
                    words = remain
                    result['ward'] = result_sub
                    break

        if result['province'] is None:
            result['province'] = ''

        if result['district'] is None:
            result['district'] = ''

        if result['ward'] is None:
            result['ward'] = ''

        output = {
            'province': result['province'],
            'district': result['district'],
            'ward': result['ward']
        }
        self.cache[input_address] = output
        return output

    def clean_address(self, address):
        # Expanded replacements for administrative units
        replacements = {
            # City/Province prefixes
            'TP.': ' ', 'TP ': ' ', 'ThP ': ' ', 'Thành Phố ': ' ', 'Thành phố ': ' ', 'thành phố ': ' ',
            'Tnh': ' ', 'TỉnhC': ' ',
            'tỉnh ': ' ', 'Tỉnh ': ' ', 'tp.': ' ', 'tp ': ' ', 'T ': ' ',

            # District prefixes
            'Quận ': ' ', 'Quận': ' ', 'Q.': ' ', 'Q ': ' ',
            'quận': ' ',
            'Huyện ': ' ', 'H.': ' ', 'H ': ' ', 'huyện ': ' ',
            'Huyện': ' ', 'huyện': ' ',

            # Ward/Commune prefixes
            'Thị Trấn ': ' ', 'thị trấn ': ' ', 'Thị Trấn': ' ',  'thị trấn': ' ', 'Thị trấn': ' ', 'TT.': ' ', 'TT ': ' ',
            'Thị Xã ': ' ', 'thị xã ': ' ', 'TX.': ' ', 'TX ': ' ', 'Thị xã ': ' ',
            'Phường ': ' ', 'phường ': ' ', 'Ph.': ' ', 'P.': ' ', 'P ': ' ', 'F ': ' ', 'f ': ' ', 'F. ': ' ',
            'F.': ' ', 'f': ' ', 'f.': ' ',
            'Xã ': ' ', 'Xã': ' ', 'xã ': ' ', 'xã': ' ', 'X.': ' ', 'X ': ' ', 'x.': ' ',

            # Common punctuation
            '.': ' ', ',': ' ', '-': ' ', '_': ' ',

            # Common typos or variations
            'Phuong ': ' ', 'phuong ': ' ',
            'Xa ': ' ', 'xa ': ' ',
            'Huyen ': ' ', 'huyen ': ' ',
            'Tinh ': ' ', 'tinh ': ' '
        }

        admin_indicators = r'^.*?(Thị\s*[Tt]rấn|TT|Phường|P|Ph?|[Xx]ã)\.?\s+'
        match = re.search(admin_indicators, address, re.IGNORECASE)
        if match:
            address = address[match.end():].strip()

        # Apply basic replacements
        cleaned = address
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)

        # Replace P followed by number (P1 -> 1)
        cleaned = re.sub(r'P\.?\s*(\d+)', r'\1', cleaned)
        cleaned = re.sub(r'Phường\s*(\d+)', r'\1', cleaned)
        cleaned = re.sub(r'Ph\.?\s*(\d+)', r'\1', cleaned)
        cleaned = re.sub(r'p\.?\s*(\d+)', r'\1', cleaned)
        cleaned = re.sub(r'phường\s*(\d+)', r'\1', cleaned)
        cleaned = re.sub(r'ph\.?\s*(\d+)', r'\1', cleaned)

        # Replace Q followed by number (Q3 -> 3)
        cleaned = re.sub(r'Q\.?\s*(\d+)', r'\1', cleaned)
        cleaned = re.sub(r'Quận\s*(\d+)', r'\1', cleaned)
        cleaned = re.sub(r'q\.?\s*(\d+)', r'\1', cleaned)
        cleaned = re.sub(r'quận\s*(\d+)', r'\1', cleaned)

        # Remove multiple spaces and trim
        cleaned = ' '.join(cleaned.split())

        return cleaned

    def load_own_file(self, xa_file, huyen_file, tinh_file):
        # Load provinces
        with open(tinh_file, 'r', encoding='utf-8') as file:
            for line in file:
                id, name, code = line.strip().split(';')
                self.provinces[id] = Province(id, name, code)

        # Load districts
        with open(huyen_file, 'r', encoding='utf-8') as file:
            for line in file:
                id, name, code, province_id = line.strip().split(';')
                district = District(id, name, code, province_id)
                if province_id in self.provinces:
                    self.provinces[province_id].districts[id] = district

        # Load wards
        with open(xa_file, 'r', encoding='utf-8') as file:
            for line in file:
                id, name, code, district_id = line.strip().split(';')
                ward = Ward(id, name, code, district_id)
                # Find the province that contains this district
                for province in self.provinces.values():
                    if district_id in province.districts:
                        province.districts[district_id].wards[id] = ward
                        break


class Ward:
    def __init__(self, id, name, code, district_id):
        self.id = id
        self.name = name
        self.code = code
        self.district_id = district_id


class District:
    def __init__(self, id, name, code, province_id):
        self.id = id
        self.name = name
        self.code = code
        self.province_id = province_id
        self.wards = {}  # Dictionary to store wards


class Province:
    def __init__(self, id, name, code):
        self.id = id
        self.name = name
        self.code = code
        self.districts = {}  # Dictionary to store districts


# Helper function to load test cases
def load_test_cases(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)
