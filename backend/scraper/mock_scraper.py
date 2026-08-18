MOCK_SUCCESS_DATA = {
    "collector_id": "c_mock_123456",
    "status": "success",
    "records_extracted": 1,
    "data": [
        {
            "title": "Wireless Gaming Mouse",
            "price": "$49.99",
            "status": "In Stock"
        }
    ]
}

MOCK_FAILURE_DATA = {
    "collector_id": "c_mock_123456",
    "status": "failed",
    "error": "SelectorNotFound: .product-price",
    "records_extracted": 0,
    "data": []
}

def run_scraper(trigger_failure: bool = False):
    if trigger_failure:
        return MOCK_FAILURE_DATA
    return MOCK_SUCCESS_DATA