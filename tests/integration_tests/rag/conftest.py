import pytest 

@pytest.fixture(scope="module")
def get_docs() -> list:

    docs = [
        "Apple is deep red",
        "Pear is light yellow",
        "Watermelon is green on the outside and red on the inside",
    ]
    return docs