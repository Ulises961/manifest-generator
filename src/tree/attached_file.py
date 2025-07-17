class AttachedFile:
    def __init__(self, name, type, size, content) -> None:
        self._name: str = name
        self._type: str = type
        self._size: int = size
        self._content: str = content

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        if isinstance(name, str):
            self._name = name
        else:
            raise ValueError(f"Name must be a string. Got {type(name)} instead.")

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, type):
        if isinstance(type, str):
            self._type = type
        else:
            raise ValueError(f"Type must be a string. Got {type(type)} instead.")

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, size):
        if isinstance(size, int):
            self._size = size
        else:
            raise ValueError(f"Size must be an integer. Got {type(size)} instead.")

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, content):
        if isinstance(content, str):
            self._content = content
        else:
            raise ValueError(f"Content must be a string. Got {type(content)} instead.")

    def __to_dict__(self):
        return {
            "name": self.name,
            "type": self.type,
            "size": self.size,
            "content": self.content,
        }

    def __repr__(self):
        return f"AttachedFile(name={self.name}, type={self.type}, size={self.size}, content={self.content})"

    def __eq__(self, value):
        if not isinstance(value, AttachedFile):
            return False
        return (
            self.name == value.name
            and self.type == value.type
            and self.size == value.size
            and self.content == value.content
        )

