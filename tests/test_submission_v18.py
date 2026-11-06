import io
import zipfile
from dashboard.server import build_submission_bundle, submission_page


def test_bundle_has_manifest_and_readme():
    with zipfile.ZipFile(io.BytesIO(build_submission_bundle())) as z:
        assert 'experiment_manifest.json' in z.namelist()
        assert 'README_SUBMISSION.txt' in z.namelist()
        assert 'Missing (not generated)' in z.read('README_SUBMISSION.txt').decode()


def test_submission_navigation_page():
    assert 'Submission Center' in submission_page()
    assert '/export-submission' in submission_page()
