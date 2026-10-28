"""Tests never touch the network, even when .env has real keys. Tests that need the AI or Sarvam fake them."""
import pytest

from app import config


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setitem(config.RUNTIME, "offline", True)
