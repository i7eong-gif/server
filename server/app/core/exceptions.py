class StockNotFoundError(Exception):
    def __init__(self, market: str, code: str):
        self.market = market
        self.code = code
        super().__init__(f"{market} stock not found: {code}")

class InvalidMarketError(Exception):
    def __init__(self, market: str):
        self.market = market
