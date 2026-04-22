import unittest

from lba2_lm2_viewer.viewer import Lm2Error, parse_multipart_upload


def multipart_body(boundary: str, parts: list[tuple[bytes, bytes]]) -> bytes:
    body = bytearray()
    for headers, data in parts:
        body.extend(f"--{boundary}\r\n".encode("ascii"))
        body.extend(headers)
        body.extend(b"\r\n\r\n")
        body.extend(data)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("ascii"))
    return bytes(body)


class ParseMultipartUploadTests(unittest.TestCase):
    def test_parses_file_field_with_quoted_boundary_and_filename(self) -> None:
        boundary = "upload-boundary"
        data = b"lm2 bytes with upload-boundary text\x00\x01"
        body = multipart_body(
            boundary,
            [
                (b'Content-Disposition: form-data; name="comment"', b"ignored"),
                (
                    b'Content-Disposition: form-data; name="file"; filename="model;v1.lm2"\r\n'
                    b"Content-Type: application/octet-stream",
                    data,
                ),
            ],
        )

        result = parse_multipart_upload(f'multipart/form-data; boundary="{boundary}"', body)

        self.assertEqual(result["filename"], "model;v1.lm2")
        self.assertEqual(result["data"], data)

    def test_missing_file_field_raises(self) -> None:
        boundary = "upload-boundary"
        body = multipart_body(
            boundary,
            [(b'Content-Disposition: form-data; name="not_file"', b"ignored")],
        )

        with self.assertRaisesRegex(Lm2Error, "upload did not include a file field"):
            parse_multipart_upload(f"multipart/form-data; boundary={boundary}", body)

    def test_non_multipart_upload_raises(self) -> None:
        with self.assertRaisesRegex(Lm2Error, "expected multipart/form-data upload"):
            parse_multipart_upload("application/octet-stream", b"raw bytes")


if __name__ == "__main__":
    unittest.main()
