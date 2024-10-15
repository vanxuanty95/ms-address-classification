import re
import unicodedata
import json


class AddressMatcher:
    def __init__(self, xa_file, huyen_file, tinh_file):
        self.data = {
            'xa': set(self.load_data(xa_file)),
            'huyen': set(self.load_data(huyen_file)),
            'tinh': set(self.load_data(tinh_file))
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
        return best_match if best_score <= len(normalized_part) / 2 else None

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

        parts = [part.strip() for part in re.split(r'[,.]', input_address) if part.strip()]
        result = {'tinh': '', 'huyen': '', 'xa': ''}

        # Handle the "happy case" of three-part addresses
        if len(parts) == 3:
            result['xa'] = self.find_exact_match(parts[0], 'xa') or self.find_best_match(parts[0], 'xa') or ''
            result['huyen'] = self.find_exact_match(parts[1], 'huyen') or self.find_best_match(parts[1], 'huyen') or ''
            result['tinh'] = self.find_exact_match(parts[2], 'tinh') or self.find_best_match(parts[2], 'tinh') or ''
        else:
            # Start from the end for other cases
            for i, part in enumerate(reversed(parts)):
                normalized = re.sub(r'^(X\.|Xã|H\.|Huyện|TT\.|Thị Trấn|TP\.|Tỉnh|P\.|Phường|Q\.|Quận)\s*', '', part,
                                    flags=re.IGNORECASE)

                if i == 0 and not result['tinh']:
                    result['tinh'] = self.find_exact_match(normalized, 'tinh') or self.find_best_match(normalized,
                                                                                                       'tinh') or ''
                elif i == 1 and not result['huyen']:
                    result['huyen'] = self.find_exact_match(normalized, 'huyen') or self.find_best_match(normalized,
                                                                                                         'huyen') or ''
                elif i == 2 and not result['xa']:
                    result['xa'] = self.find_exact_match(normalized, 'xa') or self.find_best_match(normalized,
                                                                                                   'xa') or ''

                if result['tinh'] and result['huyen'] and result['xa']:
                    break

        output = {
            'province': result['tinh'],
            'district': result['huyen'],
            'ward': result['xa']
        }
        self.cache[input_address] = output
        return output


# Helper function to load test cases
def load_test_cases(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)