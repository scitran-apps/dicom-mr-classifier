import csv
import os
import sys

import pytest

# Import measurement from label (hijinks due to dashes in name)
test_dir = os.path.dirname(__file__)
base_dir = os.path.abspath(os.path.join(test_dir, '..'))
sys.path.append(base_dir)
infer_measurement = __import__('measurement-from-label', globals(), locals()).infer_measurement

def test_measurement_from_label():
    # Load up all of the labels
    test_file = os.path.join(test_dir, 'test_classifications.csv')
    with open(test_file, 'r') as f:
        reader = csv.reader(f)

        row = 0
        for label, classification in reader:
            result = infer_measurement(label)
            if result != classification:
                pytest.fail('Row %d expected label "%s" to be classified as %s, but got: %s' % (row, label, classification, result))

            row = row + 1

