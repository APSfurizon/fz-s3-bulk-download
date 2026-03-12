"""
In python using any http webserver framework, I want to retrieve files from an s3 server, merge them together in a single zip file and reply to the user with it.  However, I DON'T want to retrieve all files first (both in memory or on disk), then zip and then reply. I want to use streams, to while I download the file from the s3, I add it to the zip, then pass to the next file and so on, while the user keeps downloading the file

This is a fantastic architectural choice. Downloading large files into memory or onto disk before zipping is a common trap that leads to Out-Of-Memory (OOM) crashes and slow Time-To-First-Byte (TTFB) for the user. Streaming everything from S3 straight through your server and to the client is exactly how you want to build this.

### The Challenge

The built-in Python `zipfile` module is tricky to use for pure streaming because it historically wants to seek to the end of a file to write the central directory. While there are workarounds, it usually involves buffering.

### The Solution

To achieve true, bufferless streaming, the standard industry practice is to use a library specifically built for this, like **`stream-zip`**. We'll combine this with **FastAPI** (for its excellent `StreamingResponse`) and **boto3** (to read from S3).

Here is the complete recipe to achieve this.

### Prerequisites

You'll need to install these packages:

```bash
pip install fastapi uvicorn boto3 stream-zip

```

### How it works:

1. **The Request:** The user hits the endpoint.
2. **The S3 Call:** `boto3` contacts S3 but only asks to open a connection to the first file. It gets a `StreamingBody` back.
3. **The Chunking:** Our inner generator reads a tiny chunk (64KB) from S3 and hands it to `stream-zip`.
4. **The Zipping:** `stream-zip` compresses that 64KB chunk and hands it to FastAPI.
5. **The Response:** FastAPI pushes that compressed chunk straight to the user's browser over HTTP.

This process repeats chunk by chunk, file by file. Your server memory usage will remain flat and minimal, no matter if you are zipping 10 Megabytes or 100 Gigabytes of data.

---

**Would you like me to adapt this example to use an asynchronous S3 client (like `aioboto3`) if you are expecting very high concurrent traffic?**
"""

# HURR DURR YOU'RE USING AI INSTEAD OF PROGRAMMING IT BY YOURSELF!!!
# Man, I'm doing this for free as a volunteer instead of dedicating time to myself, my life, my thesis, my partner i love. If I can save time, why not

from datetime import datetime
import boto3
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from stream_zip import stream_zip, ZIP_64

app = FastAPI()

# Initialize your S3 client (ensure you have your AWS credentials configured)
s3_client = boto3.client('s3')

def generate_zip_stream(bucket_name: str, file_keys: list):
    """
    Generator that yields chunks of the resulting ZIP file.
    """
    def member_files():
        for key in file_keys:
            # 1. Ask S3 for the file. This returns a StreamingBody, 
            # so it doesn't download the file into memory.
            response = s3_client.get_object(Bucket=bucket_name, Key=key)
            s3_stream = response['Body']
            
            # 2. Create a generator that yields chunks of the S3 file
            def file_chunks():
                # 65536 bytes (64KB) is a good chunk size for network streaming
                for chunk in s3_stream.iter_chunks(chunk_size=65536):
                    yield chunk
            
            # 3. stream-zip expects a tuple for each file:
            # (filename, modified_at, permissions, compression_method, data_iterable)
            # Using ZIP_64 allows for files larger than 4GB.
            yield (
                key,                 # Use the S3 key as the filename in the zip
                datetime.now(),      # Timestamp for the file inside the zip
                0o600,               # File permissions inside the zip
                ZIP_64,              # Zip format
                file_chunks()        # The streaming data from S3
            )

    # 4. stream_zip consumes the member_files generator and yields zipped bytes
    for zipped_chunk in stream_zip(member_files()):
        yield zipped_chunk


@app.get("/download-zipped-s3-files")
def download_zipped_s3_files():
    # Example bucket and keys you want to zip
    bucket = "my-aws-storage-bucket"
    keys_to_zip = ["docs/report.pdf", "images/photo1.jpg", "data/huge-export.csv"]

    # Set headers so the browser triggers a file download
    headers = {
        "Content-Disposition": "attachment; filename=my_s3_files.zip"
    }

    # Pass our generator directly to FastAPI's StreamingResponse
    return StreamingResponse(
        generate_zip_stream(bucket, keys_to_zip),
        media_type="application/zip",
        headers=headers
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
