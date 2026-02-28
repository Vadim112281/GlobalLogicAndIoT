import csv

class FileDatasource:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.file = None
        self.reader = None

    def start_reading(self):
        """Відкриває файл для читання."""
        self.file = open(self.filepath, 'r', encoding='utf-8')
        # Передбачається, що CSV має заголовки, напр.: latitude,longitude,road_state
        self.reader = csv.DictReader(self.file)

    def read(self):
        """Читає наступний рядок з файлу."""
        if self.reader:
            try:
                return next(self.reader)
            except StopIteration:
                return None
        return None

    def stop_reading(self):
        """Закриває файл."""
        if self.file:
            self.file.close()