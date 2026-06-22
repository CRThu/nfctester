from __future__ import annotations
from contextlib import contextmanager
from typing import TypeVar, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .cards.base_card import BaseCard
    from .cards.base_tag import BaseTag
    from .drivers.card_reader import CardReader
    from .hardware.base import Transport

_CardT = TypeVar("_CardT", bound=Union["BaseCard", "BaseTag"])
_TagT = TypeVar("_TagT", bound="BaseTag")
_ReaderT = TypeVar("_ReaderT", bound="CardReader")
_TransportT = TypeVar("_TransportT", bound="Transport")


class TransportRegistry:
    """传输层注册表，管理 Transport 类的注册与实例化。"""

    _transports: dict[str, type[Transport]] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(klass: type[_TransportT]) -> type[_TransportT]:
            cls._transports[name] = klass
            return klass
        return decorator

    @classmethod
    def create(cls, name: str, **kwargs) -> Transport:
        if name not in cls._transports:
            raise ValueError(
                f"Unknown transport: {name}. Available: {list(cls._transports)}"
            )
        return cls._transports[name](**kwargs)

    @classmethod
    def get(cls, name: str) -> type[Transport]:
        if name not in cls._transports:
            raise ValueError(
                f"Unknown transport: {name}. Available: {list(cls._transports)}"
            )
        return cls._transports[name]

    @classmethod
    def list(cls) -> list[str]:
        return list(cls._transports.keys())


class CardReaderRegistry:
    """读卡器注册表，管理 CardReader 类的注册与实例化。"""

    _readers: dict[str, type[CardReader]] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(klass: type[_ReaderT]) -> type[_ReaderT]:
            cls._readers[name] = klass
            return klass
        return decorator

    @classmethod
    def create(cls, name: str, transport: str | None = None, **kwargs) -> CardReader:
        if name not in cls._readers:
            raise ValueError(
                f"Unknown reader: {name}. Available: {list(cls._readers)}"
            )
        reader_cls = cls._readers[name]

        if transport is not None:
            t = TransportRegistry.create(transport, **kwargs)
            return reader_cls(t)

        return reader_cls(**kwargs)

    @classmethod
    def get(cls, name: str) -> type[CardReader]:
        if name not in cls._readers:
            raise ValueError(
                f"Unknown reader: {name}. Available: {list(cls._readers)}"
            )
        return cls._readers[name]

    @classmethod
    def list(cls) -> list[str]:
        return list(cls._readers.keys())


class CardRegistry:
    """卡片注册表，管理 Card 类的注册与实例化。"""

    _cards: dict[str, Union[BaseCard, BaseTag]] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(klass: type[_CardT]) -> type[_CardT]:
            cls._cards[name] = klass
            return klass
        return decorator

    @classmethod
    def create(cls, name: str, reader, **kwargs) -> Union[BaseCard, BaseTag]:
        if name not in cls._cards:
            raise ValueError(
                f"Unknown card: {name}. Available: {list(cls._cards)}"
            )
        return cls._cards[name](reader, **kwargs)

    @classmethod
    def get(cls, name: str) -> type[Union[BaseCard, BaseTag]]:
        if name not in cls._cards:
            raise ValueError(
                f"Unknown card: {name}. Available: {list(cls._cards)}"
            )
        return cls._cards[name]

    @classmethod
    def list(cls) -> list[str]:
        return list(cls._cards.keys())


class Session:
    """会话上下文管理器，封装 reader 的生命周期操作。

    用法:
        with Session("pn532", transport="serial") as s:
            tag = s.find()
            data = s.exchange(b"\\x30\\x00")

    也可以传入已有的 reader:
        with Session(reader=my_reader) as s:
            ...
    """

    def __init__(
        self,
        reader_type: str | None = None,
        reader=None,
        **kwargs,
    ):
        self._reader_type = reader_type
        self._reader = reader
        self._kwargs = kwargs
        self._reader_instance = None

    def __enter__(self) -> "Session":
        if self._reader is not None:
            self._reader_instance = self._reader
        else:
            self._reader_instance = CardReaderRegistry.create(
                self._reader_type, **self._kwargs
            )
        self._reader_instance.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self._reader_instance.disconnect()
        except Exception:
            pass
        return False

    @property
    def reader(self):
        return self._reader_instance

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._reader_instance, name)


@contextmanager
def session(reader_type: str | None = None, reader=None, **kwargs):
    """便捷函数，等价于 Session(...) 的上下文管理器。

    用法:
        with session("pn532", transport="serial") as s:
            tag = s.find()
    """
    s = Session(reader_type=reader_type, reader=reader, **kwargs)
    with s:
        yield s


def load_entry_points():
    """通过 entry-points 自动发现并注册外部 Transport 和 CardReader 实现。"""
    try:
        from importlib.metadata import entry_points

        eps = entry_points()

        transport_eps = eps.select(group="nfctester.transports") if hasattr(eps, 'select') else eps.get("nfctester.transports", [])
        for ep in transport_eps:
            if ep.name not in TransportRegistry._transports:
                klass = ep.load()
                TransportRegistry._transports[ep.name] = klass

        reader_eps = eps.select(group="nfctester.readers") if hasattr(eps, 'select') else eps.get("nfctester.readers", [])
        for ep in reader_eps:
            if ep.name not in CardReaderRegistry._readers:
                klass = ep.load()
                CardReaderRegistry._readers[ep.name] = klass

        card_eps = eps.select(group="nfctester.cards") if hasattr(eps, 'select') else eps.get("nfctester.cards", [])
        for ep in card_eps:
            if ep.name not in CardRegistry._cards:
                klass = ep.load()
                CardRegistry._cards[ep.name] = klass
    except Exception:
        pass
