import csv
import os
import sys

import pytest

# Import measurement from label (hijinks due to dashes in name)
test_dir = os.path.dirname(__file__)
base_dir = os.path.abspath(os.path.join(test_dir, '..'))
sys.path.append(base_dir)
from classification_from_label import infer_classification

KEYS = ['Intent', 'Contrast', 'Features', 'Custom']

def classification_from_row(row):
    # Test Columns are: Label, Intent, Contrast, Features, Custom
    result = {}

    for i in range(len(KEYS)):
        value = row[i+1]
        if value:
            result[KEYS[i]] = [value]

    return result


def test_measurement_from_label():
    # Load up all of the labels
    test_file = os.path.join(test_dir, 'test_classifications.csv')
    with open(test_file, 'r') as f:
        reader = csv.reader(f)

        row_idx = 0
        for row in reader:
            label = row[0]
            expected = classification_from_row(row)
            result = infer_classification(label)
            if result != expected:
                pytest.fail('Row %d expected label "%s" to be classified as %s, but got: %s' % (row_idx, label, expected, result))

            row_idx = row_idx + 1

def test_measurement_from_empty_label():
    assert infer_classification(None) == {}
    assert infer_classification('') == {}
    assert infer_classification('hkjl') == {}
    
