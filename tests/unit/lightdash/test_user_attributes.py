import json

from lightdash_companion_integration_spike.lightdash import user_attributes


class TestBuildHeader:
    def test_serializes_single_and_multiple_values(self) -> None:
        header = user_attributes.build_header(
            attributes={"tenant_id": "123", "regions": ["uk", "au"]}
        )

        assert json.loads(header["X-Lightdash-User-Attributes"]) == {
            "tenant_id": "123",
            "regions": ["uk", "au"],
        }
