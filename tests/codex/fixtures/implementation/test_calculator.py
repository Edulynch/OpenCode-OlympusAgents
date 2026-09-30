import unittest

from calculator import add


class CalculatorTests(unittest.TestCase):
    def test_adds_positive_integers(self):
        self.assertEqual(add(2, 3), 5)

    def test_adds_negative_and_positive_integers(self):
        self.assertEqual(add(-4, 6), 2)


if __name__ == "__main__":
    unittest.main()
