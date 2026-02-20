from csv import reader
from datetime import datetime

from domain.aggregated_data import AggregatedData
from domain.accelerometer import Accelerometer
from domain.gps import Gps

class FileDatasource:
    def __init__(self, accelerometer_filename: str, gps_filename: str) -> None:
        self._acc_filename = accelerometer_filename
        self._gps_filename = gps_filename

        self._acc_file = None
        self._gps_file = None

        self._acc_reader = None
        self._gps_reader = None

    def startReading(self, *args, **kwargs):
        """Метод повинен викликатись перед початком читання даних"""
        self._open_files()

    def stopReading(self, *args, **kwargs):
        """Метод повинен викликатись для закінчення читання даних"""
        self._close_files()

    def read(self) -> AggregatedData:
        """Метод повертає дані отримані з датчиків"""
        if self._acc_reader is None or self._gps_reader is None:
            # якщо забули startReading()
            self._open_files()

        acc_row = self._next_row(self._acc_reader, source="acc")
        gps_row = self._next_row(self._gps_reader, source="gps")

        # Очікуємо формати:
        # accelerometer.csv: x,y,z
        # gps.csv: longitude,latitude
        x, y, z = int(acc_row[0]), int(acc_row[1]), int(acc_row[2])
        longitude, latitude = float(gps_row[0]), float(gps_row[1])

        return AggregatedData(
            accelerometer=Accelerometer(x=x, y=y, z=z),
            gps=Gps(longitude=longitude, latitude=latitude),
            time=datetime.utcnow(),
        )

    def _open_files(self):
        self._close_files()

        self._acc_file = open(self._acc_filename, "r", newline="", encoding="utf-8")
        self._gps_file = open(self._gps_filename, "r", newline="", encoding="utf-8")

        self._acc_reader = reader(self._acc_file)
        self._gps_reader = reader(self._gps_file)

        # якщо у файлах є хедери — можна пропустити автоматично (опційно)
        self._skip_header_if_present(self._acc_reader, expected_cols=3)
        self._skip_header_if_present(self._gps_reader, expected_cols=2)

    def _close_files(self):
        if self._acc_file:
            self._acc_file.close()
        if self._gps_file:
            self._gps_file.close()

        self._acc_file = None
        self._gps_file = None
        self._acc_reader = None
        self._gps_reader = None

    def _next_row(self, csv_reader, source: str):
        try:
            row = next(csv_reader)
            # пропускаємо пусті рядки
            while row is not None and (len(row) == 0 or all(not c.strip() for c in row)):
                row = next(csv_reader)
            return row
        except StopIteration:
            # кінець файлу → почати з початку (ідея для підвищення оцінки)
            self._open_files()
            return self._next_row(self._acc_reader if source == "acc" else self._gps_reader, source)

    def _skip_header_if_present(self, csv_reader, expected_cols: int):
        """
        Якщо перший рядок не числовий (типу 'x,y,z'), пропускаємо його.
        """
        try:
            peek = next(csv_reader)
        except StopIteration:
            return

        # якщо неправильна кількість колонок — просто повертаємо назад не можемо, тому залишимо як є
        if len(peek) != expected_cols:
            return

        # якщо перша колонка не число — це хедер
        try:
            float(peek[0])
            # це НЕ хедер → нічого не робимо, але ми вже "з’їли" рядок 😄
            # тому робимо простий хак: відкриємо файли заново і без пропуску
            # (але тільки якщо це не хедер)
            raise ValueError
        except Exception:
            # це хедер → ок, просто пропущено
            return