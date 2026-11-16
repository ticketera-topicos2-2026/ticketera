"""Deliberately failing test for task 7.2 of the project-bootstrap change.

It proves that a red required check (quality) blocks the merge
(Req contribution-workflow: Failing required checks block the merge).
The pull request that carries it is closed without merging.
"""

import unittest


class RequiredChecksProbeTest(unittest.TestCase):
    def test_fails_on_purpose_to_prove_that_quality_blocks_the_merge(self):
        self.fail("Deliberate failure for task 7.2: this pull request must never be merged.")
