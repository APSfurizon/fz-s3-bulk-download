import os
import time
import json
import hmac
import boto3
import base64
import hashlib
from datetime import datetime
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from stream_zip import stream_zip, ZIP_64

app = FastAPI()

s3_client = boto3.client(
    service_name='s3',
    aws_access_key_id=os.environ["AWS_ACCESS_KEY"],
    aws_secret_access_key=os.environ["AWS_SECRET_KEY"],
    endpoint_url=os.environ.get("AWS_ENDPOINT_URL", None),
    region_name=os.environ.get("AWS_REGION", None),
)
S3_BUCKET = os.environ.get("S3_BUCKET", "test")

HMAC_KEY = os.environ["HMAC_KEY"].encode()

ZIP_FILENAME_PREPEND = os.environ.get("ZIP_FILENAME_PREPEND", "gallery_")


def generate_zip_stream(files: list):
    """
    Generator that yields chunks of the resulting ZIP file.
    """
    def member_files():
        for file in files:

            response = s3_client.get_object(Bucket=S3_BUCKET, Key=file["k"])
            s3_stream = response['Body']
            
            def file_chunks():
                for chunk in s3_stream.iter_chunks(chunk_size=65536):
                    yield chunk
            
            yield (
                f'{file["ne"]}/{file["np"]}/{file["nf"]}',  # Filename
                datetime.fromisoformat(file["t"]),          # Timestamp for the file inside the zip
                0o600,                                      # File permissions inside the zip
                ZIP_64,                                     # Zip format
                file_chunks()                               # The streaming data from S3
            )

    for zipped_chunk in stream_zip(member_files()):
        yield zipped_chunk

@app.post("/d")
async def bulkDownload(request: Request, mac: str):
    data = await request.body()
    data = base64.b64decode(data)
    mac = bytes.fromhex(mac)
    computed = hmac.new(HMAC_KEY, data, hashlib.sha256).digest()
    if computed != mac:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"error": "Invalid HMAC"})
    
    data = json.loads(data)
    #TODO TODO TODO
    if int(time.time() * 1000) > data["expiryMs"]:
        pass #return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"error": "Request expired"})
    
    # TODO CHECK IF SAME USER IS NOT ALREADY DOWNLOADING OTHER FILES
    
    return StreamingResponse(
        generate_zip_stream(data["files"]),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={ZIP_FILENAME_PREPEND}{int(time.time())}.zip"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8083)
