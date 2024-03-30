import logging

import pytest


class Fruit:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return self.name == other.name


@pytest.fixture
def my_fruit():
    logging.info("Setup 1")
    yield Fruit("apple")
    logging.info("teardown1")


@pytest.fixture
def fruit_basket(my_fruit):
    logging.info("setup2")
    return [Fruit("banana"), my_fruit]


def test_my_fruit_in_basket(my_fruit, fruit_basket, dut, json_metadata, sig_gen, spec_an):
    logging.info("call1")
    json_metadata["result"] = [1, 2, 3]
    assert my_fruit in fruit_basket
