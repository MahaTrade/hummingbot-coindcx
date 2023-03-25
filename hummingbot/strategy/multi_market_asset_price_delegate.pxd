from hummingbot.strategy.asset_price_delegate cimport AssetPriceDelegate

cdef class MultiMarketAssetPriceDelegate(AssetPriceDelegate):
    cdef:
        list _price_delegates
