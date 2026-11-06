from dashboard.server import powerbi_health_report, powerbi_health_page


def test_report_has_three_artifacts():
    assert len(powerbi_health_report()) == 3
    assert all(row['status'] in ('MISSING', 'INVALID', 'READY', 'EMPTY', 'ERROR')
               for row in powerbi_health_report())


def test_navigation():
    assert 'Power BI Export Health' in powerbi_health_page()
    assert '/export-powerbi-health' in powerbi_health_page()
