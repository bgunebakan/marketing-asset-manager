import random
import time
from typing import Any


class GoogleAdsApiSimulator:

    def __init__(self, api_key: str):
        self.base_url = "https://googleads.googleapis.com"
        self.version = "v11"
        self.api_key = api_key

    def update_asset_budget(self, ad_id: str, asset_id: str, new_budget: float) -> dict[str, Any]:

        assert self.api_key, "Invalid API Key"
        time.sleep(random.uniform(3, 7))

        # Simulate occasional failure
        if random.random() < 0.1:
            return {"error": {"code": 400, "message": "Bad Request. Invalid budget amount."}}

        if new_budget < 0:
            return {
                "error": {
                    "code": 422,
                    "message": "Unprocessable Entity. Budget must be a positive value.",
                }
            }

        simulated_response = {
            "ad_id": ad_id,
            "asset_id": asset_id,
            "new_budget": new_budget,
            "status": "SUCCESS",
        }

        return simulated_response
