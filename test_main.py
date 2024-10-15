import unittest
from address_matcher import AddressMatcher, load_test_cases

class TestAddressMatcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize the AddressMatcher with your data files
        cls.matcher = AddressMatcher('Xa.txt', 'Huyen.txt', 'Tinh.txt')
        cls.test_cases = load_test_cases('public.json')

    def test_match_address(self):
        for case in self.test_cases:
            with self.subTest(input=case['text']):
                result = self.matcher.match_address(case['text'])
                expected = case['result']
                self.assertEqual(result['province'], expected['province'])
                self.assertEqual(result['district'], expected['district'])
                self.assertEqual(result['ward'], expected['ward'])

if __name__ == '__main__':
    unittest.main()