import csv
import io


def stream_rows_to_csv(rows, columns, batch_size=10_000):
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(columns)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    batch = []

    for row in rows:
        batch.append(row)

        if len(batch) == batch_size:
            writer.writerows(batch)
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            batch.clear()

    if batch:
        writer.writerows(batch)
        yield buffer.getvalue()
