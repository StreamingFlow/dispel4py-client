import json

class SearchData:
    def __init__(self, *, search: str, search_type: bool):
        self.search = search
        self.search_type = search_type

    def to_dict(self):
        return {
            "search": self.search,
            "searchType": self.search_type,
        }

    def __str__(self):
        return "SearchData(" + json.dumps(self.to_dict(), indent=4) + ")"
