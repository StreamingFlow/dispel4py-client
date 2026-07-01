"""Base class for serializable data-transfer objects."""

import json


class SerializableDTO:
    """A payload object that can be serialized to a server-side ``dict``.

    Subclasses implement :meth:`to_dict`; the shared ``__str__`` gives every DTO
    a consistent, readable representation.
    """

    def to_dict(self) -> dict:
        raise NotImplementedError

    def __str__(self) -> str:
        return f"{type(self).__name__}(" + json.dumps(self.to_dict(), indent=4) + ")"
