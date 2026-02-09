"""Fast smoke checks for critical workflows."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services.bid_excel_service import export_internal_bid_workbook, export_proposal_workbook
from app.ui.excel_mapper import map_excel_with_catalog


@pytest.mark.smoke
def test_smoke_health_endpoint(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_PREFIX}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.smoke
def test_smoke_input_to_exports() -> None:
    fixture = Path(__file__).parent / "test_data" / "client_input_data.xlsx"
    state, warnings, debug = map_excel_with_catalog(str(fixture), template="baycrest_v1")
    assert state.total_items > 0
    assert debug["catalog"]["metrics"]["missing_extracted_count"] == 0

    internal = export_internal_bid_workbook(state)
    proposal = export_proposal_workbook(state)
    assert len(internal) > 0
    assert len(proposal) > 0

