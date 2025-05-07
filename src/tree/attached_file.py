class AttachedFile:
    def __init__(self, name, type, size, content) -> None:
        self.name: str = name
        self.type: str = type
        self.size: int = size
        self.content: str = content

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        if isinstance(name, str):
            self._name = name
        else:
            raise ValueError("Name must be a string.")

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, type):
        if isinstance(type, str):
            self._type = type
        else:
            raise ValueError("Type must be a string.")

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, size):
        if isinstance(size, int):
            self._size = size
        else:
            raise ValueError("Size must be an integer.")

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, content):
        if isinstance(content, str):
            self._content = content
        else:
            raise ValueError("Content must be a string.")

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

