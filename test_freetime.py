
########## UNDER DEVELOPMENT #######

import unittest
from main import main, addTouple

class TestACP(unittest.TestCase):
	def test_calc_date(self):
                dictTemp = [{'calendars': {'4karenbrooks@gmail.com': {'busy': [{'start': '2015-11-25T01:15:00Z', 'end': '2015-11-25T02:30:00Z'}, {'start': '2015-11-26T20:00:00Z', 'end': '2015-11-26T21:00:00Z'}, {'start': '2015-12-02T01:15:00Z', 'end': '2015-12-02T02:30:00Z'}]}}, 'kind': 'calendar#freeBusy', 'timeMax': '2015-12-05T08:00:00.000Z', 'timeMin': '2015-11-24T08:00:00.000Z'}]
		self.assertEqual( addTouple((1,0),(1,1)),(2,1))

	def test_range1(self):
		self.assertEqual( acpBrevit(0), (60,0))

	def test_range1(self):
		self.assertEqual( acpBrevit(10), (17,40))

	def test_60(self):
		self.assertEqual( acpBrevit(60), (106,240))

	def test_120(self):
		self.assertEqual( acpBrevit(120), (212,480))

	def test_175(self):
		self.assertEqual( acpBrevit(175), (309,700))

	def test_Max(self):
		self.assertEqual( acpBrevit(200), (353,780))

if __name__ == '__main__':
	unittest.main()
