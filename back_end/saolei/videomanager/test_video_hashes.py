from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from django.test import SimpleTestCase

from .utils import calculate_original_hash


class OriginalHashTests(SimpleTestCase):
    def test_hashes_entire_memory_or_temporary_upload_and_rewinds_for_parser(self):
        uploads = [SimpleUploadedFile('hash.evf', b'abc'), TemporaryUploadedFile('hash.evf', 'application/octet-stream', 3, None)]
        for upload in uploads:
            with self.subTest(upload=type(upload).__name__), upload:
                if isinstance(upload, TemporaryUploadedFile):
                    upload.write(b'abc')
                upload.seek(2)
                self.assertEqual(calculate_original_hash(upload), 'ba7816bf8f01cfea414140de')
                self.assertEqual(upload.tell(), 0)
                self.assertEqual(upload.read(), b'abc')
