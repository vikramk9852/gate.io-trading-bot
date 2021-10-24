from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime, Numeric, String, Text
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.sql import func

Base = declarative_base()


class CoinScanInfo(Base):
    __tablename__ = 'CoinScanInfo'
    _id = Column(pg.UUID(as_uuid=True),
                 primary_key=True,
                 server_default=str("uuid_generate_v4()"),)
    symbol = Column(String)
    baseAsset = Column(String)
    quoteAsset = Column(String)
    scanTime = Column(DateTime(timezone=True), server_default=func.now())
    price = Column(Numeric)
    type = Column(String)
    exchange = Column(String)
    tradeId = Column(String)

    def __repr__(self):
        return "<CoinScanInfo(_id='{}', symbol='{}', baseAsset='{}', quoteAsset='{}', scanTime={}, price={}, type={}, exchange={}, tradeId={})>"\
            .format(self._id, self.symbol, self.baseAsset, self.quoteAsset, self.scanTime, self.price, self.type, self.exchange, self.tradeId)


class ListedCoins(Base):
    __tablename__ = 'ListedCoins'
    _id = Column(pg.UUID(as_uuid=True),
                 primary_key=True,
                 server_default=str("uuid_generate_v4()"),)
    symbol = Column(String)
    baseAsset = Column(String)
    quoteAsset = Column(String)
    exchange = Column(String)

    def __repr__(self):
        return "<ListedCoins(_id='{}', symbol='{}', baseAsset='{}', quoteAsset='{}', exchange={})>"\
            .format(self._id, self.symbol, self.baseAsset, self.quoteAsset, self.exchange)
